"""Controlled fact domains and predicates for Step 3 extraction."""

from __future__ import annotations

FACT_DOMAINS = [
    "TaxonomyAndPhylogeny",
    "MorphologyAndIdentification",
    "DistributionAndMovement",
    "Habitat",
    "EcologyAndDiet",
    "VocalAndBehavior",
    "LifeHistoryAndBreeding",
    "ConservationAndResearch",
]

PREDICATES_BY_DOMAIN = {
    "TaxonomyAndPhylogeny": [
        "HAS_SUBSPECIES",
        "HAS_GEOGRAPHIC_VARIATION",
        "HAS_SUBSPECIES_TRAIT",
        "HAS_SUBSPECIES_DISTRIBUTION",
        "HYBRIDIZES_WITH",
        "RELATED_TO",
        "HAS_CLASSIFICATION_HISTORY",
        "HAS_TAXONOMIC_NOTE",
    ],
    "MorphologyAndIdentification": [
        "HAS_BODY_LENGTH",
        "HAS_BODY_MASS",
        "HAS_WING_LENGTH",
        "HAS_TAIL_LENGTH",
        "HAS_BILL_LENGTH",
        "HAS_TARSUS_LENGTH",
        "HAS_WINGSPAN",
        "HAS_PLUMAGE_TRAIT",
        "HAS_MOLT_PATTERN",
        "HAS_SEXUAL_DIMORPHISM",
        "HAS_AGE_DIMORPHISM",
        "HAS_DIAGNOSTIC_TRAIT",
        "HAS_STRUCTURE_TRAIT",
    ],
    "DistributionAndMovement": [
        "OCCURS_IN",
        "ENDEMIC_TO",
        "BREEDS_IN",
        "WINTERS_IN",
        "MIGRATES_VIA",
        "HAS_MIGRATION_PATTERN",
        "HAS_ELEVATION_RANGE",
        "HAS_DISTRIBUTION_NOTE",
    ],
    "Habitat": [
        "INHABITS_BIOME",
        "USES_MICROHABITAT",
    ],
    "EcologyAndDiet": [
        "EATS_CATEGORY",
        "EATS_ITEM",
        "FORAGES_BY",
        "FORAGES_IN_STRATUM",
        "HAS_ECOLOGICAL_ROLE",
    ],
    "VocalAndBehavior": [
        "HAS_VOCALIZATION_TYPE",
        "CALLS_DURING",
        "HAS_NONVOCAL_SOUND",
        "HAS_SOUND_DIAGNOSTIC",
        "HAS_SOCIAL_BEHAVIOR",
        "HAS_TERRITORIAL_BEHAVIOR",
        "HAS_LOCOMOTION_STYLE",
        "HAS_FLIGHT_ABILITY",
        "HAS_RUNNING_SPEED",
        "HAS_JUMP_HEIGHT",
        "HAS_SWIMMING_ABILITY",
        "HAS_CLIMBING_ABILITY",
        "HAS_DAILY_ACTIVITY_PATTERN",
        "HAS_COURTSHIP_BEHAVIOR",
        "HAS_MATING_SYSTEM",
        "HAS_PAIR_BOND",
        "HAS_COPULATION_BEHAVIOR",
        "HAS_AGONISTIC_BEHAVIOR",
    ],
    "LifeHistoryAndBreeding": [
        "BREEDS_DURING",
        "NESTS_AT",
        "HAS_NEST_STRUCTURE",
        "HAS_EGG_TRAIT",
        "HAS_CLUTCH_SIZE",
        "HAS_INCUBATION_PERIOD",
        "HAS_FLEDGING_PERIOD",
        "HAS_PARENTAL_ROLE",
        "HAS_DEVELOPMENT_NOTE",
        "HAS_DEMOGRAPHIC_NOTE",
    ],
    "ConservationAndResearch": [
        "HAS_IUCN_STATUS",
        "HAS_POPULATION_TREND",
        "THREATENED_BY",
        "HAS_CONSERVATION_ACTION",
        "INTERACTS_WITH_HUMANS",
        "HAS_PREDATOR",
        "HAS_PARASITE",
        "HAS_DISEASE",
        "HAS_MORTALITY_CAUSE",
        "REQUIRES_RESEARCH_ON",
    ],
}

ALL_PREDICATES = {predicate for predicates in PREDICATES_BY_DOMAIN.values() for predicate in predicates}

SPECIES_DOMAIN_FACT_QUOTAS = {
    "TaxonomyAndPhylogeny": 3,
    "MorphologyAndIdentification": 5,
    "DistributionAndMovement": 5,
    "Habitat": 3,
    "EcologyAndDiet": 5,
    "VocalAndBehavior": 4,
    "LifeHistoryAndBreeding": 7,
    "ConservationAndResearch": 4,
}

FAMILY_DOMAIN_FACT_QUOTAS = {
    "TaxonomyAndPhylogeny": 2,
    "MorphologyAndIdentification": 2,
    "DistributionAndMovement": 2,
    "Habitat": 2,
    "EcologyAndDiet": 3,
    "VocalAndBehavior": 1,
    "LifeHistoryAndBreeding": 3,
    "ConservationAndResearch": 3,
}


def predicates_for_domains(domains: list[str]) -> list[str]:
    predicates: list[str] = []
    for domain in domains:
        predicates.extend(PREDICATES_BY_DOMAIN.get(domain, []))
    return predicates
