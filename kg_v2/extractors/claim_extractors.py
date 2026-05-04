"""Main V2.1 species claim extraction."""

from __future__ import annotations

from collections import defaultdict
import re

from kg_v2.extractors.measurement_extractors import extract_measurements
from kg_v2.parsers.normalize_text import clean_text
from kg_v2.parsers.normalize_labels import (
    BEHAVIOR_RULES,
    BREEDING_RULES,
    CONSERVATION_ACTION_RULES,
    DIET_RULES,
    GEOGRAPHY_RULES,
    HABITAT_RULES,
    MOVEMENT_RULES,
    NEST_SITE_RULES,
    RESEARCH_PRIORITY_RULES,
    THREAT_RULES,
    VOCAL_RULES,
    canonical_status,
    extract_labels,
)
from kg_v2.schema.ontology_v2 import INTERMEDIATE_DIR, load_jsonl, write_jsonl

CLAIM_RULE_SPECS = [
    ("INHABITS", "Habitat", HABITAT_RULES),
    ("OCCURS_IN", "Geography", GEOGRAPHY_RULES),
    ("EATS", "Food", DIET_RULES),
    ("HAS_TRAIT", "Behavior", BEHAVIOR_RULES),
    ("HAS_TRAIT", "Behavior", MOVEMENT_RULES),
    ("HAS_VOCALIZATION", "Behavior", VOCAL_RULES),
    ("HAS_TRAIT", "Behavior", BREEDING_RULES),
    ("NESTS_AT", "Behavior", NEST_SITE_RULES),
    ("THREATENED_BY", "Threat", THREAT_RULES),
    ("MANAGED_BY", "Behavior", CONSERVATION_ACTION_RULES),
    ("REQUIRES_RESEARCH", "Behavior", RESEARCH_PRIORITY_RULES),
]

CHAPTER_RULE_MAP = {
    "Habitat": {"INHABITS", "OCCURS_IN"},
    "Distribution": {"OCCURS_IN"},
    "MovementAndMigration": {"HAS_TRAIT", "OCCURS_IN"},
    "DietAndForaging": {"EATS", "FORAGES_BY"},
    "VocalBehavior": {"HAS_VOCALIZATION"},
    "Locomotion": {"HAS_TRAIT"},
    "SocialBehavior": {"HAS_TRAIT"},
    "SexualBehavior": {"HAS_TRAIT"},
    "BreedingPhenology": {"HAS_TRAIT"},
    "NestAndEggs": {"NESTS_AT"},
    "IncubationAndParentalCare": {"HAS_TRAIT", "NESTS_AT"},
    "Conservation": {"THREATENED_BY", "MANAGED_BY"},
    "FutureResearch": {"REQUIRES_RESEARCH"},
}

MAX_CLAIMS_PER_SPECIES_AND_PREDICATE = {
    "INHABITS": 4,
    "OCCURS_IN": 4,
    "EATS": 4,
    "FORAGES_BY": 3,
    "HAS_TRAIT": 10,
    "HAS_VOCALIZATION": 4,
    "NESTS_AT": 3,
    "THREATENED_BY": 3,
    "MANAGED_BY": 3,
    "REQUIRES_RESEARCH": 3,
    "HAS_STATUS": 1,
    "BODY_LENGTH": 2,
    "BODY_MASS": 2,
    "ELEVATION_RANGE": 1,
    "CLUTCH_SIZE": 2,
    "INCUBATION_PERIOD": 2,
    "FLEDGING_PERIOD": 2,
    "LIFESPAN": 1,
    "TAXONOMY_NOTE": 2,
    "BREEDING_PROFILE": 2,
    "CONSERVATION_PROFILE": 2,
    "FUTURE_RESEARCH": 2,
}

SUMMARY_CHAPTER_TO_PREDICATE = {
    "Systematics": "TAXONOMY_NOTE",
    "BreedingPhenology": "BREEDING_PROFILE",
    "NestAndEggs": "BREEDING_PROFILE",
    "IncubationAndParentalCare": "BREEDING_PROFILE",
    "Conservation": "CONSERVATION_PROFILE",
    "FutureResearch": "FUTURE_RESEARCH",
}


def _make_claim(
    claim_id: str,
    species_record: dict,
    chunk: dict,
    *,
    predicate: str,
    object_type: str | None = None,
    object_name: str | None = None,
    value_type: str = "entity",
    value_min: float | None = None,
    value_max: float | None = None,
    value_text: str | None = None,
    unit: str | None = None,
    qualifiers: dict | None = None,
    confidence: float = 0.7,
    supported_chunk_ids: list[str] | None = None,
) -> dict:
    return {
        "claim_id": claim_id,
        "subject_name": species_record.get("species_name"),
        "subject_type": "Species",
        "predicate": predicate,
        "object_type": object_type,
        "object_name": object_name,
        "value_type": value_type,
        "value_min": value_min,
        "value_max": value_max,
        "value_text": value_text,
        "unit": unit,
        "qualifiers": qualifiers or {},
        "source_chapter": chunk.get("source_chapter", "Unknown"),
        "source_subchapter": chunk.get("source_subchapter", "Unknown"),
        "supported_chunk_ids": (supported_chunk_ids or [chunk.get("chunk_id")])[:2],
        "confidence": confidence,
        "family_name": species_record.get("family_name"),
        "order_name": species_record.get("order_name"),
    }


