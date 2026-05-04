"""Schema constraints and shared helpers for KG V2."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

from kg_v2.schema import node_types, relation_types

ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT_DIR / "outputs"
INTERMEDIATE_DIR = OUTPUTS_DIR / "intermediate"
JSONL_DIR = OUTPUTS_DIR / "jsonl"
NEO4J_CSV_DIR = OUTPUTS_DIR / "neo4j_csv"
LOGS_DIR = OUTPUTS_DIR / "logs"
VECTOR_INDEX_DIR = INTERMEDIATE_DIR / "vector_index"
CONTROLLED_DOCS_PATH = INTERMEDIATE_DIR / "controlled_docs.jsonl"
TRUTH_ARTIFACTS_DIR = INTERMEDIATE_DIR / "truth_artifacts"

NODE_FIELDS: dict[str, tuple[str, ...]] = {
    node_types.ORDER: ("name",),
    node_types.FAMILY: ("name", "order_name"),
    node_types.GENUS: ("name", "family_name", "order_name"),
    node_types.SPECIES: (
        "common_name",
        "species_name",
        "genus_name",
        "family_name",
        "order_name",
        "iucn_status",
    ),
    node_types.FAMILY_ASPECT: (
        "family_name",
        "aspect_type",
        "raw_chapter_name",
        "source_type",
        "direct_family_text",
        "derived_from_species",
    ),
    node_types.FAMILY_SUMMARY: (
        "family_name",
        "summary_type",
        "summary_text",
        "source_type",
    ),
    node_types.HABITAT: ("name", "normalized_name", "category_type"),
    node_types.GEOGRAPHY: ("name", "normalized_name", "category_type"),
    node_types.FOOD: ("name", "normalized_name", "category_type"),
    node_types.BEHAVIOR: ("name", "normalized_name", "category_type"),
    node_types.THREAT: ("name", "normalized_name", "category_type"),
    node_types.CONSERVATION_STATUS: ("name", "normalized_name", "category_type"),
    node_types.FACT: (
        "fact_id",
        "subject_type",
        "subject_name",
        "fact_type",
        "predicate",
        "object_type",
        "object_name",
        "value_type",
        "value_min",
        "value_max",
        "value_text",
        "unit",
        "qualifiers",
        "source_level",
        "source_chapter",
        "source_subchapter",
        "species",
        "family",
        "order_name",
        "confidence",
        "is_derived",
    ),
    node_types.EVIDENCE_CHUNK: (
        "chunk_id",
        "raw_text",
        "cleaned_text",
        "source_db",
        "source_file",
        "source_chapter",
        "source_subchapter",
        "source_chapter_raw",
        "species_name",
        "family_name",
        "order_name",
        "offset_start",
        "offset_end",
    ),
}

ALLOWED_RELATIONS = set(relation_types.ALL_RELATION_TYPES)


def ensure_output_dirs() -> None:
    for path in (
        OUTPUTS_DIR,
        INTERMEDIATE_DIR,
        JSONL_DIR,
        NEO4J_CSV_DIR,
        LOGS_DIR,
        VECTOR_INDEX_DIR,
        TRUTH_ARTIFACTS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def slugify(text: str) -> str:
    text = normalize_space(text).lower()
    text = re.sub(r"[^\w]+", "-", text, flags=re.UNICODE)
    return text.strip("-") or "unknown"


def stable_hash(*parts: object, length: int = 12) -> str:
    raw = "||".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


def make_node_id(label: str, *parts: object) -> str:
    readable = slugify(" ".join(str(part) for part in parts if part))
    return f"{label.lower()}:{readable}:{stable_hash(label, *parts)}"


def build_node(label: str, properties: dict, node_id: str | None = None) -> dict:
    if label not in NODE_FIELDS:
        raise ValueError(f"Unsupported node label: {label}")
    clean_props = {k: v for k, v in properties.items() if v is not None}
    if node_id is None:
        preferred = (
            clean_props.get("name")
            or clean_props.get("species_name")
            or clean_props.get("common_name")
            or clean_props.get("family_name")
            or clean_props.get("fact_id")
            or clean_props.get("chunk_id")
        )
        node_id = make_node_id(label, preferred or stable_hash(clean_props))
    return {"id": node_id, "label": label, "properties": clean_props}


def build_edge(source: str, target: str, relation_type: str, properties: dict | None = None) -> dict:
    if relation_type not in ALLOWED_RELATIONS:
        raise ValueError(f"Unsupported relation type: {relation_type}")
    return {
        "source": source,
        "target": target,
        "type": relation_type,
        "properties": {k: v for k, v in (properties or {}).items() if v is not None},
    }


def load_jsonl(path: str | Path) -> list[dict]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    rows: list[dict] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def merge_node_rows(rows: Iterable[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in rows:
        existing = merged.get(row["id"])
        if existing is None:
            merged[row["id"]] = row
        else:
            existing["properties"].update({k: v for k, v in row.get("properties", {}).items() if v not in ("", None)})
    return list(merged.values())


def merge_edge_rows(rows: Iterable[dict]) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (row["source"], row["target"], row["type"])
        existing = merged.get(key)
        if existing is None:
            merged[key] = row
        else:
            existing["properties"].update({k: v for k, v in row.get("properties", {}).items() if v not in ("", None)})
    return list(merged.values())


def schema_constraints_cypher() -> list[str]:
    return [
        "CREATE CONSTRAINT kg_v2_node_id IF NOT EXISTS FOR (n) REQUIRE n.id IS UNIQUE",
        "CREATE INDEX kg_v2_species_name IF NOT EXISTS FOR (n:Species) ON (n.species_name)",
        "CREATE INDEX kg_v2_family_name IF NOT EXISTS FOR (n:Family) ON (n.name)",
        "CREATE INDEX kg_v2_fact_type IF NOT EXISTS FOR (n:Fact) ON (n.fact_type)",
        "CREATE INDEX kg_v2_chunk_id IF NOT EXISTS FOR (n:EvidenceChunk) ON (n.chunk_id)",
    ]
