from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.utils.hash_utils import stable_hash


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def node_id(prefix: str, value: str) -> str:
    return f"{prefix}:{clean(value)}"


def compact_props(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if value not in ("", None, [], {})}


def load_chunks(intermediate_dir: Path) -> dict[str, dict[str, Any]]:
    chunks: dict[str, dict[str, Any]] = {}
    for name in ("species_chunks.jsonl", "family_chunks.jsonl"):
        for row in load_jsonl(intermediate_dir / name):
            chunk_id = clean(row.get("chunk_id"))
            if chunk_id:
                chunks[chunk_id] = row
    return chunks


def qualifier_rows_for_fact(fact: dict[str, Any]) -> list[dict[str, Any]]:
    qualifiers = fact.get("qualifiers_norm")
    if not isinstance(qualifiers, dict):
        return []
    rows: list[dict[str, Any]] = []
    for key, value in sorted(qualifiers.items()):
        value = clean(value)
        if not value:
            continue
        qid = stable_hash(fact.get("fact_id", ""), key, value, prefix="qualifier_")
        rows.append(
            {
                "node_id": node_id("qualifier", qid),
                "labels": ["Qualifier"],
                "properties": {"qualifier_id": qid, "key": key, "value": value},
            }
        )
    return rows


def materialize_v3_graph(
    *,
    intermediate_dir: Path,
    graph_out_dir: Path,
    limit_facts: int = 0,
) -> dict[str, Any]:
    claims_dir = intermediate_dir / "claims"
    taxonomy_dir = intermediate_dir / "taxonomy"
    facts = load_jsonl(claims_dir / "species_facts.jsonl") + load_jsonl(claims_dir / "family_facts.jsonl")
    if limit_facts > 0:
        facts = facts[:limit_facts]
    fact_ids = {clean(row.get("fact_id")) for row in facts if clean(row.get("fact_id"))}

    evidences_all = load_jsonl(claims_dir / "evidences.jsonl")
    evidence_by_id = {clean(row.get("evidence_id")): row for row in evidences_all if clean(row.get("evidence_id"))}
    links_all = load_jsonl(claims_dir / "fact_evidence_links.jsonl")
    links = [
        row
        for row in links_all
        if clean(row.get("fact_id")) in fact_ids and clean(row.get("evidence_id")) in evidence_by_id
    ]
    linked_evidence_ids = {clean(row.get("evidence_id")) for row in links}
    evidences = [evidence_by_id[eid] for eid in linked_evidence_ids if eid in evidence_by_id]
    chunks = load_chunks(intermediate_dir)
    wanted_chunk_ids = {clean(row.get("source_chunk_id") or row.get("chunk_id")) for row in evidences}

    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    for taxon in load_jsonl(taxonomy_dir / "canonical_taxon_nodes.jsonl"):
        taxon_id = clean(taxon.get("taxon_id"))
        if not taxon_id:
            continue
        rank = clean(taxon.get("rank"))
        labels = ["Taxon"]
        if rank:
            labels.append(rank.title())
        nodes_by_id[node_id("taxon", taxon_id)] = {
            "node_id": node_id("taxon", taxon_id),
            "labels": labels,
            "properties": compact_props(taxon),
        }

    for edge in load_jsonl(taxonomy_dir / "canonical_taxon_edges.jsonl"):
        src = clean(edge.get("src_id"))
        dst = clean(edge.get("dst_id"))
        rel_type = clean(edge.get("relation_type")) or "CONTAINS"
        if src and dst:
            edges.append(
                {
                    "source": node_id("taxon", src),
                    "target": node_id("taxon", dst),
                    "type": rel_type,
                    "properties": {},
                }
            )

    for fact in facts:
        fact_id = clean(fact.get("fact_id"))
        taxon_id = clean(fact.get("subject_taxon_id"))
        if not fact_id:
            continue
        fact_node = node_id("fact", fact_id)
        nodes_by_id[fact_node] = {
            "node_id": fact_node,
            "labels": ["Fact"],
            "properties": compact_props(fact),
        }
        if taxon_id:
            taxon_node = node_id("taxon", taxon_id)
            if taxon_node not in nodes_by_id:
                nodes_by_id[taxon_node] = {
                    "node_id": taxon_node,
                    "labels": ["Taxon"],
                    "properties": {"taxon_id": taxon_id, "rank": clean(fact.get("subject_rank"))},
                }
            edges.append({"source": taxon_node, "target": fact_node, "type": "HAS_FACT", "properties": {}})
        for qualifier in qualifier_rows_for_fact(fact):
            nodes_by_id[qualifier["node_id"]] = qualifier
            edges.append({"source": fact_node, "target": qualifier["node_id"], "type": "HAS_QUALIFIER", "properties": {}})

    for evidence in evidences:
        evidence_id = clean(evidence.get("evidence_id"))
        if not evidence_id:
            continue
        evidence_node = node_id("evidence", evidence_id)
        nodes_by_id[evidence_node] = {
            "node_id": evidence_node,
            "labels": ["Evidence"],
            "properties": compact_props(evidence),
        }
        chunk_id = clean(evidence.get("source_chunk_id") or evidence.get("chunk_id"))
        if chunk_id and chunk_id in chunks:
            chunk = chunks[chunk_id]
            chunk_node = node_id("chunk", chunk_id)
            nodes_by_id[chunk_node] = {
                "node_id": chunk_node,
                "labels": ["Chunk"],
                "properties": compact_props(chunk),
            }
            edges.append({"source": evidence_node, "target": chunk_node, "type": "FROM_CHUNK", "properties": {}})

    for link in links:
        edges.append(
            {
                "source": node_id("fact", clean(link.get("fact_id"))),
                "target": node_id("evidence", clean(link.get("evidence_id"))),
                "type": "SUPPORTED_BY",
                "properties": {},
            }
        )

    nodes = list(nodes_by_id.values())
    graph_out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(graph_out_dir / "nodes.jsonl", nodes)
    write_jsonl(graph_out_dir / "edges.jsonl", edges)

    facts_with_evidence = len({clean(row.get("fact_id")) for row in links})
    evidence_with_chunk = sum(
        1 for row in evidences if clean(row.get("source_chunk_id") or row.get("chunk_id")) in chunks
    )
    total_facts = len(facts)
    evidence_with_chunk_id = sum(1 for row in evidences if clean(row.get("source_chunk_id") or row.get("chunk_id")))
    summary = {
        "status": "ok",
        "source_artifacts": {
            "species_facts": str(claims_dir / "species_facts.jsonl"),
            "family_facts": str(claims_dir / "family_facts.jsonl"),
            "evidences": str(claims_dir / "evidences.jsonl"),
            "fact_evidence_links": str(claims_dir / "fact_evidence_links.jsonl"),
            "species_chunks": str(intermediate_dir / "species_chunks.jsonl"),
            "family_chunks": str(intermediate_dir / "family_chunks.jsonl"),
            "taxonomy_nodes": str(taxonomy_dir / "canonical_taxon_nodes.jsonl"),
            "taxonomy_edges": str(taxonomy_dir / "canonical_taxon_edges.jsonl"),
        },
        "graph_out_dir": str(graph_out_dir),
        "limit_facts": int(limit_facts),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_type_counts": dict(Counter(label for node in nodes for label in node.get("labels", []))),
        "edge_type_counts": dict(Counter(edge.get("type") for edge in edges)),
        "facts_with_evidence": facts_with_evidence,
        "evidence_with_chunk": evidence_with_chunk,
        "orphan_fact_ratio": ((total_facts - facts_with_evidence) / total_facts) if total_facts else 0.0,
        "chunk_resolution_rate": (evidence_with_chunk / evidence_with_chunk_id) if evidence_with_chunk_id else 0.0,
        "wanted_chunk_count": len(wanted_chunk_ids),
    }
    (graph_out_dir / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"nodes": nodes, "edges": edges, "summary": summary}


