from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas
from .bootstrap import init_db
from .config import settings
from .database import get_session
from .jobs import capture_service, filesystem_service, polish_service
from .repository import Repository
from .task_dispatch import enqueue_process_task, retry_task_job


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="URL Markdown Workbench", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def build_integrations_status() -> schemas.IntegrationStatusRead:
    obsidian_detail = (
        f"Vault: {settings.obsidian_vault_dir} · 输出模式：本地 Obsidian 目录"
        if settings.obsidian_configured
        else "缺少 OBSIDIAN_VAULT_PATH。"
    )
    openai_detail = (
        f"已配置 OpenAI Responses API，polish 模型为 {settings.openai_polish_model}。"
        if settings.openai_enabled
        else "缺少 OPENAI_API_KEY。"
    )
    return schemas.IntegrationStatusRead(
        obsidian=schemas.IntegrationProviderRead(
            provider="obsidian",
            configured=settings.obsidian_configured,
            mode="vault-output" if settings.obsidian_configured else "missing-config",
            detail=obsidian_detail,
        ),
        openai=schemas.IntegrationProviderRead(
            provider="openai",
            configured=settings.openai_enabled,
            mode="responses" if settings.openai_enabled else "missing-config",
            detail=openai_detail,
            model=settings.openai_polish_model,
        ),
    )


def serialize_document(document: models.Document) -> schemas.DocumentRead:
    return schemas.DocumentRead(
        id=document.id,
        source_url=document.source_url,
        source_title=document.source_title,
        slug=document.slug,
        status=document.status,
        output_dir=document.output_dir,
        raw_markdown_path=document.raw_markdown_path,
        polished_markdown_path=document.polished_markdown_path,
        asset_count=document.asset_count,
        metadata=document.document_metadata,
        error=document.error,
        created_at=document.created_at,
        updated_at=document.updated_at,
        processed_at=document.processed_at,
    )


@app.get("/health", response_model=schemas.HealthRead)
def health() -> schemas.HealthRead:
    return schemas.HealthRead(
        status="ok",
        queue_backend="db",
        output_root=str(settings.obsidian_output_root) if settings.obsidian_output_root else None,
    )


@app.get("/integrations/status", response_model=schemas.IntegrationStatusRead)
def integrations_status() -> schemas.IntegrationStatusRead:
    return build_integrations_status()


@app.post("/integrations/obsidian/test", response_model=schemas.IntegrationTestRead)
def test_obsidian_integration() -> schemas.IntegrationTestRead:
    ok, detail = capture_service.test_connection()
    if ok:
        try:
            output_root = filesystem_service.ensure_output_root_writable()
            detail = f"{detail} · 输出目录可写：{output_root}"
        except Exception as exc:
            ok = False
            detail = f"输出目录不可写：{exc}"
    return schemas.IntegrationTestRead(provider="obsidian", ok=ok, detail=detail)


@app.post("/integrations/openai/test", response_model=schemas.IntegrationTestRead)
def test_openai_integration() -> schemas.IntegrationTestRead:
    ok, detail = polish_service.test_connection()
    return schemas.IntegrationTestRead(provider="openai", ok=ok, detail=detail)


@app.post("/documents/process", response_model=schemas.ProcessDocumentsResponse)
def process_documents(
    payload: schemas.ProcessDocumentsRequest,
    session: Session = Depends(get_session),
) -> schemas.ProcessDocumentsResponse:
    urls: list[str] = []
    seen: set[str] = set()
    for raw_url in payload.urls:
        normalized = raw_url.strip()
        if not normalized:
            continue
        if not normalized.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail=f"Invalid URL: {normalized}")
        if normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)

    if not urls:
        raise HTTPException(status_code=400, detail="At least one URL is required")

    repo = Repository(session)
    items: list[schemas.DocumentQueueRead] = []
    for url in urls:
        slug = filesystem_service.slugify_url(url)
        document = repo.create_document(url, slug)
        job = enqueue_process_task(repo, document.id)
        items.append(
            schemas.DocumentQueueRead(
                document=serialize_document(document),
                job=schemas.TaskJobRead.model_validate(job),
            )
        )
    session.commit()
    return schemas.ProcessDocumentsResponse(accepted=len(items), items=items)


@app.get("/documents", response_model=list[schemas.DocumentRead])
def list_documents(
    limit: int = 50,
    session: Session = Depends(get_session),
):
    repo = Repository(session)
    return [serialize_document(document) for document in repo.list_documents(limit=limit)]


@app.get("/documents/{document_id}", response_model=schemas.DocumentDetailRead)
def get_document(document_id: str, session: Session = Depends(get_session)):
    repo = Repository(session)
    document = repo.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    raw_markdown = None
    polished_markdown = None
    assets: list[schemas.AssetRead] = []
    if document.raw_markdown_path and Path(document.raw_markdown_path).exists():
        raw_markdown = filesystem_service.read_text(document.raw_markdown_path)
    if document.polished_markdown_path and Path(document.polished_markdown_path).exists():
        polished_markdown = filesystem_service.read_text(document.polished_markdown_path)
    if document.output_dir:
        assets = [
            schemas.AssetRead(**asset)
            for asset in filesystem_service.list_assets(Path(document.output_dir) / "assets")
        ]

    latest_job = repo.get_latest_task_job_for_document(document.id)
    return schemas.DocumentDetailRead(
        **serialize_document(document).model_dump(),
        raw_markdown=raw_markdown,
        polished_markdown=polished_markdown,
        assets=assets,
        latest_job=schemas.TaskJobRead.model_validate(latest_job) if latest_job else None,
    )


@app.get("/jobs", response_model=list[schemas.TaskJobRead])
def list_jobs(
    limit: int = 20,
    status: str | None = None,
    task_type: str | None = None,
    session: Session = Depends(get_session),
):
    repo = Repository(session)
    return [
        schemas.TaskJobRead.model_validate(job)
        for job in repo.list_task_jobs(limit=limit, status=status, task_type=task_type)
    ]


@app.get("/jobs/{job_id}", response_model=schemas.TaskJobRead)
def get_job(job_id: str, session: Session = Depends(get_session)):
    repo = Repository(session)
    job = repo.get_task_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return schemas.TaskJobRead.model_validate(job)


@app.post("/jobs/{job_id}/retry", response_model=schemas.TaskJobRead)
def retry_job(
    job_id: str,
    _payload: schemas.TaskJobRetryRequest | None = None,
    session: Session = Depends(get_session),
):
    repo = Repository(session)
    source_job = repo.get_task_job(job_id)
    if not source_job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        retried_job = retry_task_job(repo, source_job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    session.refresh(retried_job)
    return schemas.TaskJobRead.model_validate(retried_job)
