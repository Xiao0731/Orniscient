"""Plan and run supplementary claim extraction for chunks that hit claim caps."""

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

from kg_v2.Step3_extraction.chapter_router import route_chapter
from kg_v2.Step3_extraction.normalizers import QUALIFIER_KEYS, short_quote
from kg_v2.Step3_extraction.predicate_registry import predicates_for_domains
from kg_v2.utils.hash_utils import stable_hash
from kg_v2.utils.jsonl_utils import write_json, write_jsonl
from kg_v2.utils.llm_utils import LLMResponseError, chat_json_raw, load_openai_compatible_config


SYSTEM_PROMPT_TEMPLATE = """You are a supplementary structured information extraction engine for a bird ecology knowledge graph.

You will receive one BOW chunk and the claims already extracted from it.
Extract ONLY additional high-value claims that are not already covered by the existing claims.

Rules:
- Return valid JSON only.
- Return [] if there are no useful additional structured claims.
- Avoid duplicates and near-duplicates of existing claims.
- Be conservative: only keep claims that are clearly novel, directly supported, atomic, and useful for downstream Fact/Object construction.
- If remaining content is a near-duplicate, a paraphrase of an existing fact, too fine-grained, weakly useful, or just a different split of the same fact, return [].
- Use only the allowed fact domains and allowed predicates.
- Each additional claim must be directly supported by a short evidence quote from the chunk.
- Extract at most {max_additional_claims} additional claims.
- {max_additional_claims} is a single-call safety cap, not a target. Do not fill the list just because space remains.
- Do not invent facts or infer beyond the chunk.
- Keep each claim atomic.
"""


