from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./document_workbench.db")
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:3000")
    worker_poll_interval_seconds: float = float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "1.0"))

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    openai_polish_model: str = os.getenv("OPENAI_POLISH_MODEL", "gpt-5")

    obsidian_vault_path: str | None = os.getenv("OBSIDIAN_VAULT_PATH")
    obsidian_output_subdir: str = os.getenv("OBSIDIAN_OUTPUT_SUBDIR", "url-markdown-workbench").strip("/") or "url-markdown-workbench"

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def obsidian_configured(self) -> bool:
        return bool(self.obsidian_vault_path)

    @property
    def obsidian_vault_dir(self) -> Path | None:
        if not self.obsidian_vault_path:
            return None
        return Path(self.obsidian_vault_path).expanduser().resolve()

    @property
    def obsidian_output_root(self) -> Path | None:
        vault_dir = self.obsidian_vault_dir
        if vault_dir is None:
            return None
        return vault_dir / self.obsidian_output_subdir


settings = Settings()
