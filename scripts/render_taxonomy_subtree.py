#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Render a local taxonomy subtree from canonical_taxon_nodes.jsonl and canonical_taxon_edges.jsonl.

Example:
python scripts/render_taxonomy_subtree.py \
  --nodes kg_v2/outputs/intermediate/taxonomy/canonical_taxon_nodes.jsonl \
  --edges kg_v2/outputs/intermediate/taxonomy/canonical_taxon_edges.jsonl \
  --root Accipitriformes \
  --max-rank species \
  --out docs/assets/taxonomy_tree_accipitriformes.dot

Then render with Graphviz:
dot -Tpng docs/assets/taxonomy_tree_accipitriformes.dot -o docs/assets/taxonomy_tree_accipitriformes.png
dot -Tsvg docs/assets/taxonomy_tree_accipitriformes.dot -o docs/assets/taxonomy_tree_accipitriformes.svg
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
    eng = node.get("english_name_primary") or ""
    rank = node.get("rank") or ""
    if eng:
        return f"{sci}\\n{eng} | {rank}"
    return f"{sci}\\n{rank}"


def dot_escape(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", required=True)
    ap.add_argument("--edges", required=True)
    ap.add_argument("--root", required=True, help="scientific_name or english_name_primary of root taxon")
    ap.add_argument("--max-rank", default="species", choices=list(RANK_ORDER))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    nodes = {}
    name_to_ids = defaultdict(list)

    for n in read_jsonl(args.nodes):
        tid = n["taxon_id"]
        nodes[tid] = n
        for key in ["scientific_name", "english_name_primary", "order_name", "family_name", "genus_name"]:
            val = n.get(key)
            if val:
                name_to_ids[val.lower()].append(tid)

    root_ids = name_to_ids.get(args.root.lower(), [])
    if not root_ids:
        raise SystemExit(f"Root not found: {args.root}")

    # Prefer exact scientific_name match if multiple.
    root_id = root_ids[0]
    for tid in root_ids:
        if nodes[tid].get("scientific_name", "").lower() == args.root.lower():
            root_id = tid
            break

    children = defaultdict(list)
    for e in read_jsonl(args.edges):
        src = e.get("src_id")
        dst = e.get("dst_id")
        if src in nodes and dst in nodes:
            children[src].append(dst)

    max_depth = RANK_ORDER[args.max_rank]
    keep = set()
    q = deque([root_id])
    while q:
        u = q.popleft()
        if u in keep:
            continue
        rank = nodes[u].get("rank", "")
        if RANK_ORDER.get(rank, 99) > max_depth:
            continue
        keep.add(u)
        for v in children.get(u, []):
            q.append(v)

    lines = [
        "digraph TaxonomyTree {",
        '  graph [rankdir=TB, bgcolor="white", splines=true, overlap=false];',
        '  node [shape=box, style="rounded,filled", fontname="Arial", fontsize=12];',
        '  edge [color="#6C8AA1"];',
    ]

    for tid in keep:
        n = nodes[tid]
        rank = n.get("rank", "")
        fill = RANK_COLOR.get(rank, "#FFFFFF")
        font = "white" if rank in {"order", "family"} else "black"
        lines.append(
            f'  "{dot_escape(tid)}" [label="{dot_escape(label_of(n))}", fillcolor="{fill}", fontcolor="{font}"];'
        )

    for src in keep:
        for dst in children.get(src, []):
            if dst in keep:
                lines.append(f'  "{dot_escape(src)}" -> "{dot_escape(dst)}";')

    lines.append("}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out} with {len(keep)} nodes.")


if __name__ == "__main__":
    main()
