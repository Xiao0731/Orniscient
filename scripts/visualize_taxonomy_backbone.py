from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_AVILIST_XLSX = ROOT_DIR / "data" / "AviList-v2025-11Jun-extended.xlsx"
DEFAULT_CLEMENTS_XLSX = ROOT_DIR / "data" / "Clements_v2025-October-2025.xlsx"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "evaluation" / "figures" / "taxonomy"
DEFAULT_ARTIFACT_ROOT = ROOT_DIR / "kg_v2" / "outputs"
TREE_RANKS = ("order", "family", "genus", "species")
RANK_PRIORITY = {"order": 0, "family": 1, "genus": 2, "species": 3, "subspecies": 4}

TREE_COLORS = {
    "order": {"fill": "#0B3954", "font": "#FFFFFF"},
    "family": {"fill": "#1F7A8C", "font": "#FFFFFF"},
    "genus": {"fill": "#B8E1F2", "font": "#0F172A"},
    "species": {"fill": "#FFFFFF", "font": "#0F172A"},
}
EXTERNAL_NODE_STYLE = {"fill": "#F8F6F2", "font": "#0F172A", "border": "#7C8B9C"}
RELATION_STYLES = {
    "exact": {"color": "#2E8B57", "style": "solid", "label": "exact match"},
    "alias": {"color": "#1D70B8", "style": "dashed", "label": "alias / synonym"},
    "conflict": {"color": "#E68A00", "style": "dashed", "label": "conflict / unresolved"},
}


class TaxonomyVisualizationError(RuntimeError):
    """Raised when the visualization inputs or runtime are invalid."""


@dataclass(frozen=True)
class TaxonNode:
    taxon_id: str
    rank: str
    scientific_name: str
    english_name_primary: str
    order_name: str
    family_name: str
    genus_name: str
    parent_taxon_id: str = ""
    canonical_source: str = "AviList"
    canonical_release: str = ""
    avibase_id: str = ""
    cornell_species_code: str = ""


@dataclass(frozen=True)
class CrosswalkRelation:
    relation_id: str
    relation_kind: str
    canonical_taxon_id: str
    external_node_id: str
    external_label: str
    external_rank: str
    external_source: str
    edge_label: str
    detail: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a compact AviList taxonomy backbone figure and a Clements crosswalk alignment figure."
    )
    parser.add_argument("--avilist-xlsx", type=Path, default=DEFAULT_AVILIST_XLSX)
    parser.add_argument("--clements-xlsx", type=Path, default=DEFAULT_CLEMENTS_XLSX)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--root-order", type=str, default="Accipitriformes")
    parser.add_argument("--max-families", type=int, default=6)
    parser.add_argument("--max-genera-per-family", type=int, default=4)
    parser.add_argument("--max-species-per-genus", type=int, default=4)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    return parser.parse_args()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(value)).casefold()


def stable_id(prefix: str, *parts: Any) -> str:
    payload = "||".join(normalize_text(part) for part in parts)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return slug or "taxonomy"


def require_graphviz_package():
    try:
        import graphviz  # type: ignore
    except ModuleNotFoundError as exc:
        raise TaxonomyVisualizationError(
            "Missing Python package 'graphviz'. Install it first, for example with "
            "`pip install graphviz`, then rerun this script."
        ) from exc
    return graphviz


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise TaxonomyVisualizationError(f"Missing input file: {path}")
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path).to_dict(orient="records")
    raise TaxonomyVisualizationError(f"Unsupported file format for artifact reuse: {path}")


def find_artifact(artifact_root: Path, basenames: list[str]) -> Path | None:
    exts = (".jsonl", ".csv")
    for basename in basenames:
        for ext in exts:
            direct = artifact_root / f"{basename}{ext}"
            if direct.exists():
                return direct
    for basename in basenames:
        for ext in exts:
            matches = sorted(artifact_root.rglob(f"{basename}{ext}"))
            if matches:
                return matches[0]
    return None


def choose_species_label(node: TaxonNode) -> str:
    if node.rank == "species" and node.english_name_primary:
        return f"{node.scientific_name}\\n{node.english_name_primary}"
    return node.scientific_name


def add_ordered_child(children: dict[str, list[str]], parent_id: str, child_id: str) -> None:
    bucket = children[parent_id]
    if child_id not in bucket:
        bucket.append(child_id)