def import_neo4j(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    try:
        from neo4j import GraphDatabase
    except Exception:
        return {"enabled": True, "status": "skip", "error": "neo4j package is not installed"}
    password = args.neo4j_password or os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        return {"enabled": True, "status": "skip", "error": "NEO4J_PASSWORD is missing"}

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, password))
    try:
        with driver.session(database=args.neo4j_database) as session:
            for node in nodes:
                labels = ":".join(label.replace(" ", "_") for label in node.get("labels", []) if label)
                props = dict(node.get("properties") or {})
                props["node_id"] = node["node_id"]
                session.run(f"MERGE (n:{labels} {{node_id: $node_id}}) SET n += $props", node_id=node["node_id"], props=props).consume()
            for edge in edges:
                rel_type = clean(edge.get("type")).replace(" ", "_")
                session.run(
                    f"MATCH (a {{node_id: $source}}), (b {{node_id: $target}}) MERGE (a)-[r:{rel_type}]->(b) SET r += $props",
                    source=edge["source"],
                    target=edge["target"],
                    props=dict(edge.get("properties") or {}),
                ).consume()
    finally:
        driver.close()
    return {"enabled": True, "status": "ok", "node_count": len(nodes), "edge_count": len(edges)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the V3 Taxon-Fact-Evidence-Chunk graph to JSONL.")
    parser.add_argument("--intermediate-dir", type=str, default="kg_v2/outputs/intermediate")
    parser.add_argument("--graph-out-dir", type=str, default="kg_v2/outputs/graph_v3_full")
    parser.add_argument("--limit-facts", type=int, default=0)
    parser.add_argument("--skip-neo4j", action="store_true")
    parser.add_argument("--neo4j-uri", type=str, default=os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7688"))
    parser.add_argument("--neo4j-user", type=str, default=os.environ.get("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--neo4j-password", type=str, default=os.environ.get("NEO4J_PASSWORD", ""))
    parser.add_argument("--neo4j-database", type=str, default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = materialize_v3_graph(
        intermediate_dir=Path(args.intermediate_dir),
        graph_out_dir=Path(args.graph_out_dir),
        limit_facts=args.limit_facts,
    )
    summary = dict(result["summary"])
    summary["neo4j"] = {"enabled": False, "status": "skipped"}
    if not args.skip_neo4j:
        summary["neo4j"] = import_neo4j(result["nodes"], result["edges"], args)
    (Path(args.graph_out_dir) / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
