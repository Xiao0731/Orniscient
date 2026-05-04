"""Build taxonomy tree nodes and edges."""

from __future__ import annotations

from kg_v2.schema import node_types, relation_types
from kg_v2.schema.ontology_v2 import JSONL_DIR, build_edge, build_node, load_jsonl, make_node_id, merge_edge_rows, merge_node_rows, write_jsonl


def build_taxonomy_tree(
    species_records_path,
    family_records_path,
    nodes_output_path=JSONL_DIR / "taxonomy_nodes.jsonl",
    edges_output_path=JSONL_DIR / "taxonomy_edges.jsonl",
) -> tuple[list[dict], list[dict]]:
    species_records = load_jsonl(species_records_path)
    family_records = load_jsonl(family_records_path)

    nodes: list[dict] = []
    edges: list[dict] = []

    order_ids: dict[str, str] = {}
    family_ids: dict[tuple[str, str], str] = {}
    genus_ids: dict[tuple[str, str, str], str] = {}
    species_ids: dict[str, str] = {}

    for family_record in family_records:
        order_name = family_record.get("order_name")
        family_name = family_record.get("family_name")
        if order_name:
            order_id = order_ids.setdefault(order_name, make_node_id(node_types.ORDER, order_name))
            nodes.append(build_node(node_types.ORDER, {"name": order_name}, order_id))
        if family_name:
            family_id = family_ids.setdefault((family_name, order_name), make_node_id(node_types.FAMILY, family_name, order_name))
            nodes.append(build_node(node_types.FAMILY, {"name": family_name, "order_name": order_name}, family_id))
            if order_name:
                edges.append(build_edge(order_ids[order_name], family_id, relation_types.CONTAINS_FAMILY))

    for record in species_records:
        order_name = record.get("order_name")
        family_name = record.get("family_name")
        genus_name = record.get("genus_name")
        species_name = record.get("species_name")
        common_name = record.get("common_name")
        if not species_name:
            continue

        order_id = order_ids.setdefault(order_name, make_node_id(node_types.ORDER, order_name))
        family_id = family_ids.setdefault((family_name, order_name), make_node_id(node_types.FAMILY, family_name, order_name))
        genus_key = (genus_name, family_name, order_name)
        genus_id = genus_ids.setdefault(genus_key, make_node_id(node_types.GENUS, genus_name, family_name, order_name))
        species_id = species_ids.setdefault(species_name, make_node_id(node_types.SPECIES, species_name))

        nodes.extend(
            [
                build_node(node_types.ORDER, {"name": order_name}, order_id),
                build_node(node_types.FAMILY, {"name": family_name, "order_name": order_name}, family_id),
                build_node(
                    node_types.GENUS,
                    {"name": genus_name, "family_name": family_name, "order_name": order_name},
                    genus_id,
                ),
                build_node(
                    node_types.SPECIES,
                    {
                        "common_name": common_name,
                        "species_name": species_name,
                        "genus_name": genus_name,
                        "family_name": family_name,
                        "order_name": order_name,
                        "iucn_status": record.get("iucn_status"),
                    },
                    species_id,
                ),
            ]
        )
        edges.extend(
            [
                build_edge(order_id, family_id, relation_types.CONTAINS_FAMILY),
                build_edge(family_id, genus_id, relation_types.CONTAINS_GENUS),
                build_edge(genus_id, species_id, relation_types.CONTAINS_SPECIES),
            ]
        )

    nodes = merge_node_rows(nodes)
    edges = merge_edge_rows(edges)
    write_jsonl(nodes_output_path, nodes)
    write_jsonl(edges_output_path, edges)
    return nodes, edges
