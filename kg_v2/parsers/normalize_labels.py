"""Concept normalization and rule-based label dictionaries."""

from __future__ import annotations

import re

NORMALIZATION_REPLACEMENTS = {
    r"\bfreshwater marsh(?:es)?\b": "Freshwater Wetlands",
    r"\briver(?:s)?\b": "Freshwater Wetlands",
    r"\bpond(?:s)?\b": "Freshwater Wetlands",
    r"\bswamp(?:s)?\b": "Freshwater Wetlands",
    r"\blake(?:s)?\b": "Freshwater Wetlands",
    r"\bmangrove(?:s)?\b": "Mangroves",
    r"\bprimary forest(?:s)?\b": "Tropical Forests",
    r"\bmontane forest(?:s)?\b": "Montane Forests",
    r"\bcloud forest(?:s)?\b": "Montane Forests",
}

HABITAT_RULES = {
    "Freshwater Wetlands": [
        r"\bfreshwater wetlands?\b",
        r"\bmarsh(?:es)?\b",
        r"\bswamp(?:s)?\b",
        r"\bpond(?:s)?\b",
        r"\briver(?:s)?\b",
        r"\blake(?:s)?\b",
        r"\bwetland(?:s)?\b",
        r"\bfen(?:s)?\b",
        r"\bbog(?:s)?\b",
    ],
    "Mangroves": [r"\bmangrove(?:s)?\b"],
    "Tropical Forests": [
        r"\btropical forest(?:s)?\b",
        r"\brainforest(?:s)?\b",
        r"\bprimary forest(?:s)?\b",
        r"\blowland forest(?:s)?\b",
        r"\bevergreen forest(?:s)?\b",
    ],
    "Montane Forests": [
        r"\bmontane forest(?:s)?\b",
        r"\bcloud forest(?:s)?\b",
        r"\bsubmontane forest(?:s)?\b",
    ],
    "Temperate Forests": [r"\btemperate forest(?:s)?\b", r"\bdeciduous forest(?:s)?\b", r"\bmixed forest(?:s)?\b"],
    "Savanna": [r"\bsavann?a\b", r"\bgrassland(?:s)?\b", r"\bopen country\b"],
    "Marine Coastal": [r"\bcoast(?:al)?\b", r"\bestuar(?:y|ies)\b", r"\bshore\b", r"\bmarine\b", r"\btidal\b"],
    "Arid Shrubland": [r"\barid\b", r"\bdesert\b", r"\bshrubland\b", r"\bsemi-arid\b"],
    "Alpine": [r"\balpine\b", r"\bhigh mountain\b", r"\bsubalpine\b"],
    "Agricultural Landscapes": [r"\bcropland\b", r"\bfarmland\b", r"\bagricultural\b", r"\bpasture\b", r"\brice field(?:s)?\b"],
    "Urban Areas": [r"\burban\b", r"\bcity\b", r"\bsuburban\b", r"\bgarden(?:s)?\b", r"\bparkland\b"],
}

DIET_RULES = {
    "Insects": [r"\binsectivor", r"\binsects?\b", r"\barthropods?\b", r"\binvertebrates?\b", r"\blarvae\b"],
    "Seeds": [r"\bgranivor", r"\bseeds?\b", r"\bgrains?\b"],
    "Fruit": [r"\bfrugivor", r"\bfruit\b", r"\bberries\b", r"\bfigs?\b"],
    "Nectar": [r"\bnectar\b", r"\bnectarivor"],
    "Small Fish": [r"\bfish\b", r"\bpiscivor"],
    "Aquatic Vegetation": [r"\baquatic vegetation\b", r"\bwater plants?\b", r"\bmacrophytes?\b"],
    "Small Vertebrates": [r"\bsmall vertebrates?\b", r"\blizards?\b", r"\bfrogs?\b", r"\brodents?\b"],
    "Carrion": [r"\bcarrion\b", r"\bscaveng"],
    "Crustaceans": [r"\bcrustaceans?\b", r"\bcrabs?\b", r"\bshrimp\b"],
    "Mollusks": [r"\bmollusks?\b", r"\bsnails?\b", r"\bbivalves?\b"],
}

