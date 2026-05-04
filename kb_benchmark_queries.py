from __future__ import annotations

"""
kb_benchmark_queries.py
=======================

Benchmark-facing query helpers for the schema-first ornithology knowledge base.

This module is the missing adapter layer between:
1. `direct_neo4j_insert_v2.py`  -> writes Species / Taxon / Fact / Evidence into Neo4j
2. `benchmark_complete.py`      -> needs compact KG anchors + evidence bundles

Design principles
-----------------
- The KB is used to *focus* generation, not to blindly replace source text.
- Query functions are dataset-aware and return structured results.
- Fine-grained `Fact` + `Evidence` records are preferred when available.
- If a fine-grained fact is absent, callers can fall back to raw BOW section retrieval.

Schema assumptions
------------------
The loader writes the following core pieces:
- (:Species {id, common_name, scientific_name})
- (:Alias {id})
- (:Taxon {id, rank})
- (:Habitat / :Geography / :Food / :Behavior / :Threat / :ConservationStatus)
- (:Fact {fact_type, value, normalized_value, metric_name, source_chapter, ...})
- (:Evidence {exact_quote, source_file, source_chapter, ...})

Useful patterns:
- (s:Species)-[:HAS_FACT]->(f:Fact)-[:SUPPORTED_BY]->(e:Evidence)
- (s:Species)-[:BELONGS_TO|HAS_STATUS|INHABITS|FOUND_IN|PREYS_ON|EXHIBITS|THREATENED_BY]->(...)
"""

import os
import re
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Optional

from neo4j import GraphDatabase, Driver

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j") or "neo4j"


# -----------------------------------------------------------------------------
# Small data containers
# -----------------------------------------------------------------------------

@dataclass
class ResolvedSpecies:
    species_id: str
    common_name: str
    scientific_name: str


@dataclass
class EvidenceItem:
    fact_type: str
    value: str
    normalized_value: str
    metric_name: str
    source_chapter: str
    exact_quote: str
    extractor: str
    confidence: Optional[float] = None


# -----------------------------------------------------------------------------
# Shared utilities
# -----------------------------------------------------------------------------


def make_driver() -> Driver:
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))



def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())



def compact(text: str, max_len: int = 220) -> str:
    text = normalize_space(text)
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"



