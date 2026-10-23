import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.pipeline_runner import PipelineRunner
from config import settings
from logging_setup import configure_logging

configure_logging()

app = FastAPI(title="ConceptScape API", version="1.0")

# The Next.js dev server runs on a different origin, so the browser needs
# explicit permission to call this service.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: Optional[int] = None


# The RAG pipeline loads a 2.2GB embedding model and opens Qdrant and Neo4j
# connections, so it is built once on demand and reused. Constructing it per
# request would make every question take tens of seconds.
_pipeline = None
_pipeline_error: Optional[str] = None


def get_pipeline():
    global _pipeline, _pipeline_error
    if _pipeline is None and _pipeline_error is None:
        try:
            from rag.pipeline import RAGPipeline
            logging.info("Initialising RAG pipeline (first request warms the embedding model)…")
            _pipeline = RAGPipeline()
            logging.info("RAG pipeline ready")
        except Exception as e:
            _pipeline_error = str(e)
            logging.error(f"Could not initialise RAG pipeline: {e}")
    if _pipeline is None:
        raise HTTPException(503, f"RAG pipeline unavailable: {_pipeline_error}")
    return _pipeline


def _load(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise HTTPException(
            404,
            f"{os.path.basename(path)} not found. Run the pipeline first "
            f"(run_ingestion → run_preprocessing → run_extraction → "
            f"run_normalization → run_relationships → run_build_graph).",
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/health")
def health() -> Dict[str, Any]:
    """Reports which artefacts exist, so the UI can explain what is missing."""
    files = {
        "concepts": os.path.join(settings.data_dir, "normalized_concepts.json"),
        "relationships": os.path.join(settings.data_dir, "relationships.json"),
        "graph": os.path.join(settings.data_dir, "graph_export.json"),
        "chunks": os.path.join(settings.output_dir, "preprocessed_chunks.json"),
    }
    return {
        "status": "ok",
        "artifacts": {k: os.path.exists(v) for k, v in files.items()},
        "pipeline_loaded": _pipeline is not None,
        "pipeline_error": _pipeline_error,
    }


@app.get("/graph")
def graph() -> Dict[str, Any]:
    return _load(os.path.join(settings.data_dir, "graph_export.json"))


@app.get("/concepts")
def concepts(q: str = "", limit: int = 200) -> Dict[str, Any]:
    data = _load(os.path.join(settings.data_dir, "normalized_concepts.json"))
    items: List[dict] = data.get("concepts", [])
    if q:
        needle = q.casefold()
        items = [
            c for c in items
            if needle in c.get("canonical_name", "").casefold()
            or any(needle in a.casefold() for a in c.get("aliases", []))
            or any(needle in k.casefold() for k in c.get("keywords", []))
        ]
    return {"total": len(items), "concepts": items[:limit]}


@app.get("/concepts/{concept_id}")
def concept_detail(concept_id: str) -> Dict[str, Any]:
    data = _load(os.path.join(settings.data_dir, "normalized_concepts.json"))
    concept = next((c for c in data.get("concepts", []) if c["concept_id"] == concept_id), None)
    if concept is None:
        raise HTTPException(404, f"No concept with id {concept_id}")

    rels = _load(os.path.join(settings.data_dir, "relationships.json")).get("relationships", [])
    related = [
        r for r in rels
        if r["source_concept_id"] == concept_id or r["target_concept_id"] == concept_id
    ]
    return {"concept": concept, "relationships": related}


# ── documents & pipeline ─────────────────────────────────────────────────

ALLOWED_SUFFIXES = {".pdf", ".pptx", ".ppt", ".png", ".jpg", ".jpeg", ".webp"}


def _safe_name(filename: str) -> str:
    """
    Reduce an uploaded filename to a bare, safe basename.

    An upload endpoint that trusts the client's filename is a directory
    traversal waiting to happen — "../../etc/passwd" must not escape the
    documents folder.
    """
    name = os.path.basename(filename or "").strip().replace("\x00", "")
    name = name.lstrip(".")  # no hidden files, no "..".
    if not name:
        raise HTTPException(400, "Invalid filename")
    if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(
            400,
            f"Unsupported file type '{Path(name).suffix}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}",
        )
    return name


def _invalidate_pipeline() -> None:
    """Drop the cached RAG pipeline so the next question sees the new corpus."""
    global _pipeline, _pipeline_error
    _pipeline = None
    _pipeline_error = None
    logging.info("Pipeline cache invalidated — next question reloads the corpus")


runner = PipelineRunner(on_complete=_invalidate_pipeline)


@app.get("/documents")
def documents() -> Dict[str, Any]:
    d = Path(settings.documents_dir)
    if not d.is_dir():
        return {"documents": []}
    items = [
        {"filename": f.name, "size_bytes": f.stat().st_size, "suffix": f.suffix.lower()}
        for f in sorted(d.iterdir())
        if f.is_file() and f.suffix.lower() in ALLOWED_SUFFIXES
    ]
    return {"documents": items, "total": len(items)}


@app.post("/documents")
async def upload(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    d = Path(settings.documents_dir)
    d.mkdir(parents=True, exist_ok=True)

    saved, rejected = [], []
    for f in files:
        try:
            name = _safe_name(f.filename)
        except HTTPException as e:
            rejected.append({"filename": f.filename, "reason": e.detail})
            continue

        content = await f.read()
        if len(content) > settings.upload_max_bytes:
            rejected.append({
                "filename": name,
                "reason": f"Too large ({len(content) // 1_000_000}MB); "
                          f"limit is {settings.upload_max_bytes // 1_000_000}MB",
            })
            continue

        (d / name).write_bytes(content)
        saved.append({"filename": name, "size_bytes": len(content)})
        logging.info(f"Uploaded {name} ({len(content)} bytes)")

    return {"saved": saved, "rejected": rejected}


@app.delete("/documents/{filename}")
def delete_document(filename: str) -> Dict[str, Any]:
    name = _safe_name(filename)
    path = Path(settings.documents_dir) / name
    if not path.is_file():
        raise HTTPException(404, f"No document named {name}")
    path.unlink()
    logging.info(f"Deleted {name}")
    return {"deleted": name}


@app.post("/pipeline/run")
def pipeline_run() -> Dict[str, Any]:
    return runner.start()


@app.get("/pipeline/status")
def pipeline_status() -> Dict[str, Any]:
    return runner.state


@app.post("/ask")
def ask(req: AskRequest) -> Dict[str, Any]:
    pipeline = get_pipeline()
    try:
        return pipeline.ask(req.query, req.top_k).to_dict()
    except Exception as e:
        logging.exception("Question failed")
        raise HTTPException(500, f"Question failed: {e}")
