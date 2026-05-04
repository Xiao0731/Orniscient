"""Build canonical taxonomy backbone from AviList."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from kg_v2.Step1_taxonomy.common import stable_hash, write_jsonl
from kg_v2.Step1_taxonomy.parsers.normalize_taxonomy_names import extract_genus_from_scientific_name
from kg_v2.Step1_taxonomy.schema.taxonomy_schema import CanonicalTaxonEdge, CanonicalTaxonNode
from kg_v2.Step1_taxonomy.schema.taxonomy_types import AVILIST, FAMILY, GENUS, ORDER, SPECIES, SUBSPECIES


def _make_taxon_id(release: str, rank: str, scientific_name: str) -> str:
    return stable_hash(AVILIST, release, rank, scientific_name, prefix=f"taxon_{rank}_")


def build_taxonomy_backbone(
    avilist_rows: list[dict],
    release: str,
    nodes_output_path: str | Path,
    edges_output_path: str | Path,
) -> tuple[list[dict], list[dict]]:
    order_rows = [row for row in avilist_rows if row["rank"] == ORDER]
    family_rows = [row for row in avilist_rows if row["rank"] == FAMILY]
    genus_rows = [row for row in avilist_rows if row["rank"] == GENUS]
    species_rows = [row for row in avilist_rows if row["rank"] == SPECIES]
    subspecies_rows = [row for row in avilist_rows if row["rank"] == SUBSPECIES]

    nodes: dict[str, dict] = {}
    edges: dict[tuple[str, str, str], dict] = {}

    def add_node(node: CanonicalTaxonNode) -> None:
        nodes[node.taxon_id] = node.to_dict()

    def add_edge(edge: CanonicalTaxonEdge) -> None:
        edges[(edge.src_id, edge.dst_id, edge.relation_type)] = edge.to_dict()

    order_ids: dict[str, str] = {}
    family_ids: dict[str, str] = {}
    genus_ids: dict[str, str] = {}
    species_ids: dict[str, str] = {}

    for row in order_rows:
        scientific_name = row["scientific_name"]
        taxon_id = _make_taxon_id(release, ORDER, scientific_name)
        order_ids[scientific_name] = taxon_id
        add_node(
            CanonicalTaxonNode(
                taxon_id=taxon_id,
                rank=ORDER,
                scientific_name=scientific_name,
                english_name_primary=row.get("english_name_primary", ""),
                order_name=scientific_name,
                family_name="",
                genus_name="",
                parent_taxon_id="",
                canonical_source=AVILIST,
                canonical_release=release,
                avibase_id=row.get("avibase_id", ""),
                cornell_species_code=row.get("cornell_species_code", ""),
                bow_url=row.get("bow_url", ""),
                iucn_status=row.get("iucn_status", ""),
                taxonomy_status="active",
            )
        )

    for row in family_rows:
        scientific_name = row["scientific_name"]
        order_name = row.get("order_name", "")
        taxon_id = _make_taxon_id(release, FAMILY, scientific_name)
        family_ids[scientific_name] = taxon_id
        parent_id = order_ids.get(order_name, "")
        add_node(
            CanonicalTaxonNode(
                taxon_id=taxon_id,
                rank=FAMILY,
                scientific_name=scientific_name,
                english_name_primary=row.get("family_english_name", ""),
                order_name=order_name,
                family_name=scientific_name,
                genus_name="",
                parent_taxon_id=parent_id,
                canonical_source=AVILIST,
                canonical_release=release,
                avibase_id=row.get("avibase_id", ""),
                cornell_species_code=row.get("cornell_species_code", ""),
                bow_url=row.get("bow_url", ""),
                iucn_status=row.get("iucn_status", ""),
                taxonomy_status="active",
            )
        )
        if parent_id:
            add_edge(CanonicalTaxonEdge(src_id=parent_id, dst_id=taxon_id, relation_type="CONTAINS_FAMILY"))

    for row in genus_rows:
        scientific_name = row["scientific_name"]
        family_name = row.get("family_name", "")
        order_name = row.get("order_name", "")
        taxon_id = _make_taxon_id(release, GENUS, scientific_name)
        genus_ids[scientific_name] = taxon_id
        parent_id = family_ids.get(family_name, "")
        add_node(
            CanonicalTaxonNode(
                taxon_id=taxon_id,
                rank=GENUS,
                scientific_name=scientific_name,
                english_name_primary=row.get("english_name_primary", ""),
                order_name=order_name,
                family_name=family_name,
                genus_name=scientific_name,
                parent_taxon_id=parent_id,
                canonical_source=AVILIST,
                canonical_release=release,
                avibase_id=row.get("avibase_id", ""),
                cornell_species_code=row.get("cornell_species_code", ""),
                bow_url=row.get("bow_url", ""),
                iucn_status=row.get("iucn_status", ""),
                taxonomy_status="active",
            )
        )
        if parent_id:
            add_edge(CanonicalTaxonEdge(src_id=parent_id, dst_id=taxon_id, relation_type="CONTAINS_GENUS"))

    for row in species_rows:
        scientific_name = row["scientific_name"]
        genus_name = row.get("genus_name") or extract_genus_from_scientific_name(scientific_name)
        family_name = row.get("family_name", "")
        order_name = row.get("order_name", "")
        taxon_id = _make_taxon_id(release, SPECIES, scientific_name)
        species_ids[scientific_name] = taxon_id
        parent_id = genus_ids.get(genus_name, "")
        add_node(
            CanonicalTaxonNode(
                taxon_id=taxon_id,
                rank=SPECIES,
                scientific_name=scientific_name,
                english_name_primary=row.get("english_name_primary", ""),
                order_name=order_name,
                family_name=family_name,
                genus_name=genus_name,
                parent_taxon_id=parent_id,
                canonical_source=AVILIST,
                canonical_release=release,
                avibase_id=row.get("avibase_id", ""),
                cornell_species_code=row.get("cornell_species_code", ""),
                bow_url=row.get("bow_url", ""),
                iucn_status=row.get("iucn_status", ""),
                taxonomy_status="active",
            )
        )
        if parent_id:
            add_edge(CanonicalTaxonEdge(src_id=parent_id, dst_id=taxon_id, relation_type="CONTAINS_SPECIES"))

    for row in subspecies_rows:
        scientific_name = row["scientific_name"]
        parts = scientific_name.split()
        parent_species_name = " ".join(parts[:2]) if len(parts) >= 2 else ""
        genus_name = parts[0] if parts else ""
        family_name = row.get("family_name", "")
        order_name = row.get("order_name", "")
        taxon_id = _make_taxon_id(release, SUBSPECIES, scientific_name)
        parent_id = species_ids.get(parent_species_name, "")
        add_node(
            CanonicalTaxonNode(
                taxon_id=taxon_id,
                rank=SUBSPECIES,
                scientific_name=scientific_name,
                english_name_primary=row.get("english_name_primary", ""),
                order_name=order_name,
                family_name=family_name,
                genus_name=genus_name,
                parent_taxon_id=parent_id,
                canonical_source=AVILIST,
                canonical_release=release,
                avibase_id=row.get("avibase_id", ""),
                cornell_species_code=row.get("cornell_species_code", ""),
                bow_url=row.get("bow_url", ""),
                iucn_status=row.get("iucn_status", ""),
                taxonomy_status="active",
            )
        )
        if parent_id:
            add_edge(CanonicalTaxonEdge(src_id=parent_id, dst_id=taxon_id, relation_type="CONTAINS_SUBSPECIES"))

    node_rows = list(nodes.values())
    edge_rows = list(edges.values())
    write_jsonl(nodes_output_path, node_rows)
    write_jsonl(edges_output_path, edge_rows)
    return node_rows, edge_rows
