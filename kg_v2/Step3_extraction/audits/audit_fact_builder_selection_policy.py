"""Audit conservative Step 3 fact-builder selection policies without writing facts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step3_extraction.evidence_builder import build_evidence_record
from kg_v2.Step3_extraction.fact_builder import (
    _apply_subject_limits,
    _fact_group_key,
    _fact_id_for_group,
    _status_for_fact,
)
from kg_v2.Step3_extraction.normalizers import canonicalize_object, normalize_qualifiers
from kg_v2.Step3_extraction.predicate_registry import FAMILY_DOMAIN_FACT_QUOTAS, SPECIES_DOMAIN_FACT_QUOTAS
from kg_v2.utils.jsonl_utils import write_json


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


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _fmt_float(value: float) -> str:
    return f"{value:.4f}"


def _object_label(fact: dict) -> str:
    name = str(fact.get("object_canonical_name", "") or "").strip()
    object_id = str(fact.get("object_canonical_id", "") or "").strip()
    value_min = fact.get("value_min")
    value_max = fact.get("value_max")
    unit = str(fact.get("unit", "") or "").strip()
    if name:
        return name
    if object_id:
        return object_id
    if value_min is not None or value_max is not None:
        if value_min is not None and value_max is not None and value_min != value_max:
            return f"{value_min}-{value_max} {unit}".strip()
        value = value_min if value_min is not None else value_max
        return f"{value} {unit}".strip()
    return str(fact.get("object_text", "") or "").strip()


def _make_fact_candidate(group_key: tuple, group_claims: list[dict], *, subject_rank: str) -> dict:
    first = group_claims[0]
    object_id, object_name = canonicalize_object(first)
    qualifiers_norm = normalize_qualifiers(first.get("qualifiers_raw", {}))
    confidence = sum(float(claim.get("confidence", 0.0)) for claim in group_claims) / len(group_claims)
    return {
        "fact_id": _fact_id_for_group(group_key),
        "subject_taxon_id": first.get("subject_taxon_id", ""),
        "subject_rank": first.get("subject_rank", subject_rank),
        "fact_domain": first.get("fact_domain", ""),
        "predicate": first.get("predicate", ""),
        "object_type": first.get("object_type", ""),
        "object_canonical_id": object_id,
        "object_canonical_name": object_name,
        "object_text": first.get("object_text", ""),
        "value_min": first.get("value_min"),
        "value_max": first.get("value_max"),
        "unit": first.get("unit", ""),
        "qualifiers_norm": qualifiers_norm,
        "support_count": len(group_claims),
        "confidence": round(confidence, 4),
        "status": _status_for_fact(group_claims, object_id, object_name),
    }


def _group_claims(claims: list[dict], *, subject_rank: str) -> tuple[list[dict], dict[str, list[dict]]]:
    grouped_claims: dict[tuple, list[dict]] = defaultdict(list)
    for claim in claims:
        grouped_claims[_fact_group_key(claim)].append(claim)

    candidates: list[dict] = []
    claims_by_fact_id: dict[str, list[dict]] = {}
    for group_key, group_claims in grouped_claims.items():
        fact = _make_fact_candidate(group_key, group_claims, subject_rank=subject_rank)
        candidates.append(fact)
        claims_by_fact_id[fact["fact_id"]] = group_claims
    return candidates, claims_by_fact_id


def _select_with_current_policy(candidates: list[dict], *, subject_rank: str) -> list[dict]:
    facts_by_subject: dict[str, list[dict]] = defaultdict(list)
    for fact in candidates:
        facts_by_subject[str(fact.get("subject_taxon_id", "") or "")].append(fact)

    selected: list[dict] = []
    for subject_facts in facts_by_subject.values():
        selected.extend(_apply_subject_limits(subject_facts, subject_rank))
    return selected


def _count_claims_by_field(claims: list[dict], field: str) -> Counter:
    return Counter(str(row.get(field, "") or "") for row in claims)


def _count_facts_by_field(facts: list[dict], field: str) -> Counter:
    return Counter(str(row.get(field, "") or "") for row in facts)


def _breakdown_rows(claims: list[dict], candidates: list[dict], selected: list[dict], field: str) -> list[dict]:
    claim_counts = _count_claims_by_field(claims, field)
    candidate_counts = _count_facts_by_field(candidates, field)
    selected_counts = _count_facts_by_field(selected, field)
    values = sorted(set(claim_counts) | set(candidate_counts) | set(selected_counts))
    rows = []
    for value in values:
        candidate_count = candidate_counts.get(value, 0)
        selected_count = selected_counts.get(value, 0)
        rows.append(
            {
                field: value,
                "raw_claim_count": claim_counts.get(value, 0),
                "raw_fact_candidate_count_before_quota": candidate_count,
                "selected_fact_count_after_quota": selected_count,
                "dropped_fact_candidate_count_due_to_quota": candidate_count - selected_count,
                "claim_to_selected_fact_ratio": _safe_div(claim_counts.get(value, 0), selected_count),
                "candidate_to_selected_fact_ratio": _safe_div(candidate_count, selected_count),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -int(row["dropped_fact_candidate_count_due_to_quota"]),
            -int(row["raw_fact_candidate_count_before_quota"]),
            str(row[field]),
        ),
    )


def _unique_evidence_ids(claims: list[dict]) -> list[str]:
    seen: set[str] = set()
    evidence_ids: list[str] = []
    for claim in claims:
        evidence_id = build_evidence_record(claim)["evidence_id"]
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        evidence_ids.append(evidence_id)
    return evidence_ids


def _source_chunk_ids(claims: list[dict], *, limit: int = 20) -> list[str]:
    values = []
    seen = set()
    for claim in claims:
        chunk_id = str(claim.get("source_chunk_id", "") or "").strip()
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        values.append(chunk_id)
        if len(values) >= limit:
            break
    return values


def _fact_sample(fact: dict, claims_by_fact_id: dict[str, list[dict]]) -> dict:
    claims = claims_by_fact_id.get(str(fact.get("fact_id", "") or ""), [])
    potential_evidence_count = len(_unique_evidence_ids(claims))
    return {
        "fact_id": fact.get("fact_id", ""),
        "subject_taxon_id": fact.get("subject_taxon_id", ""),
        "subject_rank": fact.get("subject_rank", ""),
        "fact_domain": fact.get("fact_domain", ""),
        "predicate": fact.get("predicate", ""),
        "object": _object_label(fact),
        "support_count": fact.get("support_count", 0),
        "potential_unique_evidence_link_count": potential_evidence_count,
        "kept_evidence_link_count_under_current_policy": min(potential_evidence_count, 2),
        "source_chunk_ids": _source_chunk_ids(claims),
    }


def _evidence_cap_summary(selected: list[dict], claims_by_fact_id: dict[str, list[dict]]) -> dict:
    potential_link_count = 0
    kept_link_count = 0
    affected_fact_count = 0
    support_gt_2_fact_count = 0
    selected_with_support = []
    for fact in selected:
        claims = claims_by_fact_id.get(str(fact.get("fact_id", "") or ""), [])
        unique_evidence_count = len(_unique_evidence_ids(claims))
        kept_count = min(unique_evidence_count, 2)
        potential_link_count += unique_evidence_count
        kept_link_count += kept_count
        if unique_evidence_count > 2:
            affected_fact_count += 1
        if int(fact.get("support_count") or 0) > 2:
            support_gt_2_fact_count += 1
        if int(fact.get("support_count") or 0) > 2 and kept_count == 2:
            selected_with_support.append(fact)

    fact_count = len(selected)
    return {
        "selected_fact_count_considered": fact_count,
        "full_potential_evidence_link_count_before_max_2_cap": potential_link_count,
        "kept_evidence_link_count_after_max_2_cap": kept_link_count,
        "dropped_evidence_link_count_due_to_max_2_cap": potential_link_count - kept_link_count,
        "affected_fact_count_with_more_than_2_unique_evidences": affected_fact_count,
        "support_count_gt_2_fact_count": support_gt_2_fact_count,
        "average_potential_unique_evidence_links_per_selected_fact": _safe_div(potential_link_count, fact_count),
        "average_kept_evidence_links_per_selected_fact": _safe_div(kept_link_count, fact_count),
        "cap_sample_source_fact_ids": [fact.get("fact_id", "") for fact in selected_with_support[:10]],
    }


def _rank_audit(claims: list[dict], *, subject_rank: str, sample_limit: int) -> dict:
    candidates, claims_by_fact_id = _group_claims(claims, subject_rank=subject_rank)
    selected = _select_with_current_policy(candidates, subject_rank=subject_rank)
    selected_object_ids = {id(fact) for fact in selected}
    dropped = [fact for fact in candidates if id(fact) not in selected_object_ids]
    candidate_fact_id_counts = Counter(str(fact.get("fact_id", "") or "") for fact in candidates)
    selected_fact_id_counts = Counter(str(fact.get("fact_id", "") or "") for fact in selected)
    candidate_collision_ids = sorted(fact_id for fact_id, count in candidate_fact_id_counts.items() if fact_id and count > 1)
    selected_collision_ids = sorted(fact_id for fact_id, count in selected_fact_id_counts.items() if fact_id and count > 1)

    dropped_sample_facts = sorted(
        dropped,
        key=lambda row: (-int(row.get("support_count") or 0), -float(row.get("confidence") or 0.0), row.get("fact_id", "")),
    )[:sample_limit]
    cap_sample_candidates = []
    for fact in sorted(selected, key=lambda row: (-int(row.get("support_count") or 0), row.get("fact_id", ""))):
        group_claims = claims_by_fact_id.get(str(fact.get("fact_id", "") or ""), [])
        if int(fact.get("support_count") or 0) > 2 and len(_unique_evidence_ids(group_claims)) > 2:
            cap_sample_candidates.append(fact)
        if len(cap_sample_candidates) >= sample_limit:
            break

    return {
        "subject_rank": subject_rank,
        "raw_claim_count": len(claims),
        "raw_grouped_fact_candidate_count_before_quota": len(candidates),
        "selected_fact_count_after_subject_domain_quota": len(selected),
        "dropped_fact_candidate_count_due_to_quota": len(dropped),
        "claim_to_raw_candidate_ratio": _safe_div(len(claims), len(candidates)),
        "claim_to_selected_fact_ratio": _safe_div(len(claims), len(selected)),
        "raw_candidate_to_selected_fact_ratio": _safe_div(len(candidates), len(selected)),
        "fact_id_collision_count_before_quota": len(candidate_collision_ids),
        "fact_id_collision_candidate_excess_before_quota": sum(candidate_fact_id_counts[fact_id] - 1 for fact_id in candidate_collision_ids),
        "fact_id_collision_examples_before_quota": candidate_collision_ids[:20],
        "fact_id_duplicate_count_after_quota": len(selected_collision_ids),
        "fact_id_duplicate_excess_after_quota": sum(selected_fact_id_counts[fact_id] - 1 for fact_id in selected_collision_ids),
        "fact_id_duplicate_examples_after_quota": selected_collision_ids[:20],
        "by_fact_domain": _breakdown_rows(claims, candidates, selected, "fact_domain"),
        "by_predicate": _breakdown_rows(claims, candidates, selected, "predicate"),
        "evidence_cap": _evidence_cap_summary(selected, claims_by_fact_id),
        "quota_dropped_samples": [_fact_sample(fact, claims_by_fact_id) for fact in dropped_sample_facts],
        "max_2_evidence_cap_samples": [_fact_sample(fact, claims_by_fact_id) for fact in cap_sample_candidates],
    }


def _combine_breakdowns(rank_audits: list[dict], key: str, field: str) -> list[dict]:
    combined: dict[str, Counter] = defaultdict(Counter)
    for audit in rank_audits:
        for row in audit[key]:
            value = str(row.get(field, "") or "")
            combined[value]["raw_claim_count"] += int(row["raw_claim_count"])
            combined[value]["raw_fact_candidate_count_before_quota"] += int(row["raw_fact_candidate_count_before_quota"])
            combined[value]["selected_fact_count_after_quota"] += int(row["selected_fact_count_after_quota"])
            combined[value]["dropped_fact_candidate_count_due_to_quota"] += int(row["dropped_fact_candidate_count_due_to_quota"])
    rows = []
    for value, counts in combined.items():
        selected = counts["selected_fact_count_after_quota"]
        candidates = counts["raw_fact_candidate_count_before_quota"]
        claims = counts["raw_claim_count"]
        rows.append(
            {
                field: value,
                "raw_claim_count": claims,
                "raw_fact_candidate_count_before_quota": candidates,
                "selected_fact_count_after_quota": selected,
                "dropped_fact_candidate_count_due_to_quota": counts["dropped_fact_candidate_count_due_to_quota"],
                "claim_to_selected_fact_ratio": _safe_div(claims, selected),
                "candidate_to_selected_fact_ratio": _safe_div(candidates, selected),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -int(row["dropped_fact_candidate_count_due_to_quota"]),
            -int(row["raw_fact_candidate_count_before_quota"]),
            str(row[field]),
        ),
    )


def _combine_evidence_caps(rank_audits: list[dict]) -> dict:
    total_selected = sum(int(audit["evidence_cap"]["selected_fact_count_considered"]) for audit in rank_audits)
    potential = sum(int(audit["evidence_cap"]["full_potential_evidence_link_count_before_max_2_cap"]) for audit in rank_audits)
    kept = sum(int(audit["evidence_cap"]["kept_evidence_link_count_after_max_2_cap"]) for audit in rank_audits)
    affected = sum(int(audit["evidence_cap"]["affected_fact_count_with_more_than_2_unique_evidences"]) for audit in rank_audits)
    support_gt_2 = sum(int(audit["evidence_cap"]["support_count_gt_2_fact_count"]) for audit in rank_audits)
    return {
        "selected_fact_count_considered": total_selected,
        "full_potential_evidence_link_count_before_max_2_cap": potential,
        "kept_evidence_link_count_after_max_2_cap": kept,
        "dropped_evidence_link_count_due_to_max_2_cap": potential - kept,
        "affected_fact_count_with_more_than_2_unique_evidences": affected,
        "support_count_gt_2_fact_count": support_gt_2,
        "average_potential_unique_evidence_links_per_selected_fact": _safe_div(potential, total_selected),
        "average_kept_evidence_links_per_selected_fact": _safe_div(kept, total_selected),
    }


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


def _sample_rows(samples: list[dict]) -> list[list[Any]]:
    return [
        [
            row["subject_rank"],
            row["subject_taxon_id"],
            row["predicate"],
            row["object"],
            row["support_count"],
            row["potential_unique_evidence_link_count"],
            ", ".join(row["source_chunk_ids"][:5]),
        ]
        for row in samples
    ]


def _build_markdown(summary: dict) -> str:
    overview = summary["overall"]
    fact_rows = [
        ["Raw claims", _fmt_int(overview["raw_claim_count"])],
        ["Raw grouped fact candidates before quota", _fmt_int(overview["raw_grouped_fact_candidate_count_before_quota"])],
        ["Selected facts after quota", _fmt_int(overview["selected_fact_count_after_subject_domain_quota"])],
        ["Dropped fact candidates due to quota", _fmt_int(overview["dropped_fact_candidate_count_due_to_quota"])],
        ["Claim/raw candidate ratio", _fmt_float(overview["claim_to_raw_candidate_ratio"])],
        ["Claim/selected fact ratio", _fmt_float(overview["claim_to_selected_fact_ratio"])],
        ["Raw candidate/selected fact ratio", _fmt_float(overview["raw_candidate_to_selected_fact_ratio"])],
    ]
    rank_rows = [
        [
            audit["subject_rank"],
            _fmt_int(audit["raw_claim_count"]),
            _fmt_int(audit["raw_grouped_fact_candidate_count_before_quota"]),
            _fmt_int(audit["selected_fact_count_after_subject_domain_quota"]),
            _fmt_int(audit["dropped_fact_candidate_count_due_to_quota"]),
        ]
        for audit in summary["by_subject_rank"]
    ]
    evidence = summary["evidence_cap_overall"]
    evidence_rows = [
        ["Selected facts considered", _fmt_int(evidence["selected_fact_count_considered"])],
        ["Potential unique evidence links before max-2 cap", _fmt_int(evidence["full_potential_evidence_link_count_before_max_2_cap"])],
        ["Kept evidence links after max-2 cap", _fmt_int(evidence["kept_evidence_link_count_after_max_2_cap"])],
        ["Dropped evidence links due to max-2 cap", _fmt_int(evidence["dropped_evidence_link_count_due_to_max_2_cap"])],
        ["Facts with >2 unique evidences", _fmt_int(evidence["affected_fact_count_with_more_than_2_unique_evidences"])],
        ["Facts with support_count > 2", _fmt_int(evidence["support_count_gt_2_fact_count"])],
        [
            "Average potential unique evidence links per selected fact",
            _fmt_float(evidence["average_potential_unique_evidence_links_per_selected_fact"]),
        ],
    ]
    collision = summary["fact_id_collision_sanity"]
    collision_rows = [
        ["Candidate fact_id collision count before quota", _fmt_int(collision["fact_id_collision_count_before_quota"])],
        ["Candidate collision excess before quota", _fmt_int(collision["fact_id_collision_candidate_excess_before_quota"])],
        ["Selected duplicate fact_id count after quota", _fmt_int(collision["fact_id_duplicate_count_after_quota"])],
        ["Selected duplicate fact_id excess after quota", _fmt_int(collision["fact_id_duplicate_excess_after_quota"])],
    ]
    domain_rows = [
        [
            row["fact_domain"],
            _fmt_int(row["raw_claim_count"]),
            _fmt_int(row["raw_fact_candidate_count_before_quota"]),
            _fmt_int(row["selected_fact_count_after_quota"]),
            _fmt_int(row["dropped_fact_candidate_count_due_to_quota"]),
        ]
        for row in summary["by_fact_domain"]
    ]
    predicate_rows = [
        [
            row["predicate"],
            _fmt_int(row["raw_claim_count"]),
            _fmt_int(row["raw_fact_candidate_count_before_quota"]),
            _fmt_int(row["selected_fact_count_after_quota"]),
            _fmt_int(row["dropped_fact_candidate_count_due_to_quota"]),
        ]
        for row in summary["by_predicate"][:50]
    ]
    quota_samples = summary["samples"]["quota_dropped_fact_candidates"]
    cap_samples = summary["samples"]["max_2_evidence_cap_facts"]
    return "\n\n".join(
        [
            "# Fact Builder Selection Policy Audit",
            (
                "This is a read-only audit. It reads only `claims_final_global/species_claims.jsonl` "
                "and `claims_final_global/family_claims.jsonl`, reuses the current fact grouping and "
                "subject/domain quota selection policy, and does not write or regenerate fact artifacts."
            ),
            "## Current Policies Audited\n\n"
            + _markdown_table(
                ["Policy", "Current value"],
                [
                    ["Species subject hard limit", summary["policy"]["species_subject_hard_limit"]],
                    ["Family subject hard limit", summary["policy"]["family_subject_hard_limit"]],
                    ["Max evidence links per selected fact", summary["policy"]["max_evidence_links_per_fact"]],
                    ["Evidence cap scope", summary["policy"]["evidence_cap_scope"]],
                ],
            ),
            "## Fact Group Overview\n\n" + _markdown_table(["Metric", "Value"], fact_rows),
            "## By Subject Rank\n\n"
            + _markdown_table(["Rank", "Claims", "Candidates before quota", "Selected", "Dropped"], rank_rows),
            "## Evidence Cap Overview\n\n" + _markdown_table(["Metric", "Value"], evidence_rows),
            "## Fact ID Collision Sanity\n\n" + _markdown_table(["Metric", "Value"], collision_rows),
            "## By Fact Domain\n\n"
            + _markdown_table(["Domain", "Claims", "Candidates before quota", "Selected", "Dropped"], domain_rows),
            "## Top Predicates By Dropped Candidates\n\n"
            + _markdown_table(["Predicate", "Claims", "Candidates before quota", "Selected", "Dropped"], predicate_rows),
            "## Quota-dropped Fact Candidate Samples\n\n"
            + _markdown_table(
                ["Rank", "Taxon", "Predicate", "Object", "Support", "Potential evidences", "Chunk IDs"],
                _sample_rows(quota_samples),
            ),
            "## Max-2 Evidence Cap Samples\n\n"
            + _markdown_table(
                ["Rank", "Taxon", "Predicate", "Object", "Support", "Potential evidences", "Chunk IDs"],
                _sample_rows(cap_samples),
            ),
        ]
    )


def audit_selection_policy(*, claims_dir: Path, out_json: Path, out_md: Path, sample_limit: int) -> dict:
    species_claims = _read_jsonl(claims_dir / "species_claims.jsonl")
    family_claims = _read_jsonl(claims_dir / "family_claims.jsonl")

    species_audit = _rank_audit(species_claims, subject_rank="species", sample_limit=sample_limit)
    family_audit = _rank_audit(family_claims, subject_rank="family", sample_limit=sample_limit)
    rank_audits = [species_audit, family_audit]

    raw_claim_count = species_audit["raw_claim_count"] + family_audit["raw_claim_count"]
    raw_candidate_count = (
        species_audit["raw_grouped_fact_candidate_count_before_quota"]
        + family_audit["raw_grouped_fact_candidate_count_before_quota"]
    )
    selected_count = (
        species_audit["selected_fact_count_after_subject_domain_quota"]
        + family_audit["selected_fact_count_after_subject_domain_quota"]
    )
    dropped_count = species_audit["dropped_fact_candidate_count_due_to_quota"] + family_audit[
        "dropped_fact_candidate_count_due_to_quota"
    ]
    collision_sanity = {
        "fact_id_collision_count_before_quota": (
            species_audit["fact_id_collision_count_before_quota"] + family_audit["fact_id_collision_count_before_quota"]
        ),
        "fact_id_collision_candidate_excess_before_quota": (
            species_audit["fact_id_collision_candidate_excess_before_quota"]
            + family_audit["fact_id_collision_candidate_excess_before_quota"]
        ),
        "fact_id_collision_examples_before_quota": (
            species_audit["fact_id_collision_examples_before_quota"] + family_audit["fact_id_collision_examples_before_quota"]
        )[:20],
        "fact_id_duplicate_count_after_quota": (
            species_audit["fact_id_duplicate_count_after_quota"] + family_audit["fact_id_duplicate_count_after_quota"]
        ),
        "fact_id_duplicate_excess_after_quota": (
            species_audit["fact_id_duplicate_excess_after_quota"] + family_audit["fact_id_duplicate_excess_after_quota"]
        ),
        "fact_id_duplicate_examples_after_quota": (
            species_audit["fact_id_duplicate_examples_after_quota"] + family_audit["fact_id_duplicate_examples_after_quota"]
        )[:20],
        "note": "This audit counts quota-dropped candidates by object identity, not by fact_id, so hash/id duplicates do not hide dropped candidates.",
    }
    summary = {
        "claims_dir": str(claims_dir),
        "outputs": {
            "json": str(out_json),
            "markdown": str(out_md),
        },
        "policy": {
            "fact_builder_source": "kg_v2.Step3_extraction.fact_builder",
            "grouping_logic": "_fact_group_key + _fact_id_for_group",
            "ranking_and_selection_logic": "_apply_subject_limits",
            "species_subject_hard_limit": 40,
            "family_subject_hard_limit": 18,
            "species_domain_fact_quotas": SPECIES_DOMAIN_FACT_QUOTAS,
            "family_domain_fact_quotas": FAMILY_DOMAIN_FACT_QUOTAS,
            "max_evidence_links_per_fact": 2,
            "evidence_cap_scope": "selected facts after subject/domain quota, matching current build_facts_and_evidence order",
            "potential_evidence_definition": "unique evidence_id per selected fact before applying the max-2 cap",
        },
        "overall": {
            "raw_claim_count": raw_claim_count,
            "raw_grouped_fact_candidate_count_before_quota": raw_candidate_count,
            "selected_fact_count_after_subject_domain_quota": selected_count,
            "dropped_fact_candidate_count_due_to_quota": dropped_count,
            "claim_to_raw_candidate_ratio": _safe_div(raw_claim_count, raw_candidate_count),
            "claim_to_selected_fact_ratio": _safe_div(raw_claim_count, selected_count),
            "raw_candidate_to_selected_fact_ratio": _safe_div(raw_candidate_count, selected_count),
        },
        "by_subject_rank": rank_audits,
        "by_fact_domain": _combine_breakdowns(rank_audits, "by_fact_domain", "fact_domain"),
        "by_predicate": _combine_breakdowns(rank_audits, "by_predicate", "predicate"),
        "evidence_cap_overall": _combine_evidence_caps(rank_audits),
        "fact_id_collision_sanity": collision_sanity,
        "samples": {
            "quota_dropped_fact_candidates": (
                species_audit["quota_dropped_samples"][: sample_limit // 2]
                + family_audit["quota_dropped_samples"][: sample_limit - sample_limit // 2]
            ),
            "max_2_evidence_cap_facts": (
                species_audit["max_2_evidence_cap_samples"][: sample_limit // 2]
                + family_audit["max_2_evidence_cap_samples"][: sample_limit - sample_limit // 2]
            ),
        },
        "note": "Read-only audit only; existing facts_final_global artifacts are not read or modified.",
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_json, summary)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Step3 fact builder quota and max-2 evidence policies.")
    parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global")
    parser.add_argument("--out-json", default="KG/reports/fact_builder_selection_policy_audit.json")
    parser.add_argument("--out-md", default="KG/reports/fact_builder_selection_policy_audit.md")
    parser.add_argument("--sample-limit", type=int, default=10)
    args = parser.parse_args()

    summary = audit_selection_policy(
        claims_dir=_resolve_path(args.claims_dir),
        out_json=_resolve_path(args.out_json),
        out_md=_resolve_path(args.out_md),
        sample_limit=max(1, args.sample_limit),
    )
    print(f"[Step3][FACT_BUILDER_POLICY_AUDIT] json={summary['outputs']['json']}")
    print(f"[Step3][FACT_BUILDER_POLICY_AUDIT] md={summary['outputs']['markdown']}")
    print(
        "[Step3][FACT_BUILDER_POLICY_AUDIT] "
        f"claims={summary['overall']['raw_claim_count']} "
        f"candidates={summary['overall']['raw_grouped_fact_candidate_count_before_quota']} "
        f"selected={summary['overall']['selected_fact_count_after_subject_domain_quota']} "
        f"quota_dropped={summary['overall']['dropped_fact_candidate_count_due_to_quota']} "
        f"evidence_dropped={summary['evidence_cap_overall']['dropped_evidence_link_count_due_to_max_2_cap']}"
    )


if __name__ == "__main__":
    main()