BEHAVIOR_RULES = {
    "Migratory": [r"\bmigrat", r"\blong-distance migrant", r"\bpartial migrant", r"\bseasonal migrant"],
    "Resident": [r"\bresident\b", r"\bsedentary\b"],
    "Nomadic": [r"\bnomadic\b"],
    "Ground-nesting": [r"\bground[- ]nest", r"\bnests? on the ground\b"],
    "Cavity-nesting": [r"\bcavity[- ]nest", r"\bnests? in cavities\b", r"\bhole[- ]nest\b"],
    "Tree-nesting": [r"\bnests? in trees\b", r"\btree[- ]nest\b"],
    "Colonial": [r"\bcolonial\b", r"\bnests? in colonies\b"],
    "Monogamous": [r"\bmonogam"],
    "Polygynous": [r"\bpolygyn"],
    "Arboreal": [r"\barboreal\b", r"\bforages? in trees\b"],
    "Aquatic Foraging": [r"\bdives?\b", r"\bwades?\b", r"\bforages? in shallow water\b", r"\bswims?\b"],
    "Nocturnal": [r"\bnocturnal\b", r"\bactive at night\b"],
}

MOVEMENT_RULES = {
    "Resident": [r"\bresident\b", r"\bsedentary\b"],
    "Migratory": [r"\bmigrat", r"\bpassage migrant\b", r"\blong-distance migrant\b"],
    "Partial Migrant": [r"\bpartial migrant\b"],
    "Nomadic": [r"\bnomadic\b"],
    "Dispersive": [r"\bdispersive\b"],
    "Altitudinal Migrant": [r"\baltitudinal migrant\b", r"\bseasonal elevational\b"],
}

VOCAL_RULES = {
    "Booming": [r"\bboom(?:ing)?\b"],
    "Whistling": [r"\bwhistl(?:e|ing)\b"],
    "Song": [r"\bsong\b", r"\bsings?\b"],
    "Call": [r"\bcall(?:s)?\b", r"\bcalling\b"],
    "Drumming": [r"\bdrumm(?:ing)?\b"],
}

BREEDING_RULES = {
    "Monogamous": [r"\bmonogam"],
    "Polygynous": [r"\bpolygyn"],
    "Polyandrous": [r"\bpolyandr"],
    "Colonial Breeding": [r"\bcolonial\b", r"\bnests? in colonies\b"],
    "Ground Breeding": [r"\bnests? on the ground\b", r"\bground[- ]nest"],
}

NEST_SITE_RULES = {
    "Ground": [r"\bground[- ]nest", r"\bon the ground\b"],
    "Tree": [r"\bnests? in trees\b", r"\btree[- ]nest\b"],
    "Cavity": [r"\bcavity[- ]nest", r"\bnests? in cavities\b", r"\bhole[- ]nest\b"],
    "Cliff": [r"\bcliff\b", r"\brock face\b"],
    "Reedbed": [r"\breeds?\b", r"\breedbed\b"],
}

THREAT_RULES = {
    "Habitat Loss": [r"\bhabitat loss\b", r"\bhabitat destruction\b", r"\bdeforestation\b", r"\bdrainage\b", r"\bland conversion\b"],
    "Habitat Fragmentation": [r"\bfragmentation\b"],
    "Invasive Species": [r"\binvasive\b", r"\bintroduced predators?\b", r"\bexotic predators?\b", r"\bferal (?:cats?|dogs?)\b", r"\brats?\b"],
    "Hunting": [r"\bhunting\b", r"\btrapping\b", r"\bpersecution\b", r"\bpoaching\b"],
    "Climate Change": [r"\bclimate change\b", r"\bsea-level rise\b", r"\bwarming\b"],
    "Pollution": [r"\bpollution\b", r"\bpesticides?\b", r"\bcontamination\b", r"\boil spill\b"],
    "Hybridization": [r"\bhybridization\b"],
    "Human Disturbance": [r"\bdisturbance\b", r"\btourism\b", r"\bhuman activity\b"],
    "Overgrazing": [r"\bovergrazing\b"],
    "Water Management": [r"\bwater extraction\b", r"\bdam(?:ming)?\b", r"\bwetland drainage\b"],
}

GEOGRAPHY_RULES = {
    "Neotropics": [r"\bneotropic", r"\bamazon\b", r"\bsouth america\b", r"\bcentral america\b", r"\bcaribbean\b"],
    "Nearctic": [r"\bnorth america\b", r"\bnearctic\b"],
    "Palearctic": [r"\bpalearctic\b", r"\beurope\b", r"\bcentral asia\b", r"\bnorth africa\b", r"\bwestern palearctic\b"],
    "Afrotropics": [r"\bsub-saharan africa\b", r"\bafrotropic\b", r"\bafrica south of the sahara\b"],
    "Indomalaya": [r"\bindia\b", r"\bsouth asia\b", r"\bsoutheast asia\b", r"\bindomalaya\b"],
    "Australasia": [r"\baustralia\b", r"\bnew guinea\b", r"\baustralasia\b"],
    "Oceania": [r"\bpolynesia\b", r"\bmicronesia\b", r"\bmelanesia\b", r"\boceania\b"],
    "Antarctic/Subantarctic": [r"\bantarctic\b", r"\bsubantarctic\b"],
    "Indian Ocean Islands": [r"\bindian ocean\b", r"\bmascarene\b", r"\bseychelles\b", r"\bmadagascar\b"],
}

