from dataclasses import dataclass, field
from typing import Any, Dict, List

# Query taxonomy. Routing differs per type because the evidence that answers a
# "what is X" question is not the evidence that answers "what does X require".
TYPE_A = "A"  # concept lookup      — "Gradient Descent", "what is SGD?"
TYPE_B = "B"  # relationship query  — "what does mini-batch SGD require?"
TYPE_C = "C"  # open question       — "why does momentum cause overshoot?"

QUERY_TYPES = {
    TYPE_A: "concept lookup",
    TYPE_B: "relationship query",
    TYPE_C: "question answering",
}


@dataclass
class QueryUnderstanding:
    query_type: str
    concepts: List[str] = field(default_factory=list)
    reasoning: str = ""
    model_used: str = ""


@dataclass
class Citation:
    """
    One numbered piece of evidence offered to the generator.

    Every field below is what makes the answer auditable — the reader can walk
    back from a bracketed number in the answer to a page in a source document.
    """
    index: int
    kind: str                       # "concept" | "relationship" | "chunk"
    text: str
    concept_name: str = ""
    filename: str = ""
    page_number: int = 0
    chunk_id: str = ""
    relationship: str = ""          # "A -requires-> B" for relationship evidence

    def label(self) -> str:
        where = self.filename or "?"
        if self.page_number:
            where += f" p{self.page_number}"
        return where


@dataclass
class Answer:
    query: str
    query_type: str
    answer: str
    citations: List[Citation] = field(default_factory=list)
    used_citations: List[int] = field(default_factory=list)
    sufficient_evidence: bool = True
    flags: List[str] = field(default_factory=list)
    concepts_identified: List[str] = field(default_factory=list)
    model_used: str = ""
    retriever_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "query_type": self.query_type,
            "query_type_label": QUERY_TYPES.get(self.query_type, "unknown"),
            "answer": self.answer,
            "sufficient_evidence": self.sufficient_evidence,
            "flags": self.flags,
            "concepts_identified": self.concepts_identified,
            "retriever_used": self.retriever_used,
            "model_used": self.model_used,
            "used_citations": self.used_citations,
            "citations": [vars(c) for c in self.citations],
        }
