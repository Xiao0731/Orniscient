"""Merge old and repair Step 3 claims into a global, taxon-sorted claim layer."""

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

from kg_v2.utils.jsonl_utils import write_json, write_jsonl


CLAIM_FILES = ("species_claims.jsonl", "family_claims.jsonl")


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "KG":
        return (ROOT / path).resolve()
    return (KG_ROOT / path).resolve()


def _read_jsonl_lenient(path: Path, warnings: list[str]) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        warnings.append(f"missing file: {path}")
        return rows
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
                    rows.append(row)
                else:
                    warnings.append(f"non-object JSONL row in {path}: line={line_no}")
    except OSError as exc:
        warnings.append(f"could not read {path}: {exc}")
    return rows


def _chunk_id(row: dict) -> str:
    return str(row.get("chunk_id") or row.get("source_chunk_id") or "").strip()


def _claim_sort_key(row: dict) -> tuple[str, str, str, str, str, str, str]:
    return (
        str(row.get("subject_rank", "") or ""),
        str(row.get("subject_taxon_id", "") or ""),
        str(row.get("source_doc_id", "") or ""),
        str(row.get("source_chunk_id", "") or ""),
        str(row.get("fact_domain", "") or ""),
        str(row.get("predicate", "") or ""),
        str(row.get("claim_id", "") or ""),
    )


def _discover_shard_dirs(root: Path, expected_shards: int) -> list[Path]:
    return [root / f"shard_{index:02d}" for index in range(expected_shards)]


def _read_processed(shard_dirs: list[Path], label: str, warnings: list[str]) -> tuple[list[dict], dict[str, dict]]:
    rows: list[dict] = []
    by_chunk_id: dict[str, dict] = {}
    for shard_dir in shard_dirs:
        path = shard_dir / "processed_chunks.jsonl"
        for row in _read_jsonl_lenient(path, warnings):
            chunk_id = _chunk_id(row)
            wrapped = {"merge_source": label, "shard": shard_dir.name, **row}
            rows.append(wrapped)
            if chunk_id and chunk_id not in by_chunk_id:
                by_chunk_id[chunk_id] = wrapped
    return rows, by_chunk_id


def _read_claims(shard_dirs: list[Path], label: str, warnings: list[str]) -> tuple[list[dict], list[dict]]:
    claims: list[dict] = []
    audit_rows: list[dict] = []
    for shard_dir in shard_dirs:
        for claim_file in CLAIM_FILES:
            path = shard_dir / claim_file
            for row_no, row in enumerate(_read_jsonl_lenient(path, warnings), start=1):
                claims.append(row)
                audit_rows.append(
                    {
                        "merge_source": label,
                        "shard": shard_dir.name,
                        "file": claim_file,
                        "row_no": row_no,
                        "claim_id": row.get("claim_id", ""),
                        "source_chunk_id": row.get("source_chunk_id", ""),
                        "subject_taxon_id": row.get("subject_taxon_id", ""),
                        "subject_rank": row.get("subject_rank", ""),
                        "fact_domain": row.get("fact_domain", ""),
                        "predicate": row.get("predicate", ""),
                    }
                )
    return claims, audit_rows


def _duplicate_claim_rows(audit_rows: list[dict]) -> tuple[int, int, list[dict]]:
    by_claim_id: dict[str, list[dict]] = defaultdict(list)
    missing_claim_id_rows: list[dict] = []
    for row in audit_rows:
        claim_id = str(row.get("claim_id", "") or "").strip()
        if claim_id:
            by_claim_id[claim_id].append(row)
        else:
            missing_claim_id_rows.append(row)
    duplicate_rows: list[dict] = []
    duplicate_id_count = 0
    duplicate_row_excess = 0
    for claim_id, rows in sorted(by_claim_id.items()):
        if len(rows) <= 1:
            continue
        duplicate_id_count += 1
        duplicate_row_excess += len(rows) - 1
        for row in rows:
            duplicate_rows.append(row)
    duplicate_rows.extend({**row, "duplicate_reason": "missing_claim_id"} for row in missing_claim_id_rows)
    return duplicate_id_count, duplicate_row_excess, duplicate_rows