def read_excel_table(path: Path) -> pd.DataFrame:
    try:
        workbook = pd.ExcelFile(path)
    except ImportError as exc:
        raise TaxonomyVisualizationError(
            "Reading .xlsx files requires an Excel engine such as 'openpyxl'. Install it and rerun."
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive path
        raise TaxonomyVisualizationError(f"Failed to open Excel workbook: {path}") from exc
    return workbook.parse(workbook.sheet_names[0])


def load_backbone_from_artifacts(artifact_root: Path) -> tuple[dict[str, TaxonNode], dict[str, list[str]], dict[str, Any]] | None:
    node_path = find_artifact(artifact_root, ["canonical_taxon_nodes"])
    edge_path = find_artifact(artifact_root, ["canonical_taxon_edges"])
    if not node_path or not edge_path:
        return None

    nodes: dict[str, TaxonNode] = {}
    for row in load_records(node_path):
        rank = normalize_text(row.get("rank")).lower()
        if rank not in RANK_PRIORITY:
            continue
        node = TaxonNode(
            taxon_id=normalize_text(row.get("taxon_id")) or stable_id("taxon", rank, row.get("scientific_name")),
            rank=rank,
            scientific_name=normalize_text(row.get("scientific_name")),
            english_name_primary=normalize_text(row.get("english_name_primary")),
            order_name=normalize_text(row.get("order_name")),
            family_name=normalize_text(row.get("family_name")),
            genus_name=normalize_text(row.get("genus_name")),
            parent_taxon_id=normalize_text(row.get("parent_taxon_id")),
            canonical_source=normalize_text(row.get("canonical_source")) or "AviList",
            canonical_release=normalize_text(row.get("canonical_release")),
            avibase_id=normalize_text(row.get("avibase_id")),
            cornell_species_code=normalize_text(row.get("cornell_species_code")),
        )
        nodes[node.taxon_id] = node

    children: dict[str, list[str]] = defaultdict(list)
    for row in load_records(edge_path):
        src_id = normalize_text(row.get("src_id"))
        dst_id = normalize_text(row.get("dst_id"))
        if src_id in nodes and dst_id in nodes:
            add_ordered_child(children, src_id, dst_id)

    return nodes, children, {
        "backbone_source": "artifact",
        "backbone_nodes_path": str(node_path),
        "backbone_edges_path": str(edge_path),
    }


def load_backbone_from_avilist_xlsx(path: Path) -> tuple[dict[str, TaxonNode], dict[str, list[str]], dict[str, Any]]:
    df = read_excel_table(path)
    nodes: dict[str, TaxonNode] = {}
    children: dict[str, list[str]] = defaultdict(list)
    genus_lookup: dict[tuple[str, str, str], str] = {}
    family_lookup: dict[tuple[str, str], str] = {}
    order_lookup: dict[str, str] = {}

    for row in df.to_dict(orient="records"):
        rank = normalize_text(row.get("Taxon_rank")).lower()
        if rank not in RANK_PRIORITY:
            continue

        scientific_name = normalize_text(row.get("Scientific_name"))
        order_name = normalize_text(row.get("Order")) or scientific_name
        family_name = normalize_text(row.get("Family"))
        english_name_primary = (
            normalize_text(row.get("English_name_AviList"))
            or normalize_text(row.get("English_name_Clements_v2024"))
            or normalize_text(row.get("English_name_BirdLife_v9"))
            or normalize_text(row.get("Family_English_name"))
        )
        avibase_id = normalize_text(row.get("AvibaseID"))
        cornell_species_code = normalize_text(row.get("Species_code_Cornell_Lab"))

        order_id = order_lookup.get(order_name)
        if not order_id:
            order_id = stable_id("taxon_order", order_name)
            order_lookup[order_name] = order_id
            nodes[order_id] = TaxonNode(
                taxon_id=order_id,
                rank="order",
                scientific_name=order_name,
                english_name_primary="",
                order_name=order_name,
                family_name="",
                genus_name="",
                canonical_release="xlsx-fallback",
                avibase_id="",
                cornell_species_code="",
            )

        if rank == "order":
            continue

        if rank == "family":
            family_name = family_name or scientific_name
            family_key = (order_name, family_name)
            family_id = family_lookup.get(family_key)
            if not family_id:
                family_id = stable_id("taxon_family", order_name, family_name)
                family_lookup[family_key] = family_id
                nodes[family_id] = TaxonNode(
                    taxon_id=family_id,
                    rank="family",
                    scientific_name=family_name,
                    english_name_primary=normalize_text(row.get("Family_English_name")) or english_name_primary,
                    order_name=order_name,
                    family_name=family_name,
                    genus_name="",
                    parent_taxon_id=order_id,
                    canonical_release="xlsx-fallback",
                )
                add_ordered_child(children, order_id, family_id)
            continue

        family_name = family_name or normalize_text(row.get("Scientific_name"))
        family_key = (order_name, family_name)
        family_id = family_lookup.get(family_key)
        if not family_id:
            family_id = stable_id("taxon_family", order_name, family_name)
            family_lookup[family_key] = family_id
            nodes[family_id] = TaxonNode(
                taxon_id=family_id,
                rank="family",
                scientific_name=family_name,
                english_name_primary=normalize_text(row.get("Family_English_name")),
                order_name=order_name,
                family_name=family_name,
                genus_name="",
                parent_taxon_id=order_id,
                canonical_release="xlsx-fallback",
            )
            add_ordered_child(children, order_id, family_id)

        if rank == "genus":
            genus_name = scientific_name
        else:
            genus_name = scientific_name.split(" ", 1)[0] if scientific_name else ""
        genus_key = (order_name, family_name, genus_name)
        genus_id = genus_lookup.get(genus_key)
        if not genus_id:
            genus_id = stable_id("taxon_genus", order_name, family_name, genus_name)
            genus_lookup[genus_key] = genus_id
            nodes[genus_id] = TaxonNode(
                taxon_id=genus_id,
                rank="genus",
                scientific_name=genus_name,
                english_name_primary="",
                order_name=order_name,
                family_name=family_name,
                genus_name=genus_name,
                parent_taxon_id=family_id,
                canonical_release="xlsx-fallback",
            )
            add_ordered_child(children, family_id, genus_id)

        if rank == "genus":
            continue
        if rank != "species":
            continue

        species_id = stable_id("taxon_species", order_name, family_name, scientific_name)
        if species_id not in nodes:
            nodes[species_id] = TaxonNode(
                taxon_id=species_id,
                rank="species",
                scientific_name=scientific_name,
                english_name_primary=english_name_primary,
                order_name=order_name,
                family_name=family_name,
                genus_name=genus_name,
                parent_taxon_id=genus_id,
                canonical_release="xlsx-fallback",
                avibase_id=avibase_id,
                cornell_species_code=cornell_species_code,
            )
            add_ordered_child(children, genus_id, species_id)

    return nodes, children, {
        "backbone_source": "xlsx-fallback",
        "backbone_nodes_path": str(path),
        "backbone_edges_path": str(path),
    }


def load_backbone(artifact_root: Path, avilist_xlsx: Path) -> tuple[dict[str, TaxonNode], dict[str, list[str]], dict[str, Any]]:
    artifact_result = load_backbone_from_artifacts(artifact_root)
    if artifact_result is not None:
        return artifact_result
    return load_backbone_from_avilist_xlsx(avilist_xlsx)


def find_root_order_id(nodes: dict[str, TaxonNode], root_order: str) -> str:
    matches = [
        node_id
        for node_id, node in nodes.items()
        if node.rank == "order" and normalize_key(node.scientific_name) == normalize_key(root_order)
    ]
    if not matches:
        raise TaxonomyVisualizationError(f"Could not find order '{root_order}' in the AviList backbone.")
    return matches[0]


def select_backbone_subtree(
    nodes: dict[str, TaxonNode],
    children: dict[str, list[str]],
    root_order: str,
    max_families: int,
    max_genera_per_family: int,
    max_species_per_genus: int,
) -> tuple[set[str], list[tuple[str, str]], dict[str, int]]:
    root_id = find_root_order_id(nodes, root_order)
    selected_node_ids: set[str] = {root_id}
    selected_edges: list[tuple[str, str]] = []

    family_ids = [child for child in children.get(root_id, []) if nodes.get(child) and nodes[child].rank == "family"][:max_families]
    for family_id in family_ids:
        selected_node_ids.add(family_id)
        selected_edges.append((root_id, family_id))

        genus_ids = [
            child for child in children.get(family_id, []) if nodes.get(child) and nodes[child].rank == "genus"
        ][:max_genera_per_family]
        for genus_id in genus_ids:
            selected_node_ids.add(genus_id)
            selected_edges.append((family_id, genus_id))

            species_ids = [
                child for child in children.get(genus_id, []) if nodes.get(child) and nodes[child].rank == "species"
            ][:max_species_per_genus]
            for species_id in species_ids:
                selected_node_ids.add(species_id)
                selected_edges.append((genus_id, species_id))

    counts = Counter(nodes[node_id].rank for node_id in selected_node_ids)
    return selected_node_ids, selected_edges, dict(counts)


def format_node_label(node: TaxonNode) -> str:
    return choose_species_label(node)


def compact_species_label(node: TaxonNode) -> str:
    """
    Make species labels shorter so the compact tree does not become too wide.
    """
    sci = normalize_text(node.scientific_name)
    eng = normalize_text(node.english_name_primary)

    if node.rank != "species":
        return sci

    # Split scientific name into two lines: Genus / species epithet
    parts = sci.split()
    if len(parts) >= 2:
        sci_label = f"{parts[0]}\\n{' '.join(parts[1:])}"
    else:
        sci_label = sci

    # Keep common name only if it is not too long
    if eng and len(eng) <= 28:
        return f"{sci_label}\\n{eng}"
    return sci_label


def build_taxonomy_tree_graph(
    graphviz,
    nodes: dict[str, TaxonNode],
    edges: list[tuple[str, str]],
    root_order: str,
):
    """
    Build a compact top-down taxonomy tree for thesis figures.

    Compared with the original version:
    - no orthogonal right-angle edges
    - softer top-down layout
    - rank-specific node style
    - smaller species leaves
    - arrowless edges, visually closer to a taxonomy tree
    """
    graph = graphviz.Digraph(
        name=f"taxonomy_tree_compact_{slugify(root_order)}",
        engine="dot",
    )

    graph.attr(
        rankdir="TB",
        label=f"AviList 规范分类主树局部示意：{root_order}",
        labelloc="t",
        fontsize="24",
        fontname="Microsoft YaHei",
        bgcolor="white",
        pad="0.35",
        nodesep="0.20",
        ranksep="0.62",
        splines="polyline",
        outputorder="edgesfirst",
        ordering="out",
        concentrate="false",
    )

    graph.attr(
        "node",
        fontname="Microsoft YaHei",
        color="#8AA0B6",
        penwidth="1.1",
        margin="0.10,0.06",
    )

    graph.attr(
        "edge",
        color="#9AA9B8",
        penwidth="1.25",
        arrowsize="0.0",
        dir="none",
    )

    # Keep original edge order so the tree follows the selected subtree order.
    ordered_node_ids: list[str] = []
    seen: set[str] = set()
    for src_id, dst_id in edges:
        if src_id not in seen:
            ordered_node_ids.append(src_id)
            seen.add(src_id)
        if dst_id not in seen:
            ordered_node_ids.append(dst_id)
            seen.add(dst_id)

    # Add any isolated selected node, if present.
    for node_id, node in sorted(
        nodes.items(),
        key=lambda item: (
            RANK_PRIORITY.get(item[1].rank, 99),
            item[1].scientific_name,
        ),
    ):
        if node_id not in seen:
            ordered_node_ids.append(node_id)
            seen.add(node_id)

    for node_id in ordered_node_ids:
        node = nodes[node_id]

        if node.rank == "order":
            graph.node(
                node_id,
                label=node.scientific_name,
                shape="box",
                style="rounded,filled",
                fillcolor="#0B3954",
                fontcolor="#FFFFFF",
                fontsize="18",
                penwidth="1.4",
                margin="0.18,0.10",
            )

        elif node.rank == "family":
            label = node.scientific_name
            if node.english_name_primary:
                label = f"{node.scientific_name}\\n{node.english_name_primary}"

            graph.node(
                node_id,
                label=label,
                shape="box",
                style="rounded,filled",
                fillcolor="#1F7A8C",
                fontcolor="#FFFFFF",
                fontsize="15",
                penwidth="1.2",
                margin="0.15,0.08",
            )

        elif node.rank == "genus":
            graph.node(
                node_id,
                label=node.scientific_name,
                shape="box",
                style="rounded,filled",
                fillcolor="#B8E1F2",
                fontcolor="#0F172A",
                fontsize="13",
                penwidth="1.0",
                margin="0.12,0.06",
            )

        elif node.rank == "species":
            graph.node(
                node_id,
                label=compact_species_label(node),
                shape="box",
                style="rounded,filled",
                fillcolor="#FFFFFF",
                fontcolor="#0F172A",
                fontsize="11",
                penwidth="0.9",
                margin="0.08,0.04",
            )

        else:
            graph.node(
                node_id,
                label=node.scientific_name,
                shape="box",
                style="rounded,filled",
                fillcolor="#F8FAFC",
                fontcolor="#0F172A",
                fontsize="11",
            )

    for src_id, dst_id in edges:
        src_rank = nodes[src_id].rank
        dst_rank = nodes[dst_id].rank

        if src_rank == "order" and dst_rank == "family":
            edge_color = "#6F879B"
            edge_width = "1.6"
        elif src_rank == "family" and dst_rank == "genus":
            edge_color = "#91A4B5"
            edge_width = "1.25"
        else:
            edge_color = "#B4C0CC"
            edge_width = "1.0"

        graph.edge(
            src_id,
            dst_id,
            color=edge_color,
            penwidth=edge_width,
        )

    # Add a tiny legend at the bottom.
    with graph.subgraph(name="cluster_legend") as legend:
        legend.attr(
            label="层级说明",
            fontsize="12",
            fontname="Microsoft YaHei",
            color="#D8E0E8",
            style="rounded,dashed",
        )
        legend.node(
            "legend_order",
            label="目 Order",
            shape="box",
            style="rounded,filled",
            fillcolor="#0B3954",
            fontcolor="#FFFFFF",
            fontsize="10",
        )
        legend.node(
            "legend_family",
            label="科 Family",
            shape="box",
            style="rounded,filled",
            fillcolor="#1F7A8C",
            fontcolor="#FFFFFF",
            fontsize="10",
        )
        legend.node(
            "legend_genus",
            label="属 Genus",
            shape="box",
            style="rounded,filled",
            fillcolor="#B8E1F2",
            fontcolor="#0F172A",
            fontsize="10",
        )
        legend.node(
            "legend_species",
            label="种 Species",
            shape="box",
            style="rounded,filled",
            fillcolor="#FFFFFF",
            fontcolor="#0F172A",
            fontsize="10",
        )

        legend.edge("legend_order", "legend_family", style="invis")
        legend.edge("legend_family", "legend_genus", style="invis")
        legend.edge("legend_genus", "legend_species", style="invis")

    return graph

def load_artifact_records(artifact_root: Path, basenames: list[str]) -> tuple[list[dict[str, Any]], Path | None]:
    artifact_path = find_artifact(artifact_root, basenames)
    if artifact_path is None:
        return [], None
    return load_records(artifact_path), artifact_path


def build_external_taxon_label(scientific_name: str, rank: str, english_name: str = "", note: str = "") -> str:
    pieces = [normalize_text(scientific_name) or normalize_text(note) or "Unnamed Clements node"]
    subtitle_bits = []
    if normalize_text(english_name):
        subtitle_bits.append(normalize_text(english_name))
    if normalize_text(rank):
        subtitle_bits.append(f"[{normalize_text(rank)}]")
    if normalize_text(note):
        subtitle_bits.append(normalize_text(note))
    if subtitle_bits:
        pieces.append(" | ".join(subtitle_bits))
    return "\\n".join(pieces)


def build_crosswalk_relations_from_artifacts(
    artifact_root: Path,
    nodes: dict[str, TaxonNode],
    root_order: str,
) -> tuple[list[CrosswalkRelation], dict[str, Any]]:
    crosswalk_rows, crosswalk_path = load_artifact_records(artifact_root, ["taxonomy_crosswalks"])
    alias_rows, alias_path = load_artifact_records(artifact_root, ["taxonomy_aliases"])
    conflict_rows, conflict_path = load_artifact_records(artifact_root, ["taxonomy_conflicts"])

    if not crosswalk_rows and not alias_rows and not conflict_rows:
        return [], {}

    relations: list[CrosswalkRelation] = []
    for row in crosswalk_rows:
        canonical_taxon_id = normalize_text(row.get("canonical_taxon_id"))
        canonical_node = nodes.get(canonical_taxon_id)
        if not canonical_node or normalize_key(canonical_node.order_name or canonical_node.scientific_name) != normalize_key(root_order):
            continue
        match_method = normalize_text(row.get("match_method")) or "MATCH"
        relation_kind = "exact" if match_method == "EXACT_MATCH" else "alias"
        external_rank = normalize_text(row.get("external_rank"))
        external_label = build_external_taxon_label(
            scientific_name=normalize_text(row.get("external_scientific_name")),
            rank=external_rank,
            english_name=normalize_text(row.get("external_english_name")),
        )
        relation = CrosswalkRelation(
            relation_id=normalize_text(row.get("crosswalk_id")) or stable_id("crosswalk", canonical_taxon_id, external_label),
            relation_kind=relation_kind,
            canonical_taxon_id=canonical_taxon_id,
            external_node_id=stable_id("external", match_method, external_rank, row.get("external_scientific_name"), row.get("external_english_name")),
            external_label=external_label,
            external_rank=external_rank,
            external_source=normalize_text(row.get("external_source")) or "Clements",
            edge_label=match_method.replace("_", " ").title(),
        )
        relations.append(relation)

    alias_relations: list[CrosswalkRelation] = []
    for row in alias_rows:
        canonical_taxon_id = normalize_text(row.get("canonical_taxon_id"))
        canonical_node = nodes.get(canonical_taxon_id)
        if not canonical_node or normalize_key(canonical_node.order_name or canonical_node.scientific_name) != normalize_key(root_order):
            continue
        alias_type = normalize_text(row.get("alias_type"))
        alias_value = normalize_text(row.get("alias_value"))
        if alias_type not in {"scientific_name", "english_name"} or not alias_value:
            continue
        if alias_type == "scientific_name" and normalize_key(alias_value) == normalize_key(canonical_node.scientific_name):
            continue
        alias_relations.append(
            CrosswalkRelation(
                relation_id=normalize_text(row.get("alias_id")) or stable_id("alias", canonical_taxon_id, alias_type, alias_value),
                relation_kind="alias",
                canonical_taxon_id=canonical_taxon_id,
                external_node_id=stable_id("external_alias", canonical_taxon_id, alias_type, alias_value),
                external_label=build_external_taxon_label(
                    scientific_name=alias_value,
                    rank=alias_type,
                    english_name="",
                    note=f"Clements {alias_type}",
                ),
                external_rank=alias_type,
                external_source=normalize_text(row.get("alias_source")) or "Clements",
                edge_label="Alias",
            )
        )

    relations.extend(alias_relations)

    for row in conflict_rows:
        canonical_taxon_id = normalize_text(row.get("canonical_taxon_id"))
        canonical_node = nodes.get(canonical_taxon_id)
        if not canonical_node or normalize_key(canonical_node.order_name or canonical_node.scientific_name) != normalize_key(root_order):
            continue
        conflict_type = normalize_text(row.get("conflict_type")) or "UNRESOLVED"
        external_value = normalize_text(row.get("external_value")) or normalize_text(row.get("canonical_value"))
        note = normalize_text(row.get("resolution_status")) or normalize_text(row.get("notes"))
        relations.append(
            CrosswalkRelation(
                relation_id=normalize_text(row.get("conflict_id")) or stable_id("conflict", canonical_taxon_id, conflict_type, external_value),
                relation_kind="conflict",
                canonical_taxon_id=canonical_taxon_id,
                external_node_id=stable_id("external_conflict", canonical_taxon_id, conflict_type, external_value),
                external_label=build_external_taxon_label(
                    scientific_name=external_value,
                    rank="Clements",
                    english_name="",
                    note=conflict_type.replace("_", " ").title(),
                ),
                external_rank="conflict",
                external_source=normalize_text(row.get("external_source")) or "Clements",
                edge_label=conflict_type.replace("_", " ").title(),
                detail=note,
            )
        )

    meta = {
        "crosswalk_source": "artifact",
        "crosswalk_path": str(crosswalk_path) if crosswalk_path else "",
        "alias_path": str(alias_path) if alias_path else "",
        "conflict_path": str(conflict_path) if conflict_path else "",
    }
    return relations, meta


def build_canonical_indexes(nodes: dict[str, TaxonNode], root_order: str) -> dict[str, dict[Any, Any]]:
    by_rank_and_name: dict[tuple[str, str], str] = {}
    by_name: dict[str, list[str]] = defaultdict(list)
    by_common_name: dict[str, list[str]] = defaultdict(list)
    by_cornell_code: dict[str, str] = {}
    for node_id, node in nodes.items():
        if normalize_key(node.order_name or node.scientific_name) != normalize_key(root_order):
            continue
        by_rank_and_name[(node.rank, normalize_key(node.scientific_name))] = node_id
        by_name[normalize_key(node.scientific_name)].append(node_id)
        if node.english_name_primary:
            by_common_name[normalize_key(node.english_name_primary)].append(node_id)
        if node.cornell_species_code:
            by_cornell_code[normalize_key(node.cornell_species_code)] = node_id
    return {
        "by_rank_and_name": by_rank_and_name,
        "by_name": by_name,
        "by_common_name": by_common_name,
        "by_cornell_code": by_cornell_code,
    }


def normalize_clements_rank(raw_rank: str) -> str:
    rank = normalize_text(raw_rank).lower()
    if rank == "group (monotypic)":
        return "subspecies"
    return rank


def build_crosswalk_relations_from_xlsx(
    clements_xlsx: Path,
    nodes: dict[str, TaxonNode],
    root_order: str,
) -> tuple[list[CrosswalkRelation], dict[str, Any]]:
    df = read_excel_table(clements_xlsx)
    indexes = build_canonical_indexes(nodes, root_order)
    relations: list[CrosswalkRelation] = []
    seen_relation_keys: set[tuple[str, str, str]] = set()

    for row in df.to_dict(orient="records"):
        raw_rank = normalize_text(row.get("category"))
        rank = normalize_clements_rank(raw_rank)
        if not raw_rank or rank not in RANK_PRIORITY:
            continue
        if normalize_key(row.get("order")) != normalize_key(root_order):
            continue

        scientific_name = normalize_text(row.get("scientific name"))
        english_name = normalize_text(row.get("English name"))
        species_code = normalize_text(row.get("species_code"))
        relation_kind = ""
        canonical_taxon_id = ""
        edge_label = ""

        exact_id = indexes["by_rank_and_name"].get((rank, normalize_key(scientific_name)))
        if exact_id:
            relation_kind = "exact"
            canonical_taxon_id = exact_id
            edge_label = "Exact Match"
        elif species_code and normalize_key(species_code) in indexes["by_cornell_code"]:
            canonical_taxon_id = indexes["by_cornell_code"][normalize_key(species_code)]
            relation_kind = "alias"
            edge_label = "Species Code Alias"
        elif scientific_name and normalize_key(scientific_name) in indexes["by_name"]:
            candidates = indexes["by_name"][normalize_key(scientific_name)]
            canonical_taxon_id = candidates[0]
            relation_kind = "conflict"
            edge_label = "Rank Mismatch"
        elif english_name and normalize_key(english_name) in indexes["by_common_name"]:
            candidates = indexes["by_common_name"][normalize_key(english_name)]
            canonical_taxon_id = candidates[0]
            relation_kind = "alias"
            edge_label = "Common Name Alias"
        else:
            continue

        relation_key = (relation_kind, canonical_taxon_id, normalize_key(scientific_name or english_name or raw_rank))
        if relation_key in seen_relation_keys:
            continue
        seen_relation_keys.add(relation_key)

        relations.append(
            CrosswalkRelation(
                relation_id=stable_id("crosswalk", relation_kind, canonical_taxon_id, scientific_name, english_name, raw_rank),
                relation_kind=relation_kind,
                canonical_taxon_id=canonical_taxon_id,
                external_node_id=stable_id("external", relation_kind, scientific_name, english_name, raw_rank),
                external_label=build_external_taxon_label(
                    scientific_name=scientific_name or english_name,
                    rank=raw_rank,
                    english_name=english_name,
                ),
                external_rank=raw_rank,
                external_source="Clements",
                edge_label=edge_label,
            )
        )

    return relations, {
        "crosswalk_source": "xlsx-fallback",
        "crosswalk_path": str(clements_xlsx),
        "alias_path": str(clements_xlsx),
        "conflict_path": str(clements_xlsx),
    }


def build_crosswalk_relations(
    artifact_root: Path,
    clements_xlsx: Path,
    nodes: dict[str, TaxonNode],
    root_order: str,
) -> tuple[list[CrosswalkRelation], dict[str, Any]]:
    artifact_relations, artifact_meta = build_crosswalk_relations_from_artifacts(artifact_root, nodes, root_order)
    if artifact_relations:
        return artifact_relations, artifact_meta
    return build_crosswalk_relations_from_xlsx(clements_xlsx, nodes, root_order)


def unique_preserving_order(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output


def relation_sort_key(relation: CrosswalkRelation, nodes: dict[str, TaxonNode], preferred_node_ids: set[str]) -> tuple[int, int, str, str]:
    canonical_node = nodes[relation.canonical_taxon_id]
    preferred = 0 if relation.canonical_taxon_id in preferred_node_ids else 1
    rank_score = RANK_PRIORITY.get(canonical_node.rank, 99)
    return preferred, rank_score, canonical_node.scientific_name, relation.external_label


def select_representative_crosswalks(
    relations: list[CrosswalkRelation],
    nodes: dict[str, TaxonNode],
    preferred_node_ids: set[str],
    minimum_total: int = 5,
    maximum_total: int = 10,
) -> list[CrosswalkRelation]:
    grouped: dict[str, list[CrosswalkRelation]] = {
        "exact": sorted(
            [relation for relation in relations if relation.relation_kind == "exact"],
            key=lambda relation: relation_sort_key(relation, nodes, preferred_node_ids),
        ),
        "alias": sorted(
            [relation for relation in relations if relation.relation_kind == "alias"],
            key=lambda relation: relation_sort_key(relation, nodes, preferred_node_ids),
        ),
        "conflict": sorted(
            [relation for relation in relations if relation.relation_kind == "conflict"],
            key=lambda relation: relation_sort_key(relation, nodes, preferred_node_ids),
        ),
    }
    budgets = {"exact": 3, "alias": 3, "conflict": 2}

    selected: list[CrosswalkRelation] = []
    used_relation_ids: set[str] = set()
    used_canonical_ids_by_kind: dict[str, set[str]] = defaultdict(set)

    for kind in ("exact", "alias", "conflict"):
        for relation in grouped[kind]:
            if len([item for item in selected if item.relation_kind == kind]) >= budgets[kind]:
                break
            if relation.relation_id in used_relation_ids:
                continue
            if relation.canonical_taxon_id in used_canonical_ids_by_kind[kind]:
                continue
            selected.append(relation)
            used_relation_ids.add(relation.relation_id)
            used_canonical_ids_by_kind[kind].add(relation.canonical_taxon_id)

    if len(selected) < minimum_total:
        remaining = sorted(relations, key=lambda relation: relation_sort_key(relation, nodes, preferred_node_ids))
        for relation in remaining:
            if len(selected) >= maximum_total:
                break
            if relation.relation_id in used_relation_ids:
                continue
            selected.append(relation)
            used_relation_ids.add(relation.relation_id)
            if len(selected) >= minimum_total:
                break

    if not selected:
        raise TaxonomyVisualizationError("No Clements crosswalk relations were found for the requested order.")

    return selected[:maximum_total]


def build_canonical_crosswalk_label(node: TaxonNode) -> str:
    pieces = [node.scientific_name]
    subtitle_bits = [f"[{node.rank}]"]
    if node.english_name_primary:
        subtitle_bits.insert(0, node.english_name_primary)
    pieces.append(" | ".join(subtitle_bits))
    return "\\n".join(pieces)


def build_crosswalk_graph(graphviz, relations: list[CrosswalkRelation], nodes: dict[str, TaxonNode], root_order: str):
    graph = graphviz.Digraph(name=f"checklist_crosswalk_{slugify(root_order)}")
    graph.attr(
        rankdir="LR",
        label="Checklist Crosswalk: AviList Canonical Backbone and Clements Compatibility Layer",
        labelloc="t",
        fontsize="20",
        fontname="Helvetica-Bold",
        bgcolor="white",
        pad="0.3",
        nodesep="0.45",
        ranksep="1.1",
        splines="spline",
        newrank="true",
    )

    canonical_ids = unique_preserving_order([relation.canonical_taxon_id for relation in relations])
    external_ids = unique_preserving_order([relation.external_node_id for relation in relations])

    with graph.subgraph(name="cluster_avilist") as subgraph:
        subgraph.attr(label="AviList Canonical", color="#A7B7C7", style="rounded")
        subgraph.attr(rank="same")
        for canonical_id in canonical_ids:
            node = nodes[canonical_id]
            palette = TREE_COLORS.get(node.rank, TREE_COLORS["species"])
            subgraph.node(
                canonical_id,
                label=build_canonical_crosswalk_label(node),
                shape="box",
                style="rounded,filled",
                fillcolor=palette["fill"],
                fontcolor=palette["font"],
                color="#5C7285",
                fontname="Helvetica",
                penwidth="1.1",
                margin="0.14,0.1",
            )

    with graph.subgraph(name="cluster_clements") as subgraph:
        subgraph.attr(label="Clements / BOW-compatible", color="#A7B7C7", style="rounded")
        subgraph.attr(rank="same")
        relation_lookup = {relation.external_node_id: relation for relation in relations}
        for external_id in external_ids:
            relation = relation_lookup[external_id]
            subgraph.node(
                external_id,
                label=relation.external_label,
                shape="box",
                style="rounded,filled",
                fillcolor=EXTERNAL_NODE_STYLE["fill"],
                fontcolor=EXTERNAL_NODE_STYLE["font"],
                color=EXTERNAL_NODE_STYLE["border"],
                fontname="Helvetica",
                penwidth="1.0",
                margin="0.14,0.1",
            )

    for relation in relations:
        style = RELATION_STYLES[relation.relation_kind]
        edge_label = relation.edge_label or style["label"]
        graph.edge(
            relation.canonical_taxon_id,
            relation.external_node_id,
            color=style["color"],
            style=style["style"],
            fontcolor=style["color"],
            penwidth="1.7",
            arrowsize="0.75",
            label=edge_label,
        )

    return graph


def save_dot(graph, dot_path: Path) -> Path:
    dot_path.parent.mkdir(parents=True, exist_ok=True)
    saved_path = Path(graph.save(filename=dot_path.name, directory=str(dot_path.parent)))
    return saved_path


def render_graph_outputs(graph, base_path: Path) -> dict[str, str]:
    dot_path = save_dot(graph, base_path.with_suffix(".dot"))
    dot_binary = shutil.which("dot")
    if not dot_binary:
        raise TaxonomyVisualizationError(
            "Graphviz system binary 'dot' was not found on PATH. Install Graphviz from "
            "https://graphviz.org/download/ and make sure `dot` is available, then rerun this script. "
            f"The DOT source was still written to: {dot_path}"
        )

    outputs = {"dot": str(dot_path), "dot_binary": dot_binary}
    svg_path = base_path.with_suffix(".svg")
    png_path = base_path.with_suffix(".png")
    svg_path.write_bytes(graph.pipe(format="svg"))
    png_path.write_bytes(graph.pipe(format="png"))
    outputs["svg"] = str(svg_path)
    outputs["png"] = str(png_path)
    return outputs


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def validate_args(args: argparse.Namespace) -> None:
    if args.max_families <= 0 or args.max_genera_per_family <= 0 or args.max_species_per_genus <= 0:
        raise TaxonomyVisualizationError("All subtree size limits must be positive integers.")
    if not args.avilist_xlsx.exists():
        raise TaxonomyVisualizationError(f"AviList workbook not found: {args.avilist_xlsx}")
    if not args.clements_xlsx.exists():
        raise TaxonomyVisualizationError(f"Clements workbook not found: {args.clements_xlsx}")


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        graphviz = require_graphviz_package()

        nodes, children, backbone_meta = load_backbone(args.artifact_root, args.avilist_xlsx)
        selected_node_ids, selected_edges, tree_counts = select_backbone_subtree(
            nodes=nodes,
            children=children,
            root_order=args.root_order,
            max_families=args.max_families,
            max_genera_per_family=args.max_genera_per_family,
            max_species_per_genus=args.max_species_per_genus,
        )
        tree_nodes = {node_id: nodes[node_id] for node_id in selected_node_ids}
        tree_graph = build_taxonomy_tree_graph(graphviz, tree_nodes, selected_edges, args.root_order)

        crosswalk_relations, crosswalk_meta = build_crosswalk_relations(
            artifact_root=args.artifact_root,
            clements_xlsx=args.clements_xlsx,
            nodes=nodes,
            root_order=args.root_order,
        )
        representative_relations = select_representative_crosswalks(
            relations=crosswalk_relations,
            nodes=nodes,
            preferred_node_ids=selected_node_ids,
        )
        crosswalk_graph = build_crosswalk_graph(graphviz, representative_relations, nodes, args.root_order)

        args.out_dir.mkdir(parents=True, exist_ok=True)
        root_slug = slugify(args.root_order)
        tree_base = args.out_dir / f"taxonomy_tree_{root_slug}"
        crosswalk_base = args.out_dir / f"checklist_crosswalk_{root_slug}"

        tree_outputs = render_graph_outputs(tree_graph, tree_base)
        crosswalk_outputs = render_graph_outputs(crosswalk_graph, crosswalk_base)

        manifest_path = args.out_dir / "taxonomy_visualization_manifest.json"
        manifest = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "root_order": args.root_order,
            "parameters": {
                "max_families": args.max_families,
                "max_genera_per_family": args.max_genera_per_family,
                "max_species_per_genus": args.max_species_per_genus,
            },
            "inputs": {
                "avilist_xlsx": str(args.avilist_xlsx),
                "clements_xlsx": str(args.clements_xlsx),
                "artifact_root": str(args.artifact_root),
            },
            "reuse": {
                "backbone": backbone_meta,
                "crosswalk": crosswalk_meta,
            },
            "taxonomy_tree": {
                "outputs": tree_outputs,
                "node_count": len(tree_nodes),
                "edge_count": len(selected_edges),
                "counts_by_rank": tree_counts,
            },
            "crosswalk": {
                "outputs": crosswalk_outputs,
                "relation_count": len(representative_relations),
                "counts_by_relation": dict(Counter(relation.relation_kind for relation in representative_relations)),
            },
        }
        write_manifest(manifest_path, manifest)

        print(f"Wrote taxonomy tree to {tree_outputs['dot']}, {tree_outputs['svg']}, and {tree_outputs['png']}")
        print(
            f"Wrote checklist crosswalk to {crosswalk_outputs['dot']}, "
            f"{crosswalk_outputs['svg']}, and {crosswalk_outputs['png']}"
        )
        print(f"Wrote manifest to {manifest_path}")
        return 0
    except TaxonomyVisualizationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
