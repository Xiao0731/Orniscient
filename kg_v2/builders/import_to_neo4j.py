"""Import the merged KG V2 graph into Neo4j."""

from __future__ import annotations

import csv
import os
from pathlib import Path

from kg_v2.schema.ontology_v2 import JSONL_DIR, NEO4J_CSV_DIR, load_jsonl, schema_constraints_cypher

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover
    GraphDatabase = None


def _write_nodes_csv(nodes: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "nodes.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "label", "properties_json"])
        for row in nodes:
            writer.writerow([row["id"], row["label"], row.get("properties", {})])


def _write_edges_csv(edges: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "edges.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "target", "type", "properties_json"])
        for row in edges:
            writer.writerow([row["source"], row["target"], row["type"], row.get("properties", {})])


def import_to_neo4j(
    all_nodes_path=JSONL_DIR / "all_nodes.jsonl",
    all_edges_path=JSONL_DIR / "all_edges.jsonl",
    csv_dir=NEO4J_CSV_DIR,
) -> dict:
    nodes = load_jsonl(all_nodes_path)
    edges = load_jsonl(all_edges_path)
    _write_nodes_csv(nodes, csv_dir)
    _write_edges_csv(edges, csv_dir)

    if GraphDatabase is None:
        return {"status": "skipped", "reason": "neo4j package is not installed", "nodes": len(nodes), "edges": len(edges)}

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            for statement in schema_constraints_cypher():
                session.run(statement)
            for node in nodes:
                label = node["label"]
                session.run(
                    f"MERGE (n:{label} {{id: $id}}) SET n += $props",
                    id=node["id"],
                    props=node.get("properties", {}),
                )
            for edge in edges:
                relation_type = edge["type"]
                session.run(
                    f"""
                    MATCH (s {{id: $source}})
                    MATCH (t {{id: $target}})
                    MERGE (s)-[r:{relation_type}]->(t)
                    SET r += $props
                    """,
                    source=edge["source"],
                    target=edge["target"],
                    props=edge.get("properties", {}),
                )
    finally:
        driver.close()

    return {"status": "imported", "nodes": len(nodes), "edges": len(edges)}
