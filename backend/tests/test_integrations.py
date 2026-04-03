from __future__ import annotations

from pathlib import Path

import app.main as main
from app.services.markdown_polish import MarkdownPolishService
from app.services.obsidian_capture import ObsidianCaptureService


def test_build_integrations_status_reports_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(main.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    Path(main.settings.obsidian_vault_path).mkdir()
    monkeypatch.setattr(main.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(main.settings, "openai_polish_model", "gpt-5")

    status = main.build_integrations_status()

    assert status.obsidian.configured is True
    assert status.obsidian.mode == "vault-output"
    assert status.openai.configured is True
    assert status.openai.model == "gpt-5"


def test_obsidian_capture_service_test_connection_reports_missing_vault(monkeypatch):
    monkeypatch.setattr(main.settings, "obsidian_vault_path", None)

    ok, detail = ObsidianCaptureService().test_connection()

    assert ok is False
    assert "OBSIDIAN_VAULT_PATH" in detail


def test_obsidian_capture_service_falls_back_to_builtin_requests(monkeypatch, tmp_path):
    class _HtmlResponse:
        def __init__(self) -> None:
            self.text = """
                <html>
                  <head>
                    <title>Example Title</title>
                    <meta name="description" content="Page summary">
                  </head>
                  <body>
                    <img src="/hero.png" />
                    <p>First paragraph.</p>
                    <p>Second paragraph.</p>
                  </body>
                </html>
            """
            self.encoding = "utf-8"
            self.apparent_encoding = "utf-8"

        def raise_for_status(self) -> None:
            return None

    service = ObsidianCaptureService()
    monkeypatch.setattr("app.services.obsidian_capture.shutil.which", lambda command: None)
    monkeypatch.setattr(service.session, "get", lambda url, timeout=30: _HtmlResponse())

    raw_path = tmp_path / "raw.md"
    result = service.capture("https://example.com/article", raw_path, tmp_path / "assets")

    markdown = raw_path.read_text(encoding="utf-8")
    assert result.title == "Example Title"
    assert result.metadata["capture_backend"] == "builtin-requests"
    assert "# Example Title" in markdown
    assert "Source: https://example.com/article" in markdown
    assert "![](https://example.com/hero.png)" in markdown
    assert "First paragraph." in markdown


def test_markdown_polish_service_test_connection_returns_success(monkeypatch):
    monkeypatch.setattr(main.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(main.settings, "openai_polish_model", "gpt-5-mini")

    service = MarkdownPolishService()
    monkeypatch.setattr(service, "_request_openai", lambda prompt, model, max_output_tokens=None: ("OK", None))

    ok, detail = service.test_connection()

    assert ok is True
    assert "gpt-5-mini" in detail
    assert "OK" in detail
