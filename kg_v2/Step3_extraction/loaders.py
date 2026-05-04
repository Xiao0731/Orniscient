"""Load Step 2 attachment outputs and source chunks for Step 3."""

from __future__ import annotations

from pathlib import Path

from kg_v2.utils.jsonl_utils import read_jsonl


def require_path(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {label}: {path}")
    return path


def load_step3_inputs(*, intermediate_dir: Path, attachments_dir: Path, taxonomy_dir: Path) -> dict[str, object]:
    species_chunk_links = read_jsonl(require_path(attachments_dir / "species_chunk_taxonomy_links.jsonl", "species chunk links"))
    family_chunk_links = read_jsonl(require_path(attachments_dir / "family_chunk_taxonomy_links.jsonl", "family chunk links"))
    species_links = read_jsonl(require_path(attachments_dir / "species_taxonomy_links.jsonl", "species taxonomy links"))
    family_links = read_jsonl(require_path(attachments_dir / "family_taxonomy_links.jsonl", "family taxonomy links"))
    species_chunks = read_jsonl(require_path(intermediate_dir / "species_chunks.jsonl", "species chunks"))
    family_chunks = read_jsonl(require_path(intermediate_dir / "family_chunks.jsonl", "family chunks"))
    canonical_nodes = read_jsonl(require_path(taxonomy_dir / "canonical_taxon_nodes.jsonl", "canonical taxonomy nodes"))

    return {
        "species_chunk_links": species_chunk_links,
        "family_chunk_links": family_chunk_links,
        "species_links": species_links,
        "family_links": family_links,
        "species_chunks_by_id": {row.get("chunk_id", ""): row for row in species_chunks},
        "family_chunks_by_id": {row.get("chunk_id", ""): row for row in family_chunks},
        "canonical_nodes_by_id": {row.get("taxon_id", ""): row for row in canonical_nodes},
    }

