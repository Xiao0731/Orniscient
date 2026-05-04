"""Small OpenAI-compatible chat client for structured extraction.

DeepSeek-compatible JSON mode version:
- Uses response_format={"type": "json_object"}
- Does NOT send OpenAI-style json_schema to provider
- Leaves schema validation to Python caller
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv is optional.
    load_dotenv = None


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 30
    temperature: float = 1.0
    max_retries: int = 2
    provider: str = "DeepSeek-compatible"
    api_key_source: str = ""
    base_url_source: str = ""
    model_source: str = ""


class LLMResponseError(RuntimeError):
    def __init__(self, message: str, *, raw_response_preview: str = "") -> None:
        super().__init__(message)
        self.raw_response_preview = raw_response_preview


def _load_repo_env() -> None:
    if not load_dotenv:
        return
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    else:
        load_dotenv(override=False)


def _first_env(names: list[str]) -> tuple[str, str]:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value, name
    return "", ""


def load_openai_compatible_config() -> OpenAICompatibleConfig | None:
    _load_repo_env()
    api_key, api_key_source = _first_env(["DEEPSEEK_API_KEY", "OPENAI_API_KEY"])
    base_url, base_url_source = _first_env(["DEEPSEEK_BASE_URL", "OPENAI_BASE_URL"])
    model, model_source = _first_env(["KG_LLM_MODEL", "DEEPSEEK_MODEL", "OPENAI_MODEL"])
    if not model:
        model = "deepseek-chat"
        model_source = "default"

    temperature_raw = os.environ.get("KG_EXTRACTION_TEMPERATURE", "1.0").strip()
    try:
        temperature = float(temperature_raw)
    except ValueError:
        temperature = 1.0

    timeout_raw = os.environ.get("KG_LLM_TIMEOUT_SECONDS", "30").strip()
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError:
        timeout_seconds = 30

    if not api_key or not base_url or not model:
        return None

    return OpenAICompatibleConfig(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model=model,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        api_key_source=api_key_source,
        base_url_source=base_url_source,
        model_source=model_source,
    )


def _strip_json_fence(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def chat_json_raw(
    *,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict[str, Any],  # kept for caller compatibility; validated locally, not sent to provider
    config: OpenAICompatibleConfig,
) -> tuple[dict[str, Any], str]:
    url = f"{config.base_url}/chat/completions"
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": config.temperature,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            response_payload = json.loads(response_body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMResponseError(
            f"LLM request failed: HTTP {exc.code}: {detail}",
            raw_response_preview=detail[:500],
        ) from exc
    except Exception as exc:
        raise LLMResponseError(f"LLM request failed before response parsing: {exc}") from exc

    try:
        content = response_payload["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LLMResponseError(
            f"LLM response missing choices/message/content: {exc}",
            raw_response_preview=json.dumps(response_payload, ensure_ascii=False)[:500],
        ) from exc

    if content is None:
        raise LLMResponseError("LLM returned empty JSON content", raw_response_preview="")

    content = _strip_json_fence(str(content))
    if not content:
        raise LLMResponseError("LLM returned empty JSON content", raw_response_preview="")

    try:
        return json.loads(content), content
    except json.JSONDecodeError as exc:
        raise LLMResponseError(
            f"LLM returned malformed JSON: {exc}",
            raw_response_preview=content[:500],
        ) from exc


def chat_json(
    *,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict[str, Any],
    config: OpenAICompatibleConfig,
) -> dict[str, Any]:
    parsed, _raw = chat_json_raw(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_schema=json_schema,
        config=config,
    )
    return parsed
