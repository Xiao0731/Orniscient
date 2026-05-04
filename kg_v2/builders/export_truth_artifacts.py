"""Export required truth/control JSONL artifacts for V2.1."""

from __future__ import annotations

from kg_v2.schema.ontology_v2 import INTERMEDIATE_DIR, JSONL_DIR, TRUTH_ARTIFACTS_DIR, load_jsonl, write_jsonl


def export_truth_artifacts(
    claims_path=INTERMEDIATE_DIR / "species_claims.jsonl",
    controlled_docs_path=INTERMEDIATE_DIR / "controlled_docs.jsonl",
    family_nodes_path=JSONL_DIR / "family_nodes.jsonl",
    species_nodes_path=JSONL_DIR / "species_nodes.jsonl",
    all_edges_path=JSONL_DIR / "all_edges.jsonl",
) -> dict:
    TRUTH_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    claims = load_jsonl(claims_path)
    controlled_docs = load_jsonl(controlled_docs_path)
    family_nodes = load_jsonl(family_nodes_path)
    species_nodes = load_jsonl(species_nodes_path)
    edges = load_jsonl(all_edges_path)

    taxonomy_docs = [row for row in controlled_docs if row.get("doc_type") == "taxonomy_and_identification"]
    fact_nodes = [row for row in species_nodes if row.get("label") == "Fact"]
    evidence_nodes = [row for row in species_nodes if row.get("label") == "EvidenceChunk"]
    family_aspect_docs = [row for row in family_nodes if row.get("label") == "FamilyAspect"]
    family_summary_docs = [row for row in family_nodes if row.get("label") == "FamilySummary"]

    write_jsonl(TRUTH_ARTIFACTS_DIR / "taxonomy_docs.jsonl", taxonomy_docs)
    write_jsonl(TRUTH_ARTIFACTS_DIR / "species_claims.jsonl", claims)
    write_jsonl(TRUTH_ARTIFACTS_DIR / "fact_nodes.jsonl", fact_nodes)
    write_jsonl(TRUTH_ARTIFACTS_DIR / "evidence_nodes.jsonl", evidence_nodes)
    write_jsonl(TRUTH_ARTIFACTS_DIR / "family_aspect_docs.jsonl", family_aspect_docs)
    write_jsonl(TRUTH_ARTIFACTS_DIR / "family_summary_docs.jsonl", family_summary_docs)
    write_jsonl(TRUTH_ARTIFACTS_DIR / "edges.jsonl", edges)

    return {
        "taxonomy_docs": len(taxonomy_docs),
        "species_claims": len(claims),
        "fact_nodes": len(fact_nodes),
        "evidence_nodes": len(evidence_nodes),
        "family_aspect_docs": len(family_aspect_docs),
        "family_summary_docs": len(family_summary_docs),
        "edges": len(edges),
    }
