"""Plan a unique-chunk Step 3 repair run without calling the LLM."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
KG_ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step3_extraction.loaders import load_step3_inputs
from kg_v2.Step3_extraction.run_extract_claims_and_facts import _collect_attached_chunks
from kg_v2.utils.jsonl_utils import write_json, write_jsonl


def _resolve_under_kg(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
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


def _chunk_id(value: Any) -> str:
    return str(value or "").strip()


def _chapter(value: Any) -> str:
    text = str(value or "").strip()
    return text or "Unknown"


def _candidate_sort_key(row: tuple[dict, dict, str]) -> tuple[str, str, str]:
    metadata = row[0]
    return (
        str(metadata.get("subject_rank", "") or ""),
        str(metadata.get("source_chunk_id", "") or ""),
        str(metadata.get("source_doc_id", "") or ""),
    )


def _collect_new_candidates(inputs: dict[str, object], *, source_release: str, max_chars: int) -> list[tuple[dict, dict, str]]:
    species_candidates = _collect_attached_chunks(
        links=inputs["species_chunk_links"],
        chunks_by_id=inputs["species_chunks_by_id"],
        subject_rank="species",
        source_release=source_release,
        max_chunks=-1,
        max_chars=max_chars,
    )
    family_candidates = _collect_attached_chunks(
        links=inputs["family_chunk_links"],
        chunks_by_id=inputs["family_chunks_by_id"],
        subject_rank="family",
        source_release=source_release,
        max_chunks=-1,
        max_chars=max_chars,
    )
    return sorted(species_candidates + family_candidates, key=_candidate_sort_key)


def _read_old_processed(shards_dir: Path, expected_shards: int, warnings: list[str]) -> tuple[list[dict], dict[str, dict]]:
    rows: list[dict] = []
    by_chunk_id: dict[str, dict] = {}
    for shard_index in range(expected_shards):
        path = shards_dir / f"shard_{shard_index:02d}" / "processed_chunks.jsonl"
        shard_rows = _read_jsonl_lenient(path, warnings)
        rows.extend(shard_rows)
        for row in shard_rows:
            chunk_id = _chunk_id(row.get("chunk_id"))
            if chunk_id and chunk_id not in by_chunk_id:
                by_chunk_id[chunk_id] = row
    return rows, by_chunk_id


def _count_by_chunk_id(rows: list[dict], field: str = "chunk_id") -> Counter:
    counter: Counter = Counter()
    for row in rows:
        chunk_id = _chunk_id(row.get(field))
        if chunk_id:
            counter[chunk_id] += 1
    return counter


def _unique_candidates(candidates: list[tuple[dict, dict, str]]) -> dict[str, tuple[dict, dict, str]]:
    unique: dict[str, tuple[dict, dict, str]] = {}
    for candidate in candidates:
        chunk_id = _chunk_id(candidate[0].get("source_chunk_id"))
        if chunk_id and chunk_id not in unique:
            unique[chunk_id] = candidate
    return unique


def _distribution_for_candidates(candidates_by_id: dict[str, tuple[dict, dict, str]], chunk_ids: set[str]) -> dict:
    record_type_counts: Counter = Counter()
    chapter_counts: Counter = Counter()
    domain_counts: Counter = Counter()
    route_counts: Counter = Counter()
    max_claim_counts: Counter = Counter()
    for chunk_id in sorted(chunk_ids):
        candidate = candidates_by_id.get(chunk_id)
        if not candidate:
            continue
        metadata, routing, _ = candidate
        record_type_counts[str(metadata.get("subject_rank", "") or "unknown")] += 1
        chapter_counts[_chapter(metadata.get("source_chapter"))] += 1
        domains = tuple(routing.get("allowed_fact_domains", []) or [])
        route_counts[" + ".join(domains) if domains else "none"] += 1
        max_claim_counts[str(routing.get("max_claims", ""))] += 1
        for domain in domains:
            domain_counts[str(domain)] += 1
    return {
        "record_type": [{"value": key, "count": count} for key, count in record_type_counts.most_common()],
        "source_chapter": [{"value": key, "count": count} for key, count in chapter_counts.most_common()],
        "fact_domain": [{"value": key, "count": count} for key, count in domain_counts.most_common()],
        "route_domain_set": [{"value": key, "count": count} for key, count in route_counts.most_common()],
        "max_claims": [{"value": key, "count": count} for key, count in max_claim_counts.most_common()],
    }


def _duplicate_source_class(raw_count: int, link_count: int) -> str:
    raw_dup = raw_count > 1
    link_dup = link_count > 1
    if raw_dup and link_dup:
        return "source_chunk_and_taxonomy_link_duplicate"
    if link_dup:
        return "taxonomy_link_duplicate"
    if raw_dup:
        return "source_chunk_duplicate"
    return "candidate_duplicate_without_raw_or_link_duplicate"


def _duplicate_audit(
    *,
    candidates: list[tuple[dict, dict, str]],
    species_chunks: list[dict],
    family_chunks: list[dict],
    species_links: list[dict],
    family_links: list[dict],
) -> dict:
    selected_counts: Counter = Counter(_chunk_id(metadata.get("source_chunk_id")) for metadata, _, _ in candidates)
    selected_counts.pop("", None)
    raw_counts = _count_by_chunk_id(species_chunks + family_chunks)
    link_counts = _count_by_chunk_id(species_links + family_links)
    duplicate_items = [(chunk_id, count) for chunk_id, count in selected_counts.items() if count > 1]
    source_counts: Counter = Counter()
    examples: list[dict] = []
    for chunk_id, selected_count in sorted(duplicate_items, key=lambda item: (-item[1], item[0])):
        source = _duplicate_source_class(raw_counts.get(chunk_id, 0), link_counts.get(chunk_id, 0))
        source_counts[source] += 1
        if len(examples) < 20:
            examples.append(
                {
                    "source_chunk_id": chunk_id,
                    "selected_record_count": selected_count,
                    "raw_chunk_row_count": raw_counts.get(chunk_id, 0),
                    "taxonomy_link_record_count": link_counts.get(chunk_id, 0),
                    "source_class": source,
                }
            )
    return {
        "duplicate_chunk_id_count": len(duplicate_items),
        "duplicate_record_excess": sum(count - 1 for _, count in duplicate_items),
        "source_class_counts": [{"source_class": key, "count": count} for key, count in source_counts.most_common()],
        "examples": examples,
    }


def _manifest_row(candidate: tuple[dict, dict, str]) -> dict:
    metadata, routing, chunk_text = candidate
    return {
        "source_chunk_id": metadata.get("source_chunk_id", ""),
        "record_type": metadata.get("subject_rank", ""),
        "subject_rank": metadata.get("subject_rank", ""),
        "subject_taxon_id": metadata.get("subject_taxon_id", ""),
        "source_doc_id": metadata.get("source_doc_id", ""),
        "source_chapter": metadata.get("source_chapter", ""),
        "source_subchapter": metadata.get("source_subchapter", ""),
        "common_name": metadata.get("common_name", ""),
        "scientific_name": metadata.get("scientific_name", ""),
        "source_db": metadata.get("source_db", ""),
        "source_release": metadata.get("source_release", ""),
        "allowed_fact_domains": routing.get("allowed_fact_domains", []),
        "allowed_predicates": routing.get("allowed_predicates", []),
        "max_claims": routing.get("max_claims", 0),
        "chunk_text": chunk_text,
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


def _build_markdown(summary: dict) -> str:
    overview_rows = [
        ["Old processed candidate records", _fmt_int(summary["old_processed_candidate_record_count"])],
        ["Old processed unique chunk ids", _fmt_int(summary["old_processed_unique_chunk_id_count"])],
        ["New selected candidate records", _fmt_int(summary["new_selected_candidate_record_count"])],
        ["New selected unique chunk ids", _fmt_int(summary["new_selected_unique_chunk_id_count"])],
        ["Already covered unique chunk ids", _fmt_int(summary["already_covered_unique_chunk_count"])],
        ["Repair unique chunk ids", _fmt_int(summary["repair_unique_chunk_count"])],
        ["No longer selected old chunk ids", _fmt_int(summary["no_longer_selected_old_chunk_count"])],
        ["New selected duplicate chunk ids", _fmt_int(summary["duplicate_audit"]["duplicate_chunk_id_count"])],
        ["New selected duplicate record excess", _fmt_int(summary["duplicate_audit"]["duplicate_record_excess"])],
    ]
    record_rows = [[item["value"], _fmt_int(item["count"])] for item in summary["repair_distribution"]["record_type"]]
    chapter_rows = [[item["value"], _fmt_int(item["count"])] for item in summary["repair_distribution"]["source_chapter"]]
    domain_rows = [[item["value"], _fmt_int(item["count"])] for item in summary["repair_distribution"]["fact_domain"]]
    duplicate_source_rows = [
        [item["source_class"], _fmt_int(item["count"])] for item in summary["duplicate_audit"]["source_class_counts"]
    ]
    output_rows = [[key, value] for key, value in summary["output_files"].items()]
    return "\n\n".join(
        [
            "# Step3 Repair Plan",
            (
                "This report is a planning artifact only. It does not call the LLM and does not modify existing "
                "Step3 shard outputs. Repair runs should iterate `repair_unique_chunks.jsonl`, not raw candidate records."
            ),
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## Repair By Record Type\n\n" + _markdown_table(["Record type", "Unique chunks"], record_rows),
            "## Repair By Source Chapter\n\n" + _markdown_table(["Source chapter", "Unique chunks"], chapter_rows),
            "## Repair By Fact Domain\n\n" + _markdown_table(["Fact domain", "Route hits"], domain_rows),
            "## Duplicate Candidate Source Audit\n\n" + _markdown_table(["Source class", "Duplicate chunk ids"], duplicate_source_rows),
            "## Outputs\n\n" + _markdown_table(["Output", "Path"], output_rows),
        ]
    )


def build_repair_plan(
    *,
    intermediate_dir: Path,
    attachments_dir: Path,
    taxonomy_dir: Path,
    old_shards_dir: Path,
    repair_plan_dir: Path,
    reports_dir: Path,
    source_release: str,
    max_chars_per_chunk: int,
    expected_shards: int,
) -> dict:
    warnings: list[str] = []
    inputs = load_step3_inputs(
        intermediate_dir=intermediate_dir,
        attachments_dir=attachments_dir,
        taxonomy_dir=taxonomy_dir,
    )
    species_chunks = _read_jsonl_lenient(intermediate_dir / "species_chunks.jsonl", warnings)
    family_chunks = _read_jsonl_lenient(intermediate_dir / "family_chunks.jsonl", warnings)
    species_links = list(inputs["species_chunk_links"])
    family_links = list(inputs["family_chunk_links"])

    old_rows, old_by_chunk_id = _read_old_processed(old_shards_dir, expected_shards, warnings)
    old_unique_ids = set(old_by_chunk_id)

    new_candidates = _collect_new_candidates(inputs, source_release=source_release, max_chars=max_chars_per_chunk)
    new_by_chunk_id = _unique_candidates(new_candidates)
    new_unique_ids = set(new_by_chunk_id)

    repair_ids = new_unique_ids - old_unique_ids
    already_covered_ids = new_unique_ids & old_unique_ids
    no_longer_selected_old_ids = old_unique_ids - new_unique_ids

    repair_distribution = _distribution_for_candidates(new_by_chunk_id, repair_ids)
    already_covered_distribution = _distribution_for_candidates(new_by_chunk_id, already_covered_ids)
    duplicate_audit = _duplicate_audit(
        candidates=new_candidates,
        species_chunks=species_chunks,
        family_chunks=family_chunks,
        species_links=species_links,
        family_links=family_links,
    )

    manifest_rows = [_manifest_row(new_by_chunk_id[chunk_id]) for chunk_id in sorted(repair_ids)]

    repair_plan_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = repair_plan_dir / "repair_unique_chunks.jsonl"
    summary_json_path = reports_dir / "step3_repair_plan.json"
    summary_md_path = reports_dir / "step3_repair_plan.md"

    summary = {
        "intermediate_dir": str(intermediate_dir),
        "attachments_dir": str(attachments_dir),
        "taxonomy_dir": str(taxonomy_dir),
        "old_shards_dir": str(old_shards_dir),
        "source_release": source_release,
        "max_chars_per_chunk": max_chars_per_chunk,
        "expected_shards": expected_shards,
        "old_processed_candidate_record_count": len(old_rows),
        "old_processed_unique_chunk_id_count": len(old_unique_ids),
        "old_processed_duplicate_record_excess": len(old_rows) - len(old_unique_ids),
        "new_selected_candidate_record_count": len(new_candidates),
        "new_selected_unique_chunk_id_count": len(new_unique_ids),
        "new_selected_duplicate_record_excess": len(new_candidates) - len(new_unique_ids),
        "repair_unique_chunk_count": len(repair_ids),
        "already_covered_unique_chunk_count": len(already_covered_ids),
        "no_longer_selected_old_chunk_count": len(no_longer_selected_old_ids),
        "repair_distribution": repair_distribution,
        "already_covered_distribution": already_covered_distribution,
        "duplicate_audit": duplicate_audit,
        "no_longer_selected_old_chunk_id_examples": sorted(no_longer_selected_old_ids)[:50],
        "repair_chunk_id_examples": sorted(repair_ids)[:50],
        "warnings": warnings,
        "output_files": {
            "repair_manifest": str(manifest_path),
            "summary_json": str(summary_json_path),
            "summary_markdown": str(summary_md_path),
        },
        "note": "Future repair LLM runs must use repair_unique_chunks.jsonl as input instead of iterating selected candidate records.",
    }

    write_jsonl(manifest_path, manifest_rows)
    write_json(summary_json_path, summary)
    summary_md_path.write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan unique chunk repair work for Step3 without calling the LLM.")
    parser.add_argument("--intermediate-dir", default="outputs/intermediate")
    parser.add_argument("--attachments-dir", default="outputs/intermediate/attachments")
    parser.add_argument("--taxonomy-dir", default="outputs/intermediate/taxonomy")
    parser.add_argument("--old-shards-dir", default="../KG/intermediate/claims_shards_full")
    parser.add_argument("--repair-plan-dir", default="../KG/intermediate/step3_repair_plan")
    parser.add_argument("--reports-dir", default="../KG/reports")
    parser.add_argument("--source-release", default="bow_2025_snapshot")
    parser.add_argument("--max-chars-per-chunk", type=int, default=4500)
    parser.add_argument("--expected-shards", type=int, default=16)
    args = parser.parse_args()

    summary = build_repair_plan(
        intermediate_dir=_resolve_under_kg(args.intermediate_dir),
        attachments_dir=_resolve_under_kg(args.attachments_dir),
        taxonomy_dir=_resolve_under_kg(args.taxonomy_dir),
        old_shards_dir=_resolve_under_kg(args.old_shards_dir),
        repair_plan_dir=_resolve_under_kg(args.repair_plan_dir),
        reports_dir=_resolve_under_kg(args.reports_dir),
        source_release=args.source_release,
        max_chars_per_chunk=args.max_chars_per_chunk,
        expected_shards=args.expected_shards,
    )
    print(f"[Step3][REPAIR_PLAN] manifest={summary['output_files']['repair_manifest']}")
    print(f"[Step3][REPAIR_PLAN] summary_json={summary['output_files']['summary_json']}")
    print(f"[Step3][REPAIR_PLAN] summary_markdown={summary['output_files']['summary_markdown']}")
    print(
        "[Step3][REPAIR_PLAN] "
        f"old_processed_records={summary['old_processed_candidate_record_count']} "
        f"old_unique={summary['old_processed_unique_chunk_id_count']} "
        f"new_records={summary['new_selected_candidate_record_count']} "
        f"new_unique={summary['new_selected_unique_chunk_id_count']} "
        f"repair_unique={summary['repair_unique_chunk_count']} "
        f"duplicate_excess={summary['new_selected_duplicate_record_excess']} "
        f"warnings={len(summary['warnings'])}"
    )


if __name__ == "__main__":
    main()
