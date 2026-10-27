"""Database-backed pipeline worker for the production compose stack."""
import time
from datetime import datetime, timezone

from api.pipeline_runner import PipelineRunner
from config import settings
from storage.database import SessionLocal, init_db
from storage.models import DocumentRecord, PipelineJob


def finish(job_id: str, workspace_id: str, state: dict) -> None:
    db = SessionLocal()
    try:
        job = db.get(PipelineJob, job_id)
        if job:
            job.status = "failed" if state.get("error") else "completed"
            job.current = state.get("current")
            job.error = state.get("error")
            job.finished_at = datetime.now(timezone.utc)
            if job.status == "completed":
                db.query(DocumentRecord).filter_by(workspace_id=workspace_id).update(
                    {DocumentRecord.status: "processed", DocumentRecord.error: None,
                     DocumentRecord.processed_at: job.finished_at},
                    synchronize_session=False,
                )
            else:
                db.query(DocumentRecord).filter_by(workspace_id=workspace_id, status="queued").update(
                    {DocumentRecord.status: "error", DocumentRecord.error: job.error},
                    synchronize_session=False,
                )
            db.commit()
    finally:
        db.close()


def main() -> None:
    init_db()
    while True:
        db = SessionLocal()
        job = db.query(PipelineJob).filter_by(status="queued").order_by(PipelineJob.created_at.asc()).first()
        if job:
            job.status = "running"; job.started_at = datetime.now(timezone.utc); db.commit()
            job_id, workspace_id = job.id, job.workspace_id
            db.close()
            runner = PipelineRunner()
            runner.start(workspace_id)
            while runner.state.get("running"):
                time.sleep(1)
            finish(job_id, workspace_id, runner.state)
        else:
            db.close()
            time.sleep(2)


if __name__ == "__main__":
    main()
