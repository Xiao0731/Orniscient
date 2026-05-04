"""Build conflict records between canonical AviList and Clements."""

from __future__ import annotations

from pathlib import Path

from kg_v2.Step1_taxonomy.common import stable_hash, write_jsonl
from kg_v2.Step1_taxonomy.parsers.normalize_taxonomy_names import extract_genus_from_scientific_name
from kg_v2.Step1_taxonomy.schema.taxonomy_schema import TaxonomyConflict
from kg_v2.Step1_taxonomy.schema.taxonomy_types import (
    CLEMENTS,
    FAMILY_MISMATCH,
    GENUS_MISMATCH,
    NAME_MISMATCH,
    RANK_MISMATCH,
    SPLIT_LUMP_DRIFT,
    UNRESOLVED,
)


def build_taxonomy_conflicts(
    canonical_nodes: list[dict],
    clements_rows: list[dict],
    crosswalks: list[dict],
    output_path: str | Path,
) -> list[dict]:
    canonical_by_id = {node["taxon_id"]: node for node in canonical_nodes}
    clements_by_key = {
        (
            row.get("rank", ""),
            row.get("scientific_name", ""),
            row.get("species_code", ""),
            row.get("external_id", ""),
        ): row
        for row in clements_rows
    }
    conflicts: list[dict] = []

    def add_conflict(canonical_taxon_id: str, conflict_type: str, canonical_value: str, external_value: str, notes: str) -> None:
        conflicts.append(
            TaxonomyConflict(
                conflict_id=stable_hash(canonical_taxon_id, conflict_type, canonical_value, external_value, notes, prefix="conflict_"),
                canonical_taxon_id=canonical_taxon_id,
                external_source=CLEMENTS,
                conflict_type=conflict_type,
                canonical_value=canonical_value,
                external_value=external_value,
                resolution_status="pending_review",
                notes=notes,
            ).to_dict()
        )

    for crosswalk in crosswalks:
        row = clements_by_key.get(
            (
                crosswalk.get("external_rank", ""),
                crosswalk.get("external_scientific_name", ""),
                crosswalk.get("external_code", ""),
                crosswalk.get("external_id", ""),
            )
        )
        canonical_taxon_id = crosswalk.get("canonical_taxon_id", "")
        if not canonical_taxon_id:
            add_conflict("", UNRESOLVED, "", crosswalk.get("external_scientific_name", ""), "Crosswalk could not be resolved.")
            continue
        canonical = canonical_by_id.get(canonical_taxon_id)
        if not canonical or not row:
            add_conflict(canonical_taxon_id, UNRESOLVED, "", crosswalk.get("external_scientific_name", ""), "Missing canonical or external row.")
            continue

        if canonical["rank"] != row.get("rank", ""):
            add_conflict(canonical_taxon_id, RANK_MISMATCH, canonical["rank"], row.get("rank", ""), "Canonical and external ranks differ.")
        if canonical.get("family_name", "") != row.get("family_name", ""):
            add_conflict(canonical_taxon_id, FAMILY_MISMATCH, canonical.get("family_name", ""), row.get("family_name", ""), "Canonical and external family differ.")
        canonical_genus = canonical.get("genus_name", "") or extract_genus_from_scientific_name(canonical.get("scientific_name", ""))
        external_genus = row.get("genus_name", "") or extract_genus_from_scientific_name(row.get("scientific_name", ""))
        if canonical_genus != external_genus:
            add_conflict(canonical_taxon_id, GENUS_MISMATCH, canonical_genus, external_genus, "Canonical and external genus differ.")
        if canonical.get("scientific_name", "") != row.get("scientific_name", ""):
            add_conflict(canonical_taxon_id, NAME_MISMATCH, canonical.get("scientific_name", ""), row.get("scientific_name", ""), "Canonical and external scientific names differ.")
        if row.get("change_note") or row.get("website_note"):
            notes = " ".join(part for part in [row.get("change_note", ""), row.get("website_note", "")] if part).strip()
            add_conflict(canonical_taxon_id, SPLIT_LUMP_DRIFT, canonical.get("scientific_name", ""), row.get("scientific_name", ""), notes)

    write_jsonl(output_path, conflicts)
    return conflicts
