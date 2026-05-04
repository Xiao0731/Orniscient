"""End-to-end KG V2 build pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.builders.build_fact_graph import build_fact_graph
from kg_v2.builders.export_truth_artifacts import export_truth_artifacts
from kg_v2.builders.build_family_graph import build_family_graph
from kg_v2.builders.build_species_graph import build_species_graph
from kg_v2.builders.build_taxonomy_tree import build_taxonomy_tree
from kg_v2.builders.import_to_neo4j import import_to_neo4j
from kg_v2.extractors.claim_extractors import build_species_claims
from kg_v2.extractors.evidence_chunker import build_evidence_chunks
from kg_v2.extractors.fact_extractors import build_species_facts
from kg_v2.extractors.family_summary_extractors import build_family_summaries
from kg_v2.extractors.rule_based_extractors import extract_species_label_candidates
from kg_v2.parsers.parse_bow_species_xlsx import parse_species_xlsx_files
from kg_v2.parsers.parse_order_family_xlsx import (
    filter_family_chunks,
    filter_family_records,
    parse_family_order_xlsx,
)
from kg_v2.rag.build_vector_index import build_vector_index
from kg_v2.renderers.controlled_doc_renderer import render_controlled_docs
from kg_v2.schema.ontology_v2 import CONTROLLED_DOCS_PATH, INTERMEDIATE_DIR, JSONL_DIR, LOGS_DIR, ensure_output_dirs, write_jsonl
from kg_v2.validators.graph_budget_validator import validate_graph_budget
from kg_v2.validators.noise_validator import validate_noise


def resolve_family_scope(args) -> str:
    if args.family_scope == "sample":
        return "sample"
    if args.family_scope == "full":
        return "full"
    has_species_sample = args.species_limit is not None and args.species_limit > 0
    has_file_sample = args.bow_limit_files is not None
    return "sample" if has_species_sample or has_file_sample else "full"


def main() -> None:
    def _ingest_controlled_docs():
        from kg_v2.rag.lightrag_ingest import ingest_controlled_docs

        return ingest_controlled_docs

    parser = argparse.ArgumentParser(description="Build KG V2 bird knowledge base")
    parser.add_argument("--bow-dir", default="data/BOW")
    parser.add_argument("--family-file", default="data/Order.xlsx")
    parser.add_argument("--bow-limit-files", type=int, default=None)
    parser.add_argument("--species-limit", type=int, default=None)
    parser.add_argument("--skip-neo4j", action="store_true")
    parser.add_argument("--vector-backend", choices=("hashing", "openai"), default="hashing")
    parser.add_argument("--use-lightrag", action="store_true")
    parser.add_argument("--skip-classic-vector", action="store_true")
    parser.add_argument("--lightrag-only", action="store_true")
    parser.add_argument("--graph-budget-report", action="store_true")
    parser.add_argument("--family-scope", choices=("auto", "sample", "full"), default="auto")
    args = parser.parse_args()

    ensure_output_dirs()
    family_scope = resolve_family_scope(args)

    if args.lightrag_only:
        ingest_result = _ingest_controlled_docs()(docs_path=CONTROLLED_DOCS_PATH)
        print(json.dumps({"lightrag_ingest": ingest_result}, ensure_ascii=False, indent=2))
        return

    species_records, species_chunks = parse_species_xlsx_files(
        bow_dir=args.bow_dir,
        limit_files=args.bow_limit_files,
        species_limit=args.species_limit,
    )
    sample_family_names = {row.get("family_name") for row in species_records if row.get("family_name")}
    sample_order_names = {row.get("order_name") for row in species_records if row.get("order_name")}

    family_records, family_chunks = parse_family_order_xlsx(args.family_file)
    family_records_before_filter = len(family_records)
    family_chunks_before_filter = len(family_chunks)
    family_records = filter_family_records(
        family_records,
        sample_family_names=sample_family_names,
        sample_order_names=sample_order_names,
        family_scope=family_scope,
    )
    family_chunks = filter_family_chunks(
        family_chunks,
        sample_family_names=sample_family_names,
        sample_order_names=sample_order_names,
        family_scope=family_scope,
    )
    write_jsonl(INTERMEDIATE_DIR / "family_records.jsonl", family_records)
    write_jsonl(INTERMEDIATE_DIR / "family_chunks.jsonl", family_chunks)

    evidence_rows = build_evidence_chunks()
    taxonomy_nodes, taxonomy_edges = build_taxonomy_tree(
        INTERMEDIATE_DIR / "species_records.jsonl",
        INTERMEDIATE_DIR / "family_records.jsonl",
    )
    candidates = extract_species_label_candidates()
    species_claims = build_species_claims()
    species_facts = build_species_facts()
    family_summaries = build_family_summaries()
    family_nodes, family_edges = build_family_graph(
        INTERMEDIATE_DIR / "family_records.jsonl",
        INTERMEDIATE_DIR / "family_chunks.jsonl",
        INTERMEDIATE_DIR / "species_records.jsonl",
        INTERMEDIATE_DIR / "species_claims.jsonl",
        INTERMEDIATE_DIR / "family_summaries.jsonl",
    )
    species_nodes, species_edges = build_species_graph(
        INTERMEDIATE_DIR / "species_records.jsonl",
        INTERMEDIATE_DIR / "species_claims.jsonl",
        INTERMEDIATE_DIR / "evidence_chunks.jsonl",
    )
    all_nodes, all_edges = build_fact_graph()
    controlled_docs = render_controlled_docs(
        family_records_path=INTERMEDIATE_DIR / "family_records.jsonl",
        family_chunks_path=INTERMEDIATE_DIR / "family_chunks.jsonl",
        family_summaries_path=INTERMEDIATE_DIR / "family_summaries.jsonl",
    )
    truth_artifacts = export_truth_artifacts()

    neo4j_result = {"status": "skipped"}
    if not args.skip_neo4j:
        neo4j_result = import_to_neo4j()

    vector_manifest = {"status": "skipped"}
    if not args.skip_classic_vector:
        vector_manifest = build_vector_index(backend=args.vector_backend)

    lightrag_result = {"status": "skipped"}
    if args.use_lightrag:
        lightrag_result = _ingest_controlled_docs()(docs_path=CONTROLLED_DOCS_PATH)

    budget_report = []
    if args.graph_budget_report:
        budget_report = validate_graph_budget()
    noise_report = validate_noise()

    summary = {
        "species_records": len(species_records),
        "species_chunks": len(species_chunks),
        "family_records": len(family_records),
        "family_chunks": len(family_chunks),
        "family_scope": family_scope,
        "sample_family_count": len(sample_family_names),
        "sample_order_count": len(sample_order_names),
        "family_records_before_filter": family_records_before_filter,
        "family_records_after_filter": len(family_records),
        "family_chunks_before_filter": family_chunks_before_filter,
        "family_chunks_after_filter": len(family_chunks),
        "evidence_chunks": len(evidence_rows),
        "candidate_rows": len(candidates),
        "species_claims": len(species_claims),
        "species_facts": len(species_facts),
        "family_summaries": len(family_summaries),
        "taxonomy_nodes": len(taxonomy_nodes),
        "taxonomy_edges": len(taxonomy_edges),
        "family_nodes": len(family_nodes),
        "family_edges": len(family_edges),
        "sample_family_nodes": len(family_nodes),
        "sample_family_edges": len(family_edges),
        "species_nodes": len(species_nodes),
        "species_edges": len(species_edges),
        "all_nodes": len(all_nodes),
        "all_edges": len(all_edges),
        "sample_graph_total_nodes": len(all_nodes),
        "sample_graph_total_edges": len(all_edges),
        "controlled_docs": len(controlled_docs),
        "truth_artifacts": truth_artifacts,
        "neo4j": neo4j_result,
        "vector_index": vector_manifest,
        "lightrag": lightrag_result,
        "budget_report_count": len(budget_report),
        "noise_issues": len(noise_report),
    }
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
