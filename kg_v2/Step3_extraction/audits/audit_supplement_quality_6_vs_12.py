"""Read-only quality audit comparing max=6 pilot claims with max=12 extras."""

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

from kg_v2.Step3_extraction.run_claim_cap_supplement_full import _load_chunk_texts, _safe_div
from kg_v2.utils.jsonl_utils import write_json
from kg_v2.utils.llm_utils import LLMResponseError, chat_json_raw, load_openai_compatible_config


QUALITY_SYSTEM_PROMPT = """You are a strict but fair quality auditor for bird ecology KG claim extraction.

You will receive one raw BOW chunk, already-existing claims, the max=6 supplementary claims, and the max=12 extra claims beyond index 6.

Audit each claim independently. Return JSON only.

For every claim, score six dimensions as booleans:
- faithful: directly supported by the raw chunk text and evidence quote.
- novel: adds a fact not already covered by the existing formal claims.
- non_duplicate: not a near-duplicate of existing formal claims; for max12_extra, also not a near-duplicate of max6 claims.
- atomic: one clear structured fact, not a bundle of multiple facts.
- predicate_domain_fit: fact_domain and predicate are appropriate for the claim.
- practically_useful: worth keeping as raw material for downstream Fact/Object construction.

Be conservative about unsupported, vague, duplicate, or badly typed claims. Do not require perfect ontology canonical IDs; focus on the six listed dimensions.
"""


QUALITY_USER_PROMPT_TEMPLATE = """## Source
- source_chunk_id: {source_chunk_id}
- source_chapter: {source_chapter}
- source_subchapter: {source_subchapter}

## Raw chunk text
{raw_text}

## Existing formal claims
{existing_claims}

## Max=6 supplementary claims to audit
{max6_claims}

## Max=12 extra claims to audit
These are the claims after the first 6 claims from the max=12 verification output.
{max12_extra_claims}

Return exactly one JSON object:
{{
  "claim_audits": [
    {{
      "claim_ref": "max6:0 or max12_extra:0",
      "faithful": true,
      "novel": true,
      "non_duplicate": true,
      "atomic": true,
      "predicate_domain_fit": true,
      "practically_useful": true,
      "issue_tags": ["unsupported|duplicate|not_novel|non_atomic|predicate_mismatch|domain_mismatch|too_vague|low_value"],
      "rationale": "brief reason"
    }}
  ],
  "chunk_summary": "brief comparison of max6 vs max12_extra quality for this chunk"
}}
"""


TARGET_BUCKETS = [
    "Introduction",
    "Habitat",
    "Identification",
    "MortalityPredationParasites",
    "DietAndForaging",
    "Other",
]

DIMENSIONS = [
    "faithful",
    "novel",
    "non_duplicate",
    "atomic",
    "predicate_domain_fit",
    "practically_useful",
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


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path)


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL in {path}: line={line_no} error={exc.msg}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def _load_audit_cache(path: Path) -> dict[str, dict]:
    cached = {}
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


def _claim_for_prompt(claim: dict) -> dict:
    return {
        "fact_domain": claim.get("fact_domain", ""),
        "predicate": claim.get("predicate", ""),
        "object_type": claim.get("object_type", ""),
        "object_text": claim.get("object_text", ""),
        "object_canonical_name": claim.get("object_canonical_name", ""),
        "value_min": claim.get("value_min"),
        "value_max": claim.get("value_max"),
        "unit": claim.get("unit", ""),
        "qualifiers_raw": claim.get("qualifiers_raw", {}),
        "evidence_quote": claim.get("evidence_quote", ""),
    }


def _claim_signature(claim: dict) -> str:
    return _norm(
        " ".join(
            str(claim.get(key, "") or "")
            for key in ("fact_domain", "predicate", "object_text", "object_canonical_name", "value_min", "value_max", "unit")
        )
    )


def _claim_ref(group: str, index: int) -> str:
    return f"{group}:{index}"


