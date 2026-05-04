"""Merge taxonomy, family, and species graph layers."""

from __future__ import annotations

from kg_v2.schema.ontology_v2 import JSONL_DIR, load_jsonl, merge_edge_rows, merge_node_rows, write_jsonl


def build_fact_graph(
    taxonomy_nodes_path=JSONL_DIR / "taxonomy_nodes.jsonl",
    taxonomy_edges_path=JSONL_DIR / "taxonomy_edges.jsonl",
    family_nodes_path=JSONL_DIR / "family_nodes.jsonl",
    family_edges_path=JSONL_DIR / "family_edges.jsonl",
    species_nodes_path=JSONL_DIR / "species_nodes.jsonl",
    species_edges_path=JSONL_DIR / "species_edges.jsonl",
    all_nodes_output_path=JSONL_DIR / "all_nodes.jsonl",
    all_edges_output_path=JSONL_DIR / "all_edges.jsonl",
) -> tuple[list[dict], list[dict]]:
    nodes = merge_node_rows(
        load_jsonl(taxonomy_nodes_path)
        + load_jsonl(family_nodes_path)
        + load_jsonl(species_nodes_path)
    )
    edges = merge_edge_rows(
        load_jsonl(taxonomy_edges_path)
        + load_jsonl(family_edges_path)
        + load_jsonl(species_edges_path)
    )
    write_jsonl(all_nodes_output_path, nodes)
    write_jsonl(all_edges_output_path, edges)
    return nodes, edges
