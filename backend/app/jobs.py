from __future__ import annotations

from . import models
from .database import SessionLocal
from .repository import Repository
from .services.document_orchestrator import DocumentOrchestrator
from .services.filesystem import DocumentFilesystemService
from .services.markdown_polish import MarkdownPolishService
from .services.obsidian_capture import ObsidianCaptureService

filesystem_service = DocumentFilesystemService()
capture_service = ObsidianCaptureService()
polish_service = MarkdownPolishService()
orchestrator = DocumentOrchestrator(capture_service, filesystem_service, polish_service)


def execute_task_job(task_job_id: str, already_running: bool = False) -> dict:
    with SessionLocal() as session:
        repo = Repository(session)
        task_job = repo.get_task_job(task_job_id)
        if not task_job:
            raise ValueError("Task job not found")
        if not task_job.target_id:
            raise ValueError("Task job target is missing")
        target_id = task_job.target_id
        document = repo.get_document(target_id)
        if not document:
            raise ValueError("Document not found")
        if not already_running:
            repo.mark_task_job_running(task_job)
            session.commit()

    try:
        with SessionLocal() as session:
            repo = Repository(session)
            document = repo.get_document(target_id)
            if not document:
                raise ValueError("Document not found")
            result = orchestrator.process(repo, document)

        with SessionLocal() as session:
            repo = Repository(session)
            task_job = repo.get_task_job(task_job_id)
            if task_job:
                repo.mark_task_job_succeeded(task_job, result)
                session.commit()
        return result
    except Exception as exc:
        with SessionLocal() as session:
            repo = Repository(session)
            task_job = repo.get_task_job(task_job_id)
            if task_job:
                repo.mark_task_job_failed(task_job, str(exc))
            document = repo.get_document(target_id)
            if document:
                repo.mark_document_status(document, models.DocumentStatus.failed.value, error=str(exc))
            session.commit()
        raise
