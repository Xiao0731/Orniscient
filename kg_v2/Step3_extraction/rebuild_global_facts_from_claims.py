"""Rebuild global Step 3 facts, evidence, and links from the official Claim layer."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
KG_ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step3_extraction.fact_builder import _fact_group_key, _fact_id_for_group, build_facts_and_evidence
from kg_v2.utils.jsonl_utils import write_json, write_jsonl


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "KG":
        return (ROOT / path).resolve()
    return (KG_ROOT / path).resolve()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required JSONL: {path}")
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL row in {path}: line={line_no} error={exc.msg}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Non-object JSONL row in {path}: line={line_no}")
            rows.append(row)
    return rows


def _safe_div(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _support_distribution(facts: list[dict]) -> dict[str, int]:
    counts = {"support_count_1": 0, "support_count_2": 0, "support_count_ge_3": 0}
    for fact in facts:
        support = int(fact.get("support_count") or 0)
        if support <= 1:
            counts["support_count_1"] += 1
        elif support == 2:
            counts["support_count_2"] += 1
        else:
            counts["support_count_ge_3"] += 1
    return counts


def _claim_count_by_field(claims: list[dict], field: str) -> Counter:
    return Counter(str(row.get(field, "") or "") for row in claims)


def _fact_count_by_field(facts: list[dict], field: str) -> Counter:
    return Counter(str(row.get(field, "") or "") for row in facts)


def _compression_rows(claims: list[dict], facts: list[dict], field: str, *, limit: int | None = None) -> list[dict]:
    claim_counts = _claim_count_by_field(claims, field)
    fact_counts = _fact_count_by_field(facts, field)
    rows = []
    for value, claim_count in claim_counts.most_common():
        fact_count = fact_counts.get(value, 0)
        rows.append(
            {
                field: value,
                "claim_count": claim_count,
                "fact_count": fact_count,
                "claim_to_fact_compression_ratio": _safe_div(claim_count, fact_count),
            }
        )
    return rows[:limit] if limit is not None else rows


def _fact_object_label(fact: dict) -> str:
    value_min = fact.get("value_min")
    value_max = fact.get("value_max")
    unit = str(fact.get("unit", "") or "")
    name = str(fact.get("object_canonical_name", "") or "").strip()
    object_id = str(fact.get("object_canonical_id", "") or "").strip()
    if name:
        return name
    if object_id:
        return object_id
    if value_min is not None or value_max is not None:
        if value_min is not None and value_max is not None and value_min != value_max:
            return f"{value_min}-{value_max} {unit}".strip()
        value = value_min if value_min is not None else value_max
        return f"{value} {unit}".strip()
    return ""


def _group_claims_by_fact_id(claims: list[dict]) -> dict[str, list[dict]]:
    grouped_by_key: dict[tuple, list[dict]] = defaultdict(list)
    for claim in claims:
        grouped_by_key[_fact_group_key(claim)].append(claim)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for group_key, group_claims in grouped_by_key.items():
        grouped[_fact_id_for_group(group_key)].extend(group_claims)
    return grouped


def _fact_id_collision_audit(claims: list[dict], facts: list[dict]) -> dict:
    grouped_by_key: dict[tuple, int] = defaultdict(int)
    for claim in claims:
        grouped_by_key[_fact_group_key(claim)] += 1
    group_key_by_fact_id: dict[str, set[str]] = defaultdict(set)
    for group_key in grouped_by_key:
        group_key_by_fact_id[_fact_id_for_group(group_key)].add(repr(group_key))
    candidate_collisions = {
        fact_id: sorted(values)
        for fact_id, values in group_key_by_fact_id.items()
        if len(values) > 1
    }
    final_fact_id_counts = Counter(str(fact.get("fact_id", "") or "") for fact in facts)
    duplicate_final_fact_ids = {
        fact_id: count
        for fact_id, count in final_fact_id_counts.items()
        if fact_id and count > 1
    }
    return {
        "fact_id_strategy": "fact_ + first 32 hex chars of SHA1 over stable fact group key",
        "raw_grouped_fact_candidate_count": len(grouped_by_key),
        "candidate_fact_id_collision_count": len(candidate_collisions),
        "candidate_fact_id_collision_row_excess": sum(len(values) - 1 for values in candidate_collisions.values()),
        "candidate_fact_id_collision_examples": [
            {"fact_id": fact_id, "group_keys": values[:5]}
            for fact_id, values in list(candidate_collisions.items())[:20]
        ],
        "final_duplicate_fact_id_count": len(duplicate_final_fact_ids),
        "final_duplicate_fact_id_row_excess": sum(count - 1 for count in duplicate_final_fact_ids.values()),
        "final_duplicate_fact_id_examples": dict(list(duplicate_final_fact_ids.items())[:20]),
        "ok": not candidate_collisions and not duplicate_final_fact_ids,
    }


def _multi_support_samples(facts: list[dict], claims_by_fact_id: dict[str, list[dict]], *, limit: int = 30) -> list[dict]:
    samples: list[dict] = []
    for fact in sorted(facts, key=lambda row: (-int(row.get("support_count") or 0), row.get("fact_id", ""))):
        support = int(fact.get("support_count") or 0)
        if support < 2:
            continue
        claims = claims_by_fact_id.get(fact.get("fact_id", ""), [])
        samples.append(
            {
                "fact_id": fact.get("fact_id", ""),
                "subject_taxon_id": fact.get("subject_taxon_id", ""),
                "subject_rank": fact.get("subject_rank", ""),
                "fact_domain": fact.get("fact_domain", ""),
                "predicate": fact.get("predicate", ""),
                "object": _fact_object_label(fact),
                "support_count": support,
                "supporting_claim_ids": [claim.get("claim_id", "") for claim in claims[:20]],
                "source_chunk_ids": sorted({str(claim.get("source_chunk_id", "") or "") for claim in claims if claim.get("source_chunk_id")})[:20],
            }
        )
        if len(samples) >= limit:
            break
    return samples


def _link_integrity(facts: list[dict], evidences: list[dict], links: list[dict]) -> dict:
    fact_ids = {str(row.get("fact_id", "") or "") for row in facts}
    evidence_ids = {str(row.get("evidence_id", "") or "") for row in evidences}
    missing_fact_links = [
        row for row in links if str(row.get("fact_id", "") or "") not in fact_ids
    ]
    missing_evidence_links = [
        row for row in links if str(row.get("evidence_id", "") or "") not in evidence_ids
    ]
    evidence_missing_chunk_id = [
        row for row in evidences if not str(row.get("source_chunk_id", "") or "").strip()
    ]
    return {
        "evidence_total": len(evidences),
        "evidence_with_source_chunk_id": len(evidences) - len(evidence_missing_chunk_id),
        "evidence_missing_source_chunk_id_count": len(evidence_missing_chunk_id),
        "evidence_missing_source_chunk_id_examples": evidence_missing_chunk_id[:20],
        "link_total": len(links),
        "links_with_missing_fact_count": len(missing_fact_links),
        "links_with_missing_evidence_count": len(missing_evidence_links),
        "links_with_missing_fact_examples": missing_fact_links[:20],
        "links_with_missing_evidence_examples": missing_evidence_links[:20],
        "ok": not evidence_missing_chunk_id and not missing_fact_links and not missing_evidence_links,
    }


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _fmt_float(value: float) -> str:
    return f"{value:.4f}"


def _build_markdown(summary: dict) -> str:
    overview_rows = [
        ["Species claims", _fmt_int(summary["species_claim_total"])],
        ["Family claims", _fmt_int(summary["family_claim_total"])],
        ["Total claims", _fmt_int(summary["total_claim_total"])],
        ["Species facts", _fmt_int(summary["species_fact_total"])],
        ["Family facts", _fmt_int(summary["family_fact_total"])],
        ["Total facts", _fmt_int(summary["total_fact_total"])],
        ["Evidences", _fmt_int(summary["evidence_total"])],
        ["Fact-evidence links", _fmt_int(summary["fact_evidence_link_total"])],
        ["Claim-to-fact compression ratio", _fmt_float(summary["claim_to_fact_compression_ratio"])],
        ["Raw grouped fact candidates", _fmt_int(summary["raw_grouped_fact_candidate_total"])],
        ["Fact quota removed", summary["fact_quota_removed"]],
        ["Evidence max-2 cap removed", summary["evidence_max2_cap_removed"]],
        ["Fact ID collision OK", summary["fact_id_collision_audit"]["ok"]],
        ["Integrity OK", summary["integrity"]["ok"]],
    ]
    support_rows = [[key, _fmt_int(value)] for key, value in summary["support_count_distribution"].items()]
    domain_rows = [
        [row["fact_domain"], _fmt_int(row["claim_count"]), _fmt_int(row["fact_count"]), _fmt_float(row["claim_to_fact_compression_ratio"])]
        for row in summary["by_fact_domain"]
    ]
    predicate_rows = [
        [row["predicate"], _fmt_int(row["claim_count"]), _fmt_int(row["fact_count"]), _fmt_float(row["claim_to_fact_compression_ratio"])]
        for row in summary["top_predicates"]
    ]
    sample_rows = [
        [
            row["fact_id"],
            row["subject_taxon_id"],
            row["predicate"],
            row["object"],
            row["support_count"],
            ", ".join(row["supporting_claim_ids"][:5]),
            ", ".join(row["source_chunk_ids"][:5]),
        ]
        for row in summary["multi_support_fact_samples"][:15]
    ]
    integrity_rows = [
        ["Evidence missing source_chunk_id", _fmt_int(summary["integrity"]["evidence_missing_source_chunk_id_count"])],
        ["Links with missing fact", _fmt_int(summary["integrity"]["links_with_missing_fact_count"])],
        ["Links with missing evidence", _fmt_int(summary["integrity"]["links_with_missing_evidence_count"])],
    ]
    return "\n\n".join(
        [
            "# Step3 Global Fact Rebuild Audit",
            (
                "Facts, evidences, and fact-evidence links were rebuilt only from `claims_final_global_v2`; "
                "no shard-local fact artifacts or old facts_final_global outputs were read. "
                "Subject/domain fact quota and evidence max-2 cap are removed."
            ),
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## Support Count Distribution\n\n" + _markdown_table(["Support bucket", "Fact count"], support_rows),
            "## By Fact Domain\n\n" + _markdown_table(["Fact domain", "Claims", "Facts", "Claims/Facts"], domain_rows),
            "## Top Predicates\n\n" + _markdown_table(["Predicate", "Claims", "Facts", "Claims/Facts"], predicate_rows),
            "## Multi-support Fact Samples\n\n"
            + _markdown_table(["Fact ID", "Taxon", "Predicate", "Object", "Support", "Claim IDs", "Chunk IDs"], sample_rows),
            "## Integrity Checks\n\n" + _markdown_table(["Check", "Count"], integrity_rows),
            "## Fact ID Collision Audit\n\n"
            + _markdown_table(
                ["Metric", "Value"],
                [
                    ["Strategy", summary["fact_id_collision_audit"]["fact_id_strategy"]],
                    ["Candidate collisions", _fmt_int(summary["fact_id_collision_audit"]["candidate_fact_id_collision_count"])],
                    ["Final duplicate fact IDs", _fmt_int(summary["fact_id_collision_audit"]["final_duplicate_fact_id_count"])],
                    ["OK", summary["fact_id_collision_audit"]["ok"]],
                ],
            ),
        ]
    )


def rebuild_global_facts(*, claims_dir: Path, out_dir: Path, sample_limit: int) -> dict:
    species_claims = _read_jsonl(claims_dir / "species_claims.jsonl")
    family_claims = _read_jsonl(claims_dir / "family_claims.jsonl")
    all_claims = species_claims + family_claims

    species_facts, species_evidences, species_links = build_facts_and_evidence(species_claims, subject_rank="species")
    family_facts, family_evidences, family_links = build_facts_and_evidence(family_claims, subject_rank="family")
    facts = species_facts + family_facts
    evidences_by_id = {row["evidence_id"]: row for row in species_evidences + family_evidences}
    evidences = list(evidences_by_id.values())
    links = species_links + family_links

    claims_by_fact_id = _group_claims_by_fact_id(all_claims)
    integrity = _link_integrity(facts, evidences, links)
    collision_audit = _fact_id_collision_audit(all_claims, facts)
    summary = {
        "claims_dir": str(claims_dir),
        "out_dir": str(out_dir),
        "species_claim_total": len(species_claims),
        "family_claim_total": len(family_claims),
        "total_claim_total": len(all_claims),
        "species_fact_total": len(species_facts),
        "family_fact_total": len(family_facts),
        "total_fact_total": len(facts),
        "raw_grouped_fact_candidate_total": collision_audit["raw_grouped_fact_candidate_count"],
        "final_facts_equal_grouped_candidates": len(facts) == collision_audit["raw_grouped_fact_candidate_count"],
        "evidence_total": len(evidences),
        "fact_evidence_link_total": len(links),
        "claim_to_fact_compression_ratio": _safe_div(len(all_claims), len(facts)),
        "support_count_distribution": _support_distribution(facts),
        "by_fact_domain": _compression_rows(all_claims, facts, "fact_domain"),
        "by_predicate": _compression_rows(all_claims, facts, "predicate"),
        "top_predicates": _compression_rows(all_claims, facts, "predicate", limit=50),
        "multi_support_fact_samples": _multi_support_samples(facts, claims_by_fact_id, limit=sample_limit),
        "integrity": integrity,
        "fact_id_collision_audit": collision_audit,
        "fact_quota_removed": True,
        "evidence_max2_cap_removed": True,
        "input_policy": "claims_final_global_v2 species_claims.jsonl + family_claims.jsonl only",
        "note": (
            "Rebuilt from claims_final_global_v2 only. Shard-local facts/evidences/links and old facts_final_global "
            "are intentionally ignored."
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "species_facts": out_dir / "species_facts.jsonl",
        "family_facts": out_dir / "family_facts.jsonl",
        "evidences": out_dir / "evidences.jsonl",
        "fact_evidence_links": out_dir / "fact_evidence_links.jsonl",
        "summary": out_dir / "global_fact_rebuild_summary.json",
        "audit": out_dir / "fact_rebuild_audit.md",
        "fact_id_collision_audit_json": out_dir / "fact_id_collision_audit.json",
        "fact_id_collision_audit_md": out_dir / "fact_id_collision_audit.md",
    }
    write_jsonl(paths["species_facts"], species_facts)
    write_jsonl(paths["family_facts"], family_facts)
    write_jsonl(paths["evidences"], evidences)
    write_jsonl(paths["fact_evidence_links"], links)
    summary["output_files"] = {key: str(path) for key, path in paths.items()}
    write_json(paths["summary"], summary)
    write_json(paths["fact_id_collision_audit_json"], collision_audit)
    paths["audit"].write_text(_build_markdown(summary), encoding="utf-8")
    paths["fact_id_collision_audit_md"].write_text(
        "\n\n".join(
            [
                "# Fact ID Collision Audit",
                _markdown_table(
                    ["Metric", "Value"],
                    [
                        ["Strategy", collision_audit["fact_id_strategy"]],
                        ["Raw grouped fact candidates", _fmt_int(collision_audit["raw_grouped_fact_candidate_count"])],
                        ["Candidate fact_id collision count", _fmt_int(collision_audit["candidate_fact_id_collision_count"])],
                        ["Candidate collision row excess", _fmt_int(collision_audit["candidate_fact_id_collision_row_excess"])],
                        ["Final duplicate fact_id count", _fmt_int(collision_audit["final_duplicate_fact_id_count"])],
                        ["Final duplicate fact_id row excess", _fmt_int(collision_audit["final_duplicate_fact_id_row_excess"])],
                        ["OK", collision_audit["ok"]],
                    ],
                ),
            ]
        ),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Globally rebuild Step3 facts/evidence/links from claims_final_global_v2.")
    parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global_v2")
    parser.add_argument("--out-dir", default="KG/intermediate/facts_final_global_v2")
    parser.add_argument("--sample-limit", type=int, default=30)
    args = parser.parse_args()

    summary = rebuild_global_facts(
        claims_dir=_resolve_path(args.claims_dir),
        out_dir=_resolve_path(args.out_dir),
        sample_limit=args.sample_limit,
    )
    print(f"[Step3][GLOBAL_FACT_REBUILD] summary={summary['output_files']['summary']}")
    print(f"[Step3][GLOBAL_FACT_REBUILD] audit={summary['output_files']['audit']}")
    print(
        "[Step3][GLOBAL_FACT_REBUILD] "
        f"claims={summary['total_claim_total']} facts={summary['total_fact_total']} "
        f"evidences={summary['evidence_total']} links={summary['fact_evidence_link_total']} "
        f"compression={summary['claim_to_fact_compression_ratio']:.4f} integrity_ok={summary['integrity']['ok']}"
    )
    if not summary["integrity"]["ok"] or not summary["fact_id_collision_audit"]["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
