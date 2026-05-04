"""Generate species Fact records from rule-based label candidates."""

from __future__ import annotations

import re
from collections import defaultdict

from kg_v2.parsers.normalize_labels import FACT_TYPE_TO_OBJECT_TYPE
from kg_v2.schema.ontology_v2 import INTERMEDIATE_DIR, load_jsonl, write_jsonl

_RELATED_TO_PATTERNS = (
    re.compile(r"\bsister to ([A-Z][a-z]+(?: [a-z][a-z-]+)+)"),
    re.compile(r"\bsimilar to ([A-Z][a-z]+(?: [a-z][a-z-]+)+)"),
    re.compile(r"\bconfused with ([A-Z][a-z]+(?: [a-z][a-z-]+)+)"),
)


def _detect_related_species(species_record: dict) -> list[str]:
    full_text = species_record.get("full_text", "")
    hits: list[str] = []
    for pattern in _RELATED_TO_PATTERNS:
        hits.extend(match.group(1).strip() for match in pattern.finditer(full_text))
    seen = set()
    ordered: list[str] = []
    for hit in hits:
        if hit != species_record.get("species_name") and hit not in seen:
            seen.add(hit)
            ordered.append(hit)
    return ordered[:5]


def build_species_facts(
    species_records_path=INTERMEDIATE_DIR / "species_records.jsonl",
    species_chunks_path=INTERMEDIATE_DIR / "species_chunks.jsonl",
    evidence_chunks_path=INTERMEDIATE_DIR / "evidence_chunks.jsonl",
    candidate_path=INTERMEDIATE_DIR / "species_label_candidates.jsonl",
    claims_path=INTERMEDIATE_DIR / "species_claims.jsonl",
    output_path=INTERMEDIATE_DIR / "species_facts.jsonl",
) -> list[dict]:
    existing_claims = load_jsonl(claims_path)
    if existing_claims:
        fact_rows: list[dict] = []
        counters: defaultdict[str, int] = defaultdict(int)
        for claim in existing_claims:
            if claim.get("value_type") != "entity":
                continue
            predicate = claim.get("predicate")
            if predicate not in {"INHABITS", "OCCURS_IN", "EATS", "HAS_TRAIT", "THREATENED_BY", "HAS_STATUS", "SIMILAR_TO"}:
                continue
            fact_type_map = {
                "INHABITS": "INHABITS",
                "OCCURS_IN": "FOUND_IN",
                "EATS": "PREYS_ON",
                "HAS_TRAIT": "EXHIBITS",
                "THREATENED_BY": "THREATENED_BY",
                "HAS_STATUS": "HAS_STATUS",
                "SIMILAR_TO": "RELATED_TO",
            }
            fact_type = fact_type_map[predicate]
            counters[fact_type] += 1
            fact_rows.append(
                {
                    "fact_id": f"fact_species_{fact_type.lower()}_{counters[fact_type]:06d}",
                    "subject_name": claim.get("subject_name"),
                    "subject_type": claim.get("subject_type", "Species"),
                    "fact_type": fact_type,
                    "object_type": claim.get("object_type"),
                    "object_name": claim.get("object_name"),
                    "source_level": "species",
                    "is_derived": False,
                    "supported_chunk_ids": claim.get("supported_chunk_ids", []),
                    "family_name": claim.get("family_name"),
                    "order_name": claim.get("order_name"),
                    "confidence": claim.get("confidence"),
                }
            )
        write_jsonl(output_path, fact_rows)
        return fact_rows

    species_records = load_jsonl(species_records_path)
    candidates = load_jsonl(candidate_path)
    chunk_lookup = {row["chunk_id"]: row for row in load_jsonl(species_chunks_path)}
    _ = load_jsonl(evidence_chunks_path)

    fact_buckets: dict[tuple[str, str, str, str], dict] = {}
    fact_order = [
        ("INHABITS", "habitat"),
        ("FOUND_IN", "geography"),
        ("PREYS_ON", "diet"),
        ("EXHIBITS", "behavior"),
        ("THREATENED_BY", "threat"),
        ("HAS_STATUS", "conservation_status"),
    ]

    for candidate in candidates:
        for fact_type, field in fact_order:
            values = candidate.get(field, [])
            for value in values:
                object_type = FACT_TYPE_TO_OBJECT_TYPE[fact_type]
                key = (candidate["species_name"], fact_type, object_type, value)
                bucket = fact_buckets.setdefault(
                    key,
                    {
                        "subject_name": candidate["species_name"],
                        "subject_type": "Species",
                        "fact_type": fact_type,
                        "object_type": object_type,
                        "object_name": value,
                        "source_level": "species",
                        "is_derived": False,
                        "supported_chunk_ids": [],
                        "family_name": candidate.get("family_name"),
                        "order_name": candidate.get("order_name"),
                        "confidence_votes": 0,
                    },
                )
                if candidate["chunk_id"] not in bucket["supported_chunk_ids"]:
                    bucket["supported_chunk_ids"].append(candidate["chunk_id"])
                    bucket["confidence_votes"] += 1

    for record in species_records:
        for related_species in _detect_related_species(record):
            key = (record["species_name"], "RELATED_TO", "Species", related_species)
            bucket = fact_buckets.setdefault(
                key,
                {
                    "subject_name": record["species_name"],
                    "subject_type": "Species",
                    "fact_type": "RELATED_TO",
                    "object_type": "Species",
                    "object_name": related_species,
                    "source_level": "species",
                    "is_derived": False,
                    "supported_chunk_ids": [],
                    "family_name": record.get("family_name"),
                    "order_name": record.get("order_name"),
                    "confidence_votes": 1,
                },
            )
            if not bucket["supported_chunk_ids"]:
                for chunk_id, chunk in chunk_lookup.items():
                    if chunk.get("species_name") == record["species_name"] and chunk.get("source_chapter") in ("Systematics", "Identification"):
                        bucket["supported_chunk_ids"].append(chunk_id)
                        break

    fact_rows: list[dict] = []
    counters: defaultdict[str, int] = defaultdict(int)
    ordered_keys = sorted(fact_buckets.keys(), key=lambda item: (item[0], item[1], item[3]))
    for key in ordered_keys:
        bucket = fact_buckets[key]
        counters[bucket["fact_type"]] += 1
        fact_id = f"fact_species_{bucket['fact_type'].lower()}_{counters[bucket['fact_type']]:06d}"
        fact_rows.append(
            {
                "fact_id": fact_id,
                "subject_name": bucket["subject_name"],
                "subject_type": bucket["subject_type"],
                "fact_type": bucket["fact_type"],
                "object_type": bucket["object_type"],
                "object_name": bucket["object_name"],
                "source_level": bucket["source_level"],
                "is_derived": bucket["is_derived"],
                "supported_chunk_ids": bucket["supported_chunk_ids"],
                "family_name": bucket.get("family_name"),
                "order_name": bucket.get("order_name"),
                "confidence": round(min(0.99, 0.55 + 0.1 * bucket["confidence_votes"]), 2),
            }
        )

    write_jsonl(output_path, fact_rows)
    return fact_rows


if __name__ == "__main__":
    build_species_facts()
