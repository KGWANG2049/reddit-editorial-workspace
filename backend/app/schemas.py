from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthRead(BaseModel):
    status: str
    queue_backend: str
    output_root: str | None = None


class IntegrationProviderRead(BaseModel):
    provider: str
    configured: bool
    mode: str
    detail: str
    model: str | None = None


class IntegrationStatusRead(BaseModel):
    obsidian: IntegrationProviderRead
    openai: IntegrationProviderRead


class IntegrationTestRead(BaseModel):
    provider: str
    ok: bool
    detail: str


class ProcessDocumentsRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)


class DocumentRead(BaseModel):
    id: str
    source_url: str
    source_title: str | None = None
    slug: str
    status: str
    output_dir: str | None = None
    raw_markdown_path: str | None = None
    polished_markdown_path: str | None = None
    asset_count: int
    metadata: dict[str, Any]
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None

    model_config = {"from_attributes": True}


class AssetRead(BaseModel):
    name: str
    path: str
    size_bytes: int


class TaskJobRead(BaseModel):
    id: str
    task_type: str
    status: str
    queue_backend: str
    target_id: str | None = None
    result_payload: dict[str, Any]
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class DocumentQueueRead(BaseModel):
    document: DocumentRead
    job: TaskJobRead


class ProcessDocumentsResponse(BaseModel):
    accepted: int
    items: list[DocumentQueueRead]


class DocumentDetailRead(DocumentRead):
    raw_markdown: str | None = None
    polished_markdown: str | None = None
    assets: list[AssetRead] = Field(default_factory=list)
    latest_job: TaskJobRead | None = None


class TaskJobRetryRequest(BaseModel):
    note: str | None = None
