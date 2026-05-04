from __future__ import annotations
from kb_benchmark_queries import build_benchmark_bundle

"""
benchmark.py
============

A pragmatic benchmark-generation pipeline for the ornithology project.

Why this version exists
-----------------------
Your current LightRAG graph is useful as a *semantic neighbor index*, but its
Neo4j materialization does NOT preserve your intended relation ontology as
explicit Neo4j relationship types. In practice, nearly all edges are stored as
`DIRECTED`, while the real semantics live inside relationship properties such as
`description` and `keywords`.

Therefore this pipeline makes two deliberate changes:
1. It no longer depends on `rag.query(...)` for KG access.
2. It builds `kg_context` directly from Neo4j via Cypher.

This keeps the KG in the loop as a weak anchor, while letting BOW source text
remain the final authority for question generation and quote validation.

What this script is optimized for
---------------------------------
Species-level datasets only:
    QA-SC / QA-MC / QA-SA
    Bird-Taxonomy / Bird-Geo / Bird-Comp / Bird-Life / Bird-Con
    Bird-Eco / Bird-Reason / Bird-Plan / Bird-ID

Not emitted by the main loop here:
    Bird-Classify / List-Global
"""

import concurrent.futures
import dataclasses
import glob
import json
import math
import os
import random
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from openai import OpenAI
from neo4j import GraphDatabase

from prompt_complete import (
    get_bird_classify_prompt,
    get_bird_comp_prompt,
    get_bird_con_prompt,
    get_bird_eco_prompt,
    get_bird_geo_prompt,
    get_bird_id_prompt,
    get_bird_life_prompt,
    get_bird_plan_prompt,
    get_bird_reason_prompt,
    get_bird_taxonomy_prompt,
    
    get_quality_review_prompt,
    get_qa_mc_prompt,
    get_qa_sa_prompt,
    get_qa_sc_prompt,
)

from build_list_patched import get_list_global_prompt

# ---------------------------------------------------------------------
# 0. Environment and global configuration
# ---------------------------------------------------------------------

load_dotenv(override=True)

# BOW paths
DATA_DIR = os.getenv("BOW_DATA_DIR", "./data/BOW")
OUT_DIR = os.getenv("QUESTION_OUT_DIR", "./question")

# Generator backend
GEN_MODEL = os.getenv("GEN_MODEL", "deepseek-chat")
GEN_BASE_URL = os.getenv("GEN_BASE_URL", "https://api.deepseek.com")
GEN_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()

# Neo4j access: this pipeline talks to Neo4j directly for KG anchor recovery.
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "") or None

