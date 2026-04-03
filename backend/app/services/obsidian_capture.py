from __future__ import annotations

import html
import re
import shutil
import subprocess
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

from ..config import settings

TITLE_PATTERN = re.compile(r"^\s*#\s+(.+?)\s*$", flags=re.MULTILINE)
FALLBACK_LINE_PATTERN = re.compile(r"\S")


@dataclass(slots=True)
class CaptureResult:
    title: str | None
    metadata: dict


class _SimpleHtmlMarkdownParser(HTMLParser):
    def __init__(self, source_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.title: str | None = None
        self.description: str | None = None
        self.images: list[str] = []
        self.paragraphs: list[str] = []
        self._inside_title = False
        self._current_paragraph: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value for name, value in attrs}
        tag = tag.lower()
        if tag == "title":
            self._inside_title = True
            return
        if tag == "meta":
            self._handle_meta(attr_map)
            return
        if tag == "img":
            src = attr_map.get("src")
            if src:
                normalized = urljoin(self.source_url, src.strip())
                if normalized not in self.images:
                    self.images.append(normalized)
            return
        if tag == "p":
            self._current_paragraph = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._inside_title = False
            return
        if tag == "p" and self._current_paragraph is not None:
            paragraph = self._collapse_text("".join(self._current_paragraph))
            if paragraph:
                self.paragraphs.append(paragraph)
            self._current_paragraph = None

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return
        if self._inside_title:
            title = self._collapse_text(data)
            if title and not self.title:
                self.title = title
            return
        if self._current_paragraph is not None:
            self._current_paragraph.append(data)

    def _handle_meta(self, attrs: dict[str, str | None]) -> None:
        name = (attrs.get("name") or attrs.get("property") or "").lower()
        content = self._collapse_text(attrs.get("content") or "")
        if not content:
            return
        if name == "og:title" and not self.title:
            self.title = content
        elif name in {"description", "og:description"} and not self.description:
            self.description = content

    def _collapse_text(self, value: str) -> str:
        return " ".join(html.unescape(value).split())


class ObsidianCaptureService:
    def __init__(self) -> None:
        self.session = requests.Session()

    def capture(self, source_url: str, raw_path: str | Path, assets_dir: str | Path) -> CaptureResult:
        raw_file = Path(raw_path)
        assets_path = Path(assets_dir)
        assets_path.mkdir(parents=True, exist_ok=True)

        defuddle_path = shutil.which("defuddle")
        if defuddle_path:
            return self._capture_with_defuddle(defuddle_path, source_url, raw_file, assets_path)
        return self._capture_with_builtin_parser(source_url, raw_file)

    def test_connection(self) -> tuple[bool, str]:
        vault_dir = settings.obsidian_vault_dir
        if vault_dir is None:
            return False, "缺少 OBSIDIAN_VAULT_PATH。"
        if not vault_dir.exists():
            return False, f"Obsidian vault 不存在：{vault_dir}"
        if not vault_dir.is_dir():
            return False, f"Obsidian vault 不是目录：{vault_dir}"
        backend = "defuddle" if shutil.which("defuddle") else "built-in requests parser"
        return True, f"Obsidian vault 已配置：{vault_dir} · 抓取后端：{backend}"

    def _capture_with_defuddle(
        self,
        defuddle_path: str,
        source_url: str,
        raw_path: Path,
        _assets_dir: Path,
    ) -> CaptureResult:
        command = [defuddle_path, "parse", source_url, "--md", "-o", str(raw_path)]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or f"exit={completed.returncode}"
            raise RuntimeError(f"Defuddle 抓取失败：{stderr}")
        if not raw_path.exists():
            raise RuntimeError("Defuddle 未生成 raw.md。")

        markdown = raw_path.read_text(encoding="utf-8")
        title = self._infer_title(markdown)
        return CaptureResult(
            title=title,
            metadata={"capture_backend": "defuddle", "command": command},
        )

    def _capture_with_builtin_parser(self, source_url: str, raw_path: Path) -> CaptureResult:
        response = self.session.get(source_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.encoding or response.apparent_encoding or "utf-8"

        parser = _SimpleHtmlMarkdownParser(source_url)
        parser.feed(response.text)
        parser.close()

        markdown = self._render_markdown(
            source_url=source_url,
            title=parser.title,
            description=parser.description,
            images=parser.images,
            paragraphs=parser.paragraphs,
        )
        raw_path.write_text(markdown.rstrip() + "\n", encoding="utf-8")
        return CaptureResult(
            title=parser.title or self._infer_title(markdown),
            metadata={"capture_backend": "builtin-requests"},
        )

    def _render_markdown(
        self,
        *,
        source_url: str,
        title: str | None,
        description: str | None,
        images: list[str],
        paragraphs: list[str],
    ) -> str:
        lines: list[str] = []
        heading = title or "Captured Page"
        lines.append(f"# {heading}")
        lines.append("")
        lines.append(f"Source: {source_url}")
        if description:
            lines.extend(["", f"> {description}"])
        for image in images:
            lines.extend(["", f"![]({image})"])
        body = paragraphs or ["页面已抓取，但未从 HTML 中提取到正文段落。"]
        for paragraph in body:
            lines.extend(["", paragraph])
        return "\n".join(lines)

    def _infer_title(self, markdown: str) -> str | None:
        heading = TITLE_PATTERN.search(markdown)
        if heading:
            return heading.group(1).strip()
        first_line = FALLBACK_LINE_PATTERN.search(markdown)
        if not first_line:
            return None
        line = markdown[first_line.start() :].splitlines()[0].strip()
        return line[:160] if line else None
