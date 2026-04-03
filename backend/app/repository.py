from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


class Repository:
    def __init__(self, session: Session):
        self.session = session

    def create_document(self, source_url: str, slug: str) -> models.Document:
        document = models.Document(source_url=source_url, slug=slug)
        self.session.add(document)
        self.session.flush()
        return document

    def get_document(self, document_id: str) -> models.Document | None:
        return self.session.get(models.Document, document_id)

    def list_documents(self, limit: int = 50) -> Sequence[models.Document]:
        return self.session.scalars(
            select(models.Document).order_by(models.Document.created_at.desc()).limit(limit)
        ).all()

    def mark_document_status(
        self,
        document: models.Document,
        status: str,
        *,
        error: str | None = None,
    ) -> None:
        document.status = status
        document.error = error
        document.updated_at = models.utcnow()
        if status == models.DocumentStatus.completed.value:
            document.processed_at = models.utcnow()

    def update_document_paths(
        self,
        document: models.Document,
        *,
        output_dir: str,
        raw_markdown_path: str,
        polished_markdown_path: str,
    ) -> None:
        document.output_dir = output_dir
        document.raw_markdown_path = raw_markdown_path
        document.polished_markdown_path = polished_markdown_path
        document.updated_at = models.utcnow()

    def update_document_capture(
        self,
        document: models.Document,
        *,
        source_title: str | None,
        asset_count: int,
        metadata: dict,
    ) -> None:
        document.source_title = source_title
        document.asset_count = asset_count
        document.document_metadata = metadata
        document.updated_at = models.utcnow()

    def complete_document(
        self,
        document: models.Document,
        *,
        source_title: str | None,
        asset_count: int,
        metadata: dict,
    ) -> None:
        document.source_title = source_title
        document.asset_count = asset_count
        document.document_metadata = metadata
        document.status = models.DocumentStatus.completed.value
        document.error = None
        document.updated_at = models.utcnow()
        document.processed_at = models.utcnow()

    def create_task_job(
        self,
        task_type: str,
        target_id: str | None = None,
        status: str = models.TaskStatus.queued.value,
    ) -> models.TaskJob:
        job = models.TaskJob(
            task_type=task_type,
            queue_backend="db",
            target_id=target_id,
            status=status,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get_task_job(self, job_id: str) -> models.TaskJob | None:
        return self.session.get(models.TaskJob, job_id)

    def list_task_jobs(
        self,
        limit: int = 20,
        status: str | None = None,
        task_type: str | None = None,
    ) -> Sequence[models.TaskJob]:
        stmt = select(models.TaskJob).order_by(models.TaskJob.created_at.desc())
        if status:
            stmt = stmt.where(models.TaskJob.status == status)
        if task_type:
            stmt = stmt.where(models.TaskJob.task_type == task_type)
        return self.session.scalars(stmt.limit(limit)).all()

    def get_latest_task_job_for_document(self, document_id: str) -> models.TaskJob | None:
        return self.session.scalar(
            select(models.TaskJob)
            .where(models.TaskJob.target_id == document_id)
            .order_by(models.TaskJob.created_at.desc())
            .limit(1)
        )

    def claim_next_task_job(self, queue_backend: str = "db") -> models.TaskJob | None:
        job = self.session.scalar(
            select(models.TaskJob)
            .where(
                models.TaskJob.queue_backend == queue_backend,
                models.TaskJob.status == models.TaskStatus.queued.value,
            )
            .order_by(models.TaskJob.created_at.asc())
            .limit(1)
        )
        if not job:
            return None
        self.mark_task_job_running(job)
        self.session.flush()
        return job

    def mark_task_job_running(self, job: models.TaskJob) -> None:
        job.status = models.TaskStatus.running.value
        job.started_at = models.utcnow()
        job.error = None

    def mark_task_job_succeeded(self, job: models.TaskJob, result_payload: dict) -> None:
        job.status = models.TaskStatus.succeeded.value
        job.result_payload = result_payload
        job.finished_at = models.utcnow()
        job.error = None

    def mark_task_job_failed(self, job: models.TaskJob, error: str) -> None:
        job.status = models.TaskStatus.failed.value
        job.error = error
        job.finished_at = models.utcnow()
