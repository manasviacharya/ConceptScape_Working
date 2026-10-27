import logging
import os
import threading
import time
from typing import Any

from config import settings

try:
    from google import genai
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    GEMINI_SDK_AVAILABLE = False

try:
    from groq import Groq
    GROQ_SDK_AVAILABLE = True
except ImportError:
    GROQ_SDK_AVAILABLE = False


def is_rate_limit(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()


class LLMProvider:
    """
    Gemini primary, Groq fallback, shared by every stage that calls an LLM.

    Circuit breaker: once Gemini has rate-limited `gemini_rate_limit_trip_after`
    times in a run, it is disabled for the remainder. Without this, a daily
    quota makes every single call sit through the full retry backoff before
    falling back — minutes of sleeping per chunk, for nothing.
    """

    # Breaker state is class-level, not per-instance. Each pipeline stage builds
    # its own LLMProvider, so instance-level state meant a daily quota that was
    # already exhausted got re-probed — and its full retry backoff paid — once
    # per stage. Exhaustion is a property of the account, not of one object.
    #
    # The lock matters now that the model-calling stages issue their calls on a
    # thread pool: without it concurrent 429s race on the counter and the
    # breaker trips early or late depending on interleaving.
    _gemini_rate_limit_hits = 0
    _gemini_disabled = False
    _breaker_lock = threading.Lock()

    # Wall-clock instant before which no worker should issue a call.
    #
    # Per-call retry alone cannot fix a per-minute quota: with several workers
    # running, each one backs off independently and they all return together,
    # producing the same burst that caused the limit. One shared deadline makes
    # a 429 slow every worker down, which is the only thing a rate limit
    # actually responds to.
    _cooldown_until = 0.0
    _cooldown_lock = threading.Lock()

    @classmethod
    def _wait_for_cooldown(cls) -> None:
        while True:
            with cls._cooldown_lock:
                remaining = cls._cooldown_until - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 1.0))

    @classmethod
    def _start_cooldown(cls, seconds: float, provider: str) -> None:
        until = time.monotonic() + seconds
        with cls._cooldown_lock:
            if until <= cls._cooldown_until:
                return          # a longer pause is already in force
            cls._cooldown_until = until
        logging.warning(f"{provider} rate limit — pausing all workers for {seconds:.0f}s")

    def __init__(self):
        self.gemini_api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.groq_api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")

        self.gemini_client = None
        self.groq_client = None
        if self.gemini_api_key and GEMINI_SDK_AVAILABLE:
            self.gemini_client = genai.Client(
                api_key=self.gemini_api_key,
                http_options={"retry_options": {"attempts": 1}}
            )
            logging.info(f"LLM primary provider: Gemini ({settings.gemini_model})")

        if self.groq_api_key and GROQ_SDK_AVAILABLE:
            self.groq_client = Groq(api_key=self.groq_api_key)
            logging.info(f"LLM fallback provider: Groq ({settings.groq_model})")

        if not self.gemini_client and not self.groq_client:
            raise ValueError("Neither GEMINI_API_KEY nor GROQ_API_KEY is available with required SDK.")

    def _call_gemini(self, prompt: str, system_instruction: str, schema: dict[str, Any]) -> str:
        max_retries = settings.gemini_max_retries
        delay = settings.gemini_retry_base_delay
        for attempt in range(max_retries):
            try:
                response = self.gemini_client.models.generate_content(
                    model=settings.gemini_model,
                    contents=prompt,
                    config={
                        "system_instruction": system_instruction,
                        "response_mime_type": "application/json",
                        "response_schema": schema,
                        "temperature": settings.gemini_temperature,
                    },
                )
                return response.text
            except Exception as e:
                if is_rate_limit(e) and attempt < max_retries - 1:
                    logging.warning(
                        f"Gemini rate limit. Retrying in {delay}s (attempt {attempt+1}/{max_retries})"
                    )
                    time.sleep(delay)
                    delay *= 2.0
                else:
                    raise
        raise RuntimeError("Exhausted retries for Gemini API")

    def _call_groq(self, prompt: str, system_instruction: str) -> str:
        response = self.groq_client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=settings.groq_temperature,
        )
        return response.choices[0].message.content

    def call(
        self, prompt: str, system_instruction: str, schema: dict[str, Any]
    ) -> tuple[str, str] | None:
        """
        Returns (raw_json, model_used), or None if every provider failed.

        None is distinct from an empty result: it means "do not cache this,
        retry on a later run". That distinction is what makes a quota-limited
        run resumable rather than destructive.
        """
        self._wait_for_cooldown()

        if self.gemini_client and not self._gemini_disabled:
            try:
                return self._call_gemini(prompt, system_instruction, schema), settings.gemini_model
            except Exception as e:
                if is_rate_limit(e):
                    with LLMProvider._breaker_lock:
                        LLMProvider._gemini_rate_limit_hits += 1
                        tripped = (LLMProvider._gemini_rate_limit_hits
                                   >= settings.gemini_rate_limit_trip_after
                                   and not LLMProvider._gemini_disabled)
                        hits = LLMProvider._gemini_rate_limit_hits
                        if tripped:
                            LLMProvider._gemini_disabled = True
                            logging.warning(
                                f"Gemini rate-limited {hits} times — disabling Gemini "
                                f"for the rest of this run, using Groq only."
                            )
                        elif not LLMProvider._gemini_disabled:
                            logging.info(
                                f"Gemini rate limit {hits}/"
                                f"{settings.gemini_rate_limit_trip_after} — still primary."
                            )
                    # Only pause everyone if there is no fallback to fall back
                    # to. When Gemini's daily quota is spent, every call 429s
                    # and Groq serves the request anyway — pausing on those
                    # would throttle the provider that is actually working,
                    # which is the opposite of what the cooldown is for. Groq's
                    # own limits drive the pause in that case.
                    if not self.groq_client:
                        self._start_cooldown(settings.rate_limit_cooldown_seconds, "Gemini")
                logging.warning(f"Gemini call failed ({str(e)[:120]}). Trying fallback...")

        if self.groq_client:
            try:
                self._wait_for_cooldown()
                return self._call_groq(prompt, system_instruction), settings.groq_model
            except Exception as e:
                if is_rate_limit(e):
                    # Groq limits tokens per minute, so the useful response is
                    # to stop sending for a while rather than to keep retrying
                    # into a closed window.
                    self._start_cooldown(settings.rate_limit_cooldown_seconds, "Groq")
                logging.error(f"Groq call failed: {str(e)[:200]}")

        return None
