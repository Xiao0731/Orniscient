"""Lightweight normalization for Step 3 claims and facts."""

from __future__ import annotations

from kg_v2.utils.hash_utils import stable_hash

QUALIFIER_KEYS = [
    "sex",
    "life_stage",
    "season",
    "breeding_status",
    "subspecies",
    "region_scope",
    "frequency",
]


def normalize_qualifiers(raw: dict | None) -> dict:
    raw = raw or {}
    normalized: dict[str, str] = {}
    for key in QUALIFIER_KEYS:
        value = " ".join(str(raw.get(key, "") or "").strip().split()).casefold()
        if key == "sex":
            if value in {"male", "males", "adult male"}:
                value = "male"
            elif value in {"female", "females", "adult female"}:
                value = "female"
        elif key == "life_stage":
            if value in {"juvenile", "juveniles", "immature", "immatures"}:
                value = "juvenile"
            elif value in {"adult", "adults"}:
                value = "adult"
        elif key == "breeding_status":
            if value in {"breeding", "breeding season", "during breeding"}:
                value = "breeding"
            elif value in {"non-breeding", "nonbreeding", "outside breeding"}:
                value = "non-breeding"
        normalized[key] = value
    return normalized


def canonicalize_object(claim: dict) -> tuple[str, str]:
    name = " ".join(str(claim.get("object_canonical_name") or "").strip().split())
    object_id = " ".join(str(claim.get("object_canonical_id") or "").strip().split())
    if object_id or name:
        return object_id, name
    return "", ""


def short_quote(text: str, max_chars: int = 240) -> str:
    quote = " ".join((text or "").strip().split())
    if len(quote) <= max_chars:
        return quote
    return quote[: max_chars - 1].rstrip() + "…"