def _load_reviews(report_path: Path, cache_path: Path | None = None) -> dict[str, dict]:
    reviews: dict[str, dict] = {}
    if report_path.exists():
        report = _read_json(report_path)
        for row in report.get("reviews", []):
            if isinstance(row, dict):
                chunk_id = str(row.get("source_chunk_id", "") or "")
                if chunk_id:
                    reviews[chunk_id] = row
    if cache_path and cache_path.exists():
        for row in _read_jsonl(cache_path):
            chunk_id = str(row.get("source_chunk_id", "") or "")
            if chunk_id:
                reviews[chunk_id] = row
    return reviews


def _build_units(
    *,
    pilot_report: Path,
    pilot_cache: Path,
    max12_report: Path,
    max12_cache: Path,
) -> list[dict]:
    pilot_reviews = _load_reviews(pilot_report, pilot_cache)
    max12_reviews = _load_reviews(max12_report, max12_cache)

    units: list[dict] = []
    for chunk_id, pilot in sorted(pilot_reviews.items()):
        if pilot.get("review_status") != "ok":
            continue
        max6_claims = pilot.get("additional_claims", [])
        if len(max6_claims) != 6:
            continue
        max12 = max12_reviews.get(chunk_id)
        if not max12 or max12.get("review_status") != "ok":
            continue
        max12_claims = max12.get("additional_claims", [])
        max12_extra = max12_claims[6:] if isinstance(max12_claims, list) else []
        units.append(
            {
                "source_chunk_id": chunk_id,
                "source_chapter": pilot.get("source_chapter", max12.get("source_chapter", "")),
                "source_subchapter": pilot.get("source_subchapter", max12.get("source_subchapter", "")),
                "stratum": pilot.get("stratum", max12.get("stratum", "")),
                "existing_claims": pilot.get("existing_claims", []),
                "max6_claims": max6_claims,
                "max12_extra_claims": max12_extra,
            }
        )
    return units


def _build_prompt(unit: dict, raw_text: str, *, max_chars: int) -> str:
    return QUALITY_USER_PROMPT_TEMPLATE.format(
        source_chunk_id=unit["source_chunk_id"],
        source_chapter=unit.get("source_chapter", ""),
        source_subchapter=unit.get("source_subchapter", ""),
        raw_text=str(raw_text or "")[:max_chars],
        existing_claims=json.dumps([_claim_for_prompt(c) for c in unit.get("existing_claims", [])], ensure_ascii=False, indent=2),
        max6_claims=json.dumps([_claim_for_prompt(c) for c in unit.get("max6_claims", [])], ensure_ascii=False, indent=2),
        max12_extra_claims=json.dumps([_claim_for_prompt(c) for c in unit.get("max12_extra_claims", [])], ensure_ascii=False, indent=2),
    )


def _coerce_bool(value: object) -> bool:
    return bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"true", "yes", "1"}


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


def _coerce_chunk_audit(wrapper: dict, unit: dict, raw_text: str) -> dict:
    expected: dict[str, tuple[str, int, dict]] = {}
    comparison_for_max6 = list(unit.get("existing_claims", []))
    comparison_for_extra = list(unit.get("existing_claims", [])) + list(unit.get("max6_claims", []))
    for index, claim in enumerate(unit.get("max6_claims", [])):
        expected[_claim_ref("max6", index)] = ("max6", index, claim)
    for index, claim in enumerate(unit.get("max12_extra_claims", [])):
        expected[_claim_ref("max12_extra", index)] = ("max12_extra", index, claim)

    raw_audits = wrapper.get("claim_audits", []) if isinstance(wrapper, dict) else []
    by_ref = {}
    if isinstance(raw_audits, list):
        for item in raw_audits:
            if isinstance(item, dict):
                ref = str(item.get("claim_ref", "") or "")
                if ref:
                    by_ref[ref] = item

    claim_audits: list[dict] = []
    for ref, (group, index, claim) in expected.items():
        item = by_ref.get(ref, {})
        dims = {dimension: _coerce_bool(item.get(dimension, False)) for dimension in DIMENSIONS}
        issue_tags = item.get("issue_tags", [])
        if not isinstance(issue_tags, list):
            issue_tags = [str(issue_tags)]
        comparison_claims = comparison_for_max6 if group == "max6" else comparison_for_extra
        heuristics = _heuristic_checks(claim, comparison_claims, raw_text)
        claim_audits.append(
            {
                "claim_ref": ref,
                "claim_group": group,
                "claim_index": index,
                "source_chunk_id": unit["source_chunk_id"],
                "source_chapter": unit.get("source_chapter", ""),
                "chapter_bucket": _chapter_bucket(unit),
                "claim": _claim_for_prompt(claim),
                **dims,
                "all_dimensions_pass": all(dims.values()),
                "issue_tags": [str(tag) for tag in issue_tags if str(tag)],
                "rationale": _compact(item.get("rationale", ""), max_chars=300),
                "heuristics": heuristics,
            }
        )
    return {
        "source_chunk_id": unit["source_chunk_id"],
        "source_chapter": unit.get("source_chapter", ""),
        "chapter_bucket": _chapter_bucket(unit),
        "chunk_summary": _compact(wrapper.get("chunk_summary", "") if isinstance(wrapper, dict) else "", max_chars=500),
        "claim_audits": claim_audits,
    }


