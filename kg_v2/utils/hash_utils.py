"""Hash helpers shared across kg_v2 steps."""

from __future__ import annotations

import hashlib


def stable_hash(*parts: object, prefix: str = "") -> str:
    raw = "||".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:16]}"

