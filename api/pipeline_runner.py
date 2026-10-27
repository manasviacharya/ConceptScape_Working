import logging
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

# Ordered pipeline stages. Each is (key, human label, callable factory) — the
# import happens inside the callable so a broken optional dependency surfaces as
# a failed stage rather than preventing the whole API from starting.
STAGES: list[tuple] = [
    ("ingestion", "Parsing documents (PDF/PPTX/images, OCR where needed)"),
    ("preprocessing", "Cleaning, splitting and chunking text"),
    ("extraction", "Extracting concepts with evidence"),
    ("normalization", "Merging concepts across documents"),
    ("relationships", "Extracting relationships"),
    ("graph", "Building the knowledge graph"),
    ("index", "Embedding and indexing for search"),
]

# The legacy pipeline scripts read their directories from the process-global
# settings object. Serialize path-scoped runs so two workspaces cannot swap
# those values while another run is executing.
SETTINGS_LOCK = threading.Lock()


@dataclass
class StageState:
    key: str
    label: str
    status: str = "pending"      # pending | running | done | failed | skipped
    detail: str = ""
    seconds: float = 0.0


@dataclass
class RunState:
    running: bool = False
    started_at: float | None = None
    finished_at: float | None = None
    current: str | None = None
    error: str | None = None
    stages: list[StageState] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["elapsed"] = round(
            (self.finished_at or time.time()) - self.started_at, 1
        ) if self.started_at else 0
        return d


class PipelineRunner:
    """
    Runs the pipeline in a background thread and reports per-stage progress.

    A full run takes minutes and makes real LLM calls that can exhaust a daily
    quota partway through, so the UI needs honest per-stage state rather than a
    spinner. Every stage caches, so a failed run is resumed — not restarted — by
    running again.

    Only one run at a time: concurrent runs would write the same output files.
    """

    def __init__(self, on_complete: Callable[[str], None] | None = None):
        self._lock = threading.Lock()
        self._state = RunState()
        self._thread: threading.Thread | None = None
        self._on_complete = on_complete
        self._workspace_id: str | None = None

    @property
    def state(self) -> dict[str, Any]:
        with self._lock:
            return self._state.to_dict()

    def start(self, workspace_id: str) -> dict[str, Any]:
        with self._lock:
            if self._state.running:
                return {"started": False, "reason": "A pipeline run is already in progress."}
            self._state = RunState(
                running=True,
                started_at=time.time(),
                stages=[StageState(key=k, label=l) for k, l in STAGES],
            )
            self._workspace_id = workspace_id
        self._thread = threading.Thread(target=self._run, args=(workspace_id,), daemon=True)
        self._thread.start()
        return {"started": True}

    def _set(self, key: str, **kw) -> None:
        with self._lock:
            for s in self._state.stages:
                if s.key == key:
                    for k, v in kw.items():
                        setattr(s, k, v)

    def _run(self, workspace_id: str) -> None:
        # Imported here so module-level import failures cannot break API startup.
        import run_build_graph
        import run_extraction
        import run_index
        import run_ingestion
        import run_normalization
        import run_preprocessing
        import run_relationships

        steps = {
            "ingestion": run_ingestion.main,
            "preprocessing": run_preprocessing.main,
            "extraction": run_extraction.main,
            "normalization": run_normalization.main,
            "relationships": run_relationships.main,
            "graph": run_build_graph.main,
            "index": run_index.main,
        }

        from config import settings
        from storage.paths import ensure_workspace_paths

        paths = ensure_workspace_paths(workspace_id)
        previous_paths = (settings.documents_dir, settings.output_dir, settings.data_dir,
                          settings.qdrant_path, settings.qdrant_collection_prefix)
        SETTINGS_LOCK.acquire()
        settings.documents_dir = str(paths["documents"])
        settings.output_dir = str(paths["output"])
        settings.data_dir = str(paths["data"])
        settings.qdrant_path = str(paths["vectors"])
        settings.qdrant_collection_prefix = f"workspace_{workspace_id}"

        try:
            for key, _ in STAGES:
                with self._lock:
                    self._state.current = key
                self._set(key, status="running")
                t0 = time.time()
                try:
                    steps[key]()
                    self._set(key, status="done", seconds=round(time.time() - t0, 1))
                except Exception as e:
                    logging.exception(f"Pipeline stage '{key}' failed")
                    self._set(
                        key,
                        status="failed",
                        detail=str(e)[:300],
                        seconds=round(time.time() - t0, 1),
                    )
                    with self._lock:
                        self._state.error = f"Stage '{key}' failed: {str(e)[:200]}"
                    # Later stages depend on this one's output, so stop rather
                    # than producing a half-built graph from stale inputs.
                    for s in self._state.stages:
                        if s.status == "pending":
                            self._set(s.key, status="skipped", detail="earlier stage failed")
                    break
        except Exception:
            with self._lock:
                self._state.error = traceback.format_exc()[-400:]
        finally:
            with self._lock:
                self._state.running = False
                self._state.current = None
                self._state.finished_at = time.time()
            (settings.documents_dir, settings.output_dir, settings.data_dir,
             settings.qdrant_path, settings.qdrant_collection_prefix) = previous_paths
            SETTINGS_LOCK.release()
            if self._on_complete:
                try:
                    self._on_complete(workspace_id)
                except Exception:
                    logging.exception("Post-run callback failed")