def _audit_one(unit: dict, raw_text: str, *, config, max_chars: int) -> dict:
    prompt = _build_prompt(unit, raw_text, max_chars=max_chars)
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
            audit = _coerce_chunk_audit(wrapper, unit, raw_text)
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
    audit = _coerce_chunk_audit({}, unit, raw_text)
    audit["review_status"] = "error"
    audit["error_message"] = last_error
    audit["raw_response_preview"] = raw_preview
    return audit


def _aggregate_claims(claim_audits: list[dict]) -> dict:
    out: dict[str, Any] = {"claim_count": len(claim_audits)}
    for dimension in DIMENSIONS:
        passes = sum(1 for row in claim_audits if row.get(dimension) is True)
        out[f"{dimension}_pass_count"] = passes
        out[f"{dimension}_pass_rate"] = _safe_div(passes, len(claim_audits))
        out[f"{dimension}_issue_count"] = len(claim_audits) - passes
        out[f"{dimension}_issue_rate"] = _safe_div(len(claim_audits) - passes, len(claim_audits))
    all_pass = sum(1 for row in claim_audits if row.get("all_dimensions_pass") is True)
    out["all_dimensions_pass_count"] = all_pass
    out["all_dimensions_pass_rate"] = _safe_div(all_pass, len(claim_audits))
    out["heuristic_quote_support_rate"] = _safe_div(
        sum(1 for row in claim_audits if row.get("heuristics", {}).get("evidence_quote_exactly_in_raw_text")),
        len(claim_audits),
    )
    out["heuristic_near_duplicate_rate"] = _safe_div(
        sum(1 for row in claim_audits if row.get("heuristics", {}).get("heuristic_near_duplicate")),
        len(claim_audits),
    )
    issue_counter = Counter(tag for row in claim_audits for tag in row.get("issue_tags", []))
    out["issue_tags"] = dict(issue_counter.most_common())
    return out


