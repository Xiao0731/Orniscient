"""Load Step 1 taxonomy outputs and parsed BOW attachment inputs."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from kg_v2.utils.jsonl_utils import read_jsonl
from kg_v2.utils.match_utils import build_alias_index
from kg_v2.utils.taxonomy_utils import (
    extract_genus_from_scientific_name,
    normalize_family_name,
    normalize_lookup_value,
    normalize_order_name,
    normalize_scientific_name,
    scientific_binomial,
)


def require_path(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {label}: {path}")
    return path


def load_attachment_inputs(
    *,
    taxonomy_dir: Path,
    intermediate_dir: Path,
) -> dict[str, object]:
    canonical_nodes = read_jsonl(require_path(taxonomy_dir / "canonical_taxon_nodes.jsonl", "canonical nodes"))
    canonical_edges = read_jsonl(require_path(taxonomy_dir / "canonical_taxon_edges.jsonl", "canonical edges"))
    taxonomy_crosswalks = read_jsonl(require_path(taxonomy_dir / "taxonomy_crosswalks.jsonl", "taxonomy crosswalks"))
    taxonomy_aliases = read_jsonl(require_path(taxonomy_dir / "taxonomy_aliases.jsonl", "taxonomy aliases"))
    taxonomy_conflicts = read_jsonl(require_path(taxonomy_dir / "taxonomy_conflicts.jsonl", "taxonomy conflicts"))

    species_records = read_jsonl(require_path(intermediate_dir / "species_records.jsonl", "species records"))
    species_chunks = read_jsonl(require_path(intermediate_dir / "species_chunks.jsonl", "species chunks"))
    family_records = read_jsonl(require_path(intermediate_dir / "family_records.jsonl", "family records"))
    family_chunks = read_jsonl(require_path(intermediate_dir / "family_chunks.jsonl", "family chunks"))

    canonical_nodes_by_id = {node["taxon_id"]: node for node in canonical_nodes if node.get("taxon_id")}
    species_nodes = [node for node in canonical_nodes if node.get("rank") == "species"]
    family_nodes = [node for node in canonical_nodes if node.get("rank") == "family"]

    species_by_name: dict[str, list[dict]] = defaultdict(list)
    species_by_binomial: dict[str, list[dict]] = defaultdict(list)
    species_by_genus_family_order: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for node in species_nodes:
        normalized_name = normalize_lookup_value(node.get("scientific_name", ""), "scientific_name")
        if normalized_name:
            species_by_name[normalized_name].append(node)
        binomial = normalize_lookup_value(scientific_binomial(node.get("scientific_name", "")), "scientific_name")
        if binomial:
            species_by_binomial[binomial].append(node)
        genus = extract_genus_from_scientific_name(node.get("scientific_name", ""))
        key = (
            normalize_scientific_name(genus).casefold(),
            normalize_family_name(node.get("family_name", "")).casefold(),
            normalize_order_name(node.get("order_name", "")).casefold(),
        )
        species_by_genus_family_order[key].append(node)

    family_by_name: dict[str, list[dict]] = defaultdict(list)
    family_by_order: dict[str, list[dict]] = defaultdict(list)
    for node in family_nodes:
        normalized_family = normalize_lookup_value(node.get("scientific_name", ""), "family_name")
        if normalized_family:
            family_by_name[normalized_family].append(node)
        family_by_order[normalize_lookup_value(node.get("order_name", ""), "order_name")].append(node)

    species_alias_index = build_alias_index(
        taxonomy_aliases,
        canonical_nodes_by_id,
        allowed_ranks={"species"},
    )
    family_alias_index = build_alias_index(
        taxonomy_aliases,
        canonical_nodes_by_id,
        allowed_ranks={"family"},
    )

    return {
        "canonical_nodes": canonical_nodes,
        "canonical_edges": canonical_edges,
        "taxonomy_crosswalks": taxonomy_crosswalks,
        "taxonomy_aliases": taxonomy_aliases,
        "taxonomy_conflicts": taxonomy_conflicts,
        "canonical_nodes_by_id": canonical_nodes_by_id,
        "species_nodes": species_nodes,
        "family_nodes": family_nodes,
        "species_by_name": dict(species_by_name),
        "species_by_binomial": dict(species_by_binomial),
        "species_by_genus_family_order": dict(species_by_genus_family_order),
        "family_by_name": dict(family_by_name),
        "family_by_order": dict(family_by_order),
        "species_alias_index": species_alias_index,
        "family_alias_index": family_alias_index,
        "species_records": species_records,
        "species_chunks": species_chunks,
        "family_records": family_records,
        "family_chunks": family_chunks,
    }

