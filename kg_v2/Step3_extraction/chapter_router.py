"""Lightweight chapter routing for Step 3 extraction."""

from __future__ import annotations

from kg_v2.Step3_extraction.predicate_registry import predicates_for_domains


def _norm(value: str) -> str:
    return " ".join((value or "").replace("_", " ").split()).casefold()


CHAPTER_DOMAIN_ROUTES = {
    "systematics": ["TaxonomyAndPhylogeny"],
    "field identification": ["MorphologyAndIdentification"],
    "identification": ["MorphologyAndIdentification"],
    "plumages molts and structure": ["MorphologyAndIdentification"],
    "plumageandmolt": ["MorphologyAndIdentification"],
    "plumage and molt": ["MorphologyAndIdentification"],
    "morphology": ["MorphologyAndIdentification"],
    "measurements": ["MorphologyAndIdentification"],
    "subspeciesandvariation": ["TaxonomyAndPhylogeny", "MorphologyAndIdentification", "DistributionAndMovement"],
    "subspecies and variation": ["TaxonomyAndPhylogeny", "MorphologyAndIdentification", "DistributionAndMovement"],
    "distribution": ["DistributionAndMovement"],
    "habitat": ["Habitat", "EcologyAndDiet"],
    "movementandmigration": ["DistributionAndMovement"],
    "movements and migration": ["DistributionAndMovement"],
    "dietandforaging": ["EcologyAndDiet"],
    "diet and foraging": ["EcologyAndDiet"],
    "sounds and vocal behavior": ["VocalAndBehavior"],
    "vocalbehavior": ["VocalAndBehavior"],
    "behavior": ["VocalAndBehavior", "LifeHistoryAndBreeding"],
    "generalbehavior": ["VocalAndBehavior"],
    "locomotion": ["VocalAndBehavior"],
    "sexualbehavior": ["VocalAndBehavior", "LifeHistoryAndBreeding"],
    "sexual behavior": ["VocalAndBehavior", "LifeHistoryAndBreeding"],
    "breeding": ["LifeHistoryAndBreeding"],
    "breedingphenology": ["LifeHistoryAndBreeding"],
    "nestandeggs": ["LifeHistoryAndBreeding"],
    "incubationandparentalcare": ["LifeHistoryAndBreeding"],
    "demography": ["LifeHistoryAndBreeding", "ConservationAndResearch"],
    "demography and populations": ["LifeHistoryAndBreeding", "ConservationAndResearch"],
    "conservation": ["ConservationAndResearch"],
    "conservation and management": ["ConservationAndResearch"],
    "relationships with people": ["ConservationAndResearch"],
    "humanrelations": ["ConservationAndResearch"],
    "mortalitypredationparasites": ["ConservationAndResearch", "EcologyAndDiet", "LifeHistoryAndBreeding"],
    "mortality predation parasites": ["ConservationAndResearch", "EcologyAndDiet", "LifeHistoryAndBreeding"],
    "priorities for future research": ["ConservationAndResearch"],
    "futureresearch": ["ConservationAndResearch"],
    "other": ["ConservationAndResearch", "EcologyAndDiet"],
    "unknown": [
        "TaxonomyAndPhylogeny",
        "DistributionAndMovement",
        "Habitat",
        "EcologyAndDiet",
        "ConservationAndResearch",
    ],
    "introduction": [
        "MorphologyAndIdentification",
        "DistributionAndMovement",
        "Habitat",
        "EcologyAndDiet",
        "LifeHistoryAndBreeding",
        "ConservationAndResearch",
    ],
}

SKIP_CHAPTERS = {
    "about the author(s)",
    "about the authors",
    "acknowledgements",
    "acknowledgments",
    "meta",
}


def route_chapter(source_chapter: str, source_subchapter: str = "") -> dict:
    chapter_norm = _norm(source_chapter)
    subchapter_norm = _norm(source_subchapter)
    if chapter_norm in SKIP_CHAPTERS or subchapter_norm in SKIP_CHAPTERS:
        return {"skip": True, "allowed_fact_domains": [], "allowed_predicates": [], "max_claims": 0}
    domains = CHAPTER_DOMAIN_ROUTES.get(chapter_norm, [])
    if not domains:
        return {"skip": True, "allowed_fact_domains": [], "allowed_predicates": [], "max_claims": 0}
    max_claims = 2 if chapter_norm == "introduction" else 4
    return {
        "skip": False,
        "allowed_fact_domains": domains,
        "allowed_predicates": predicates_for_domains(domains),
        "max_claims": max_claims,
    }