def _dedupe_claims_by_claim_id(sorted_claims: list[dict]) -> tuple[list[dict], int]:
    seen_claim_ids: set[str] = set()
    deduped: list[dict] = []
    missing_claim_id_count = 0
    for claim in sorted_claims:
        claim_id = str(claim.get("claim_id", "") or "").strip()
        if not claim_id:
            missing_claim_id_count += 1
            deduped.append(claim)
            continue
        if claim_id in seen_claim_ids:
            continue
        seen_claim_ids.add(claim_id)
        deduped.append(claim)
    return deduped, missing_claim_id_count


def _processed_unique_rows(old_by_id: dict[str, dict], repair_by_id: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    all_chunk_ids = sorted(set(old_by_id) | set(repair_by_id))
    for chunk_id in all_chunk_ids:
        old_row = old_by_id.get(chunk_id)
        repair_row = repair_by_id.get(chunk_id)
        row = repair_row or old_row or {}
        sources = []
        if old_row:
            sources.append("old")
        if repair_row:
            sources.append("repair")
        rows.append(
            {
                "chunk_id": chunk_id,
                "merge_sources": sources,
                "subject_rank": row.get("subject_rank", ""),
                "subject_taxon_id": row.get("subject_taxon_id", ""),
                "source_doc_id": row.get("source_doc_id", ""),
                "source_chapter": row.get("source_chapter", ""),
                "shard_index": row.get("shard_index", ""),
                "num_shards": row.get("num_shards", ""),
            }
        )
    return rows


def _build_taxon_index(sorted_claims: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row_index, claim in enumerate(sorted_claims):
        taxon_id = str(claim.get("subject_taxon_id", "") or "")
        if not taxon_id:
            taxon_id = "__missing_subject_taxon_id__"
        entry = index.setdefault(
            taxon_id,
            {
                "subject_taxon_id": taxon_id,
                "subject_rank": claim.get("subject_rank", ""),
                "claim_count": 0,
                "chunk_count": 0,
                "source_chunk_ids": [],
                "start_row": row_index,
                "end_row": row_index,
            },
        )
        entry["claim_count"] += 1
        entry["end_row"] = row_index
        chunk_id = str(claim.get("source_chunk_id", "") or "")
        if chunk_id and chunk_id not in entry["source_chunk_ids"]:
            entry["source_chunk_ids"].append(chunk_id)
            entry["chunk_count"] += 1
    return index


def _count_by_rank(claims: list[dict]) -> dict[str, int]:
    return dict(Counter(str(row.get("subject_rank", "") or "") for row in claims))


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


def _build_markdown(summary: dict) -> str:
    overview_rows = [
        ["Audit status", summary["audit_status"]],
        ["Old unique processed chunks", _fmt_int(summary["old_processed_unique_chunk_id_count"])],
        ["Repair unique processed chunks", _fmt_int(summary["repair_processed_unique_chunk_id_count"])],
        ["Merged unique processed chunks", _fmt_int(summary["merged_processed_unique_chunk_id_count"])],
        ["Old/repair processed overlap", _fmt_int(summary["old_repair_processed_intersection_count"])],
        ["Species claims", _fmt_int(summary["species_claim_total"])],
        ["Family claims", _fmt_int(summary["family_claim_total"])],
        ["Raw input claims", _fmt_int(summary["raw_input_claim_total"])],
        ["Official unique claims", _fmt_int(summary["all_claim_total"])],
        ["Duplicate claim ids", _fmt_int(summary["duplicate_claim_id_count"])],
        ["Duplicate claim row excess", _fmt_int(summary["duplicate_claim_row_excess"])],
        ["Duplicate claim rows dropped", _fmt_int(summary["duplicate_claim_rows_dropped"])],
        ["Warnings", _fmt_int(len(summary["warnings"]))],
    ]
    count_rows = [
        ["old processed records", _fmt_int(summary["old_processed_candidate_record_count"]), _fmt_int(summary["expected_old_unique_chunks"])],
        ["old processed unique", _fmt_int(summary["old_processed_unique_chunk_id_count"]), _fmt_int(summary["expected_old_unique_chunks"])],
        ["repair processed unique", _fmt_int(summary["repair_processed_unique_chunk_id_count"]), _fmt_int(summary["expected_repair_unique_chunks"])],
        ["merged processed unique", _fmt_int(summary["merged_processed_unique_chunk_id_count"]), _fmt_int(summary["expected_merged_unique_chunks"])],
    ]
    output_rows = [[key, value] for key, value in summary["output_files"].items()]
    failure_rows = [[item] for item in summary["audit_failures"]] or [["None"]]
    return "\n\n".join(
        [
            "# Step3 Global Claim Merge Audit",
            (
                "Old 16 shards and repair 16 shards are runtime partitions only. "
                "`claims_final_global` is the only official Claim-layer input for later global fact rebuild."
            ),
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## Expected Count Checks\n\n" + _markdown_table(["Check", "Observed", "Expected"], count_rows),
            "## Audit Failures\n\n" + _markdown_table(["Failure"], failure_rows),
            "## Outputs\n\n" + _markdown_table(["Output", "Path"], output_rows),
        ]
    )


def merge_claims(
    *,
    old_shards_dir: Path,
    repair_shards_dir: Path,
    out_dir: Path,
    expected_shards: int,
    expected_old_unique: int,
    expected_repair_unique: int,
    expected_merged_unique: int,
    allow_incomplete: bool,
) -> dict:
    warnings: list[str] = []
    audit_failures: list[str] = []
    old_shards = _discover_shard_dirs(old_shards_dir, expected_shards)
    repair_shards = _discover_shard_dirs(repair_shards_dir, expected_shards)

    old_processed_rows, old_processed_by_id = _read_processed(old_shards, "old", warnings)
    repair_processed_rows, repair_processed_by_id = _read_processed(repair_shards, "repair", warnings)
    old_claims, old_claim_audit_rows = _read_claims(old_shards, "old", warnings)
    repair_claims, repair_claim_audit_rows = _read_claims(repair_shards, "repair", warnings)

    old_ids = set(old_processed_by_id)
    repair_ids = set(repair_processed_by_id)
    intersection_ids = old_ids & repair_ids
    merged_ids = old_ids | repair_ids

    if len(old_ids) != expected_old_unique:
        audit_failures.append(f"old unique processed chunk count mismatch: observed={len(old_ids)} expected={expected_old_unique}")
    if len(repair_ids) != expected_repair_unique:
        audit_failures.append(
            f"repair unique processed chunk count mismatch: observed={len(repair_ids)} expected={expected_repair_unique}"
        )
    if len(merged_ids) != expected_merged_unique:
        audit_failures.append(
            f"merged unique processed chunk count mismatch: observed={len(merged_ids)} expected={expected_merged_unique}"
        )
    if intersection_ids:
        audit_failures.append(f"old and repair processed chunks overlap: {len(intersection_ids)}")

    raw_claims = old_claims + repair_claims
    raw_sorted_claims = sorted(raw_claims, key=_claim_sort_key)
    all_claims, missing_claim_id_count = _dedupe_claims_by_claim_id(raw_sorted_claims)
    species_claims = [row for row in all_claims if row.get("subject_rank") == "species"]
    family_claims = [row for row in all_claims if row.get("subject_rank") == "family"]
    duplicate_claim_id_count, duplicate_claim_row_excess, duplicate_claim_rows = _duplicate_claim_rows(
        old_claim_audit_rows + repair_claim_audit_rows
    )
    if missing_claim_id_count:
        audit_failures.append(f"claims missing claim_id detected: {missing_claim_id_count}")

    taxon_index = _build_taxon_index(all_claims)
    processed_unique_rows = _processed_unique_rows(old_processed_by_id, repair_processed_by_id)

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "species_claims": out_dir / "species_claims.jsonl",
        "family_claims": out_dir / "family_claims.jsonl",
        "all_claims": out_dir / "all_claims.jsonl",
        "processed_unique_chunks": out_dir / "processed_unique_chunks.jsonl",
        "taxon_claim_index": out_dir / "taxon_claim_index.json",
        "claim_merge_summary": out_dir / "claim_merge_summary.json",
        "claim_merge_audit": out_dir / "claim_merge_audit.md",
        "duplicate_claim_rows": out_dir / "duplicate_claim_rows.jsonl",
    }

    audit_status = "ok" if not audit_failures else "fail"
    should_write_claim_layer = audit_status == "ok" or allow_incomplete

    summary = {
        "audit_status": audit_status,
        "allow_incomplete": allow_incomplete,
        "old_shards_dir": str(old_shards_dir),
        "repair_shards_dir": str(repair_shards_dir),
        "out_dir": str(out_dir),
        "expected_shards": expected_shards,
        "expected_old_unique_chunks": expected_old_unique,
        "expected_repair_unique_chunks": expected_repair_unique,
        "expected_merged_unique_chunks": expected_merged_unique,
        "old_processed_candidate_record_count": len(old_processed_rows),
        "old_processed_unique_chunk_id_count": len(old_ids),
        "repair_processed_candidate_record_count": len(repair_processed_rows),
        "repair_processed_unique_chunk_id_count": len(repair_ids),
        "merged_processed_unique_chunk_id_count": len(merged_ids),
        "old_repair_processed_intersection_count": len(intersection_ids),
        "old_repair_processed_intersection_examples": sorted(intersection_ids)[:50],
        "old_claim_total": len(old_claims),
        "repair_claim_total": len(repair_claims),
        "raw_input_claim_total": len(raw_claims),
        "species_claim_total": len(species_claims),
        "family_claim_total": len(family_claims),
        "all_claim_total": len(all_claims),
        "claim_count_by_rank": _count_by_rank(all_claims),
        "taxon_count": len(taxon_index),
        "duplicate_claim_id_count": duplicate_claim_id_count,
        "duplicate_claim_row_excess": duplicate_claim_row_excess,
        "duplicate_claim_row_count": len(duplicate_claim_rows),
        "duplicate_claim_rows_dropped": len(raw_claims) - len(all_claims),
        "missing_claim_id_count": missing_claim_id_count,
        "duplicate_claim_examples": duplicate_claim_rows[:50],
        "formal_claim_layer_written": should_write_claim_layer,
        "audit_failures": audit_failures,
        "warnings": warnings,
        "output_files": {key: str(path) for key, path in paths.items()},
        "note": "claims_final_global is the only official Claim-layer input for later global fact rebuild.",
    }

    if should_write_claim_layer:
        write_jsonl(paths["species_claims"], species_claims)
        write_jsonl(paths["family_claims"], family_claims)
        write_jsonl(paths["all_claims"], all_claims)
        write_jsonl(paths["processed_unique_chunks"], processed_unique_rows)
        write_json(paths["taxon_claim_index"], taxon_index)
    write_jsonl(paths["duplicate_claim_rows"], duplicate_claim_rows)
    write_json(paths["claim_merge_summary"], summary)
    paths["claim_merge_audit"].write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge old and repair Step3 claims into a global claim layer.")
    parser.add_argument("--old-shards-dir", default="KG/intermediate/claims_shards_full")
    parser.add_argument("--repair-shards-dir", default="KG/intermediate/claims_repair_router_expansion")
    parser.add_argument("--out-dir", default="KG/intermediate/claims_final_global")
    parser.add_argument("--expected-shards", type=int, default=16)
    parser.add_argument("--expected-old-unique", type=int, default=244947)
    parser.add_argument("--expected-repair-unique", type=int, default=64422)
    parser.add_argument("--expected-merged-unique", type=int, default=309369)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()

    summary = merge_claims(
        old_shards_dir=_resolve_path(args.old_shards_dir),
        repair_shards_dir=_resolve_path(args.repair_shards_dir),
        out_dir=_resolve_path(args.out_dir),
        expected_shards=args.expected_shards,
        expected_old_unique=args.expected_old_unique,
        expected_repair_unique=args.expected_repair_unique,
        expected_merged_unique=args.expected_merged_unique,
        allow_incomplete=args.allow_incomplete,
    )
    print(f"[Step3][CLAIM_MERGE] status={summary['audit_status']}")
    print(f"[Step3][CLAIM_MERGE] summary={summary['output_files']['claim_merge_summary']}")
    print(f"[Step3][CLAIM_MERGE] audit={summary['output_files']['claim_merge_audit']}")
    print(
        "[Step3][CLAIM_MERGE] "
        f"old_unique={summary['old_processed_unique_chunk_id_count']} "
        f"repair_unique={summary['repair_processed_unique_chunk_id_count']} "
        f"merged_unique={summary['merged_processed_unique_chunk_id_count']} "
        f"claims={summary['all_claim_total']} duplicates={summary['duplicate_claim_id_count']}"
    )
    if summary["audit_status"] != "ok" and not summary["allow_incomplete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
