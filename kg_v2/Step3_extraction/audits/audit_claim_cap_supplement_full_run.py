"""Audit the full claim-cap supplementary extraction run.

Read-only: scans KG/intermediate/claims_cap_supplement_full shard outputs and
writes report files under KG/reports. It does not modify supplementary outputs,
claims_final_global, facts, or Neo4j artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.utils.jsonl_utils import write_json


EXPECTED_SHARDS = 16
EXPECTED_GLOBAL_CHUNKS = 93542


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_configure_stdio()


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path)


def _safe_div(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                yield {"__invalid_json__": True, "__line_no__": line_no}
                continue
            if isinstance(row, dict):
                yield row
            else:
                yield {"__non_object_json__": True, "__line_no__": line_no}


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def _error_bucket(message: object) -> str:
    text = str(message or "")
    if "Insufficient Balance" in text or "HTTP 402" in text:
        return "http_402_insufficient_balance"
    if "HTTP" in text:
        return text[:160]
    if not text:
        return "missing_error_message"
    return text[:160]


def _audit_shard(shard_dir: Path, shard_index: int) -> dict:
    manifest_path = shard_dir / "shard_manifest.jsonl"
    reviews_path = shard_dir / "chunk_reviews.jsonl"
    failures_path = shard_dir / "failures.jsonl"
    additional_path = shard_dir / "additional_claims.jsonl"
    hit_soft_cap_path = shard_dir / "hit_soft_cap_chunks.jsonl"
    run_summary_path = shard_dir / "run_summary.json"

    target_count = _count_jsonl(manifest_path)
    additional_count = _count_jsonl(additional_path)
    hit_soft_cap_count = _count_jsonl(hit_soft_cap_path)
    failure_file_rows_count = _count_jsonl(failures_path)

    physical_review_row_count = 0
    invalid_review_rows = 0
    physical_status_counts: Counter[str] = Counter()
    physical_final_status_counts: Counter[str] = Counter()
    latest_reviews_by_chunk: dict[str, dict] = {}
    duplicate_review_chunk_ids: Counter[str] = Counter()

    for row in _iter_jsonl(reviews_path) or []:
        physical_review_row_count += 1
        if row.get("__invalid_json__") or row.get("__non_object_json__"):
            invalid_review_rows += 1
            continue
        chunk_id = str(row.get("source_chunk_id", "") or "")
        if chunk_id:
            if chunk_id in latest_reviews_by_chunk:
                duplicate_review_chunk_ids[chunk_id] += 1
            latest_reviews_by_chunk[chunk_id] = row
        status = str(row.get("review_status", "") or "missing")
        physical_status_counts[status] += 1
        physical_final_status_counts[str(row.get("final_completion_status", "") or "missing")] += 1

    latest_status_counts: Counter[str] = Counter()
    latest_final_status_counts: Counter[str] = Counter()
    latest_failure_error_counts: Counter[str] = Counter()
    ok_review_count = 0
    error_review_count = 0
    review_additional_total = 0
    review_hit_soft_cap_count = 0
    for row in latest_reviews_by_chunk.values():
        status = str(row.get("review_status", "") or "missing")
        latest_status_counts[status] += 1
        latest_final_status_counts[str(row.get("final_completion_status", "") or "missing")] += 1
        if status == "ok":
            ok_review_count += 1
            try:
                review_additional_total += int(row.get("additional_claim_count", 0) or 0)
            except Exception:
                pass
            if bool(row.get("hit_soft_cap")):
                review_hit_soft_cap_count += 1
        elif status in {"error", "failed"}:
            error_review_count += 1
            latest_failure_error_counts[_error_bucket(row.get("error_message", ""))] += 1

    failure_error_counts: Counter[str] = Counter()
    failure_status_counts: Counter[str] = Counter()
    invalid_failure_rows = 0
    for row in _iter_jsonl(failures_path) or []:
        if row.get("__invalid_json__") or row.get("__non_object_json__"):
            invalid_failure_rows += 1
            continue
        failure_error_counts[_error_bucket(row.get("error_message", ""))] += 1
        failure_status_counts[str(row.get("final_completion_status", "") or row.get("review_status", "") or "missing")] += 1

    run_summary = _read_json(run_summary_path)
    files_present = {
        "shard_manifest.jsonl": manifest_path.exists(),
        "chunk_reviews.jsonl": reviews_path.exists(),
        "failures.jsonl": failures_path.exists(),
        "additional_claims.jsonl": additional_path.exists(),
        "hit_soft_cap_chunks.jsonl": hit_soft_cap_path.exists(),
        "run_summary.json": run_summary_path.exists(),
    }
    return {
        "shard_index": shard_index,
        "shard_name": f"shard_{shard_index:02d}",
        "shard_dir": _display_path(shard_dir),
        "files_present": files_present,
        "is_complete_file_set": all(files_present.values()),
        "target_chunk_count": target_count,
        "chunk_reviews_count": physical_review_row_count,
        "physical_chunk_review_rows": physical_review_row_count,
        "unique_reviewed_chunk_count": len(latest_reviews_by_chunk),
        "ok_review_count": ok_review_count,
        "error_review_count": error_review_count,
        "failures_count": error_review_count,
        "failure_file_rows_count": failure_file_rows_count,
        "additional_claims_count": review_additional_total,
        "additional_claims_file_rows_count": additional_count,
        "hit_soft_cap_chunks_count": review_hit_soft_cap_count,
        "hit_soft_cap_file_rows_count": hit_soft_cap_count,
        "review_hit_soft_cap_count": review_hit_soft_cap_count,
        "review_additional_claims_total": review_additional_total,
        "invalid_review_rows": invalid_review_rows,
        "invalid_failure_rows": invalid_failure_rows,
        "duplicate_review_chunk_id_count": sum(duplicate_review_chunk_ids.values()),
        "duplicate_review_chunk_ids_sample": dict(duplicate_review_chunk_ids.most_common(10)),
        "physical_review_status_counts": dict(sorted(physical_status_counts.items())),
        "physical_final_completion_status_counts": dict(sorted(physical_final_status_counts.items())),
        "review_status_counts": dict(sorted(latest_status_counts.items())),
        "final_completion_status_counts": dict(sorted(latest_final_status_counts.items())),
        "failure_error_counts": dict(failure_error_counts.most_common(20)),
        "latest_failure_error_counts": dict(latest_failure_error_counts.most_common(20)),
        "failure_status_counts": dict(sorted(failure_status_counts.items())),
        "chunk_reviews_match_target": physical_review_row_count == target_count,
        "unique_reviewed_chunks_match_target": len(latest_reviews_by_chunk) == target_count,
        "failures_match_error_reviews": failure_file_rows_count == error_review_count,
        "additional_claims_match_review_total": additional_count == review_additional_total,
        "hit_soft_cap_match_reviews": hit_soft_cap_count == review_hit_soft_cap_count,
        "run_summary_selected": {
            "total_target_chunks": run_summary.get("total_target_chunks"),
            "total_shard_chunks": run_summary.get("total_shard_chunks"),
            "completed_chunks": run_summary.get("completed_chunks"),
            "failed_chunks": run_summary.get("failed_chunks"),
            "reviewed_chunks_total": run_summary.get("reviewed_chunks_total"),
            "total_additional_claims": run_summary.get("total_additional_claims"),
            "hit_soft_cap_chunk_count": run_summary.get("hit_soft_cap_chunk_count"),
            "max_additional_claims_per_round": run_summary.get("max_additional_claims_per_round", run_summary.get("max_additional_claims")),
            "continuation_policy": run_summary.get("continuation_policy"),
            "hit_soft_cap_policy": run_summary.get("hit_soft_cap_policy"),
        },
    }


def _aggregate(shards: list[dict], expected_count: int, expected_shards: int) -> dict:
    totals = {
        "target_chunk_count": sum(int(s["target_chunk_count"]) for s in shards),
        "chunk_reviews_count": sum(int(s["chunk_reviews_count"]) for s in shards),
        "physical_chunk_review_rows": sum(int(s["physical_chunk_review_rows"]) for s in shards),
        "unique_reviewed_chunk_count_sum": sum(int(s["unique_reviewed_chunk_count"]) for s in shards),
        "ok_review_count": sum(int(s["ok_review_count"]) for s in shards),
        "error_review_count": sum(int(s["error_review_count"]) for s in shards),
        "failures_count": sum(int(s["failures_count"]) for s in shards),
        "failure_file_rows_count": sum(int(s["failure_file_rows_count"]) for s in shards),
        "additional_claims_count": sum(int(s["additional_claims_count"]) for s in shards),
        "additional_claims_file_rows_count": sum(int(s["additional_claims_file_rows_count"]) for s in shards),
        "hit_soft_cap_chunks_count": sum(int(s["hit_soft_cap_chunks_count"]) for s in shards),
        "hit_soft_cap_file_rows_count": sum(int(s["hit_soft_cap_file_rows_count"]) for s in shards),
        "invalid_review_rows": sum(int(s["invalid_review_rows"]) for s in shards),
        "invalid_failure_rows": sum(int(s["invalid_failure_rows"]) for s in shards),
        "duplicate_review_chunk_id_count": sum(int(s["duplicate_review_chunk_id_count"]) for s in shards),
    }
    failure_errors = Counter()
    for shard in shards:
        failure_errors.update(shard.get("latest_failure_error_counts", {}))
    missing_shards = [index for index in range(expected_shards) if not any(s["shard_index"] == index for s in shards)]
    all_files_present = all(s["is_complete_file_set"] for s in shards) and not missing_shards
    physical_chunk_reviews_match_target = all(s["chunk_reviews_match_target"] for s in shards)
    all_unique_reviewed_chunks_match_target = all(s["unique_reviewed_chunks_match_target"] for s in shards)
    all_additional_match_reviews = all(s["additional_claims_match_review_total"] for s in shards)
    all_failures_match_errors = all(s["failures_match_error_reviews"] for s in shards)
    all_hit_soft_cap_match = all(s["hit_soft_cap_match_reviews"] for s in shards)
    physical_chunk_reviews_equals_expected = totals["chunk_reviews_count"] == expected_count
    unique_reviewed_chunks_equals_expected = totals["unique_reviewed_chunk_count_sum"] == expected_count
    ok_reviews_equals_expected = totals["ok_review_count"] == expected_count
    severe_failure_count = totals["failures_count"]
    ready_to_merge = (
        all_files_present
        and all_unique_reviewed_chunks_match_target
        and unique_reviewed_chunks_equals_expected
        and severe_failure_count == 0
        and totals["invalid_review_rows"] == 0
        and totals["invalid_failure_rows"] == 0
        and all_additional_match_reviews
        and all_failures_match_errors
        and all_hit_soft_cap_match
    )
    return {
        **totals,
        "expected_shard_count": expected_shards,
        "actual_shard_count": len(shards),
        "missing_shards": missing_shards,
        "all_shards_present": len(shards) == expected_shards and not missing_shards,
        "all_required_files_present": all_files_present,
        "all_chunk_reviews_match_targets": physical_chunk_reviews_match_target,
        "all_unique_reviewed_chunks_match_targets": all_unique_reviewed_chunks_match_target,
        "completed_chunk_reviews_equals_expected": physical_chunk_reviews_equals_expected,
        "physical_chunk_reviews_equals_expected": physical_chunk_reviews_equals_expected,
        "unique_reviewed_chunks_equals_expected": unique_reviewed_chunks_equals_expected,
        "ok_reviews_equals_expected": ok_reviews_equals_expected,
        "expected_global_chunk_count": expected_count,
        "failure_error_counts": dict(failure_errors.most_common(20)),
        "failure_rate_over_targets": _safe_div(totals["failures_count"], totals["target_chunk_count"]),
        "ok_rate_over_targets": _safe_div(totals["ok_review_count"], totals["target_chunk_count"]),
        "additional_claims_per_ok_chunk": _safe_div(totals["additional_claims_count"], totals["ok_review_count"]),
        "hit_soft_cap_rate_over_ok_chunks": _safe_div(totals["hit_soft_cap_chunks_count"], totals["ok_review_count"]),
        "all_additional_claims_match_review_totals": all_additional_match_reviews,
        "all_failures_match_error_reviews": all_failures_match_errors,
        "all_hit_soft_cap_files_match_reviews": all_hit_soft_cap_match,
        "severe_failure_count": severe_failure_count,
        "ready_to_merge": ready_to_merge,
        "blocking_reasons": _blocking_reasons(
            all_files_present=all_files_present,
            all_chunk_reviews_match_target=physical_chunk_reviews_match_target,
            completed_chunk_reviews_equals_expected=physical_chunk_reviews_equals_expected,
            all_unique_reviewed_chunks_match_target=all_unique_reviewed_chunks_match_target,
            unique_reviewed_chunks_equals_expected=unique_reviewed_chunks_equals_expected,
            severe_failure_count=severe_failure_count,
            invalid_review_rows=totals["invalid_review_rows"],
            invalid_failure_rows=totals["invalid_failure_rows"],
            all_additional_match_reviews=all_additional_match_reviews,
            all_failures_match_errors=all_failures_match_errors,
            all_hit_soft_cap_match=all_hit_soft_cap_match,
        ),
    }


def _blocking_reasons(**kwargs) -> list[str]:
    reasons = []
    if not kwargs["all_files_present"]:
        reasons.append("One or more shard directories/files are missing.")
    if not kwargs["all_unique_reviewed_chunks_match_target"]:
        reasons.append("At least one shard has latest unique reviewed chunk count not matching its target manifest count.")
    if not kwargs["unique_reviewed_chunks_equals_expected"]:
        reasons.append(f"Global latest unique reviewed chunk count does not equal expected {EXPECTED_GLOBAL_CHUNKS}.")
    if not kwargs["all_chunk_reviews_match_target"] or not kwargs["completed_chunk_reviews_equals_expected"]:
        reasons.append(
            "Physical chunk_reviews row count differs from manifest count. This can happen after retry appends; "
            "latest unique chunk status is used for merge gating."
        )
    if kwargs["severe_failure_count"] > 0:
        reasons.append(f"Supplement run has {kwargs['severe_failure_count']} failed chunk reviews; retry is needed before merge.")
    if kwargs["invalid_review_rows"] > 0:
        reasons.append(f"Found {kwargs['invalid_review_rows']} invalid chunk review rows.")
    if kwargs["invalid_failure_rows"] > 0:
        reasons.append(f"Found {kwargs['invalid_failure_rows']} invalid failure rows.")
    if not kwargs["all_additional_match_reviews"]:
        reasons.append("Additional claims JSONL line counts do not match summed review additional counts.")
    if not kwargs["all_failures_match_errors"]:
        reasons.append("Failures JSONL line counts do not match error review counts.")
    if not kwargs["all_hit_soft_cap_match"]:
        reasons.append("Hit-soft-cap JSONL line counts do not match review hit_soft_cap flags.")
    return reasons


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(value) for value in row) + " |")
    return "\n".join(lines)


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _fmt_float(value: float) -> str:
    return f"{value:.4f}"


def _build_markdown(summary: dict) -> str:
    g = summary["global"]
    overview_rows = [
        ["Expected shards", _fmt_int(g["expected_shard_count"])],
        ["Actual shards", _fmt_int(g["actual_shard_count"])],
        ["All shards present", g["all_shards_present"]],
        ["Target chunks", _fmt_int(g["target_chunk_count"])],
        ["physical chunk_reviews rows", _fmt_int(g["physical_chunk_review_rows"])],
        ["physical chunk_reviews rows == 93,542", g["physical_chunk_reviews_equals_expected"]],
        ["latest unique reviewed chunks", _fmt_int(g["unique_reviewed_chunk_count_sum"])],
        ["latest unique reviewed chunks == 93,542", g["unique_reviewed_chunks_equals_expected"]],
        ["Latest OK review chunks", _fmt_int(g["ok_review_count"])],
        ["Latest failure chunks", _fmt_int(g["failures_count"])],
        ["failure file rows", _fmt_int(g["failure_file_rows_count"])],
        ["Failure rate over targets", _fmt_float(g["failure_rate_over_targets"])],
        ["Additional claims", _fmt_int(g["additional_claims_count"])],
        ["additional_claims file rows", _fmt_int(g["additional_claims_file_rows_count"])],
        ["Hit soft cap chunks", _fmt_int(g["hit_soft_cap_chunks_count"])],
        ["hit_soft_cap file rows", _fmt_int(g["hit_soft_cap_file_rows_count"])],
        ["Ready to merge", g["ready_to_merge"]],
    ]
    shard_rows = [
        [
            shard["shard_name"],
            _fmt_int(shard["target_chunk_count"]),
            _fmt_int(shard["physical_chunk_review_rows"]),
            _fmt_int(shard["unique_reviewed_chunk_count"]),
            _fmt_int(shard["ok_review_count"]),
            _fmt_int(shard["failures_count"]),
            _fmt_int(shard["additional_claims_count"]),
            _fmt_int(shard["hit_soft_cap_chunks_count"]),
            shard["chunk_reviews_match_target"],
            shard["is_complete_file_set"],
        ]
        for shard in summary["shards"]
    ]
    failure_rows = [[key, _fmt_int(value)] for key, value in g["failure_error_counts"].items()]
    if not failure_rows:
        failure_rows = [["none", "0"]]
    blocking_text = "\n".join(f"- {reason}" for reason in g["blocking_reasons"]) if g["blocking_reasons"] else "None."
    return "\n\n".join(
        [
            "# Claim Cap Supplement Full Run Audit",
            (
                "Read-only audit of KG/intermediate/claims_cap_supplement_full. "
                "No Claim/Fact artifacts were modified and no merge/rebuild/materialization was run."
            ),
            "## Global Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## Blocking Reasons\n\n" + blocking_text,
            "## Shards\n\n"
            + _markdown_table(
                [
                    "Shard",
                    "Target chunks",
                    "physical reviews",
                    "latest unique",
                    "Latest OK",
                    "Latest failures",
                    "Additional claims",
                    "Hit soft cap",
                    "Physical rows match target",
                    "Files complete",
                ],
                shard_rows,
            ),
            "## Failure Error Buckets\n\n" + _markdown_table(["Error bucket", "Count"], failure_rows),
            "## Decision\n\n"
            + (
                "The run is merge-ready."
                if g["ready_to_merge"]
                else "The run is not merge-ready. Retry or resolve failed chunk reviews before merging into claims_final_global_v2."
            ),
        ]
    )


def audit_run(*, supplement_dir: Path, out_json: Path, out_md: Path, expected_count: int, expected_shards: int) -> dict:
    shards = []
    for index in range(expected_shards):
        shard_dir = supplement_dir / f"shard_{index:02d}"
        if shard_dir.exists():
            shards.append(_audit_shard(shard_dir, index))
    summary = {
        "inputs": {
            "supplement_dir": _display_path(supplement_dir),
        },
        "outputs": {
            "json": _display_path(out_json),
            "markdown": _display_path(out_md),
        },
        "global": _aggregate(shards, expected_count, expected_shards),
        "shards": shards,
        "note": (
            "Read-only run audit. This report does not modify claims_final_global, "
            "claims_cap_supplement_full, facts_final_global, or Neo4j artifacts."
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_json, summary)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit full claim-cap supplementary extraction shard outputs.")
    parser.add_argument("--supplement-dir", default="KG/intermediate/claims_cap_supplement_full")
    parser.add_argument("--out-json", default="KG/reports/claim_cap_supplement_full_run_audit.json")
    parser.add_argument("--out-md", default="KG/reports/claim_cap_supplement_full_run_audit.md")
    parser.add_argument("--expected-count", type=int, default=EXPECTED_GLOBAL_CHUNKS)
    parser.add_argument("--expected-shards", type=int, default=EXPECTED_SHARDS)
    args = parser.parse_args()
    summary = audit_run(
        supplement_dir=_resolve_path(args.supplement_dir),
        out_json=_resolve_path(args.out_json),
        out_md=_resolve_path(args.out_md),
        expected_count=args.expected_count,
        expected_shards=args.expected_shards,
    )
    g = summary["global"]
    print(f"[Step3][CLAIM_CAP_SUPPLEMENT_AUDIT] json={summary['outputs']['json']}")
    print(f"[Step3][CLAIM_CAP_SUPPLEMENT_AUDIT] md={summary['outputs']['markdown']}")
    print(
        "[Step3][CLAIM_CAP_SUPPLEMENT_AUDIT] "
        f"targets={g['target_chunk_count']} chunk_reviews={g['chunk_reviews_count']} "
        f"ok={g['ok_review_count']} failures={g['failures_count']} "
        f"additional={g['additional_claims_count']} hit_soft_cap={g['hit_soft_cap_chunks_count']} "
        f"ready_to_merge={g['ready_to_merge']}"
    )


if __name__ == "__main__":
    main()