def build_species_claims(
    species_records_path=INTERMEDIATE_DIR / "species_records.jsonl",
    species_chunks_path=INTERMEDIATE_DIR / "species_chunks.jsonl",
    output_path=INTERMEDIATE_DIR / "species_claims.jsonl",
) -> list[dict]:
    species_records = {row["species_name"]: row for row in load_jsonl(species_records_path)}
    species_chunks = load_jsonl(species_chunks_path)

    claim_buckets: dict[tuple, dict] = {}
    claim_counter = 0

    for chunk in species_chunks:
        species_record = species_records.get(chunk.get("species_name"))
        if not species_record:
            continue
        text = chunk.get("raw_text", "")
        allowed_predicates = CHAPTER_RULE_MAP.get(chunk.get("source_chapter"), set())

        for predicate, object_type, rule_map in CLAIM_RULE_SPECS:
            if predicate not in allowed_predicates:
                continue
            for object_name in extract_labels(text, rule_map, max_n=4):
                key = (species_record["species_name"], predicate, object_type, object_name, chunk.get("source_chapter"))
                bucket = claim_buckets.get(key)
                if bucket is None:
                    claim_counter += 1
                    bucket = _make_claim(
                        f"claim_species_{claim_counter:07d}",
                        species_record,
                        chunk,
                        predicate=predicate,
                        object_type=object_type,
                        object_name=object_name,
                        value_type="entity",
                        confidence=0.72,
                    )
                    claim_buckets[key] = bucket
                elif chunk["chunk_id"] not in bucket["supported_chunk_ids"]:
                    bucket["supported_chunk_ids"] = (bucket["supported_chunk_ids"] + [chunk["chunk_id"]])[:2]

        for measurement in extract_measurements(text):
            key = (
                species_record["species_name"],
                measurement["predicate"],
                measurement["value_min"],
                measurement["value_max"],
                chunk.get("source_chapter"),
            )
            if key not in claim_buckets:
                claim_counter += 1
                claim_buckets[key] = _make_claim(
                    f"claim_species_{claim_counter:07d}",
                    species_record,
                    chunk,
                    predicate=measurement["predicate"],
                    value_type=measurement["value_type"],
                    value_min=measurement["value_min"],
                    value_max=measurement["value_max"],
                    value_text=measurement["value_text"],
                    unit=measurement["unit"],
                    qualifiers=measurement["qualifiers"],
                    confidence=0.78,
                )

        summary_predicate = SUMMARY_CHAPTER_TO_PREDICATE.get(chunk.get("source_chapter"))
        if summary_predicate and text:
            cleaned_summary = clean_text(text)
            first_sentence = re.split(r"(?<=[.!?])\s+", cleaned_summary)[0]
            summary_text = " ".join(first_sentence.split())[:220]
            if (
                not re.match(r"^[A-Za-z]", summary_text)
                or len(re.findall(r"\b\d{4}\b", summary_text)) >= 2
                or any(token in summary_text.lower() for token in ("scopus", "journal", "doi", "vol.", "pp."))
            ):
                summary_text = ""
            key = (species_record["species_name"], summary_predicate, summary_text)
            if summary_text and key not in claim_buckets:
                claim_counter += 1
                claim_buckets[key] = _make_claim(
                    f"claim_species_{claim_counter:07d}",
                    species_record,
                    chunk,
                    predicate=summary_predicate,
                    value_type="text_summary",
                    value_text=summary_text,
                    confidence=0.64,
                )

    for species_record in species_records.values():
        if species_record.get("iucn_status"):
            claim_counter += 1
            chunk_stub = {"chunk_id": f"{species_record['species_name']}::status", "source_chapter": "Conservation", "source_subchapter": "Unknown"}
            status_value = canonical_status(species_record["iucn_status"])
            claim_buckets[(species_record["species_name"], "HAS_STATUS", status_value)] = _make_claim(
                f"claim_species_{claim_counter:07d}",
                species_record,
                chunk_stub,
                predicate="HAS_STATUS",
                object_type="ConservationStatus",
                object_name=status_value,
                value_type="entity",
                confidence=0.95,
                supported_chunk_ids=[],
            )

    grouped_claims: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for claim in claim_buckets.values():
        grouped_claims[(claim["subject_name"], claim["predicate"])].append(claim)

    claims: list[dict] = []
    for (species_name, predicate), rows in grouped_claims.items():
        limit = MAX_CLAIMS_PER_SPECIES_AND_PREDICATE.get(predicate, 4)
        rows.sort(
            key=lambda row: (
                len(row.get("supported_chunk_ids", [])),
                row.get("confidence", 0.0),
                row.get("object_name") or row.get("value_text") or "",
            ),
            reverse=True,
        )
        claims.extend(rows[:limit])
    write_jsonl(output_path, claims)
    return claims


if __name__ == "__main__":
    build_species_claims()
