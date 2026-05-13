#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build Checklist Crosswalk graph with Chinese labels.
"""

import graphviz
from collections import defaultdict, Counter
from pathlib import Path

EXTERNAL_NODE_STYLE = {"fill": "#F8F6F2", "font": "#0F172A", "border": "#7C8B9C"}
TREE_COLORS = {
    "order": {"fill": "#0B3954", "font": "#FFFFFF"},
    "family": {"fill": "#1F7A8C", "font": "#FFFFFF"},
    "genus": {"fill": "#B8E1F2", "font": "#0F172A"},
    "species": {"fill": "#FFFFFF", "font": "#0F172A"},
}

RELATION_STYLES = {
    "exact": {"color": "#2E8B57", "style": "solid", "label": "完全匹配"},
    "alias": {"color": "#1D70B8", "style": "dashed", "label": "别名/同义词"},
    "conflict": {"color": "#E68A00", "style": "dashed", "label": "冲突/未解决"},
}


def build_canonical_crosswalk_label(node):
    sci = node.scientific_name
    cn = getattr(node, "chinese_name_primary", "")
    rank_cn = {"order":"目","family":"科","genus":"属","species":"种"}.get(node.rank,node.rank)
    label = f"{sci}\\n{cn} | {rank_cn}" if cn else f"{sci}\\n{rank_cn}"
    return label


def build_crosswalk_graph(relations, nodes, root_order):
    graph = graphviz.Digraph(name=f"checklist_crosswalk_{root_order}")
    graph.attr(
        rankdir="LR",
        label=f"Checklist 对照图：{root_order} 的 AviList 主骨架与 Clements 对齐层",
        labelloc="t",
        fontsize="20",
        fontname="Microsoft YaHei",
        bgcolor="white",
        nodesep="0.45",
        ranksep="1.1",
        splines="spline",
    )

    canonical_ids = list(dict.fromkeys([r.canonical_taxon_id for r in relations]))
    external_ids = list(dict.fromkeys([r.external_node_id for r in relations]))

    with graph.subgraph(name="cluster_avilist") as subgraph:
        subgraph.attr(label="AviList 主骨架", color="#A7B7C7", style="rounded")
        for cid in canonical_ids:
            node = nodes[cid]
            palette = TREE_COLORS.get(node.rank, TREE_COLORS["species"])
            subgraph.node(
                cid,
                label=build_canonical_crosswalk_label(node),
                shape="box",
                style="rounded,filled",
                fillcolor=palette["fill"],
                fontcolor=palette["font"],
                fontname="Microsoft YaHei",
            )

    with graph.subgraph(name="cluster_clements") as subgraph:
        subgraph.attr(label="Clements 对齐层", color="#A7B7C7", style="rounded")
        rel_lookup = {r.external_node_id: r for r in relations}
        for eid in external_ids:
            r = rel_lookup[eid]
            subgraph.node(
                eid,
                label=r.external_label,
                shape="box",
                style="rounded,filled",
                fillcolor=EXTERNAL_NODE_STYLE["fill"],
                fontcolor=EXTERNAL_NODE_STYLE["font"],
                color=EXTERNAL_NODE_STYLE["border"],
                fontname="Microsoft YaHei",
            )

    for r in relations:
        style = RELATION_STYLES[r.relation_kind]
        graph.edge(
            r.canonical_taxon_id,
            r.external_node_id,
            color=style["color"],
            style=style["style"],
            label=style["label"],
        )

    return graph