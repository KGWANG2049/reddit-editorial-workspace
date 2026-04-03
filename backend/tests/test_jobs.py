from __future__ import annotations

from pathlib import Path

import pytest

import app.db_worker as db_worker
import app.jobs as jobs
from app import models
from app.repository import Repository
from app.services.obsidian_capture import CaptureResult


class _FakeResponse:
    def __init__(self, content: bytes, content_type: str = "image/png"):
        self.content = content
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self) -> None:
        return None


def _fake_capture(source_url: str, raw_path: Path, assets_dir: Path) -> CaptureResult:
    _ = source_url
    Path(assets_dir).mkdir(parents=True, exist_ok=True)
    Path(raw_path).write_text(
        "# Sample Title\n\n![](https://images.example.com/hero.png)\n\nBody.\n",
        encoding="utf-8",
    )
    return CaptureResult(title="Sample Title", metadata={"capture_backend": "test"})


def test_db_worker_processes_job_and_writes_artifacts(db_session_factory, monkeypatch, tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    monkeypatch.setattr("app.config.settings.obsidian_vault_path", str(vault_dir))
    monkeypatch.setattr("app.config.settings.obsidian_output_subdir", "captures")
    monkeypatch.setattr("app.config.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("app.config.settings.openai_polish_model", "gpt-5")
    monkeypatch.setattr(jobs.capture_service, "capture", _fake_capture)
    monkeypatch.setattr(
        jobs.filesystem_service.session,
        "get",
        lambda url, timeout=30: _FakeResponse(b"png-bits"),
    )
    monkeypatch.setattr(
        jobs.polish_service,
        "_request_openai",
        lambda prompt, model, max_output_tokens=None: ("# Polished\n\n![[assets/hero.png]]\n\nBetter body.", None),
    )

    with db_session_factory() as session:
        repo = Repository(session)
        document = repo.create_document("https://example.com/sample", "sample")
        repo.create_task_job(models.TaskType.process_url.value, target_id=document.id)
        session.commit()

    assert db_worker.run_one_job() is True

    with db_session_factory() as session:
        repo = Repository(session)
        document = repo.list_documents(limit=1)[0]
        latest_job = repo.get_latest_task_job_for_document(document.id)

        assert document.status == models.DocumentStatus.completed.value
        assert latest_job is not None
        assert latest_job.status == models.TaskStatus.succeeded.value
        assert Path(document.raw_markdown_path).exists()
        assert Path(document.polished_markdown_path).exists()
        assert (Path(document.output_dir) / "assets").exists()


def test_execute_task_job_marks_failure_when_obsidian_missing(db_session_factory, monkeypatch):
    monkeypatch.setattr("app.config.settings.obsidian_vault_path", None)

    with db_session_factory() as session:
        repo = Repository(session)
        document = repo.create_document("https://example.com/fail", "fail")
        job = repo.create_task_job(models.TaskType.process_url.value, target_id=document.id)
        document_id = document.id
        job_id = job.id
        session.commit()

    with pytest.raises(Exception):
        jobs.execute_task_job(job_id)

    with db_session_factory() as session:
        repo = Repository(session)
        document = repo.get_document(document_id)
        latest_job = repo.get_latest_task_job_for_document(document_id)
        assert document is not None
        assert document.status == models.DocumentStatus.failed.value
        assert latest_job is not None
        assert latest_job.status == models.TaskStatus.failed.value
