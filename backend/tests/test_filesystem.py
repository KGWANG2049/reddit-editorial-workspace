from __future__ import annotations

from pathlib import Path

from app.services.filesystem import DocumentFilesystemService


class _FakeResponse:
    def __init__(self, content: bytes, content_type: str):
        self.content = content
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self) -> None:
        return None


def test_localize_markdown_assets_downloads_remote_images(monkeypatch, tmp_path):
    service = DocumentFilesystemService()
    monkeypatch.setattr(
        service.session,
        "get",
        lambda url, timeout=30: _FakeResponse(b"image-bytes", "image/png"),
    )

    markdown = "![hero](https://images.example.com/photo)\n"
    localized, assets = service.localize_markdown_assets(
        markdown,
        assets_dir=tmp_path / "assets",
        source_dir=tmp_path,
    )

    assert "![[assets/photo-" in localized
    assert assets[0]["name"].endswith(".png")
    assert Path(str(assets[0]["path"])).exists()


def test_build_paths_uses_slug_hash_and_date(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.filesystem.settings.obsidian_vault_path", str(tmp_path))
    monkeypatch.setattr("app.services.filesystem.settings.obsidian_output_subdir", "captures")
    service = DocumentFilesystemService()
    created_at = __import__("datetime").datetime(2026, 4, 17)

    paths = service.build_paths("https://example.com/posts/hello-world", "hello-world", created_at)

    assert "/captures/2026-04-17/hello-world-" in str(paths.output_dir)
    assert paths.raw_path.name == "raw.md"
    assert paths.polished_path.name == "polished.md"
    assert paths.assets_dir.name == "assets"