# Optional reranker used ONLY for source-section ranking.
SILICON_API_KEY = os.getenv("SILICON_API_KEY", "").strip()
SILICON_RERANK_URL = os.getenv("SILICON_RERANK_URL", "https://api.siliconflow.cn/v1/rerank")
SILICON_RERANK_MODEL = os.getenv("SILICON_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

# Runtime knobs
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
TOP_K_SECTIONS = int(os.getenv("TOP_K_SECTIONS", "3"))
MIN_CONTEXT_CHARS = int(os.getenv("MIN_CONTEXT_CHARS", "120"))
QUALITY_REVIEW_ENABLED = os.getenv("QUALITY_REVIEW_ENABLED", "1") == "1"
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# Hard acceptance thresholds.
# These are deliberately "evidence-first": difficulty is advisory, not fatal.
MIN_FORMAT_SCORE = float(os.getenv("MIN_FORMAT_SCORE", "0.90"))
MIN_GROUNDING_SCORE = float(os.getenv("MIN_GROUNDING_SCORE", "0.75"))
MIN_QUOTE_SCORE = float(os.getenv("MIN_QUOTE_SCORE", "0.72"))
MIN_LEAKAGE_SCORE = float(os.getenv("MIN_LEAKAGE_SCORE", "0.55"))

# ---------------------------------------------------------------------
# 1. Dataset metadata
# ---------------------------------------------------------------------

DATASET_TYPES: Dict[str, List[Optional[str]]] = {
    "QA-SC": [None],
    "QA-MC": [None],
    "QA-SA": [None],
    "Bird-Taxonomy": [
        "Taxonomic Trap",
        "Subspecies Check",
        "Monotypic Verification",
        "Sister/Similar Taxa",
        "Nomenclature & Etymology",
    ],
    "Bird-Geo": ["Geographic Range", "Habitat & Elevation", "Migration Pattern"],
    "Bird-Comp": ["Similar Species ID", "Subspecies Variation", "Sister Taxa"],
    "Bird-Life": [
        "Courtship & Mating",
        "Phenology",
        "Nest Ecology",
        "Development",
        "Parental Care",
        "Life Cycle Synthesis",
    ],
    "Bird-Con": ["Status & Trend", "Threat Analysis", "Historical & Extinction"],
    "Bird-Eco": ["Dietary Niche", "Foraging Strategy", "Ecological Role", "Impact Analysis"],
    "Bird-Reason": ["Prediction", "Attribution", "Correction", "Multi-hop", "Synthesis"],
    "Bird-Plan": ["Predator Control", "Habitat Rescue", "Population Intervention"],
    "Bird-ID": ["Morphological Diagnosis", "Behavioral Fingerprint", "Acoustic & Phenological ID", "Sex & Age Diagnosis"],
    "Bird-Classify": ["Feature-to-Family", "Taxon-to-Feature", "Taxonomic Hierarchy"],
    "List-Global": ["Conservation & Distribution", "Ecological Traits", "Life History & Nesting", "Extreme Values"],
}

DATASET_TARGETS: Dict[str, int] = {
    "QA-SC": 2400,
    "QA-MC": 1200,
    "QA-SA": 1200,
    "Bird-Geo": 400,
    "Bird-Taxonomy": 800,
    "Bird-Comp": 1000,
    "Bird-Life": 400,
    "Bird-Con": 200,
    "Bird-Eco": 200,
    "Bird-ID": 1000,
    "Bird-Reason": 200,
    "Bird-Plan": 100,
}

IUCN_WEIGHTS = {
    "CR": 10.0,
    "EN": 8.0,
    "VU": 5.0,
    "NT": 3.0,
    "LC": 1.0,
    "DD": 1.2,
    "NE": 1.0,
    "EW": 10.0,
    "EX": 3.0,
}

PROMPT_GETTERS = {
    "QA-SC": get_qa_sc_prompt,
    "QA-MC": get_qa_mc_prompt,
    "QA-SA": get_qa_sa_prompt,
    "Bird-Taxonomy": get_bird_taxonomy_prompt,
    "Bird-Geo": get_bird_geo_prompt,
    "Bird-Comp": get_bird_comp_prompt,
    "Bird-Life": get_bird_life_prompt,
    "Bird-Con": get_bird_con_prompt,
    "Bird-Eco": get_bird_eco_prompt,
    "Bird-Reason": get_bird_reason_prompt,
    "Bird-Plan": get_bird_plan_prompt,
    "Bird-ID": get_bird_id_prompt,
    "Bird-Classify": get_bird_classify_prompt,
    "List-Global": get_list_global_prompt,
}

DATASET_CHAPTER_PRIORITIES: Dict[str, List[str]] = {
    "QA-SC": [
        "Field Identification",
        "Plumages, Molts, and Structure",
        "Systematics",
        "Distribution",
        "Habitat",
        "Movements and Migration",
        "Diet and Foraging",
        "Sounds and Vocal Behavior",
        "Behavior",
        "Breeding",
        "Demography and Populations",
        "Conservation and Management",
        "Introduction",
    ],
    "QA-MC": [
        "Plumages, Molts, and Structure",
        "Systematics",
        "Distribution",
        "Habitat",
        "Movements and Migration",
        "Diet and Foraging",
        "Sounds and Vocal Behavior",
        "Behavior",
        "Breeding",
        "Conservation and Management",
        "Demography and Populations",
    ],
    "QA-SA": [
        "Plumages, Molts, and Structure",
        "Systematics",
        "Distribution",
        "Habitat",
        "Movements and Migration",
        "Diet and Foraging",
        "Sounds and Vocal Behavior",
        "Behavior",
        "Breeding",
        "Demography and Populations",
        "Conservation and Management",
    ],
    "Bird-Taxonomy": ["Systematics", "Subspecies", "Introduction"],
    "Bird-Geo": ["Distribution", "Habitat", "Movements and Migration", "Introduction"],
    "Bird-Comp": ["Field Identification", "Plumages, Molts, and Structure", "Systematics", "Subspecies"],
    "Bird-Life": ["Behavior", "Breeding", "Introduction"],
    "Bird-Con": ["Conservation and Management", "Demography and Populations", "Introduction"],
    "Bird-Eco": ["Diet and Foraging", "Habitat", "Behavior", "Introduction"],
    "Bird-Reason": [
        "Introduction",
        "Field Identification",
        "Plumages, Molts, and Structure",
        "Systematics",
        "Distribution",
        "Habitat",
        "Movements and Migration",
        "Diet and Foraging",
        "Sounds and Vocal Behavior",
        "Behavior",
        "Breeding",
        "Demography and Populations",
        "Conservation and Management",
    ],
    "Bird-Plan": ["Conservation and Management", "Breeding", "Habitat", "Demography and Populations"],
    "Bird-ID": ["Field Identification", "Plumages, Molts, and Structure", "Sounds and Vocal Behavior", "Behavior"],
}

# Dataset-specific words used to downselect useful graph descriptions from the
# current LightRAG-generated Neo4j graph.
KG_TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "Bird-Taxonomy": ["taxonomy", "taxonomic", "scientific name", "genus", "family", "order", "subspecies", "monotypic", "related", "sister"],
    "Bird-Con": ["conservation", "status", "threat", "decline", "population", "iucn", "extinct"],
    "Bird-Geo": ["distribution", "range", "realm", "region", "habitat", "migrat", "elevation"],
    "Bird-Eco": ["diet", "forag", "feeds", "prey", "ecological", "seed", "nectar", "insect"],
    "Bird-Life": ["breed", "courtship", "nest", "incubation", "fledg", "parental", "mating"],
    "Bird-Comp": ["similar", "related", "distinguish", "subspecies", "diagnostic", "plumage"],
    "Bird-Plan": ["threat", "conservation", "status", "habitat", "decline", "population"],
    "Bird-ID": ["diagnostic", "plumage", "bill", "leg", "song", "call", "vocal", "behavior"],
    "Bird-Reason": ["ecology", "behavior", "conservation", "distribution", "diet", "trait"],
    "QA-SC": ["taxonomy", "distribution", "habitat", "diet", "behavior", "conservation", "vocal"],
    "QA-MC": ["taxonomy", "distribution", "habitat", "diet", "behavior", "conservation", "vocal"],
    "QA-SA": ["taxonomy", "distribution", "habitat", "diet", "behavior", "conservation", "vocal"],
}

