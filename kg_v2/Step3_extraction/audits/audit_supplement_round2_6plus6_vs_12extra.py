"""Validate conservative 6+6 continuation quality against max=12 extras.

This read-only helper uses the 55 pilot chunks that hit the max=6 supplement
cap, runs a second conservative continuation pass with max=6, audits the Round 2
claims, and compares the result with the existing max=12-extra quality report.
It writes reports under KG/reports only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import replace
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step3_extraction.audit_supplement_quality_6_vs_12 import (
    DIMENSIONS,
    TARGET_BUCKETS,
    _aggregate_claims,
    _claim_for_prompt,
    _display_path,
    _fmt_float,
    _fmt_int,
    _markdown_table,
    _md_cell,
    _read_json,
    _read_jsonl,
    _safe_div,
)
from kg_v2.Step3_extraction.run_claim_cap_supplement_full import (
    _allowed_for_row,
    _assign_supplement_ids,
    _coerce_additional_claims,
    _duplicate_assessment,
    _existing_claims_for_prompt,
    _load_chunk_texts,
)
from kg_v2.utils.jsonl_utils import write_json
from kg_v2.utils.llm_utils import LLMResponseError, chat_json_raw, load_openai_compatible_config


ROUND2_SYSTEM_PROMPT_TEMPLATE = """You are a conservative continuation extractor for a bird ecology knowledge graph.

You will receive one BOW chunk, the formal claims already extracted from it, and the Round 1 supplementary claims already added.
Extract ONLY remaining high-value additional claims that are clearly not covered by the formal claims or Round 1 supplementary claims.

Rules:
- Return valid JSON only.
- Return [] if there are no clearly useful remaining structured claims.
- Extract at most {max_additional_claims} Round 2 claims.
- {max_additional_claims} is a safety cap, not a target. Do not fill the list just because space remains.
- Be stricter than Round 1: only keep claims that are clearly novel, directly supported, atomic, and useful for downstream Fact/Object construction.
- If the remaining content is a near-duplicate, a paraphrase of an existing fact, too fine-grained, weakly useful, or a different split of the same fact, return [].
- Do not invent facts or infer beyond the chunk.
- Use only the allowed fact domains and allowed predicates.
- Each claim must be directly supported by a short evidence quote from the chunk.
- Keep every claim atomic.
"""


ROUND2_USER_PROMPT_TEMPLATE = """## Subject metadata
- subject_taxon_id: {subject_taxon_id}
- subject_rank: {subject_rank}

## Source metadata
- source_db: BOW
- source_release: {source_release}
- source_doc_id: {source_doc_id}
- source_chunk_id: {source_chunk_id}
- source_chapter: {source_chapter}
- source_subchapter: {source_subchapter}

Allowed fact domains:
{allowed_fact_domains}

Allowed predicates:
{allowed_predicates}

Formal claims already extracted from this chunk:
{existing_claims}

Round 1 supplementary claims already added:
{round1_claims}

Input chunk:
{chunk_text}

Return exactly one JSON object:
{{
  "additional_claims": [
    {{
      "fact_domain": "...",
      "predicate": "...",
      "object_type": "concept|numeric|text|relation",
      "object_text": "...",
      "object_canonical_id": "",
      "object_canonical_name": "",
      "value_min": null,
      "value_max": null,
      "unit": "",
      "qualifiers_raw": {{
        "sex": "",
        "life_stage": "",
        "season": "",
        "breeding_status": "",
        "subspecies": "",
        "region_scope": "",
        "frequency": ""
      }},
      "evidence_quote": "...",
      "confidence": 0.0
    }}
  ]
}}
"""


QUALITY_SYSTEM_PROMPT = """You are a strict but fair quality auditor for bird ecology KG claim extraction.

You will receive one raw BOW chunk, formal claims already extracted from it, Round 1 max=6 supplementary claims, and Round 2 continuation claims from a conservative 6+6 policy.

Audit each Round 2 claim independently. Return JSON only.

For every claim, score six dimensions as booleans:
- faithful: directly supported by the raw chunk text and evidence quote.
- novel: adds a fact not already covered by the formal claims or Round 1 claims.
- non_duplicate: not a near-duplicate of the formal claims or Round 1 claims.
- atomic: one clear structured fact, not a bundle of multiple facts.
- predicate_domain_fit: fact_domain and predicate are appropriate for the claim.
- practically_useful: worth keeping as raw material for downstream Fact/Object construction.

Be conservative about unsupported, vague, duplicate, over-split, or weakly useful claims. Do not require perfect ontology canonical IDs; focus on the six listed dimensions.
"""


QUALITY_USER_PROMPT_TEMPLATE = """## Source
- source_chunk_id: {source_chunk_id}
- source_chapter: {source_chapter}
- source_subchapter: {source_subchapter}