def _dicts(records: Iterable[Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in records]


# -----------------------------------------------------------------------------
# Species resolution
# -----------------------------------------------------------------------------


def resolve_species(driver: Driver, species_name: str) -> Optional[ResolvedSpecies]:
    """Resolve a user/benchmark species name to a canonical Species.id.

    Resolution order:
    1. Exact / case-insensitive match on Species.id
    2. Exact / case-insensitive match on common_name
    3. Exact / case-insensitive match on scientific_name
    4. Alias lookup via (:Alias)<-[:HAS_ALIAS]-(:Species)
    """
    with driver.session(database=NEO4J_DATABASE) as session:
        exact_q = """
        MATCH (s:Species)
        WHERE toLower(s.id) = toLower($name)
           OR toLower(s.common_name) = toLower($name)
           OR toLower(s.scientific_name) = toLower($name)
        RETURN s.id AS species_id,
               coalesce(s.common_name, '') AS common_name,
               coalesce(s.scientific_name, '') AS scientific_name
        LIMIT 1
        """
        rec = session.run(exact_q, name=species_name).single()
        if rec:
            return ResolvedSpecies(**dict(rec))

        alias_q = """
        MATCH (a:Alias)<-[:HAS_ALIAS]-(s:Species)
        WHERE toLower(a.id) = toLower($name)
        RETURN s.id AS species_id,
               coalesce(s.common_name, '') AS common_name,
               coalesce(s.scientific_name, '') AS scientific_name
        LIMIT 1
        """
        rec = session.run(alias_q, name=species_name).single()
        if rec:
            return ResolvedSpecies(**dict(rec))
    return None


# -----------------------------------------------------------------------------
# Low-level fetchers
# -----------------------------------------------------------------------------

CORE_REL_TYPES = (
    "BELONGS_TO",
    "HAS_STATUS",
    "INHABITS",
    "FOUND_IN",
    "PREYS_ON",
    "EXHIBITS",
    "THREATENED_BY",
    "RELATED_TO",
)


def fetch_structural_relations(driver: Driver, species_id: str) -> list[dict[str, Any]]:
    query = """
    MATCH (s:Species {id: $species_id})-[r]->(t)
    WHERE type(r) IN $rel_types
    RETURN type(r) AS rel_type,
           labels(t) AS target_labels,
           coalesce(t.id, '') AS target_id,
           coalesce(t.rank, '') AS taxon_rank,
           coalesce(r.source_chapter, '') AS source_chapter,
           coalesce(r.extractor, '') AS extractor
    ORDER BY rel_type, target_id
    """
    with driver.session(database=NEO4J_DATABASE) as session:
        return _dicts(session.run(query, species_id=species_id, rel_types=list(CORE_REL_TYPES)))



def fetch_facts_by_types(driver: Driver, species_id: str, fact_types: list[str], limit: int = 20) -> list[EvidenceItem]:
    query = """
    MATCH (s:Species {id: $species_id})-[:HAS_FACT]->(f:Fact)-[:SUPPORTED_BY]->(e:Evidence)
    WHERE f.fact_type IN $fact_types
    RETURN f.fact_type AS fact_type,
           coalesce(f.value, '') AS value,
           coalesce(f.normalized_value, '') AS normalized_value,
           coalesce(f.metric_name, '') AS metric_name,
           coalesce(e.source_chapter, f.source_chapter, '') AS source_chapter,
           coalesce(e.exact_quote, '') AS exact_quote,
           coalesce(f.extractor, '') AS extractor,
           f.confidence AS confidence
    ORDER BY coalesce(f.metric_name, ''), coalesce(f.value, '')
    LIMIT $limit
    """
    with driver.session(database=NEO4J_DATABASE) as session:
        rows = _dicts(session.run(query, species_id=species_id, fact_types=fact_types, limit=limit))
    return [EvidenceItem(**row) for row in rows]



def fetch_facts_by_relation_mirror(driver: Driver, species_id: str, relation_fact_types: list[str], limit: int = 20) -> list[EvidenceItem]:
    """Rule-based structural edges are mirrored into Fact nodes using lowercased relation types.

    Examples:
      INHABITS      -> fact_type='inhabits'
      THREATENED_BY -> fact_type='threatened_by'
    """
    return fetch_facts_by_types(driver, species_id, relation_fact_types, limit=limit)


# -----------------------------------------------------------------------------
# Benchmark-facing high-level query functions
# -----------------------------------------------------------------------------


def get_species_anchor_facts(driver: Driver, species_name: str, dataset: Optional[str] = None, max_lines: int = 8) -> dict[str, Any]:
    """Return a compact dataset-aware anchor bundle for prompt injection.

    Output keys:
    - species
    - lines
    - kg_context
    - structural_relations
    - fine_facts
    """
    species = resolve_species(driver, species_name)
    if not species:
        return {
            "species": None,
            "lines": [],
            "kg_context": "(No KB match found for this species.)",
            "structural_relations": [],
            "fine_facts": [],
        }

    structural = fetch_structural_relations(driver, species.species_id)

    dataset = (dataset or "").strip()
    if dataset == "Bird-Taxonomy":
        fact_types = ["taxonomy_history", "split_lump", "nomenclature_etymology", "subspecies_validity"]
        mirror_types = ["belongs_to", "related_species"]
    elif dataset == "Bird-Con":
        fact_types = ["population_trend", "population_estimate"]
        mirror_types = ["has_status", "threatened_by"]
    elif dataset == "Bird-Life":
        fact_types = ["breeding_metric"]
        mirror_types = ["exhibits"]
    elif dataset == "Bird-Eco":
        fact_types = []
        mirror_types = ["preys_on", "inhabits", "exhibits"]
    elif dataset == "Bird-Geo":
        fact_types = []
        mirror_types = ["found_in", "inhabits"]
    else:
        fact_types = [
            "taxonomy_history",
            "split_lump",
            "subspecies_validity",
            "population_trend",
            "population_estimate",
            "breeding_metric",
        ]
        mirror_types = ["belongs_to", "has_status", "inhabits", "found_in", "preys_on", "exhibits", "threatened_by"]

    fine_facts = fetch_facts_by_types(driver, species.species_id, fact_types, limit=10) if fact_types else []
    mirror_facts = fetch_facts_by_relation_mirror(driver, species.species_id, mirror_types, limit=20) if mirror_types else []

    lines: list[str] = [
        f"Matched species: {species.common_name or species.species_id}",
        f"Scientific name: {species.scientific_name or species.species_id}",
    ]

    # Structural summary first.
    for row in structural:
        rel_type = row["rel_type"]
        target = row["target_id"]
        if rel_type == "BELONGS_TO" and row.get("taxon_rank"):
            lines.append(f"- {row['taxon_rank']}: {target}")
        elif rel_type == "HAS_STATUS":
            lines.append(f"- Conservation status: {target}")
        elif rel_type == "INHABITS":
            lines.append(f"- Habitat: {target}")
        elif rel_type == "FOUND_IN":
            lines.append(f"- Geography: {target}")
        elif rel_type == "PREYS_ON":
            lines.append(f"- Diet/food: {target}")
        elif rel_type == "EXHIBITS":
            lines.append(f"- Behavior: {target}")
        elif rel_type == "THREATENED_BY":
            lines.append(f"- Threat: {target}")
        elif rel_type == "RELATED_TO":
            lines.append(f"- Related species: {target}")
        if len(lines) >= max_lines + 2:
            break

    # Fine-grained fact summary second.
    for fact in fine_facts:
        if fact.fact_type == "breeding_metric" and fact.metric_name:
            lines.append(f"- Breeding metric ({fact.metric_name}): {fact.value}")
        elif fact.fact_type == "population_estimate":
            lines.append(f"- Population estimate: {fact.value}")
        elif fact.fact_type == "population_trend":
            lines.append(f"- Population trend: {fact.value}")
        elif fact.fact_type == "subspecies_validity":
            lines.append(f"- Subspecies fact: {fact.value}")
        elif fact.fact_type == "taxonomy_history":
            lines.append(f"- Taxonomy history: {compact(fact.value, 140)}")
        elif fact.fact_type == "split_lump":
            lines.append(f"- Split/lump fact: {compact(fact.value, 140)}")
        elif fact.fact_type == "nomenclature_etymology":
            lines.append(f"- Name/etymology: {compact(fact.value, 140)}")
        if len(lines) >= max_lines + 2:
            break

    # De-duplicate while preserving order.
    seen = set()
    unique_lines = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)
        if len(unique_lines) >= max_lines + 2:
            break

    return {
        "species": asdict(species),
        "lines": unique_lines,
        "kg_context": "\n".join(unique_lines),
        "structural_relations": structural,
        "fine_facts": [asdict(f) for f in fine_facts],
        "mirror_facts": [asdict(f) for f in mirror_facts],
    }



