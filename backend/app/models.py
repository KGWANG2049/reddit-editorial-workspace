from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_id() -> str:
    return str(uuid.uuid4())


class DocumentStatus(str, enum.Enum):
    queued = "queued"
    capturing = "capturing"
    polishing = "polishing"
    completed = "completed"
    failed = "failed"


class TaskType(str, enum.Enum):
    process_url = "process_url"


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_id)
    source_url: Mapped[str] = mapped_column(Text, index=True)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    slug: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(16), default=DocumentStatus.queued.value, index=True)
    output_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_markdown_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    polished_markdown_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_count: Mapped[int] = mapped_column(Integer, default=0)
    document_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskJob(Base):
    __tablename__ = "task_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_id)
    task_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), default=TaskStatus.queued.value, index=True)
    queue_backend: Mapped[str] = mapped_column(String(16), default="db")
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
