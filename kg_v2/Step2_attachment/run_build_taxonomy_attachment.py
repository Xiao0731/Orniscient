"""Run Step 2 taxonomy attachment pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KG_ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step2_attachment.family_attachment import attach_family_records_and_chunks
from kg_v2.Step2_attachment.loaders import load_attachment_inputs, require_path
from kg_v2.Step2_attachment.reporting import build_attachment_summary
from kg_v2.Step2_attachment.species_attachment import attach_species_records_and_chunks
from kg_v2.utils.jsonl_utils import write_json, write_jsonl


def _resolve_under_kg(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (KG_ROOT / path).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Step 2 taxonomy attachment artifacts")
    parser.add_argument("--taxonomy-dir", default="outputs/intermediate/taxonomy")
    parser.add_argument("--intermediate-dir", default="outputs/intermediate")
    parser.add_argument("--attachments-dir", default="outputs/intermediate/attachments")
    args = parser.parse_args()

    taxonomy_dir = _resolve_under_kg(args.taxonomy_dir)
    intermediate_dir = _resolve_under_kg(args.intermediate_dir)
    attachments_dir = _resolve_under_kg(args.attachments_dir)
    attachments_dir.mkdir(parents=True, exist_ok=True)

    require_path(taxonomy_dir / "canonical_taxon_nodes.jsonl", "canonical taxonomy nodes")
    require_path(intermediate_dir / "species_records.jsonl", "species records")
    require_path(intermediate_dir / "species_chunks.jsonl", "species chunks")
    require_path(intermediate_dir / "family_records.jsonl", "family records")
    require_path(intermediate_dir / "family_chunks.jsonl", "family chunks")

    inputs = load_attachment_inputs(taxonomy_dir=taxonomy_dir, intermediate_dir=intermediate_dir)

    species_links, species_chunk_links, unresolved_species = attach_species_records_and_chunks(
        species_records=inputs["species_records"],
        species_chunks=inputs["species_chunks"],
        indexes=inputs,
    )
    family_links, family_chunk_links, unresolved_family = attach_family_records_and_chunks(
        family_records=inputs["family_records"],
        family_chunks=inputs["family_chunks"],
        indexes=inputs,
    )

    species_links_path = attachments_dir / "species_taxonomy_links.jsonl"
    species_chunk_links_path = attachments_dir / "species_chunk_taxonomy_links.jsonl"
    family_links_path = attachments_dir / "family_taxonomy_links.jsonl"
    family_chunk_links_path = attachments_dir / "family_chunk_taxonomy_links.jsonl"
    unresolved_species_path = attachments_dir / "taxonomy_unresolved_species.jsonl"
    unresolved_family_path = attachments_dir / "taxonomy_unresolved_family.jsonl"
    summary_path = attachments_dir / "attachment_summary.json"

    write_jsonl(species_links_path, species_links)
    write_jsonl(species_chunk_links_path, species_chunk_links)
    write_jsonl(family_links_path, family_links)
    write_jsonl(family_chunk_links_path, family_chunk_links)
    write_jsonl(unresolved_species_path, unresolved_species)
    write_jsonl(unresolved_family_path, unresolved_family)

    summary = build_attachment_summary(
        species_record_links=species_links,
        species_chunk_links=species_chunk_links,
        family_record_links=family_links,
        family_chunk_links=family_chunk_links,
        unresolved_species=unresolved_species,
        unresolved_family=unresolved_family,
        input_paths={
            "taxonomy_dir": str(taxonomy_dir),
            "intermediate_dir": str(intermediate_dir),
        },
        output_paths={
            "species_taxonomy_links": str(species_links_path),
            "species_chunk_taxonomy_links": str(species_chunk_links_path),
            "family_taxonomy_links": str(family_links_path),
            "family_chunk_taxonomy_links": str(family_chunk_links_path),
            "taxonomy_unresolved_species": str(unresolved_species_path),
            "taxonomy_unresolved_family": str(unresolved_family_path),
            "attachment_summary": str(summary_path),
        },
    )
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