USER_PROMPT_TEMPLATE = """## Subject metadata
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
    with path.open("r", encoding="utf-8-sig") as handle:
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


def _safe_div(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _norm(value: object) -> str:
    return " ".join(str(value or "").replace("_", " ").split()).casefold()


def _chapter_group(chapter: str) -> str:
    norm = _norm(chapter)
    if chapter in {
        "Introduction",
        "DietAndForaging",
        "Habitat",
        "Identification",
        "Measurements",
        "SubspeciesAndVariation",
        "MortalityPredationParasites",
    }:
        return chapter
    if any(token in norm for token in ("conservation", "relationships with people", "humanrelations", "future research", "futureresearch")):
        return "Conservation_related"
    if any(token in norm for token in ("breeding", "nest", "egg", "incubation", "parental", "demography", "sexualbehavior")):
        return "LifeHistoryAndBreeding_related"
    return "Other_at_or_over_cap"


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


def _existing_claims_for_prompt(claims: list[dict]) -> list[dict]:
    return [
        {
            "fact_domain": claim.get("fact_domain", ""),
            "predicate": claim.get("predicate", ""),
            "object_type": claim.get("object_type", ""),
            "object_text": claim.get("object_text", ""),
            "object_canonical_id": claim.get("object_canonical_id", ""),
            "object_canonical_name": claim.get("object_canonical_name", ""),
            "value_min": claim.get("value_min"),
            "value_max": claim.get("value_max"),
            "unit": claim.get("unit", ""),
            "qualifiers_raw": claim.get("qualifiers_raw", {}),
            "evidence_quote": claim.get("evidence_quote", ""),
        }
        for claim in claims
    ]


def _allowed_for_row(row: dict) -> tuple[list[str], list[str]]:
    route = route_chapter(str(row.get("source_chapter", "") or ""), str(row.get("source_subchapter", "") or ""))
    domains = [str(value) for value in route.get("allowed_fact_domains", [])]
    predicates = [str(value) for value in route.get("allowed_predicates", [])]
    if not predicates and domains:
        predicates = predicates_for_domains(domains)
    return domains, predicates


def _build_high_risk_manifest(processed_chunks_path: Path, claims_by_chunk: dict[str, list[dict]]) -> list[dict]:
    rows: list[dict] = []
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
        rows.append(
            {
                "source_chunk_id": chunk_id,
                "source_chapter": row.get("source_chapter", ""),
                "source_subchapter": row.get("source_subchapter", ""),
                "subject_rank": row.get("subject_rank", ""),
                "subject_taxon_id": row.get("subject_taxon_id", ""),
                "source_doc_id": row.get("source_doc_id", ""),
                "claim_count": claim_count,
                "max_claims_current_policy": max_claims,
                "cap_status": "over_cap" if claim_count > max_claims else "exact_cap",
                "chapter_group": _chapter_group(str(row.get("source_chapter", "") or "")),
            }
        )
    return sorted(rows, key=lambda item: (item["subject_rank"], item["source_chunk_id"]))


def _write_shard_manifests(manifest_rows: list[dict], out_dir: Path, num_shards: int) -> list[dict]:
    shards = [[] for _ in range(num_shards)]
    for index, row in enumerate(manifest_rows):
        shards[index % num_shards].append(row)
    shard_summaries = []
    for index, rows in enumerate(shards):
        shard_dir = out_dir / f"shard_{index:02d}"
        shard_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = shard_dir / "shard_manifest.jsonl"
        write_jsonl(manifest_path, rows)
        by_chapter = Counter(row.get("source_chapter", "") for row in rows)
        by_group = Counter(row.get("chapter_group", "") for row in rows)
        shard_summaries.append(
            {
                "shard_index": index,
                "chunk_count": len(rows),
                "manifest": str(manifest_path),
                "by_chapter_top20": dict(by_chapter.most_common(20)),
                "by_chapter_group": dict(sorted(by_group.items())),
            }
        )
    return shard_summaries


def plan_supplement(
    *,
    claims_dir: Path,
    processed_chunks_path: Path,
    out_dir: Path,
    num_shards: int,
    expected_count: int,
) -> dict:
    claims_by_chunk = _load_claims_by_chunk(claims_dir)
    manifest_rows = _build_high_risk_manifest(processed_chunks_path, claims_by_chunk)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "supplement_manifest.jsonl"
    write_jsonl(manifest_path, manifest_rows)
    shard_summaries = _write_shard_manifests(manifest_rows, out_dir, num_shards)
    by_chapter = Counter(row["source_chapter"] for row in manifest_rows)
    by_group = Counter(row["chapter_group"] for row in manifest_rows)
    by_rank = Counter(row["subject_rank"] for row in manifest_rows)
    summary = {
        "claims_dir": str(claims_dir),
        "processed_chunks": str(processed_chunks_path),
        "out_dir": str(out_dir),
        "manifest": str(manifest_path),
        "num_shards": num_shards,
        "high_risk_chunk_count": len(manifest_rows),
        "expected_high_risk_chunk_count": expected_count,
        "count_matches_expected": len(manifest_rows) == expected_count,
        "by_subject_rank": dict(sorted(by_rank.items())),
        "by_chapter_group": dict(sorted(by_group.items())),
        "by_source_chapter_top50": dict(by_chapter.most_common(50)),
        "shards": shard_summaries,
        "note": "Planning only. This does not modify claims_final_global and does not rebuild facts.",
    }
    write_json(out_dir / "supplement_shard_plan.json", summary)
    return summary


def _load_chunk_texts(chunk_ids: set[str], chunk_files: list[Path]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    remaining = set(chunk_ids)
    for path in chunk_files:
        if not path.exists() or not remaining:
            continue
        with path.open("r", encoding="utf-8-sig") as handle:
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
    for index, claim in enumerate(additional_claims):
        signature = _claim_signature(claim)
        quote = _norm(claim.get("evidence_quote", ""))
        best_signature_similarity = max((_similarity(signature, old) for old in existing_signatures), default=0.0)
        best_quote_similarity = max((_similarity(quote, old) for old in existing_quotes), default=0.0)
        same_predicate_object = any(
            str(claim.get("predicate", "")) == str(existing.get("predicate", ""))
            and _similarity(_norm(claim.get("object_text", "")), _norm(existing.get("object_text", ""))) >= 0.86
            for existing in existing_claims
        )
        is_duplicate = same_predicate_object or best_signature_similarity >= 0.9 or best_quote_similarity >= 0.92
        duplicate_rows.append(
            {
                "additional_claim_index": index,
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
    }


def _build_prompt(row: dict, raw_text: str, existing_claims: list[dict], *, max_chars: int) -> str:
    allowed_domains, allowed_predicates = _allowed_for_row(row)
    return USER_PROMPT_TEMPLATE.format(
        subject_taxon_id=row.get("subject_taxon_id", ""),
        subject_rank=row.get("subject_rank", ""),
        source_release=row.get("source_release", "bow_2025_snapshot"),
        source_doc_id=row.get("source_doc_id", ""),
        source_chunk_id=row.get("source_chunk_id", ""),
        source_chapter=row.get("source_chapter", ""),
        source_subchapter=row.get("source_subchapter", ""),
        allowed_fact_domains=json.dumps(allowed_domains, ensure_ascii=False),
        allowed_predicates=json.dumps(allowed_predicates, ensure_ascii=False),
        existing_claims=json.dumps(_existing_claims_for_prompt(existing_claims), ensure_ascii=False, indent=2),
        chunk_text=str(raw_text or "")[:max_chars],
    )


def _coerce_additional_claims(wrapper: dict, row: dict, *, max_additional_claims: int) -> tuple[list[dict], list[str]]:
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
    for claim in claims[:max_additional_claims]:
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
                "subject_taxon_id": row.get("subject_taxon_id", ""),
                "subject_rank": row.get("subject_rank", ""),
                "fact_domain": domain,
                "predicate": predicate,
                "object_type": object_type,
                "object_text": str(claim.get("object_text", "") or ""),
                "object_canonical_id": str(claim.get("object_canonical_id", "") or ""),
                "object_canonical_name": str(claim.get("object_canonical_name", "") or ""),
                "value_min": claim.get("value_min"),
                "value_max": claim.get("value_max"),
                "unit": str(claim.get("unit", "") or ""),
                "qualifiers_raw": qualifiers,
                "source_db": "BOW",
                "source_release": row.get("source_release", "bow_2025_snapshot"),
                "source_doc_id": row.get("source_doc_id", ""),
                "source_chunk_id": row.get("source_chunk_id", ""),
                "source_chapter": row.get("source_chapter", ""),
                "source_subchapter": row.get("source_subchapter", ""),
                "evidence_quote": quote,
                "confidence": max(0.0, min(confidence, 1.0)),
                "extraction_method": "claim_cap_supplement",
            }
        )
    if len(claims) > max_additional_claims:
        warnings.append(f"response_exceeded_{max_additional_claims}_additional_claims_truncated")
    return out, warnings


def _assign_supplement_ids(row: dict, additional_claims: list[dict]) -> list[dict]:
    out = []
    for index, claim in enumerate(additional_claims):
        payload = dict(claim)
        payload["supplement_claim_id"] = stable_hash(
            payload.get("subject_taxon_id", ""),
            payload.get("source_chunk_id", ""),
            payload.get("predicate", ""),
            payload.get("object_text", ""),
            payload.get("evidence_quote", ""),
            "claim_cap_supplement",
            prefix="supclaim_",
        )
        payload["source_existing_claim_count"] = row.get("claim_count", 0)
        payload["source_max_claims_current_policy"] = row.get("max_claims_current_policy", 0)
        payload["supplement_round"] = 1
        payload["supplement_index_in_round"] = index
        payload["supplement_index_in_chunk"] = index
        out.append(payload)
    return out


def _review_completion_fields(review_status: str, additional_count: int, *, max_additional_claims: int) -> dict:
    hit_soft_cap = review_status == "ok" and additional_count >= max_additional_claims
    if review_status == "ok":
        final_status = "completed_round_1_hit_soft_cap" if hit_soft_cap else "completed_round_1_not_hit_cap"
    elif review_status == "dry_run":
        final_status = "dry_run"
    else:
        final_status = "failed_round_1"
    return {
        "round_count": 1 if review_status == "ok" else 0,
        "round_1_additional_claim_count": additional_count if review_status == "ok" else 0,
        "total_additional_claim_count": additional_count if review_status == "ok" else 0,
        "hit_soft_cap": hit_soft_cap,
        "hit_soft_cap_round_1": hit_soft_cap,
        "possibly_incomplete_due_to_cap": hit_soft_cap,
        "final_completion_status": final_status,
    }


def _review_chunk(
    row: dict,
    raw_text: str,
    existing_claims: list[dict],
    *,
    config,
    max_chars: int,
    max_additional_claims: int,
) -> dict:
    prompt = _build_prompt(row, raw_text, existing_claims, max_chars=max_chars)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(max_additional_claims=max_additional_claims)
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
            additional_claims, warnings = _coerce_additional_claims(
                wrapper,
                row,
                max_additional_claims=max_additional_claims,
            )
            additional_claims = _assign_supplement_ids(row, additional_claims)
            duplicate_assessment = _duplicate_assessment(additional_claims, existing_claims)
            return {
                **row,
                "review_status": "ok",
                "existing_claim_count": len(existing_claims),
                "additional_claim_count": len(additional_claims),
                "additional_claims": additional_claims,
                "duplicate_assessment": duplicate_assessment,
                "warnings": warnings,
                "raw_response_preview": raw_preview,
                **_review_completion_fields(
                    "ok",
                    len(additional_claims),
                    max_additional_claims=max_additional_claims,
                ),
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
        **row,
        "review_status": "error",
        "existing_claim_count": len(existing_claims),
        "additional_claim_count": 0,
        "additional_claims": [],
        "duplicate_assessment": _duplicate_assessment([], existing_claims),
        "warnings": [],
        "error_message": last_error,
        "raw_response_preview": raw_preview,
        **_review_completion_fields("error", 0, max_additional_claims=max_additional_claims),
    }


def _load_reviewed(review_path: Path) -> dict[str, dict]:
    if not review_path.exists():
        return {}
    reviewed: dict[str, dict] = {}
    with review_path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            chunk_id = str(row.get("source_chunk_id", "") or "")
            if chunk_id:
                reviewed[chunk_id] = row
    return reviewed


def _is_failed_review(row: dict | None) -> bool:
    if not isinstance(row, dict):
        return False
    review_status = str(row.get("review_status", "") or "").casefold()
    final_status = str(row.get("final_completion_status", "") or "").casefold()
    return review_status in {"error", "failed"} or final_status.startswith("failed")


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


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
        "round_1_additional_claim_count": review.get("round_1_additional_claim_count", review.get("additional_claim_count", 0)),
        "hit_soft_cap_round_1": bool(review.get("hit_soft_cap_round_1")),
        "possibly_incomplete_due_to_cap": bool(review.get("possibly_incomplete_due_to_cap")),
        "final_completion_status": review.get("final_completion_status", ""),
    }


def _rewrite_additional_claims(reviewed: dict[str, dict], output_path: Path) -> int:
    rows = []
    for review in reviewed.values():
        for claim in _claims_from_review(review):
            rows.append(claim)
    rows = sorted(rows, key=lambda row: (row.get("source_chunk_id", ""), row.get("supplement_claim_id", "")))
    write_jsonl(output_path, rows)
    return len(rows)


def _rewrite_derived_outputs(
    reviewed: dict[str, dict],
    *,
    additional_path: Path,
    failure_path: Path,
    hit_soft_cap_path: Path,
) -> dict:
    additional_total = _rewrite_additional_claims(reviewed, additional_path)
    failures = sorted(
        [row for row in reviewed.values() if row.get("review_status") == "error"],
        key=lambda row: str(row.get("source_chunk_id", "")),
    )
    write_jsonl(failure_path, failures)
    hit_rows = sorted(
        [_hit_soft_cap_row(row) for row in reviewed.values() if row.get("hit_soft_cap_round_1") is True],
        key=lambda row: str(row.get("source_chunk_id", "")),
    )
    write_jsonl(hit_soft_cap_path, hit_rows)
    return {
        "additional_claims_written": additional_total,
        "failures_written": len(failures),
        "hit_soft_cap_chunks_written": len(hit_rows),
    }


def _summarize_reviews(reviews: list[dict]) -> dict:
    ok = [row for row in reviews if row.get("review_status") == "ok"]
    errors = [row for row in reviews if row.get("review_status") == "error"]
    dry_runs = [row for row in reviews if row.get("review_status") == "dry_run"]
    positive = [row for row in ok if int(row.get("additional_claim_count", 0)) > 0]
    hit_soft_cap = [row for row in ok if row.get("hit_soft_cap_round_1") is True]
    additional_total = sum(int(row.get("additional_claim_count", 0)) for row in ok)
    near_dup = sum(int(row.get("duplicate_assessment", {}).get("near_duplicate_count", 0)) for row in ok)
    by_chapter = defaultdict(lambda: {"chunks": 0, "positive": 0, "additional": 0, "near_duplicate": 0, "hit_soft_cap": 0})
    for row in ok:
        chapter = str(row.get("source_chapter", "") or "")
        by_chapter[chapter]["chunks"] += 1
        by_chapter[chapter]["positive"] += 1 if int(row.get("additional_claim_count", 0)) > 0 else 0
        by_chapter[chapter]["additional"] += int(row.get("additional_claim_count", 0))
        by_chapter[chapter]["near_duplicate"] += int(row.get("duplicate_assessment", {}).get("near_duplicate_count", 0))
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


def run_shard(
    *,
    out_dir: Path,
    shard_index: int,
    claims_dir: Path,
    species_chunks_path: Path,
    family_chunks_path: Path,
    max_chars: int,
    max_additional_claims: int,
    log_every: int,
    dry_run: bool,
    retry_failures: bool,
) -> dict:
    shard_dir = out_dir / f"shard_{shard_index:02d}"
    shard_manifest = shard_dir / "shard_manifest.jsonl"
    rows = _read_jsonl(shard_manifest)
    review_path = shard_dir / "chunk_reviews.jsonl"
    additional_path = shard_dir / "additional_claims.jsonl"
    failure_path = shard_dir / "failures.jsonl"
    hit_soft_cap_path = shard_dir / "hit_soft_cap_chunks.jsonl"
    log_path = shard_dir / "run.log"
    reviewed = _load_reviewed(review_path)
    derived_counts = _rewrite_derived_outputs(
        reviewed,
        additional_path=additional_path,
        failure_path=failure_path,
        hit_soft_cap_path=hit_soft_cap_path,
    )
    if retry_failures:
        pending = [
            row
            for row in rows
            if row["source_chunk_id"] in reviewed and _is_failed_review(reviewed.get(row["source_chunk_id"]))
        ]
    else:
        pending = [row for row in rows if row["source_chunk_id"] not in reviewed]
    claims_by_chunk = _load_claims_by_chunk(claims_dir)
    chunk_texts = _load_chunk_texts({row["source_chunk_id"] for row in pending}, [species_chunks_path, family_chunks_path])
    config = None
    if not dry_run:
        config = load_openai_compatible_config()
        if config is None:
            raise RuntimeError("Missing OpenAI-compatible LLM config. Use --dry-run to verify shard wiring.")
        config = replace(config, temperature=0.0)

    started_at = time.time()
    with log_path.open("a", encoding="utf-8") as log:
        log.write(
            f"[START] shard={shard_index} total={len(rows)} already_reviewed={len(reviewed)} "
            f"pending={len(pending)} max_additional_claims={max_additional_claims} dry_run={dry_run} "
            f"retry_failures={retry_failures} "
            f"repaired_additional={derived_counts['additional_claims_written']} "
            f"repaired_failures={derived_counts['failures_written']} "
            f"repaired_hit_soft_cap={derived_counts['hit_soft_cap_chunks_written']}\n"
        )
        for offset, row in enumerate(pending, start=1):
            chunk_id = row["source_chunk_id"]
            raw_text = ""
            chunk = chunk_texts.get(chunk_id, {})
            if chunk:
                raw_text = str(chunk.get("raw_text") or chunk.get("chunk_text") or chunk.get("text") or "")
            existing_claims = claims_by_chunk.get(chunk_id, [])
            if dry_run:
                review = {
                    **row,
                    "review_status": "dry_run",
                    "existing_claim_count": len(existing_claims),
                    "additional_claim_count": 0,
                    "additional_claims": [],
                    "duplicate_assessment": _duplicate_assessment([], existing_claims),
                    "warnings": ["dry_run_no_llm_review"],
                    **_review_completion_fields("dry_run", 0, max_additional_claims=max_additional_claims),
                }
            elif not raw_text:
                review = {
                    **row,
                    "review_status": "error",
                    "existing_claim_count": len(existing_claims),
                    "additional_claim_count": 0,
                    "additional_claims": [],
                    "duplicate_assessment": _duplicate_assessment([], existing_claims),
                    "warnings": [],
                    "error_message": "raw_text_not_found",
                    **_review_completion_fields("error", 0, max_additional_claims=max_additional_claims),
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
            reviewed[chunk_id] = review
            _append_jsonl(review_path, review)
            for claim in _claims_from_review(review):
                _append_jsonl(additional_path, claim)
            if review.get("review_status") == "error":
                _append_jsonl(failure_path, review)
            if review.get("hit_soft_cap_round_1") is True:
                _append_jsonl(hit_soft_cap_path, _hit_soft_cap_row(review))
            if offset == 1 or offset % max(1, log_every) == 0 or offset == len(pending):
                elapsed = max(time.time() - started_at, 1e-3)
                speed = offset / elapsed
                line = (
                    f"[PROGRESS] shard={shard_index} processed={offset}/{len(pending)} "
                    f"chunk={chunk_id} status={review.get('review_status')} "
                    f"additional={review.get('additional_claim_count', 0)} "
                    f"hit_soft_cap={review.get('hit_soft_cap_round_1', False)} speed={speed:.3f}/s\n"
                )
                log.write(line)
                log.flush()
                print(line.rstrip(), flush=True)

    derived_counts = _rewrite_derived_outputs(
        reviewed,
        additional_path=additional_path,
        failure_path=failure_path,
        hit_soft_cap_path=hit_soft_cap_path,
    )
    review_summary = _summarize_reviews(list(reviewed.values()))
    summary = {
        "shard_index": shard_index,
        "shard_dir": str(shard_dir),
        "manifest": str(shard_manifest),
        "review_path": str(review_path),
        "additional_claims_path": str(additional_path),
        "failures_path": str(failure_path),
        "hit_soft_cap_chunks_path": str(hit_soft_cap_path),
        "log_path": str(log_path),
        "total_target_chunks": len(rows),
        "total_shard_chunks": len(rows),
        "completed_chunks": review_summary["ok_count"],
        "failed_chunks": review_summary["error_count"],
        "reviewed_chunks_total": len(reviewed),
        "chunks_with_additional_claims": review_summary["chunks_with_additional_claims"],
        "total_additional_claims": review_summary["total_additional_claims"],
        "average_additional_claims_per_chunk": _safe_div(review_summary["total_additional_claims"], review_summary["ok_count"]),
        "hit_soft_cap_chunks": review_summary["hit_soft_cap_chunks"],
        "hit_soft_cap_chunk_count": review_summary["hit_soft_cap_chunks"],
        "total_round_1_additional_claims": review_summary["total_additional_claims"],
        "additional_claims_written": derived_counts["additional_claims_written"],
        "failures_written": derived_counts["failures_written"],
        "hit_soft_cap_chunks_written": derived_counts["hit_soft_cap_chunks_written"],
        "max_chars": max_chars,
        "max_additional_claims": max_additional_claims,
        "max_additional_claims_per_round": max_additional_claims,
        "continuation_policy": "none_single_round_only",
        "hit_soft_cap_policy": "record_only_no_continuation",
        "dry_run": dry_run,
        "retry_failures": retry_failures,
        "inputs": {
            "claims_dir": str(claims_dir),
            "species_chunks": str(species_chunks_path),
            "family_chunks": str(family_chunks_path),
            "shard_manifest": str(shard_manifest),
        },
        "summary": review_summary,
    }
    write_json(shard_dir / "run_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan/run full supplementary extraction for claim-cap chunks.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global")
    plan_parser.add_argument("--processed-chunks", default="KG/intermediate/claims_final_global/processed_unique_chunks.jsonl")
    plan_parser.add_argument("--out-dir", default="KG/intermediate/claims_cap_supplement_full")
    plan_parser.add_argument("--num-shards", type=int, default=16)
    plan_parser.add_argument("--expected-count", type=int, default=93542)

    run_parser = sub.add_parser("run-shard")
    run_parser.add_argument("--out-dir", default="KG/intermediate/claims_cap_supplement_full")
    run_parser.add_argument("--shard-index", type=int, required=True)
    run_parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global")
    run_parser.add_argument("--species-chunks", default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    run_parser.add_argument("--family-chunks", default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    run_parser.add_argument("--max-chars", type=int, default=6500)
    run_parser.add_argument("--max-additional-claims", type=int, default=6)
    run_parser.add_argument("--log-every", type=int, default=25)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument(
        "--retry-failures",
        action="store_true",
        help="Retry only prior failed/error chunk reviews in this shard; successful ok reviews are skipped.",
    )

    args = parser.parse_args()
    if args.command == "plan":
        summary = plan_supplement(
            claims_dir=_resolve_path(args.claims_dir),
            processed_chunks_path=_resolve_path(args.processed_chunks),
            out_dir=_resolve_path(args.out_dir),
            num_shards=max(1, args.num_shards),
            expected_count=args.expected_count,
        )
        print(f"[Step3][CLAIM_CAP_SUPPLEMENT_PLAN] manifest={summary['manifest']}")
        print(f"[Step3][CLAIM_CAP_SUPPLEMENT_PLAN] shard_plan={Path(summary['out_dir']) / 'supplement_shard_plan.json'}")
        print(
            "[Step3][CLAIM_CAP_SUPPLEMENT_PLAN] "
            f"chunks={summary['high_risk_chunk_count']} expected={summary['expected_high_risk_chunk_count']} "
            f"matches={summary['count_matches_expected']} shards={summary['num_shards']}"
        )
        for shard in summary["shards"]:
            print(f"[Step3][CLAIM_CAP_SUPPLEMENT_PLAN] shard_{shard['shard_index']:02d} chunks={shard['chunk_count']}")
    elif args.command == "run-shard":
        summary = run_shard(
            out_dir=_resolve_path(args.out_dir),
            shard_index=args.shard_index,
            claims_dir=_resolve_path(args.claims_dir),
            species_chunks_path=_resolve_path(args.species_chunks),
            family_chunks_path=_resolve_path(args.family_chunks),
            max_chars=max(1000, args.max_chars),
            max_additional_claims=max(1, args.max_additional_claims),
            log_every=max(1, args.log_every),
            dry_run=args.dry_run,
            retry_failures=args.retry_failures,
        )
        print(f"[Step3][CLAIM_CAP_SUPPLEMENT_SHARD] summary={summary['shard_dir']}/run_summary.json")
        print(
            "[Step3][CLAIM_CAP_SUPPLEMENT_SHARD] "
            f"reviewed={summary['reviewed_chunks_total']} additional={summary['additional_claims_written']} "
            f"errors={summary['summary']['error_count']}"
        )


if __name__ == "__main__":
    main()
