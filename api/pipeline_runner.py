import logging
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

# Ordered pipeline stages. Each is (key, human label, callable factory) — the
# import happens inside the callable so a broken optional dependency surfaces as
# a failed stage rather than preventing the whole API from starting.
STAGES: List[tuple] = [
    ("ingestion", "Parsing documents (PDF/PPTX/images, OCR where needed)"),
    ("preprocessing", "Cleaning, splitting and chunking text"),
    ("extraction", "Extracting concepts with evidence"),
    ("normalization", "Merging concepts across documents"),
    ("relationships", "Extracting relationships"),
    ("graph", "Building the knowledge graph"),
    ("index", "Embedding and indexing for search"),
]


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
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    current: Optional[str] = None
    error: Optional[str] = None
    stages: List[StageState] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
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

    def __init__(self, on_complete: Optional[Callable[[], None]] = None):
        self._lock = threading.Lock()
        self._state = RunState()
        self._thread: Optional[threading.Thread] = None
        self._on_complete = on_complete

    @property
    def state(self) -> Dict[str, Any]:
        with self._lock:
            return self._state.to_dict()

    def start(self) -> Dict[str, Any]:
        with self._lock:
            if self._state.running:
                return {"started": False, "reason": "A pipeline run is already in progress."}
            self._state = RunState(
                running=True,
                started_at=time.time(),
                stages=[StageState(key=k, label=l) for k, l in STAGES],
            )
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return {"started": True}

    def _set(self, key: str, **kw) -> None:
        with self._lock:
            for s in self._state.stages:
                if s.key == key:
                    for k, v in kw.items():
                        setattr(s, k, v)

    def _run(self) -> None:
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
            if self._on_complete:
                try:
                    self._on_complete()
                except Exception:
                    logging.exception("Post-run callback failed")