# ---------------------------------------------------------------------
# 2. Canonical chapter inventory and section parsing helpers
# ---------------------------------------------------------------------

CANONICAL_HEADINGS = [
    "Introduction",
    "Field Identification",
    "Plumages, Molts, and Structure",
    "Systematics",
    "Subspecies",
    "Distribution",
    "Habitat",
    "Movements and Migration",
    "Diet and Foraging",
    "Sounds and Vocal Behavior",
    "Behavior",
    "Breeding",
    "Demography and Populations",
    "Conservation and Management",
    "Relationships with People",
    "Relationship with Humans",
    "Priorities for Future Research",
    "About the Author(s)",
    "Acknowledgments",
    "Other",
]

HEADING_CANONICAL_MAP = {
    "Relationship with Humans": "Relationships with People",
}

HEADING_PATTERN = re.compile(
    r"(?im)^(Introduction|Field Identification|Plumages,\s*Molts,\s*and\s*Structure|Systematics|Subspecies|Distribution|Habitat|Movements\s+and\s+Migration|Diet\s+and\s+Foraging|Sounds\s+and\s+Vocal\s+Behavior|Behavior|Breeding|Demography\s+and\s+Populations|Conservation\s+and\s+Management|Relationships?\s+with\s+(?:People|Humans)|Priorities\s+for\s+Future\s+Research|About\s+the\s+Author\(s\)|Acknowledgments|Other)\s*$"
)

# ---------------------------------------------------------------------
# 3. Lightweight data structures
# ---------------------------------------------------------------------

@dataclasses.dataclass
class BirdRecord:
    common_name: str
    species: str
    genus: str
    family: str
    order: str
    level: str
    source_file: str
    raw_full_text: str
    masked_full_text: str
    raw_sections: Dict[str, str]
    masked_sections: Dict[str, str]


@dataclasses.dataclass
class GenerationTask:
    dataset: str
    question_id: str
    question_type: str
    bird: BirdRecord


# ---------------------------------------------------------------------
# 4. Shared preprocessing utilities
# ---------------------------------------------------------------------