def get_evidence_for_taxonomy(driver: Driver, species_name: str, limit: int = 10) -> dict[str, Any]:
    species = resolve_species(driver, species_name)
    if not species:
        return {"species": None, "facts": [], "evidence_text": ""}

    facts = fetch_facts_by_types(
        driver,
        species.species_id,
        ["taxonomy_history", "split_lump", "nomenclature_etymology", "subspecies_validity"],
        limit=limit,
    )
    evidence_lines = []
    for fact in facts:
        label = fact.metric_name or fact.fact_type
        evidence_lines.append(f"[{fact.source_chapter}] {label}: {fact.value}")
        evidence_lines.append(f"Quote: {fact.exact_quote}")
    return {
        "species": asdict(species),
        "facts": [asdict(f) for f in facts],
        "evidence_text": "\n".join(evidence_lines),
    }



def get_breeding_metrics(driver: Driver, species_name: str, limit: int = 12) -> dict[str, Any]:
    species = resolve_species(driver, species_name)
    if not species:
        return {"species": None, "metrics": [], "evidence_text": ""}

    metrics = fetch_facts_by_types(driver, species.species_id, ["breeding_metric"], limit=limit)
    evidence_lines = []
    for fact in metrics:
        metric = fact.metric_name or "breeding_metric"
        evidence_lines.append(f"[{fact.source_chapter}] {metric}: {fact.value}")
        evidence_lines.append(f"Quote: {fact.exact_quote}")
    return {
        "species": asdict(species),
        "metrics": [asdict(f) for f in metrics],
        "evidence_text": "\n".join(evidence_lines),
    }



def get_conservation_facts(driver: Driver, species_name: str, limit: int = 12) -> dict[str, Any]:
    species = resolve_species(driver, species_name)
    if not species:
        return {"species": None, "facts": [], "evidence_text": ""}

    fine = fetch_facts_by_types(driver, species.species_id, ["population_trend", "population_estimate"], limit=limit)
    mirror = fetch_facts_by_relation_mirror(driver, species.species_id, ["has_status", "threatened_by"], limit=limit)

    all_items = fine + mirror
    evidence_lines = []
    for fact in all_items:
        label = fact.metric_name or fact.fact_type
        evidence_lines.append(f"[{fact.source_chapter}] {label}: {fact.value}")
        evidence_lines.append(f"Quote: {fact.exact_quote}")
    return {
        "species": asdict(species),
        "facts": [asdict(f) for f in all_items],
        "evidence_text": "\n".join(evidence_lines),
    }



