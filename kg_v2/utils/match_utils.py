"""Generic matching helpers for taxonomy attachment."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from kg_v2.utils.taxonomy_utils import (
    extract_genus_from_scientific_name,
    normalize_family_name,
    normalize_lookup_value,
    normalize_order_name,
)


def build_alias_index(
    alias_rows: Iterable[dict],
    canonical_nodes_by_id: dict[str, dict],
    allowed_ranks: set[str] | None = None,
) -> dict[str, list[dict]]:
    alias_index: dict[str, list[dict]] = defaultdict(list)
    ranks = allowed_ranks or set()
    for alias in alias_rows:
        canonical_taxon_id = alias.get("canonical_taxon_id", "")
        if not canonical_taxon_id:
            continue
        node = canonical_nodes_by_id.get(canonical_taxon_id)
        if not node:
            continue
        if ranks and node.get("rank") not in ranks:
            continue
        alias_type = alias.get("alias_type", "scientific_name")
        normalized = normalize_lookup_value(alias.get("alias_value", ""), alias_type)
        if not normalized:
            continue
        alias_index[normalized].append(node)
    return dict(alias_index)


def dedupe_candidates(candidates: Iterable[dict]) -> list[dict]:
    unique: dict[str, dict] = {}
    for candidate in candidates:
        taxon_id = candidate.get("taxon_id", "")
        if taxon_id:
            unique[taxon_id] = candidate
    return list(unique.values())


def filter_candidates(
    candidates: Iterable[dict],
    *,
    family_name: str = "",
    order_name: str = "",
    genus_name: str = "",
) -> list[dict]:
    normalized_family = normalize_family_name(family_name)
    normalized_order = normalize_order_name(order_name)
    normalized_genus = extract_genus_from_scientific_name(genus_name) if genus_name else ""
    filtered = list(dedupe_candidates(candidates))

    if normalized_family:
        filtered = [
            candidate
            for candidate in filtered
            if normalize_family_name(candidate.get("family_name", "")) == normalized_family
        ]
    if normalized_order:
        filtered = [
            candidate
            for candidate in filtered
            if normalize_order_name(candidate.get("order_name", "")) == normalized_order
        ]
    if normalized_genus:
        filtered = [
            candidate
            for candidate in filtered
            if extract_genus_from_scientific_name(candidate.get("genus_name") or candidate.get("scientific_name", ""))
            == normalized_genus
        ]
    return filtered


def mismatch_reason(
    candidates: Iterable[dict],
    *,
    family_name: str = "",
    order_name: str = "",
    genus_name: str = "",
    empty_reason: str,
    ambiguous_reason: str = "AMBIGUOUS_MATCH",
) -> tuple[str, str]:
    deduped = dedupe_candidates(candidates)
    if not deduped:
        return empty_reason, ""

    normalized_family = normalize_family_name(family_name)
    normalized_order = normalize_order_name(order_name)
    normalized_genus = extract_genus_from_scientific_name(genus_name) if genus_name else ""

    if normalized_order and all(normalize_order_name(candidate.get("order_name", "")) != normalized_order for candidate in deduped):
        return "ORDER_MISMATCH", f"requested_order={order_name}"
    if normalized_family and all(normalize_family_name(candidate.get("family_name", "")) != normalized_family for candidate in deduped):
        return "FAMILY_MISMATCH", f"requested_family={family_name}"
    if normalized_genus and all(
        extract_genus_from_scientific_name(candidate.get("genus_name") or candidate.get("scientific_name", ""))
        != normalized_genus
        for candidate in deduped
    ):
        return "GENUS_MISMATCH", f"requested_genus={genus_name}"
    if len(deduped) > 1:
        sample = ", ".join(sorted(candidate.get("scientific_name", "") for candidate in deduped[:5]))
        return ambiguous_reason, sample
    return empty_reason, ""
