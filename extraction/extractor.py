import json
import logging
import os
import time
import uuid
from typing import List, Dict, Any

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


def _load_previous_extraction_cache() -> dict:
    cache_path = os.path.join(settings.data_dir, "extracted_concepts.json")
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        lookup = {}
        for concept in data.get("concepts", []):
            src = concept.get("source_reference", {})
            chunk_id = src.get("chunk_id")
            content_hash = src.get("content_hash")
            if chunk_id and content_hash:
                key = f"{chunk_id}:{content_hash}"
                lookup.setdefault(key, []).append(concept)
        return lookup
    except Exception:
        logging.warning("Could not load previous extracted_concepts.json for caching — treating as full cache miss")
        return {}


class ConceptExtractor:
    def __init__(self):
        self.gemini_api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.groq_api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")

        self.gemini_client = None
        self.groq_client = None

        if self.gemini_api_key and GEMINI_SDK_AVAILABLE:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
            self.primary_provider = "gemini"
            logging.info("ConceptExtractor primary provider: Gemini 2.5 Flash (google-genai SDK)")

        if self.groq_api_key and GROQ_SDK_AVAILABLE:
            self.groq_client = Groq(api_key=self.groq_api_key)
            if not self.gemini_client:
                self.primary_provider = "groq"
            logging.info("ConceptExtractor secondary/fallback provider: Groq (llama-3.3-70b-versatile)")

        if not self.gemini_client and not self.groq_client:
            raise ValueError("Neither GEMINI_API_KEY nor GROQ_API_KEY is available with required SDK.")

    def _extract_with_gemini(self, prompt: str, system_instruction: str) -> str:
        schema = {
            "type": "OBJECT",
            "properties": {
                "concepts": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "concept_name": {"type": "STRING"},
                            "definition": {"type": "STRING"},
                            "keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "relationships": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "target": {"type": "STRING"},
                                        "type": {"type": "STRING"}
                                    },
                                    "required": ["target", "type"]
                                }
                            }
                        },
                        "required": ["concept_name", "definition", "keywords", "relationships"]
                    }
                }
            },
            "required": ["concepts"]
        }

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
                        "temperature": settings.gemini_temperature
                    }
                )
                return response.text
            except Exception as e:
                err_msg = str(e)
                if ("429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg) and attempt < max_retries - 1:
                    logging.warning(f"Gemini API rate limit hit (429). Retrying in {delay}s... (attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                    delay *= 2.0
                else:
                    raise e
        raise RuntimeError("Exhausted retries for Gemini API")

    def _extract_with_groq(self, prompt: str, system_instruction: str) -> str:
        response = self.groq_client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return response.choices[0].message.content

    def extract_from_chunk(self, text: str) -> List[Dict[str, Any]]:
        prompt = f"""
Extract meaningful educational concepts from the following text.
Extract actual concepts a student could learn, not generic terms.
Concept extraction must be grounded STRICTLY in the supplied text.
Do not invent concepts or definitions not present in the text.

Text:
{text}
"""
        system_instruction = (
            "You are an AI educational extraction engine. "
            "You must output valid JSON matching this schema: "
            "{\"concepts\": [{\"concept_name\": \"string\", \"definition\": \"string\", "
            "\"keywords\": [\"string\"], \"relationships\": [{\"target\": \"string\", \"type\": \"requires|related_to|part_of\"}]}]}"
        )

        result_json = None

        if self.gemini_client:
            try:
                result_json = self._extract_with_gemini(prompt, system_instruction)
            except Exception as e:
                logging.warning(f"Gemini extraction failed ({e}). Trying fallback provider...")
                if self.groq_client:
                    try:
                        result_json = self._extract_with_groq(prompt, system_instruction)
                    except Exception as ge:
                        logging.error(f"Groq fallback extraction also failed: {ge}")
                else:
                    logging.error(f"Gemini extraction failed and no Groq fallback available: {e}")

        elif self.groq_client:
            try:
                result_json = self._extract_with_groq(prompt, system_instruction)
            except Exception as e:
                logging.error(f"Groq extraction failed: {e}")

        if result_json:
            try:
                result_data = json.loads(result_json)
                return result_data.get("concepts", [])
            except Exception as e:
                logging.error(f"Failed to parse LLM JSON output: {e}")
                return []

        return []

    def process_ingestion_result(self, ingestion_data: dict) -> List[Dict[str, Any]]:
        all_concepts = []
        subject_id = ingestion_data.get("subject_id")

        extraction_cache = _load_previous_extraction_cache()

        for resource in ingestion_data.get("resources", []):
            resource_id = resource.get("resource_id")
            resource_type = resource.get("resource_type")
            filename = resource.get("filename")

            for chunk in resource.get("content", []):
                text = chunk.get("text", "").strip()
                if not text:
                    continue

                chunk_id = chunk.get("chunk_id", chunk.get("content_id", ""))
                content_hash = chunk.get("content_hash", "")
                location_type = chunk.get("location_type")
                location_number = chunk.get("location_number")

                cache_key = f"{chunk_id}:{content_hash}" if chunk_id and content_hash else None
                if cache_key and cache_key in extraction_cache:
                    logging.info(f"CACHE HIT (unchanged): chunk {chunk_id}")
                    all_concepts.extend(extraction_cache[cache_key])
                    continue

                logging.info(f"CACHE MISS (extracting): chunk {chunk_id}")
                logging.info(f"Processing {resource_type.upper()} {location_type} {location_number} ({filename})")

                concepts = self.extract_from_chunk(text)
                logging.info(f"Extracted {len(concepts)} concept mention(s)")

                for concept in concepts:
                    concept_mention = {
                        "concept_id": f"mention_{uuid.uuid4().hex[:8]}",
                        "concept_name": concept.get("concept_name", ""),
                        "definition": concept.get("definition", ""),
                        "keywords": concept.get("keywords", []),
                        "relationships": [
                            {"target": r.get("target"), "type": r.get("type")}
                            for r in concept.get("relationships", [])
                        ],
                        "source_reference": {
                            "resource_id": resource_id,
                            "resource_type": resource_type,
                            "filename": filename,
                            "chunk_id": chunk_id,
                            "content_hash": content_hash,
                        },
                        "workspace_id": subject_id
                    }

                    if location_type == "page":
                        concept_mention["source_reference"]["page_number"] = location_number
                    elif location_type == "slide":
                        concept_mention["source_reference"]["slide_number"] = location_number

                    all_concepts.append(concept_mention)

        return all_concepts
