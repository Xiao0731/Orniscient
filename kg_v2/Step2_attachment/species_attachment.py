"""Attach parsed BOW species records and chunks to canonical taxonomy species."""

from __future__ import annotations

from kg_v2.utils.hash_utils import stable_hash
from kg_v2.utils.match_utils import dedupe_candidates, filter_candidates, mismatch_reason
from kg_v2.utils.taxonomy_utils import (
    clean_bow_scientific_name,
    extract_genus_from_scientific_name,
    normalize_lookup_value,
    scientific_binomial,
)

ALLOWED_SPECIES_METHODS = {
    "DIRECT_SCI_MATCH",
    "ALIAS_MATCH",
    "CROSSWALK_MATCH",
    "FAMILY_ORDER_ASSISTED_MATCH",
    "UNRESOLVED",
}


def _species_record_id(record: dict) -> str:
    return stable_hash(
        record.get("common_name", ""),
        record.get("species_name", ""),
        record.get("genus_name", ""),
        record.get("family_name", ""),
        record.get("order_name", ""),
        prefix="species_record_",
    )


def _species_key(record: dict) -> tuple[str, str, str, str, str]:
    return (
        record.get("common_name", ""),
        record.get("species_name", ""),
        record.get("genus_name", ""),
        record.get("family_name", ""),
        record.get("order_name", ""),
    )


def _species_name_key(record: dict) -> tuple[str, str, str, str]:
    return (
        record.get("common_name", ""),
        record.get("species_name", ""),
        record.get("family_name", ""),
        record.get("order_name", ""),
    )


def _unresolved_payload(base_link: dict, reason: str, notes: str) -> dict:
    return {
        **base_link,
        "unresolved_reason": reason,
        "candidate_notes": notes,
    }


def _link_payload(base_link: dict, *, node: dict | None, method: str, confidence: float, status: str) -> dict:
    return {
        **base_link,
        "canonical_taxon_id": node["taxon_id"] if node else "",
        "canonical_scientific_name": node.get("scientific_name", "") if node else "",
        "canonical_rank": node.get("rank", "species") if node else "species",
        "match_method": method,
        "match_confidence": confidence,
        "resolution_status": status,
    }


