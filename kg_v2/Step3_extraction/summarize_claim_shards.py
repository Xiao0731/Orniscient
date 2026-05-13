"""Summarize partial Step 3 shard outputs without merging them."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
KG_ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.utils.jsonl_utils import write_json


def _resolve_under_kg(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (KG_ROOT / path).resolve()


def _read_json(path: Path, warnings: list[str]) -> dict:
    if not path.exists():
        warnings.append(f"missing file: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"invalid JSON in {path}: line={exc.lineno} column={exc.colno} error={exc.msg}")
    except OSError as exc:
        warnings.append(f"could not read {path}: {exc}")
    return {}


def _iter_jsonl(path: Path, warnings: list[str]):
    if not path.exists():
        warnings.append(f"missing file: {path}")
        return
    try:
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
                if isinstance(row, dict):
                    yield row
                else:
                    warnings.append(f"non-object JSONL row in {path}: line={line_no}")
    except OSError as exc:
        warnings.append(f"could not read {path}: {exc}")


def _count_jsonl(path: Path, warnings: list[str]) -> int:
    return sum(1 for _ in _iter_jsonl(path, warnings))


def _safe_div(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _discover_shard_dirs(shards_dir: Path, expected_shards: int) -> dict[int, Path]:
    shard_dirs: dict[int, Path] = {}
    for index in range(expected_shards):
        shard_dirs[index] = shards_dir / f"shard_{index:02d}"
    return shard_dirs


def _status_for_shard(shard_dir: Path, expected_chunks: int, processed_chunks: int) -> str:
    if not shard_dir.exists():
        return "missing"
    if expected_chunks > 0 and processed_chunks >= expected_chunks:
        return "completed"
    if processed_chunks > 0:
        return "partial"
    return "empty"


def _summary_reasons(summary: dict) -> Counter:
    reasons: Counter = Counter()
    for item in summary.get("dropped_claim_reasons", []):
        reason = str(item.get("reason", "") or "").strip() or "unknown"
        try:
            count = int(item.get("count", 0))
        except (TypeError, ValueError):
            count = 0
        reasons[reason] += count
    return reasons


def _format_int(value: int | float) -> str:
    return f"{int(value):,}"


def _format_float(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _build_markdown(summary: dict, per_shard_rows: list[dict], top_predicates: list[dict], domain_rows: list[dict]) -> str:
    overview = [
        ["Expected total global chunks", _format_int(summary["expected_total_global"])],
        ["Processed chunks", _format_int(summary["processed_chunk_total"])],
        ["Completion rate", _format_float(summary["completion_rate"] * 100, 2) + "%"],
        ["Completed shards", summary["completed_shard_count"]],
        ["Partial shards", summary["partial_shard_count"]],
        ["Missing shards", summary["missing_shard_count"]],
    ]
    shard_table = [
        [
            row["shard"],
            _format_int(row["expected_chunks"]),
            _format_int(row["processed_chunks"]),
            _format_float(row["progress_rate"] * 100, 2) + "%",
            row["status"],
            _format_int(row["extractor_failure_count"]),
        ]
        for row in per_shard_rows
    ]
    artifact_rows = [
        ["Species claims", _format_int(summary["species_claim_total"])],
        ["Family claims", _format_int(summary["family_claim_total"])],
        ["Total claims", _format_int(summary["total_claim_total"])],
        ["Species facts", _format_int(summary["species_fact_total"])],
        ["Family facts", _format_int(summary["family_fact_total"])],
        ["Total facts", _format_int(summary["total_fact_total"])],
        ["Evidences", _format_int(summary["evidence_total"])],
        ["Fact-evidence links", _format_int(summary["fact_evidence_link_total"])],
        ["Extractor failures", _format_int(summary["extractor_failure_total"])],
    ]
    predicate_rows = [
        [row["predicate"], _format_int(row["count"])]
        for row in top_predicates
    ]
    fact_domain_rows = [
        [row["fact_domain"], _format_int(row["count"]), _format_float(row["share"] * 100, 2) + "%"]
        for row in domain_rows
    ]
    projected = summary["projected_final_scale"]
    projected_rows = [
        ["Projected claim total", _format_int(projected["projected_claim_total"])],
        ["Projected fact total", _format_int(projected["projected_fact_total"])],
        ["Projected evidence total", _format_int(projected["projected_evidence_total"])],
        ["Projected fact-evidence link total", _format_int(projected["projected_fact_evidence_link_total"])],
    ]
    return "\n\n".join(
        [
            "# Step3 Full Extraction Snapshot Summary",
            (
                "This report is a partial snapshot based on currently available shard JSONL artifacts. "
                "Final values should be regenerated after all shards finish and the official merge has completed."
            ),
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview),
            "## Per-shard progress\n\n"
            + _markdown_table(["Shard", "Expected chunks", "Processed chunks", "Progress", "Status", "Failures"], shard_table),
            "## Artifact totals\n\n" + _markdown_table(["Artifact", "Observed count"], artifact_rows),
            "## Top predicates\n\n" + _markdown_table(["Predicate", "Observed fact count"], predicate_rows),
            "## Fact domains\n\n" + _markdown_table(["Fact domain", "Observed fact count", "Share"], fact_domain_rows),
            "## Projected final scale\n\n"
            + _markdown_table(["Estimated metric", "Projected value"], projected_rows)
            + "\n\nThese projected values are estimated from the current processed-chunk density and are not observed totals.",
        ]
    )


def summarize_shards(shards_dir: Path, expected_total_global: int, out_dir: Path, expected_shards: int = 16) -> dict:
    warnings: list[str] = []
    shard_dirs = _discover_shard_dirs(shards_dir, expected_shards)

    per_shard_rows: list[dict[str, Any]] = []
    predicate_counts: Counter = Counter()
    fact_domain_counts: Counter = Counter()
    dropped_reasons: Counter = Counter()

    totals = Counter()
    observed_summary_dropped_count = 0
    summary_present_count = 0

    for shard_index, shard_dir in shard_dirs.items():
        if not shard_dir.exists():
            warnings.append(f"missing shard directory: {shard_dir}")

        summary_path = shard_dir / "extraction_summary.json"
        summary = _read_json(summary_path, warnings) if shard_dir.exists() else {}
        if summary:
            summary_present_count += 1
        expected_chunks = int(summary.get("total_shard") or 0)
        if not expected_chunks and expected_total_global:
            base, extra = divmod(expected_total_global, expected_shards)
            expected_chunks = base + (1 if shard_index < extra else 0)

        processed_species = 0
        processed_family = 0
        processed_chunks = 0
        for row in _iter_jsonl(shard_dir / "processed_chunks.jsonl", warnings):
            processed_chunks += 1
            subject_rank = row.get("subject_rank")
            if subject_rank == "species":
                processed_species += 1
            elif subject_rank == "family":
                processed_family += 1

        species_claims = _count_jsonl(shard_dir / "species_claims.jsonl", warnings)
        family_claims = _count_jsonl(shard_dir / "family_claims.jsonl", warnings)
        species_facts = 0
        family_facts = 0
        for row in _iter_jsonl(shard_dir / "species_facts.jsonl", warnings):
            species_facts += 1
            predicate_counts[str(row.get("predicate", "") or "unknown")] += 1
            fact_domain_counts[str(row.get("fact_domain", "") or "unknown")] += 1
        for row in _iter_jsonl(shard_dir / "family_facts.jsonl", warnings):
            family_facts += 1
            predicate_counts[str(row.get("predicate", "") or "unknown")] += 1
            fact_domain_counts[str(row.get("fact_domain", "") or "unknown")] += 1

        evidences = _count_jsonl(shard_dir / "evidences.jsonl", warnings)
        links = _count_jsonl(shard_dir / "fact_evidence_links.jsonl", warnings)
        failures = _count_jsonl(shard_dir / "extractor_failures.jsonl", warnings)

        observed_summary_dropped_count += int(summary.get("dropped_claim_count") or 0)
        dropped_reasons.update(_summary_reasons(summary))

        totals["processed_chunks"] += processed_chunks
        totals["processed_species_chunks"] += processed_species
        totals["processed_family_chunks"] += processed_family
        totals["species_claims"] += species_claims
        totals["family_claims"] += family_claims
        totals["species_facts"] += species_facts
        totals["family_facts"] += family_facts
        totals["evidences"] += evidences
        totals["links"] += links
        totals["failures"] += failures

        status = _status_for_shard(shard_dir, expected_chunks, processed_chunks)
        per_shard_rows.append(
            {
                "shard": f"shard_{shard_index:02d}",
                "shard_index": shard_index,
                "expected_chunks": expected_chunks,
                "processed_chunks": processed_chunks,
                "progress_rate": _round(_safe_div(processed_chunks, expected_chunks)),
                "status": status,
                "species_processed_chunks": processed_species,
                "family_processed_chunks": processed_family,
                "species_claim_count": species_claims,
                "family_claim_count": family_claims,
                "species_fact_count": species_facts,
                "family_fact_count": family_facts,
                "evidence_count": evidences,
                "fact_evidence_link_count": links,
                "extractor_failure_count": failures,
                "summary_present": bool(summary),
            }
        )

    total_claims = totals["species_claims"] + totals["family_claims"]
    total_facts = totals["species_facts"] + totals["family_facts"]
    processed_chunks = totals["processed_chunks"]

    top_predicates = [
        {"predicate": predicate, "count": count}
        for predicate, count in predicate_counts.most_common(30)
    ]
    domain_total = sum(fact_domain_counts.values())
    domain_rows = [
        {
            "fact_domain": domain,
            "count": count,
            "share": _round(_safe_div(count, domain_total)),
        }
        for domain, count in fact_domain_counts.most_common()
    ]
    dropped_reason_rows = [
        {"reason": reason, "count": count}
        for reason, count in dropped_reasons.most_common()
    ]

    completed_shard_count = sum(1 for row in per_shard_rows if row["status"] == "completed")
    partial_shard_count = sum(1 for row in per_shard_rows if row["status"] in {"partial", "empty"})
    missing_shard_count = sum(1 for row in per_shard_rows if row["status"] == "missing")

    density = {
        "claim_per_processed_chunk": _safe_div(total_claims, processed_chunks),
        "fact_per_processed_chunk": _safe_div(total_facts, processed_chunks),
        "evidence_per_processed_chunk": _safe_div(totals["evidences"], processed_chunks),
        "link_per_processed_chunk": _safe_div(totals["links"], processed_chunks),
    }
    projected = {
        "basis": "estimated from observed artifacts per processed chunk",
        "is_estimated": True,
        "processed_chunk_total_used": processed_chunks,
        "expected_total_global_used": expected_total_global,
        "projected_claim_total": round(density["claim_per_processed_chunk"] * expected_total_global),
        "projected_fact_total": round(density["fact_per_processed_chunk"] * expected_total_global),
        "projected_evidence_total": round(density["evidence_per_processed_chunk"] * expected_total_global),
        "projected_fact_evidence_link_total": round(density["link_per_processed_chunk"] * expected_total_global),
    }

    summary = {
        "report_type": "partial_snapshot",
        "shards_dir": str(shards_dir),
        "expected_total_global": expected_total_global,
        "expected_shard_count": expected_shards,
        "processed_chunk_total": processed_chunks,
        "completion_rate": _round(_safe_div(processed_chunks, expected_total_global)),
        "completed_shard_count": completed_shard_count,
        "partial_shard_count": partial_shard_count,
        "missing_shard_count": missing_shard_count,
        "summary_present_count": summary_present_count,
        "species_claim_total": totals["species_claims"],
        "family_claim_total": totals["family_claims"],
        "total_claim_total": total_claims,
        "species_fact_total": totals["species_facts"],
        "family_fact_total": totals["family_facts"],
        "total_fact_total": total_facts,
        "evidence_total": totals["evidences"],
        "fact_evidence_link_total": totals["links"],
        "extractor_failure_total": totals["failures"],
        "average_claims_per_processed_chunk": _round(_safe_div(total_claims, processed_chunks)),
        "average_facts_per_processed_chunk": _round(_safe_div(total_facts, processed_chunks)),
        "average_evidences_per_fact": _round(_safe_div(totals["evidences"], total_facts)),
        "average_links_per_fact": _round(_safe_div(totals["links"], total_facts)),
        "species_claims_per_processed_species_chunk": _round(
            _safe_div(totals["species_claims"], totals["processed_species_chunks"])
        ),
        "family_claims_per_processed_family_chunk": _round(
            _safe_div(totals["family_claims"], totals["processed_family_chunks"])
        ),
        "processed_species_chunk_total": totals["processed_species_chunks"],
        "processed_family_chunk_total": totals["processed_family_chunks"],
        "top_predicates": top_predicates,
        "fact_domain_distribution": domain_rows,
        "dropped_claim_count_from_summaries": observed_summary_dropped_count,
        "dropped_claim_reasons_from_summaries": dropped_reason_rows,
        "per_shard_failure_counts": [
            {"shard": row["shard"], "extractor_failure_count": row["extractor_failure_count"]}
            for row in per_shard_rows
        ],
        "projected_final_scale": projected,
        "per_shard": per_shard_rows,
        "warnings": warnings,
        "note": "Partial snapshot only. Regenerate final numbers after all shards complete and merge.",
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_json = out_dir / "step3_shards_snapshot_summary.json"
    summary_md = out_dir / "step3_shards_snapshot_summary.md"
    progress_csv = out_dir / "step3_shards_progress.csv"
    predicates_csv = out_dir / "step3_top_predicates.csv"
    domains_csv = out_dir / "step3_fact_domain_distribution.csv"

    write_json(summary_json, summary)
    summary_md.write_text(_build_markdown(summary, per_shard_rows, top_predicates, domain_rows), encoding="utf-8")
    _write_csv(
        progress_csv,
        per_shard_rows,
        [
            "shard",
            "shard_index",
            "expected_chunks",
            "processed_chunks",
            "progress_rate",
            "status",
            "species_processed_chunks",
            "family_processed_chunks",
            "species_claim_count",
            "family_claim_count",
            "species_fact_count",
            "family_fact_count",
            "evidence_count",
            "fact_evidence_link_count",
            "extractor_failure_count",
            "summary_present",
        ],
    )
    _write_csv(predicates_csv, top_predicates, ["predicate", "count"])
    _write_csv(domains_csv, domain_rows, ["fact_domain", "count", "share"])

    summary["output_files"] = {
        "summary_json": str(summary_json),
        "summary_md": str(summary_md),
        "progress_csv": str(progress_csv),
        "top_predicates_csv": str(predicates_csv),
        "fact_domain_distribution_csv": str(domains_csv),
    }
    write_json(summary_json, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize current Step 3 shard artifacts without requiring all shards to finish.")
    parser.add_argument("--shards-dir", required=True)
    parser.add_argument("--expected-total-global", required=True, type=int)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--expected-shards", type=int, default=16)
    args = parser.parse_args()

    shards_dir = _resolve_under_kg(args.shards_dir)
    out_dir = _resolve_under_kg(args.out_dir)
    summary = summarize_shards(
        shards_dir=shards_dir,
        expected_total_global=args.expected_total_global,
        out_dir=out_dir,
        expected_shards=args.expected_shards,
    )
    output_files = summary["output_files"]
    print(f"[Step3][SNAPSHOT] summary_json={output_files['summary_json']}")
    print(f"[Step3][SNAPSHOT] summary_md={output_files['summary_md']}")
    print(
        "[Step3][SNAPSHOT] "
        f"processed={summary['processed_chunk_total']}/{summary['expected_total_global']} "
        f"completion_rate={summary['completion_rate']:.4%} "
        f"claims={summary['total_claim_total']} facts={summary['total_fact_total']} "
        f"evidences={summary['evidence_total']} links={summary['fact_evidence_link_total']} "
        f"failures={summary['extractor_failure_total']} warnings={len(summary['warnings'])}"
    )


if __name__ == "__main__":
    main()
