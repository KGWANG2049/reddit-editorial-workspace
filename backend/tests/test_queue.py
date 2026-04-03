from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.repository import Repository
from app.task_dispatch import retry_task_job


def test_claim_next_task_job_marks_oldest_db_job_running():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with SessionLocal() as session:
        repo = Repository(session)
        repo.create_document("https://example.com/one", "one")
        first = repo.create_task_job(
            task_type=models.TaskType.process_url.value,
            target_id="doc-1",
            status=models.TaskStatus.queued.value,
        )
        second = repo.create_task_job(
            task_type=models.TaskType.process_url.value,
            target_id="doc-2",
            status=models.TaskStatus.queued.value,
        )
        session.commit()

        claimed = repo.claim_next_task_job("db")

        assert claimed is not None
        assert claimed.id == first.id
        assert claimed.status == models.TaskStatus.running.value
        assert claimed.started_at is not None
        assert second.status == models.TaskStatus.queued.value


def test_retry_task_job_requeues_failed_document():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with SessionLocal() as session:
        repo = Repository(session)
        document = repo.create_document("https://example.com/retry", "retry")
        document.status = models.DocumentStatus.failed.value
        document.error = "broken"
        failed_job = repo.create_task_job(
            task_type=models.TaskType.process_url.value,
            target_id=document.id,
            status=models.TaskStatus.failed.value,
        )
        session.commit()

        retried_job = retry_task_job(repo, failed_job)
        session.commit()

        assert retried_job.id != failed_job.id
        assert retried_job.status == models.TaskStatus.queued.value
        assert retried_job.target_id == document.id
        assert document.status == models.DocumentStatus.queued.value
