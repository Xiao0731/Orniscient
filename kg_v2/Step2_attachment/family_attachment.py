"""Attach parsed family records and chunks to canonical taxonomy families."""

from __future__ import annotations

from kg_v2.utils.hash_utils import stable_hash
from kg_v2.utils.match_utils import dedupe_candidates, filter_candidates, mismatch_reason
from kg_v2.utils.taxonomy_utils import normalize_lookup_value


def _family_record_id(record: dict) -> str:
    return stable_hash(
        record.get("family_name", ""),
        record.get("order_name", ""),
        prefix="family_record_",
    )


def _family_key(record: dict) -> tuple[str, str]:
    return (record.get("family_name", ""), record.get("order_name", ""))


def _match_family_record(record: dict, indexes: dict[str, object]) -> tuple[dict, dict | None]:
    family_name = record.get("family_name", "")
    order_name = record.get("order_name", "")
    base_link = {
        "record_id": _family_record_id(record),
        "family_name": family_name,
        "order_name": order_name,
    }

    if not family_name:
        return (
            {
                **base_link,
                "canonical_family_id": "",
                "canonical_family_name": "",
                "canonical_order_name": "",
                "match_method": "UNRESOLVED",
                "match_confidence": 0.0,
                "resolution_status": "unresolved",
            },
            {
                **base_link,
                "unresolved_reason": "EMPTY_FAMILY_NAME",
                "candidate_notes": "",
            },
        )

    normalized_family = normalize_lookup_value(family_name, "family_name")
    direct_candidates = dedupe_candidates(indexes["family_by_name"].get(normalized_family, []))
    filtered_direct = filter_candidates(direct_candidates, family_name=family_name, order_name=order_name)
    if len(filtered_direct) == 1:
        node = filtered_direct[0]
        return (
            {
                **base_link,
                "canonical_family_id": node["taxon_id"],
                "canonical_family_name": node.get("scientific_name", ""),
                "canonical_order_name": node.get("order_name", ""),
                "match_method": "DIRECT_FAMILY_MATCH",
                "match_confidence": 1.0,
                "resolution_status": "attached",
            },
            None,
        )
    if len(filtered_direct) > 1:
        return (
            {
                **base_link,
                "canonical_family_id": "",
                "canonical_family_name": "",
                "canonical_order_name": "",
                "match_method": "UNRESOLVED",
                "match_confidence": 0.0,
                "resolution_status": "unresolved",
            },
            {
                **base_link,
                "unresolved_reason": "AMBIGUOUS_MATCH",
                "candidate_notes": f"multiple direct candidates for {family_name}",
            },
        )

    alias_candidates = dedupe_candidates(indexes["family_alias_index"].get(normalized_family, []))
    filtered_alias = filter_candidates(alias_candidates, family_name=family_name, order_name=order_name)
    if len(filtered_alias) == 1:
        node = filtered_alias[0]
        return (
            {
                **base_link,
                "canonical_family_id": node["taxon_id"],
                "canonical_family_name": node.get("scientific_name", ""),
                "canonical_order_name": node.get("order_name", ""),
                "match_method": "ALIAS_MATCH",
                "match_confidence": 0.9,
                "resolution_status": "attached",
            },
            None,
        )

    order_key = normalize_lookup_value(order_name, "order_name")
    order_candidates = dedupe_candidates(indexes["family_by_order"].get(order_key, []))
    order_assisted = [
        candidate
        for candidate in order_candidates
        if normalize_lookup_value(candidate.get("scientific_name", ""), "family_name") == normalized_family
    ]
    if len(order_assisted) == 1:
        node = order_assisted[0]
        return (
            {
                **base_link,
                "canonical_family_id": node["taxon_id"],
                "canonical_family_name": node.get("scientific_name", ""),
                "canonical_order_name": node.get("order_name", ""),
                "match_method": "ORDER_ASSISTED_FAMILY_MATCH",
                "match_confidence": 0.84,
                "resolution_status": "attached",
            },
            None,
        )

    if direct_candidates:
        reason, notes = mismatch_reason(
            direct_candidates,
            family_name=family_name,
            order_name=order_name,
            empty_reason="FAMILY_NAME_NOT_FOUND",
        )
    elif alias_candidates:
        reason, notes = mismatch_reason(
            alias_candidates,
            family_name=family_name,
            order_name=order_name,
            empty_reason="FAMILY_NAME_NOT_FOUND",
        )
    elif len(order_candidates) > 1:
        reason, notes = "AMBIGUOUS_MATCH", f"multiple families under order {order_name}"
    else:
        reason, notes = "FAMILY_NAME_NOT_FOUND", "no canonical or alias hit"

    return (
        {
            **base_link,
            "canonical_family_id": "",
            "canonical_family_name": "",
            "canonical_order_name": "",
            "match_method": "UNRESOLVED",
            "match_confidence": 0.0,
            "resolution_status": "unresolved",
        },
        {
            **base_link,
            "unresolved_reason": reason,
            "candidate_notes": notes,
        },
    )


def attach_family_records_and_chunks(
    family_records: list[dict],
    family_chunks: list[dict],
    indexes: dict[str, object],
) -> tuple[list[dict], list[dict], list[dict]]:
    record_links: list[dict] = []
    unresolved_records: list[dict] = []
    link_by_key: dict[tuple[str, str], dict] = {}

    for record in family_records:
        link, unresolved = _match_family_record(record, indexes)
        record_links.append(link)
        link_by_key[_family_key(record)] = link
        if unresolved:
            unresolved_records.append(unresolved)

    chunk_links: list[dict] = []
    for chunk in family_chunks:
        record_link = link_by_key.get(_family_key(chunk))
        if record_link is None:
            record_link, _ = _match_family_record(chunk, indexes)
        chunk_links.append(
            {
                "chunk_id": chunk.get("chunk_id", ""),
                "family_name": chunk.get("family_name", ""),
                "order_name": chunk.get("order_name", ""),
                "source_file": chunk.get("source_file", ""),
                "source_chapter": chunk.get("source_chapter", "Unknown"),
                "source_subchapter": chunk.get("source_subchapter", "Unknown"),
                "canonical_family_id": record_link.get("canonical_family_id", ""),
                "canonical_family_name": record_link.get("canonical_family_name", ""),
                "match_method": record_link.get("match_method", "UNRESOLVED"),
                "resolution_status": record_link.get("resolution_status", "unresolved"),
            }
        )

    return record_links, chunk_links, unresolved_records
