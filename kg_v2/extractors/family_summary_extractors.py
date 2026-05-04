"""Aggregate species facts upward into derived family summaries."""

from __future__ import annotations

from collections import Counter, defaultdict

from kg_v2.schema.ontology_v2 import INTERMEDIATE_DIR, load_jsonl, write_jsonl

FACT_TO_SUMMARY_FIELD = {
    "INHABITS": "top_habitats",
    "PREYS_ON": "top_foods",
    "FOUND_IN": "top_geographies",
    "EXHIBITS": "top_behaviors",
    "THREATENED_BY": "top_threats",
}


def _top_values(counter: Counter, limit: int = 5) -> list[str]:
    return [value for value, _ in counter.most_common(limit)]


def build_family_summaries(
    species_records_path=INTERMEDIATE_DIR / "species_records.jsonl",
    species_claims_path=INTERMEDIATE_DIR / "species_claims.jsonl",
    output_path=INTERMEDIATE_DIR / "family_summaries.jsonl",
) -> list[dict]:
    species_records = load_jsonl(species_records_path)
    species_facts = load_jsonl(species_claims_path)

    species_counts: Counter = Counter()
    family_counters: dict[str, dict[str, Counter]] = defaultdict(
        lambda: {
            "top_habitats": Counter(),
            "top_foods": Counter(),
            "top_geographies": Counter(),
            "top_behaviors": Counter(),
            "top_threats": Counter(),
        }
    )

    for record in species_records:
        if record.get("family_name"):
            species_counts[record["family_name"]] += 1

    for fact in species_facts:
        family_name = fact.get("family_name")
        fact_type = fact.get("predicate") or fact.get("fact_type")
        summary_field = FACT_TO_SUMMARY_FIELD.get(fact_type)
        if family_name and summary_field:
            object_name = fact.get("object_name")
            if object_name:
                family_counters[family_name][summary_field][object_name] += 1

    summary_rows: list[dict] = []
    family_names = sorted(set(species_counts) | set(family_counters))
    for family_name in family_names:
        counter_map = family_counters[family_name]
        top_habitats = _top_values(counter_map["top_habitats"])
        top_foods = _top_values(counter_map["top_foods"])
        top_geographies = _top_values(counter_map["top_geographies"])
        top_behaviors = _top_values(counter_map["top_behaviors"])
        top_threats = _top_values(counter_map["top_threats"])
        summary_text = (
            f"{family_name} includes {species_counts[family_name]} species records. "
            f"Common habitats: {', '.join(top_habitats) or 'n/a'}. "
            f"Common foods: {', '.join(top_foods) or 'n/a'}. "
            f"Common geographies: {', '.join(top_geographies) or 'n/a'}. "
            f"Common behaviors: {', '.join(top_behaviors) or 'n/a'}. "
            f"Common threats: {', '.join(top_threats) or 'n/a'}."
        )
        summary_rows.append(
            {
                "family_name": family_name,
                "summary_type": "derived_from_species",
                "summary_text": summary_text,
                "top_habitats": top_habitats,
                "top_foods": top_foods,
                "top_geographies": top_geographies,
                "top_behaviors": top_behaviors,
                "top_threats": top_threats,
                "species_count": species_counts[family_name],
            }
        )

    write_jsonl(output_path, summary_rows)
    return summary_rows


if __name__ == "__main__":
    build_family_summaries()
