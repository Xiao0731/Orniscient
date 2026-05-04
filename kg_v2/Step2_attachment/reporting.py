"""Reporting helpers for Step 2 taxonomy attachment."""

from __future__ import annotations

from collections import Counter


def _top_reason_counts(rows: list[dict], *, field_name: str) -> list[dict]:
    counter = Counter(row.get(field_name, "UNKNOWN") for row in rows)
    return [{"reason": reason, "count": count} for reason, count in counter.most_common()]


def build_attachment_summary(
    *,
    species_record_links: list[dict],
    species_chunk_links: list[dict],
    family_record_links: list[dict],
    family_chunk_links: list[dict],
    unresolved_species: list[dict],
    unresolved_family: list[dict],
    input_paths: dict[str, str],
    output_paths: dict[str, str],
) -> dict:
    species_record_total = len(species_record_links)
    species_record_attached = sum(1 for row in species_record_links if row.get("resolution_status") == "attached")
    species_chunk_total = len(species_chunk_links)
    species_chunk_attached = sum(1 for row in species_chunk_links if row.get("resolution_status") == "attached")
    family_record_total = len(family_record_links)
    family_record_attached = sum(1 for row in family_record_links if row.get("resolution_status") == "attached")
    family_chunk_total = len(family_chunk_links)
    family_chunk_attached = sum(1 for row in family_chunk_links if row.get("resolution_status") == "attached")

    return {
        "input_paths": input_paths,
        "output_paths": output_paths,
        "species_record_total": species_record_total,
        "species_record_attached": species_record_attached,
        "species_record_unresolved": len(unresolved_species),
        "species_record_attachment_rate": (species_record_attached / species_record_total) if species_record_total else 0.0,
        "species_chunk_total": species_chunk_total,
        "species_chunk_attached": species_chunk_attached,
        "family_record_total": family_record_total,
        "family_record_attached": family_record_attached,
        "family_record_unresolved": len(unresolved_family),
        "family_record_attachment_rate": (family_record_attached / family_record_total) if family_record_total else 0.0,
        "family_chunk_total": family_chunk_total,
        "family_chunk_attached": family_chunk_attached,
        "top_species_unresolved_reasons": _top_reason_counts(unresolved_species, field_name="unresolved_reason"),
        "top_family_unresolved_reasons": _top_reason_counts(unresolved_family, field_name="unresolved_reason"),
    }

