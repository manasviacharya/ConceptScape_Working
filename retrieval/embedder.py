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
    BGE-M3 sentence embeddings, loaded lazily and shared for a whole run.

    The model is ~2.2GB and takes seconds to load, so it is initialised on
    first use and reused — indexing and querying in one process must not pay
    for it twice.
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
            logging.info(f"Loading embedding model: {self.model_name} (first run downloads ~2.2GB)")
            self._model = SentenceTransformer(self.model_name)
            logging.info(f"Embedding dimension: {self.dimension}")
        return self._model

    @property
    def dimension(self) -> int:
        return self._get_model().get_sentence_embedding_dimension()

    def encode(self, texts: List[str], batch_size: int = 8) -> List[List[float]]:
        if not texts:
            return []
        model = self._get_model()
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,  # cosine similarity becomes a dot product
            show_progress_bar=len(texts) > 32,
        )
        return [v.tolist() for v in vectors]

    def encode_one(self, text: str) -> List[float]:
        return self.encode([text])[0]


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
