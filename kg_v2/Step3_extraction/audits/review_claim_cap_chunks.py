"""Small-sample LLM review for chunks that hit Step 3 claim-count caps."""

from __future__ import annotations

import argparse
import json
import random
import re
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

from kg_v2.Step3_extraction.chapter_router import route_chapter
from kg_v2.Step3_extraction.normalizers import QUALIFIER_KEYS, short_quote
from kg_v2.Step3_extraction.predicate_registry import predicates_for_domains
from kg_v2.utils.jsonl_utils import write_json
from kg_v2.utils.llm_utils import LLMResponseError, chat_json_raw, load_openai_compatible_config


REVIEW_SYSTEM_PROMPT = """You are a careful audit reviewer for a bird ecology knowledge graph.

You will receive one BOW chunk and the claims that have already been extracted from it.
Your task is ONLY to check whether the chunk still contains additional high-value structured claims that are NOT duplicates of the existing claims.

Rules:
- Return valid JSON only.
- Return [] if the existing claims already cover the useful structured facts.
- Do not repeat or paraphrase an existing claim.
- Use only the allowed fact domains and predicates.
- Prefer concrete ecological, taxonomic, distributional, morphological, behavioral, breeding, measurement, conservation, predation, parasite, disease, or mortality facts.
- Each additional claim must be directly supported by a short evidence quote from the chunk.
- Extract at most 6 additional claims.
- This is an audit sample only; do not invent facts.
"""


