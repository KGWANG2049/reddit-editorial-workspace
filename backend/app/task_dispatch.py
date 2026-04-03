from __future__ import annotations

from . import models
from .repository import Repository


def enqueue_process_task(repo: Repository, document_id: str) -> models.TaskJob:
    return repo.create_task_job(
        task_type=models.TaskType.process_url.value,
        target_id=document_id,
        status=models.TaskStatus.queued.value,
    )


def retry_task_job(repo: Repository, source_job: models.TaskJob) -> models.TaskJob:
    if source_job.status != models.TaskStatus.failed.value:
        raise ValueError("Only failed jobs can be retried")
    if source_job.task_type != models.TaskType.process_url.value:
        raise ValueError(f"Unsupported task type for retry: {source_job.task_type}")
    if not source_job.target_id:
        raise ValueError("Retry target is missing")

    document = repo.get_document(source_job.target_id)
    if not document:
        raise ValueError("Retry target document not found")

    repo.mark_document_status(document, models.DocumentStatus.queued.value, error=None)
    return enqueue_process_task(repo, document.id)
