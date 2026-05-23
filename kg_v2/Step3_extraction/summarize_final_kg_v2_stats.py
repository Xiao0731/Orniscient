"""Summarize final v2 Claim/Fact/Evidence artifacts for README tables."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
KG_ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step3_extraction.predicate_registry import FACT_DOMAINS, PREDICATES_BY_DOMAIN
from kg_v2.utils.jsonl_utils import write_json


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "KG":
        return (ROOT / path).resolve()
    return (KG_ROOT / path).resolve()


def _read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"missing JSON file: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"invalid JSON in {path}: line={exc.lineno} column={exc.colno} error={exc.msg}")
        return {}
    if not isinstance(payload, dict):
        warnings.append(f"non-object JSON payload: {path}")
        return {}
    return payload


def _iter_jsonl(path: Path, warnings: list[str]) -> Iterable[dict[str, Any]]:
    if not path.exists():
        warnings.append(f"missing JSONL file: {path}")
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                warnings.append(f"invalid JSONL row in {path}: line={line_no} error={exc.msg}")
                continue
            if not isinstance(row, dict):
                warnings.append(f"non-object JSONL row in {path}: line={line_no}")
                continue
            yield row


def _count_jsonl(path: Path, warnings: list[str]) -> int:
    return sum(1 for _ in _iter_jsonl(path, warnings))


def _safe_div(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _fmt_int(value: int | float | None) -> str:
    return f"{int(value or 0):,}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    right_aligned_headers = {
        "Count",
        "Fact Count",
        "Share",
        "Predicate Count",
        "Count / Value",
    }
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---:" if header in right_aligned_headers else "---" for header in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _top_rows(counter: Counter, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows = [{"predicate": key, "fact_count": int(value)} for key, value in counter.most_common()]
    return rows[:limit] if limit is not None else rows


def _representative_predicates(predicates: list[str]) -> list[str]:
    return predicates[:5]


def _status(value: Any) -> str:
    if isinstance(value, bool):
        return "ok" if value else "failed"
    return str(value)


def _build_markdown(summary: dict[str, Any]) -> str:
    overall_rows = [[row["metric"], _fmt_int(row["count"])] for row in summary["overall_artifact_scale"]]
    node_rows = [[row["node_label"], _fmt_int(row["count"])] for row in summary["core_graph_size_estimate"]["nodes"]]
    edge_rows = [
        [row["concept_edge_type"], row["actual_relation_name"], _fmt_int(row["count"])]
        for row in summary["core_graph_size_estimate"]["edges"]
    ]
    domain_rows = [
        [row["fact_domain"], _fmt_int(row["fact_count"]), _fmt_pct(row["share"])]
        for row in summary["fact_domain_distribution"]
    ]
    top_predicate_rows = [
        [row["predicate"], _fmt_int(row["fact_count"])]
        for row in summary["top_predicates"]["top_30"]
    ]
    schema_rows = [
        [
            row["fact_domain"],
            _fmt_int(row["predicate_count"]),
            ", ".join(row["representative_predicates"]),
        ]
        for row in summary["controlled_schema"]["schema_table"]
    ]
    supplement_rows = [
        [row["item"], _fmt_int(row["count"])]
        for row in summary["supplementary_claim_extraction_summary"]["table"]
    ]
    policy_rows = [
        [row["policy_or_check"], row["status"]]
        for row in summary["fact_rebuild_policy_and_integrity_checks"]
    ]
    warning_section = ""
    if summary["warnings"] or summary["baseline_differences"]:
        warning_rows = [[item] for item in summary["warnings"] + summary["baseline_differences"]]
        warning_section = "\n\n## Warnings And Baseline Differences\n\n" + _markdown_table(["Message"], warning_rows)

    return "\n\n".join(
        [
            "# Final KG v2 Statistics",
            (
                "Read-only statistics generated from `claims_final_global_v2` and `facts_final_global_v2`. "
                "This report estimates the current core Taxon-Fact-Evidence-Chunk graph only; it excludes future "
                "Object/Concept nodes, full taxonomy backbone, aliases, crosswalks, vector indexes, and Neo4j materialization side effects."
            ),
            "## Overall Artifact Scale\n\n" + _markdown_table(["Metric", "Count"], overall_rows),
            "## Core Graph Size Estimate\n\n"
            + _markdown_table(["Node Label", "Count"], node_rows)
            + "\n\n"
            + _markdown_table(["Concept Edge Type", "Actual Relation Name", "Count"], edge_rows),
            "## Fact Domain Distribution\n\n" + _markdown_table(["Fact Domain", "Fact Count", "Share"], domain_rows),
            "## Top Fact Predicates\n\n" + _markdown_table(["Predicate", "Fact Count"], top_predicate_rows),
            "## Controlled Fact Domain and Predicate Schema\n\n"
            + _markdown_table(["Fact Domain", "Predicate Count", "Representative Predicates"], schema_rows),
            "## Supplementary Claim Extraction Summary\n\n"
            + _markdown_table(["Item", "Count / Value"], supplement_rows)
            + "\n\n"
            + (
                "The original Claim extraction policy had a 2/4 per-chunk claim cap. "
                "A total of 93,542 chunks were identified as high-risk at/over-cap chunks. "
                "The final supplementary strategy used a single-pass additional-6 extraction; "
                "331,827 supplementary claims were accepted into Claim v2 after strict deduplication. "
                "Chunks that hit the soft cap are retained as a high-recall expansion list for future continuation passes."
            ),
            "## Fact Rebuild Policy and Integrity Checks\n\n" + _markdown_table(["Policy / Check", "Status"], policy_rows),
        ]
    ) + warning_section + "\n"


def summarize_final_kg_v2_stats(*, claims_dir: Path, facts_dir: Path, reports_dir: Path) -> dict[str, Any]:
    warnings: list[str] = []
    baseline_differences: list[str] = []

    claim_merge_summary = _read_json(claims_dir / "claim_merge_summary.json", warnings)
    fact_rebuild_summary = _read_json(facts_dir / "global_fact_rebuild_summary.json", warnings)
    collision_audit = _read_json(facts_dir / "fact_id_collision_audit.json", warnings)

    processed_chunk_ids: set[str] = set()
    for row in _iter_jsonl(claims_dir / "processed_unique_chunks.jsonl", warnings):
        chunk_id = str(row.get("chunk_id") or row.get("source_chunk_id") or "").strip()
        if chunk_id:
            processed_chunk_ids.add(chunk_id)
    processed_chunks = len(processed_chunk_ids)

    species_claims = _count_jsonl(claims_dir / "species_claims.jsonl", warnings)
    family_claims = _count_jsonl(claims_dir / "family_claims.jsonl", warnings)
    total_claims_from_all = _count_jsonl(claims_dir / "all_claims.jsonl", warnings)
    total_claims = species_claims + family_claims

    taxon_ids: set[str] = set()
    for path in (claims_dir / "species_claims.jsonl", claims_dir / "family_claims.jsonl"):
        for row in _iter_jsonl(path, warnings):
            taxon_id = str(row.get("subject_taxon_id") or "").strip()
            if taxon_id:
                taxon_ids.add(taxon_id)

    domain_counts: Counter = Counter()
    predicate_counts: Counter = Counter()
    species_facts = 0
    family_facts = 0
    for label, path in (("species", facts_dir / "species_facts.jsonl"), ("family", facts_dir / "family_facts.jsonl")):
        for row in _iter_jsonl(path, warnings):
            if label == "species":
                species_facts += 1
            else:
                family_facts += 1
            domain_counts[str(row.get("fact_domain") or "unknown")] += 1
            predicate_counts[str(row.get("predicate") or "unknown")] += 1
            taxon_id = str(row.get("subject_taxon_id") or "").strip()
            if taxon_id:
                taxon_ids.add(taxon_id)
    total_facts = species_facts + family_facts

    evidences = _count_jsonl(facts_dir / "evidences.jsonl", warnings)
    fact_evidence_links = _count_jsonl(facts_dir / "fact_evidence_links.jsonl", warnings)
    possible_near_duplicate_rows = _count_jsonl(claims_dir / "possible_near_duplicate_supplement_claims.jsonl", warnings)

    supplement_accepted = int(claim_merge_summary.get("supplement_accepted_claims_count") or 0)
    supplement_covered_chunks = int(claim_merge_summary.get("supplement_covered_unique_chunks") or 0)
    hit_soft_cap_chunks = int(claim_merge_summary.get("supplement_hit_soft_cap_chunk_count") or 0)
    extractor_failures = int(claim_merge_summary.get("supplement_run_failures_count") or 0)
    fact_id_collisions = int(collision_audit.get("final_duplicate_fact_id_count") or 0)

    overall = [
        {"metric": "Processed BOW chunks", "count": processed_chunks},
        {"metric": "Species claims", "count": species_claims},
        {"metric": "Family claims", "count": family_claims},
        {"metric": "Total claims", "count": total_claims},
        {"metric": "Species facts", "count": species_facts},
        {"metric": "Family facts", "count": family_facts},
        {"metric": "Total facts", "count": total_facts},
        {"metric": "Evidences", "count": evidences},
        {"metric": "Fact-Evidence links", "count": fact_evidence_links},
        {"metric": "Supplement accepted claims", "count": supplement_accepted},
        {"metric": "Supplement covered chunks", "count": supplement_covered_chunks},
        {"metric": "Hit soft-cap chunks", "count": hit_soft_cap_chunks},
        {"metric": "Fact ID collisions", "count": fact_id_collisions},
        {"metric": "Extractor failures", "count": extractor_failures},
    ]

    taxon_count = len(taxon_ids)
    core_nodes = [
        {"node_label": "Taxon", "count": taxon_count},
        {"node_label": "Fact", "count": total_facts},
        {"node_label": "Evidence", "count": evidences},
        {"node_label": "Chunk", "count": processed_chunks},
        {"node_label": "Total core nodes", "count": taxon_count + total_facts + evidences + processed_chunks},
    ]
    core_edges = [
        {"concept_edge_type": "Taxon -> Fact", "actual_relation_name": "HAS_FACT", "count": total_facts},
        {"concept_edge_type": "Fact -> Evidence", "actual_relation_name": "SUPPORTED_BY", "count": fact_evidence_links},
        {"concept_edge_type": "Evidence -> Chunk", "actual_relation_name": "FROM_CHUNK", "count": evidences},
        {"concept_edge_type": "Total core edges", "actual_relation_name": "", "count": total_facts + fact_evidence_links + evidences},
    ]

    domain_distribution = [
        {
            "fact_domain": domain,
            "fact_count": int(count),
            "share": _safe_div(count, total_facts),
            "share_percent": round(_safe_div(count, total_facts) * 100, 2),
        }
        for domain, count in domain_counts.most_common()
    ]
    predicate_distribution = _top_rows(predicate_counts)

    controlled_schema = {
        "fact_domains": list(FACT_DOMAINS),
        "predicates_by_domain": {domain: list(PREDICATES_BY_DOMAIN.get(domain, [])) for domain in FACT_DOMAINS},
        "predicate_count_by_domain": {domain: len(PREDICATES_BY_DOMAIN.get(domain, [])) for domain in FACT_DOMAINS},
        "all_predicate_count": len({predicate for predicates in PREDICATES_BY_DOMAIN.values() for predicate in predicates}),
        "schema_table": [
            {
                "fact_domain": domain,
                "predicate_count": len(PREDICATES_BY_DOMAIN.get(domain, [])),
                "representative_predicates": _representative_predicates(PREDICATES_BY_DOMAIN.get(domain, [])),
            }
            for domain in FACT_DOMAINS
        ],
    }

    supplement_table = [
        {"item": "Old official claims", "count": int(claim_merge_summary.get("old_official_claims_count") or 0)},
        {"item": "Supplement raw claims", "count": int(claim_merge_summary.get("supplement_raw_claims_count") or 0)},
        {"item": "Supplement accepted claims", "count": supplement_accepted},
        {"item": "Strict duplicates dropped", "count": int(claim_merge_summary.get("supplement_strict_duplicates_dropped") or 0)},
        {"item": "Supplement covered chunks", "count": supplement_covered_chunks},
        {"item": "Hit soft-cap chunks", "count": hit_soft_cap_chunks},
        {"item": "Final merged claims", "count": int(claim_merge_summary.get("merged_official_claims_count") or 0)},
        {"item": "Possible near-duplicate audit rows", "count": possible_near_duplicate_rows},
    ]

    policy_rows = [
        {"policy_or_check": "Subject/domain quota", "status": "removed"},
        {"policy_or_check": "Evidence max-2 cap", "status": "removed"},
        {
            "policy_or_check": "Fact ID strategy",
            "status": "typed stable group key + 32-hex SHA1",
        },
        {"policy_or_check": "Fact ID collision", "status": str(int(collision_audit.get("final_duplicate_fact_id_count") or 0))},
        {"policy_or_check": "Integrity check", "status": _status(fact_rebuild_summary.get("integrity", {}).get("ok"))},
        {
            "policy_or_check": "final facts equal grouped candidates",
            "status": _status(fact_rebuild_summary.get("final_facts_equal_grouped_candidates")),
        },
    ]

    checks = {
        "all_claims_equals_species_plus_family": total_claims_from_all == total_claims,
        "domain_total_equals_total_facts": sum(domain_counts.values()) == total_facts,
        "predicate_total_equals_total_facts": sum(predicate_counts.values()) == total_facts,
        "fact_rebuild_integrity_ok": bool(fact_rebuild_summary.get("integrity", {}).get("ok")),
        "fact_id_collision_ok": bool(collision_audit.get("ok")),
    }

    expected = {
        "Processed BOW chunks": 309369,
        "Species claims": 912598,
        "Family claims": 8563,
        "Total claims": 921161,
        "Species facts": 883500,
        "Family facts": 8362,
        "Total facts": 891862,
        "Evidences": 815896,
        "Fact-Evidence links": 915793,
        "Supplement accepted claims": 331827,
        "Supplement covered chunks": 93542,
        "Hit soft-cap chunks": 33211,
        "Fact ID collisions": 0,
        "Extractor failures": 0,
    }
    actual_by_metric = {row["metric"]: row["count"] for row in overall}
    for metric, expected_value in expected.items():
        actual_value = actual_by_metric.get(metric)
        if actual_value != expected_value:
            baseline_differences.append(f"{metric}: expected {expected_value}, observed {actual_value}")
    if not checks["all_claims_equals_species_plus_family"]:
        baseline_differences.append(f"all_claims rows {total_claims_from_all} != species+family claims {total_claims}")
    if not checks["domain_total_equals_total_facts"]:
        baseline_differences.append(f"domain total {sum(domain_counts.values())} != total facts {total_facts}")
    if not checks["predicate_total_equals_total_facts"]:
        baseline_differences.append(f"predicate total {sum(predicate_counts.values())} != total facts {total_facts}")

    summary = {
        "source_artifacts": {
            "claims_dir": str(claims_dir),
            "facts_dir": str(facts_dir),
            "predicate_registry": "kg_v2/Step3_extraction/predicate_registry.py",
        },
        "overall_artifact_scale": overall,
        "core_graph_size_estimate": {
            "notes": [
                "Core graph estimate covers Taxon-Fact-Evidence-Chunk only.",
                "It excludes Object/Concept nodes, full taxonomy backbone, aliases, crosswalks, vector indexes, and Neo4j materialization extras.",
            ],
            "nodes": core_nodes,
            "edges": core_edges,
        },
        "fact_domain_distribution": domain_distribution,
        "top_predicates": {
            "top_30": predicate_distribution[:30],
            "top_50": predicate_distribution[:50],
            "full_distribution": predicate_distribution,
        },
        "controlled_schema": controlled_schema,
        "supplementary_claim_extraction_summary": {
            "table": supplement_table,
            "notes": [
                "Original Claim extraction had a 2/4 per-chunk cap.",
                "93,542 chunks were identified as high-risk at/over-cap chunks.",
                "The final supplementary strategy used a single-pass additional-6 extraction.",
                "331,827 supplement claims were accepted into Claim v2.",
                "Hit soft-cap chunks are retained for future high-recall continuation passes.",
            ],
        },
        "fact_rebuild_policy_and_integrity_checks": policy_rows,
        "cross_checks": checks,
        "warnings": warnings,
        "baseline_differences": baseline_differences,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize final KG v2 Claim/Fact/Evidence artifacts.")
    parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global_v2")
    parser.add_argument("--facts-dir", default="KG/intermediate/facts_final_global_v2")
    parser.add_argument("--reports-dir", default="KG/reports")
    args = parser.parse_args()

    claims_dir = _resolve_path(args.claims_dir)
    facts_dir = _resolve_path(args.facts_dir)
    reports_dir = _resolve_path(args.reports_dir)
    summary = summarize_final_kg_v2_stats(claims_dir=claims_dir, facts_dir=facts_dir, reports_dir=reports_dir)

    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "final_kg_v2_stats.json"
    md_path = reports_dir / "final_kg_v2_stats.md"
    write_json(json_path, summary)
    md_path.write_text(_build_markdown(summary), encoding="utf-8")

    print(f"[Step3][FINAL_KG_V2_STATS] json={json_path}")
    print(f"[Step3][FINAL_KG_V2_STATS] md={md_path}")
    print(
        "[Step3][FINAL_KG_V2_STATS] "
        f"claims={summary['overall_artifact_scale'][3]['count']} "
        f"facts={summary['overall_artifact_scale'][6]['count']} "
        f"evidences={summary['overall_artifact_scale'][7]['count']} "
        f"links={summary['overall_artifact_scale'][8]['count']} "
        f"baseline_differences={len(summary['baseline_differences'])}"
    )
    return 1 if summary["warnings"] or summary["baseline_differences"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
