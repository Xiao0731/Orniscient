"""Audit Step 3 claim-extraction caps and final claim-count distributions."""

from __future__ import annotations

import argparse
import ast
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step3_extraction.chapter_router import route_chapter
from kg_v2.Step3_extraction.llm_extractors import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from kg_v2.utils.jsonl_utils import write_json


HIGH_INFO_CHAPTERS = {
    "Measurements",
    "SubspeciesAndVariation",
    "MortalityPredationParasites",
}
LIFE_HISTORY_CHAPTER_PATTERNS = (
    "breeding",
    "nest",
    "egg",
    "incubation",
    "parental",
    "demography",
)
CONSERVATION_CHAPTER_PATTERNS = (
    "conservation",
    "relationships with people",
    "humanrelations",
    "future research",
    "futureresearch",
    "mortalitypredationparasites",
)


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


def _safe_div(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _norm(value: object) -> str:
    return " ".join(str(value or "").replace("_", " ").split()).casefold()


def _chapter_group(chapter: str) -> str:
    norm = _norm(chapter)
    if chapter in HIGH_INFO_CHAPTERS:
        return chapter
    if any(pattern in norm for pattern in LIFE_HISTORY_CHAPTER_PATTERNS):
        return "LifeHistoryAndBreeding_related"
    if any(pattern in norm for pattern in CONSERVATION_CHAPTER_PATTERNS):
        return "Conservation_related"
    return ""


def _distribution(values: list[int]) -> dict[str, int]:
    counts = Counter(values)
    return {str(key): counts[key] for key in sorted(counts)}


def _capped_distribution(values: list[int], *, max_key: int = 8) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for value in values:
        if value >= max_key:
            counts[f">={max_key}"] += 1
        else:
            counts[str(value)] += 1
    def sort_key(item: tuple[str, int]) -> tuple[bool, int]:
        label = item[0]
        numeric = int(label[2:]) if label.startswith(">=") else int(label)
        return label.startswith(">="), numeric

    return dict(sorted(counts.items(), key=sort_key))


def _stats_for_values(values: list[int]) -> dict:
    total = len(values)
    claim_total = sum(values)
    return {
        "chunk_count": total,
        "claim_total": claim_total,
        "average_claims_per_chunk": _safe_div(claim_total, total),
        "distribution": _distribution(values),
    }


def _field_text(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = ast.literal_eval(node.value)
                    return value if isinstance(value, str) else ""
    return ""


def _extract_policy_sources() -> dict:
    llm_path = ROOT / "kg_v2/Step3_extraction/llm_extractors.py"
    router_path = ROOT / "kg_v2/Step3_extraction/chapter_router.py"
    runner_path = ROOT / "kg_v2/Step3_extraction/run_extract_claims_and_facts.py"
    schema_text = llm_path.read_text(encoding="utf-8")
    router_text = router_path.read_text(encoding="utf-8")
    runner_text = runner_path.read_text(encoding="utf-8")
    return {
        "recall_sensitive_quantity_constraints": [
            {
                "type": "per_chunk_max_claims",
                "value": 4,
                "file": str(llm_path),
                "function_or_symbol": "EXTRACTION_JSON_SCHEMA",
                "line_hint": "claims: array, maxItems: 4",
                "prompt_or_code_text": '"claims": {"type": "array", "maxItems": 4, ...}',
                "classification": "possible_recall_loss_quantity_constraint",
            },
            {
                "type": "per_chunk_max_claims",
                "value": 4,
                "file": str(llm_path),
                "function_or_symbol": "SYSTEM_PROMPT",
                "line_hint": "Extract at most 4 high-value claims from one chunk.",
                "prompt_or_code_text": "Extract at most 4 high-value claims from one chunk.",
                "classification": "possible_recall_loss_quantity_constraint",
            },
            {
                "type": "post_response_truncation",
                "value": 4,
                "file": str(llm_path),
                "function_or_symbol": "_coerce_wrapper",
                "line_hint": "for claim in claims[:4]",
                "prompt_or_code_text": "for claim in claims[:4]",
                "classification": "possible_recall_loss_quantity_constraint",
            },
            {
                "type": "post_response_validation_cap",
                "value": 4,
                "file": str(llm_path),
                "function_or_symbol": "validate_extraction_wrapper",
                "line_hint": "if len(wrapper['claims']) > 4",
                "prompt_or_code_text": 'raise ValueError("LLM response exceeded 4 claims")',
                "classification": "possible_recall_loss_quantity_constraint",
            },
            {
                "type": "router_per_chunk_max_claims",
                "value": "2 for Introduction, otherwise 4 for routed chapters",
                "file": str(router_path),
                "function_or_symbol": "route_chapter",
                "line_hint": 'max_claims = 2 if chapter_norm == "introduction" else 4',
                "prompt_or_code_text": 'max_claims = 2 if chapter_norm == "introduction" else 4',
                "classification": "possible_recall_loss_quantity_constraint",
            },
            {
                "type": "runner_validation_slice",
                "value": "routing['max_claims']",
                "file": str(runner_path),
                "function_or_symbol": "_validate_wrapper",
                "line_hint": 'for claim in claims[: routing["max_claims"]]',
                "prompt_or_code_text": 'for claim in claims[: routing["max_claims"]]',
                "classification": "possible_recall_loss_quantity_constraint",
            },
            {
                "type": "manifest_default_max_claims",
                "value": 4,
                "file": str(runner_path),
                "function_or_symbol": "_candidate_from_manifest_row",
                "line_hint": 'max_claims: int(row.get("max_claims") or 4)',
                "prompt_or_code_text": '"max_claims": int(row.get("max_claims") or 4)',
                "classification": "possible_recall_loss_quantity_constraint",
            },
        ],
        "reasonable_schema_constraints": [
            {
                "type": "closed_wrapper_schema",
                "file": str(llm_path),
                "function_or_symbol": "EXTRACTION_JSON_SCHEMA",
                "line_hint": "additionalProperties: False; required wrapper fields",
                "classification": "reasonable_schema_constraint",
            },
            {
                "type": "controlled_fact_domains",
                "file": str(llm_path),
                "function_or_symbol": "EXTRACTION_JSON_SCHEMA / validate_extraction_wrapper",
                "line_hint": "fact_domain enum and allowed_fact_domains validation",
                "classification": "reasonable_schema_constraint_but_domain_router_can_limit_recall",
            },
            {
                "type": "controlled_predicates",
                "file": str(runner_path),
                "function_or_symbol": "_validate_wrapper",
                "line_hint": "predicate must be in routing['allowed_predicates']",
                "classification": "reasonable_schema_constraint_but_router_can_limit_recall",
            },
            {
                "type": "required_evidence_quote",
                "file": str(runner_path),
                "function_or_symbol": "_validate_wrapper",
                "line_hint": "empty_evidence_quote claims are dropped",
                "classification": "reasonable_traceability_constraint",
            },
            {
                "type": "valid_object_type",
                "file": str(llm_path),
                "function_or_symbol": "EXTRACTION_JSON_SCHEMA / _normalize_object_type",
                "line_hint": "object_type enum: concept, numeric, text, relation",
                "classification": "reasonable_schema_constraint",
            },
        ],
        "not_found": [
            "No per-domain max claims setting was found beyond allowed domain/predicate routing.",
            "No per-species or per-family claim-count cap was found in Step3 claim extraction; caps are per chunk.",
        ],
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt_template": USER_PROMPT_TEMPLATE,
        "source_file_contains": {
            "schema_maxItems_4": '"maxItems": 4' in schema_text,
            "system_prompt_at_most_4": "Extract at most 4 high-value claims from one chunk." in SYSTEM_PROMPT,
            "coerce_claims_slice_4": "claims[:4]" in schema_text,
            "validate_exceeded_4": "exceeded 4 claims" in schema_text,
            "router_intro_max_2": 'chapter_norm == "introduction"' in router_text and "else 4" in router_text,
            "runner_routing_max_claims_slice": 'routing["max_claims"]' in runner_text,
        },
        "prompt_text_from_ast": {
            "system_prompt": _field_text(llm_path, "SYSTEM_PROMPT"),
            "user_prompt_template": _field_text(llm_path, "USER_PROMPT_TEMPLATE"),
        },
    }


def _load_claim_counts(claims_dir: Path) -> tuple[Counter, dict[str, Counter], dict[str, list[dict]]]:
    chunk_claim_counts: Counter = Counter()
    domain_counts_by_chunk: dict[str, Counter] = defaultdict(Counter)
    claims_by_chunk: dict[str, list[dict]] = defaultdict(list)
    for filename in ("species_claims.jsonl", "family_claims.jsonl"):
        for claim in _read_jsonl(claims_dir / filename):
            chunk_id = str(claim.get("source_chunk_id", "") or "").strip()
            if not chunk_id:
                continue
            chunk_claim_counts[chunk_id] += 1
            domain = str(claim.get("fact_domain", "") or "")
            if domain:
                domain_counts_by_chunk[chunk_id][domain] += 1
            claims_by_chunk[chunk_id].append(claim)
    return chunk_claim_counts, domain_counts_by_chunk, claims_by_chunk


def _chunk_max_claims(row: dict) -> int:
    route = route_chapter(str(row.get("source_chapter", "") or ""), str(row.get("source_subchapter", "") or ""))
    if route.get("skip"):
        return 0
    return int(route.get("max_claims") or 0)


def _build_chunk_rows(processed_chunks: list[dict], chunk_claim_counts: Counter) -> list[dict]:
    rows = []
    seen = set()
    for row in processed_chunks:
        chunk_id = str(row.get("chunk_id", "") or row.get("source_chunk_id", "") or "").strip()
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        max_claims = _chunk_max_claims(row)
        claim_count = int(chunk_claim_counts.get(chunk_id, 0))
        rows.append(
            {
                "chunk_id": chunk_id,
                "subject_rank": row.get("subject_rank", ""),
                "subject_taxon_id": row.get("subject_taxon_id", ""),
                "source_doc_id": row.get("source_doc_id", ""),
                "source_chapter": row.get("source_chapter", ""),
                "source_subchapter": row.get("source_subchapter", ""),
                "claim_count": claim_count,
                "max_claims_current_policy": max_claims,
                "at_current_cap": max_claims > 0 and claim_count >= max_claims,
            }
        )
    return rows


def _chapter_stats(chunk_rows: list[dict]) -> list[dict]:
    by_chapter: dict[str, list[int]] = defaultdict(list)
    cap_counts: Counter = Counter()
    exact_cap_counts: Counter = Counter()
    over_cap_counts: Counter = Counter()
    for row in chunk_rows:
        chapter = str(row.get("source_chapter", "") or "")
        by_chapter[chapter].append(int(row["claim_count"]))
        if row["at_current_cap"]:
            cap_counts[chapter] += 1
        if int(row["max_claims_current_policy"]) > 0 and int(row["claim_count"]) == int(row["max_claims_current_policy"]):
            exact_cap_counts[chapter] += 1
        if int(row["max_claims_current_policy"]) > 0 and int(row["claim_count"]) > int(row["max_claims_current_policy"]):
            over_cap_counts[chapter] += 1
    stats = []
    for chapter, values in by_chapter.items():
        row = _stats_for_values(values)
        row["source_chapter"] = chapter
        row["chunks_at_current_cap"] = int(cap_counts.get(chapter, 0))
        row["chunks_exactly_at_current_cap"] = int(exact_cap_counts.get(chapter, 0))
        row["chunks_over_current_cap"] = int(over_cap_counts.get(chapter, 0))
        row["share_at_current_cap"] = _safe_div(row["chunks_at_current_cap"], row["chunk_count"])
        stats.append(row)
    return sorted(stats, key=lambda row: (-row["chunk_count"], row["source_chapter"]))


def _domain_stats(
    chunk_rows: list[dict],
    domain_counts_by_chunk: dict[str, Counter],
) -> list[dict]:
    all_chunk_ids = {row["chunk_id"] for row in chunk_rows}
    per_domain_values: dict[str, list[int]] = defaultdict(list)
    per_domain_positive_chunks: Counter = Counter()
    per_domain_total_claims: Counter = Counter()
    domains = sorted({domain for counts in domain_counts_by_chunk.values() for domain in counts})
    for domain in domains:
        for chunk_id in all_chunk_ids:
            count = int(domain_counts_by_chunk.get(chunk_id, {}).get(domain, 0))
            if count > 0:
                per_domain_values[domain].append(count)
                per_domain_positive_chunks[domain] += 1
                per_domain_total_claims[domain] += count
    rows = []
    denominator = len(all_chunk_ids)
    for domain in domains:
        values = per_domain_values.get(domain, [])
        rows.append(
            {
                "fact_domain": domain,
                "chunks_with_domain_claims": int(per_domain_positive_chunks.get(domain, 0)),
                "domain_claim_total": int(per_domain_total_claims.get(domain, 0)),
                "average_domain_claims_per_all_chunks": _safe_div(per_domain_total_claims.get(domain, 0), denominator),
                "average_domain_claims_per_positive_chunk": _safe_div(per_domain_total_claims.get(domain, 0), len(values)),
                "positive_chunk_distribution": _distribution(values),
            }
        )
    return sorted(rows, key=lambda row: -row["domain_claim_total"])


def _high_info_stats(chunk_rows: list[dict]) -> list[dict]:
    groups: dict[str, list[int]] = defaultdict(list)
    cap_counts: Counter = Counter()
    exact_cap_counts: Counter = Counter()
    over_cap_counts: Counter = Counter()
    for row in chunk_rows:
        group = _chapter_group(str(row.get("source_chapter", "") or ""))
        if not group:
            continue
        groups[group].append(int(row["claim_count"]))
        if row["at_current_cap"]:
            cap_counts[group] += 1
        if int(row["max_claims_current_policy"]) > 0 and int(row["claim_count"]) == int(row["max_claims_current_policy"]):
            exact_cap_counts[group] += 1
        if int(row["max_claims_current_policy"]) > 0 and int(row["claim_count"]) > int(row["max_claims_current_policy"]):
            over_cap_counts[group] += 1
    rows = []
    for group, values in groups.items():
        stats = _stats_for_values(values)
        stats["group"] = group
        stats["chunks_at_current_cap"] = int(cap_counts.get(group, 0))
        stats["chunks_exactly_at_current_cap"] = int(exact_cap_counts.get(group, 0))
        stats["chunks_over_current_cap"] = int(over_cap_counts.get(group, 0))
        stats["share_at_current_cap"] = _safe_div(stats["chunks_at_current_cap"], stats["chunk_count"])
        rows.append(stats)
    return sorted(rows, key=lambda row: row["group"])


def _preview(text: str, *, max_chars: int = 650) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 1].rstrip() + "..."


def _sentence_count(text: str) -> int:
    parts = [part for part in re.split(r"(?<=[.!?])\s+", str(text or "").strip()) if part]
    return len(parts)


def _possible_unextracted_signal(text: str, claim_count: int) -> dict:
    clean = str(text or "")
    numeric_mentions = len(re.findall(r"\b\d+(?:\.\d+)?\b", clean))
    semicolon_count = clean.count(";")
    comma_count = clean.count(",")
    sentences = _sentence_count(clean)
    signal = sentences > claim_count + 1 or numeric_mentions >= 4 or semicolon_count >= 2 or comma_count >= 8
    return {
        "possible_unextracted_fact_signal": bool(signal),
        "heuristic_basis": {
            "sentence_count": sentences,
            "numeric_mentions": numeric_mentions,
            "semicolon_count": semicolon_count,
            "comma_count": comma_count,
        },
    }


def _load_chunk_texts(chunk_ids: set[str], chunk_files: list[Path]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    if not chunk_ids:
        return found
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


def _cap_samples(
    chunk_rows: list[dict],
    claims_by_chunk: dict[str, list[dict]],
    chunk_files: list[Path],
    *,
    sample_size: int,
    seed: int,
) -> list[dict]:
    cap_rows = [row for row in chunk_rows if row["at_current_cap"]]
    rnd = random.Random(seed)
    sampled = rnd.sample(cap_rows, min(sample_size, len(cap_rows))) if cap_rows else []
    chunk_texts = _load_chunk_texts({row["chunk_id"] for row in sampled}, chunk_files)
    samples = []
    for row in sampled:
        chunk = chunk_texts.get(row["chunk_id"], {})
        raw_text = str(chunk.get("raw_text") or chunk.get("chunk_text") or chunk.get("text") or chunk.get("content") or "")
        signal = _possible_unextracted_signal(raw_text, int(row["claim_count"]))
        samples.append(
            {
                "chunk_id": row["chunk_id"],
                "subject_rank": row.get("subject_rank", ""),
                "subject_taxon_id": row.get("subject_taxon_id", ""),
                "source_chapter": row.get("source_chapter", ""),
                "source_subchapter": row.get("source_subchapter", ""),
                "claims_count": int(row["claim_count"]),
                "max_claims_current_policy": int(row["max_claims_current_policy"]),
                "raw_text_preview": _preview(raw_text),
                "raw_text_found": bool(raw_text),
                "claim_predicates": [claim.get("predicate", "") for claim in claims_by_chunk.get(row["chunk_id"], [])],
                "claim_domains": [claim.get("fact_domain", "") for claim in claims_by_chunk.get(row["chunk_id"], [])],
                **signal,
            }
        )
    return samples


def _cap_phenomenon(chunk_rows: list[dict]) -> dict:
    total = len(chunk_rows)
    cap_counts = Counter(int(row["max_claims_current_policy"]) for row in chunk_rows)
    at_cap = [row for row in chunk_rows if row["at_current_cap"]]
    exact_cap = [
        row
        for row in chunk_rows
        if int(row["max_claims_current_policy"]) > 0 and int(row["claim_count"]) == int(row["max_claims_current_policy"])
    ]
    over_cap = [
        row
        for row in chunk_rows
        if int(row["max_claims_current_policy"]) > 0 and int(row["claim_count"]) > int(row["max_claims_current_policy"])
    ]
    by_cap_value: dict[str, dict] = {}
    for max_claims in sorted(cap_counts):
        rows = [row for row in chunk_rows if int(row["max_claims_current_policy"]) == max_claims]
        capped = [row for row in rows if row["at_current_cap"]]
        exact = [row for row in rows if max_claims > 0 and int(row["claim_count"]) == max_claims]
        over = [row for row in rows if max_claims > 0 and int(row["claim_count"]) > max_claims]
        by_cap_value[str(max_claims)] = {
            "chunk_count": len(rows),
            "chunks_at_cap": len(capped),
            "chunks_exactly_at_cap": len(exact),
            "chunks_over_cap": len(over),
            "share_at_cap": _safe_div(len(capped), len(rows)),
            "share_exactly_at_cap": _safe_div(len(exact), len(rows)),
            "share_over_cap": _safe_div(len(over), len(rows)),
        }
    return {
        "total_chunks": total,
        "chunks_at_current_cap": len(at_cap),
        "chunks_exactly_at_current_cap": len(exact_cap),
        "chunks_over_current_cap": len(over_cap),
        "share_at_current_cap": _safe_div(len(at_cap), total),
        "share_exactly_at_current_cap": _safe_div(len(exact_cap), total),
        "share_over_current_cap": _safe_div(len(over_cap), total),
        "by_current_max_claims": by_cap_value,
        "interpretation": (
            "A high share at the current cap is evidence of a ceiling effect. "
            "It cannot prove missing facts by itself, but it indicates the extraction policy may be recall-limited."
        ),
        "over_cap_note": (
            "Chunks over the current per-response cap can occur in the final merged Claim layer when the same source_chunk_id "
            "has multiple non-identical claim rows from duplicate or historical candidate records; this audit reports them separately."
        ),
    }


def _build_markdown(summary: dict) -> str:
    def fmt_int(value: int) -> str:
        return f"{value:,}"

    def fmt_float(value: float) -> str:
        return f"{value:.4f}"

    overview = summary["claim_count_overall"]
    cap = summary["cap_phenomenon"]
    overview_rows = [
        ["Processed unique chunks", fmt_int(overview["chunk_count"])],
        ["Total claims", fmt_int(overview["claim_total"])],
        ["Average claims/chunk", fmt_float(overview["average_claims_per_chunk"])],
        ["0-claim chunks", fmt_int(summary["zero_claim_chunks"])],
        ["Chunks at current cap", fmt_int(cap["chunks_at_current_cap"])],
        ["Chunks exactly at current cap", fmt_int(cap["chunks_exactly_at_current_cap"])],
        ["Chunks over current cap", fmt_int(cap["chunks_over_current_cap"])],
        ["Share at current cap", fmt_float(cap["share_at_current_cap"])],
    ]
    cap_rows = [
        [
            max_claims,
            fmt_int(row["chunk_count"]),
            fmt_int(row["chunks_exactly_at_cap"]),
            fmt_int(row["chunks_over_cap"]),
            fmt_int(row["chunks_at_cap"]),
            fmt_float(row["share_at_cap"]),
        ]
        for max_claims, row in cap["by_current_max_claims"].items()
    ]
    chapter_rows = [
        [
            row["source_chapter"],
            fmt_int(row["chunk_count"]),
            fmt_int(row["claim_total"]),
            fmt_float(row["average_claims_per_chunk"]),
            fmt_int(row["chunks_exactly_at_current_cap"]),
            fmt_int(row["chunks_over_current_cap"]),
            fmt_int(row["chunks_at_current_cap"]),
            fmt_float(row["share_at_current_cap"]),
            json.dumps(row["distribution"], ensure_ascii=False),
        ]
        for row in summary["by_source_chapter"][:40]
    ]
    domain_rows = [
        [
            row["fact_domain"],
            fmt_int(row["chunks_with_domain_claims"]),
            fmt_int(row["domain_claim_total"]),
            fmt_float(row["average_domain_claims_per_all_chunks"]),
            fmt_float(row["average_domain_claims_per_positive_chunk"]),
            json.dumps(row["positive_chunk_distribution"], ensure_ascii=False),
        ]
        for row in summary["by_fact_domain"]
    ]
    high_rows = [
        [
            row["group"],
            fmt_int(row["chunk_count"]),
            fmt_int(row["claim_total"]),
            fmt_float(row["average_claims_per_chunk"]),
            fmt_int(row["chunks_exactly_at_current_cap"]),
            fmt_int(row["chunks_over_current_cap"]),
            fmt_int(row["chunks_at_current_cap"]),
            fmt_float(row["share_at_current_cap"]),
            json.dumps(row["distribution"], ensure_ascii=False),
        ]
        for row in summary["high_information_chapter_groups"]
    ]
    recall_rows = [
        [
            item["type"],
            item["value"],
            Path(item["file"]).name,
            item["function_or_symbol"],
            item["line_hint"],
        ]
        for item in summary["policy_audit"]["recall_sensitive_quantity_constraints"]
    ]
    schema_rows = [
        [item["type"], Path(item["file"]).name, item["function_or_symbol"], item["classification"]]
        for item in summary["policy_audit"]["reasonable_schema_constraints"]
    ]
    sample_rows = [
        [
            row["chunk_id"],
            row["source_chapter"],
            row["claims_count"],
            row["max_claims_current_policy"],
            row["possible_unextracted_fact_signal"],
            row["raw_text_preview"],
        ]
        for row in summary["samples"]["chunks_at_cap"]
    ]
    return "\n\n".join(
        [
            "# Claim Extraction Policy Audit",
            (
                "Read-only audit. It does not rerun the LLM and does not modify Claim, Fact, "
                "or existing intermediate artifacts."
            ),
            "## Recall-sensitive Quantity Constraints\n\n"
            + _markdown_table(["Type", "Value", "File", "Function/Symbol", "Evidence"], recall_rows),
            "## Reasonable Schema Constraints\n\n"
            + _markdown_table(["Type", "File", "Function/Symbol", "Classification"], schema_rows),
            "## Overall Claim Count Distribution\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "Distribution: `" + json.dumps(overview["distribution"], ensure_ascii=False) + "`",
            "## Cap Phenomenon\n\n"
            + _markdown_table(
                ["Current max claims", "Chunks", "Exactly at cap", "Over cap", "At/over cap", "Share at/over cap"],
                cap_rows,
            ),
            cap["interpretation"] + " " + cap["over_cap_note"],
            "## By Source Chapter\n\n"
            + _markdown_table(
                [
                    "Chapter",
                    "Chunks",
                    "Claims",
                    "Avg claims/chunk",
                    "Exactly at cap",
                    "Over cap",
                    "At/over cap",
                    "Share at/over cap",
                    "Distribution",
                ],
                chapter_rows,
            ),
            "## By Fact Domain\n\n"
            + _markdown_table(
                [
                    "Domain",
                    "Chunks with domain claims",
                    "Claims",
                    "Avg/all chunks",
                    "Avg/positive chunk",
                    "Positive distribution",
                ],
                domain_rows,
            ),
            "## High-information Chapter Groups\n\n"
            + _markdown_table(
                [
                    "Group",
                    "Chunks",
                    "Claims",
                    "Avg claims/chunk",
                    "Exactly at cap",
                    "Over cap",
                    "At/over cap",
                    "Share at/over cap",
                    "Distribution",
                ],
                high_rows,
            ),
            "## Chunks At Cap Samples\n\n"
            + _markdown_table(
                ["Chunk ID", "Chapter", "Claims", "Cap", "Possible unextracted signal", "Raw text preview"],
                sample_rows,
            ),
            "## Not Found\n\n" + "\n".join(f"- {item}" for item in summary["policy_audit"]["not_found"]),
        ]
    )


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


def audit_claim_extraction_policy(
    *,
    claims_dir: Path,
    processed_chunks_path: Path,
    species_chunks_path: Path,
    family_chunks_path: Path,
    out_json: Path,
    out_md: Path,
    sample_size: int,
    seed: int,
) -> dict:
    chunk_claim_counts, domain_counts_by_chunk, claims_by_chunk = _load_claim_counts(claims_dir)
    processed_chunks = _read_jsonl(processed_chunks_path)
    chunk_rows = _build_chunk_rows(processed_chunks, chunk_claim_counts)
    claim_values = [int(row["claim_count"]) for row in chunk_rows]

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
        },
        "policy_audit": _extract_policy_sources(),
        "claim_count_overall": _stats_for_values(claim_values),
        "zero_claim_chunks": sum(1 for value in claim_values if value == 0),
        "claim_count_distribution_capped": _capped_distribution(claim_values),
        "cap_phenomenon": _cap_phenomenon(chunk_rows),
        "by_source_chapter": _chapter_stats(chunk_rows),
        "by_fact_domain": _domain_stats(chunk_rows, domain_counts_by_chunk),
        "high_information_chapter_groups": _high_info_stats(chunk_rows),
        "samples": {
            "chunks_at_cap": _cap_samples(
                chunk_rows,
                claims_by_chunk,
                [species_chunks_path, family_chunks_path],
                sample_size=sample_size,
                seed=seed,
            )
        },
        "notes": [
            "0-claim chunks are counted from processed_unique_chunks.jsonl minus final claims by source_chunk_id.",
            "Chunk-at-cap means final claim count is greater than or equal to the current router max_claims for that chapter.",
            "possible_unextracted_fact_signal is a local heuristic based on raw text density; it is not an LLM or human judgment.",
        ],
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_json, summary)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Step3 claim extraction caps and claim-count distributions.")
    parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global")
    parser.add_argument("--processed-chunks", default="KG/intermediate/claims_final_global/processed_unique_chunks.jsonl")
    parser.add_argument("--species-chunks", default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    parser.add_argument("--family-chunks", default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    parser.add_argument("--out-json", default="KG/reports/claim_extraction_policy_audit.json")
    parser.add_argument("--out-md", default="KG/reports/claim_extraction_policy_audit.md")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260515)
    args = parser.parse_args()

    summary = audit_claim_extraction_policy(
        claims_dir=_resolve_path(args.claims_dir),
        processed_chunks_path=_resolve_path(args.processed_chunks),
        species_chunks_path=_resolve_path(args.species_chunks),
        family_chunks_path=_resolve_path(args.family_chunks),
        out_json=_resolve_path(args.out_json),
        out_md=_resolve_path(args.out_md),
        sample_size=max(0, args.sample_size),
        seed=args.seed,
    )
    print(f"[Step3][CLAIM_POLICY_AUDIT] json={summary['outputs']['json']}")
    print(f"[Step3][CLAIM_POLICY_AUDIT] md={summary['outputs']['markdown']}")
    print(
        "[Step3][CLAIM_POLICY_AUDIT] "
        f"chunks={summary['claim_count_overall']['chunk_count']} "
        f"claims={summary['claim_count_overall']['claim_total']} "
        f"zero_claim_chunks={summary['zero_claim_chunks']} "
        f"chunks_at_cap={summary['cap_phenomenon']['chunks_at_current_cap']} "
        f"share_at_cap={summary['cap_phenomenon']['share_at_current_cap']:.4f}"
    )


if __name__ == "__main__":
    main()
