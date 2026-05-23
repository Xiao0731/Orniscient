"""Compact claim-cap supplement shard reviews to latest valid review per chunk.

This script does not call an LLM and does not touch claims/facts final outputs.
It normalizes each shard directory by rewriting:
- chunk_reviews.jsonl
- additional_claims.jsonl
- failures.jsonl
- hit_soft_cap_chunks.jsonl
- run_summary.json

The "latest" review policy matches audit_claim_cap_supplement_full_run.py:
valid JSON review rows are read in file order, and later rows for the same
source_chunk_id replace earlier rows. Empty and malformed rows are recorded in
the compaction audit but are not allowed to crash the run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
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


def _read_jsonl_valid(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _claims_from_review(review: dict) -> list[dict]:
    return [claim for claim in review.get("additional_claims", []) if isinstance(claim, dict)]


def _hit_soft_cap_row(review: dict) -> dict:
    return {
        "source_chunk_id": review.get("source_chunk_id", ""),
        "source_chapter": review.get("source_chapter", ""),
        "source_subchapter": review.get("source_subchapter", ""),
        "subject_taxon_id": review.get("subject_taxon_id", ""),
        "subject_rank": review.get("subject_rank", ""),
        "existing_claim_count": review.get("existing_claim_count", review.get("claim_count", 0)),
        "round_1_additional_claim_count": review.get(
            "round_1_additional_claim_count",
            review.get("additional_claim_count", 0),
        ),
        "hit_soft_cap_round_1": bool(review.get("hit_soft_cap_round_1")),
        "possibly_incomplete_due_to_cap": bool(review.get("possibly_incomplete_due_to_cap")),
        "final_completion_status": review.get("final_completion_status", ""),
    }


def _summarize_reviews(reviews: list[dict]) -> dict:
    ok = [row for row in reviews if row.get("review_status") == "ok"]
    errors = [row for row in reviews if row.get("review_status") == "error"]
    dry_runs = [row for row in reviews if row.get("review_status") == "dry_run"]
    positive = [row for row in ok if int(row.get("additional_claim_count", 0) or 0) > 0]
    hit_soft_cap = [row for row in ok if row.get("hit_soft_cap_round_1") is True]
    additional_total = sum(int(row.get("additional_claim_count", 0) or 0) for row in ok)
    near_dup = sum(int(row.get("duplicate_assessment", {}).get("near_duplicate_count", 0) or 0) for row in ok)
    by_chapter = defaultdict(lambda: {"chunks": 0, "positive": 0, "additional": 0, "near_duplicate": 0, "hit_soft_cap": 0})
    for row in ok:
        chapter = str(row.get("source_chapter", "") or "")
        by_chapter[chapter]["chunks"] += 1
        by_chapter[chapter]["positive"] += 1 if int(row.get("additional_claim_count", 0) or 0) > 0 else 0
        by_chapter[chapter]["additional"] += int(row.get("additional_claim_count", 0) or 0)
        by_chapter[chapter]["near_duplicate"] += int(row.get("duplicate_assessment", {}).get("near_duplicate_count", 0) or 0)
        by_chapter[chapter]["hit_soft_cap"] += 1 if row.get("hit_soft_cap_round_1") is True else 0
    return {
        "reviewed_chunk_count": len(reviews),
        "ok_count": len(ok),
        "error_count": len(errors),
        "dry_run_count": len(dry_runs),
        "chunks_with_additional_claims": len(positive),
        "positive_chunk_ratio": _safe_div(len(positive), len(ok)),
        "total_additional_claims": additional_total,
        "avg_additional_claims_per_ok_chunk": _safe_div(additional_total, len(ok)),
        "avg_additional_claims_per_positive_chunk": _safe_div(additional_total, len(positive)),
        "hit_soft_cap_chunks": len(hit_soft_cap),
        "hit_soft_cap_ratio": _safe_div(len(hit_soft_cap), len(ok)),
        "near_duplicate_additional_claims": near_dup,
        "near_duplicate_ratio": _safe_div(near_dup, additional_total),
        "by_source_chapter": dict(sorted(by_chapter.items())),
    }


def _compact_reviews(path: Path) -> dict:
    latest: dict[str, dict] = {}
    raw_physical_lines = 0
    raw_nonempty_lines = 0
    empty_lines = 0
    bad_json_lines = 0
    non_object_rows = 0
    missing_chunk_id_rows = 0
    overwritten_valid_rows = 0
    bad_samples = []

    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw_physical_lines += 1
            stripped = line.strip()
            if not stripped:
                empty_lines += 1
                continue
            raw_nonempty_lines += 1
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                bad_json_lines += 1
                if len(bad_samples) < 20:
                    bad_samples.append(
                        {
                            "line_no": line_no,
                            "error": exc.msg,
                            "preview": stripped[:240],
                        }
                    )
                continue
            if not isinstance(row, dict):
                non_object_rows += 1
                continue
            chunk_id = str(row.get("source_chunk_id", "") or "").strip()
            if not chunk_id:
                missing_chunk_id_rows += 1
                continue
            if chunk_id in latest:
                overwritten_valid_rows += 1
            latest[chunk_id] = row

    return {
        "latest": latest,
        "raw_physical_lines": raw_physical_lines,
        "raw_nonempty_lines": raw_nonempty_lines,
        "empty_lines": empty_lines,
        "bad_json_lines": bad_json_lines,
        "non_object_rows": non_object_rows,
        "missing_chunk_id_rows": missing_chunk_id_rows,
        "overwritten_valid_rows": overwritten_valid_rows,
        "bad_json_samples": bad_samples,
    }


def _ordered_latest_reviews(latest: dict[str, dict], manifest_rows: list[dict]) -> tuple[list[dict], list[str], list[str]]:
    ordered = []
    seen = set()
    missing = []
    for manifest in manifest_rows:
        chunk_id = str(manifest.get("source_chunk_id", "") or "").strip()
        if not chunk_id:
            continue
        row = latest.get(chunk_id)
        if row is None:
            missing.append(chunk_id)
            continue
        ordered.append(row)
        seen.add(chunk_id)
    extras = sorted(chunk_id for chunk_id in latest if chunk_id not in seen)
    for chunk_id in extras:
        ordered.append(latest[chunk_id])
    return ordered, missing, extras


def _rewrite_derived_outputs(shard_dir: Path, reviews: list[dict]) -> dict:
    additional_rows = []
    for review in reviews:
        additional_rows.extend(_claims_from_review(review))
    additional_rows = sorted(
        additional_rows,
        key=lambda row: (
            str(row.get("source_chunk_id", "")),
            str(row.get("supplement_claim_id", "")),
            str(row.get("predicate", "")),
            str(row.get("object_text", "")),
        ),
    )
    failures = sorted(
        [row for row in reviews if row.get("review_status") == "error"],
        key=lambda row: str(row.get("source_chunk_id", "")),
    )
    hit_rows = sorted(
        [_hit_soft_cap_row(row) for row in reviews if row.get("hit_soft_cap_round_1") is True],
        key=lambda row: str(row.get("source_chunk_id", "")),
    )
    _write_jsonl_atomic(shard_dir / "additional_claims.jsonl", additional_rows)
    _write_jsonl_atomic(shard_dir / "failures.jsonl", failures)
    _write_jsonl_atomic(shard_dir / "hit_soft_cap_chunks.jsonl", hit_rows)
    return {
        "additional_claims_written": len(additional_rows),
        "failures_written": len(failures),
        "hit_soft_cap_chunks_written": len(hit_rows),
    }


def _write_run_summary(shard_dir: Path, shard_index: int, manifest_rows: list[dict], reviews: list[dict], derived: dict) -> dict:
    previous = {}
    summary_path = shard_dir / "run_summary.json"
    if summary_path.exists():
        try:
            previous = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
    review_summary = _summarize_reviews(reviews)
    summary = {
        "shard_index": shard_index,
        "shard_dir": str(shard_dir),
        "manifest": str(shard_dir / "shard_manifest.jsonl"),
        "review_path": str(shard_dir / "chunk_reviews.jsonl"),
        "additional_claims_path": str(shard_dir / "additional_claims.jsonl"),
        "failures_path": str(shard_dir / "failures.jsonl"),
        "hit_soft_cap_chunks_path": str(shard_dir / "hit_soft_cap_chunks.jsonl"),
        "log_path": str(shard_dir / "run.log"),
        "total_target_chunks": len(manifest_rows),
        "total_shard_chunks": len(manifest_rows),
        "completed_chunks": review_summary["ok_count"],
        "failed_chunks": review_summary["error_count"],
        "reviewed_chunks_total": len(reviews),
        "chunks_with_additional_claims": review_summary["chunks_with_additional_claims"],
        "total_additional_claims": review_summary["total_additional_claims"],
        "average_additional_claims_per_chunk": _safe_div(review_summary["total_additional_claims"], review_summary["ok_count"]),
        "hit_soft_cap_chunks": review_summary["hit_soft_cap_chunks"],
        "hit_soft_cap_chunk_count": review_summary["hit_soft_cap_chunks"],
        "total_round_1_additional_claims": review_summary["total_additional_claims"],
        "additional_claims_written": derived["additional_claims_written"],
        "failures_written": derived["failures_written"],
        "hit_soft_cap_chunks_written": derived["hit_soft_cap_chunks_written"],
        "max_chars": previous.get("max_chars", 6500),
        "max_additional_claims": previous.get("max_additional_claims", 6),
        "max_additional_claims_per_round": previous.get("max_additional_claims_per_round", previous.get("max_additional_claims", 6)),
        "continuation_policy": previous.get("continuation_policy", "none_single_round_only"),
        "hit_soft_cap_policy": previous.get("hit_soft_cap_policy", "record_only_no_continuation"),
        "dry_run": False,
        "compacted_from_retry_log": True,
        "inputs": previous.get("inputs", {}),
        "summary": review_summary,
    }
    write_json(summary_path, summary)
    return summary


def _compact_shard(supplement_dir: Path, shard_index: int) -> dict:
    shard_dir = supplement_dir / f"shard_{shard_index:02d}"
    manifest_path = shard_dir / "shard_manifest.jsonl"
    review_path = shard_dir / "chunk_reviews.jsonl"
    manifest_rows = _read_jsonl_valid(manifest_path)
    compacted = _compact_reviews(review_path)
    ordered_reviews, missing_manifest_chunk_ids, extra_review_chunk_ids = _ordered_latest_reviews(compacted["latest"], manifest_rows)
    _write_jsonl_atomic(review_path, ordered_reviews)
    derived = _rewrite_derived_outputs(shard_dir, ordered_reviews)
    run_summary = _write_run_summary(shard_dir, shard_index, manifest_rows, ordered_reviews, derived)
    status_counts = Counter(str(row.get("review_status", "") or "missing") for row in ordered_reviews)
    final_status_counts = Counter(str(row.get("final_completion_status", "") or "missing") for row in ordered_reviews)
    return {
        "shard_index": shard_index,
        "shard_name": f"shard_{shard_index:02d}",
        "shard_dir": _display_path(shard_dir),
        "target_chunk_count": len(manifest_rows),
        "raw_physical_lines": compacted["raw_physical_lines"],
        "raw_nonempty_lines": compacted["raw_nonempty_lines"],
        "empty_lines": compacted["empty_lines"],
        "bad_json_lines": compacted["bad_json_lines"],
        "non_object_rows": compacted["non_object_rows"],
        "missing_chunk_id_rows": compacted["missing_chunk_id_rows"],
        "discarded_old_review_rows": compacted["overwritten_valid_rows"],
        "compacted_review_rows": len(ordered_reviews),
        "missing_manifest_chunk_count": len(missing_manifest_chunk_ids),
        "missing_manifest_chunk_ids_sample": missing_manifest_chunk_ids[:20],
        "extra_review_chunk_count": len(extra_review_chunk_ids),
        "extra_review_chunk_ids_sample": extra_review_chunk_ids[:20],
        "review_status_counts": dict(sorted(status_counts.items())),
        "final_completion_status_counts": dict(sorted(final_status_counts.items())),
        "additional_claims_written": derived["additional_claims_written"],
        "failures_written": derived["failures_written"],
        "hit_soft_cap_chunks_written": derived["hit_soft_cap_chunks_written"],
        "run_summary_selected": {
            "completed_chunks": run_summary["completed_chunks"],
            "failed_chunks": run_summary["failed_chunks"],
            "reviewed_chunks_total": run_summary["reviewed_chunks_total"],
            "total_additional_claims": run_summary["total_additional_claims"],
            "hit_soft_cap_chunk_count": run_summary["hit_soft_cap_chunk_count"],
        },
        "bad_json_samples": compacted["bad_json_samples"],
    }


def _aggregate(shards: list[dict], expected_count: int) -> dict:
    totals = {
        "raw_physical_lines": sum(int(row["raw_physical_lines"]) for row in shards),
        "raw_nonempty_lines": sum(int(row["raw_nonempty_lines"]) for row in shards),
        "empty_lines": sum(int(row["empty_lines"]) for row in shards),
        "bad_json_lines": sum(int(row["bad_json_lines"]) for row in shards),
        "non_object_rows": sum(int(row["non_object_rows"]) for row in shards),
        "missing_chunk_id_rows": sum(int(row["missing_chunk_id_rows"]) for row in shards),
        "discarded_old_review_rows": sum(int(row["discarded_old_review_rows"]) for row in shards),
        "compacted_review_rows": sum(int(row["compacted_review_rows"]) for row in shards),
        "target_chunk_count": sum(int(row["target_chunk_count"]) for row in shards),
        "additional_claims_written": sum(int(row["additional_claims_written"]) for row in shards),
        "failures_written": sum(int(row["failures_written"]) for row in shards),
        "hit_soft_cap_chunks_written": sum(int(row["hit_soft_cap_chunks_written"]) for row in shards),
        "missing_manifest_chunk_count": sum(int(row["missing_manifest_chunk_count"]) for row in shards),
        "extra_review_chunk_count": sum(int(row["extra_review_chunk_count"]) for row in shards),
    }
    totals["expected_global_chunk_count"] = expected_count
    totals["compacted_rows_match_expected"] = totals["compacted_review_rows"] == expected_count
    totals["target_count_match_expected"] = totals["target_chunk_count"] == expected_count
    totals["failures_zero"] = totals["failures_written"] == 0
    totals["ok_to_reaudit"] = (
        totals["compacted_rows_match_expected"]
        and totals["target_count_match_expected"]
        and totals["failures_zero"]
        and totals["missing_manifest_chunk_count"] == 0
        and totals["extra_review_chunk_count"] == 0
    )
    return totals


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


def _build_markdown(summary: dict) -> str:
    g = summary["global"]
    overview_rows = [
        ["Original raw non-empty chunk_reviews rows", _fmt_int(g["raw_nonempty_lines"])],
        ["Original physical chunk_reviews lines", _fmt_int(g["raw_physical_lines"])],
        ["Compacted chunk_reviews rows", _fmt_int(g["compacted_review_rows"])],
        ["Expected target chunks", _fmt_int(g["expected_global_chunk_count"])],
        ["Discarded old review rows", _fmt_int(g["discarded_old_review_rows"])],
        ["Empty lines", _fmt_int(g["empty_lines"])],
        ["Bad JSON lines", _fmt_int(g["bad_json_lines"])],
        ["Non-object rows", _fmt_int(g["non_object_rows"])],
        ["Missing chunk-id rows", _fmt_int(g["missing_chunk_id_rows"])],
        ["Additional claims after rewrite", _fmt_int(g["additional_claims_written"])],
        ["Hit-soft-cap chunks after rewrite", _fmt_int(g["hit_soft_cap_chunks_written"])],
        ["Failures after rewrite", _fmt_int(g["failures_written"])],
        ["OK to rerun audit", g["ok_to_reaudit"]],
    ]
    shard_rows = [
        [
            row["shard_name"],
            _fmt_int(row["target_chunk_count"]),
            _fmt_int(row["raw_nonempty_lines"]),
            _fmt_int(row["compacted_review_rows"]),
            _fmt_int(row["discarded_old_review_rows"]),
            _fmt_int(row["empty_lines"]),
            _fmt_int(row["bad_json_lines"]),
            _fmt_int(row["additional_claims_written"]),
            _fmt_int(row["hit_soft_cap_chunks_written"]),
            _fmt_int(row["failures_written"]),
        ]
        for row in summary["shards"]
    ]
    shard15 = next((row for row in summary["shards"] if row["shard_name"] == "shard_15"), {})
    bad_samples = []
    for row in summary["shards"]:
        for sample in row.get("bad_json_samples", []):
            bad_samples.append([row["shard_name"], sample["line_no"], sample["error"], sample["preview"]])
    bad_section = (
        _markdown_table(["Shard", "Line", "Error", "Preview"], bad_samples[:20])
        if bad_samples
        else "No bad JSON lines were found."
    )
    return "\n\n".join(
        [
            "# Claim Cap Supplement Review Compaction",
            (
                "Compacted retry-expanded supplement review artifacts to one latest valid review per source_chunk_id. "
                "No LLM calls, claim merge, fact rebuild, object layer, or Neo4j materialization were performed."
            ),
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## Shards\n\n"
            + _markdown_table(
                [
                    "Shard",
                    "Target",
                    "Raw non-empty",
                    "Compacted",
                    "Discarded old",
                    "Empty",
                    "Bad JSON",
                    "Additional",
                    "Hit soft cap",
                    "Failures",
                ],
                shard_rows,
            ),
            "## Shard 15 Bad Lines\n\n"
            + _markdown_table(
                ["Metric", "Value"],
                [
                    ["shard_15 bad JSON lines", _fmt_int(int(shard15.get("bad_json_lines", 0)))],
                    ["shard_15 empty lines", _fmt_int(int(shard15.get("empty_lines", 0)))],
                ],
            ),
            "## Bad JSON Samples\n\n" + bad_section,
        ]
    )


def compact_all(*, supplement_dir: Path, out_json: Path, out_md: Path, expected_shards: int, expected_count: int) -> dict:
    shards = []
    for shard_index in range(expected_shards):
        shard_dir = supplement_dir / f"shard_{shard_index:02d}"
        if not shard_dir.exists():
            raise FileNotFoundError(f"Missing shard directory: {shard_dir}")
        shards.append(_compact_shard(supplement_dir, shard_index))
    summary = {
        "inputs": {
            "supplement_dir": _display_path(supplement_dir),
            "expected_shards": expected_shards,
            "expected_global_chunk_count": expected_count,
        },
        "outputs": {
            "json": _display_path(out_json),
            "markdown": _display_path(out_md),
        },
        "global": _aggregate(shards, expected_count),
        "shards": shards,
        "note": (
            "Compaction rewrites supplement shard artifacts only: chunk_reviews.jsonl, additional_claims.jsonl, "
            "failures.jsonl, hit_soft_cap_chunks.jsonl, and run_summary.json. It does not modify old claims/facts "
            "or perform merge/rebuild/materialization."
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_json, summary)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    _write_text_atomic(out_md, _build_markdown(summary))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Compact claim-cap supplement reviews to latest valid row per chunk.")
    parser.add_argument("--supplement-dir", default="KG/intermediate/claims_cap_supplement_full")
    parser.add_argument("--out-json", default="KG/reports/claim_cap_supplement_review_compaction.json")
    parser.add_argument("--out-md", default="KG/reports/claim_cap_supplement_review_compaction.md")
    parser.add_argument("--expected-shards", type=int, default=EXPECTED_SHARDS)
    parser.add_argument("--expected-count", type=int, default=EXPECTED_GLOBAL_CHUNKS)
    args = parser.parse_args()
    summary = compact_all(
        supplement_dir=_resolve_path(args.supplement_dir),
        out_json=_resolve_path(args.out_json),
        out_md=_resolve_path(args.out_md),
        expected_shards=args.expected_shards,
        expected_count=args.expected_count,
    )
    g = summary["global"]
    print(f"[Step3][CLAIM_CAP_SUPPLEMENT_COMPACT] json={summary['outputs']['json']}")
    print(f"[Step3][CLAIM_CAP_SUPPLEMENT_COMPACT] md={summary['outputs']['markdown']}")
    print(
        "[Step3][CLAIM_CAP_SUPPLEMENT_COMPACT] "
        f"raw_nonempty={g['raw_nonempty_lines']} compacted={g['compacted_review_rows']} "
        f"discarded_old={g['discarded_old_review_rows']} empty={g['empty_lines']} "
        f"bad_json={g['bad_json_lines']} additional={g['additional_claims_written']} "
        f"hit_soft_cap={g['hit_soft_cap_chunks_written']} failures={g['failures_written']} "
        f"ok_to_reaudit={g['ok_to_reaudit']}"
    )


if __name__ == "__main__":
    main()