def get_distribution_habitat_facts(driver: Driver, species_name: str, limit: int = 12) -> dict[str, Any]:
    species = resolve_species(driver, species_name)
    if not species:
        return {"species": None, "facts": [], "evidence_text": ""}

    facts = fetch_facts_by_relation_mirror(driver, species.species_id, ["found_in", "inhabits"], limit=limit)
    evidence_lines = []
    for fact in facts:
        evidence_lines.append(f"[{fact.source_chapter}] {fact.fact_type}: {fact.value}")
        evidence_lines.append(f"Quote: {fact.exact_quote}")
    return {
        "species": asdict(species),
        "facts": [asdict(f) for f in facts],
        "evidence_text": "\n".join(evidence_lines),
    }



def get_ecology_facts(driver: Driver, species_name: str, limit: int = 12) -> dict[str, Any]:
    species = resolve_species(driver, species_name)
    if not species:
        return {"species": None, "facts": [], "evidence_text": ""}

    facts = fetch_facts_by_relation_mirror(driver, species.species_id, ["preys_on", "exhibits", "inhabits"], limit=limit)
    evidence_lines = []
    for fact in facts:
        evidence_lines.append(f"[{fact.source_chapter}] {fact.fact_type}: {fact.value}")
        evidence_lines.append(f"Quote: {fact.exact_quote}")
    return {
        "species": asdict(species),
        "facts": [asdict(f) for f in facts],
        "evidence_text": "\n".join(evidence_lines),
    }



def get_related_species(driver: Driver, species_name: str, limit: int = 12) -> dict[str, Any]:
    species = resolve_species(driver, species_name)
    if not species:
        return {"species": None, "facts": [], "evidence_text": ""}

    facts = fetch_facts_by_relation_mirror(driver, species.species_id, ["related_species"], limit=limit)
    evidence_lines = []
    for fact in facts:
        evidence_lines.append(f"[{fact.source_chapter}] related_species: {fact.value}")
        evidence_lines.append(f"Quote: {fact.exact_quote}")
    return {
        "species": asdict(species),
        "facts": [asdict(f) for f in facts],
        "evidence_text": "\n".join(evidence_lines),
    }


# -----------------------------------------------------------------------------
# Adapter bundle for benchmark generation
# -----------------------------------------------------------------------------


def build_benchmark_bundle(driver: Driver, species_name: str, dataset: str, max_anchor_lines: int = 8) -> dict[str, Any]:
    """Dataset-aware one-stop bundle for benchmark generation.

    Returns:
      {
        'species': ...,
        'kg_context': '...',
        'preferred_evidence_text': '...',
        'preferred_facts': [...],
      }

    Integration rule of thumb for benchmark:
    - Use `kg_context` as a soft anchor in the prompt.
    - Prefer `preferred_evidence_text` as a short high-value source supplement.
    - If preferred evidence is empty, fall back to your existing raw-section retrieval.
    """
    anchor = get_species_anchor_facts(driver, species_name, dataset=dataset, max_lines=max_anchor_lines)

    if dataset == "Bird-Taxonomy":
        ev = get_evidence_for_taxonomy(driver, species_name)
        facts = ev["facts"]
        evidence_text = ev["evidence_text"]
    elif dataset == "Bird-Life":
        ev = get_breeding_metrics(driver, species_name)
        facts = ev["metrics"]
        evidence_text = ev["evidence_text"]
    elif dataset == "Bird-Con":
        ev = get_conservation_facts(driver, species_name)
        facts = ev["facts"]
        evidence_text = ev["evidence_text"]
    elif dataset == "Bird-Geo":
        ev = get_distribution_habitat_facts(driver, species_name)
        facts = ev["facts"]
        evidence_text = ev["evidence_text"]
    elif dataset in {"Bird-Eco", "Bird-Reason", "QA-SC", "QA-MC", "QA-SA"}:
        ev = get_ecology_facts(driver, species_name)
        facts = ev["facts"]
        evidence_text = ev["evidence_text"]
    elif dataset in {"Bird-Comp", "Bird-ID"}:
        ev = get_related_species(driver, species_name)
        facts = ev["facts"]
        evidence_text = ev["evidence_text"]
    else:
        facts = []
        evidence_text = ""

    return {
        "species": anchor.get("species"),
        "kg_context": anchor.get("kg_context", ""),
        "preferred_facts": facts,
        "preferred_evidence_text": evidence_text,
    }


# -----------------------------------------------------------------------------
# Simple CLI smoke test
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Smoke-test KB benchmark queries")
    parser.add_argument("--species", required=True)
    parser.add_argument("--dataset", default="Bird-Con")
    args = parser.parse_args()

    driver = make_driver()
    try:
        bundle = build_benchmark_bundle(driver, args.species, args.dataset)
        print("=" * 80)
        print("KG CONTEXT")
        print(bundle["kg_context"])
        print("\n" + "=" * 80)
        print("PREFERRED EVIDENCE")
        print(bundle["preferred_evidence_text"] or "(none)")
    finally:
        driver.close()
