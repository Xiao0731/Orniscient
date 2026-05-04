"""Name normalization helpers for taxonomy backbone parsing."""

from __future__ import annotations

import re

from kg_v2.Step1_taxonomy.schema.taxonomy_types import FAMILY, GENUS, ORDER, SPECIES, SUBSPECIES


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
    normalized = _normalize_space(value).lower()
    mapping = {
        "order": ORDER,
        "family": FAMILY,
        "genus": GENUS,
        "species": SPECIES,
        "subspecies": SUBSPECIES,
        "ssp": SUBSPECIES,
    }
    return mapping.get(normalized, normalized)


def normalize_code(value: str) -> str:
    return _normalize_space(value).lower()


def normalize_avibase_id(value: str) -> str:
    text = _normalize_space(value)
    text = text.replace("avibase-", "").replace("Avibase-", "")
    return text.upper()
