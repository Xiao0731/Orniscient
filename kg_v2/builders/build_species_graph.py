"""Build the species-centered fact graph."""

from __future__ import annotations

from kg_v2.schema import node_types, relation_types
from kg_v2.schema.ontology_v2 import JSONL_DIR, build_edge, build_node, load_jsonl, make_node_id, merge_edge_rows, merge_node_rows, write_jsonl

OBJECT_NODE_TYPE_MAP = {
    "Habitat": node_types.HABITAT,
    "Geography": node_types.GEOGRAPHY,
    "Food": node_types.FOOD,
    "Behavior": node_types.BEHAVIOR,
    "Threat": node_types.THREAT,
    "ConservationStatus": node_types.CONSERVATION_STATUS,
    "Species": node_types.SPECIES,
}


def _iter_claim_like_rows(claims_or_facts: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in claims_or_facts:
        if "claim_id" in row:
            normalized.append(
                {
                    "fact_id": row["claim_id"],
                    "subject_name": row.get("subject_name"),
                    "subject_type": row.get("subject_type", "Species"),
                    "fact_type": row.get("predicate"),
                    "predicate": row.get("predicate"),
                    "object_type": row.get("object_type"),
                    "object_name": row.get("object_name"),
                    "value_type": row.get("value_type"),
                    "value_min": row.get("value_min"),
                    "value_max": row.get("value_max"),
                    "value_text": row.get("value_text"),
                    "unit": row.get("unit"),
                    "qualifiers": row.get("qualifiers", {}),
                    "source_level": "species",
                    "source_chapter": row.get("source_chapter"),
                    "source_subchapter": row.get("source_subchapter"),
                    "family_name": row.get("family_name"),
                    "order_name": row.get("order_name"),
                    "confidence": row.get("confidence"),
                    "is_derived": False,
                    "supported_chunk_ids": row.get("supported_chunk_ids", []),
                }
            )
        else:
            normalized.append(
                {
                    "fact_id": row["fact_id"],
                    "subject_name": row.get("subject_name"),
                    "subject_type": row.get("subject_type", "Species"),
                    "fact_type": row.get("fact_type"),
                    "predicate": row.get("fact_type"),
                    "object_type": row.get("object_type"),
                    "object_name": row.get("object_name"),
                    "value_type": "entity",
                    "value_min": None,
                    "value_max": None,
                    "value_text": None,
                    "unit": None,
                    "qualifiers": {},
                    "source_level": row.get("source_level", "species"),
                    "source_chapter": None,
                    "source_subchapter": None,
                    "family_name": row.get("family_name"),
                    "order_name": row.get("order_name"),
                    "confidence": row.get("confidence"),
                    "is_derived": row.get("is_derived", False),
                    "supported_chunk_ids": row.get("supported_chunk_ids", []),
                }
            )
    return normalized


def build_species_graph(
    species_records_path,
    claims_or_facts_path,
    evidence_chunks_path,
    nodes_output_path=JSONL_DIR / "species_nodes.jsonl",
    edges_output_path=JSONL_DIR / "species_edges.jsonl",
) -> tuple[list[dict], list[dict]]:
    species_records = {row["species_name"]: row for row in load_jsonl(species_records_path)}
    claim_like_rows = _iter_claim_like_rows(load_jsonl(claims_or_facts_path))
    evidence_chunks = {row["chunk_id"]: row for row in load_jsonl(evidence_chunks_path)}

    nodes: list[dict] = []
    edges: list[dict] = []

    for species_name, record in species_records.items():
        species_id = make_node_id(node_types.SPECIES, species_name)
        nodes.append(
            build_node(
                node_types.SPECIES,
                {
                    "common_name": record.get("common_name"),
                    "species_name": species_name,
                    "genus_name": record.get("genus_name"),
                    "family_name": record.get("family_name"),
                    "order_name": record.get("order_name"),
                    "iucn_status": record.get("iucn_status"),
                },
                species_id,
            )
        )

    for fact in claim_like_rows:
        subject_name = fact.get("subject_name")
        if not subject_name:
            continue
        species_record = species_records.get(subject_name, {})
        species_id = make_node_id(node_types.SPECIES, subject_name)
        fact_id = make_node_id(node_types.FACT, fact["fact_id"])
        nodes.append(
            build_node(
                node_types.FACT,
                {
                    "fact_id": fact["fact_id"],
                    "subject_type": fact.get("subject_type", "Species"),
                    "subject_name": subject_name,
                    "fact_type": fact.get("fact_type"),
                    "predicate": fact.get("predicate"),
                    "object_type": fact.get("object_type"),
                    "object_name": fact.get("object_name"),
                    "value_type": fact.get("value_type"),
                    "value_min": fact.get("value_min"),
                    "value_max": fact.get("value_max"),
                    "value_text": fact.get("value_text"),
                    "unit": fact.get("unit"),
                    "qualifiers": fact.get("qualifiers", {}),
                    "source_level": fact.get("source_level", "species"),
                    "source_chapter": fact.get("source_chapter"),
                    "source_subchapter": fact.get("source_subchapter"),
                    "species": subject_name,
                    "family": fact.get("family_name") or species_record.get("family_name"),
                    "order_name": fact.get("order_name") or species_record.get("order_name"),
                    "confidence": fact.get("confidence"),
                    "is_derived": fact.get("is_derived", False),
                },
                fact_id,
            )
        )
        edges.append(build_edge(species_id, fact_id, relation_types.HAS_FACT))

        object_type = fact.get("object_type")
        object_name = fact.get("object_name")
        object_node_type = OBJECT_NODE_TYPE_MAP.get(object_type)
        if object_node_type and object_name and fact.get("value_type") != "numeric":
            object_id = make_node_id(object_node_type, object_name)
            object_props = {"name": object_name, "normalized_name": object_name, "category_type": object_type}
            if object_node_type == node_types.SPECIES:
                object_props = {
                    "common_name": None,
                    "species_name": object_name,
                    "genus_name": None,
                    "family_name": None,
                    "order_name": None,
                    "iucn_status": None,
                }
            nodes.append(build_node(object_node_type, object_props, object_id))
            edges.append(build_edge(fact_id, object_id, relation_types.OBJECT))

        for chunk_id in fact.get("supported_chunk_ids", []):
            chunk = evidence_chunks.get(chunk_id)
            if not chunk:
                continue
            evidence_id = make_node_id(node_types.EVIDENCE_CHUNK, chunk_id)
            nodes.append(
                build_node(
                    node_types.EVIDENCE_CHUNK,
                    {
                        "chunk_id": chunk_id,
                        "raw_text": chunk.get("raw_text", ""),
                        "cleaned_text": chunk.get("cleaned_text", ""),
                        "source_db": chunk.get("source_db"),
                        "source_file": chunk.get("source_file"),
                        "source_chapter": chunk.get("source_chapter"),
                        "source_subchapter": chunk.get("source_subchapter", "Unknown"),
                        "source_chapter_raw": chunk.get("source_chapter_raw"),
                        "species_name": chunk.get("species_name"),
                        "family_name": chunk.get("family_name"),
                        "order_name": chunk.get("order_name"),
                        "offset_start": chunk.get("offset_start"),
                        "offset_end": chunk.get("offset_end"),
                    },
                    evidence_id,
                )
            )
            edges.append(build_edge(fact_id, evidence_id, relation_types.SUPPORTED_BY))

    nodes = merge_node_rows(nodes)
    edges = merge_edge_rows(edges)
    write_jsonl(nodes_output_path, nodes)
    write_jsonl(edges_output_path, edges)
    return nodes, edges