def normalize_whitespace(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_visuals_and_citations(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = normalize_whitespace(text)
    text = re.sub(r"\(?[Ff]ig(?:ure)?\.?\s*\d+[A-Za-z]?\)?", "", text)
    text = re.sub(r"\(?[Pp]late\s*\d+[A-Za-z]?\)?", "", text)
    text = re.sub(r"\(?[Pp]hoto[^)\n]*\)?", "", text)
    text = re.sub(r"\([A-Z][A-Za-z\-]+(?: et al\.)?,\s*\d{4}[a-z]?\)", "", text)
    text = re.sub(r"\[[0-9,\s]+\]", "", text)
    text = re.sub(r"\n\s*\d+\s*\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def normalize_for_quote_matching(text: str) -> str:
    """More robust than strict substring matching on raw scraped BOW text."""
    text = clean_visuals_and_citations(text)
    text = text.replace("Close", " ")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\([^)]*\d{4}[^)]*\)", " ", text)  # remove citation-like parentheses
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def mask_entities(text: str, entities: Iterable[str]) -> str:
    masked = text
    cleaned_entities = sorted(
        {
            str(e).strip()
            for e in entities
            if e is not None and str(e).strip() and str(e).strip().lower() != "nan"
        },
        key=len,
        reverse=True,
    )
    for entity in cleaned_entities:
        masked = re.sub(re.escape(entity), "[the bird]", masked, flags=re.IGNORECASE)
    return masked


def canonicalize_heading(heading: str) -> str:
    heading = re.sub(r"\s+", " ", heading.strip())
    return HEADING_CANONICAL_MAP.get(heading, heading)


def infer_first_heading(text: str) -> Optional[str]:
    if not isinstance(text, str):
        return None
    for line in normalize_whitespace(text).split("\n"):
        line = line.strip()
        if line:
            if line in CANONICAL_HEADINGS:
                return canonicalize_heading(line)
            return None
    return None


def split_embedded_sections(text: str) -> Dict[str, str]:
    text = clean_visuals_and_citations(text)
    matches = list(HEADING_PATTERN.finditer(text))
    if not matches:
        guessed = infer_first_heading(text)
        return {guessed: text} if guessed else {}

    sections: Dict[str, str] = {}
    for idx, match in enumerate(matches):
        heading = canonicalize_heading(match.group(1))
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if len(chunk) < 20:
            continue
        sections[heading] = sections.get(heading, "") + ("\n\n" if heading in sections else "") + chunk
    return sections


def join_sections_in_priority_order(section_map: Dict[str, str]) -> str:
    ordered_chunks: List[str] = []
    used = set()
    for heading in CANONICAL_HEADINGS:
        canonical = canonicalize_heading(heading)
        if canonical in section_map and canonical not in used:
            ordered_chunks.append(section_map[canonical].strip())
            used.add(canonical)
    for heading, text in section_map.items():
        if heading not in used:
            ordered_chunks.append(text.strip())
            used.add(heading)
    return "\n\n".join(chunk for chunk in ordered_chunks if chunk)


def process_bow_file(file_path: str) -> List[BirdRecord]:
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    df["Common_name"] = df["Common_name"].ffill().astype(str).str.strip()
    df["Level"] = df["Level"].fillna("NE").astype(str).str.strip().replace("", "NE")
    df["Species"] = df["Species"].astype(str).apply(lambda x: x.split("\n")[0].strip())
    df["Genus"] = df["Genus"].astype(str).str.strip()
    df["Family"] = df["Family"].astype(str).str.strip()
    df["Order"] = df["Order"].astype(str).str.strip()

    grouped = df.groupby(["Common_name", "Species", "Genus", "Family", "Order", "Level"], dropna=False)
    records: List[BirdRecord] = []

    for identity, group in grouped:
        common_name, species, genus, family, order, level = identity
        raw_sections: Dict[str, List[str]] = defaultdict(list)

        for _, row in group.iterrows():
            raw_text = clean_visuals_and_citations(str(row["text"]))
            if not raw_text:
                continue
            embedded = split_embedded_sections(raw_text)
            if embedded:
                for heading, chunk in embedded.items():
                    raw_sections[heading].append(chunk)
                continue
            guessed = infer_first_heading(raw_text) or "Introduction"
            raw_sections[guessed].append(raw_text)

        merged_raw = {
            heading: "\n\n".join(chunks).strip()
            for heading, chunks in raw_sections.items()
            if any(chunk.strip() for chunk in chunks)
        }
        raw_full_text = join_sections_in_priority_order(merged_raw)

        entities = [common_name, species, genus, family, order]
        masked_sections = {heading: mask_entities(text, entities) for heading, text in merged_raw.items()}
        masked_full_text = mask_entities(raw_full_text, entities)

        records.append(
            BirdRecord(
                common_name=common_name,
                species=species,
                genus=genus,
                family=family,
                order=order,
                level=level or "NE",
                source_file=file_path,
                raw_full_text=raw_full_text,
                masked_full_text=masked_full_text,
                raw_sections=merged_raw,
                masked_sections=masked_sections,
            )
        )
    return records


# ---------------------------------------------------------------------
# 5. Sampling and ID helpers
# ---------------------------------------------------------------------

_round_robin_state: Dict[str, int] = {name: 0 for name in DATASET_TYPES}


def get_next_type(dataset_name: str) -> Optional[str]:
    types = DATASET_TYPES.get(dataset_name, [None])
    if not types or types == [None]:
        return None
    idx = _round_robin_state[dataset_name]
    value = types[idx]
    _round_robin_state[dataset_name] = (idx + 1) % len(types)
    return value


def make_question_id(dataset: str, counter: int) -> str:
    prefix = dataset.lower().replace("-", "_")
    return f"{prefix}_{counter:04d}"


def sample_birds_by_iucn(records: List[BirdRecord], sample_size: int) -> List[BirdRecord]:
    if not records or sample_size <= 0:
        return []
    if len(records) <= sample_size:
        shuffled = records[:]
        random.shuffle(shuffled)
        return shuffled

    weights = np.array([IUCN_WEIGHTS.get(str(r.level).upper().strip(), 1.0) for r in records], dtype=float)
    weights = weights / weights.sum()
    idxs = np.random.choice(len(records), size=sample_size, replace=False, p=weights)
    return [records[i] for i in idxs]


# ---------------------------------------------------------------------
# 6. Neo4j-based KG anchor extraction
# ---------------------------------------------------------------------


def make_neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def title_like(text: str) -> str:
    return " ".join(part[:1].upper() + part[1:].lower() if part else part for part in text.split())


def build_name_candidates(bird: BirdRecord) -> List[str]:
    candidates = []
    raw = [bird.common_name, bird.species, title_like(bird.common_name), title_like(bird.species)]
    for item in raw:
        item = (item or "").strip()
        if item and item not in candidates:
            candidates.append(item)
    return candidates


def resolve_graph_node(session, candidates: List[str]) -> Optional[Dict[str, Any]]:
    # Pass 1: case-insensitive exact entity_id match.
    exact_query = """
    MATCH (n:base)
    WHERE toLower(n.entity_id) = toLower($candidate)
    RETURN elementId(n) AS element_id, n.entity_id AS entity_id, labels(n) AS labels,
           coalesce(n.entity_type, '') AS entity_type, coalesce(n.description, '') AS description
    LIMIT 1
    """
    for cand in candidates:
        rec = session.run(exact_query, candidate=cand).single()
        if rec:
            return dict(rec)

    # Pass 2: fulltext fallback on indexed entity_id.
    ft_query = """
    CALL db.index.fulltext.queryNodes('entity_id_fulltext_idx_base', $candidate)
    YIELD node, score
    RETURN elementId(node) AS element_id, node.entity_id AS entity_id, labels(node) AS labels,
           coalesce(node.entity_type, '') AS entity_type, coalesce(node.description, '') AS description,
           score
    ORDER BY score DESC
    LIMIT 1
    """
    for cand in candidates:
        rec = session.run(ft_query, candidate=cand).single()
        if rec:
            return dict(rec)
    return None


def fetch_graph_neighbors(session, element_id: str, hop_limit: int = 2, max_rows: int = 80) -> List[Dict[str, Any]]:
    query = """
    MATCH (n:base)
    WHERE elementId(n) = $element_id
    MATCH p = (n)-[r1]-(m)
    OPTIONAL MATCH p2 = (m)-[r2]-(k)
    RETURN
        n.entity_id AS center,
        m.entity_id AS hop1_entity,
        labels(m) AS hop1_labels,
        coalesce(r1.keywords, '') AS hop1_keywords,
        coalesce(r1.description, '') AS hop1_description,
        CASE WHEN p2 IS NULL THEN '' ELSE k.entity_id END AS hop2_entity,
        CASE WHEN p2 IS NULL THEN [] ELSE labels(k) END AS hop2_labels,
        CASE WHEN p2 IS NULL THEN '' ELSE coalesce(r2.keywords, '') END AS hop2_keywords,
        CASE WHEN p2 IS NULL THEN '' ELSE coalesce(r2.description, '') END AS hop2_description
    LIMIT $max_rows
    """
    return [dict(r) for r in session.run(query, element_id=element_id, max_rows=max_rows)]


def score_graph_row(dataset: str, row: Dict[str, Any]) -> float:
    topic_words = KG_TOPIC_KEYWORDS.get(dataset, [])
    hay = " ".join(
        [
            row.get("hop1_keywords", ""),
            row.get("hop1_description", ""),
            row.get("hop2_keywords", ""),
            row.get("hop2_description", ""),
            row.get("hop1_entity", ""),
            row.get("hop2_entity", ""),
        ]
    ).lower()
    score = 0.0
    for word in topic_words:
        if word.lower() in hay:
            score += 1.0
    # Prefer rows that actually expose two-hop context.
    if row.get("hop2_entity"):
        score += 0.35
    return score


def compact_graph_rows(dataset: str, node_info: Dict[str, Any], rows: List[Dict[str, Any]], max_lines: int = 8) -> str:
    if not node_info:
        return ""

    lines = [
        f"Matched graph node: {node_info.get('entity_id', '')}",
        f"Node labels: {', '.join(node_info.get('labels', []))}",
    ]
    if node_info.get("description"):
        lines.append(f"Node description: {normalize_whitespace(node_info['description'])[:240]}")

    if not rows:
        return "\n".join(lines)

    ranked = sorted(rows, key=lambda r: score_graph_row(dataset, r), reverse=True)
    used = set()
    kept = []

    for row in ranked:
        for text in [row.get("hop1_description", ""), row.get("hop2_description", "")]:
            text = normalize_whitespace(text)
            if not text:
                continue
            key = text.lower()
            if key in used:
                continue
            used.add(key)
            kept.append(text)
            if len(kept) >= max_lines:
                break
        if len(kept) >= max_lines:
            break

    if kept:
        lines.append("Recovered graph anchor facts:")
        lines.extend(f"- {text}" for text in kept)

    return "\n".join(lines)


def get_kg_context_from_cypher(driver, bird: BirdRecord, dataset: str) -> str:
    candidates = build_name_candidates(bird)
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            node_info = resolve_graph_node(session, candidates)
            if not node_info:
                return "(No graph node matched this species by common/scientific name.)"
            rows = fetch_graph_neighbors(session, node_info["element_id"])
            return compact_graph_rows(dataset, node_info, rows)
    except Exception as exc:
        return f"(Graph lookup failed: {type(exc).__name__}: {exc})"


# ---------------------------------------------------------------------
# 7. Source-section retrieval and ranking
# ---------------------------------------------------------------------


def build_section_retrieval_query(dataset: str, question_type: str, bird: BirdRecord) -> str:
    return (
        f"Dataset={dataset}; QuestionType={question_type}; Bird={bird.common_name}; "
        f"Find the most relevant evidence section to support a benchmark question."
    )


def tokenize_for_overlap(text: str) -> List[str]:
    return re.findall(r"[A-Za-z][A-Za-z\-]+", text.lower())


def lexical_overlap_score(query: str, text: str) -> float:
    q = set(tokenize_for_overlap(query))
    t = set(tokenize_for_overlap(text))
    if not q or not t:
        return 0.0
    return len(q & t) / math.sqrt(len(q) * len(t))


def requests_rerank(query: str, documents: List[str]) -> List[float]:
    if not SILICON_API_KEY or not documents:
        return [0.0] * len(documents)
    payload = {
        "model": SILICON_RERANK_MODEL,
        "query": query,
        "texts": documents,
        "return_documents": False,
    }
    headers = {
        "Authorization": f"Bearer {SILICON_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(SILICON_RERANK_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        scores = [0.0] * len(documents)
        for item in data.get("results", []):
            idx = int(item.get("index", -1))
            if 0 <= idx < len(documents):
                scores[idx] = float(item.get("relevance_score", 0.0))
        return scores
    except Exception:
        return [0.0] * len(documents)


def rank_sections(query: str, section_items: List[Tuple[str, str]]) -> List[Tuple[str, str, float]]:
    if not section_items:
        return []
    prelim = [(heading, text, lexical_overlap_score(query, text)) for heading, text in section_items]
    prelim.sort(key=lambda x: x[2], reverse=True)
    shortlist = prelim[: min(8, len(prelim))]
    if not SILICON_API_KEY:
        return shortlist
    docs = [text for _, text, _ in shortlist]
    rerank_scores = requests_rerank(query, docs)
    reranked = []
    for (heading, text, base_score), rr in zip(shortlist, rerank_scores):
        reranked.append((heading, text, 0.35 * base_score + 0.65 * rr))
    reranked.sort(key=lambda x: x[2], reverse=True)
    return reranked


def select_source_context(dataset: str, question_type: str, bird: BirdRecord) -> Tuple[str, str]:
    preferred = DATASET_CHAPTER_PRIORITIES.get(dataset, [])
    candidate_items: List[Tuple[str, str, str]] = []

    for heading in preferred:
        if heading in bird.masked_sections:
            candidate_items.append((heading, bird.masked_sections[heading], bird.raw_sections.get(heading, "")))
    for heading, masked_text in bird.masked_sections.items():
        if heading not in preferred:
            candidate_items.append((heading, masked_text, bird.raw_sections.get(heading, "")))

    if not candidate_items:
        return bird.masked_full_text, bird.raw_full_text

    query = build_section_retrieval_query(dataset, question_type, bird)
    rank_input = [(heading, masked_text) for heading, masked_text, _ in candidate_items]
    ranked = rank_sections(query, rank_input)
    if not ranked:
        return bird.masked_full_text, bird.raw_full_text

    chosen = ranked[: min(TOP_K_SECTIONS, len(ranked))]
    masked_chunks, raw_chunks = [], []
    for heading, _, _ in chosen:
        if bird.masked_sections.get(heading):
            masked_chunks.append(bird.masked_sections[heading])
        if bird.raw_sections.get(heading):
            raw_chunks.append(bird.raw_sections[heading])

    masked_context = "\n\n".join(masked_chunks).strip()
    raw_context = "\n\n".join(raw_chunks).strip()
    if len(masked_context) < MIN_CONTEXT_CHARS:
        return bird.masked_full_text, bird.raw_full_text
    return masked_context, raw_context


# ---------------------------------------------------------------------
# 8. Type eligibility heuristics
# ---------------------------------------------------------------------


def text_supports_question_type(dataset: str, qtype: str, text: str) -> bool:
    lowered = text.lower()
    if dataset == "Bird-Con":
        if qtype == "Status & Trend":
            has_status = any(x in lowered for x in ["least concern", "near threatened", "vulnerable", "endangered", "critically endangered", "data deficient", "extinct"]) or "iucn" in lowered
            has_trend = any(x in lowered for x in ["declin", "increas", "stable", "trend"])
            return has_status and has_trend
        if qtype == "Threat Analysis":
            return any(x in lowered for x in ["threat", "habitat loss", "fragment", "predator", "invasive", "climate", "pollution", "hunting", "disturbance"])
        if qtype == "Historical & Extinction":
            return any(x in lowered for x in ["last seen", "last recorded", "extinct", "rediscovered", "histor", "disappeared", "collapse", "range contraction"])

    if dataset == "Bird-Taxonomy":
        if qtype == "Taxonomic Trap":
            return any(x in lowered for x in ["formerly", "previously", "split", "lumped", "considered", "placed in", "moved to", "treated as"])
        if qtype == "Subspecies Check":
            return "subspecies" in lowered or re.search(r"\bsubsp\b", lowered) is not None or re.search(r"\b[a-z]+\s+[a-z]+\s+[a-z]+\b", lowered) is not None
        if qtype == "Monotypic Verification":
            return "monotypic" in lowered or "subspecies" in lowered
        if qtype == "Sister/Similar Taxa":
            return any(x in lowered for x in ["sister", "related", "closely related", "similar species", "confused with", "conspecific"])
        if qtype == "Nomenclature & Etymology":
            return any(x in lowered for x in ["etymolog", "named after", "described by", "originally described", "honours", "year"])

    # For other datasets, keep the gate permissive for now.
    return True


def choose_supported_type(dataset: str, bird: BirdRecord) -> str:
    types = DATASET_TYPES.get(dataset, [None])
    if not types or types == [None]:
        return "General"

    start_idx = _round_robin_state[dataset]
    n = len(types)
    full_text = bird.masked_full_text

    for offset in range(n):
        idx = (start_idx + offset) % n
        candidate = types[idx]
        if candidate is None:
            _round_robin_state[dataset] = (idx + 1) % n
            return "General"
        if text_supports_question_type(dataset, candidate, full_text):
            _round_robin_state[dataset] = (idx + 1) % n
            return candidate

    # If nothing is supported, return the starting type anyway to avoid deadlock.
    candidate = types[start_idx] or "General"
    _round_robin_state[dataset] = (start_idx + 1) % n
    return candidate


# ---------------------------------------------------------------------
# 9. Generator / validator / judge helpers
# ---------------------------------------------------------------------


def make_generator_client() -> OpenAI:
    if not GEN_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is empty. Please set it in your environment.")
    return OpenAI(api_key=GEN_API_KEY, base_url=GEN_BASE_URL)


def safe_json_loads(text: str) -> Optional[dict]:
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
        return None


def call_generation_model(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2500,
) -> Optional[dict]:
    try:
        response = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return safe_json_loads(response.choices[0].message.content)
    except Exception:
        return None


def validate_exact_quote(exact_quote: str, masked_context: str) -> bool:
    if not exact_quote or not masked_context:
        return False
    lhs = normalize_for_quote_matching(exact_quote)
    rhs = normalize_for_quote_matching(masked_context)
    return bool(lhs) and lhs in rhs


def patch_special_datasets(item: dict, dataset: str, bird: BirdRecord) -> dict:
    if dataset == "Bird-ID":
        item["answer"] = f"{bird.common_name} ({bird.species})"
    return item


def review_generated_item(
    client: OpenAI,
    dataset: str,
    question_type: str,
    generated_item: dict,
    kg_context: str,
    masked_source_context: str,
) -> dict:
    if not QUALITY_REVIEW_ENABLED:
        return {"passed": True, "overall_score": 1.0, "needs_revision": False, "issues": []}

    judge_prompt = get_quality_review_prompt()
    judge_prompt = (
        judge_prompt
        .replace("{dataset}", dataset)
        .replace("{type}", question_type or "General")
        .replace("{kg_context}", kg_context or "(No KG anchor available.)")
        .replace("{source_text}", masked_source_context)
        .replace("{candidate_json}", json.dumps(generated_item, ensure_ascii=False, indent=2))
    )

    review = call_generation_model(
        client=client,
        system_prompt=judge_prompt,
        user_prompt="Review the candidate benchmark item and return JSON only.",
        temperature=0.0,
        max_tokens=1400,
    )

    if not review:
        return {
            "passed": False,
            "overall_score": 0.0,
            "needs_revision": True,
            "issues": ["Judge model failed to return valid JSON."],
            "dimension_scores": {},
        }
    return review


def judge_accepts(review: dict, quote_valid: bool) -> bool:
    if not quote_valid:
        return False

    dims = review.get("dimension_scores", {}) or {}
    fmt = float(dims.get("format_compliance", 0.0))
    grounding = float(dims.get("source_grounding", 0.0))
    quote = float(dims.get("quote_faithfulness", 0.0))
    leakage = float(dims.get("leakage_risk", 0.0))

    return (
        fmt >= MIN_FORMAT_SCORE
        and grounding >= MIN_GROUNDING_SCORE
        and quote >= MIN_QUOTE_SCORE
        and leakage >= MIN_LEAKAGE_SCORE
    )


# ---------------------------------------------------------------------
# 10. Per-item processing
# ---------------------------------------------------------------------


def process_single_task(task: GenerationTask, neo4j_driver, client: OpenAI) -> Optional[dict]:
    dataset = task.dataset
    qtype = task.question_type or "General"
    bird = task.bird

    print(f"[GEN] {task.question_id} | {bird.common_name} | {dataset} | {qtype}")

    # # 1) KG anchor from Neo4j directly. This is a weak anchor, not the final authority.
    # kg_context = get_kg_context_from_cypher(neo4j_driver, bird, dataset)

    # # 2) Source evidence selection from BOW sections.
    # masked_context, raw_context = select_source_context(dataset, qtype, bird)

    bundle = build_benchmark_bundle(neo4j_driver, bird.common_name, dataset)
    kg_context = bundle.get("kg_context", "")

    masked_context, raw_context = select_source_context(dataset, qtype, bird)

    preferred_evidence = bundle.get("preferred_evidence_text", "").strip()
    if preferred_evidence:
        masked_context = preferred_evidence + "\n\n" + masked_context

    # 3) Prompt assembly.
    system_prompt = PROMPT_GETTERS[dataset]()
    system_prompt = (
        system_prompt
        .replace("{type}", qtype)
        .replace("{kg_context}", kg_context)
        .replace("{source_text}", masked_context)
        .replace("{context}", masked_context)
    )

    generated = call_generation_model(
        client=client,
        system_prompt=system_prompt,
        user_prompt="Generate exactly ONE benchmark item following the required JSON schema.",
        temperature=0.7,
        max_tokens=2500,
    )
    if not generated:
        print(f"[FAIL] {task.question_id} | generator returned no valid JSON")
        return None

    generated = patch_special_datasets(generated, dataset, bird)

    provenance = generated.get("provenance", {}) if isinstance(generated, dict) else {}
    exact_quote = provenance.get("exact_quote", "") if isinstance(provenance, dict) else ""
    quote_valid = validate_exact_quote(exact_quote, masked_context)

    review = review_generated_item(
        client=client,
        dataset=dataset,
        question_type=qtype,
        generated_item=generated,
        kg_context=kg_context,
        masked_source_context=masked_context,
    )

    accepted = judge_accepts(review, quote_valid)
    difficulty_score = float((review.get("dimension_scores", {}) or {}).get("difficulty_quality", 0.0))

    item = {
        "question_id": task.question_id,
        "dataset": dataset,
        "question_type": qtype,
        "target_entity": bird.common_name,
        "scientific_name": bird.species,
        "iucn_level": bird.level,
        "source_file": bird.source_file,
        "kg_context": kg_context,
        "source_context_used": masked_context,
        "quote_validated": quote_valid,
        "quality_review": review,
        "difficulty_warning": difficulty_score < 0.60,
        "accepted": accepted,
        **generated,
    }

    status = "OK" if accepted else "REVIEW"
    print(f"[{status}] {task.question_id} | quote={quote_valid} | difficulty={difficulty_score:.2f}")
    return item


# ---------------------------------------------------------------------
# 11. Persistence
# ---------------------------------------------------------------------


def save_to_jsonl(dataset: str, item: dict, accepted: bool, out_dir: str = OUT_DIR) -> None:
    dataset_dir = os.path.join(out_dir, dataset)
    os.makedirs(dataset_dir, exist_ok=True)
    suffix = "accepted" if accepted else "rejected"
    path = os.path.join(dataset_dir, f"{dataset}_{suffix}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------
# 12. Main pipeline
# ---------------------------------------------------------------------


def build_task_queue(
    records: List[BirdRecord],
    datasets_to_generate: List[str],
    per_dataset_target: Dict[str, int],
    id_counters: Dict[str, int],
    seen_triplets: set,
) -> List[GenerationTask]:
    tasks: List[GenerationTask] = []

    for dataset in datasets_to_generate:
        if dataset in {"Bird-Classify", "List-Global"}:
            print(f"[SKIP] {dataset} is not emitted from the species-level loop in this script.")
            continue

        target_n = per_dataset_target.get(dataset, 0)
        if target_n <= 0:
            continue

        if dataset == "Bird-Plan":
            eligible = [r for r in records if r.level.upper() in {"CR", "EN", "VU"}]
        else:
            eligible = records

        sampled = sample_birds_by_iucn(eligible, target_n)
        print(f"  [{dataset}] target={target_n}, sampled={len(sampled)}")

        for bird in sampled:
            if len(bird.masked_full_text.strip()) < MIN_CONTEXT_CHARS:
                continue

            qtype = choose_supported_type(dataset, bird)
            dedup_key = (bird.common_name, dataset, qtype)
            if dedup_key in seen_triplets:
                continue
            seen_triplets.add(dedup_key)

            id_counters[dataset] += 1
            tasks.append(
                GenerationTask(
                    dataset=dataset,
                    question_id=make_question_id(dataset, id_counters[dataset]),
                    question_type=qtype,
                    bird=bird,
                )
            )
    return tasks


def discover_bow_files(data_dir: str) -> List[str]:
    files = [
        f for f in glob.glob(os.path.join(data_dir, "*.xlsx"))
        if os.path.basename(f).split("-")[0].isdigit()
    ]
    files.sort(key=lambda x: int(os.path.basename(x).split("-")[0]))
    return files


def main() -> None:
    client = make_generator_client()
    neo4j_driver = make_neo4j_driver()

    # Start with these if you want a conservative first run.
    datasets_to_generate = [
        "Bird-Con",
        "Bird-Taxonomy",
        # Then gradually expand:
        # "Bird-Geo",
        # "Bird-Life",
        # "Bird-Eco",
        # "QA-SC",
        # "QA-MC",
        # "QA-SA",
        # "Bird-Comp",
        # "Bird-Reason",
        # "Bird-Plan",
        # "Bird-ID",
    ]

    all_files = discover_bow_files(DATA_DIR)
    if not all_files:
        raise FileNotFoundError(f"No xlsx files found under {DATA_DIR}")

    print(f"Discovered {len(all_files)} BOW file(s).")
    per_dataset_target = {
        dataset: math.ceil(DATASET_TARGETS.get(dataset, 0) / len(all_files))
        for dataset in datasets_to_generate
    }

    id_counters = defaultdict(int)
    seen_triplets = set()

    try:
        for file_idx, file_path in enumerate(all_files, start=1):
            print("\n" + "=" * 80)
            print(f"File {file_idx}/{len(all_files)}: {os.path.basename(file_path)}")

            records = process_bow_file(file_path)
            print(f"Recovered {len(records)} species record(s) from this file.")

            tasks = build_task_queue(
                records=records,
                datasets_to_generate=datasets_to_generate,
                per_dataset_target=per_dataset_target,
                id_counters=id_counters,
                seen_triplets=seen_triplets,
            )
            print(f"Task queue size: {len(tasks)}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [executor.submit(process_single_task, task, neo4j_driver, client) for task in tasks]
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if not result:
                        continue
                    save_to_jsonl(
                        dataset=result["dataset"],
                        item=result,
                        accepted=bool(result.get("accepted", False)),
                    )
    finally:
        neo4j_driver.close()

    print("\nDone. Accepted and rejected items have been written to separate jsonl files.")


if __name__ == "__main__":
    main()
