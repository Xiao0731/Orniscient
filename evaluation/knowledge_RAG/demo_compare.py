from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INTENT_ROUTES = [
    {
        "name": "conservation_threats",
        "keywords": {
            "threat",
            "threats",
            "conservation",
            "endangered",
            "vulnerable",
            "human",
            "humans",
            "predator",
            "parasite",
            "disease",
            "mortality",
            "decline",
            "risk",
        },
        "domains": {"ConservationAndResearch"},
        "predicates": {
            "THREATENED_BY",
            "HAS_CONSERVATION_ACTION",
            "HAS_IUCN_STATUS",
            "HAS_POPULATION_TREND",
            "INTERACTS_WITH_HUMANS",
            "HAS_PREDATOR",
            "HAS_PARASITE",
            "HAS_DISEASE",
            "HAS_MORTALITY_CAUSE",
            "REQUIRES_RESEARCH_ON",
        },
        "chapter_hints": {"conservation", "management", "population", "demography"},
    },
    {
        "name": "diet_foraging",
        "keywords": {"diet", "eat", "eats", "food", "forage", "forages", "foraging", "feed", "feeds", "feeding", "prey"},
        "domains": {"EcologyAndDiet"},
        "predicates": {"EATS_ITEM", "EATS_CATEGORY", "FORAGES_BY", "FORAGES_IN_STRATUM", "HAS_ECOLOGICAL_ROLE"},
        "chapter_hints": {"diet", "food", "foraging", "ecology"},
    },
    {
        "name": "habitat",
        "keywords": {
            "habitat",
            "habitats",
            "use",
            "uses",
            "biome",
            "forest",
            "wetland",
            "wetlands",
            "marsh",
            "marshes",
            "pond",
            "ponds",
            "stream",
            "streams",
            "lagoon",
            "lagoons",
            "estuary",
            "estuaries",
            "grassland",
            "microhabitat",
            "woodland",
            "mangrove",
        },
        "domains": {"Habitat"},
        "predicates": {"INHABITS_BIOME", "USES_MICROHABITAT"},
        "chapter_hints": {"habitat", "ecology"},
    },
    {
        "name": "breeding_life_history",
        "keywords": {"breed", "breeds", "breeding", "nest", "nests", "egg", "eggs", "clutch", "parent", "parental", "incubation", "fledging"},
        "domains": {"LifeHistoryAndBreeding"},
        "predicates": {
            "BREEDS_DURING",
            "NESTS_AT",
            "HAS_NEST_STRUCTURE",
            "HAS_EGG_TRAIT",
            "HAS_CLUTCH_SIZE",
            "HAS_PARENTAL_ROLE",
            "HAS_INCUBATION_PERIOD",
            "HAS_FLEDGING_PERIOD",
            "HAS_DEVELOPMENT_NOTE",
            "HAS_DEMOGRAPHIC_NOTE",
        },
        "chapter_hints": {"breeding", "reproduction", "life", "history"},
    },
    {
        "name": "morphology_identification",
        "keywords": {"plumage", "identify", "identification", "morphology", "body", "bill", "wing", "tail", "tarsus", "mass", "length", "diagnostic"},
        "domains": {"MorphologyAndIdentification"},
        "predicates": {
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
        },
        "chapter_hints": {"identification", "plumage", "measurements", "appearance"},
    },
    {
        "name": "vocal_behavior",
        "keywords": {"call", "calls", "song", "songs", "vocal", "sound", "behavior", "courtship", "mating", "pair", "territorial", "locomotion"},
        "domains": {"VocalAndBehavior"},
        "predicates": {
            "HAS_VOCALIZATION_TYPE",
            "CALLS_DURING",
            "HAS_NONVOCAL_SOUND",
            "HAS_SOUND_DIAGNOSTIC",
            "HAS_SOCIAL_BEHAVIOR",
            "HAS_TERRITORIAL_BEHAVIOR",
            "HAS_LOCOMOTION_STYLE",
            "HAS_FLIGHT_ABILITY",
            "HAS_DAILY_ACTIVITY_PATTERN",
            "HAS_COURTSHIP_BEHAVIOR",
            "HAS_MATING_SYSTEM",
            "HAS_PAIR_BOND",
            "HAS_COPULATION_BEHAVIOR",
            "HAS_AGONISTIC_BEHAVIOR",
        },
        "chapter_hints": {"sounds", "vocal", "behavior", "behavioral"},
    },
    {
        "name": "distribution_movement",
        "keywords": {"range", "occur", "occurs", "distribution", "migrate", "migrates", "migration", "winter", "winters", "endemic", "elevation"},
        "domains": {"DistributionAndMovement"},
        "predicates": {
            "OCCURS_IN",
            "ENDEMIC_TO",
            "BREEDS_IN",
            "WINTERS_IN",
            "MIGRATES_VIA",
            "HAS_MIGRATION_PATTERN",
            "HAS_ELEVATION_RANGE",
            "HAS_DISTRIBUTION_NOTE",
        },
        "chapter_hints": {"distribution", "movement", "migration", "range"},
    },
    {
        "name": "taxonomy",
        "keywords": {"taxonomy", "taxonomic", "subspecies", "related", "hybrid", "hybridizes", "classification", "phylogeny"},
        "domains": {"TaxonomyAndPhylogeny"},
        "predicates": {
            "HAS_SUBSPECIES",
            "HAS_GEOGRAPHIC_VARIATION",
            "HAS_SUBSPECIES_TRAIT",
            "HAS_SUBSPECIES_DISTRIBUTION",
            "HYBRIDIZES_WITH",
            "RELATED_TO",
            "HAS_CLASSIFICATION_HISTORY",
            "HAS_TAXONOMIC_NOTE",
        },
        "chapter_hints": {"systematics", "taxonomy", "taxonomic", "subspecies"},
    },
]