CONSERVATION_ACTION_RULES = {
    "Protected Areas": [r"\bprotected area", r"\bnational park", r"\breserve\b"],
    "Habitat Restoration": [r"\brestoration\b", r"\brestore habitat\b"],
    "Predator Control": [r"\bpredator control\b", r"\binvasive control\b"],
    "Captive Breeding": [r"\bcaptive breeding\b", r"\breintroduction\b"],
    "Monitoring": [r"\bmonitoring\b", r"\bsurvey(?:s)?\b"],
}

RESEARCH_PRIORITY_RULES = {
    "Distribution Surveys": [r"\bdistribution\b", r"\bsurvey(?:s)?\b"],
    "Population Monitoring": [r"\bpopulation monitoring\b", r"\bpopulation estimate\b"],
    "Breeding Biology": [r"\bbreeding biology\b", r"\bnest success\b"],
    "Migration Ecology": [r"\bmigration\b", r"\bmovement ecology\b"],
    "Threat Assessment": [r"\bthreat assessment\b", r"\bimpact of\b"],
}

STATUS_CANONICAL = {
    "LC": "Least Concern",
    "Least Concern": "Least Concern",
    "NT": "Near Threatened",
    "Near Threatened": "Near Threatened",
    "VU": "Vulnerable",
    "Vulnerable": "Vulnerable",
    "EN": "Endangered",
    "Endangered": "Endangered",
    "CR": "Critically Endangered",
    "Critically Endangered": "Critically Endangered",
    "EW": "Extinct in the Wild",
    "Extinct in the Wild": "Extinct in the Wild",
    "EX": "Extinct",
    "Extinct": "Extinct",
    "DD": "Data Deficient",
    "Data Deficient": "Data Deficient",
    "NE": "Not Evaluated",
    "Not Evaluated": "Not Evaluated",
}

FACT_TYPE_TO_OBJECT_TYPE = {
    "INHABITS": "Habitat",
    "FOUND_IN": "Geography",
    "OCCURS_IN": "Geography",
    "BREEDS_IN": "Geography",
    "WINTERS_IN": "Geography",
    "PREYS_ON": "Food",
    "EATS": "Food",
    "EXHIBITS": "Behavior",
    "FORAGES_BY": "Behavior",
    "HAS_VOCALIZATION": "Behavior",
    "NESTS_AT": "Behavior",
    "THREATENED_BY": "Threat",
    "HAS_STATUS": "ConservationStatus",
    "RELATED_TO": "Species",
    "SIMILAR_TO": "Species",
    "HYBRIDIZES_WITH": "Species",
    "MANAGED_BY": "Behavior",
    "REQUIRES_RESEARCH": "Behavior",
}

CANONICAL_FACT_TYPES = (
    "INHABITS",
    "FOUND_IN",
    "PREYS_ON",
    "EXHIBITS",
    "THREATENED_BY",
    "HAS_STATUS",
    "RELATED_TO",
)


def normalize_before_rules(text: str) -> str:
    output = text
    for pattern, replacement in NORMALIZATION_REPLACEMENTS.items():
        output = re.sub(pattern, replacement, output, flags=re.IGNORECASE)
    return output


def canonical_status(raw: str) -> str:
    value = (raw or "NE").strip()
    if not value:
        value = "NE"
    return STATUS_CANONICAL.get(value, STATUS_CANONICAL.get(value.upper(), value))


def extract_labels(text: str, rule_map: dict[str, list[str]], max_n: int | None = None) -> list[str]:
    lowered = normalize_before_rules((text or "").lower())
    hits: list[str] = []
    for label, patterns in rule_map.items():
        for pattern in patterns:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                hits.append(label)
                break
    if max_n is None:
        return hits
    return hits[:max_n]


def concept_category_for_fact_type(fact_type: str) -> str:
    return FACT_TYPE_TO_OBJECT_TYPE.get(fact_type, "Unknown")
