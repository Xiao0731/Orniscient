"""Verify whether max_additional_claims=12 is wide enough for pilot cap-hit chunks.

This is a read-only Step 3 audit helper. It re-reviews only the pilot chunks that
hit the temporary max_additional_claims=6 cap and writes a compact report under
KG/reports. It does not modify claims_final_global or rebuild facts.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step3_extraction.review_claim_cap_chunks import _compact_text, _existing_claims_for_prompt
from kg_v2.Step3_extraction.run_claim_cap_supplement_full import (
    _load_chunk_texts,
    _load_claims_by_chunk,
    _review_chunk,
    _safe_div,
)
from kg_v2.utils.jsonl_utils import write_json
from kg_v2.utils.llm_utils import load_openai_compatible_config


TARGET_CHAPTER_BUCKETS = [
    "Introduction",
    "Habitat",
    "Identification",
    "MortalityPredationParasites",
    "DietAndForaging",
    "Other",
]


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


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing required JSON report: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def _load_cache(cache_path: Path) -> dict[str, dict]:
    if not cache_path.exists():
        return {}
    cached: dict[str, dict] = {}
    with cache_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid cache JSONL row in {cache_path}: line={line_no} error={exc.msg}") from exc
            chunk_id = str(row.get("source_chunk_id", "") or "").strip()
            if chunk_id:
                cached[chunk_id] = row
    return cached


def _pilot_cap(pilot_report: dict) -> int:
    prompt = pilot_report.get("review_prompt", {})
    cap = prompt.get("temporary_additional_claim_cap", 6) if isinstance(prompt, dict) else 6
    try:
        return int(cap)
    except Exception:
        return 6


def _load_pilot_cap_hit_rows(pilot_report_path: Path) -> tuple[list[dict], int]:
    pilot_report = _read_json(pilot_report_path)
    pilot_cap = _pilot_cap(pilot_report)
    reviews = pilot_report.get("reviews", [])
    if not isinstance(reviews, list):
        raise ValueError(f"Expected reviews array in {pilot_report_path}")

    rows: list[dict] = []
    seen: set[str] = set()
    for review in reviews:
        if not isinstance(review, dict):
            continue
        chunk_id = str(review.get("source_chunk_id", "") or "").strip()
        if not chunk_id or chunk_id in seen:
            continue
        if review.get("review_status") != "ok":
            continue
        try:
            additional_count = int(review.get("additional_claim_count", 0))
        except Exception:
            additional_count = 0
        if additional_count != pilot_cap:
            continue
        seen.add(chunk_id)
        rows.append(
            {
                "source_chunk_id": chunk_id,
                "stratum": review.get("stratum", ""),
                "source_chapter": review.get("source_chapter", ""),
                "source_subchapter": review.get("source_subchapter", ""),
                "subject_rank": review.get("subject_rank", ""),
                "subject_taxon_id": review.get("subject_taxon_id", ""),
                "source_doc_id": review.get("source_doc_id", ""),
                "claim_count": review.get("claim_count", 0),
                "max_claims_current_policy": review.get("max_claims_current_policy", 0),
            }
        )
    return sorted(rows, key=lambda row: (str(row.get("stratum", "")), str(row.get("source_chunk_id", "")))), pilot_cap


def _chapter_bucket(row: dict) -> str:
    chapter = str(row.get("source_chapter", "") or "")
    if chapter in TARGET_CHAPTER_BUCKETS[:-1]:
        return chapter
    return "Other"


def _claim_summary(claims: list[dict], *, max_items: int = 5) -> str:
    parts = []
    for claim in claims[:max_items]:
        predicate = str(claim.get("predicate", "") or "")
        obj = str(claim.get("object_text", "") or claim.get("object_canonical_name", "") or "")
        if predicate or obj:
            parts.append(f"{predicate}: {obj}".strip(": "))
    if len(claims) > max_items:
        parts.append(f"... +{len(claims) - max_items} more")
    return "; ".join(parts)


def _still_possible_missing(row: dict, raw_text: str, *, max_additional_claims: int) -> dict:
    additional_count = int(row.get("additional_claim_count", 0) or 0)
    preview = _compact_text(raw_text, max_chars=900)
    if additional_count >= max_additional_claims:
        return {
            "possible": True,
            "reason": (
                "Hit the max=12 verification cap; from the preview alone this remains a recall-risk chunk, "
                "so further omissions cannot be ruled out without a wider cap or manual review."
            ),
            "raw_text_preview": preview,
        }
    return {
        "possible": False,
        "reason": "Did not hit max=12 in this verification pass.",
        "raw_text_preview": preview,
    }


def _aggregate(results: list[dict], *, max_additional_claims: int) -> dict:
    ok = [row for row in results if row.get("review_status") == "ok"]
    positive = [row for row in ok if int(row.get("additional_claim_count", 0) or 0) > 0]
    cap_hit = [row for row in ok if int(row.get("additional_claim_count", 0) or 0) >= max_additional_claims]
    total_additional = sum(int(row.get("additional_claim_count", 0) or 0) for row in ok)
    near_dup = sum(int(row.get("duplicate_assessment", {}).get("near_duplicate_count", 0) or 0) for row in ok)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in results:
        grouped[_chapter_bucket(row)].append(row)

    by_chapter_bucket: dict[str, dict] = {}
    for bucket in TARGET_CHAPTER_BUCKETS:
        rows = grouped.get(bucket, [])
        ok_rows = [row for row in rows if row.get("review_status") == "ok"]
        hit_rows = [row for row in ok_rows if int(row.get("additional_claim_count", 0) or 0) >= max_additional_claims]
        by_chapter_bucket[bucket] = {
            "sampled_chunk_count": len(rows),
            "ok_review_count": len(ok_rows),
            "max12_cap_hit_chunk_count": len(hit_rows),
            "max12_cap_hit_ratio": _safe_div(len(hit_rows), len(ok_rows)),
            "total_additional_claims": sum(int(row.get("additional_claim_count", 0) or 0) for row in ok_rows),
        }

    return {
        "sampled_chunk_count": len(results),
        "ok_review_count": len(ok),
        "error_count": len(results) - len(ok),
        "chunks_with_additional_claims": len(positive),
        "positive_chunk_ratio": _safe_div(len(positive), len(ok)),
        "total_additional_claims": total_additional,
        "avg_additional_claims_per_ok_chunk": _safe_div(total_additional, len(ok)),
        "avg_additional_claims_per_positive_chunk": _safe_div(total_additional, len(positive)),
        "max12_cap_hit_chunk_count": len(cap_hit),
        "max12_cap_hit_ratio": _safe_div(len(cap_hit), len(ok)),
        "near_duplicate_additional_claims": near_dup,
        "near_duplicate_ratio": _safe_div(near_dup, total_additional),
        "by_chapter_bucket": by_chapter_bucket,
        "by_source_chapter": dict(sorted(Counter(str(row.get("source_chapter", "") or "") for row in ok).items())),
    }


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
    overview = summary["aggregate"]
    overview_rows = [
        ["Pilot cap-hit chunks re-reviewed", _fmt_int(overview["sampled_chunk_count"])],
        ["OK reviews", _fmt_int(overview["ok_review_count"])],
        ["Errors", _fmt_int(overview["error_count"])],
        ["Chunks with additional claims", _fmt_int(overview["chunks_with_additional_claims"])],
        ["Total additional claims", _fmt_int(overview["total_additional_claims"])],
        ["Max=12 cap-hit chunks", _fmt_int(overview["max12_cap_hit_chunk_count"])],
        ["Max=12 cap-hit ratio", _fmt_float(overview["max12_cap_hit_ratio"])],
        ["Near-duplicate additional claims", _fmt_int(overview["near_duplicate_additional_claims"])],
        ["Near-duplicate ratio", _fmt_float(overview["near_duplicate_ratio"])],
    ]
    bucket_rows = [
        [
            bucket,
            _fmt_int(stats["sampled_chunk_count"]),
            _fmt_int(stats["ok_review_count"]),
            _fmt_int(stats["max12_cap_hit_chunk_count"]),
            _fmt_float(stats["max12_cap_hit_ratio"]),
            _fmt_int(stats["total_additional_claims"]),
        ]
        for bucket, stats in overview["by_chapter_bucket"].items()
    ]
    hit_rows = [
        [
            row.get("source_chunk_id", ""),
            row.get("source_chapter", ""),
            row.get("existing_claims_summary", ""),
            _fmt_int(int(row.get("additional_claim_count", 0) or 0)),
            "yes" if row.get("still_possible_missing_from_preview", {}).get("possible") else "no",
            row.get("still_possible_missing_from_preview", {}).get("reason", ""),
            row.get("still_possible_missing_from_preview", {}).get("raw_text_preview", ""),
        ]
        for row in summary["max12_cap_hit_chunks"]
    ]
    if not hit_rows:
        hit_section = "No chunk hit max=12 in this verification pass."
    else:
        hit_section = _markdown_table(
            [
                "Chunk ID",
                "Chapter",
                "Existing claims summary",
                "Additional",
                "Possible still missing",
                "Reason",
                "Raw text preview",
            ],
            hit_rows,
        )
    return "\n\n".join(
        [
            "# Supplement Max=12 Verification",
            (
                "Read-only verification on the 55 pilot chunks that exactly hit the temporary "
                "max_additional_claims=6 review cap. Formal Claim and Fact artifacts were not modified."
            ),
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## Max=12 Cap Hit By Chapter Bucket\n\n"
            + _markdown_table(
                ["Bucket", "Sampled", "OK", "Max=12 hits", "Hit ratio", "Additional claims"],
                bucket_rows,
            ),
            "## All Max=12 Cap-Hit Chunks\n\n" + hit_section,
            "## Run Command\n\n```powershell\n" + summary["run_command"] + "\n```",
            "## Safety Note\n\n"
            + summary["note"],
        ]
    )


def verify_supplement_max12(
    *,
    pilot_report_path: Path,
    claims_dir: Path,
    species_chunks_path: Path,
    family_chunks_path: Path,
    out_json: Path,
    out_md: Path,
    cache_path: Path,
    max_chars: int,
    max_additional_claims: int,
    limit: int,
    dry_run: bool,
) -> dict:
    rows, pilot_cap = _load_pilot_cap_hit_rows(pilot_report_path)
    if limit > 0:
        rows = rows[:limit]
    claims_by_chunk = _load_claims_by_chunk(claims_dir)
    chunk_texts = _load_chunk_texts(
        {row["source_chunk_id"] for row in rows},
        [species_chunks_path, family_chunks_path],
    )

    config = None
    if not dry_run:
        config = load_openai_compatible_config()
        if config is None:
            raise RuntimeError("Missing OpenAI-compatible LLM config. Use --dry-run to verify wiring.")
        config = replace(config, temperature=0.0)

    results: list[dict] = []
    cached = _load_cache(cache_path)
    for index, row in enumerate(rows, start=1):
        chunk_id = row["source_chunk_id"]
        chunk = chunk_texts.get(chunk_id, {})
        raw_text = str(chunk.get("raw_text") or chunk.get("chunk_text") or chunk.get("text") or "")
        existing_claims = claims_by_chunk.get(chunk_id, [])
        cached_row = cached.get(chunk_id)
        if cached_row and not dry_run:
            review = cached_row
            print(
                "[Step3][SUPPLEMENT_MAX12_VERIFY] "
                f"cached {index}/{len(rows)} chunk={chunk_id} "
                f"status={review.get('review_status')} additional={review.get('additional_claim_count', 0)}",
                flush=True,
            )
        elif dry_run:
            review = {
                **row,
                "review_status": "dry_run",
                "additional_claim_count": 0,
                "additional_claims": [],
                "duplicate_assessment": {"near_duplicate_count": 0, "near_duplicate_ratio": 0.0},
                "warnings": ["dry_run_no_llm_review"],
            }
        elif not raw_text:
            review = {
                **row,
                "review_status": "error",
                "additional_claim_count": 0,
                "additional_claims": [],
                "duplicate_assessment": {"near_duplicate_count": 0, "near_duplicate_ratio": 0.0},
                "warnings": [],
                "error_message": "raw_text_not_found",
            }
        else:
            review = _review_chunk(
                row,
                raw_text,
                existing_claims,
                config=config,
                max_chars=max_chars,
                max_additional_claims=max_additional_claims,
            )
            _append_jsonl(cache_path, review)
        review["existing_claim_count"] = len(existing_claims)
        review["existing_claims_summary"] = _claim_summary(_existing_claims_for_prompt(existing_claims))
        review["raw_text_preview"] = _compact_text(raw_text, max_chars=900)
        review["still_possible_missing_from_preview"] = _still_possible_missing(
            review,
            raw_text,
            max_additional_claims=max_additional_claims,
        )
        results.append(review)
        print(
            "[Step3][SUPPLEMENT_MAX12_VERIFY] "
            f"reviewed {index}/{len(rows)} chunk={chunk_id} "
            f"status={review['review_status']} additional={review['additional_claim_count']}",
            flush=True,
        )

    aggregate = _aggregate(results, max_additional_claims=max_additional_claims)
    max12_hit_chunks = [
        row
        for row in results
        if row.get("review_status") == "ok" and int(row.get("additional_claim_count", 0) or 0) >= max_additional_claims
    ]
    summary = {
        "inputs": {
            "pilot_report": str(pilot_report_path),
            "claims_dir": str(claims_dir),
            "species_chunks": str(species_chunks_path),
            "family_chunks": str(family_chunks_path),
        },
        "outputs": {
            "json": str(out_json),
            "markdown": str(out_md),
            "cache": str(cache_path),
        },
        "selection": {
            "source": "pilot reviews with review_status == ok and additional_claim_count == pilot temporary cap",
            "pilot_temporary_additional_claim_cap": pilot_cap,
            "selected_chunk_count": len(rows),
            "limit": limit,
            "selected_by_stratum": dict(sorted(Counter(str(row.get("stratum", "") or "") for row in rows).items())),
            "selected_chunk_ids": [row["source_chunk_id"] for row in rows],
        },
        "verification_prompt": {
            "max_additional_claims": max_additional_claims,
            "max_chars_per_chunk": max_chars,
            "dry_run": dry_run,
        },
        "aggregate": aggregate,
        "max12_cap_hit_chunks": sorted(max12_hit_chunks, key=lambda row: (str(row.get("source_chapter", "")), str(row.get("source_chunk_id", "")))),
        "reviews": results,
        "run_command": (
            "python kg_v2/Step3_extraction/verify_supplement_max12.py "
            "--max-additional-claims 12 "
            "--cache KG/reports/supplement_max12_verification_cache.jsonl"
        ),
        "note": (
            "Read-only verification only. This script writes reports under KG/reports and does not modify "
            "KG/intermediate/claims_final_global, KG/intermediate/facts_final_global, or any Neo4j materialization."
        ),
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_json, summary)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify max_additional_claims=12 on pilot cap-hit chunks.")
    parser.add_argument("--pilot-report", default="KG/reports/claim_cap_chunk_review.json")
    parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global")
    parser.add_argument("--species-chunks", default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    parser.add_argument("--family-chunks", default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    parser.add_argument("--out-json", default="KG/reports/supplement_max12_verification.json")
    parser.add_argument("--out-md", default="KG/reports/supplement_max12_verification.md")
    parser.add_argument("--cache", default="KG/reports/supplement_max12_verification_cache.jsonl")
    parser.add_argument("--max-chars", type=int, default=6500)
    parser.add_argument("--max-additional-claims", type=int, default=12)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = verify_supplement_max12(
        pilot_report_path=_resolve_path(args.pilot_report),
        claims_dir=_resolve_path(args.claims_dir),
        species_chunks_path=_resolve_path(args.species_chunks),
        family_chunks_path=_resolve_path(args.family_chunks),
        out_json=_resolve_path(args.out_json),
        out_md=_resolve_path(args.out_md),
        cache_path=_resolve_path(args.cache),
        max_chars=max(1000, args.max_chars),
        max_additional_claims=max(1, args.max_additional_claims),
        limit=max(0, args.limit),
        dry_run=args.dry_run,
    )
    aggregate = summary["aggregate"]
    print(f"[Step3][SUPPLEMENT_MAX12_VERIFY] json={summary['outputs']['json']}")
    print(f"[Step3][SUPPLEMENT_MAX12_VERIFY] md={summary['outputs']['markdown']}")
    print(
        "[Step3][SUPPLEMENT_MAX12_VERIFY] "
        f"sampled={aggregate['sampled_chunk_count']} ok={aggregate['ok_review_count']} "
        f"additional={aggregate['total_additional_claims']} "
        f"max12_hits={aggregate['max12_cap_hit_chunk_count']} "
        f"max12_hit_ratio={aggregate['max12_cap_hit_ratio']:.4f}"
    )


if __name__ == "__main__":
    main()