PREFERRED_PREDICATE_ORDER = {
    "conservation_threats": [
        "THREATENED_BY",
        "INTERACTS_WITH_HUMANS",
        "HAS_PREDATOR",
        "HAS_MORTALITY_CAUSE",
        "HAS_PARASITE",
        "HAS_DISEASE",
        "HAS_POPULATION_TREND",
        "HAS_IUCN_STATUS",
        "HAS_CONSERVATION_ACTION",
        "REQUIRES_RESEARCH_ON",
    ],
    "diet_foraging": ["EATS_ITEM", "EATS_CATEGORY", "FORAGES_BY", "FORAGES_IN_STRATUM", "HAS_ECOLOGICAL_ROLE"],
    "habitat": ["INHABITS_BIOME", "USES_MICROHABITAT"],
    "breeding_life_history": [
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
    "morphology_identification": [
        "HAS_DIAGNOSTIC_TRAIT",
        "HAS_PLUMAGE_TRAIT",
        "HAS_STRUCTURE_TRAIT",
        "HAS_SEXUAL_DIMORPHISM",
        "HAS_AGE_DIMORPHISM",
        "HAS_BODY_LENGTH",
        "HAS_BODY_MASS",
        "HAS_WING_LENGTH",
        "HAS_TAIL_LENGTH",
        "HAS_BILL_LENGTH",
        "HAS_TARSUS_LENGTH",
        "HAS_WINGSPAN",
        "HAS_MOLT_PATTERN",
    ],
    "vocal_behavior": [
        "HAS_VOCALIZATION_TYPE",
        "CALLS_DURING",
        "HAS_SOUND_DIAGNOSTIC",
        "HAS_SOCIAL_BEHAVIOR",
        "HAS_COURTSHIP_BEHAVIOR",
        "HAS_TERRITORIAL_BEHAVIOR",
        "HAS_MATING_SYSTEM",
        "HAS_PAIR_BOND",
        "HAS_LOCOMOTION_STYLE",
        "HAS_FLIGHT_ABILITY",
        "HAS_DAILY_ACTIVITY_PATTERN",
        "HAS_NONVOCAL_SOUND",
        "HAS_COPULATION_BEHAVIOR",
        "HAS_AGONISTIC_BEHAVIOR",
    ],
    "distribution_movement": [
        "OCCURS_IN",
        "ENDEMIC_TO",
        "BREEDS_IN",
        "WINTERS_IN",
        "MIGRATES_VIA",
        "HAS_MIGRATION_PATTERN",
        "HAS_ELEVATION_RANGE",
        "HAS_DISTRIBUTION_NOTE",
    ],
    "taxonomy": [
        "HAS_SUBSPECIES",
        "HAS_TAXONOMIC_NOTE",
        "HAS_CLASSIFICATION_HISTORY",
        "RELATED_TO",
        "HYBRIDIZES_WITH",
        "HAS_GEOGRAPHIC_VARIATION",
        "HAS_SUBSPECIES_TRAIT",
        "HAS_SUBSPECIES_DISTRIBUTION",
    ],
}

PREFERRED_PREDICATE_ORDER["taxonomy_morphology_variation"] = (
    PREFERRED_PREDICATE_ORDER["taxonomy"] + PREFERRED_PREDICATE_ORDER["morphology_identification"]
)

TAXONOMY_QUERY_TERMS = {"taxonomy", "taxonomic", "subspecies", "classification", "phylogeny", "systematics"}
MORPHOLOGY_QUERY_TERMS = {
    "morphology",
    "plumage",
    "trait",
    "traits",
    "variation",
    "identify",
    "identification",
    "diagnostic",
    "measurements",
}
BREEDING_QUERY_TERMS = {"egg", "eggs", "nest", "nests", "breeding", "breed", "clutch", "clutches"}
BREEDING_FACT_TERMS = {"egg", "eggs", "nest", "nests", "breeding", "breed", "clutch", "clutches", "incubation", "fledging"}
PLANT_FAMILY_TERMS = {
    "annonaceae",
    "arecaceae",
    "combretaceae",
    "elaeocarpaceae",
    "icacinaceae",
    "lauraceae",
    "myrtaceae",
    "pandanaceae",
    "rubiaceae",
    "sapindaceae",
    "sapotaceae",
}
FRUIT_SEED_TERMS = {"fruit", "fruits", "frugivore", "frugivorous", "seed", "seeds", "berries", "berry", "drupes", "fig", "figs"}
FUNGI_TERMS = {"fungi", "fungus", "mushroom", "mushrooms", "bracket"}
INVERTEBRATE_TERMS = {"invertebrate", "invertebrates", "insect", "insects", "beetle", "beetles", "larvae", "worms", "snails", "mollusks"}
VERTEBRATE_TERMS = {"vertebrate", "vertebrates", "lizard", "lizards", "frog", "frogs", "snake", "snakes", "mammal", "mammals", "bird", "birds"}
CARRION_TERMS = {"carrion", "roadkill", "carcass", "carcasses", "dead"}
GENERAL_DIET_TERMS = {"primarily", "mainly", "mostly", "chiefly", "diet", "eats", "eat", "feeding", "food", "omnivore", "omnivorous", "also"}
FORAGING_BEHAVIOR_TERMS = {"forage", "forages", "foraging", "glean", "gleans", "probe", "probes", "ground", "floor", "stratum"}
ECOLOGICAL_ROLE_TERMS = {"dispersal", "disperser", "disperses", "pollination", "pollinator", "ecological", "role"}
MINERAL_OR_INCIDENTAL_DIET_TERMS = {"earth", "soil", "mineral", "minerals"}


@dataclass
class RetrievedItem:
    fact_id: str
    predicate: str
    fact_domain: str
    object_text: str
    source_chunk_id: str
    source_chapter: str
    evidence_id: str
    evidence_quote: str
    chunk_text: str = ""
    score: float = 0.0


@dataclass
class DemoGraph:
    taxa: list[dict[str, Any]]
    taxa_by_id: dict[str, dict[str, Any]]
    facts_by_taxon: dict[str, list[dict[str, Any]]]
    evidences_by_id: dict[str, dict[str, Any]]
    links_by_fact: dict[str, list[str]]
    chunks_by_id: dict[str, dict[str, Any]]
    available_domains: set[str]
    available_predicates: set[str]
    available_chapters: set[str]
    name_index: dict[str, list[str]]


@dataclass
class APIConfig:
    api_key: str
    api_base: str
    key_source: str
    final_url: str


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9\-]{2,}", value.lower()))


def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JSONL in {path}: line={line_no} error={exc.msg}") from exc
            if isinstance(row, dict):
                yield row