REVIEW_USER_PROMPT_TEMPLATE = """## Subject metadata
- subject_taxon_id: {subject_taxon_id}
- subject_rank: {subject_rank}

## Source metadata
- source_chunk_id: {source_chunk_id}
- source_chapter: {source_chapter}
- source_subchapter: {source_subchapter}

Allowed fact domains:
{allowed_fact_domains}

Allowed predicates:
{allowed_predicates}

Existing claims from this chunk:
{existing_claims}

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


REVIEW_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "additional_claims": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "fact_domain": {"type": "string"},
                    "predicate": {"type": "string"},
                    "object_type": {"type": "string"},
                    "object_text": {"type": "string"},
                    "value_min": {"type": ["number", "null"]},
                    "value_max": {"type": ["number", "null"]},
                    "unit": {"type": "string"},
                    "qualifiers_raw": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {key: {"type": "string"} for key in QUALIFIER_KEYS},
                        "required": QUALIFIER_KEYS,
                    },
                    "evidence_quote": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "fact_domain",
                    "predicate",
                    "object_type",
                    "object_text",
                    "value_min",
                    "value_max",
                    "unit",
                    "qualifiers_raw",
                    "evidence_quote",
                    "confidence",
                ],
            },
        }
    },
    "required": ["additional_claims"],
}


STRATA = [
    "Introduction",
    "DietAndForaging",
    "Habitat",
    "Identification",
    "Conservation_related",
    "LifeHistoryAndBreeding_related",
    "Measurements",
    "SubspeciesAndVariation",
    "MortalityPredationParasites",
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


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def _safe_div(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _norm(value: object) -> str:
    return " ".join(str(value or "").replace("_", " ").split()).casefold()


def _compact_text(value: object, *, max_chars: int = 900) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def _stratum_for_chapter(chapter: str) -> str:
    norm = _norm(chapter)
    if chapter in {"Introduction", "DietAndForaging", "Habitat", "Identification", "Measurements", "SubspeciesAndVariation"}:
        return chapter
    if chapter == "MortalityPredationParasites":
        return "MortalityPredationParasites"
    if any(token in norm for token in ("conservation", "relationships with people", "humanrelations", "future research", "futureresearch")):
        return "Conservation_related"
    if any(
        token in norm
        for token in (
            "breeding",
            "nest",
            "egg",
            "incubation",
            "parental",
            "demography",
            "sexualbehavior",
            "sexual behavior",
        )
    ):
        return "LifeHistoryAndBreeding_related"
    return ""


def _chunk_max_claims(row: dict) -> int:
    route = route_chapter(str(row.get("source_chapter", "") or ""), str(row.get("source_subchapter", "") or ""))
    if route.get("skip"):
        return 0
    return int(route.get("max_claims") or 0)


def _load_claims_by_chunk(claims_dir: Path) -> dict[str, list[dict]]:
    claims_by_chunk: dict[str, list[dict]] = defaultdict(list)
    for filename in ("species_claims.jsonl", "family_claims.jsonl"):
        for claim in _read_jsonl(claims_dir / filename):
            chunk_id = str(claim.get("source_chunk_id", "") or "").strip()
            if chunk_id:
                claims_by_chunk[chunk_id].append(claim)
    return claims_by_chunk


def _build_cap_chunk_pool(processed_chunks_path: Path, claims_by_chunk: dict[str, list[dict]]) -> dict[str, list[dict]]:
    strata: dict[str, list[dict]] = defaultdict(list)
    seen: set[str] = set()
    for row in _read_jsonl(processed_chunks_path):
        chunk_id = str(row.get("chunk_id", "") or row.get("source_chunk_id", "") or "").strip()
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        claim_count = len(claims_by_chunk.get(chunk_id, []))
        max_claims = _chunk_max_claims(row)
        if max_claims <= 0 or claim_count < max_claims:
            continue
        stratum = _stratum_for_chapter(str(row.get("source_chapter", "") or ""))
        if not stratum:
            continue
        sample_row = {
            "source_chunk_id": chunk_id,
            "source_chapter": row.get("source_chapter", ""),
            "source_subchapter": row.get("source_subchapter", ""),
            "subject_rank": row.get("subject_rank", ""),
            "subject_taxon_id": row.get("subject_taxon_id", ""),
            "source_doc_id": row.get("source_doc_id", ""),
            "claim_count": claim_count,
            "max_claims_current_policy": max_claims,
            "stratum": stratum,
        }
        strata[stratum].append(sample_row)
    return strata


def _sample_cap_chunks(strata_pool: dict[str, list[dict]], *, per_stratum: int, seed: int) -> list[dict]:
    rnd = random.Random(seed)
    selected: list[dict] = []
    selected_ids: set[str] = set()
    for stratum in STRATA:
        candidates = [row for row in strata_pool.get(stratum, []) if row["source_chunk_id"] not in selected_ids]
        candidates = sorted(candidates, key=lambda row: row["source_chunk_id"])
        sample_size = min(per_stratum, len(candidates))
        for row in rnd.sample(candidates, sample_size):
            selected.append(row)
            selected_ids.add(row["source_chunk_id"])
    return sorted(selected, key=lambda row: (row["stratum"], row["source_chunk_id"]))


def _load_chunk_texts(chunk_ids: set[str], chunk_files: list[Path]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    remaining = set(chunk_ids)
    for path in chunk_files:
        if not path.exists() or not remaining:
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not remaining:
                    break
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                chunk_id = str(row.get("chunk_id", "") or "").strip()
                if chunk_id in remaining:
                    found[chunk_id] = row
                    remaining.remove(chunk_id)
    return found


def _existing_claims_for_prompt(claims: list[dict]) -> list[dict]:
    rows = []
    for claim in claims:
        rows.append(
            {
                "fact_domain": claim.get("fact_domain", ""),
                "predicate": claim.get("predicate", ""),
                "object_text": claim.get("object_text", ""),
                "object_canonical_name": claim.get("object_canonical_name", ""),
                "value_min": claim.get("value_min"),
                "value_max": claim.get("value_max"),
                "unit": claim.get("unit", ""),
                "qualifiers_raw": claim.get("qualifiers_raw", {}),
                "evidence_quote": claim.get("evidence_quote", ""),
            }
        )
    return rows


def _allowed_for_row(row: dict) -> tuple[list[str], list[str]]:
    route = route_chapter(str(row.get("source_chapter", "") or ""), str(row.get("source_subchapter", "") or ""))
    domains = [str(value) for value in route.get("allowed_fact_domains", [])]
    predicates = [str(value) for value in route.get("allowed_predicates", [])]
    if not predicates and domains:
        predicates = predicates_for_domains(domains)
    return domains, predicates


def _build_review_prompt(row: dict, raw_text: str, existing_claims: list[dict], *, max_chars: int) -> str:
    allowed_domains, allowed_predicates = _allowed_for_row(row)
    return REVIEW_USER_PROMPT_TEMPLATE.format(
        subject_taxon_id=row.get("subject_taxon_id", ""),
        subject_rank=row.get("subject_rank", ""),
        source_chunk_id=row.get("source_chunk_id", ""),
        source_chapter=row.get("source_chapter", ""),
        source_subchapter=row.get("source_subchapter", ""),
        allowed_fact_domains=json.dumps(allowed_domains, ensure_ascii=False),
        allowed_predicates=json.dumps(allowed_predicates, ensure_ascii=False),
        existing_claims=json.dumps(_existing_claims_for_prompt(existing_claims), ensure_ascii=False, indent=2),
        chunk_text=str(raw_text or "")[:max_chars],
    )


def _coerce_additional_claims(wrapper: dict, row: dict) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    if not isinstance(wrapper, dict):
        return [], ["response_root_not_object"]
    claims = wrapper.get("additional_claims", [])
    if not isinstance(claims, list):
        return [], ["additional_claims_not_array"]
    allowed_domains, allowed_predicates = _allowed_for_row(row)
    allowed_domain_set = set(allowed_domains)
    allowed_predicate_set = set(allowed_predicates)
    out: list[dict] = []
    for claim in claims[:6]:
        if not isinstance(claim, dict):
            warnings.append("non_object_claim_dropped")
            continue
        domain = str(claim.get("fact_domain", "") or "")
        predicate = str(claim.get("predicate", "") or "")
        if domain not in allowed_domain_set:
            warnings.append(f"disallowed_domain:{domain}")
            continue
        if predicate not in allowed_predicate_set:
            warnings.append(f"disallowed_predicate:{predicate}")
            continue
        quote = short_quote(claim.get("evidence_quote", ""))
        if not quote:
            warnings.append("empty_evidence_quote")
            continue
        qualifiers = claim.get("qualifiers_raw") if isinstance(claim.get("qualifiers_raw"), dict) else {}
        qualifiers = {key: str(qualifiers.get(key, "") or "") for key in QUALIFIER_KEYS}
        try:
            confidence = float(claim.get("confidence", 0.0))
        except Exception:
            confidence = 0.0
        object_type = str(claim.get("object_type", "") or "text")
        if object_type not in {"concept", "numeric", "text", "relation"}:
            object_type = "text"
        out.append(
            {
                "fact_domain": domain,
                "predicate": predicate,
                "object_type": object_type,
                "object_text": str(claim.get("object_text", "") or ""),
                "value_min": claim.get("value_min"),
                "value_max": claim.get("value_max"),
                "unit": str(claim.get("unit", "") or ""),
                "qualifiers_raw": qualifiers,
                "evidence_quote": quote,
                "confidence": max(0.0, min(confidence, 1.0)),
            }
        )
    if len(claims) > 6:
        warnings.append("response_exceeded_6_additional_claims_truncated")
    return out, warnings


def _claim_signature(claim: dict) -> str:
    parts = [
        claim.get("predicate", ""),
        claim.get("object_text", ""),
        claim.get("object_canonical_name", ""),
        claim.get("value_min", ""),
        claim.get("value_max", ""),
        claim.get("unit", ""),
    ]
    return _norm(" ".join(str(part or "") for part in parts))


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _duplicate_assessment(additional_claims: list[dict], existing_claims: list[dict]) -> dict:
    duplicate_rows = []
    existing_signatures = [_claim_signature(claim) for claim in existing_claims]
    existing_quotes = [_norm(claim.get("evidence_quote", "")) for claim in existing_claims]
    for idx, claim in enumerate(additional_claims):
        signature = _claim_signature(claim)
        quote = _norm(claim.get("evidence_quote", ""))
        best_signature_similarity = max((_similarity(signature, sig) for sig in existing_signatures), default=0.0)
        best_quote_similarity = max((_similarity(quote, old_quote) for old_quote in existing_quotes), default=0.0)
        same_predicate_object = any(
            str(claim.get("predicate", "")) == str(existing.get("predicate", ""))
            and _similarity(_norm(claim.get("object_text", "")), _norm(existing.get("object_text", ""))) >= 0.86
            for existing in existing_claims
        )
        is_duplicate = same_predicate_object or best_signature_similarity >= 0.9 or best_quote_similarity >= 0.92
        duplicate_rows.append(
            {
                "additional_claim_index": idx,
                "is_near_duplicate_of_existing": bool(is_duplicate),
                "best_signature_similarity": round(best_signature_similarity, 4),
                "best_evidence_quote_similarity": round(best_quote_similarity, 4),
            }
        )
    duplicate_count = sum(1 for row in duplicate_rows if row["is_near_duplicate_of_existing"])
    return {
        "additional_claim_count": len(additional_claims),
        "near_duplicate_count": duplicate_count,
        "near_duplicate_ratio": _safe_div(duplicate_count, len(additional_claims)),
        "per_claim": duplicate_rows,
        "method": "Local heuristic: same predicate+similar object, signature similarity >=0.90, or evidence quote similarity >=0.92.",
    }


def _review_one(
    row: dict,
    raw_text: str,
    existing_claims: list[dict],
    *,
    config,
    max_chars: int,
) -> dict:
    prompt = _build_review_prompt(row, raw_text, existing_claims, max_chars=max_chars)
    last_error = ""
    raw_preview = ""
    for attempt in range(config.max_retries + 1):
        try:
            wrapper, raw_response = chat_json_raw(
                system_prompt=REVIEW_SYSTEM_PROMPT,
                user_prompt=prompt,
                json_schema=REVIEW_JSON_SCHEMA,
                config=config,
            )
            raw_preview = raw_response[:500]
            additional_claims, warnings = _coerce_additional_claims(wrapper, row)
            duplicate_assessment = _duplicate_assessment(additional_claims, existing_claims)
            return {
                "source_chunk_id": row["source_chunk_id"],
                "stratum": row["stratum"],
                "source_chapter": row.get("source_chapter", ""),
                "source_subchapter": row.get("source_subchapter", ""),
                "subject_rank": row.get("subject_rank", ""),
                "subject_taxon_id": row.get("subject_taxon_id", ""),
                "claim_count": row.get("claim_count", 0),
                "max_claims_current_policy": row.get("max_claims_current_policy", 0),
                "raw_text_preview": _compact_text(raw_text, max_chars=900),
                "existing_claims": _existing_claims_for_prompt(existing_claims),
                "additional_claims": additional_claims,
                "additional_claim_count": len(additional_claims),
                "has_additional_claims": bool(additional_claims),
                "duplicate_assessment": duplicate_assessment,
                "warnings": warnings,
                "review_status": "ok",
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
        "source_chunk_id": row["source_chunk_id"],
        "stratum": row["stratum"],
        "source_chapter": row.get("source_chapter", ""),
        "source_subchapter": row.get("source_subchapter", ""),
        "subject_rank": row.get("subject_rank", ""),
        "subject_taxon_id": row.get("subject_taxon_id", ""),
        "claim_count": row.get("claim_count", 0),
        "max_claims_current_policy": row.get("max_claims_current_policy", 0),
        "raw_text_preview": _compact_text(raw_text, max_chars=900),
        "existing_claims": _existing_claims_for_prompt(existing_claims),
        "additional_claims": [],
        "additional_claim_count": 0,
        "has_additional_claims": False,
        "duplicate_assessment": _duplicate_assessment([], existing_claims),
        "warnings": [],
        "review_status": "error",
        "error_message": last_error,
        "raw_response_preview": raw_preview,
    }


def _load_cache(cache_path: Path) -> dict[str, dict]:
    if not cache_path.exists():
        return {}
    cached: dict[str, dict] = {}
    with cache_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            chunk_id = str(row.get("source_chunk_id", "") or "")
            if chunk_id:
                cached[chunk_id] = row
    return cached


def _aggregate_results(results: list[dict]) -> dict:
    sampled = len(results)
    ok_results = [row for row in results if row.get("review_status") == "ok"]
    positive = [row for row in ok_results if row.get("additional_claim_count", 0) > 0]
    total_additional = sum(int(row.get("additional_claim_count", 0)) for row in ok_results)
    duplicate_total = sum(int(row.get("duplicate_assessment", {}).get("near_duplicate_count", 0)) for row in ok_results)
    by_stratum: dict[str, dict] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in results:
        grouped[str(row.get("stratum", "") or "")].append(row)
    for stratum, rows in grouped.items():
        ok_rows = [row for row in rows if row.get("review_status") == "ok"]
        positive_rows = [row for row in ok_rows if int(row.get("additional_claim_count", 0)) > 0]
        added = sum(int(row.get("additional_claim_count", 0)) for row in ok_rows)
        dup = sum(int(row.get("duplicate_assessment", {}).get("near_duplicate_count", 0)) for row in ok_rows)
        by_stratum[stratum] = {
            "sampled_chunk_count": len(rows),
            "ok_review_count": len(ok_rows),
            "error_count": len(rows) - len(ok_rows),
            "chunks_with_additional_claims": len(positive_rows),
            "positive_chunk_ratio": _safe_div(len(positive_rows), len(ok_rows)),
            "total_additional_claims": added,
            "avg_additional_claims_per_sampled_chunk": _safe_div(added, len(ok_rows)),
            "avg_additional_claims_among_positive_chunks": _safe_div(added, len(positive_rows)),
            "near_duplicate_additional_claims": dup,
            "near_duplicate_ratio": _safe_div(dup, added),
        }
    recommendations = sorted(
        [
            {
                "stratum": stratum,
                "priority_score": round(stats["positive_chunk_ratio"] * stats["avg_additional_claims_among_positive_chunks"], 6),
                **stats,
            }
            for stratum, stats in by_stratum.items()
        ],
        key=lambda row: (-row["priority_score"], -row["total_additional_claims"], row["stratum"]),
    )
    return {
        "sampled_chunk_count": sampled,
        "ok_review_count": len(ok_results),
        "error_count": sampled - len(ok_results),
        "chunks_with_additional_claims": len(positive),
        "positive_chunk_ratio": _safe_div(len(positive), len(ok_results)),
        "total_additional_claims": total_additional,
        "avg_additional_claims_per_sampled_chunk": _safe_div(total_additional, len(ok_results)),
        "avg_additional_claims_among_positive_chunks": _safe_div(total_additional, len(positive)),
        "near_duplicate_additional_claims": duplicate_total,
        "near_duplicate_ratio": _safe_div(duplicate_total, total_additional),
        "by_stratum": by_stratum,
        "recommended_followup_strata": recommendations,
    }


def _sample_examples(results: list[dict], *, per_stratum: int = 3) -> dict[str, list[dict]]:
    examples: dict[str, list[dict]] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in results:
        if row.get("additional_claim_count", 0) > 0:
            grouped[str(row.get("stratum", "") or "")].append(row)
    for stratum, rows in grouped.items():
        rows = sorted(rows, key=lambda row: (-int(row.get("additional_claim_count", 0)), row.get("source_chunk_id", "")))
        examples[stratum] = [
            {
                "source_chunk_id": row.get("source_chunk_id", ""),
                "source_chapter": row.get("source_chapter", ""),
                "raw_text_preview": row.get("raw_text_preview", ""),
                "existing_claims": row.get("existing_claims", [])[:6],
                "additional_claims": row.get("additional_claims", []),
                "duplicate_assessment": row.get("duplicate_assessment", {}),
            }
            for row in rows[:per_stratum]
        ]
    return examples


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(value) for value in row) + " |")
    return "\n".join(lines)


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _fmt_float(value: float) -> str:
    return f"{value:.4f}"


def _build_markdown(summary: dict) -> str:
    overview = summary["aggregate"]
    overview_rows = [
        ["Sampled chunks", _fmt_int(overview["sampled_chunk_count"])],
        ["OK reviews", _fmt_int(overview["ok_review_count"])],
        ["Errors", _fmt_int(overview["error_count"])],
        ["Chunks with additional claims", _fmt_int(overview["chunks_with_additional_claims"])],
        ["Positive chunk ratio", _fmt_float(overview["positive_chunk_ratio"])],
        ["Total additional claims", _fmt_int(overview["total_additional_claims"])],
        ["Avg additional/sample chunk", _fmt_float(overview["avg_additional_claims_per_sampled_chunk"])],
        ["Avg additional/positive chunk", _fmt_float(overview["avg_additional_claims_among_positive_chunks"])],
        ["Near-duplicate additional claims", _fmt_int(overview["near_duplicate_additional_claims"])],
        ["Near-duplicate ratio", _fmt_float(overview["near_duplicate_ratio"])],
    ]
    stratum_rows = [
        [
            stratum,
            _fmt_int(stats["sampled_chunk_count"]),
            _fmt_int(stats["chunks_with_additional_claims"]),
            _fmt_float(stats["positive_chunk_ratio"]),
            _fmt_int(stats["total_additional_claims"]),
            _fmt_float(stats["avg_additional_claims_per_sampled_chunk"]),
            _fmt_float(stats["avg_additional_claims_among_positive_chunks"]),
            _fmt_float(stats["near_duplicate_ratio"]),
        ]
        for stratum, stats in sorted(overview["by_stratum"].items())
    ]
    rec_rows = [
        [
            row["stratum"],
            _fmt_float(row["priority_score"]),
            _fmt_float(row["positive_chunk_ratio"]),
            _fmt_float(row["avg_additional_claims_among_positive_chunks"]),
            _fmt_int(row["total_additional_claims"]),
        ]
        for row in overview["recommended_followup_strata"]
    ]
    example_sections = []
    for stratum in STRATA:
        rows = summary["examples_by_stratum"].get(stratum, [])
        if not rows:
            continue
        example_rows = []
        for row in rows:
            existing = "; ".join(
                f"{claim.get('predicate', '')}: {claim.get('object_text', '')}" for claim in row.get("existing_claims", [])[:4]
            )
            additional = "; ".join(
                f"{claim.get('predicate', '')}: {claim.get('object_text', '')}" for claim in row.get("additional_claims", [])[:6]
            )
            example_rows.append(
                [
                    row.get("source_chunk_id", ""),
                    row.get("source_chapter", ""),
                    row.get("raw_text_preview", ""),
                    existing,
                    additional,
                    _fmt_float(row.get("duplicate_assessment", {}).get("near_duplicate_ratio", 0.0)),
                ]
            )
        example_sections.append(
            f"### {stratum}\n\n"
            + _markdown_table(
                ["Chunk ID", "Chapter", "Raw text preview", "Existing claims", "Additional claims", "Near-dup ratio"],
                example_rows,
            )
        )
    return "\n\n".join(
        [
            "# Claim Cap Chunk Supplementary Review",
            (
                "Read-only LLM review for a stratified sample of chunks that reached or exceeded the current "
                "claim extraction cap. No formal Claim or Fact artifacts were modified."
            ),
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## By Stratum\n\n"
            + _markdown_table(
                [
                    "Stratum",
                    "Sampled",
                    "Positive chunks",
                    "Positive ratio",
                    "Additional claims",
                    "Avg/sample",
                    "Avg/positive",
                    "Near-dup ratio",
                ],
                stratum_rows,
            ),
            "## Recommended Follow-up Strata\n\n"
            + _markdown_table(
                ["Stratum", "Priority score", "Positive ratio", "Avg/positive", "Additional claims"],
                rec_rows,
            ),
            "## Duplicate Assessment\n\n"
            + summary["duplicate_assessment_method"],
            "## Examples\n\n" + "\n\n".join(example_sections),
        ]
    )


def review_claim_cap_chunks(
    *,
    claims_dir: Path,
    processed_chunks_path: Path,
    species_chunks_path: Path,
    family_chunks_path: Path,
    out_json: Path,
    out_md: Path,
    cache_path: Path,
    per_stratum: int,
    seed: int,
    max_chars: int,
    dry_run: bool,
) -> dict:
    claims_by_chunk = _load_claims_by_chunk(claims_dir)
    strata_pool = _build_cap_chunk_pool(processed_chunks_path, claims_by_chunk)
    sampled_rows = _sample_cap_chunks(strata_pool, per_stratum=per_stratum, seed=seed)
    chunk_texts = _load_chunk_texts(
        {row["source_chunk_id"] for row in sampled_rows},
        [species_chunks_path, family_chunks_path],
    )

    cached = _load_cache(cache_path)
    results: list[dict] = []
    if dry_run:
        for row in sampled_rows:
            chunk = chunk_texts.get(row["source_chunk_id"], {})
            raw_text = str(chunk.get("raw_text") or chunk.get("chunk_text") or chunk.get("text") or "")
            results.append(
                {
                    "source_chunk_id": row["source_chunk_id"],
                    "stratum": row["stratum"],
                    "source_chapter": row.get("source_chapter", ""),
                    "source_subchapter": row.get("source_subchapter", ""),
                    "subject_rank": row.get("subject_rank", ""),
                    "subject_taxon_id": row.get("subject_taxon_id", ""),
                    "claim_count": row.get("claim_count", 0),
                    "max_claims_current_policy": row.get("max_claims_current_policy", 0),
                    "raw_text_preview": _compact_text(raw_text, max_chars=900),
                    "existing_claims": _existing_claims_for_prompt(claims_by_chunk.get(row["source_chunk_id"], [])),
                    "additional_claims": [],
                    "additional_claim_count": 0,
                    "has_additional_claims": False,
                    "duplicate_assessment": _duplicate_assessment([], claims_by_chunk.get(row["source_chunk_id"], [])),
                    "warnings": ["dry_run_no_llm_review"],
                    "review_status": "dry_run",
                }
            )
    else:
        config = load_openai_compatible_config()
        if config is None:
            raise RuntimeError("Missing OpenAI-compatible LLM config. Use --dry-run to only build the sample.")
        config = replace(config, temperature=0.0)
        for index, row in enumerate(sampled_rows, start=1):
            cached_row = cached.get(row["source_chunk_id"])
            if cached_row:
                results.append(cached_row)
                print(f"[Step3][CLAIM_CAP_REVIEW] cached {index}/{len(sampled_rows)} {row['source_chunk_id']}", flush=True)
                continue
            chunk = chunk_texts.get(row["source_chunk_id"], {})
            raw_text = str(chunk.get("raw_text") or chunk.get("chunk_text") or chunk.get("text") or "")
            existing_claims = claims_by_chunk.get(row["source_chunk_id"], [])
            review = _review_one(row, raw_text, existing_claims, config=config, max_chars=max_chars)
            results.append(review)
            _append_jsonl(cache_path, review)
            print(
                "[Step3][CLAIM_CAP_REVIEW] "
                f"reviewed {index}/{len(sampled_rows)} chunk={row['source_chunk_id']} "
                f"status={review['review_status']} additional={review['additional_claim_count']}",
                flush=True,
            )

    aggregate = _aggregate_results(results)
    summary = {
        "inputs": {
            "claims_dir": str(claims_dir),
            "processed_chunks": str(processed_chunks_path),
            "species_chunks": str(species_chunks_path),
            "family_chunks": str(family_chunks_path),
        },
        "outputs": {
            "json": str(out_json),
            "markdown": str(out_md),
            "cache": str(cache_path),
        },
        "sampling": {
            "strata": STRATA,
            "per_stratum": per_stratum,
            "seed": seed,
            "candidate_pool_counts": {stratum: len(strata_pool.get(stratum, [])) for stratum in STRATA},
            "sampled_counts": dict(Counter(row["stratum"] for row in sampled_rows)),
            "sampled_chunk_ids": [row["source_chunk_id"] for row in sampled_rows],
        },
        "review_prompt": {
            "system_prompt": REVIEW_SYSTEM_PROMPT,
            "temporary_additional_claim_cap": 6,
            "max_chars_per_chunk": max_chars,
            "dry_run": dry_run,
        },
        "aggregate": aggregate,
        "duplicate_assessment_method": (
            "Near-duplicate ratio is computed locally after review: same predicate with similar object text, "
            "claim signature similarity >= 0.90, or evidence quote similarity >= 0.92."
        ),
        "examples_by_stratum": _sample_examples(results, per_stratum=3),
        "reviews": results,
        "note": "Quality review only. Additional claims are not merged into claims_final_global and no facts are rebuilt.",
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_json, summary)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Review a small sample of chunks that hit Step3 claim extraction caps.")
    parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global")
    parser.add_argument("--processed-chunks", default="KG/intermediate/claims_final_global/processed_unique_chunks.jsonl")
    parser.add_argument("--species-chunks", default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    parser.add_argument("--family-chunks", default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    parser.add_argument("--out-json", default="KG/reports/claim_cap_chunk_review.json")
    parser.add_argument("--out-md", default="KG/reports/claim_cap_chunk_review.md")
    parser.add_argument("--cache", default="KG/reports/claim_cap_chunk_review_cache.jsonl")
    parser.add_argument("--per-stratum", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260515)
    parser.add_argument("--max-chars", type=int, default=6500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = review_claim_cap_chunks(
        claims_dir=_resolve_path(args.claims_dir),
        processed_chunks_path=_resolve_path(args.processed_chunks),
        species_chunks_path=_resolve_path(args.species_chunks),
        family_chunks_path=_resolve_path(args.family_chunks),
        out_json=_resolve_path(args.out_json),
        out_md=_resolve_path(args.out_md),
        cache_path=_resolve_path(args.cache),
        per_stratum=max(1, args.per_stratum),
        seed=args.seed,
        max_chars=max(1000, args.max_chars),
        dry_run=args.dry_run,
    )
    aggregate = summary["aggregate"]
    print(f"[Step3][CLAIM_CAP_REVIEW] json={summary['outputs']['json']}")
    print(f"[Step3][CLAIM_CAP_REVIEW] md={summary['outputs']['markdown']}")
    print(
        "[Step3][CLAIM_CAP_REVIEW] "
        f"sampled={aggregate['sampled_chunk_count']} "
        f"positive={aggregate['chunks_with_additional_claims']} "
        f"additional={aggregate['total_additional_claims']} "
        f"near_dup_ratio={aggregate['near_duplicate_ratio']:.4f}"
    )


if __name__ == "__main__":
    main()
