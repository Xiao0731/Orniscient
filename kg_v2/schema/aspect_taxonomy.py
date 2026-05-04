"""Canonical aspect taxonomies and raw chapter normalization."""

from __future__ import annotations

import re

SPECIES_ASPECTS = (
    "Introduction",
    "Identification",
    "Measurements",
    "PlumageAndMolt",
    "Systematics",
    "SubspeciesAndVariation",
    "Distribution",
    "Habitat",
    "MovementAndMigration",
    "DietAndForaging",
    "VocalBehavior",
    "Locomotion",
    "SocialBehavior",
    "SexualBehavior",
    "BreedingPhenology",
    "NestAndEggs",
    "IncubationAndParentalCare",
    "Demography",
    "MortalityPredationParasites",
    "Conservation",
    "HumanRelations",
    "FutureResearch",
    "Other",
    "Meta",
)

FAMILY_ASPECTS = (
    "Introduction",
    "Systematics",
    "Morphology",
    "Habitat",
    "Movement",
    "DietAndForaging",
    "Voice",
    "Breeding",
    "Conservation",
    "HumanRelations",
    "Other",
)

_SPECIES_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("Introduction", (r"^introduction$", r"^overview$")),
    ("Identification", (r"^field identification$", r"^identification$", r"^similar species$")),
    ("Measurements", (r"^measurements?$", r"^size$")),
    ("PlumageAndMolt", (r"^plumages?, molts?, and structure$", r"^morphology$", r"^structure$", r"^plumage$")),
    (
        "Systematics",
        (
            r"^systematics$",
            r"^systematics history$",
            r"^systematicas history$",
            r"^taxonomy$",
        ),
    ),
    (
        "SubspeciesAndVariation",
        (
            r"^subspecies$",
            r"^geographic variation$",
            r"^subspecies and variation$",
        ),
    ),
    ("Distribution", (r"^distribution$", r"^range$")),
    ("Habitat", (r"^habitat$", r"^general habitat$")),
    ("MovementAndMigration", (r"^movements and migration$", r"^migration$", r"^movements$")),
    ("DietAndForaging", (r"^diet and foraging$", r"^diet$", r"^foraging$", r"^food habits$")),
    (
        "VocalBehavior",
        (r"^sounds and vocal behavior$", r"^sounds?$", r"^vocal behavior$", r"^voice$", r"^vocalizations?$"),
    ),
    ("Locomotion", (r"^locomotion$",)),
    ("SocialBehavior", (r"^social behavior$", r"^social behaviour$")),
    ("SexualBehavior", (r"^sexual behavior$", r"^sexual behaviour$")),
    ("BreedingPhenology", (r"^breeding$", r"^reproduction$", r"^breeding phenology$")),
    ("NestAndEggs", (r"^nest and eggs$", r"^nesting$", r"^nests?$", r"^eggs?$")),
    ("IncubationAndParentalCare", (r"^incubation and parental care$", r"^parental care$", r"^incubation$")),
    ("Demography", (r"^demography and populations$", r"^demography$", r"^population(?:s)?$")),
    ("MortalityPredationParasites", (r"^mortality predation parasites$", r"^mortality$", r"^predation$", r"^parasites$")),
    ("Conservation", (r"^conservation and management$", r"^conservation status$", r"^conservation$")),
    ("HumanRelations", (r"^relationships with people$", r"^human relations$", r"^people$")),
    ("FutureResearch", (r"^priorities for future research$", r"^future research$")),
    ("Meta", (r"^acknowledgements?$", r"^about the author\(s\)$", r"^references$")),
    ("Other", (r"^other$",)),
]

_FAMILY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("Introduction", (r"^introduction$", r"^overview$")),
    ("Systematics", (r"^systematics$", r"^systematicas history$", r"^systematics history$", r"^systematicshistory$")),
    ("Morphology", (r"^morphology$", r"^structure$", r"^identification$")),
    ("Habitat", (r"^general habitat$", r"^habitat$")),
    ("Movement", (r"^movement$", r"^migration$", r"^movements and migration$")),
    ("DietAndForaging", (r"^diet and foraging$", r"^dietandforaging$", r"^diet & foraging$", r"^diet$")),
    ("Voice", (r"^voice$", r"^vocal behavior$", r"^sounds?$")),
    ("Breeding", (r"^breeding$", r"^reproduction$")),
    ("Conservation", (r"^conservation$", r"^conservation status$", r"^conservationstatus$")),
    ("HumanRelations", (r"^human relations$", r"^relationships with people$")),
    ("Other", (r"^other$",)),
]


def _normalize(raw_name: str) -> str:
    return re.sub(r"\s+", " ", (raw_name or "").strip())


def normalize_species_chapter(raw_name: str) -> str:
    normalized = _normalize(raw_name).lower()
    if not normalized:
        return "Unknown"
    for canonical, patterns in _SPECIES_PATTERNS:
        if any(re.fullmatch(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns):
            return canonical
    return "Unknown"


def normalize_family_chapter(raw_name: str) -> str:
    normalized = _normalize(raw_name).lower()
    if not normalized:
        return "Unknown"
    for canonical, patterns in _FAMILY_PATTERNS:
        if any(re.fullmatch(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns):
            return canonical
    return "Unknown"


def normalize_species_subchapter(raw_name: str, parent_chapter: str | None = None) -> str:
    normalized = _normalize(raw_name)
    if not normalized:
        return "Unknown"
    chapter = normalize_species_chapter(normalized)
    if chapter != "Unknown":
        return chapter
    if parent_chapter and parent_chapter != "Unknown":
        return normalized
    return "Unknown"
