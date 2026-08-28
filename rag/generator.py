import json
import logging
import re
from typing import List, Optional, Tuple

from llm_provider import LLMProvider
from rag.evidence import format_for_prompt
from rag.models import TYPE_A, TYPE_B, Citation

ANSWER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "answer": {"type": "STRING"},
        "used_citations": {"type": "ARRAY", "items": {"type": "INTEGER"}},
        "sufficient_evidence": {"type": "BOOLEAN"},
        "flags": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["answer", "used_citations", "sufficient_evidence", "flags"],
}

_TYPE_GUIDANCE = {
    TYPE_A: ("Define the concept as the material defines it. Lead with the "
             "definition, then add what the evidence says about how it is used."),
    TYPE_B: ("Answer with the relationships the evidence establishes. State each "
             "relationship explicitly and in the correct direction."),
}
_DEFAULT_GUIDANCE = ("Answer the question directly from the evidence. Explain "
                     "using only what the sources state.")


class AnswerGenerator:
    """
    Generates an answer constrained to the assembled evidence.

    The model is told to cite by bracketed number and to declare when the
    evidence is insufficient. Citations it claims to have used are then checked
    against the ones actually supplied — a claim to have used [7] when only six
    citations exist is a fabrication signal, and is flagged rather than trusted.
    """

    def __init__(self, llm: Optional[LLMProvider] = None):
        self.llm = llm or LLMProvider()

    def generate(self, query: str, query_type: str,
                 citations: List[Citation]) -> Tuple[dict, str]:
        if not citations:
            return {
                "answer": "I could not find anything in the indexed material that "
                          "addresses this question.",
                "used_citations": [],
                "sufficient_evidence": False,
                "flags": ["no_evidence_retrieved"],
            }, ""

        guidance = _TYPE_GUIDANCE.get(query_type, _DEFAULT_GUIDANCE)
        prompt = f"""
Answer the question using ONLY the numbered evidence below.

QUESTION: {query}

EVIDENCE:
{format_for_prompt(citations)}

APPROACH FOR THIS QUESTION: {guidance}

RULES — all mandatory:
- Use ONLY the evidence above. Your own knowledge of this subject is NOT a
  source. If the evidence does not answer the question, say so plainly and set
  "sufficient_evidence" to false — that is a correct outcome, not a failure.
- Cite every claim with its bracketed number, e.g. "SGD updates weights after
  each example [3]". Cite only numbers that appear above.
- Do NOT add definitions, caveats, or context the evidence does not contain.
- If the evidence is partial, answer what it supports and state what is missing.
- If evidence items contradict each other, say so rather than picking one.
- Keep the answer concise and factual. No preamble.
- List every citation number you actually used in "used_citations".
- Use "flags" for problems the reader should know about, such as
  "partial_evidence", "conflicting_sources", or "ocr_quality" when the quoted
  text is visibly garbled.
"""
        system_instruction = (
            "You answer questions strictly from supplied evidence about educational "
            'material. Output valid JSON: {"answer": "string with [n] citations", '
            '"used_citations": [1,2], "sufficient_evidence": true, "flags": []}'
        )

        result = self.llm.call(prompt, system_instruction, ANSWER_SCHEMA)
        if result is None:
            return {
                "answer": "Answer generation is unavailable — every model provider failed.",
                "used_citations": [], "sufficient_evidence": False,
                "flags": ["generation_failed"],
            }, ""

        raw, model_used = result
        try:
            data = json.loads(raw)
        except Exception as e:
            logging.error(f"Failed to parse answer JSON: {e}")
            return {
                "answer": "The answer could not be parsed from the model response.",
                "used_citations": [], "sufficient_evidence": False,
                "flags": ["parse_failure"],
            }, model_used

        return self._validate(data, citations), model_used

    def _validate(self, data: dict, citations: List[Citation]) -> dict:
        valid = {c.index for c in citations}
        flags = [str(f) for f in (data.get("flags") or [])]

        claimed = [int(n) for n in (data.get("used_citations") or []) if isinstance(n, int)]
        kept = [n for n in claimed if n in valid]
        if len(kept) != len(claimed):
            flags.append("invalid_citation_removed")

        # Numbers cited inline but never supplied are the more dangerous case:
        # the answer text looks sourced while pointing at nothing.
        answer = data.get("answer", "")
        inline = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
        if inline - valid:
            flags.append("hallucinated_citation")
            logging.warning(f"Answer cited non-existent evidence: {sorted(inline - valid)}")
        # A refusal legitimately has nothing to cite, so only an answer that
        # claims to be grounded is suspicious for carrying no citations.
        if answer and not inline and data.get("sufficient_evidence"):
            flags.append("uncited_answer")

        return {
            "answer": answer,
            "used_citations": sorted(set(kept) | (inline & valid)),
            "sufficient_evidence": bool(data.get("sufficient_evidence", False)),
            "flags": sorted(set(flags)),
        }
