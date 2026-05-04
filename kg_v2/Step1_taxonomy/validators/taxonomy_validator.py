"""Validate taxonomy backbone outputs."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from kg_v2.Step1_taxonomy.common import write_json
from kg_v2.Step1_taxonomy.parsers.normalize_taxonomy_names import extract_genus_from_scientific_name
from kg_v2.Step1_taxonomy.schema.taxonomy_types import SUBSPECIES, SPECIES, VALID_RANKS


def validate_taxonomy(
    canonical_nodes: list[dict],
    canonical_edges: list[dict],
    crosswalks: list[dict],
    output_path: str | Path,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    rank_counts = Counter(node.get("rank", "") for node in canonical_nodes)
    ids = [node["taxon_id"] for node in canonical_nodes]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate taxon_id detected in canonical nodes.")

    nodes_by_id = {node["taxon_id"]: node for node in canonical_nodes}
    for node in canonical_nodes:
        rank = node.get("rank", "")
        if rank not in VALID_RANKS:
            errors.append(f"Invalid rank found: {rank}")
        parent_id = node.get("parent_taxon_id", "")
        if rank != "order" and parent_id and parent_id not in nodes_by_id:
            errors.append(f"Missing parent node for {node['taxon_id']}: {parent_id}")
        if rank in {SPECIES, SUBSPECIES}:
            scientific_name = node.get("scientific_name", "")
            genus = extract_genus_from_scientific_name(scientific_name)
            if not genus:
                errors.append(f"Could not extract genus from {rank} scientific name: {scientific_name}")

    seen_names: dict[tuple[str, str], list[str]] = defaultdict(list)
    for node in canonical_nodes:
        seen_names[(node.get("rank", ""), node.get("scientific_name", ""))].append(node["taxon_id"])
    duplicate_name_groups = {
        f"{rank}:{name}": ids for (rank, name), ids in seen_names.items() if len(ids) > 1 and name
    }
    if duplicate_name_groups:
        warnings.append(f"Found {len(duplicate_name_groups)} same-name same-rank duplicate groups.")

    unresolved = [row for row in crosswalks if row.get("match_method") == "UNRESOLVED"]
    unresolved_ratio = (len(unresolved) / len(crosswalks)) if crosswalks else 0.0
    if unresolved_ratio > 0.15:
        warnings.append(f"Unresolved crosswalk ratio is high: {unresolved_ratio:.4f}")

    report = {
        "summary": {
            "canonical_node_count": len(canonical_nodes),
            "canonical_edge_count": len(canonical_edges),
            "crosswalk_count": len(crosswalks),
            "unresolved_crosswalk_count": len(unresolved),
            "unresolved_crosswalk_ratio": unresolved_ratio,
        },
        "rank_counts": dict(rank_counts),
        "errors": errors,
        "warnings": warnings,
        "duplicate_name_groups": duplicate_name_groups,
    }
    write_json(output_path, report)
    return report