def parse_env_file_fallback(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def load_env(env_file: str) -> str:
    if env_file:
        path = Path(env_file)
        if path.exists():
            if load_dotenv:
                load_dotenv(dotenv_path=path, override=False)
            else:
                parse_env_file_fallback(path)
            return str(path)
        return "none"
    default_env = PROJECT_ROOT / ".env"
    if default_env.exists():
        if load_dotenv:
            load_dotenv(dotenv_path=default_env, override=False)
        else:
            parse_env_file_fallback(default_env)
        return str(default_env)
    return "none"


def object_label(fact: dict[str, Any]) -> str:
    label = clean(fact.get("object_text") or fact.get("object_canonical_name") or fact.get("object_canonical_id"))
    if label:
        return label
    value_min = fact.get("value_min")
    value_max = fact.get("value_max")
    unit = clean(fact.get("unit"))
    if value_min is not None or value_max is not None:
        if value_min is not None and value_max is not None and value_min != value_max:
            return clean(f"{value_min}-{value_max} {unit}")
        return clean(f"{value_min if value_min is not None else value_max} {unit}")
    return ""


def sample_items(target: str) -> list[RetrievedItem]:
    chunk_prefix = target or "Casuarius casuarius"
    return [
        RetrievedItem(
            fact_id="sample_fact_1",
            predicate="THREATENED_BY",
            fact_domain="ConservationAndResearch",
            object_text="habitat loss and hunting pressure",
            source_chunk_id=f"{chunk_prefix}::sample-threats",
            source_chapter="Conservation",
            evidence_id="sample_evidence_1",
            evidence_quote="Sample evidence placeholder for interface demonstration.",
            chunk_text="Sample chunk excerpt: conservation accounts often summarize direct threats, human pressures, and habitat change.",
            score=10.0,
        ),
        RetrievedItem(
            fact_id="sample_fact_2",
            predicate="INTERACTS_WITH_HUMANS",
            fact_domain="ConservationAndResearch",
            object_text="affected by roads, hunting, or land-use change",
            source_chunk_id=f"{chunk_prefix}::sample-human-interactions",
            source_chapter="Conservation",
            evidence_id="sample_evidence_2",
            evidence_quote="Sample evidence placeholder for interface demonstration.",
            chunk_text="Sample chunk excerpt: local interactions with humans can be important for conservation planning.",
            score=9.0,
        ),
    ]


def infer_intent(question: str) -> dict[str, Any]:
    q_tokens = tokens(question)
    if (q_tokens & TAXONOMY_QUERY_TERMS) and (q_tokens & MORPHOLOGY_QUERY_TERMS):
        return {
            "name": "taxonomy_morphology_variation",
            "domains": {"TaxonomyAndPhylogeny", "MorphologyAndIdentification"},
            "predicates": set(PREFERRED_PREDICATE_ORDER["taxonomy_morphology_variation"]),
            "keywords": TAXONOMY_QUERY_TERMS | MORPHOLOGY_QUERY_TERMS,
            "chapter_hints": {"systematics", "identification", "measurements"},
            "preferred_chapters": ["Systematics", "Identification", "Measurements"],
        }
    best_route: dict[str, Any] | None = None
    best_overlap = 0
    for route in INTENT_ROUTES:
        overlap = len(q_tokens & route["keywords"])
        if overlap > best_overlap:
            best_overlap = overlap
            best_route = route
    if not best_route:
        return {"name": "general", "domains": set(), "predicates": set(), "keywords": set(), "chapter_hints": set()}
    return best_route


def load_chunks(paths: list[str], wanted_chunk_ids: set[str]) -> dict[str, str]:
    if not paths or not wanted_chunk_ids:
        return {}
    chunks: dict[str, str] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        for row in iter_jsonl(path):
            chunk_id = clean(row.get("chunk_id") or row.get("source_chunk_id"))
            if chunk_id in wanted_chunk_ids:
                chunks[chunk_id] = clean(row.get("text") or row.get("cleaned_text") or row.get("raw_text"))
    return chunks


def resolve_target_from_processed_chunks(claims_dir: Path, *, target: str, question: str) -> tuple[str, set[str], str]:
    processed_path = claims_dir / "processed_unique_chunks.jsonl"
    if not processed_path.exists():
        if target:
            return target, set(), f"processed_unique_chunks.jsonl missing; using literal target={target!r}"
        return "", set(), "processed_unique_chunks.jsonl missing and --target was not provided"

    query_text = target or question
    query_norm = norm_name(query_text)
    query_tokens = set(query_norm.split())
    matches: dict[str, Counter] = defaultdict(Counter)
    name_by_taxon: dict[str, str] = {}
    for row in iter_jsonl(processed_path):
        taxon_id = clean(row.get("subject_taxon_id"))
        if not taxon_id:
            continue
        chunk_id = clean(row.get("chunk_id") or row.get("source_chunk_id"))
        source_doc_id = clean(row.get("source_doc_id"))
        chunk_name = chunk_id.split("::", 1)[0]
        doc_name = re.sub(r"^bow_(species|family)_", "", source_doc_id).replace("_", " ")
        candidates = [chunk_name, doc_name, source_doc_id]
        for candidate in candidates:
            candidate_norm = norm_name(candidate)
            candidate_tokens = set(candidate_norm.split())
            exact = bool(target) and candidate_norm == norm_name(target)
            contains = bool(target) and norm_name(target) in candidate_norm
            question_hit = not target and candidate_tokens and candidate_tokens.issubset(query_tokens)
            if exact or contains or question_hit:
                matches[taxon_id][candidate_norm] += 1
                name_by_taxon.setdefault(taxon_id, chunk_name or doc_name)
    if not matches:
        if target:
            return target, set(), f"no taxon_id match for target={target!r}; falling back to evidence/chunk text matching"
        return "", set(), "could not infer a unique target from the question; please pass --target"
    if not target and len(matches) > 1:
        ranked = sorted(matches.items(), key=lambda item: -sum(item[1].values()))
        if len(ranked) > 1 and sum(ranked[0][1].values()) == sum(ranked[1][1].values()):
            names = [name_by_taxon.get(taxon_id, taxon_id) for taxon_id, _ in ranked[:5]]
            return "", set(), "ambiguous target candidates: " + ", ".join(names) + "; please pass --target"
    best_taxon = max(matches.items(), key=lambda item: sum(item[1].values()))[0]
    return name_by_taxon.get(best_taxon, target or best_taxon), {best_taxon}, f"matched target_taxon_id={best_taxon}"


def retrieve_kg_items(
    *,
    claims_dir: Path,
    facts_dir: Path,
    chunks_paths: list[str],
    question: str,
    target: str,
    top_k: int,
) -> tuple[str, str, list[RetrievedItem]]:
    resolved_target, target_taxon_ids, target_note = resolve_target_from_processed_chunks(claims_dir, target=target, question=question)
    if not resolved_target and not target_taxon_ids:
        raise RuntimeError(target_note)

    intent = infer_intent(question)
    question_tokens = tokens(question)
    target_norm = norm_name(resolved_target or target)
    target_doc_token = target_norm.replace(" ", "_")

    candidate_facts: dict[str, dict[str, Any]] = {}
    for fact_path in (facts_dir / "species_facts.jsonl", facts_dir / "family_facts.jsonl"):
        for fact in iter_jsonl(fact_path):
            taxon_id = clean(fact.get("subject_taxon_id"))
            if target_taxon_ids and taxon_id not in target_taxon_ids:
                continue
            if intent["domains"] and clean(fact.get("fact_domain")) not in intent["domains"]:
                continue
            if intent["predicates"] and clean(fact.get("predicate")) not in intent["predicates"]:
                continue
            fact_id = clean(fact.get("fact_id"))
            if fact_id:
                candidate_facts[fact_id] = fact

    if not candidate_facts and target_taxon_ids and intent["name"] != "general":
        for fact_path in (facts_dir / "species_facts.jsonl", facts_dir / "family_facts.jsonl"):
            for fact in iter_jsonl(fact_path):
                taxon_id = clean(fact.get("subject_taxon_id"))
                if taxon_id in target_taxon_ids:
                    fact_id = clean(fact.get("fact_id"))
                    if fact_id:
                        candidate_facts[fact_id] = fact

    if not candidate_facts:
        raise RuntimeError(f"No local facts matched target={resolved_target!r}. Use --sample-mode or --demo-data to preview the interface.")

    evidence_ids_by_fact: dict[str, list[str]] = defaultdict(list)
    wanted_fact_ids = set(candidate_facts)
    for link in iter_jsonl(facts_dir / "fact_evidence_links.jsonl"):
        fact_id = clean(link.get("fact_id"))
        if fact_id in wanted_fact_ids:
            evidence_ids_by_fact[fact_id].append(clean(link.get("evidence_id")))
    wanted_evidence_ids = {evidence_id for values in evidence_ids_by_fact.values() for evidence_id in values if evidence_id}

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for evidence in iter_jsonl(facts_dir / "evidences.jsonl"):
        evidence_id = clean(evidence.get("evidence_id"))
        if evidence_id not in wanted_evidence_ids:
            continue
        if not target_taxon_ids:
            chunk_id_norm = norm_name(clean(evidence.get("source_chunk_id")))
            doc_norm = norm_name(clean(evidence.get("source_doc_id")).replace("_", " "))
            if target_norm and target_norm not in chunk_id_norm and target_doc_token not in doc_norm:
                continue
        evidence_by_id[evidence_id] = evidence

    rows: list[RetrievedItem] = []
    for fact_id, fact in candidate_facts.items():
        fact_text = " ".join([clean(fact.get("predicate")), clean(fact.get("fact_domain")), object_label(fact)])
        for evidence_id in evidence_ids_by_fact.get(fact_id, []):
            evidence = evidence_by_id.get(evidence_id)
            if not evidence:
                continue
            evidence_text = clean(evidence.get("evidence_quote"))
            score_text = " ".join([fact_text, evidence_text, clean(evidence.get("source_chapter"))])
            score = len(question_tokens & tokens(score_text)) + float(fact.get("confidence") or 0.0)
            if intent["predicates"] and clean(fact.get("predicate")) in intent["predicates"]:
                score += 3.0
            if intent["domains"] and clean(fact.get("fact_domain")) in intent["domains"]:
                score += 2.0
            rows.append(
                RetrievedItem(
                    fact_id=fact_id,
                    predicate=clean(fact.get("predicate")),
                    fact_domain=clean(fact.get("fact_domain")),
                    object_text=object_label(fact),
                    source_chunk_id=clean(evidence.get("source_chunk_id")),
                    source_chapter=clean(evidence.get("source_chapter")),
                    evidence_id=evidence_id,
                    evidence_quote=evidence_text,
                    score=score,
                )
            )

    rows = sorted(rows, key=lambda item: (-item.score, item.predicate, item.source_chunk_id))[:top_k]
    chunk_texts = load_chunks(chunks_paths, {row.source_chunk_id for row in rows})
    rows = [RetrievedItem(**{**row.__dict__, "chunk_text": chunk_texts.get(row.source_chunk_id, "")}) for row in rows]
    return resolved_target or target, f"{target_note}; intent={intent['name']}", rows


def load_demo_graph(demo_data: Path) -> DemoGraph:
    required_files = [
        "sample_taxa.jsonl",
        "sample_facts.jsonl",
        "sample_evidences.jsonl",
        "sample_fact_evidence_links.jsonl",
        "sample_chunks.jsonl",
    ]
    if not demo_data.exists():
        raise FileNotFoundError(
            f"Demo data directory not found: {demo_data}. "
            "Use --demo-data to point to demo_data/sample_100_taxa, or restore the public demo graph."
        )
    missing = [name for name in required_files if not (demo_data / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Demo data directory is incomplete: {demo_data}. Missing: {', '.join(missing)}. "
            "Restore demo_data/sample_100_taxa or pass --demo-data to a complete demo graph."
        )
    taxa = list(iter_jsonl(demo_data / "sample_taxa.jsonl"))
    taxa_by_id = {clean(row.get("canonical_taxon_id")): row for row in taxa if clean(row.get("canonical_taxon_id"))}

    facts_by_taxon: dict[str, list[dict[str, Any]]] = defaultdict(list)
    available_domains: set[str] = set()
    available_predicates: set[str] = set()
    for fact in iter_jsonl(demo_data / "sample_facts.jsonl"):
        taxon_id = clean(fact.get("subject_taxon_id"))
        facts_by_taxon[taxon_id].append(fact)
        if clean(fact.get("fact_domain")):
            available_domains.add(clean(fact.get("fact_domain")))
        if clean(fact.get("predicate")):
            available_predicates.add(clean(fact.get("predicate")))

    evidences_by_id = {
        clean(row.get("evidence_id")): row
        for row in iter_jsonl(demo_data / "sample_evidences.jsonl")
        if clean(row.get("evidence_id"))
    }
    links_by_fact: dict[str, list[str]] = defaultdict(list)
    for link in iter_jsonl(demo_data / "sample_fact_evidence_links.jsonl"):
        fact_id = clean(link.get("fact_id"))
        evidence_id = clean(link.get("evidence_id"))
        if fact_id and evidence_id:
            links_by_fact[fact_id].append(evidence_id)

    chunks_by_id = {
        clean(row.get("source_chunk_id")): row
        for row in iter_jsonl(demo_data / "sample_chunks.jsonl")
        if clean(row.get("source_chunk_id"))
    }

    available_chapters: set[str] = set()
    for evidence in evidences_by_id.values():
        if clean(evidence.get("source_chapter")):
            available_chapters.add(clean(evidence.get("source_chapter")))
    for chunk in chunks_by_id.values():
        if clean(chunk.get("source_chapter")):
            available_chapters.add(clean(chunk.get("source_chapter")))

    name_index: dict[str, list[str]] = defaultdict(list)
    for taxon in taxa:
        taxon_id = clean(taxon.get("canonical_taxon_id"))
        names = [
            clean(taxon.get("common_name")),
            clean(taxon.get("scientific_name")),
            *[clean(value) for value in (taxon.get("aliases") or [])],
        ]
        for name in names:
            if name:
                name_index[norm_name(name)].append(taxon_id)

    return DemoGraph(
        taxa=taxa,
        taxa_by_id=taxa_by_id,
        facts_by_taxon=facts_by_taxon,
        evidences_by_id=evidences_by_id,
        links_by_fact=links_by_fact,
        chunks_by_id=chunks_by_id,
        available_domains=available_domains,
        available_predicates=available_predicates,
        available_chapters=available_chapters,
        name_index=dict(name_index),
    )


def format_taxon(taxon: dict[str, Any]) -> str:
    common = clean(taxon.get("common_name"))
    scientific = clean(taxon.get("scientific_name"))
    if common and scientific and common != scientific:
        return f"{common} / {scientific}"
    return common or scientific or clean(taxon.get("canonical_taxon_id"))


def demo_taxa_examples(graph: DemoGraph, limit: int = 12) -> str:
    return ", ".join(format_taxon(taxon) for taxon in graph.taxa[:limit])


def resolve_demo_target(graph: DemoGraph, question: str, explicit_target: str = "") -> tuple[str, str]:
    query_values = [explicit_target] if explicit_target else [question]
    all_names = list(graph.name_index)

    if explicit_target:
        norm = norm_name(explicit_target)
        exact_ids = graph.name_index.get(norm, [])
        if len(set(exact_ids)) == 1:
            return exact_ids[0], f"resolved explicit --target by exact name: {explicit_target}"

    q_norm = norm_name(question)
    q_padded = f" {q_norm} "
    exact_hits: list[str] = []
    if not explicit_target:
        for name_norm, taxon_ids in graph.name_index.items():
            if f" {name_norm} " in q_padded:
                exact_hits.extend(taxon_ids)
        unique_hits = list(dict.fromkeys(exact_hits))
        if len(unique_hits) == 1:
            return unique_hits[0], "resolved target from question by exact common/scientific/alias match"
        if len(unique_hits) > 1:
            names = ", ".join(format_taxon(graph.taxa_by_id[taxon_id]) for taxon_id in unique_hits[:8])
            raise RuntimeError(f"Ambiguous target in question: {names}. Please pass --target.")

    for query in query_values:
        close = difflib.get_close_matches(norm_name(query), all_names, n=3, cutoff=0.72)
        if close:
            taxon_ids = list(dict.fromkeys(taxon_id for name in close for taxon_id in graph.name_index.get(name, [])))
            if len(taxon_ids) == 1:
                return taxon_ids[0], f"resolved target by fuzzy name match: {close[0]}"
            names = ", ".join(format_taxon(graph.taxa_by_id[taxon_id]) for taxon_id in taxon_ids[:8])
            raise RuntimeError(f"Ambiguous fuzzy target candidates: {names}. Please pass --target.")

    raise RuntimeError(
        "Could not resolve a target taxon from the question. "
        f"Please pass --target. Demo taxa examples: {demo_taxa_examples(graph)}"
    )


def preferred_chapters_for_route(graph: DemoGraph, route: dict[str, Any]) -> list[str]:
    hints = route.get("chapter_hints", set())
    scored: list[tuple[int, str]] = []
    for chapter in graph.available_chapters:
        chapter_tokens = tokens(chapter)
        overlap = len(chapter_tokens & hints)
        if overlap:
            scored.append((overlap, chapter))
    return [chapter for _, chapter in sorted(scored, key=lambda item: (-item[0], item[1]))[:6]]


def query_terms_from_question(question: str) -> list[str]:
    stop = {"what", "which", "where", "when", "does", "main", "about", "describe", "tell", "with", "from", "that", "this", "bird", "the", "are", "for", "and"}
    return sorted(term for term in tokens(question) if term not in stop)[:16]


def deterministic_demo_planner(graph: DemoGraph, question: str, explicit_target: str = "") -> tuple[dict[str, Any], dict[str, Any], str]:
    taxon_id, note = resolve_demo_target(graph, question, explicit_target)
    taxon = graph.taxa_by_id[taxon_id]
    route = infer_intent(question)
    preferred_chapters = [
        chapter for chapter in route.get("preferred_chapters", []) if chapter in graph.available_chapters
    ] or preferred_chapters_for_route(graph, route)
    planner = {
        "target": clean(taxon.get("common_name")) or clean(taxon.get("scientific_name")),
        "target_scientific_name": clean(taxon.get("scientific_name")),
        "intent": route["name"],
        "preferred_domains": sorted(domain for domain in route.get("domains", set()) if domain in graph.available_domains),
        "preferred_predicates": [
            predicate
            for predicate in PREFERRED_PREDICATE_ORDER.get(route["name"], sorted(route.get("predicates", set())))
            if predicate in graph.available_predicates
        ],
        "preferred_chapters": preferred_chapters,
        "query_terms": query_terms_from_question(question),
        "need_chunk_context": True,
        "target_taxon_id": taxon_id,
        "planner_mode": "deterministic",
    }
    return planner, taxon, note


def build_planner_prompt(graph: DemoGraph, question: str) -> list[dict[str, str]]:
    taxa_lines = []
    for taxon in graph.taxa:
        aliases = ", ".join(clean(value) for value in (taxon.get("aliases") or []) if clean(value))
        taxa_lines.append(
            f"- common_name={clean(taxon.get('common_name'))}; scientific_name={clean(taxon.get('scientific_name'))}; aliases={aliases}"
        )
    schema = {
        "target": "common name if available",
        "target_scientific_name": "scientific name",
        "intent": "short snake_case intent",
        "preferred_domains": ["one or more available fact domains"],
        "preferred_predicates": ["one or more available controlled predicates"],
        "preferred_chapters": ["one or more available BOW chapter names"],
        "query_terms": ["plain-language search terms"],
        "need_chunk_context": True,
    }
    user = "\n\n".join(
        [
            "Expert question:",
            question,
            "Available demo taxa:",
            "\n".join(taxa_lines),
            "Available BOW chapter names:",
            "\n".join(f"- {chapter}" for chapter in sorted(graph.available_chapters)),
            "Available fact domains:",
            "\n".join(f"- {domain}" for domain in sorted(graph.available_domains)),
            "Available controlled predicates:",
            "\n".join(f"- {predicate}" for predicate in sorted(graph.available_predicates)),
            "Return only JSON matching this schema. Do not answer the expert question.",
            json.dumps(schema, ensure_ascii=False, indent=2),
        ]
    )
    return [
        {
            "role": "system",
            "content": (
                "You are the Orniscient query planner. Parse the expert question into a structured retrieval request. "
                "Do not answer the question, do not generate Cypher, and do not use hidden benchmark labels."
            ),
        },
        {"role": "user", "content": user},
    ]


def parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Planner output must be a JSON object.")
    return payload


def validate_llm_planner(graph: DemoGraph, payload: dict[str, Any], question: str, explicit_target: str) -> tuple[dict[str, Any], dict[str, Any]]:
    target_query = clean(payload.get("target_scientific_name")) or clean(payload.get("target")) or explicit_target
    taxon_id, _ = resolve_demo_target(graph, question="", explicit_target=target_query)
    taxon = graph.taxa_by_id[taxon_id]

    domains = [clean(value) for value in payload.get("preferred_domains", []) if clean(value)]
    predicates = [clean(value) for value in payload.get("preferred_predicates", []) if clean(value)]
    chapters = [clean(value) for value in payload.get("preferred_chapters", []) if clean(value)]
    invalid_domains = [value for value in domains if value not in graph.available_domains]
    invalid_predicates = [value for value in predicates if value not in graph.available_predicates]
    invalid_chapters = [value for value in chapters if value not in graph.available_chapters]
    if invalid_domains or invalid_predicates or invalid_chapters:
        raise ValueError(
            "Invalid planner values: "
            f"domains={invalid_domains}, predicates={invalid_predicates}, chapters={invalid_chapters}"
        )

    planner = {
        "target": clean(taxon.get("common_name")) or clean(taxon.get("scientific_name")),
        "target_scientific_name": clean(taxon.get("scientific_name")),
        "intent": clean(payload.get("intent")) or "general",
        "preferred_domains": domains,
        "preferred_predicates": predicates,
        "preferred_chapters": chapters,
        "query_terms": [clean(value) for value in payload.get("query_terms", []) if clean(value)],
        "need_chunk_context": bool(payload.get("need_chunk_context", True)),
        "target_taxon_id": taxon_id,
        "planner_mode": "llm",
    }
    return planner, taxon


def plan_demo_query(
    graph: DemoGraph,
    question: str,
    explicit_target: str,
    planner_mode: str,
    api_args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], str, list[dict[str, str]]]:
    planner_prompt = build_planner_prompt(graph, question)
    if planner_mode == "deterministic":
        planner, taxon, note = deterministic_demo_planner(graph, question, explicit_target)
        return planner, taxon, note, planner_prompt

    if api_args.no_api:
        planner, taxon, note = deterministic_demo_planner(graph, question, explicit_target)
        note += "; --no-api selected, so llm planner was not called"
        planner["planner_mode"] = "deterministic_fallback_no_api"
        return planner, taxon, note, planner_prompt

    api_key, api_base = api_config(api_args)
    if not api_key:
        planner, taxon, note = deterministic_demo_planner(graph, question, explicit_target)
        note += "; missing API key, fell back from llm planner to deterministic planner"
        planner["planner_mode"] = "deterministic_fallback_missing_api"
        return planner, taxon, note, planner_prompt

    try:
        raw = chat_completion(planner_prompt, model=api_args.model, api_key=api_key, api_base=api_base, max_tokens=700)
        payload = parse_json_object(raw)
        planner, taxon = validate_llm_planner(graph, payload, question, explicit_target)
        return planner, taxon, "llm planner validated successfully", planner_prompt
    except Exception as exc:
        planner, taxon, note = deterministic_demo_planner(graph, question, explicit_target)
        note += f"; llm planner failed validation and fell back to deterministic planner: {exc}"
        planner["planner_mode"] = "deterministic_fallback_invalid_llm"
        return planner, taxon, note, planner_prompt


def fact_text_for_scoring(fact: dict[str, Any], evidences: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> str:
    parts = [
        clean(fact.get("predicate")),
        clean(fact.get("fact_domain")),
        object_label(fact),
        " ".join(clean(evidence.get("evidence_quote")) for evidence in evidences),
        " ".join(clean(chunk.get("text_preview")) for chunk in chunks),
    ]
    return " ".join(parts)


def diet_category(item: RetrievedItem) -> str:
    object_tokens = tokens(item.object_text)
    if object_tokens & MINERAL_OR_INCIDENTAL_DIET_TERMS:
        return "incidental_or_mineral"
    if object_tokens & CARRION_TERMS:
        return "carrion"
    if object_tokens & FUNGI_TERMS:
        return "fungi"
    if object_tokens & INVERTEBRATE_TERMS:
        return "invertebrates"
    if object_tokens & VERTEBRATE_TERMS:
        return "vertebrates"
    if object_tokens & (FRUIT_SEED_TERMS | PLANT_FAMILY_TERMS):
        return "fruit_or_seed"

    primary_tokens = tokens(" ".join([item.predicate, item.object_text, item.evidence_quote]))
    all_tokens = tokens(" ".join([item.predicate, item.object_text, item.evidence_quote, item.chunk_text]))
    if primary_tokens & MINERAL_OR_INCIDENTAL_DIET_TERMS:
        return "incidental_or_mineral"
    if item.predicate in {"FORAGES_BY", "FORAGES_IN_STRATUM"} or primary_tokens & FORAGING_BEHAVIOR_TERMS:
        return "foraging_behavior"
    if item.predicate == "HAS_ECOLOGICAL_ROLE" or primary_tokens & ECOLOGICAL_ROLE_TERMS:
        return "ecological_role"
    if primary_tokens & CARRION_TERMS:
        return "carrion"
    if primary_tokens & FUNGI_TERMS:
        return "fungi"
    if primary_tokens & INVERTEBRATE_TERMS:
        return "invertebrates"
    if primary_tokens & VERTEBRATE_TERMS:
        return "vertebrates"
    if primary_tokens & (FRUIT_SEED_TERMS | PLANT_FAMILY_TERMS):
        return "fruit_or_seed"
    if item.predicate == "EATS_CATEGORY" and all_tokens & GENERAL_DIET_TERMS:
        return "general_diet_summary"
    return "other_diet"


def is_general_diet_summary(item: RetrievedItem) -> bool:
    text_tokens = tokens(" ".join([item.object_text, item.evidence_quote]))
    nonplant_terms = FUNGI_TERMS | INVERTEBRATE_TERMS | VERTEBRATE_TERMS | CARRION_TERMS
    if item.predicate == "EATS_CATEGORY" and text_tokens & nonplant_terms:
        return True
    return bool((text_tokens & {"diet", "primarily", "predominantly", "omnivore", "omnivorous", "supplements"}) and (text_tokens & nonplant_terms))


def is_broad_diet_question(question: str) -> bool:
    q = norm_name(question)
    q_tokens = tokens(question)
    return (
        "what does" in q
        or "what do" in q
        or "diet" in q_tokens
        or "eat" in q_tokens
        or "eats" in q_tokens
        or "food" in q_tokens
        or "feeding" in q_tokens
    )


def rerank_diet_foraging(rows: list[RetrievedItem], top_k: int, question: str, max_evidence_per_chunk: int) -> list[RetrievedItem]:
    if not rows:
        return []
    broad_question = is_broad_diet_question(question)
    strict_question = bool(tokens(question) & {"strictly", "strict", "omnivore", "omnivorous", "frugivore", "frugivorous"})
    ranked = sorted(rows, key=lambda item: (-item.score, diet_category(item), item.object_text, item.fact_id))
    chunk_counts: Counter = Counter()
    selected: list[RetrievedItem] = []
    selected_fact_ids: set[str] = set()
    selected_categories: Counter = Counter()

    def can_add(item: RetrievedItem) -> bool:
        if item.fact_id in selected_fact_ids:
            return False
        if max_evidence_per_chunk > 0 and chunk_counts[item.source_chunk_id] >= max_evidence_per_chunk:
            return False
        category = diet_category(item)
        if broad_question and selected_categories[category] >= 1 and category not in {"general_diet_summary"}:
            return False
        return True

    def add_best(predicate: Any) -> bool:
        for item in ranked:
            if predicate(item) and can_add(item):
                selected.append(item)
                selected_fact_ids.add(item.fact_id)
                selected_categories[diet_category(item)] += 1
                chunk_counts[item.source_chunk_id] += 1
                return True
        return False

    if broad_question:
        add_best(lambda item: is_general_diet_summary(item))
        if not add_best(
            lambda item: diet_category(item) == "fruit_or_seed"
            and item.predicate == "EATS_CATEGORY"
            and ("seed" in norm_name(item.object_text + " " + item.evidence_quote) or "fallen fruit" in norm_name(item.evidence_quote))
        ):
            add_best(lambda item: diet_category(item) == "fruit_or_seed" and item.predicate == "EATS_CATEGORY")
        if selected_categories["fruit_or_seed"] == 0:
            add_best(lambda item: diet_category(item) == "fruit_or_seed")
        for category in ["fungi", "invertebrates", "vertebrates", "carrion"]:
            if len(selected) >= top_k:
                break
            add_best(lambda item, category=category: diet_category(item) == category)
    if strict_question:
        for category in ["fungi", "invertebrates", "vertebrates", "carrion"]:
            if len(selected) >= top_k:
                break
            add_best(lambda item, category=category: diet_category(item) == category)

    category_priority = [
        "general_diet_summary",
        "fruit_or_seed",
        "fungi",
        "invertebrates",
        "vertebrates",
        "carrion",
        "foraging_behavior",
        "ecological_role",
        "other_diet",
        "incidental_or_mineral",
    ]
    for category in category_priority:
        if len(selected) >= top_k:
            break
        add_best(lambda item, category=category: diet_category(item) == category)

    for item in ranked:
        if len(selected) >= top_k:
            break
        if can_add(item):
            selected.append(item)
            selected_fact_ids.add(item.fact_id)
            selected_categories[diet_category(item)] += 1
            chunk_counts[item.source_chunk_id] += 1
    return selected[:top_k]


def retrieve_demo_items(
    graph: DemoGraph,
    planner: dict[str, Any],
    top_k: int,
    question: str,
    max_evidence_per_chunk: int = 3,
) -> list[RetrievedItem]:
    target_taxon_id = clean(planner.get("target_taxon_id"))
    facts = list(graph.facts_by_taxon.get(target_taxon_id, []))
    preferred_domains = set(planner.get("preferred_domains") or [])
    preferred_predicates = set(planner.get("preferred_predicates") or [])
    preferred_chapters = set(planner.get("preferred_chapters") or [])
    query_terms = set(tokens(" ".join(planner.get("query_terms") or []) + " " + question))
    question_tokens = tokens(question)
    downrank_breeding_facts = bool(question_tokens & MORPHOLOGY_QUERY_TERMS) and not bool(question_tokens & BREEDING_QUERY_TERMS)

    filtered = [
        fact
        for fact in facts
        if (not preferred_domains or clean(fact.get("fact_domain")) in preferred_domains)
        and (not preferred_predicates or clean(fact.get("predicate")) in preferred_predicates)
    ]
    if not filtered and preferred_domains:
        filtered = [fact for fact in facts if clean(fact.get("fact_domain")) in preferred_domains]
    if not filtered:
        filtered = facts

    predicate_priority = {predicate: len(preferred_predicates) - index for index, predicate in enumerate(planner.get("preferred_predicates") or [])}
    rows: list[RetrievedItem] = []
    for fact in filtered:
        fact_id = clean(fact.get("fact_id"))
        evidence_ids = graph.links_by_fact.get(fact_id, [])
        evidences = [graph.evidences_by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in graph.evidences_by_id]
        if not evidences:
            evidences = [{}]
        chunks = [graph.chunks_by_id.get(clean(evidence.get("source_chunk_id")), {}) for evidence in evidences]
        overlap = len(query_terms & tokens(fact_text_for_scoring(fact, evidences, chunks)))
        support = float(fact.get("support_count") or 0)
        predicate = clean(fact.get("predicate"))
        domain = clean(fact.get("fact_domain"))

        for evidence in evidences:
            chunk_id = clean(evidence.get("source_chunk_id"))
            chunk = graph.chunks_by_id.get(chunk_id, {})
            chapter = clean(evidence.get("source_chapter") or chunk.get("source_chapter"))
            score = 0.0
            score += 10.0 if preferred_predicates and predicate in preferred_predicates else 0.0
            score += 5.0 if preferred_domains and domain in preferred_domains else 0.0
            score += 3.0 if preferred_chapters and chapter in preferred_chapters else 0.0
            score += float(predicate_priority.get(predicate, 0))
            score += overlap
            score += min(support, 5.0) * 0.2
            score += 0.5 if clean(evidence.get("evidence_quote")) else 0.0
            score += 0.25 if clean(chunk.get("text_preview")) else 0.0
            if downrank_breeding_facts:
                fact_terms = tokens(
                    " ".join(
                        [
                            predicate,
                            object_label(fact),
                            clean(evidence.get("evidence_quote")),
                            clean(chunk.get("text_preview")),
                        ]
                    )
                )
                if fact_terms & BREEDING_FACT_TERMS:
                    score -= 12.0
            rows.append(
                RetrievedItem(
                    fact_id=fact_id,
                    predicate=predicate,
                    fact_domain=domain,
                    object_text=object_label(fact),
                    source_chunk_id=chunk_id,
                    source_chapter=chapter,
                    evidence_id=clean(evidence.get("evidence_id")),
                    evidence_quote=clean(evidence.get("evidence_quote")),
                    chunk_text=clean(chunk.get("text_preview")),
                    score=score,
                )
            )

    dedup: dict[tuple[str, str], RetrievedItem] = {}
    for row in rows:
        key = (row.fact_id, row.evidence_id)
        if key not in dedup or row.score > dedup[key].score:
            dedup[key] = row
    ranked = sorted(dedup.values(), key=lambda item: (-item.score, item.predicate, item.object_text, item.fact_id))
    if max_evidence_per_chunk <= 0:
        return ranked[:top_k]
    if clean(planner.get("intent")) == "diet_foraging" or "EcologyAndDiet" in preferred_domains:
        return rerank_diet_foraging(ranked, top_k, question, max_evidence_per_chunk)

    selected: list[RetrievedItem] = []
    selected_keys: set[tuple[str, str, str]] = set()
    chunk_counts: Counter = Counter()

    def add_row(row: RetrievedItem) -> bool:
        key = (row.predicate, row.object_text, row.source_chapter)
        if chunk_counts[row.source_chunk_id] >= max_evidence_per_chunk:
            return False
        if key in selected_keys:
            return False
        selected.append(row)
        selected_keys.add(key)
        chunk_counts[row.source_chunk_id] += 1
        return True

    preferred_domain_order = [domain for domain in planner.get("preferred_domains", []) if domain]
    if len(preferred_domain_order) > 1:
        for domain in preferred_domain_order:
            for row in ranked:
                if row.fact_domain == domain and add_row(row):
                    break
            if len(selected) >= top_k:
                return selected

    for row in ranked:
        if row in selected:
            continue
        add_row(row)
        if len(selected) >= top_k:
            return selected

    for row in ranked:
        if row in selected:
            continue
        if chunk_counts[row.source_chunk_id] >= max_evidence_per_chunk:
            continue
        selected.append(row)
        chunk_counts[row.source_chunk_id] += 1
        if len(selected) >= top_k:
            return selected

    for row in ranked:
        if row not in selected:
            selected.append(row)
            if len(selected) >= top_k:
                break
    return selected


def build_messages(
    question: str,
    resolved_target: str,
    planner: dict[str, Any] | None,
    items: list[RetrievedItem],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    vanilla_user = question
    if clean(resolved_target):
        vanilla_user = "\n\n".join(["Resolved target:", resolved_target, "Question:", question])
    vanilla_messages = [
        {"role": "system", "content": "You are an expert assistant for bird ecology. Answer the question directly and concisely."},
        {"role": "user", "content": vanilla_user},
    ]
    evidence_blocks = []
    for index, item in enumerate(items, start=1):
        block = [
            f"[{index}] predicate={item.predicate}, fact_domain={item.fact_domain}, source_chunk_id={item.source_chunk_id}",
            f"Fact object: {item.object_text}" if item.object_text else "",
            f"Evidence: {item.evidence_quote}" if item.evidence_quote else "",
            f"Chunk preview: {item.chunk_text}" if item.chunk_text else "",
        ]
        evidence_blocks.append("\n".join(part for part in block if part))
    kg_user_parts = [
        "Question:",
        question,
        "Resolved target:",
        resolved_target or "unknown",
    ]
    if planner is not None:
        kg_user_parts.extend(["Planner result:", json.dumps(planner, ensure_ascii=False, indent=2)])
    kg_user_parts.extend(
        [
            "Retrieved evidence:",
            "\n\n".join(evidence_blocks) if evidence_blocks else "(no evidence retrieved)",
            (
                "Please provide a natural, evidence-grounded answer. Do not cite every evidence item in the main prose; "
                "the evidence trace will be shown separately below."
            ),
        ]
    )
    kg_messages = [
        {
            "role": "system",
            "content": (
                "You are an expert assistant for bird ecology. Answer naturally and concisely using the retrieved evidence. "
                "Synthesize the evidence into a coherent answer rather than listing each evidence item mechanically. "
                "Do not invent facts beyond the evidence. If you infer a conclusion from evidence, explicitly mark it as an inference. "
                "If evidence is insufficient, state the limitation."
            ),
        },
        {"role": "user", "content": "\n\n".join(kg_user_parts)},
    ]
    return vanilla_messages, kg_messages


def print_messages(title: str, messages: list[dict[str, str]]) -> None:
    print(f"[{title}]")
    for message in messages:
        print(f"{message['role'].title()}:")
        print(message["content"])
        print()


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str,
    api_key: str,
    api_base: str,
    max_tokens: int = 900,
) -> str:
    url = final_chat_completions_url(api_base)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if api_key:
            detail = detail.replace(api_key, "<redacted>")
        detail = re.sub(r"(api key\s*:\s*)[^\"\s,}]+", r"\1<redacted>", detail, flags=re.IGNORECASE)
        detail = re.sub(r"(Authorization\s*:\s*Bearer\s+)[^\"\s,}]+", r"\1<redacted>", detail, flags=re.IGNORECASE)
        raise RuntimeError(f"LLM request failed: HTTP {exc.code}: {detail[:500]}") from exc
    except Exception as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc
    return clean(response_payload["choices"][0]["message"]["content"])


def final_chat_completions_url(api_base: str) -> str:
    base = clean(api_base).rstrip("/")
    if not base:
        base = "https://api.deepseek.com"
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def resolve_api_config(args: argparse.Namespace) -> APIConfig:
    key_candidates = [
        ("args.api_key", clean(args.api_key)),
        ("DEEPSEEK_API_KEY", clean(os.environ.get("DEEPSEEK_API_KEY"))),
        ("OPENAI_API_KEY", clean(os.environ.get("OPENAI_API_KEY"))),
    ]
    key_source = "none"
    api_key = ""
    for source, value in key_candidates:
        if value:
            key_source = source
            api_key = value
            break

    api_base = (
        clean(args.api_base)
        or clean(os.environ.get("DEEPSEEK_BASE_URL"))
        or clean(os.environ.get("OPENAI_BASE_URL"))
        or "https://api.deepseek.com"
    )
    return APIConfig(
        api_key=api_key,
        api_base=api_base.rstrip("/"),
        key_source=key_source,
        final_url=final_chat_completions_url(api_base),
    )


def api_config(args: argparse.Namespace) -> tuple[str, str]:
    config = resolve_api_config(args)
    return config.api_key, config.api_base


def masked_key_parts(api_key: str) -> tuple[str, str]:
    if not api_key:
        return "", ""
    if len(api_key) <= 10:
        return api_key[:2], api_key[-2:]
    return api_key[:6], api_key[-4:] if len(api_key) >= 4 else api_key


def print_debug_api_config(args: argparse.Namespace) -> None:
    config = resolve_api_config(args)
    prefix, suffix = masked_key_parts(config.api_key)
    print("[API Config]")
    print(f"dotenv_available: {str(load_dotenv is not None).lower()}")
    print(f"env_file_loaded: {getattr(args, '_env_file_loaded', 'none')}")
    print(f"selected_key_source: {config.key_source}")
    print(f"selected_key_prefix: {prefix}")
    print(f"selected_key_suffix: {suffix}")
    print(f"selected_api_base: {config.api_base}")
    print(f"final_chat_completions_url: {config.final_url}")
    print(f"selected_model: {args.model}")
    print()


def ping_api(args: argparse.Namespace) -> int:
    config = resolve_api_config(args)
    if not config.api_key:
        print("[API Ping]")
        print("API ping failed: no API key selected")
        return 1
    try:
        chat_completion(
            [{"role": "user", "content": "ping"}],
            model=args.model,
            api_key=config.api_key,
            api_base=config.api_base,
            max_tokens=5,
        )
    except RuntimeError as exc:
        print("[API Ping]")
        print(str(exc))
        return 1
    print("[API Ping]")
    print("API ping ok")
    return 0


def print_retrieved(items: list[RetrievedItem]) -> None:
    print("[Retrieved Evidence / Chunks]")
    for index, item in enumerate(items, start=1):
        print(f"{index}. fact_id={item.fact_id}")
        print(f"   predicate={item.predicate}")
        print(f"   fact_domain={item.fact_domain}")
        print(f"   source_chunk_id={item.source_chunk_id}")
        print(f"   source_chapter={item.source_chapter}")
        print(f"   evidence_id={item.evidence_id}")
        print(f"   score={item.score:.2f}")
        if item.object_text:
            print(f"   object={item.object_text}")
        if item.evidence_quote:
            print(f"   evidence={item.evidence_quote[:500]}")
        if item.chunk_text:
            print(f"   chunk_preview={item.chunk_text[:700]}")


def run_demo_data_mode(args: argparse.Namespace) -> int:
    try:
        graph = load_demo_graph(Path(args.demo_data))
    except FileNotFoundError as exc:
        print("[Demo Data Error]")
        print(str(exc))
        return 2
    try:
        planner, taxon, note, planner_prompt = plan_demo_query(graph, args.question, args.target, args.planner, args)
    except RuntimeError:
        print("[Target Resolution Error]")
        print("Could not resolve a target taxon from the demo graph.")
        print("Please pass --target.")
        print(f"Demo taxa examples: {demo_taxa_examples(graph)}")
        return 2
    target_label = format_taxon(taxon)
    items = retrieve_demo_items(graph, planner, args.top_k, args.question, args.max_evidence_per_chunk)
    vanilla_messages, kg_messages = build_messages(args.question, target_label, planner, items)

    print("[Question]")
    print(args.question)
    print()
    print("[Planner Result]")
    print(json.dumps(planner, ensure_ascii=False, indent=2))
    print()
    print("[Resolved Target]")
    print(target_label)
    print()
    print("[Retrieval Note]")
    print(note)
    print()

    if args.no_api:
        print("--no-api does not generate answers. It only previews retrieval results and prompts.")
        print()
        print_messages("Planner Prompt", planner_prompt)
        print_messages("Vanilla Prompt", vanilla_messages)
        print_messages("Knowledge-Augmented Prompt", kg_messages)
        print_retrieved(items)
        return 0

    api_key, api_base = api_config(args)
    if not api_key:
        print("[API Error]")
        print("Missing API key. Set DEEPSEEK_API_KEY/OPENAI_API_KEY, pass --api-key, or use --no-api.")
        print()
        print_retrieved(items)
        return 1

    try:
        vanilla_answer = chat_completion(vanilla_messages, model=args.model, api_key=api_key, api_base=api_base)
        kg_answer = chat_completion(kg_messages, model=args.model, api_key=api_key, api_base=api_base)
    except RuntimeError as exc:
        print("[API Error]")
        print(str(exc))
        print()
        print_retrieved(items)
        return 1

    print("[Vanilla Answer]")
    print(vanilla_answer)
    print()
    print("[Knowledge-Augmented Answer]")
    print(kg_answer)
    print()
    print_retrieved(items)
    return 0


def run_local_or_sample_mode(args: argparse.Namespace) -> int:
    if args.knowledge_mode != "kg_v3":
        print(f"[Note] knowledge-mode={args.knowledge_mode} currently uses the deterministic kg_v3 local artifact retriever.")

    if args.sample_mode:
        target = args.target or "Casuarius casuarius"
        items = sample_items(target)[: args.top_k]
        note = "sample-mode"
    else:
        target, note, items = retrieve_kg_items(
            claims_dir=Path(args.claims_dir),
            facts_dir=Path(args.facts_dir),
            chunks_paths=args.chunks_path,
            question=args.question,
            target=args.target,
            top_k=args.top_k,
        )

    vanilla_messages, kg_messages = build_messages(args.question, target, None, items)
    print("[Question]")
    print(args.question)
    print()
    print("[Target]")
    print(target or args.target or "(not resolved)")
    print()
    print("[Retrieval Note]")
    print(note)
    print()

    if args.no_api:
        print("--no-api does not generate answers. It only previews retrieval results and prompts.")
        print()
        print_messages("Vanilla Prompt", vanilla_messages)
        print_messages("Knowledge-Augmented Prompt", kg_messages)
        print_retrieved(items)
        return 0

    api_key, api_base = api_config(args)
    if not api_key:
        print("[API Error]")
        print("Missing API key. Set DEEPSEEK_API_KEY/OPENAI_API_KEY, pass --api-key, or use --no-api / --sample-mode.")
        print()
        print_retrieved(items)
        return 1

    try:
        vanilla_answer = chat_completion(vanilla_messages, model=args.model, api_key=api_key, api_base=api_base)
        kg_answer = chat_completion(kg_messages, model=args.model, api_key=api_key, api_base=api_base)
    except RuntimeError as exc:
        print("[API Error]")
        print(str(exc))
        print()
        print_retrieved(items)
        return 1

    print("[Vanilla Answer]")
    print(vanilla_answer)
    print()
    print("[Knowledge-Augmented Answer]")
    print(kg_answer)
    print()
    print_retrieved(items)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a one-question vanilla vs. KG-augmented comparison.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--target", default="")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--knowledge-mode", default="kg_v3", choices=["kg_v3", "hybrid", "text_rag"])
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--max-evidence-per-chunk", type=int, default=3)
    parser.add_argument("--demo-data", default="demo_data/sample_100_taxa", help="Path to demo_data/sample_100_taxa for public demo graph mode.")
    parser.add_argument("--planner", default="deterministic", choices=["deterministic", "llm"])
    parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global_v2")
    parser.add_argument("--facts-dir", default="KG/intermediate/facts_final_global_v2")
    parser.add_argument("--chunks-path", action="append", default=[], help="Optional JSONL chunk store path. Can be passed multiple times.")
    parser.add_argument("--api-base", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--env-file", default="")
    parser.add_argument("--sample-mode", action="store_true")
    parser.add_argument("--no-api", action="store_true")
    parser.add_argument("--debug-api-config", action="store_true", help="Print redacted API configuration diagnostics.")
    parser.add_argument("--ping-api", action="store_true", help="Send a minimal chat/completions ping using the selected API configuration.")
    args = parser.parse_args()

    args._env_file_loaded = load_env(args.env_file)
    if args.debug_api_config:
        print_debug_api_config(args)
    ping_status = ping_api(args) if args.ping_api else 0
    if args.demo_data and not args.sample_mode:
        run_status = run_demo_data_mode(args)
    else:
        run_status = run_local_or_sample_mode(args)
    return run_status or ping_status


if __name__ == "__main__":
    raise SystemExit(main())
