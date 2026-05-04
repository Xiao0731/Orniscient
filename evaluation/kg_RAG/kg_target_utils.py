from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

KG_CONTEXT_VERSION = "v3_source_aligned_node_full_segment"


def _string_candidates(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        ordered_keys = ("common_name", "scientific_name", "name", "entity")
        candidates: list[str] = []
        for key in ordered_keys:
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                candidates.append(nested.strip())
        return candidates
    if isinstance(value, list):
        candidates: list[str] = []
        for item in value:
            candidates.extend(_string_candidates(item))
        return candidates
    text = str(value).strip()
    return [text] if text else []


def get_target_entity(q: dict[str, Any]) -> str:
    metadata = q.get("metadata", {}) or {}
    field_priority = (
        q.get("target_entity"),
        q.get("target_species"),
        q.get("common_name"),
        q.get("scientific_name"),
        q.get("species"),
        metadata.get("target_entity"),
        metadata.get("common_name"),
        metadata.get("scientific_name"),
    )
    for value in field_priority:
        for candidate in _string_candidates(value):
            if candidate:
                return candidate
    return ""


def classify_kg_context_status(target_entity: str, kg_context: str) -> str:
    if not str(target_entity or "").strip():
        return "missing_target_entity"
    if str(kg_context or "").startswith("[NO_KG_CONTEXT"):
        return "no_context"
    return "ok"


def build_kg_cache_key(target_entity: str, question: str, context_style: str = "relation_only") -> str:
    entity = str(target_entity or "").strip()
    style = str(context_style or "relation_only").strip() or "relation_only"
    question_hash = hashlib.sha1(str(question or "").strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"{KG_CONTEXT_VERSION}||{style}||{entity}||{question_hash}"


def load_kg_cache(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    cache_path = Path(path)
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_kg_cache(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
