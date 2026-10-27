import json
import logging
import os
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import settings
from retrieval.embedder import Embedder
from retrieval.vector_store import VectorStore


@dataclass
class RetrievalResult:
    """
    One retrieved item, in a shape every retriever produces identically.

    Uniformity is deliberate: the hybrid retriever fuses these, and the RAG
    stage assembles evidence from them, so neither should care which strategy
    produced a given hit.
    """
    kind: str                      # "concept" | "chunk"
    id: str
    name: str
    text: str
    score: float
    retriever: str
    filenames: List[str] = field(default_factory=list)
    page_numbers: List[int] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", s).strip().casefold()


def _tokens(s: str) -> List[str]:
    return [t for t in re.split(r"[^\w]+", _norm(s)) if len(t) > 2]


# ── Keyword ───────────────────────────────────────────────────────────────

class KeywordRetriever:
    """
    Lexical matching over canonical names, aliases and keywords.

    Cheap, dependency-free, and the fallback when embeddings are unavailable.
    Exact and substring matches outrank token overlap so that asking for a
    concept by name returns that concept first.
    """
    name = "keyword"

    def __init__(self, concepts: List[dict]):
        self.concepts = concepts

    def retrieve(self, query: str, top_k: int = None) -> List[RetrievalResult]:
        top_k = top_k or settings.retrieval_top_k
        q, qt = _norm(query), set(_tokens(query))
        scored = []

        for c in self.concepts:
            surfaces = [c.get("canonical_name", "")] + list(c.get("aliases") or [])
            best = 0.0
            for s in surfaces:
                ns = _norm(s)
                if not ns:
                    continue
                if ns == q:
                    best = max(best, 1.0)
                elif ns in q or q in ns:
                    best = max(best, 0.75)
            if best == 0.0 and qt:
                surface_tokens = set(_tokens(" ".join(surfaces)))
                kw_tokens = set(_tokens(" ".join(c.get("keywords") or [])))
                overlap = len(qt & (surface_tokens | kw_tokens))
                if overlap:
                    best = 0.5 * overlap / len(qt)
            if best > 0:
                scored.append((best, c))

        scored.sort(key=lambda x: (-x[0], -x[1].get("occurrence_count", 0)))
        return [_concept_result(c, s, self.name) for s, c in scored[:top_k]]


# ── Semantic ──────────────────────────────────────────────────────────────

class SemanticRetriever:
    """Sentence-Transformer nearest neighbours over concepts and chunks."""
    name = "semantic"

    def __init__(self, store: VectorStore, embedder: Embedder, search_chunks: bool = True):
        self.store = store
        self.embedder = embedder
        self.search_chunks = search_chunks

    def retrieve(self, query: str, top_k: int = None) -> List[RetrievalResult]:
        top_k = top_k or settings.retrieval_top_k
        vec = self.embedder.encode_one(query)
        out: List[RetrievalResult] = []

        for hit in self.store.search(self.store.concepts_collection, vec, top_k, settings.semantic_score_threshold):
            out.append(RetrievalResult(
                kind="concept", id=hit.get("concept_id", ""), name=hit.get("canonical_name", ""),
                text=hit.get("definition", ""), score=float(hit["score"]), retriever=self.name,
                filenames=hit.get("filenames", []), page_numbers=hit.get("page_numbers", []),
                chunk_ids=hit.get("chunk_ids", []), evidence=hit.get("evidence", []),
            ))

        if self.search_chunks:
            for hit in self.store.search(self.store.chunks_collection, vec, top_k, settings.semantic_score_threshold):
                out.append(RetrievalResult(
                    kind="chunk", id=hit.get("chunk_id", ""), name=hit.get("filename", ""),
                    text=hit.get("text", ""), score=float(hit["score"]), retriever=self.name,
                    filenames=[hit.get("filename", "")],
                    page_numbers=[hit["location_number"]] if hit.get("location_number") else [],
                    chunk_ids=[hit.get("chunk_id", "")],
                ))

        out.sort(key=lambda r: -r.score)
        return out[: top_k * 2]


# ── Graph-aware ───────────────────────────────────────────────────────────

