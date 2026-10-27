import logging
from typing import List, Optional

from config import settings

try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False


class Embedder:
    """
    Local Sentence-Transformers embeddings, loaded lazily and shared for a run.

    The default model is a lightweight semantic-search model. Query and
    document encoding are separate methods so models trained for asymmetric
    retrieval can use their task-specific prompts when available.
    """

    def __init__(self, model_name: str = ""):
        self.model_name = model_name or settings.embedding_model
        self._model: Optional["SentenceTransformer"] = None

    def _get_model(self) -> "SentenceTransformer":
        if not ST_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers is not installed. Run: pip install sentence-transformers"
            )
        if self._model is None:
            logging.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logging.info(f"Embedding dimension: {self.dimension}")
        return self._model

    @property
    def dimension(self) -> int:
        return self._get_model().get_sentence_embedding_dimension()

    def _encode(self, texts: List[str], batch_size: int, task: str = "document") -> List[List[float]]:
        if not texts:
            return []
        model = self._get_model()
        task_encoder = getattr(model, f"encode_{task}", None)
        if task_encoder is not None:
            vectors = task_encoder(texts, batch_size=batch_size,
                                   normalize_embeddings=True,
                                   show_progress_bar=len(texts) > 32)
        else:
            vectors = model.encode(texts, batch_size=batch_size,
                                   normalize_embeddings=True,
                                   show_progress_bar=len(texts) > 32)
        return [v.tolist() for v in vectors]

    def encode(self, texts: List[str], batch_size: int = 0) -> List[List[float]]:
        return self._encode(texts, batch_size or settings.embedding_batch_size)

    def encode_documents(self, texts: List[str], batch_size: int = 0) -> List[List[float]]:
        return self._encode(texts, batch_size or settings.embedding_batch_size, "document")

    def encode_queries(self, texts: List[str], batch_size: int = 0) -> List[List[float]]:
        return self._encode(texts, batch_size or settings.embedding_batch_size, "query")

    def encode_one(self, text: str) -> List[float]:
        return self.encode_queries([text])[0]


def concept_embedding_text(concept: dict) -> str:
    """
    What actually gets embedded for a concept.

    Name alone is too sparse to match a paraphrased question, so the definition
    and a sample of verified evidence are folded in — that evidence is real
    source text, which is what a user's phrasing is most likely to echo.
    """
    parts = [concept.get("canonical_name", "")]
    if concept.get("definition"):
        parts.append(concept["definition"])
    aliases = [a for a in concept.get("aliases", []) if a != concept.get("canonical_name")]
    if aliases:
        parts.append(" ".join(aliases))
    if concept.get("keywords"):
        parts.append(" ".join(concept["keywords"]))
    for ev in (concept.get("evidence") or [])[:2]:
        parts.append(ev)
    return " | ".join(p for p in parts if p)
