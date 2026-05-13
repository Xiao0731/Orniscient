#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Render a local taxonomy subtree with Chinese labels.
"""

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path

RANK_ORDER = {
    "order": 1,
    "family": 2,
    "genus": 3,
    "species": 4,
    "subspecies": 5,
}

# 中文 rank 显示
RANK_CN = {
    "order": "目",
    "family": "科",
    "genus": "属",
    "species": "种",
    "subspecies": "亚种"
}

RANK_COLOR = {
    "order": "#0B486B",
    "family": "#1F7A8C",
    "genus": "#A8DADC",
    "species": "#F8F9FA",
    "subspecies": "#FFF3B0",
}


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def label_of(node):
    sci = node.get("scientific_name") or ""
    cn = node.get("chinese_name_primary") or ""  # 新增中文名字段
    rank = node.get("rank") or ""
    rank_label = RANK_CN.get(rank, rank)
    if cn:
        return f"{sci}\\n{cn} | {rank_label}"
    return f"{sci}\\n{rank_label}"


def dot_escape(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", required=True)
    ap.add_argument("--edges", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--max-rank", default="species", choices=list(RANK_ORDER))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    nodes = {}
    children = defaultdict(list)
    for n in read_jsonl(args.nodes):
        nodes[n["taxon_id"]] = n
    for e in read_jsonl(args.edges):
        children[e["src_id"]].append(e["dst_id"])

    # 构建 DOT
    lines = [
        "digraph TaxonomyTree {",
        '  graph [rankdir=TB, bgcolor="white", splines=true, overlap=false];',
        '  node [shape=box, style="rounded,filled", fontname="Microsoft YaHei", fontsize=12];',
        '  edge [color="#6C8AA1"];',
    ]
    for tid, node in nodes.items():
        rank = node.get("rank")
        fill = RANK_COLOR.get(rank, "#FFFFFF")
        font = "white" if rank in {"order", "family"} else "black"
        lines.append(
            f'  "{dot_escape(tid)}" [label="{dot_escape(label_of(node))}", fillcolor="{fill}", fontcolor="{font}"];'
        )

    for src, dsts in children.items():
        for dst in dsts:
            lines.append(f'  "{dot_escape(src)}" -> "{dot_escape(dst)}";')

    lines.append("}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out} with {len(nodes)} nodes.")


if __name__ == "__main__":
    main()