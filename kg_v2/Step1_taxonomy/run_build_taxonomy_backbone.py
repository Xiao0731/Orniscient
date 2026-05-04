"""Run Step 1 taxonomy backbone pipeline."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KG_ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step1_taxonomy.builders.build_taxonomy_backbone import build_taxonomy_backbone
from kg_v2.Step1_taxonomy.builders.build_taxonomy_conflicts import build_taxonomy_conflicts
from kg_v2.Step1_taxonomy.builders.build_taxonomy_crosswalks import build_taxonomy_crosswalks
from kg_v2.Step1_taxonomy.common import ensure_dir, write_json
from kg_v2.Step1_taxonomy.parsers.parse_avilist_xlsx import parse_avilist_xlsx
from kg_v2.Step1_taxonomy.parsers.parse_clements_xlsx import parse_clements_xlsx
from kg_v2.Step1_taxonomy.validators.taxonomy_validator import validate_taxonomy


def _resolve_input(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    direct = (KG_ROOT / path).resolve()
    if direct.exists():
        return direct
    repo_relative = (ROOT / path).resolve()
    return repo_relative


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Step 1 taxonomy backbone")
    parser.add_argument("--avilist", default="data/AviList-v2025-11Jun-extended.xlsx")
    parser.add_argument("--clements", default="data/Clements_v2025-October-2025.xlsx")
    parser.add_argument("--avilist-release", default="v2025-11Jun")
    parser.add_argument("--clements-release", default="v2025-October")
    args = parser.parse_args()

    avilist_path = _resolve_input(args.avilist)
    clements_path = _resolve_input(args.clements)
    intermediate_dir = ensure_dir(KG_ROOT / "outputs" / "intermediate" / "taxonomy")
    jsonl_dir = ensure_dir(KG_ROOT / "outputs" / "jsonl")

    avilist_rows_path = intermediate_dir / "avilist_rows.jsonl"
    clements_rows_path = intermediate_dir / "clements_rows.jsonl"
    canonical_nodes_path = intermediate_dir / "canonical_taxon_nodes.jsonl"
    canonical_edges_path = intermediate_dir / "canonical_taxon_edges.jsonl"
    crosswalks_path = intermediate_dir / "taxonomy_crosswalks.jsonl"
    aliases_path = intermediate_dir / "taxonomy_aliases.jsonl"
    conflicts_path = intermediate_dir / "taxonomy_conflicts.jsonl"
    validator_path = intermediate_dir / "taxonomy_validation_report.json"
    summary_path = intermediate_dir / "taxonomy_build_summary.json"

    avilist_rows, avilist_sheet = parse_avilist_xlsx(
        input_path=avilist_path,
        output_path=avilist_rows_path,
        release=args.avilist_release,
    )
    clements_rows, clements_sheet = parse_clements_xlsx(
        input_path=clements_path,
        output_path=clements_rows_path,
        release=args.clements_release,
    )
    canonical_nodes, canonical_edges = build_taxonomy_backbone(
        avilist_rows=avilist_rows,
        release=args.avilist_release,
        nodes_output_path=canonical_nodes_path,
        edges_output_path=canonical_edges_path,
    )
    crosswalks, aliases = build_taxonomy_crosswalks(
        canonical_nodes=canonical_nodes,
        clements_rows=clements_rows,
        external_release=args.clements_release,
        crosswalks_output_path=crosswalks_path,
        aliases_output_path=aliases_path,
    )
    conflicts = build_taxonomy_conflicts(
        canonical_nodes=canonical_nodes,
        clements_rows=clements_rows,
        crosswalks=crosswalks,
        output_path=conflicts_path,
    )
    validation_report = validate_taxonomy(
        canonical_nodes=canonical_nodes,
        canonical_edges=canonical_edges,
        crosswalks=crosswalks,
        output_path=validator_path,
    )

    shutil.copyfile(canonical_nodes_path, jsonl_dir / "taxonomy_nodes.jsonl")
    shutil.copyfile(canonical_edges_path, jsonl_dir / "taxonomy_edges.jsonl")

    summary = {
        "input_files": {
            "avilist": str(avilist_path),
            "clements": str(clements_path),
        },
        "sheets_used": {
            "avilist": avilist_sheet,
            "clements": clements_sheet,
        },
        "releases": {
            "avilist": args.avilist_release,
            "clements": args.clements_release,
        },
        "outputs": {
            "intermediate_dir": str(intermediate_dir),
            "jsonl_dir": str(jsonl_dir),
            "avilist_rows": str(avilist_rows_path),
            "clements_rows": str(clements_rows_path),
            "canonical_taxon_nodes": str(canonical_nodes_path),
            "canonical_taxon_edges": str(canonical_edges_path),
            "taxonomy_crosswalks": str(crosswalks_path),
            "taxonomy_aliases": str(aliases_path),
            "taxonomy_conflicts": str(conflicts_path),
            "taxonomy_validation_report": str(validator_path),
            "taxonomy_build_summary": str(summary_path),
            "copied_taxonomy_nodes": str(jsonl_dir / "taxonomy_nodes.jsonl"),
            "copied_taxonomy_edges": str(jsonl_dir / "taxonomy_edges.jsonl"),
        },
        "counts": {
            "avilist_rows": len(avilist_rows),
            "clements_rows": len(clements_rows),
            "canonical_taxon_nodes": len(canonical_nodes),
            "canonical_taxon_edges": len(canonical_edges),
            "taxonomy_crosswalks": len(crosswalks),
            "taxonomy_aliases": len(aliases),
            "taxonomy_conflicts": len(conflicts),
        },
        "validator_summary": validation_report.get("summary", {}),
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
