from __future__ import annotations

import hashlib
import mimetypes
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from ..config import settings

MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)]+)\)")
HTML_IMAGE_PATTERN = re.compile(r'<img[^>]+src=["\'](?P<target>[^"\']+)["\'][^>]*>', flags=re.IGNORECASE)


@dataclass(slots=True)
class DocumentPaths:
    output_dir: Path
    raw_path: Path
    polished_path: Path
    assets_dir: Path


class DocumentFilesystemService:
    def __init__(self) -> None:
        self.session = requests.Session()

    def slugify_url(self, source_url: str) -> str:
        parsed = urlparse(source_url)
        candidates = [segment for segment in parsed.path.split("/") if segment]
        basis = candidates[-1] if candidates else parsed.netloc or "document"
        if basis.lower() in {"index", "home"} and len(candidates) > 1:
            basis = candidates[-2]
        slug = re.sub(r"[^a-z0-9]+", "-", basis.lower()).strip("-")
        return slug[:80] or "document"

    def build_paths(self, source_url: str, slug: str, created_at: datetime) -> DocumentPaths:
        output_root = settings.obsidian_output_root
        if output_root is None:
            raise ValueError("OBSIDIAN_VAULT_PATH 未配置。")

        date_segment = created_at.date().isoformat()
        digest = hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:8]
        output_dir = output_root / date_segment / f"{slug}-{digest}"
        return DocumentPaths(
            output_dir=output_dir,
            raw_path=output_dir / "raw.md",
            polished_path=output_dir / "polished.md",
            assets_dir=output_dir / "assets",
        )

    def prepare_workspace(self, paths: DocumentPaths) -> None:
        paths.output_dir.mkdir(parents=True, exist_ok=True)
        if paths.assets_dir.exists():
            shutil.rmtree(paths.assets_dir)
        paths.assets_dir.mkdir(parents=True, exist_ok=True)
        for path in (paths.raw_path, paths.polished_path):
            if path.exists():
                path.unlink()

    def ensure_output_root_writable(self) -> Path:
        output_root = settings.obsidian_output_root
        if output_root is None:
            raise ValueError("OBSIDIAN_VAULT_PATH 未配置。")
        output_root.mkdir(parents=True, exist_ok=True)
        probe = output_root / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return output_root

    def read_text(self, path: str | Path) -> str:
        return Path(path).read_text(encoding="utf-8")

    def write_text(self, path: str | Path, content: str) -> None:
        Path(path).write_text(content.rstrip() + "\n", encoding="utf-8")

    def localize_markdown_assets(
        self,
        markdown: str,
        *,
        assets_dir: str | Path,
        source_dir: str | Path,
    ) -> tuple[str, list[dict[str, str | int]]]:
        assets_path = Path(assets_dir)
        source_root = Path(source_dir)
        assets_path.mkdir(parents=True, exist_ok=True)

        url_map: dict[str, str] = {}

        def replace_markdown(match: re.Match[str]) -> str:
            target = self._clean_link_target(match.group("target"))
            if target.startswith("![["):
                return target
            localized = self._localize_target(
                target,
                assets_dir=assets_path,
                source_dir=source_root,
                url_map=url_map,
            )
            return f"![[{localized}]]"

        markdown = MARKDOWN_IMAGE_PATTERN.sub(replace_markdown, markdown)

        def replace_html(match: re.Match[str]) -> str:
            target = self._clean_link_target(match.group("target"))
            localized = self._localize_target(
                target,
                assets_dir=assets_path,
                source_dir=source_root,
                url_map=url_map,
            )
            return f"![[{localized}]]"

        markdown = HTML_IMAGE_PATTERN.sub(replace_html, markdown)
        return markdown, self.list_assets(assets_path)

    def list_assets(self, assets_dir: str | Path) -> list[dict[str, str | int]]:
        assets_path = Path(assets_dir)
        if not assets_path.exists():
            return []
        records: list[dict[str, str | int]] = []
        for path in sorted(item for item in assets_path.iterdir() if item.is_file()):
            records.append(
                {
                    "name": path.name,
                    "path": str(path.resolve()),
                    "size_bytes": path.stat().st_size,
                }
            )
        return records

    def _localize_target(
        self,
        target: str,
        *,
        assets_dir: Path,
        source_dir: Path,
        url_map: dict[str, str],
    ) -> str:
        if target.startswith("![[") and target.endswith("]]"):
            return target[3:-2]
        if target.startswith("http://") or target.startswith("https://"):
            if target in url_map:
                return url_map[target]
            filename = self._download_remote_asset(target, assets_dir)
            localized = f"assets/{filename}"
            url_map[target] = localized
            return localized

        local_path = (source_dir / target).resolve() if not Path(target).is_absolute() else Path(target)
        if not local_path.exists():
            raise ValueError(f"无法本地化图片资源：{target}")

        if local_path.parent.resolve() == assets_dir.resolve():
            return f"assets/{local_path.name}"

        destination = assets_dir / local_path.name
        if local_path.resolve() != destination.resolve():
            shutil.copy2(local_path, destination)
        return f"assets/{destination.name}"

    def _download_remote_asset(self, target: str, assets_dir: Path) -> str:
        response = self.session.get(target, timeout=30)
        response.raise_for_status()
        parsed = urlparse(target)
        stem = Path(parsed.path).stem or "image"
        stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-") or "image"
        guessed_ext = Path(parsed.path).suffix
        if not guessed_ext:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
            guessed_ext = mimetypes.guess_extension(content_type) or ".bin"
        digest = hashlib.sha1(target.encode("utf-8")).hexdigest()[:8]
        filename = f"{stem}-{digest}{guessed_ext}"
        destination = assets_dir / filename
        destination.write_bytes(response.content)
        return filename

    def _clean_link_target(self, target: str) -> str:
        cleaned = target.strip().strip("<>").strip()
        if " " in cleaned and not cleaned.startswith("http"):
            cleaned = cleaned.split(" ", 1)[0]
        return cleaned
