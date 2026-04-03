from __future__ import annotations

import time

from .bootstrap import init_db
from .config import settings
from .database import SessionLocal
from .jobs import execute_task_job
from .repository import Repository


def run_one_job() -> bool:
    with SessionLocal() as session:
        repo = Repository(session)
        job = repo.claim_next_task_job(queue_backend="db")
        if not job:
            return False
        job_id = job.id
        session.commit()

    execute_task_job(job_id, already_running=True)
    return True


def main() -> None:
    init_db()
    print(f"[worker:db] starting poll loop interval={settings.worker_poll_interval_seconds}s")
    while True:
        try:
            processed = run_one_job()
        except Exception as exc:
            print(f"[worker:db] task failed: {exc}")
            processed = True
        if not processed:
            time.sleep(settings.worker_poll_interval_seconds)
