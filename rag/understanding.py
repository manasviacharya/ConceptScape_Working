import json
import logging
import re
from typing import List, Optional

from llm_provider import LLMProvider
from rag.models import TYPE_A, TYPE_B, TYPE_C, QueryUnderstanding

UNDERSTANDING_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "query_type": {"type": "STRING"},
        "concepts": {"type": "ARRAY", "items": {"type": "STRING"}},
        "reasoning": {"type": "STRING"},
    },
    "required": ["query_type", "concepts", "reasoning"],
}

# Verbs that signal the question is about how concepts relate, not what one is.
_RELATION_HINTS = re.compile(
    r"\b(require|requires|need|needs|depend|depends|prerequisite|part of|"
    r"related|relate|relates|cause|causes|produce|produces|used for|"
    r"difference between|compare|versus|vs\.?)\b",
    re.IGNORECASE,
)
_LOOKUP_HINTS = re.compile(r"^\s*(what\s+is|what\s+are|define|definition of)\b", re.IGNORECASE)


class QueryUnderstander:
    """
    Classifies the query and names the concepts it refers to, in ONE call.

    Doing both together is deliberate: classification and concept identification
    need the same context, and a second round trip would double the per-question
    cost against a daily-quota provider.

    Concept identification here is what closes the paraphrase gap — the full
    concept list fits in a prompt at this corpus size, so the model can map
    "how do I stop overshooting" onto "Learning Rate" without embeddings.
    """

    def __init__(self, concept_names: List[str], llm: Optional[LLMProvider] = None):
        self.concept_names = concept_names
        self.llm = llm or LLMProvider()

    def _heuristic(self, query: str) -> str:
        """Cheap fallback used only when the LLM is unavailable."""
        if _RELATION_HINTS.search(query):
            return TYPE_B
        if _LOOKUP_HINTS.search(query) or len(query.split()) <= 3:
            return TYPE_A
        return TYPE_C

    def understand(self, query: str) -> QueryUnderstanding:
        listed = "\n".join(f"- {n}" for n in self.concept_names)
        prompt = f"""
Classify the question and identify which of the known concepts it refers to.

QUESTION: {query}

QUERY TYPES:
- "A" = concept lookup. The user wants to know what a single concept IS.
        e.g. "Gradient Descent", "what is SGD?", "define batch size"
- "B" = relationship query. The user asks how concepts relate to each other.
        e.g. "what does mini-batch SGD require?", "what causes overshoot?",
        "difference between batch and stochastic gradient descent"
- "C" = open question. Anything else needing an explanation drawn from the
        material. e.g. "why is a small learning rate slow?"

KNOWN CONCEPTS:
{listed}

RULES:
- "concepts" MUST contain names copied EXACTLY from the list above.
- Include a concept when the question refers to it even using different words:
  "how do I stop overshooting the minimum" refers to concepts about step size
  and overshoot, even though it names neither.
- If the question refers to no known concept, return an empty list. Do NOT
  invent a concept name that is not listed.
- Return at most 5 concepts, most relevant first.
"""
        system_instruction = (
            "You classify questions about an educational knowledge base. "
            'Output valid JSON: {"query_type": "A"|"B"|"C", '
            '"concepts": ["exact name from the list"], "reasoning": "one sentence"}'
        )

        result = self.llm.call(prompt, system_instruction, UNDERSTANDING_SCHEMA)
        if result is None:
            qt = self._heuristic(query)
            logging.warning(f"Query understanding unavailable — falling back to heuristic (type {qt})")
            return QueryUnderstanding(query_type=qt, concepts=[], reasoning="heuristic fallback")

        raw, model_used = result
        try:
            data = json.loads(raw)
        except Exception as e:
            logging.error(f"Failed to parse query understanding: {e}")
            return QueryUnderstanding(query_type=self._heuristic(query), reasoning="parse failure")

        qt = str(data.get("query_type", "")).strip().upper()
        if qt not in (TYPE_A, TYPE_B, TYPE_C):
            qt = self._heuristic(query)

        # Only keep concept names that actually exist — the model is instructed
        # not to invent them, but this is the guarantee rather than the request.
        known = {n.casefold(): n for n in self.concept_names}
        concepts = []
        for c in data.get("concepts", [])[:5]:
            match = known.get(str(c).strip().casefold())
            if match and match not in concepts:
                concepts.append(match)

        return QueryUnderstanding(
            query_type=qt,
            concepts=concepts,
            reasoning=str(data.get("reasoning", ""))[:300],
            model_used=model_used,
        )
