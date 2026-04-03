from __future__ import annotations

import requests

from ..config import settings


class MarkdownPolishService:
    def polish(self, *, source_url: str, source_title: str | None, raw_markdown: str) -> str:
        prompt = (
            "你是一个 Markdown 编辑整理助手。"
            "请把输入内容整理成更易读的中文 Markdown 成稿，保留事实顺序，不要编造信息。"
            "必须保留和重排已有图片，但只能使用已经存在的 Obsidian 本地图片 embed，例如 ![[assets/example.png]]。"
            "不要输出任何解释，只输出最终 Markdown。"
            f"\n原始链接：{source_url}"
            f"\n标题：{source_title or '未提供'}"
            f"\n原始 Markdown：\n{raw_markdown}"
        )
        text, error = self._request_openai(prompt, settings.openai_polish_model)
        if error:
            raise RuntimeError(f"OpenAI polish 失败：{error}")
        if not text:
            raise RuntimeError("OpenAI polish 返回空内容。")
        return text.strip()

    def test_connection(self) -> tuple[bool, str]:
        if not settings.openai_enabled:
            return False, "缺少 OPENAI_API_KEY。"
        text, error = self._request_openai(
            "Reply with OK only.",
            settings.openai_polish_model,
            max_output_tokens=12,
        )
        if error:
            return False, f"OpenAI 测试失败：{error}"
        return True, f"OpenAI 连通，polish 模型 {settings.openai_polish_model} 返回：{text[:40]}"

    def _request_openai(
        self,
        prompt: str,
        model: str,
        *,
        max_output_tokens: int | None = None,
    ) -> tuple[str | None, str | None]:
        if not settings.openai_enabled:
            return None, "OPENAI_API_KEY 未配置。"

        body: dict[str, object] = {"model": model, "input": prompt}
        if max_output_tokens is not None:
            body["max_output_tokens"] = max_output_tokens

        try:
            response = requests.post(
                f"{settings.openai_base_url}/responses",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return None, str(exc)

        text = payload.get("output_text")
        if isinstance(text, str) and text.strip():
            return text.strip(), None

        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    candidate = content.get("text")
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip(), None
        return None, "OpenAI 响应中没有 output_text。"
