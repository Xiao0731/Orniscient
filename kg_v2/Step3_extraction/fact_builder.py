"""Lightweight claim-to-fact consolidation for Step 3."""

from __future__ import annotations

import json
import hashlib
import math
from collections import defaultdict

from kg_v2.Step3_extraction.evidence_builder import build_evidence_record
from kg_v2.Step3_extraction.normalizers import canonicalize_object, normalize_qualifiers


def _hashable_key_part(value):
    if isinstance(value, (list, tuple)):
        return tuple(_hashable_key_part(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _hashable_key_part(item)) for key, item in value.items()))
    return value


def _fact_group_key(claim: dict) -> tuple:
    qualifiers_norm = normalize_qualifiers(claim.get("qualifiers_raw", {}))
    object_id, object_name = canonicalize_object(claim)
    object_key = object_id or object_name or claim.get("object_text", "")
    key = (
        claim.get("subject_taxon_id", ""),
        claim.get("subject_rank", ""),
        claim.get("fact_domain", ""),
        claim.get("predicate", ""),
        claim.get("object_type", ""),
        object_key.casefold() if isinstance(object_key, str) else object_key,
        claim.get("value_min"),
        claim.get("value_max"),
        claim.get("unit", ""),
        json.dumps(qualifiers_norm, sort_keys=True, ensure_ascii=False),
    )
    return tuple(_hashable_key_part(part) for part in key)


def _fact_id_for_group(group_key: tuple) -> str:
    raw = json.dumps(_stable_id_key_part(group_key), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "fact_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]


def _stable_id_key_part(value):
    if isinstance(value, tuple):
        return {"type": "tuple", "value": [_stable_id_key_part(item) for item in value]}
    if isinstance(value, list):
        return {"type": "list", "value": [_stable_id_key_part(item) for item in value]}
    if isinstance(value, dict):
        return {
            "type": "dict",
            "value": [
                [str(key), _stable_id_key_part(item)]
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            ],
        }
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return {"type": "number", "value": "NaN"}
        if isinstance(value, float) and math.isinf(value):
            return {"type": "number", "value": "Infinity" if value > 0 else "-Infinity"}
        numeric = float(value)
        if numeric.is_integer():
            return {"type": "number", "value": str(int(numeric))}
        return {"type": "number", "value": format(numeric, ".17g")}
    return {"type": type(value).__name__, "value": value}


def _status_for_fact(claims: list[dict], object_id: str, object_name: str) -> str:
    avg_confidence = sum(float(claim.get("confidence", 0.0)) for claim in claims) / len(claims)
    object_type = claims[0].get("object_type", "text")
    if avg_confidence < 0.55:
        return "low_confidence"
    if object_type in {"concept", "relation"} and not object_id and not object_name:
        return "unresolved_object"
    return "active"


def build_facts_and_evidence(claims: list[dict], *, subject_rank: str) -> tuple[list[dict], list[dict], list[dict]]:
    grouped_claims: dict[tuple, list[dict]] = defaultdict(list)
    for claim in claims:
        grouped_claims[_fact_group_key(claim)].append(claim)

    facts: list[dict] = []
    fact_claims: dict[str, list[dict]] = {}
    for group_key, group_claims in grouped_claims.items():
        first = group_claims[0]
        object_id, object_name = canonicalize_object(first)
        qualifiers_norm = normalize_qualifiers(first.get("qualifiers_raw", {}))
        fact_id = _fact_id_for_group(group_key)
        confidence = sum(float(claim.get("confidence", 0.0)) for claim in group_claims) / len(group_claims)
        fact = {
            "fact_id": fact_id,
            "subject_taxon_id": first.get("subject_taxon_id", ""),
            "subject_rank": first.get("subject_rank", subject_rank),
            "fact_domain": first.get("fact_domain", ""),
            "predicate": first.get("predicate", ""),
            "object_type": first.get("object_type", ""),
            "object_canonical_id": object_id,
            "object_canonical_name": object_name,
            "value_min": first.get("value_min"),
            "value_max": first.get("value_max"),
            "unit": first.get("unit", ""),
            "qualifiers_norm": qualifiers_norm,
            "support_count": len(group_claims),
            "confidence": round(confidence, 4),
            "status": _status_for_fact(group_claims, object_id, object_name),
        }
        facts.append(fact)
        fact_claims[fact_id] = group_claims

    selected_facts = sorted(
        facts,
        key=lambda row: (
            row.get("subject_rank", ""),
            row.get("subject_taxon_id", ""),
            row.get("fact_domain", ""),
            row.get("predicate", ""),
            row.get("fact_id", ""),
        ),
    )

    selected_fact_ids = {fact["fact_id"] for fact in selected_facts}
    evidence_by_id: dict[str, dict] = {}
    fact_evidence_links: list[dict] = []
    for fact in selected_facts:
        seen_evidence: set[str] = set()
        for claim in fact_claims.get(fact["fact_id"], []):
            evidence = build_evidence_record(claim)
            evidence_id = evidence["evidence_id"]
            if evidence_id in seen_evidence:
                continue
            if fact["fact_id"] not in selected_fact_ids:
                continue
            evidence_by_id[evidence_id] = evidence
            fact_evidence_links.append({"fact_id": fact["fact_id"], "evidence_id": evidence_id})
            seen_evidence.add(evidence_id)

    evidences = sorted(evidence_by_id.values(), key=lambda row: row.get("evidence_id", ""))
    fact_evidence_links = sorted(fact_evidence_links, key=lambda row: (row.get("fact_id", ""), row.get("evidence_id", "")))
    return selected_facts, evidences, fact_evidence_links