def _match_species_record(record: dict, indexes: dict[str, object]) -> tuple[dict, dict | None]:
    species_name = clean_bow_scientific_name(record.get("species_name", ""))
    genus_name = record.get("genus_name", "") or extract_genus_from_scientific_name(species_name)
    family_name = record.get("family_name", "")
    order_name = record.get("order_name", "")
    base_link = {
        "record_id": _species_record_id(record),
        "common_name": record.get("common_name", ""),
        "species_name": species_name,
        "genus_name": genus_name,
        "family_name": family_name,
        "order_name": order_name,
    }

    if not species_name:
        return (
            _link_payload(base_link, node=None, method="UNRESOLVED", confidence=0.0, status="unresolved"),
            _unresolved_payload(base_link, "EMPTY_SPECIES_NAME", ""),
        )

    normalized_name = normalize_lookup_value(species_name, "scientific_name")
    direct_candidates = dedupe_candidates(indexes["species_by_name"].get(normalized_name, []))
    if len(direct_candidates) == 1:
        return (
            _link_payload(base_link, node=direct_candidates[0], method="DIRECT_SCI_MATCH", confidence=1.0, status="attached"),
            None,
        )
    filtered_direct = filter_candidates(
        direct_candidates,
        family_name=family_name,
        order_name=order_name,
        genus_name=genus_name,
    )
    if len(filtered_direct) == 1:
        return (
            _link_payload(base_link, node=filtered_direct[0], method="DIRECT_SCI_MATCH", confidence=0.98, status="attached"),
            None,
        )
    if len(filtered_direct) > 1:
        return (
            _link_payload(base_link, node=None, method="UNRESOLVED", confidence=0.0, status="unresolved"),
            _unresolved_payload(base_link, "AMBIGUOUS_MATCH", f"multiple direct candidates for {species_name}"),
        )

    alias_candidates = dedupe_candidates(indexes["species_alias_index"].get(normalized_name, []))
    filtered_alias = filter_candidates(
        alias_candidates,
        family_name=family_name,
        order_name=order_name,
        genus_name=genus_name,
    )
    if len(filtered_alias) == 1:
        return (
            _link_payload(base_link, node=filtered_alias[0], method="ALIAS_MATCH", confidence=0.93, status="attached"),
            None,
        )
    if len(filtered_alias) > 1:
        return (
            _link_payload(base_link, node=None, method="UNRESOLVED", confidence=0.0, status="unresolved"),
            _unresolved_payload(base_link, "AMBIGUOUS_MATCH", f"multiple alias candidates for {species_name}"),
        )

    assisted_candidates = []
    genus_key = normalize_lookup_value(genus_name, "scientific_name")
    family_key = normalize_lookup_value(family_name, "family_name")
    order_key = normalize_lookup_value(order_name, "order_name")
    if genus_key or family_key or order_key:
        assisted_candidates.extend(indexes["species_by_genus_family_order"].get((genus_key, family_key, order_key), []))
    binomial = normalize_lookup_value(scientific_binomial(species_name), "scientific_name")
    if binomial and binomial != normalized_name:
        assisted_candidates.extend(indexes["species_by_binomial"].get(binomial, []))
    filtered_assisted = filter_candidates(
        assisted_candidates,
        family_name=family_name,
        order_name=order_name,
        genus_name=genus_name,
    )
    if len(filtered_assisted) == 1:
        return (
            _link_payload(
                base_link,
                node=filtered_assisted[0],
                method="FAMILY_ORDER_ASSISTED_MATCH",
                confidence=0.82,
                status="attached",
            ),
            None,
        )

    if direct_candidates:
        reason, notes = mismatch_reason(
            direct_candidates,
            family_name=family_name,
            order_name=order_name,
            genus_name=genus_name,
            empty_reason="SCIENTIFIC_NAME_NOT_FOUND",
        )
    elif alias_candidates:
        reason, notes = mismatch_reason(
            alias_candidates,
            family_name=family_name,
            order_name=order_name,
            genus_name=genus_name,
            empty_reason="ALIAS_NOT_FOUND",
        )
    elif len(filtered_assisted) > 1 or len(assisted_candidates) > 1:
        reason, notes = "AMBIGUOUS_MATCH", f"multiple assisted candidates for genus={genus_name}"
    else:
        reason, notes = "SCIENTIFIC_NAME_NOT_FOUND", "no canonical or alias hit"

    return (
        _link_payload(base_link, node=None, method="UNRESOLVED", confidence=0.0, status="unresolved"),
        _unresolved_payload(base_link, reason, notes),
    )


def attach_species_records_and_chunks(
    species_records: list[dict],
    species_chunks: list[dict],
    indexes: dict[str, object],
) -> tuple[list[dict], list[dict], list[dict]]:
    record_links: list[dict] = []
    unresolved_records: list[dict] = []
    link_by_key: dict[tuple[str, str, str, str, str], dict] = {}
    link_by_name_key: dict[tuple[str, str, str, str], dict] = {}

    for record in species_records:
        link, unresolved = _match_species_record(record, indexes)
        if link["match_method"] not in ALLOWED_SPECIES_METHODS:
            raise ValueError(f"Unexpected species match method: {link['match_method']}")
        record_links.append(link)
        link_by_key[_species_key(record)] = link
        link_by_name_key[_species_name_key(record)] = link
        if unresolved:
            unresolved_records.append(unresolved)

    chunk_links: list[dict] = []
    for chunk in species_chunks:
        record_link = link_by_key.get(_species_key(chunk))
        if record_link is None:
            record_link = link_by_name_key.get(_species_name_key(chunk))
        if record_link is None:
            record_link = {
                "record_id": "",
                "canonical_taxon_id": "",
                "canonical_scientific_name": "",
                "match_method": "UNRESOLVED",
                "resolution_status": "unresolved",
            }
        chunk_links.append(
            {
                "chunk_id": chunk.get("chunk_id", ""),
                "parent_record_id": record_link.get("record_id", ""),
                "species_name": chunk.get("species_name", ""),
                "source_file": chunk.get("source_file", ""),
                "source_chapter": chunk.get("source_chapter", "Unknown"),
                "source_subchapter": chunk.get("source_subchapter", "Unknown"),
                "canonical_taxon_id": record_link.get("canonical_taxon_id", ""),
                "canonical_scientific_name": record_link.get("canonical_scientific_name", ""),
                "match_method": record_link.get("match_method", "UNRESOLVED"),
                "resolution_status": record_link.get("resolution_status", "unresolved"),
            }
        )

    return record_links, chunk_links, unresolved_records
