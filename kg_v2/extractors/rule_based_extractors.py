"""Rule-based candidate extraction from species chunks."""

from __future__ import annotations

from kg_v2.parsers.normalize_labels import (
    BEHAVIOR_RULES,
    DIET_RULES,
    GEOGRAPHY_RULES,
    HABITAT_RULES,
    THREAT_RULES,
    canonical_status,
    extract_labels,
)
from kg_v2.schema.ontology_v2 import INTERMEDIATE_DIR, load_jsonl, write_jsonl

CHAPTER_FACT_PRIORS = {
    "Habitat": ("habitat", "geography"),
    "Distribution": ("geography",),
    "DietAndForaging": ("diet",),
    "Movement": ("behavior",),
    "VocalBehavior": ("behavior",),
    "GeneralBehavior": ("behavior",),
    "Breeding": ("behavior",),
    "Conservation": ("threat", "status"),
}


def extract_species_label_candidates(
    species_records_path=INTERMEDIATE_DIR / "species_records.jsonl",
    species_chunks_path=INTERMEDIATE_DIR / "species_chunks.jsonl",
    output_path=INTERMEDIATE_DIR / "species_label_candidates.jsonl",
) -> list[dict]:
    species_records = {row["species_name"]: row for row in load_jsonl(species_records_path)}
    species_chunks = load_jsonl(species_chunks_path)
    candidates: list[dict] = []

    for chunk in species_chunks:
        text = chunk.get("raw_text", "")
        chapter = chunk.get("source_chapter", "Unknown")
        priors = CHAPTER_FACT_PRIORS.get(chapter, ())
        habitats = extract_labels(text, HABITAT_RULES, max_n=5)
        geographies = extract_labels(text, GEOGRAPHY_RULES, max_n=4)
        diets = extract_labels(text, DIET_RULES, max_n=4)
        behaviors = extract_labels(text, BEHAVIOR_RULES, max_n=5)
        threats = extract_labels(text, THREAT_RULES, max_n=4)
        species_record = species_records.get(chunk.get("species_name"), {})
        statuses = []
        if species_record.get("iucn_status"):
            statuses.append(canonical_status(species_record["iucn_status"]))

        candidates.append(
            {
                "species_name": chunk.get("species_name"),
                "family_name": chunk.get("family_name"),
                "order_name": chunk.get("order_name"),
                "chunk_id": chunk.get("chunk_id"),
                "source_chapter": chapter,
                "source_chapter_raw": chunk.get("source_chapter_raw", "Unknown"),
                "chapter_priors": list(priors),
                "habitat": habitats,
                "geography": geographies,
                "diet": diets,
                "behavior": behaviors,
                "threat": threats,
                "conservation_status": statuses,
            }
        )

    write_jsonl(output_path, candidates)
    return candidates


if __name__ == "__main__":
    extract_species_label_candidates()
