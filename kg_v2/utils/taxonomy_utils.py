"""Taxonomy normalization helpers shared across Step 1 and Step 2."""

from __future__ import annotations

import re


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def normalize_scientific_name(value: str) -> str:
    text = _normalize_space(value)
    return text.replace(" ,", ",")


def strip_family_parenthetical_name(value: str) -> str:
    text = _normalize_space(value)
    return re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()


def normalize_family_name(value: str) -> str:
    return normalize_scientific_name(strip_family_parenthetical_name(value))


def normalize_order_name(value: str) -> str:
    return normalize_scientific_name(value)


def normalize_english_name(value: str) -> str:
    text = _normalize_space(value)
    return text.replace(" ,", ",")


def extract_genus_from_scientific_name(value: str) -> str:
    text = normalize_scientific_name(value)
    parts = text.split()
    return parts[0] if parts else ""


def normalize_rank(value: str) -> str:
    return _normalize_space(value).lower()


def normalize_code(value: str) -> str:
    return _normalize_space(value).lower()


def normalize_avibase_id(value: str) -> str:
    text = _normalize_space(value)
    text = text.replace("avibase-", "").replace("Avibase-", "")
    return text.upper()


def clean_bow_scientific_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    normalized = " ".join(name.split()).strip()
    normalized = re.sub(r"\s+Scientific name definitions\s*$", "", normalized, flags=re.IGNORECASE)
    return normalized


def scientific_binomial(value: str) -> str:
    parts = normalize_scientific_name(value).split()
    return " ".join(parts[:2]) if len(parts) >= 2 else normalize_scientific_name(value)


def normalize_lookup_value(value: str, value_kind: str = "scientific_name") -> str:
    if value_kind in {"scientific_name", "species_name"}:
        return normalize_scientific_name(value).casefold()
    if value_kind == "english_name":
        return normalize_english_name(value).casefold()
    if value_kind == "family_name":
        return normalize_family_name(value).casefold()
    if value_kind == "order_name":
        return normalize_order_name(value).casefold()
    if value_kind == "species_code":
        return normalize_code(value)
    if value_kind == "external_id":
        return normalize_avibase_id(value)
    return _normalize_space(value).casefold()

