"""Audit how Step 3 source chunks become extraction candidates."""

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

from kg_v2.Step3_extraction.chapter_router import route_chapter
from kg_v2.Step3_extraction.loaders import load_step3_inputs
from kg_v2.Step3_extraction.run_extract_claims_and_facts import _collect_attached_chunks, _metadata_for_chunk
from kg_v2.utils.jsonl_utils import write_json


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
    return rows


def _chapter(value: Any) -> str:
    text = str(value or "").strip()
    return text or "Unknown"


def _safe_div(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, 6)


def _audit_record_type(
    *,
    record_type: str,
    raw_chunks: list[dict],
    links: list[dict],
    chunks_by_id: dict[str, dict],
    source_release: str,
    max_chunks: int,
    max_chars: int,
) -> dict:
    warnings: list[str] = []
    candidates = _collect_attached_chunks(
        links=links,
        chunks_by_id=chunks_by_id,
        subject_rank=record_type,
        source_release=source_release,
        max_chunks=max_chunks,
        max_chars=max_chars,
    )
    selected_ids = {str(metadata.get("source_chunk_id", "") or "") for metadata, _, _ in candidates}
    selected_count = len(candidates)
    raw_by_chapter: Counter = Counter()
    selected_by_chapter: Counter = Counter()
    excluded_by_chapter: Counter = Counter()
    filter_counts: Counter = Counter()
    excluded_examples: dict[str, list[str]] = defaultdict(list)

    for chunk in raw_chunks:
        raw_by_chapter[_chapter(chunk.get("source_chapter"))] += 1

    yielded = 0
    for link in links:
        chunk_id = str(link.get("chunk_id", "") or "")
        linked_chunk = chunks_by_id.get(chunk_id)
        chapter = _chapter((linked_chunk or link).get("source_chapter"))
        reason = ""
        if max_chunks == 0:
            reason = "max_chunks_zero"
        elif max_chunks > 0 and yielded >= max_chunks:
            reason = "max_chunks_limit"
        elif link.get("resolution_status") != "attached":
            reason = "resolution_status_not_attached"
        elif not linked_chunk:
            reason = "missing_source_chunk_for_link"
        else:
            metadata = _metadata_for_chunk(
                link=link,
                source_chunk=linked_chunk,
                subject_rank=record_type,
                source_release=source_release,
            )
            chapter = _chapter(metadata.get("source_chapter"))
            if not metadata["subject_taxon_id"]:
                reason = "empty_subject_taxon_id"
            elif not linked_chunk.get("raw_text", ""):
                reason = "empty_raw_text"
            else:
                route = route_chapter(metadata["source_chapter"], metadata.get("source_subchapter", ""))
                if route["skip"]:
                    reason = "route_skipped_chapter"

        if reason:
            filter_counts[reason] += 1
            excluded_by_chapter[chapter] += 1
            if len(excluded_examples[reason]) < 5:
                excluded_examples[reason].append(chunk_id)
            continue

        yielded += 1
        selected_by_chapter[chapter] += 1

    if yielded != selected_count:
        warnings.append(f"{record_type} candidate replay count mismatch: replay={yielded} collect={selected_count}")

    all_chapters = sorted(set(raw_by_chapter) | set(selected_by_chapter) | set(excluded_by_chapter))
    chapter_rows = [
        {
            "source_chapter": chapter,
            "raw_chunk_count": raw_by_chapter[chapter],
            "selected_candidate_count": selected_by_chapter[chapter],
            "excluded_chunk_count": excluded_by_chapter[chapter],
        }
        for chapter in all_chapters
    ]

    selected_unique_count = len(selected_ids)
    raw_count = len(raw_chunks)
    return {
        "record_type": record_type,
        "raw_chunk_count": raw_count,
        "selected_candidate_count": selected_count,
        "selected_unique_chunk_count": selected_unique_count,
        "duplicate_selected_candidate_count": max(selected_count - selected_unique_count, 0),
        "excluded_chunk_count": max(raw_count - selected_count, 0),
        "excluded_unique_raw_chunk_count": max(raw_count - selected_unique_count, 0),
        "excluded_candidate_record_count": sum(filter_counts.values()),
        "selection_rate": _safe_div(selected_count, raw_count),
        "filter_counts": [{"reason": reason, "count": count} for reason, count in filter_counts.most_common()],
        "excluded_examples": dict(excluded_examples),
        "by_source_chapter": chapter_rows,
        "warnings": warnings,
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


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _build_markdown(summary: dict) -> str:
    overview_rows = [
        ["Total raw species chunks", _fmt_int(summary["total_raw_species_chunks"])],
        ["Total raw family chunks", _fmt_int(summary["total_raw_family_chunks"])],
        ["Total raw chunks", _fmt_int(summary["total_raw_chunks"])],
        ["Total selected candidates", _fmt_int(summary["total_selected_candidates"])],
        ["Total selected unique chunks", _fmt_int(summary["total_selected_unique_chunks"])],
        ["Duplicate selected candidate records", _fmt_int(summary["duplicate_selected_candidate_count"])],
        ["Total excluded chunks", _fmt_int(summary["total_excluded_chunks"])],
        ["Overall selection rate", _fmt_pct(summary["overall_selection_rate"])],
    ]
    record_rows = [
        [
            item["record_type"],
            _fmt_int(item["raw_chunk_count"]),
            _fmt_int(item["selected_candidate_count"]),
            _fmt_int(item["selected_unique_chunk_count"]),
            _fmt_int(item["duplicate_selected_candidate_count"]),
            _fmt_int(item["excluded_chunk_count"]),
            _fmt_pct(item["selection_rate"]),
        ]
        for item in summary["by_record_type"]
    ]
    filter_rows = [
        [row["record_type"], row["reason"], _fmt_int(row["count"])]
        for row in summary["filter_counts"]
    ]
    chapter_rows = [
        [
            row["record_type"],
            row["source_chapter"],
            _fmt_int(row["raw_chunk_count"]),
            _fmt_int(row["selected_candidate_count"]),
            _fmt_int(row["excluded_chunk_count"]),
        ]
        for row in summary["by_source_chapter"]
    ]
    warning_rows = [[warning] for warning in summary["warnings"]] or [["None"]]
    return "\n\n".join(
        [
            "# Step3 Candidate Selection Audit",
            "This audit is read-only. Candidate construction reuses Step3 extraction code and does not call the LLM.",
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## By Record Type\n\n"
            + _markdown_table(
                [
                    "Record type",
                    "Raw chunks",
                    "Selected candidates",
                    "Selected unique chunks",
                    "Duplicate selected candidates",
                    "Excluded chunks",
                    "Selection rate",
                ],
                record_rows,
            ),
            "## Explicit Filter Counts\n\n" + _markdown_table(["Record type", "Filter / reason", "Count"], filter_rows),
            "## By Source Chapter\n\n" + _markdown_table(["Record type", "Source chapter", "Raw chunks", "Selected candidates", "Excluded chunks"], chapter_rows),
            "## Warnings\n\n" + _markdown_table(["Warning"], warning_rows),
        ]
    )


def audit_candidate_selection(
    *,
    intermediate_dir: Path,
    attachments_dir: Path,
    taxonomy_dir: Path,
    source_release: str,
    max_species_chunks: int,
    max_family_chunks: int,
    max_chars_per_chunk: int,
    out_dir: Path,
) -> dict:
    warnings: list[str] = []
    inputs = load_step3_inputs(
        intermediate_dir=intermediate_dir,
        attachments_dir=attachments_dir,
        taxonomy_dir=taxonomy_dir,
    )
    species_chunks = _read_jsonl_lenient(intermediate_dir / "species_chunks.jsonl", warnings)
    family_chunks = _read_jsonl_lenient(intermediate_dir / "family_chunks.jsonl", warnings)

    species_audit = _audit_record_type(
        record_type="species",
        raw_chunks=species_chunks,
        links=inputs["species_chunk_links"],
        chunks_by_id=inputs["species_chunks_by_id"],
        source_release=source_release,
        max_chunks=max_species_chunks,
        max_chars=max_chars_per_chunk,
    )
    family_audit = _audit_record_type(
        record_type="family",
        raw_chunks=family_chunks,
        links=inputs["family_chunk_links"],
        chunks_by_id=inputs["family_chunks_by_id"],
        source_release=source_release,
        max_chunks=max_family_chunks,
        max_chars=max_chars_per_chunk,
    )

    record_audits = [species_audit, family_audit]
    total_raw = sum(item["raw_chunk_count"] for item in record_audits)
    total_selected = sum(item["selected_candidate_count"] for item in record_audits)
    total_selected_unique = sum(item["selected_unique_chunk_count"] for item in record_audits)
    duplicate_selected = sum(item["duplicate_selected_candidate_count"] for item in record_audits)
    total_excluded = max(total_raw - total_selected, 0)
    total_excluded_unique_raw_chunks = max(total_raw - total_selected_unique, 0)

    filter_rows: list[dict] = []
    chapter_rows: list[dict] = []
    for item in record_audits:
        for row in item["filter_counts"]:
            filter_rows.append({"record_type": item["record_type"], **row})
        for row in item["by_source_chapter"]:
            chapter_rows.append({"record_type": item["record_type"], **row})
        warnings.extend(item["warnings"])

    summary = {
        "intermediate_dir": str(intermediate_dir),
        "attachments_dir": str(attachments_dir),
        "taxonomy_dir": str(taxonomy_dir),
        "source_release": source_release,
        "max_species_chunks": max_species_chunks,
        "max_family_chunks": max_family_chunks,
        "max_chars_per_chunk": max_chars_per_chunk,
        "candidate_logic": "run_extract_claims_and_facts._collect_attached_chunks",
        "total_raw_species_chunks": species_audit["raw_chunk_count"],
        "total_raw_family_chunks": family_audit["raw_chunk_count"],
        "total_raw_chunks": total_raw,
        "total_selected_candidates": total_selected,
        "total_selected_unique_chunks": total_selected_unique,
        "duplicate_selected_candidate_count": duplicate_selected,
        "total_excluded_chunks": total_excluded,
        "total_excluded_unique_raw_chunks": total_excluded_unique_raw_chunks,
        "overall_selection_rate": _safe_div(total_selected, total_raw),
        "by_record_type": record_audits,
        "filter_counts": filter_rows,
        "by_source_chapter": chapter_rows,
        "warnings": warnings,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "step3_candidate_selection_audit.json"
    md_path = out_dir / "step3_candidate_selection_audit.md"
    summary["output_files"] = {
        "json": str(json_path),
        "markdown": str(md_path),
    }
    write_json(json_path, summary)
    md_path.write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Step3 candidate selection without modifying data or calling the LLM.")
    parser.add_argument("--intermediate-dir", default="outputs/intermediate")
    parser.add_argument("--attachments-dir", default="outputs/intermediate/attachments")
    parser.add_argument("--taxonomy-dir", default="outputs/intermediate/taxonomy")
    parser.add_argument("--source-release", default="bow_2025_snapshot")
    parser.add_argument("--max-species-chunks", type=int, default=-1)
    parser.add_argument("--max-family-chunks", type=int, default=-1)
    parser.add_argument("--max-chars-per-chunk", type=int, default=4500)
    parser.add_argument("--out-dir", default="../KG/reports")
    args = parser.parse_args()

    summary = audit_candidate_selection(
        intermediate_dir=_resolve_under_kg(args.intermediate_dir),
        attachments_dir=_resolve_under_kg(args.attachments_dir),
        taxonomy_dir=_resolve_under_kg(args.taxonomy_dir),
        source_release=args.source_release,
        max_species_chunks=args.max_species_chunks,
        max_family_chunks=args.max_family_chunks,
        max_chars_per_chunk=args.max_chars_per_chunk,
        out_dir=_resolve_under_kg(args.out_dir),
    )
    print(f"[Step3][CANDIDATE_AUDIT] json={summary['output_files']['json']}")
    print(f"[Step3][CANDIDATE_AUDIT] markdown={summary['output_files']['markdown']}")
    print(
        "[Step3][CANDIDATE_AUDIT] "
        f"raw={summary['total_raw_chunks']} selected={summary['total_selected_candidates']} "
        f"unique_selected={summary['total_selected_unique_chunks']} excluded={summary['total_excluded_chunks']} "
        f"selection_rate={summary['overall_selection_rate']:.2%} "
        f"warnings={len(summary['warnings'])}"
    )


if __name__ == "__main__":
    main()
