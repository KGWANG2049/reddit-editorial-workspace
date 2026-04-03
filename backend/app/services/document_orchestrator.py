from __future__ import annotations

from .. import models
from ..config import settings
from ..repository import Repository
from .filesystem import DocumentFilesystemService
from .markdown_polish import MarkdownPolishService
from .obsidian_capture import ObsidianCaptureService


class DocumentOrchestrator:
    def __init__(
        self,
        capture_service: ObsidianCaptureService,
        filesystem_service: DocumentFilesystemService,
        polish_service: MarkdownPolishService,
    ) -> None:
        self.capture = capture_service
        self.filesystem = filesystem_service
        self.polish = polish_service

    def process(self, repo: Repository, document: models.Document) -> dict:
        paths = self.filesystem.build_paths(document.source_url, document.slug, document.created_at)
        self.filesystem.prepare_workspace(paths)
        repo.update_document_paths(
            document,
            output_dir=str(paths.output_dir.resolve()),
            raw_markdown_path=str(paths.raw_path.resolve()),
            polished_markdown_path=str(paths.polished_path.resolve()),
        )
        repo.mark_document_status(document, models.DocumentStatus.capturing.value)
        repo.session.commit()

        capture_result = self.capture.capture(document.source_url, paths.raw_path, paths.assets_dir)
        raw_markdown = self.filesystem.read_text(paths.raw_path)
        raw_markdown, raw_assets = self.filesystem.localize_markdown_assets(
            raw_markdown,
            assets_dir=paths.assets_dir,
            source_dir=paths.output_dir,
        )
        self.filesystem.write_text(paths.raw_path, raw_markdown)
        raw_metadata = {
            **capture_result.metadata,
            "raw_asset_count": len(raw_assets),
            "stage": "captured",
        }
        repo.update_document_capture(
            document,
            source_title=capture_result.title,
            asset_count=len(raw_assets),
            metadata=raw_metadata,
        )
        repo.mark_document_status(document, models.DocumentStatus.polishing.value)
        repo.session.commit()

        polished_markdown = self.polish.polish(
            source_url=document.source_url,
            source_title=capture_result.title,
            raw_markdown=raw_markdown,
        )
        polished_markdown, polished_assets = self.filesystem.localize_markdown_assets(
            polished_markdown,
            assets_dir=paths.assets_dir,
            source_dir=paths.output_dir,
        )
        self.filesystem.write_text(paths.polished_path, polished_markdown)
        final_assets = self.filesystem.list_assets(paths.assets_dir)
        metadata = {
            **raw_metadata,
            "stage": "completed",
            "polish_model": settings.openai_polish_model,
            "asset_count": len(final_assets),
        }
        repo.complete_document(
            document,
            source_title=capture_result.title,
            asset_count=len(final_assets),
            metadata=metadata,
        )
        repo.session.commit()
        return {
            "document_id": document.id,
            "status": document.status,
            "raw_markdown_path": document.raw_markdown_path,
            "polished_markdown_path": document.polished_markdown_path,
            "asset_count": len(final_assets),
            "source_title": document.source_title,
        }