def _aggregate(chunk_audits: list[dict]) -> dict:
    ok_chunks = [row for row in chunk_audits if row.get("review_status") == "ok"]
    claims = [claim for row in ok_chunks for claim in row.get("claim_audits", [])]
    by_group = {
        group: _aggregate_claims([row for row in claims if row.get("claim_group") == group])
        for group in ("max6", "max12_extra")
    }
    by_bucket: dict[str, dict] = {}
    for bucket in TARGET_BUCKETS:
        bucket_claims = [row for row in claims if row.get("chapter_bucket") == bucket]
        by_bucket[bucket] = {
            "max6": _aggregate_claims([row for row in bucket_claims if row.get("claim_group") == "max6"]),
            "max12_extra": _aggregate_claims([row for row in bucket_claims if row.get("claim_group") == "max12_extra"]),
        }
    return {
        "audited_chunk_count": len(chunk_audits),
        "ok_chunk_count": len(ok_chunks),
        "error_chunk_count": len(chunk_audits) - len(ok_chunks),
        "audited_claim_count": len(claims),
        "by_claim_group": by_group,
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


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _fmt_float(value: float) -> str:
    return f"{value:.4f}"


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


def _comparison_rows(aggregate: dict) -> list[list[Any]]:
    rows = []
    by_group = aggregate["by_claim_group"]
    for dimension in DIMENSIONS:
        max6 = by_group["max6"].get(f"{dimension}_pass_rate", 0.0)
        extra = by_group["max12_extra"].get(f"{dimension}_pass_rate", 0.0)
        rows.append([dimension, _fmt_float(max6), _fmt_float(extra), _fmt_float(extra - max6)])
    rows.append(
        [
            "all_dimensions_pass",
            _fmt_float(by_group["max6"].get("all_dimensions_pass_rate", 0.0)),
            _fmt_float(by_group["max12_extra"].get("all_dimensions_pass_rate", 0.0)),
            _fmt_float(
                by_group["max12_extra"].get("all_dimensions_pass_rate", 0.0)
                - by_group["max6"].get("all_dimensions_pass_rate", 0.0)
            ),
        ]
    )
    rows.append(
        [
            "heuristic_near_duplicate",
            _fmt_float(by_group["max6"].get("heuristic_near_duplicate_rate", 0.0)),
            _fmt_float(by_group["max12_extra"].get("heuristic_near_duplicate_rate", 0.0)),
            _fmt_float(
                by_group["max12_extra"].get("heuristic_near_duplicate_rate", 0.0)
                - by_group["max6"].get("heuristic_near_duplicate_rate", 0.0)
            ),
        ]
    )
    return rows


def _judgment(aggregate: dict) -> dict:
    max6 = aggregate["by_claim_group"]["max6"]
    extra = aggregate["by_claim_group"]["max12_extra"]
    useful_extra = extra.get("practically_useful_pass_rate", 0.0)
    faithful_extra = extra.get("faithful_pass_rate", 0.0)
    all_extra = extra.get("all_dimensions_pass_rate", 0.0)
    dup_delta = extra.get("heuristic_near_duplicate_rate", 0.0) - max6.get("heuristic_near_duplicate_rate", 0.0)
    useful_delta = useful_extra - max6.get("practically_useful_pass_rate", 0.0)
    can_proceed = faithful_extra >= 0.9 and useful_extra >= 0.8 and all_extra >= 0.65 and dup_delta <= 0.15
    return {
        "can_enter_formal_93542_supplementary_extraction": bool(can_proceed),
        "recommended_policy_if_proceeding": {
            "max_additional_claims_per_round": 12,
            "use_continuation_when_hit_12": True,
            "treat_12_as_single_round_engineering_safety_cap_not_semantic_endpoint": True,
        },
        "reason": (
            "Proceed if max12_extra remains highly faithful/useful and duplicate inflation is modest. "
            f"Observed extra faithful={faithful_extra:.4f}, useful={useful_extra:.4f}, "
            f"all-pass={all_extra:.4f}, heuristic duplicate delta={dup_delta:.4f}, "
            f"useful delta={useful_delta:.4f}."
        ),
    }


def _build_markdown(summary: dict) -> str:
    aggregate = summary["aggregate"]
    overview_rows = [
        ["Audited chunks", _fmt_int(aggregate["audited_chunk_count"])],
        ["OK chunk audits", _fmt_int(aggregate["ok_chunk_count"])],
        ["Audited claims", _fmt_int(aggregate["audited_claim_count"])],
        ["Max=6 claims", _fmt_int(aggregate["by_claim_group"]["max6"]["claim_count"])],
        ["Max=12 extra claims", _fmt_int(aggregate["by_claim_group"]["max12_extra"]["claim_count"])],
    ]
    bucket_rows = []
    for bucket, stats in aggregate["by_chapter_bucket"].items():
        bucket_rows.append(
            [
                bucket,
                _fmt_int(stats["max6"]["claim_count"]),
                _fmt_float(stats["max6"].get("all_dimensions_pass_rate", 0.0)),
                _fmt_float(stats["max6"].get("practically_useful_pass_rate", 0.0)),
                _fmt_int(stats["max12_extra"]["claim_count"]),
                _fmt_float(stats["max12_extra"].get("all_dimensions_pass_rate", 0.0)),
                _fmt_float(stats["max12_extra"].get("practically_useful_pass_rate", 0.0)),
            ]
        )
    issue_sections = []
    for tag, rows in summary["problem_examples"].items():
        issue_rows = [
            [
                row["source_chunk_id"],
                row["chapter_bucket"],
                row["claim_group"],
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
                ["Chunk", "Bucket", "Group", "Predicate", "Object", "Evidence", "Rationale"],
                issue_rows,
            )
        )
    judgment = summary["judgment"]
    return "\n\n".join(
        [
            "# Supplement Claim Quality Comparison: max=6 vs max=12-extra",
            (
                "Read-only LLM quality audit over the same 55 pilot chunks that hit max=6. "
                "The comparison audits max=6 additional claims against the claims beyond the first 6 in max=12 verification."
            ),
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## Quality Dimension Pass Rates\n\n"
            + _markdown_table(["Dimension", "max=6", "max=12-extra", "Delta extra-minus-max6"], _comparison_rows(aggregate)),
            "## By Chapter Bucket\n\n"
            + _markdown_table(
                [
                    "Bucket",
                    "max=6 claims",
                    "max=6 all-pass",
                    "max=6 useful",
                    "max=12-extra claims",
                    "max=12-extra all-pass",
                    "max=12-extra useful",
                ],
                bucket_rows,
            ),
            "## Problem Examples\n\n" + ("\n\n".join(issue_sections) if issue_sections else "No problem examples were flagged."),
            "## Judgment\n\n"
            + _markdown_table(
                ["Question", "Answer"],
                [
                    ["Can enter formal 93,542 supplementary extraction", judgment["can_enter_formal_93542_supplementary_extraction"]],
                    ["Recommended per-round max_additional_claims", judgment["recommended_policy_if_proceeding"]["max_additional_claims_per_round"]],
                    ["Use continuation when hit 12", judgment["recommended_policy_if_proceeding"]["use_continuation_when_hit_12"]],
                    [
                        "Treat 12 as safety cap, not semantic endpoint",
                        judgment["recommended_policy_if_proceeding"][
                            "treat_12_as_single_round_engineering_safety_cap_not_semantic_endpoint"
                        ],
                    ],
                ],
            )
            + "\n\n"
            + judgment["reason"],
            "## Safety Note\n\n"
            + summary["note"],
        ]
    )


def run_quality_audit(
    *,
    pilot_report: Path,
    pilot_cache: Path,
    max12_report: Path,
    max12_cache: Path,
    species_chunks: Path,
    family_chunks: Path,
    out_json: Path,
    out_md: Path,
    cache: Path,
    max_chars: int,
    limit: int,
    dry_run: bool,
) -> dict:
    units = _build_units(
        pilot_report=pilot_report,
        pilot_cache=pilot_cache,
        max12_report=max12_report,
        max12_cache=max12_cache,
    )
    if limit > 0:
        units = units[:limit]
    chunk_texts = _load_chunk_texts({unit["source_chunk_id"] for unit in units}, [species_chunks, family_chunks])
    cached = _load_audit_cache(cache)

    config = None
    if not dry_run:
        config = load_openai_compatible_config()
        if config is None:
            raise RuntimeError("Missing OpenAI-compatible LLM config. Use --dry-run to verify wiring.")
        config = replace(config, temperature=0.0)

    chunk_audits: list[dict] = []
    for index, unit in enumerate(units, start=1):
        chunk_id = unit["source_chunk_id"]
        chunk = chunk_texts.get(chunk_id, {})
        raw_text = str(chunk.get("raw_text") or chunk.get("chunk_text") or chunk.get("text") or "")
        if dry_run:
            audit = _coerce_chunk_audit({}, unit, raw_text)
            audit["review_status"] = "dry_run"
        elif chunk_id in cached:
            audit = cached[chunk_id]
            print(
                "[Step3][SUPPLEMENT_QUALITY_6_VS_12] "
                f"cached {index}/{len(units)} chunk={chunk_id}",
                flush=True,
            )
        else:
            audit = _audit_one(unit, raw_text, config=config, max_chars=max_chars)
            _append_jsonl(cache, audit)
        chunk_audits.append(audit)
        print(
            "[Step3][SUPPLEMENT_QUALITY_6_VS_12] "
            f"audited {index}/{len(units)} chunk={chunk_id} status={audit.get('review_status')}",
            flush=True,
        )

    claim_audits = [
        claim
        for chunk_audit in chunk_audits
        if chunk_audit.get("review_status") == "ok"
        for claim in chunk_audit.get("claim_audits", [])
    ]
    aggregate = _aggregate(chunk_audits)
    summary = {
        "inputs": {
            "pilot_report": _display_path(pilot_report),
            "pilot_cache": _display_path(pilot_cache),
            "max12_report": _display_path(max12_report),
            "max12_cache": _display_path(max12_cache),
            "species_chunks": _display_path(species_chunks),
            "family_chunks": _display_path(family_chunks),
        },
        "outputs": {
            "json": _display_path(out_json),
            "markdown": _display_path(out_md),
            "cache": _display_path(cache),
        },
        "audit_design": {
            "unit": "LLM review per chunk",
            "max6_claims": "all 6 additional claims from the max=6 pilot result for the 55 cap-hit chunks",
            "max12_extra_claims": "claims after index 5 from max=12 verification output for the same chunks",
            "dimensions": DIMENSIONS,
            "max_chars_per_chunk": max_chars,
            "limit": limit,
            "dry_run": dry_run,
        },
        "aggregate": aggregate,
        "problem_examples": _examples(claim_audits),
        "judgment": _judgment(aggregate),
        "chunk_audits": chunk_audits,
        "note": (
            "Quality audit only. This script reads existing reports/cache and raw chunk text, writes KG/reports outputs, "
            "and does not modify claims_final_global, facts_final_global, start full supplementary extraction, rebuild facts, "
            "or materialize Neo4j."
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_json, summary)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit supplementary claim quality for max=6 vs max=12 extras.")
    parser.add_argument("--pilot-report", default="KG/reports/claim_cap_chunk_review.json")
    parser.add_argument("--pilot-cache", default="KG/reports/claim_cap_chunk_review_cache.jsonl")
    parser.add_argument("--max12-report", default="KG/reports/supplement_max12_verification.json")
    parser.add_argument("--max12-cache", default="KG/reports/supplement_max12_verification_cache.jsonl")
    parser.add_argument("--species-chunks", default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    parser.add_argument("--family-chunks", default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    parser.add_argument("--out-json", default="KG/reports/supplement_claim_quality_comparison_6_vs_12.json")
    parser.add_argument("--out-md", default="KG/reports/supplement_claim_quality_comparison_6_vs_12.md")
    parser.add_argument("--cache", default="KG/reports/supplement_claim_quality_comparison_6_vs_12_cache.jsonl")
    parser.add_argument("--max-chars", type=int, default=6500)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = run_quality_audit(
        pilot_report=_resolve_path(args.pilot_report),
        pilot_cache=_resolve_path(args.pilot_cache),
        max12_report=_resolve_path(args.max12_report),
        max12_cache=_resolve_path(args.max12_cache),
        species_chunks=_resolve_path(args.species_chunks),
        family_chunks=_resolve_path(args.family_chunks),
        out_json=_resolve_path(args.out_json),
        out_md=_resolve_path(args.out_md),
        cache=_resolve_path(args.cache),
        max_chars=max(1000, args.max_chars),
        limit=max(0, args.limit),
        dry_run=args.dry_run,
    )
    aggregate = summary["aggregate"]
    print(f"[Step3][SUPPLEMENT_QUALITY_6_VS_12] json={summary['outputs']['json']}")
    print(f"[Step3][SUPPLEMENT_QUALITY_6_VS_12] md={summary['outputs']['markdown']}")
    print(
        "[Step3][SUPPLEMENT_QUALITY_6_VS_12] "
        f"chunks={aggregate['ok_chunk_count']}/{aggregate['audited_chunk_count']} "
        f"claims={aggregate['audited_claim_count']} "
        f"max6_all_pass={aggregate['by_claim_group']['max6'].get('all_dimensions_pass_rate', 0.0):.4f} "
        f"extra_all_pass={aggregate['by_claim_group']['max12_extra'].get('all_dimensions_pass_rate', 0.0):.4f}"
    )


if __name__ == "__main__":
    main()
