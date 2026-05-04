"""Summary reporting for Step 3 extraction."""

from __future__ import annotations

from collections import Counter


def _top_counts(rows: list[dict], field: str) -> list[dict]:
    counter = Counter(row.get(field, "") for row in rows if row.get(field, ""))
    return [{"value": value, "count": count} for value, count in counter.most_common(20)]


def build_extraction_summary(
    *,
    species_chunk_total: int,
    family_chunk_total: int,
    species_chunks_processed: int,
    family_chunks_processed: int,
    species_claims: list[dict],
    family_claims: list[dict],
    species_facts: list[dict],
    family_facts: list[dict],
    evidences: list[dict],
    fact_evidence_links: list[dict],
    dropped_reasons: Counter,
    extractor_mode: str,
) -> dict:
    species_subject_count = len({fact.get("subject_taxon_id", "") for fact in species_facts if fact.get("subject_taxon_id")})
    family_subject_count = len({fact.get("subject_taxon_id", "") for fact in family_facts if fact.get("subject_taxon_id")})
    all_claims = species_claims + family_claims
    all_facts = species_facts + family_facts
    dropped_total = sum(dropped_reasons.values())
    return {
        "extractor_mode": extractor_mode,
        "species_chunk_total": species_chunk_total,
        "family_chunk_total": family_chunk_total,
        "species_chunks_processed": species_chunks_processed,
        "family_chunks_processed": family_chunks_processed,
        "species_claim_total": len(species_claims),
        "family_claim_total": len(family_claims),
        "species_fact_total": len(species_facts),
        "family_fact_total": len(family_facts),
        "evidence_total": len(evidences),
        "fact_evidence_link_total": len(fact_evidence_links),
        "average_claims_per_species_chunk": (len(species_claims) / species_chunks_processed) if species_chunks_processed else 0.0,
        "average_claims_per_family_chunk": (len(family_claims) / family_chunks_processed) if family_chunks_processed else 0.0,
        "average_facts_per_species": (len(species_facts) / species_subject_count) if species_subject_count else 0.0,
        "average_facts_per_family": (len(family_facts) / family_subject_count) if family_subject_count else 0.0,
        "top_predicates": _top_counts(all_claims, "predicate"),
        "top_fact_domains": _top_counts(all_facts, "fact_domain"),
        "dropped_claim_count": dropped_total,
        "dropped_claim_reasons": [{"reason": reason, "count": count} for reason, count in dropped_reasons.most_common()],
    }

