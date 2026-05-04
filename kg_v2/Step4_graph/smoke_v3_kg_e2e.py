from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.retrievers.base import RetrievalRequest
from evaluation.knowledge_RAG.retrievers.v3_fact_graph_retriever import FACT_QUERY, V3FactGraphRetriever


REPORT_DIR = ROOT / "reports"


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


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


def first_existing(paths: list[Path], warnings: list[str], label: str) -> Path | None:
    for path in paths:
        if path.exists() and path.stat().st_size > 0:
            return path
        warnings.append(f"[WARN] missing {path.name}")
    warnings.append(f"[WARN] no {label} file found in preferred locations")
    return None


def discover_artifacts(intermediate_dir: Path, warnings: list[str]) -> dict[str, Path | None]:
    claims = intermediate_dir / "claims"
    truth = intermediate_dir / "truth_artifacts"
    facts = first_existing(
        [
            claims / "species_facts.jsonl",
            claims / "family_facts.jsonl",
            truth / "fact_nodes.jsonl",
            intermediate_dir / "species_facts.jsonl",
            intermediate_dir / "family_facts.jsonl",
        ],
        warnings,
        "facts",
    )
    evidences = first_existing(
        [
            claims / "evidences.jsonl",
            truth / "evidence_nodes.jsonl",
            intermediate_dir / "evidences.jsonl",
        ],
        warnings,
        "evidences",
    )
    links = first_existing(
        [
            claims / "fact_evidence_links.jsonl",
            truth / "edges.jsonl",
            intermediate_dir / "fact_evidence_links.jsonl",
            intermediate_dir / "edges.jsonl",
        ],
        warnings,
        "fact/evidence links",
    )
    species_chunks = intermediate_dir / "species_chunks.jsonl"
    family_chunks = intermediate_dir / "family_chunks.jsonl"
    if not species_chunks.exists():
        warnings.append("[WARN] missing species_chunks.jsonl")
    if not family_chunks.exists():
        warnings.append("[WARN] missing family_chunks.jsonl")
    return {
        "facts": facts,
        "evidences": evidences,
        "links": links,
        "species_chunks": species_chunks if species_chunks.exists() else None,
        "family_chunks": family_chunks if family_chunks.exists() else None,
    }


def props(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row.get("properties") or row)