## Raw chunk text
{raw_text}

## Formal claims already extracted
{existing_claims}

## Round 1 max=6 supplementary claims already added
{round1_claims}

## Round 2 continuation claims to audit
{round2_claims}

Return exactly one JSON object:
{{
  "claim_audits": [
    {{
      "claim_ref": "round2_6plus6:0",
      "faithful": true,
      "novel": true,
      "non_duplicate": true,
      "atomic": true,
      "predicate_domain_fit": true,
      "practically_useful": true,
      "issue_tags": ["unsupported|duplicate|not_novel|non_atomic|predicate_mismatch|domain_mismatch|too_vague|low_value|over_split"],
      "rationale": "brief reason"
    }}
  ],
  "chunk_summary": "brief quality summary for this chunk"
}}
"""


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


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def _load_cache(path: Path) -> dict[str, dict]:
    cached: dict[str, dict] = {}
    for row in _read_jsonl(path):
        chunk_id = str(row.get("source_chunk_id", "") or "")
        if chunk_id:
            cached[chunk_id] = row
    return cached


def _norm(value: object) -> str:
    return " ".join(str(value or "").replace("_", " ").split()).casefold()


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _compact(value: object, *, max_chars: int = 500) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def _chapter_bucket(row: dict) -> str:
    chapter = str(row.get("source_chapter", "") or "")
    if chapter in TARGET_BUCKETS[:-1]:
        return chapter
    return "Other"


def _claim_signature(claim: dict) -> str:
    return _norm(
        " ".join(
            str(claim.get(key, "") or "")
            for key in ("fact_domain", "predicate", "object_text", "object_canonical_name", "value_min", "value_max", "unit")
        )
    )


def _heuristic_checks(claim: dict, comparison_claims: list[dict], raw_text: str) -> dict:
    sig = _claim_signature(claim)
    quote = _norm(claim.get("evidence_quote", ""))
    raw_norm = _norm(raw_text)
    quote_supported = bool(quote and quote in raw_norm)
    best_sig = max((_similarity(sig, _claim_signature(other)) for other in comparison_claims), default=0.0)
    best_quote = max((_similarity(quote, _norm(other.get("evidence_quote", ""))) for other in comparison_claims), default=0.0)
    same_pred_obj = any(
        str(claim.get("predicate", "")) == str(other.get("predicate", ""))
        and _similarity(_norm(claim.get("object_text", "")), _norm(other.get("object_text", ""))) >= 0.86
        for other in comparison_claims
    )
    return {
        "evidence_quote_exactly_in_raw_text": quote_supported,
        "best_comparison_signature_similarity": round(best_sig, 4),
        "best_comparison_evidence_quote_similarity": round(best_quote, 4),
        "heuristic_near_duplicate": bool(same_pred_obj or best_sig >= 0.9 or best_quote >= 0.92),
    }


def _load_pilot_cap_hit_units(pilot_report: Path, pilot_cache: Path, max12_report: Path, max12_cache: Path) -> list[dict]:
    pilot_reviews: dict[str, dict] = {}
    if pilot_report.exists():
        report = _read_json(pilot_report)
        for row in report.get("reviews", []):
            if isinstance(row, dict) and row.get("source_chunk_id"):
                pilot_reviews[str(row["source_chunk_id"])] = row
    for row in _read_jsonl(pilot_cache):
        if row.get("source_chunk_id"):
            pilot_reviews[str(row["source_chunk_id"])] = row

    max12_reviews: dict[str, dict] = {}
    if max12_report.exists():
        report = _read_json(max12_report)
        for row in report.get("reviews", []):
            if isinstance(row, dict) and row.get("source_chunk_id"):
                max12_reviews[str(row["source_chunk_id"])] = row
    for row in _read_jsonl(max12_cache):
        if row.get("source_chunk_id"):
            max12_reviews[str(row["source_chunk_id"])] = row

    units: list[dict] = []
    for chunk_id, pilot in sorted(pilot_reviews.items()):
        round1_claims = pilot.get("additional_claims", [])
        if pilot.get("review_status") != "ok" or not isinstance(round1_claims, list) or len(round1_claims) != 6:
            continue
        max12 = max12_reviews.get(chunk_id, {})
        max12_claims = max12.get("additional_claims", []) if isinstance(max12, dict) else []
        units.append(
            {
                "source_chunk_id": chunk_id,
                "stratum": pilot.get("stratum", ""),
                "source_chapter": pilot.get("source_chapter", max12.get("source_chapter", "")),
                "source_subchapter": pilot.get("source_subchapter", max12.get("source_subchapter", "")),
                "subject_rank": pilot.get("subject_rank", max12.get("subject_rank", "")),
                "subject_taxon_id": pilot.get("subject_taxon_id", max12.get("subject_taxon_id", "")),
                "source_doc_id": pilot.get("source_doc_id", max12.get("source_doc_id", "")),
                "claim_count": pilot.get("claim_count", max12.get("claim_count", 0)),
                "max_claims_current_policy": pilot.get("max_claims_current_policy", max12.get("max_claims_current_policy", 0)),
                "existing_claims": pilot.get("existing_claims", []),
                "round1_claims": round1_claims,
                "max12_extra_claims": max12_claims[6:] if isinstance(max12_claims, list) else [],
            }
        )
    return units


def _build_round2_prompt(unit: dict, raw_text: str, *, max_chars: int) -> str:
    allowed_domains, allowed_predicates = _allowed_for_row(unit)
    return ROUND2_USER_PROMPT_TEMPLATE.format(
        subject_taxon_id=unit.get("subject_taxon_id", ""),
        subject_rank=unit.get("subject_rank", ""),
        source_release=unit.get("source_release", "bow_2025_snapshot"),
        source_doc_id=unit.get("source_doc_id", ""),
        source_chunk_id=unit.get("source_chunk_id", ""),
        source_chapter=unit.get("source_chapter", ""),
        source_subchapter=unit.get("source_subchapter", ""),
        allowed_fact_domains=json.dumps(allowed_domains, ensure_ascii=False),
        allowed_predicates=json.dumps(allowed_predicates, ensure_ascii=False),
        existing_claims=json.dumps([_claim_for_prompt(c) for c in unit.get("existing_claims", [])], ensure_ascii=False, indent=2),
        round1_claims=json.dumps([_claim_for_prompt(c) for c in unit.get("round1_claims", [])], ensure_ascii=False, indent=2),
        chunk_text=str(raw_text or "")[:max_chars],
    )


def _run_round2_one(unit: dict, raw_text: str, *, config, max_chars: int, max_additional_claims: int) -> dict:
    prompt = _build_round2_prompt(unit, raw_text, max_chars=max_chars)
    system_prompt = ROUND2_SYSTEM_PROMPT_TEMPLATE.format(max_additional_claims=max_additional_claims)
    comparison_claims = list(unit.get("existing_claims", [])) + list(unit.get("round1_claims", []))
    last_error = ""
    raw_preview = ""
    for attempt in range(config.max_retries + 1):
        try:
            wrapper, raw_response = chat_json_raw(
                system_prompt=system_prompt,
                user_prompt=prompt,
                json_schema={},
                config=config,
            )
            raw_preview = raw_response[:500]
            claims, warnings = _coerce_additional_claims(wrapper, unit, max_additional_claims=max_additional_claims)
            claims = _assign_supplement_ids(unit, claims)
            for index, claim in enumerate(claims):
                claim["supplement_round"] = 2
                claim["supplement_index_in_round"] = index
                claim["supplement_index_in_chunk"] = 6 + index
                claim["extraction_method"] = "claim_cap_supplement_6plus6_round2_validation"
            return {
                **{key: unit.get(key, "") for key in (
                    "source_chunk_id",
                    "source_chapter",
                    "source_subchapter",
                    "subject_rank",
                    "subject_taxon_id",
                    "source_doc_id",
                    "stratum",
                )},
                "review_status": "ok",
                "round_index": 2,
                "max_additional_claims": max_additional_claims,
                "additional_claim_count": len(claims),
                "hit_soft_cap": len(claims) >= max_additional_claims,
                "additional_claims": claims,
                "duplicate_assessment": _duplicate_assessment(claims, comparison_claims),
                "warnings": warnings,
                "raw_response_preview": raw_preview,
            }
        except LLMResponseError as exc:
            last_error = str(exc)
            raw_preview = exc.raw_response_preview[:500]
            if str(exc).startswith("LLM request failed: HTTP"):
                break
            time.sleep(1 + attempt)
        except Exception as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
            time.sleep(1 + attempt)
    return {
        **{key: unit.get(key, "") for key in (
            "source_chunk_id",
            "source_chapter",
            "source_subchapter",
            "subject_rank",
            "subject_taxon_id",
            "source_doc_id",
            "stratum",
        )},
        "review_status": "error",
        "round_index": 2,
        "max_additional_claims": max_additional_claims,
        "additional_claim_count": 0,
        "hit_soft_cap": False,
        "additional_claims": [],
        "duplicate_assessment": _duplicate_assessment([], comparison_claims),
        "warnings": [],
        "error_message": last_error,
        "raw_response_preview": raw_preview,
    }


def _coerce_bool(value: object) -> bool:
    return bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"true", "yes", "1"}


def _build_quality_prompt(unit: dict, round2: dict, raw_text: str, *, max_chars: int) -> str:
    return QUALITY_USER_PROMPT_TEMPLATE.format(
        source_chunk_id=unit["source_chunk_id"],
        source_chapter=unit.get("source_chapter", ""),
        source_subchapter=unit.get("source_subchapter", ""),
        raw_text=str(raw_text or "")[:max_chars],
        existing_claims=json.dumps([_claim_for_prompt(c) for c in unit.get("existing_claims", [])], ensure_ascii=False, indent=2),
        round1_claims=json.dumps([_claim_for_prompt(c) for c in unit.get("round1_claims", [])], ensure_ascii=False, indent=2),
        round2_claims=json.dumps([_claim_for_prompt(c) for c in round2.get("additional_claims", [])], ensure_ascii=False, indent=2),
    )


def _coerce_quality_audit(wrapper: dict, unit: dict, round2: dict, raw_text: str) -> dict:
    claims = round2.get("additional_claims", []) if isinstance(round2.get("additional_claims", []), list) else []
    expected = {f"round2_6plus6:{index}": (index, claim) for index, claim in enumerate(claims)}
    raw_audits = wrapper.get("claim_audits", []) if isinstance(wrapper, dict) else []
    by_ref = {}
    if isinstance(raw_audits, list):
        for item in raw_audits:
            if isinstance(item, dict) and item.get("claim_ref"):
                by_ref[str(item["claim_ref"])] = item

    comparison_claims = list(unit.get("existing_claims", [])) + list(unit.get("round1_claims", []))
    claim_audits = []
    for ref, (index, claim) in expected.items():
        item = by_ref.get(ref, {})
        dims = {dimension: _coerce_bool(item.get(dimension, False)) for dimension in DIMENSIONS}
        issue_tags = item.get("issue_tags", [])
        if not isinstance(issue_tags, list):
            issue_tags = [str(issue_tags)]
        claim_audits.append(
            {
                "claim_ref": ref,
                "claim_group": "round2_6plus6",
                "claim_index": index,
                "source_chunk_id": unit["source_chunk_id"],
                "source_chapter": unit.get("source_chapter", ""),
                "chapter_bucket": _chapter_bucket(unit),
                "claim": _claim_for_prompt(claim),
                **dims,
                "all_dimensions_pass": all(dims.values()),
                "issue_tags": [str(tag) for tag in issue_tags if str(tag)],
                "rationale": _compact(item.get("rationale", ""), max_chars=300),
                "heuristics": _heuristic_checks(claim, comparison_claims, raw_text),
            }
        )
    return {
        "source_chunk_id": unit["source_chunk_id"],
        "source_chapter": unit.get("source_chapter", ""),
        "chapter_bucket": _chapter_bucket(unit),
        "round2_additional_claim_count": len(claims),
        "round2_hit_soft_cap": bool(round2.get("hit_soft_cap")),
        "chunk_summary": _compact(wrapper.get("chunk_summary", "") if isinstance(wrapper, dict) else "", max_chars=500),
        "claim_audits": claim_audits,
    }


def _audit_round2_one(unit: dict, round2: dict, raw_text: str, *, config, max_chars: int) -> dict:
    claims = round2.get("additional_claims", []) if isinstance(round2.get("additional_claims", []), list) else []
    if not claims:
        audit = _coerce_quality_audit({}, unit, round2, raw_text)
        audit["review_status"] = "ok"
        audit["raw_response_preview"] = ""
        return audit

    prompt = _build_quality_prompt(unit, round2, raw_text, max_chars=max_chars)
    last_error = ""
    raw_preview = ""
    for attempt in range(config.max_retries + 1):
        try:
            wrapper, raw_response = chat_json_raw(
                system_prompt=QUALITY_SYSTEM_PROMPT,
                user_prompt=prompt,
                json_schema={},
                config=config,
            )
            raw_preview = raw_response[:500]
            audit = _coerce_quality_audit(wrapper, unit, round2, raw_text)
            audit["review_status"] = "ok"
            audit["raw_response_preview"] = raw_preview
            return audit
        except LLMResponseError as exc:
            last_error = str(exc)
            raw_preview = exc.raw_response_preview[:500]
            if str(exc).startswith("LLM request failed: HTTP"):
                break
            time.sleep(1 + attempt)
        except Exception as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
            time.sleep(1 + attempt)
    audit = _coerce_quality_audit({}, unit, round2, raw_text)
    audit["review_status"] = "error"
    audit["error_message"] = last_error
    audit["raw_response_preview"] = raw_preview
    return audit


def _aggregate_round2(chunk_audits: list[dict]) -> dict:
    ok_chunks = [row for row in chunk_audits if row.get("review_status") == "ok"]
    claims = [claim for row in ok_chunks for claim in row.get("claim_audits", [])]
    by_bucket: dict[str, dict] = {}
    for bucket in TARGET_BUCKETS:
        by_bucket[bucket] = _aggregate_claims([row for row in claims if row.get("chapter_bucket") == bucket])
    return {
        "audited_chunk_count": len(chunk_audits),
        "ok_chunk_count": len(ok_chunks),
        "error_chunk_count": len(chunk_audits) - len(ok_chunks),
        "audited_claim_count": len(claims),
        "round2_hit_soft_cap_chunk_count": sum(1 for row in ok_chunks if row.get("round2_hit_soft_cap")),
        "round2_hit_soft_cap_ratio": _safe_div(sum(1 for row in ok_chunks if row.get("round2_hit_soft_cap")), len(ok_chunks)),
        "by_claim_group": {"round2_6plus6": _aggregate_claims(claims)},
        "by_chapter_bucket": by_bucket,
    }


def _examples(claim_audits: list[dict], *, max_per_tag: int = 5) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in claim_audits:
        tags = row.get("issue_tags", [])
        if not tags and not row.get("all_dimensions_pass"):
            tags = [dimension for dimension in DIMENSIONS if not row.get(dimension)]
        for tag in tags:
            if len(grouped[str(tag)]) < max_per_tag:
                grouped[str(tag)].append(
                    {
                        "source_chunk_id": row.get("source_chunk_id", ""),
                        "chapter_bucket": row.get("chapter_bucket", ""),
                        "claim_group": row.get("claim_group", ""),
                        "claim_ref": row.get("claim_ref", ""),
                        "predicate": row.get("claim", {}).get("predicate", ""),
                        "object_text": row.get("claim", {}).get("object_text", ""),
                        "evidence_quote": row.get("claim", {}).get("evidence_quote", ""),
                        "rationale": row.get("rationale", ""),
                    }
                )
    return dict(sorted(grouped.items()))


def _comparison_rows(round2_stats: dict, max12_stats: dict) -> list[list[Any]]:
    rows = []
    for dimension in DIMENSIONS:
        r2 = round2_stats.get(f"{dimension}_pass_rate", 0.0)
        extra = max12_stats.get(f"{dimension}_pass_rate", 0.0)
        rows.append([dimension, _fmt_float(r2), _fmt_float(extra), _fmt_float(r2 - extra)])
    rows.append(
        [
            "all_dimensions_pass",
            _fmt_float(round2_stats.get("all_dimensions_pass_rate", 0.0)),
            _fmt_float(max12_stats.get("all_dimensions_pass_rate", 0.0)),
            _fmt_float(round2_stats.get("all_dimensions_pass_rate", 0.0) - max12_stats.get("all_dimensions_pass_rate", 0.0)),
        ]
    )
    rows.append(
        [
            "heuristic_near_duplicate",
            _fmt_float(round2_stats.get("heuristic_near_duplicate_rate", 0.0)),
            _fmt_float(max12_stats.get("heuristic_near_duplicate_rate", 0.0)),
            _fmt_float(round2_stats.get("heuristic_near_duplicate_rate", 0.0) - max12_stats.get("heuristic_near_duplicate_rate", 0.0)),
        ]
    )
    return rows


def _judgment(round2_stats: dict, max12_stats: dict) -> dict:
    all_delta = round2_stats.get("all_dimensions_pass_rate", 0.0) - max12_stats.get("all_dimensions_pass_rate", 0.0)
    useful_delta = round2_stats.get("practically_useful_pass_rate", 0.0) - max12_stats.get("practically_useful_pass_rate", 0.0)
    novelty_delta = round2_stats.get("novel_pass_rate", 0.0) - max12_stats.get("novel_pass_rate", 0.0)
    duplicate_delta = round2_stats.get("heuristic_near_duplicate_rate", 0.0) - max12_stats.get("heuristic_near_duplicate_rate", 0.0)
    materially_better = all_delta >= 0.1 and useful_delta >= 0.1 and novelty_delta >= 0.1 and duplicate_delta <= -0.1
    return {
        "round2_6plus6_quality_materially_better_than_12extra": bool(materially_better),
        "recommended_formal_policy_if_accepted": {
            "max_additional_claims_per_round": 6,
            "continuation_policy": "round_2_on_hit_soft_cap",
            "max_continuation_rounds": 2,
            "treat_6_as_single_round_safety_cap_not_semantic_endpoint": True,
        },
        "reason": (
            f"Round2 6+6 vs max12-extra deltas: all-pass={all_delta:.4f}, useful={useful_delta:.4f}, "
            f"novelty={novelty_delta:.4f}, heuristic-duplicate={duplicate_delta:.4f}."
        ),
    }


def _build_markdown(summary: dict) -> str:
    aggregate = summary["aggregate"]
    round2_stats = aggregate["by_claim_group"]["round2_6plus6"]
    max12_stats = summary["comparison_baseline"]["max12_extra"]
    overview_rows = [
        ["Pilot chunks that hit max=6", _fmt_int(summary["selection"]["selected_chunk_count"])],
        ["Round2 extraction OK chunks", _fmt_int(summary["round2_extraction"]["ok_chunk_count"])],
        ["Round2 chunks with claims", _fmt_int(summary["round2_extraction"]["chunks_with_additional_claims"])],
        ["Round2 total claims", _fmt_int(summary["round2_extraction"]["total_additional_claims"])],
        ["Round2 hit max=6 again", _fmt_int(summary["round2_extraction"]["hit_soft_cap_chunk_count"])],
        ["Audited Round2 claims", _fmt_int(aggregate["audited_claim_count"])],
        ["Baseline max12-extra claims", _fmt_int(max12_stats.get("claim_count", 0))],
    ]
    bucket_rows = []
    baseline_by_bucket = summary["comparison_baseline"].get("by_chapter_bucket", {})
    for bucket in TARGET_BUCKETS:
        r2 = aggregate["by_chapter_bucket"].get(bucket, {})
        extra = baseline_by_bucket.get(bucket, {}).get("max12_extra", {})
        bucket_rows.append(
            [
                bucket,
                _fmt_int(r2.get("claim_count", 0)),
                _fmt_float(r2.get("all_dimensions_pass_rate", 0.0)),
                _fmt_float(r2.get("practically_useful_pass_rate", 0.0)),
                _fmt_int(extra.get("claim_count", 0)),
                _fmt_float(extra.get("all_dimensions_pass_rate", 0.0)),
                _fmt_float(extra.get("practically_useful_pass_rate", 0.0)),
            ]
        )

    issue_sections = []
    for tag, rows in summary["problem_examples"].items():
        issue_rows = [
            [
                row["source_chunk_id"],
                row["chapter_bucket"],
                row["predicate"],
                row["object_text"],
                row["evidence_quote"],
                row["rationale"],
            ]
            for row in rows
        ]
        issue_sections.append(
            f"### {tag}\n\n"
            + _markdown_table(
                ["Chunk", "Bucket", "Predicate", "Object", "Evidence", "Rationale"],
                issue_rows,
            )
        )
    judgment = summary["judgment"]
    return "\n\n".join(
        [
            "# Supplement Round 2 Quality: 6+6 vs 12-extra",
            (
                "Read-only validation over the 55 pilot chunks that hit max=6. "
                "Round 2 uses a conservative continuation prompt with max=6 and is compared against the existing max=12-extra quality baseline."
            ),
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## Quality Dimension Pass Rates\n\n"
            + _markdown_table(["Dimension", "round2_6plus6", "max12_extra baseline", "Delta round2-minus-extra"], _comparison_rows(round2_stats, max12_stats)),
            "## By Chapter Bucket\n\n"
            + _markdown_table(
                [
                    "Bucket",
                    "round2 claims",
                    "round2 all-pass",
                    "round2 useful",
                    "max12-extra claims",
                    "max12-extra all-pass",
                    "max12-extra useful",
                ],
                bucket_rows,
            ),
            "## Problem Examples\n\n" + ("\n\n".join(issue_sections) if issue_sections else "No problem examples were flagged."),
            "## Judgment\n\n"
            + _markdown_table(
                ["Question", "Answer"],
                [
                    ["Round2 6+6 materially better than 12-extra", judgment["round2_6plus6_quality_materially_better_than_12extra"]],
                    ["Recommended per-round max_additional_claims", judgment["recommended_formal_policy_if_accepted"]["max_additional_claims_per_round"]],
                    ["Continuation policy", judgment["recommended_formal_policy_if_accepted"]["continuation_policy"]],
                    ["Max continuation rounds", judgment["recommended_formal_policy_if_accepted"]["max_continuation_rounds"]],
                ],
            )
            + "\n\n"
            + judgment["reason"],
            "## Safety Note\n\n" + summary["note"],
        ]
    )


def run_round2_quality_validation(
    *,
    pilot_report: Path,
    pilot_cache: Path,
    max12_report: Path,
    max12_cache: Path,
    baseline_quality_report: Path,
    species_chunks: Path,
    family_chunks: Path,
    out_json: Path,
    out_md: Path,
    round2_cache: Path,
    audit_cache: Path,
    max_chars: int,
    max_additional_claims: int,
    limit: int,
    dry_run: bool,
) -> dict:
    units = _load_pilot_cap_hit_units(pilot_report, pilot_cache, max12_report, max12_cache)
    if limit > 0:
        units = units[:limit]
    chunk_texts = _load_chunk_texts({unit["source_chunk_id"] for unit in units}, [species_chunks, family_chunks])
    round2_cached = _load_cache(round2_cache)
    audit_cached = _load_cache(audit_cache)

    config = None
    if not dry_run:
        config = load_openai_compatible_config()
        if config is None:
            raise RuntimeError("Missing OpenAI-compatible LLM config. Use --dry-run to verify wiring.")
        config = replace(config, temperature=0.0)

    round2_results: list[dict] = []
    chunk_audits: list[dict] = []
    for index, unit in enumerate(units, start=1):
        chunk_id = unit["source_chunk_id"]
        chunk = chunk_texts.get(chunk_id, {})
        raw_text = str(chunk.get("raw_text") or chunk.get("chunk_text") or chunk.get("text") or "")
        if dry_run:
            round2 = {
                "source_chunk_id": chunk_id,
                "review_status": "dry_run",
                "round_index": 2,
                "max_additional_claims": max_additional_claims,
                "additional_claim_count": 0,
                "hit_soft_cap": False,
                "additional_claims": [],
                "warnings": ["dry_run_no_llm_round2"],
            }
        elif chunk_id in round2_cached:
            round2 = round2_cached[chunk_id]
            print(f"[Step3][SUPPLEMENT_6PLUS6_ROUND2] cached {index}/{len(units)} chunk={chunk_id}", flush=True)
        else:
            round2 = _run_round2_one(
                unit,
                raw_text,
                config=config,
                max_chars=max_chars,
                max_additional_claims=max_additional_claims,
            )
            _append_jsonl(round2_cache, round2)
        round2_results.append(round2)

        if dry_run:
            audit = _coerce_quality_audit({}, unit, round2, raw_text)
            audit["review_status"] = "dry_run"
        elif chunk_id in audit_cached:
            audit = audit_cached[chunk_id]
            print(f"[Step3][SUPPLEMENT_6PLUS6_QUALITY] cached {index}/{len(units)} chunk={chunk_id}", flush=True)
        else:
            audit = _audit_round2_one(unit, round2, raw_text, config=config, max_chars=max_chars)
            _append_jsonl(audit_cache, audit)
        chunk_audits.append(audit)
        print(
            "[Step3][SUPPLEMENT_6PLUS6] "
            f"processed {index}/{len(units)} chunk={chunk_id} "
            f"round2_status={round2.get('review_status')} round2_claims={round2.get('additional_claim_count', 0)} "
            f"audit_status={audit.get('review_status')}",
            flush=True,
        )

    baseline = _read_json(baseline_quality_report)
    baseline_aggregate = baseline.get("aggregate", {}) if isinstance(baseline, dict) else {}
    baseline_by_group = baseline_aggregate.get("by_claim_group", {}) if isinstance(baseline_aggregate, dict) else {}
    baseline_max12 = baseline_by_group.get("max12_extra", {}) if isinstance(baseline_by_group, dict) else {}
    baseline_by_bucket = baseline_aggregate.get("by_chapter_bucket", {}) if isinstance(baseline_aggregate, dict) else {}

    round2_ok = [row for row in round2_results if row.get("review_status") == "ok"]
    round2_positive = [row for row in round2_ok if int(row.get("additional_claim_count", 0) or 0) > 0]
    round2_total = sum(int(row.get("additional_claim_count", 0) or 0) for row in round2_ok)
    round2_hit = [row for row in round2_ok if row.get("hit_soft_cap")]
    claim_audits = [
        claim
        for chunk_audit in chunk_audits
        if chunk_audit.get("review_status") == "ok"
        for claim in chunk_audit.get("claim_audits", [])
    ]
    aggregate = _aggregate_round2(chunk_audits)
    summary = {
        "inputs": {
            "pilot_report": _display_path(pilot_report),
            "pilot_cache": _display_path(pilot_cache),
            "max12_report": _display_path(max12_report),
            "max12_cache": _display_path(max12_cache),
            "baseline_quality_report": _display_path(baseline_quality_report),
            "species_chunks": _display_path(species_chunks),
            "family_chunks": _display_path(family_chunks),
        },
        "outputs": {
            "json": _display_path(out_json),
            "markdown": _display_path(out_md),
            "round2_cache": _display_path(round2_cache),
            "audit_cache": _display_path(audit_cache),
        },
        "selection": {
            "basis": "pilot chunks with exactly 6 max=6 additional claims",
            "selected_chunk_count": len(units),
            "limit": limit,
        },
        "policy_under_test": {
            "round_1_max_additional_claims": 6,
            "round_2_max_additional_claims": max_additional_claims,
            "round_2_trigger": "round_1_additional_claim_count == 6",
            "round_2_prompt_mode": "conservative_continuation",
        },
        "round2_extraction": {
            "attempted_chunk_count": len(round2_results),
            "ok_chunk_count": len(round2_ok),
            "error_chunk_count": len(round2_results) - len(round2_ok),
            "chunks_with_additional_claims": len(round2_positive),
            "total_additional_claims": round2_total,
            "avg_additional_claims_per_ok_chunk": _safe_div(round2_total, len(round2_ok)),
            "avg_additional_claims_per_positive_chunk": _safe_div(round2_total, len(round2_positive)),
            "hit_soft_cap_chunk_count": len(round2_hit),
            "hit_soft_cap_ratio": _safe_div(len(round2_hit), len(round2_ok)),
        },
        "audit_design": {
            "unit": "LLM quality audit per chunk for Round 2 continuation claims",
            "comparison_baseline": "existing supplement_claim_quality_comparison_6_vs_12 max12_extra aggregate",
            "dimensions": DIMENSIONS,
            "max_chars_per_chunk": max_chars,
            "dry_run": dry_run,
        },
        "aggregate": aggregate,
        "comparison_baseline": {
            "max12_extra": baseline_max12,
            "by_chapter_bucket": baseline_by_bucket,
        },
        "problem_examples": _examples(claim_audits),
        "judgment": _judgment(aggregate["by_claim_group"]["round2_6plus6"], baseline_max12),
        "round2_results": round2_results,
        "chunk_audits": chunk_audits,
        "note": (
            "Quality validation only. This script writes KG/reports outputs/caches, does not modify claims_final_global "
            "or facts_final_global, does not start the 93,542-chunk formal supplementary extraction, does not rebuild facts, "
            "and does not touch Neo4j."
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_json, summary)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate 6+6 Round 2 supplement quality against max=12 extras.")
    parser.add_argument("--pilot-report", default="KG/reports/claim_cap_chunk_review.json")
    parser.add_argument("--pilot-cache", default="KG/reports/claim_cap_chunk_review_cache.jsonl")
    parser.add_argument("--max12-report", default="KG/reports/supplement_max12_verification.json")
    parser.add_argument("--max12-cache", default="KG/reports/supplement_max12_verification_cache.jsonl")
    parser.add_argument("--baseline-quality-report", default="KG/reports/supplement_claim_quality_comparison_6_vs_12.json")
    parser.add_argument("--species-chunks", default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    parser.add_argument("--family-chunks", default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    parser.add_argument("--out-json", default="KG/reports/supplement_round2_quality_6plus6_vs_12extra.json")
    parser.add_argument("--out-md", default="KG/reports/supplement_round2_quality_6plus6_vs_12extra.md")
    parser.add_argument("--round2-cache", default="KG/reports/supplement_round2_continuation_6plus6_cache.jsonl")
    parser.add_argument("--audit-cache", default="KG/reports/supplement_round2_quality_6plus6_vs_12extra_cache.jsonl")
    parser.add_argument("--max-chars", type=int, default=6500)
    parser.add_argument("--max-additional-claims", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = run_round2_quality_validation(
        pilot_report=_resolve_path(args.pilot_report),
        pilot_cache=_resolve_path(args.pilot_cache),
        max12_report=_resolve_path(args.max12_report),
        max12_cache=_resolve_path(args.max12_cache),
        baseline_quality_report=_resolve_path(args.baseline_quality_report),
        species_chunks=_resolve_path(args.species_chunks),
        family_chunks=_resolve_path(args.family_chunks),
        out_json=_resolve_path(args.out_json),
        out_md=_resolve_path(args.out_md),
        round2_cache=_resolve_path(args.round2_cache),
        audit_cache=_resolve_path(args.audit_cache),
        max_chars=max(1000, args.max_chars),
        max_additional_claims=max(1, args.max_additional_claims),
        limit=max(0, args.limit),
        dry_run=args.dry_run,
    )
    aggregate = summary["aggregate"]
    round2_stats = aggregate["by_claim_group"]["round2_6plus6"]
    max12_stats = summary["comparison_baseline"]["max12_extra"]
    print(f"[Step3][SUPPLEMENT_6PLUS6_QUALITY] json={summary['outputs']['json']}")
    print(f"[Step3][SUPPLEMENT_6PLUS6_QUALITY] md={summary['outputs']['markdown']}")
    print(
        "[Step3][SUPPLEMENT_6PLUS6_QUALITY] "
        f"chunks={aggregate['ok_chunk_count']}/{aggregate['audited_chunk_count']} "
        f"round2_claims={aggregate['audited_claim_count']} "
        f"round2_all_pass={round2_stats.get('all_dimensions_pass_rate', 0.0):.4f} "
        f"max12_extra_all_pass={max12_stats.get('all_dimensions_pass_rate', 0.0):.4f}"
    )


if __name__ == "__main__":
    main()
