import logging
from typing import List, Optional

from config import settings
from rag.evidence import assemble
from rag.generator import AnswerGenerator
from rag.models import TYPE_A, TYPE_B, TYPE_C, Answer
from rag.understanding import QueryUnderstander
from retrieval.retrievers import build_retrievers, load_corpus
from retrieval.vector_store import VectorStore
from retrieval.embedder import Embedder


class RAGPipeline:
    """
    Query → understanding → routed retrieval → evidence assembly → grounded answer.

    Retrieval is routed by query type because the right evidence differs:
    a "what does X require" question is answered by graph edges, while an open
    question often needs raw chunk text that no concept captured.
    """

    def __init__(self, store: Optional[VectorStore] = None, embedder: Optional[Embedder] = None):
        self.concepts, self.relationships, _ = load_corpus()
        self.concepts_by_id = {c["concept_id"]: c for c in self.concepts}
        self.store = store if store is not None else VectorStore()
        self.embedder = embedder if embedder is not None else Embedder()
        self.retrievers = build_retrievers(self.concepts, self.relationships, self.store, self.embedder)
        self.understander = QueryUnderstander([c["canonical_name"] for c in self.concepts])
        self.generator = AnswerGenerator()

    def _route(self, query_type: str) -> str:
        # A and B are graph-shaped questions: identity and connection. Graph
        # retrieval expands along evidenced edges, which is exactly the material
        # those answers need. C benefits from hybrid, which also surfaces chunks.
        if query_type in (TYPE_A, TYPE_B):
            return "graph" if self.retrievers.get("graph") else "keyword"
        return "hybrid"

    def ask(self, query: str, top_k: int = None) -> Answer:
        top_k = top_k or settings.retrieval_top_k

        understanding = self.understander.understand(query)
        logging.info(
            f"Query type {understanding.query_type} "
            f"({', '.join(understanding.concepts) or 'no concepts identified'})"
        )

        retriever_name = self._route(understanding.query_type)
        retriever = self.retrievers.get(retriever_name) or self.retrievers["keyword"]

        # Prefer searching by the concept names the understander identified —
        # that is what bridges a paraphrased question to the indexed vocabulary.
        search_text = " ".join(understanding.concepts) if understanding.concepts else query
        results = retriever.retrieve(search_text, top_k)

        # A paraphrase can still miss; fall back to the raw query before giving up.
        if not results and search_text != query:
            results = retriever.retrieve(query, top_k)

        citations = assemble(results, self.concepts_by_id, self.relationships)
        data, model_used = self.generator.generate(query, understanding.query_type, citations)

        flags = list(data["flags"])
        if len(citations) < settings.rag_thin_evidence_threshold:
            flags.append("thin_evidence")

        return Answer(
            query=query,
            query_type=understanding.query_type,
            answer=data["answer"],
            citations=citations,
            used_citations=data["used_citations"],
            sufficient_evidence=data["sufficient_evidence"],
            flags=sorted(set(flags)),
            concepts_identified=understanding.concepts,
            model_used=model_used or understanding.model_used,
            retriever_used=retriever_name,
        )

    def close(self):
        self.store.close()