class GraphRetriever:
    """
    Expands seed concepts along evidence-grounded relationships.

    This is the retriever the project's thesis rests on: a question about
    mini-batch SGD should surface Batch Size and Learning Rate because the
    graph says they are *required by* it, not because they look similar.
    Neighbours are scored below their seed so the seed stays ranked first.
    """
    name = "graph"

    def __init__(self, concepts: List[dict], relationships: List[dict], seed_retriever):
        self.by_id = {c["concept_id"]: c for c in concepts}
        self.seed_retriever = seed_retriever
        self.adjacency: Dict[str, List[dict]] = defaultdict(list)
        for r in relationships:
            self.adjacency[r["source_concept_id"]].append({**r, "direction": "outgoing"})
            self.adjacency[r["target_concept_id"]].append({**r, "direction": "incoming"})

    def retrieve(self, query: str, top_k: int = None, hops: int = 1) -> List[RetrievalResult]:
        top_k = top_k or settings.retrieval_top_k
        seeds = [r for r in self.seed_retriever.retrieve(query, top_k) if r.kind == "concept"]
        if not seeds:
            return []

        results: Dict[str, RetrievalResult] = {}
        for s in seeds[:3]:
            if s.id in self.by_id:
                results[s.id] = _concept_result(self.by_id[s.id], s.score, self.name)

        frontier = [(s.id, s.score) for s in seeds[:3] if s.id in self.by_id]
        for _ in range(max(1, hops)):
            nxt = []
            for cid, parent_score in frontier:
                for rel in self.adjacency.get(cid, []):
                    other = (rel["target_concept_id"] if rel["direction"] == "outgoing"
                             else rel["source_concept_id"])
                    concept = self.by_id.get(other)
                    if concept is None:
                        continue
                    score = parent_score * 0.6
                    if other not in results or results[other].score < score:
                        res = _concept_result(concept, score, self.name)
                        res.extra["via"] = f"{rel['source_name']} -{rel['type']}-> {rel['target_name']}"
                        ev = rel.get("evidence") or []
                        res.extra["relationship_evidence"] = ev[0].get("text", "") if ev else ""
                        results[other] = res
                    nxt.append((other, score))
            frontier = nxt

        out = sorted(results.values(), key=lambda r: -r.score)
        return out[: top_k * 2]


# ── Hybrid ────────────────────────────────────────────────────────────────

class HybridRetriever:
    """
    Weighted reciprocal-rank fusion across the other three.

    RRF is used rather than raw score averaging because the retrievers'
    scores are not comparable — cosine similarity, lexical overlap ratios and
    decayed graph scores live on different scales. Rank is comparable.
    """
    name = "hybrid"
    RRF_K = 60

    def __init__(self, keyword=None, semantic=None, graph=None):
        self.retrievers = []
        if keyword: self.retrievers.append((keyword, settings.weight_keyword))
        if semantic: self.retrievers.append((semantic, settings.weight_semantic))
        if graph: self.retrievers.append((graph, settings.weight_graph))

    def retrieve(self, query: str, top_k: int = None) -> List[RetrievalResult]:
        top_k = top_k or settings.retrieval_top_k
        fused: Dict[str, RetrievalResult] = {}
        scores: Dict[str, float] = defaultdict(float)
        sources: Dict[str, List[str]] = defaultdict(list)

        for retriever, weight in self.retrievers:
            try:
                hits = retriever.retrieve(query, top_k)
            except Exception as e:
                logging.warning(f"{retriever.name} retriever failed: {e}")
                continue
            for rank, hit in enumerate(hits, start=1):
                key = f"{hit.kind}:{hit.id}"
                scores[key] += weight / (self.RRF_K + rank)
                sources[key].append(retriever.name)
                if key not in fused or fused[key].score < hit.score:
                    fused[key] = hit

        out = []
        for key, res in fused.items():
            res.score = round(scores[key], 6)
            res.retriever = "hybrid"
            res.extra["found_by"] = sorted(set(sources[key]))
            out.append(res)
        out.sort(key=lambda r: -r.score)
        return out[:top_k]


# ── helpers ───────────────────────────────────────────────────────────────

def _concept_result(c: dict, score: float, retriever: str) -> RetrievalResult:
    return RetrievalResult(
        kind="concept", id=c["concept_id"], name=c.get("canonical_name", ""),
        text=c.get("definition", ""), score=round(float(score), 6), retriever=retriever,
        filenames=c.get("filenames", []), page_numbers=c.get("page_numbers", []),
        chunk_ids=c.get("chunk_ids", []), evidence=c.get("evidence", []),
    )


def load_corpus():
    """Load concepts, relationships and chunks from the pipeline's outputs."""
    with open(os.path.join(settings.data_dir, "normalized_concepts.json"), encoding="utf-8") as f:
        concepts = json.load(f)["concepts"]
    with open(os.path.join(settings.data_dir, "relationships.json"), encoding="utf-8") as f:
        relationships = json.load(f)["relationships"]
    with open(os.path.join(settings.output_dir, "preprocessed_chunks.json"), encoding="utf-8") as f:
        chunks = json.load(f)["chunks"]
    return concepts, relationships, chunks


def build_retrievers(concepts, relationships, store=None, embedder=None):
    """Construct all four retrievers, degrading gracefully if Qdrant is unavailable."""
    keyword = KeywordRetriever(concepts)
    semantic = None
    if store is not None and embedder is not None:
        try:
            if store.count(store.concepts_collection) > 0:
                semantic = SemanticRetriever(store, embedder)
            else:
                logging.warning("Concept collection is empty — run run_index.py to enable semantic search")
        except Exception as e:
            logging.warning(f"Semantic retriever unavailable: {e}")
    graph = GraphRetriever(concepts, relationships, semantic or keyword)
    hybrid = HybridRetriever(keyword, semantic, graph)
    return {"keyword": keyword, "semantic": semantic, "graph": graph, "hybrid": hybrid}