def make_node_id(prefix: str, raw: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", clean(raw))[:80].strip("_") or uuid.uuid4().hex[:12]
    return f"{prefix}_{safe}"


def build_link_index(links: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in links:
        if row.get("type") and row.get("type") not in {"SUPPORTED_BY", "EVIDENCED_BY", "HAS_EVIDENCE"}:
            continue
        fact_id = clean(row.get("fact_id") or row.get("source") or row.get("source_id"))
        evidence_id = clean(row.get("evidence_id") or row.get("target") or row.get("target_id"))
        fact_id = fact_id.split(":")[1] if fact_id.startswith("fact:") and ":" in fact_id else fact_id
        evidence_id = evidence_id.split(":")[1] if evidence_id.startswith("evidence") and ":" in evidence_id else evidence_id
        if fact_id and evidence_id:
            out.setdefault(fact_id, []).append(evidence_id)
    return out


def chunk_lookup(chunk_paths: list[Path], wanted_ids: set[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in chunk_paths:
        if not path or not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if len(found) >= len(wanted_ids):
                    break
                if not line.strip():
                    continue
                row = json.loads(line)
                cid = clean(row.get("chunk_id") or (row.get("properties") or {}).get("chunk_id"))
                if cid in wanted_ids:
                    found[cid] = props(row)
    return found


def normalize_fact(row: dict[str, Any]) -> dict[str, Any]:
    p = props(row)
    return {
        "fact_id": clean(p.get("fact_id") or row.get("id")),
        "subject_taxon_id": clean(p.get("subject_taxon_id") or p.get("taxon_id") or p.get("species") or p.get("subject_name")),
        "subject_name": clean(p.get("subject_name") or p.get("species")),
        "fact_domain": clean(p.get("fact_domain") or p.get("fact_type") or p.get("source_chapter") or "GeneralFacts"),
        "predicate": clean(p.get("predicate") or p.get("fact_type")),
        "object_text": clean(p.get("object_text") or p.get("object_name") or p.get("object_canonical_name") or p.get("value_text")),
        "object_canonical_name": clean(p.get("object_canonical_name") or p.get("object_name")),
        "value_text": clean(p.get("value_text")),
        "confidence": float(p.get("confidence") or 0.0),
    }


def build_smoke_graph(intermediate_dir: Path, graph_out_dir: Path, sample_size: int, target_entity: str = "") -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    artifacts = discover_artifacts(intermediate_dir, warnings)
    if not artifacts["facts"] or not artifacts["evidences"]:
        errors.append("[ERROR] no usable fact/evidence artifacts found")
        return {"status": "fail", "warnings": warnings, "errors": errors, "artifacts": artifacts}

    facts = [normalize_fact(row) for row in load_jsonl(artifacts["facts"])]
    evidences = {clean(props(row).get("evidence_id") or row.get("id")): props(row) for row in load_jsonl(artifacts["evidences"])}
    links = build_link_index(load_jsonl(artifacts["links"])) if artifacts["links"] else {}
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    wanted_chunks: set[str] = set()

    for fact in facts:
        if target_entity and target_entity.lower() not in (fact["subject_taxon_id"] + " " + fact["subject_name"]).lower():
            continue
        if not fact["fact_id"] or not fact["subject_taxon_id"]:
            continue
        evidence_ids = links.get(fact["fact_id"], [])
        for evidence_id in evidence_ids:
            evidence = evidences.get(evidence_id)
            if not evidence:
                continue
            chunk_id = clean(evidence.get("source_chunk_id") or evidence.get("chunk_id"))
            quote = clean(evidence.get("evidence_quote") or evidence.get("cleaned_text") or evidence.get("raw_text"))
            if not chunk_id or not quote:
                continue
            selected.append((fact, evidence))
            wanted_chunks.add(chunk_id)
            break
        if len(selected) >= sample_size:
            break

    if not selected:
        errors.append("[ERROR] no facts with linked evidence/source_chunk_id found")
        return {"status": "fail", "warnings": warnings, "errors": errors, "artifacts": artifacts}

    chunk_paths = [p for p in [artifacts["species_chunks"], artifacts["family_chunks"]] if isinstance(p, Path)]
    chunks = chunk_lookup(chunk_paths, wanted_chunks)
    selected = [(fact, ev) for fact, ev in selected if clean(ev.get("source_chunk_id") or ev.get("chunk_id")) in chunks]
    if not selected:
        errors.append("[ERROR] linked chunks were not found in species_chunks.jsonl or family_chunks.jsonl")
        return {"status": "fail", "warnings": warnings, "errors": errors, "artifacts": artifacts}

    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for fact, evidence in selected[:sample_size]:
        chunk_id = clean(evidence.get("source_chunk_id") or evidence.get("chunk_id"))
        chunk = chunks[chunk_id]
        taxon_id = fact["subject_taxon_id"] or clean(chunk.get("species_name") or chunk.get("family_name"))
        scientific_name = clean(chunk.get("species_name") or fact.get("subject_name") or taxon_id)
        taxon_node_id = make_node_id("taxon", taxon_id)
        fact_node_id = make_node_id("fact", fact["fact_id"])
        evidence_id = clean(evidence.get("evidence_id"))
        evidence_node_id = make_node_id("evidence", evidence_id)
        chunk_node_id = make_node_id("chunk", chunk_id)
        nodes_by_id[taxon_node_id] = {
            "node_id": taxon_node_id,
            "labels": ["Taxon", "Species"],
            "properties": {
                "taxon_id": taxon_id,
                "rank": "species",
                "scientific_name": scientific_name,
                "english_name_primary": clean(chunk.get("common_name")),
                "order_name": clean(chunk.get("order_name")),
                "family_name": clean(chunk.get("family_name")),
            },
        }
        nodes_by_id[fact_node_id] = {
            "node_id": fact_node_id,
            "labels": ["Fact"],
            "properties": {
                "fact_id": fact["fact_id"],
                "subject_taxon_id": taxon_id,
                "fact_domain": fact["fact_domain"],
                "predicate": fact["predicate"],
                "object_text": fact["object_text"] or clean(evidence.get("evidence_quote")),
                "object_canonical_name": fact["object_canonical_name"],
                "value_text": fact["value_text"],
                "confidence": fact["confidence"],
            },
        }
        nodes_by_id[evidence_node_id] = {
            "node_id": evidence_node_id,
            "labels": ["Evidence"],
            "properties": {
                "evidence_id": evidence_id,
                "source_chunk_id": chunk_id,
                "source_chapter": clean(evidence.get("source_chapter") or chunk.get("source_chapter")),
                "source_subchapter": clean(evidence.get("source_subchapter") or chunk.get("source_subchapter")),
                "evidence_quote": clean(evidence.get("evidence_quote") or evidence.get("cleaned_text") or evidence.get("raw_text")),
            },
        }
        nodes_by_id[chunk_node_id] = {
            "node_id": chunk_node_id,
            "labels": ["Chunk"],
            "properties": {
                "chunk_id": chunk_id,
                "source_chapter": clean(chunk.get("source_chapter")),
                "source_subchapter": clean(chunk.get("source_subchapter")),
                "cleaned_text": clean(chunk.get("cleaned_text") or chunk.get("raw_text"))[:2000],
                "canonical_taxon_id": taxon_id,
            },
        }
        edges.extend(
            [
                {"source": taxon_node_id, "target": fact_node_id, "type": "HAS_FACT", "properties": {}},
                {"source": fact_node_id, "target": evidence_node_id, "type": "SUPPORTED_BY", "properties": {}},
                {"source": evidence_node_id, "target": chunk_node_id, "type": "DERIVED_FROM", "properties": {}},
            ]
        )

    nodes = list(nodes_by_id.values())
    graph_out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(graph_out_dir / "nodes.jsonl", nodes)
    write_jsonl(graph_out_dir / "edges.jsonl", edges)
    summary = {
        "status": "ok",
        "source_artifacts": {k: str(v) if v else "" for k, v in artifacts.items()},
        "graph_out_dir": str(graph_out_dir),
        "node_counts": dict(Counter(label for node in nodes for label in node["labels"])),
        "edge_counts": dict(Counter(edge["type"] for edge in edges)),
        "warnings": warnings,
        "errors": errors,
        "sample_target": nodes[0]["properties"].get("scientific_name") if nodes else "",
    }
    (graph_out_dir / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**summary, "nodes": nodes, "edges": edges}


def import_neo4j(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], args: argparse.Namespace, smoke_run_id: str) -> dict[str, Any]:
    try:
        from neo4j import GraphDatabase
    except Exception:
        return {"enabled": True, "query_rows": 0, "status": "skip", "error": "neo4j package is not installed; use python -m pip install neo4j"}
    password = args.neo4j_password or os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        return {"enabled": True, "query_rows": 0, "status": "skip", "error": "NEO4J_PASSWORD is missing"}
    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, password))
    labels_allowed = {"Taxon", "Species", "Fact", "Evidence", "Chunk"}
    rel_allowed = {"HAS_FACT", "SUPPORTED_BY", "DERIVED_FROM"}
    try:
        with driver.session(database=args.neo4j_database) as session:
            if args.clear_smoke_graph:
                session.run("MATCH (n {is_smoke: true}) DETACH DELETE n").consume()
            for node in nodes:
                labels = ":".join(label for label in node["labels"] if label in labels_allowed)
                props = dict(node["properties"])
                props.update({"node_id": node["node_id"], "is_smoke": True, "smoke_run_id": smoke_run_id})
                session.run(f"MERGE (n:{labels} {{node_id: $node_id}}) SET n += $props", node_id=node["node_id"], props=props).consume()
            for edge in edges:
                if edge["type"] not in rel_allowed:
                    continue
                props = dict(edge.get("properties") or {})
                props.update({"is_smoke": True, "smoke_run_id": smoke_run_id})
                session.run(
                    f"MATCH (a {{node_id: $source}}), (b {{node_id: $target}}) MERGE (a)-[r:{edge['type']}]->(b) SET r += $props",
                    source=edge["source"],
                    target=edge["target"],
                    props=props,
                ).consume()
            rows = [
                dict(record)
                for record in session.run(
                    """
                    MATCH (t:Taxon {is_smoke: true})-[:HAS_FACT]->(f:Fact {is_smoke: true})
                          -[:SUPPORTED_BY]->(e:Evidence {is_smoke: true})
                          -[:DERIVED_FROM]->(c:Chunk {is_smoke: true})
                    RETURN t.taxon_id AS taxon_id,
                           f.fact_id AS fact_id,
                           f.predicate AS predicate,
                           e.evidence_id AS evidence_id,
                           c.chunk_id AS chunk_id
                    LIMIT 5
                    """
                )
            ]
    finally:
        driver.close()
    return {"enabled": True, "query_rows": len(rows), "status": "ok" if rows else "fail", "rows": rows}


def run_retriever_smoke(args: argparse.Namespace, target: str) -> dict[str, Any]:
    if "DIRECTED" in FACT_QUERY.upper():
        return {"name": "V3FactGraphRetriever", "used_v1_directed": True, "context_status": "fail", "errors": ["DIRECTED appears in V3 query"]}
    cfg = KnowledgeRAGConfig.from_env(
        knowledge_mode="kg_v3",
        kg_backend="neo4j",
        neo4j_uri=args.neo4j_uri,
        neo4j_username=args.neo4j_user,
        neo4j_password=args.neo4j_password or os.environ.get("NEO4J_PASSWORD", ""),
        neo4j_database=args.neo4j_database,
        enable_reranker=False,
    )
    retriever = V3FactGraphRetriever(cfg)
    result = retriever.retrieve(
        RetrievalRequest(
            question_id="smoke-v3",
            dataset="Bird-Con",
            question="Return one fact with supporting evidence and source chunk.",
            target_entity=target,
            raw_item={"question_id": "smoke-v3", "dataset": "Bird-Con", "target_entity": target},
        )
    )
    fact_count = sum(1 for item in result.items if item.fact_id)
    evidence_count = sum(1 for item in result.items if item.evidence_id)
    chunk_count = sum(1 for item in result.items if item.chunk_id or item.metadata.get("source_chunk_id"))
    return {
        "name": "V3FactGraphRetriever",
        "used_v1_directed": bool(result.debug.get("used_v1_directed", False)),
        "context_status": result.status,
        "fact_count": fact_count,
        "evidence_count": evidence_count,
        "chunk_count": chunk_count,
        "rendered_context_preview": result.rendered_context[:1200],
        "debug": result.debug,
        "errors": [] if result.status == "ok" and fact_count and evidence_count and chunk_count else ["V3 graph retrieval returned no complete Fact/Evidence/Chunk context."],
    }


def write_report(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "smoke_v3_kg_e2e_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# V3 KG E2E Smoke Report",
        "",
        f"- status: {report['status']}",
        f"- graph_out_dir: `{report['graph_out_dir']}`",
        f"- source facts: `{report['source_artifacts'].get('facts', '')}`",
        f"- source evidences: `{report['source_artifacts'].get('evidences', '')}`",
        "",
        "## Node Counts",
        *(f"- {k}: {v}" for k, v in report["node_counts"].items()),
        "",
        "## Edge Counts",
        *(f"- {k}: {v}" for k, v in report["edge_counts"].items()),
        "",
        "## Neo4j",
        f"- enabled: {report['neo4j'].get('enabled')}",
        f"- status: {report['neo4j'].get('status', '')}",
        f"- query_rows: {report['neo4j'].get('query_rows')}",
        "",
        "## Retriever",
        f"- name: {report['retriever'].get('name')}",
        f"- used_v1_directed: {report['retriever'].get('used_v1_directed')}",
        f"- context_status: {report['retriever'].get('context_status')}",
        f"- fact_count: {report['retriever'].get('fact_count')}",
        f"- evidence_count: {report['retriever'].get('evidence_count')}",
        f"- chunk_count: {report['retriever'].get('chunk_count')}",
        "",
        "## Errors",
        *(f"- {err}" for err in report.get("errors", [])),
    ]
    (REPORT_DIR / "smoke_v3_kg_e2e_report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and validate a minimal V3 Taxon-Fact-Evidence-Chunk smoke graph.")
    parser.add_argument("--intermediate-dir", type=str, default="kg_v2/outputs/intermediate")
    parser.add_argument("--graph-out-dir", type=str, default="kg_v2/outputs/graph_v3_smoke")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--neo4j-uri", type=str, default=os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7688"))
    parser.add_argument("--neo4j-user", type=str, default=os.environ.get("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--neo4j-password", type=str, default=os.environ.get("NEO4J_PASSWORD", ""))
    parser.add_argument("--neo4j-database", type=str, default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--skip-neo4j", action="store_true")
    parser.add_argument("--clear-smoke-graph", action="store_true")
    parser.add_argument("--keep-smoke-graph", action="store_true")
    parser.add_argument("--target-entity", type=str, default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    smoke_run_id = f"smoke_{uuid.uuid4().hex[:12]}"
    graph = build_smoke_graph(Path(args.intermediate_dir), Path(args.graph_out_dir), args.sample_size, args.target_entity)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    errors = list(graph.get("errors", []))
    neo4j_result = {"enabled": False, "query_rows": 0, "status": "skipped"}
    retriever_result = {
        "name": "V3FactGraphRetriever",
        "used_v1_directed": False,
        "context_status": "skipped",
        "fact_count": 0,
        "evidence_count": 0,
        "chunk_count": 0,
    }
    if not errors and not args.skip_neo4j:
        neo4j_result = import_neo4j(nodes, edges, args, smoke_run_id)
        if neo4j_result.get("status") != "ok":
            errors.append(str(neo4j_result.get("error") or "[FAIL] Neo4j Taxon->Fact->Evidence->Chunk query returned 0 rows."))
        else:
            target = args.target_entity or clean(nodes[0]["properties"].get("scientific_name") or nodes[0]["properties"].get("taxon_id"))
            retriever_result = run_retriever_smoke(args, target)
            errors.extend(retriever_result.get("errors", []))
            if retriever_result.get("used_v1_directed"):
                errors.append("[FAIL] V3 retriever used V1 DIRECTED query.")
    elif args.skip_neo4j:
        print("[WARN] --skip-neo4j enabled; retriever smoke requires Neo4j and was skipped.")

    node_counts = Counter(label for node in nodes for label in node.get("labels", []))
    edge_counts = Counter(edge.get("type") for edge in edges)
    report = {
        "status": "fail" if errors else "pass",
        "source_artifacts": {k: str(v) if v else "" for k, v in graph.get("source_artifacts", graph.get("artifacts", {})).items()},
        "graph_out_dir": str(args.graph_out_dir),
        "node_counts": {k: int(node_counts.get(k, 0)) for k in ["Taxon", "Fact", "Evidence", "Chunk"]},
        "edge_counts": {k: int(edge_counts.get(k, 0)) for k in ["HAS_FACT", "SUPPORTED_BY", "DERIVED_FROM"]},
        "neo4j": neo4j_result,
        "retriever": retriever_result,
        "warnings": graph.get("warnings", []),
        "errors": errors,
    }
    write_report(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
