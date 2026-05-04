"""Build direct family evidence graph and derived family summaries."""

from __future__ import annotations

from collections import defaultdict

from kg_v2.parsers.normalize_text import clean_text
from kg_v2.schema import node_types, relation_types
from kg_v2.schema.aspect_taxonomy import normalize_family_chapter
from kg_v2.schema.ontology_v2 import JSONL_DIR, build_edge, build_node, load_jsonl, make_node_id, merge_edge_rows, merge_node_rows, write_jsonl


def build_family_graph(
    family_records_path,
    family_chunks_path,
    species_records_path,
    species_facts_path,
    family_summaries_path,
    nodes_output_path=JSONL_DIR / "family_nodes.jsonl",
    edges_output_path=JSONL_DIR / "family_edges.jsonl",
) -> tuple[list[dict], list[dict]]:
    family_records = load_jsonl(family_records_path)
    family_chunks = load_jsonl(family_chunks_path)
    family_summaries = load_jsonl(family_summaries_path)

    nodes: list[dict] = []
    edges: list[dict] = []

    family_ids: dict[str, str] = {}
    aspect_texts: dict[tuple[str, str, str], list[str]] = defaultdict(list)

    for record in family_records:
        family_id = family_ids.setdefault(record["family_name"], make_node_id(node_types.FAMILY, record["family_name"], record.get("order_name")))
        nodes.append(build_node(node_types.FAMILY, {"name": record["family_name"], "order_name": record.get("order_name")}, family_id))

    for chunk in family_chunks:
        family_name = chunk.get("family_name")
        if not family_name:
            continue
        family_id = family_ids.setdefault(family_name, make_node_id(node_types.FAMILY, family_name, chunk.get("order_name")))
        aspect_type = normalize_family_chapter(chunk.get("source_chapter_raw", "")) or "Unknown"
        raw_chapter_name = chunk.get("source_chapter_raw", "Unknown")
        aspect_key = (family_name, aspect_type, raw_chapter_name)
        aspect_texts[aspect_key].append(chunk.get("raw_text", ""))

        evidence_id = make_node_id(node_types.EVIDENCE_CHUNK, chunk["chunk_id"])
        aspect_id = make_node_id(node_types.FAMILY_ASPECT, family_name, aspect_type, raw_chapter_name)

        nodes.extend(
            [
                build_node(node_types.FAMILY, {"name": family_name, "order_name": chunk.get("order_name")}, family_id),
                build_node(
                    node_types.EVIDENCE_CHUNK,
                    {
                        "chunk_id": chunk["chunk_id"],
                        "raw_text": chunk.get("raw_text", ""),
                        "cleaned_text": clean_text(chunk.get("raw_text", "")),
                        "source_db": chunk.get("source_db"),
                        "source_file": chunk.get("source_file"),
                        "source_chapter": aspect_type if aspect_type != "Unknown" else chunk.get("source_chapter", "Unknown"),
                        "source_subchapter": chunk.get("source_subchapter", "Unknown"),
                        "source_chapter_raw": raw_chapter_name,
                        "species_name": None,
                        "family_name": family_name,
                        "order_name": chunk.get("order_name"),
                        "offset_start": None,
                        "offset_end": None,
                    },
                    evidence_id,
                ),
            ]
        )
        edges.extend(
            [
                build_edge(family_id, aspect_id, relation_types.HAS_ASPECT),
                build_edge(aspect_id, evidence_id, relation_types.SUPPORTED_BY),
            ]
        )

    for (family_name, aspect_type, raw_chapter_name), texts in aspect_texts.items():
        aspect_id = make_node_id(node_types.FAMILY_ASPECT, family_name, aspect_type, raw_chapter_name)
        nodes.append(
            build_node(
                node_types.FAMILY_ASPECT,
                {
                    "family_name": family_name,
                    "aspect_type": aspect_type,
                    "raw_chapter_name": raw_chapter_name,
                    "source_type": "direct_family_evidence",
                    "direct_family_text": "\n\n".join(texts).strip(),
                    "derived_from_species": False,
                },
                aspect_id,
            )
        )

    for summary in family_summaries:
        family_name = summary.get("family_name")
        if not family_name:
            continue
        family_id = family_ids.setdefault(family_name, make_node_id(node_types.FAMILY, family_name))
        summary_id = make_node_id(node_types.FAMILY_SUMMARY, family_name, "derived_from_species")
        nodes.extend(
            [
                build_node(node_types.FAMILY, {"name": family_name, "order_name": None}, family_id),
                build_node(
                    node_types.FAMILY_SUMMARY,
                    {
                        "family_name": family_name,
                        "summary_type": summary.get("summary_type", "derived_from_species"),
                        "summary_text": summary.get("summary_text", ""),
                        "source_type": "derived_from_species",
                    },
                    summary_id,
                ),
            ]
        )
        edges.append(build_edge(family_id, summary_id, relation_types.HAS_DERIVED_SUMMARY))

    nodes = merge_node_rows(nodes)
    edges = merge_edge_rows(edges)
    write_jsonl(nodes_output_path, nodes)
    write_jsonl(edges_output_path, edges)
    return nodes, edges
