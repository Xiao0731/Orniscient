from __future__ import annotations

"""
kg_probe.py
===========

Debug utility for the ornithology knowledge graph.

This version supports TWO backends:
1. cypher   -> direct Neo4j querying (recommended for debugging graph contents)
2. lightrag -> LightRAG natural-language query (kept for comparison)
3. both     -> run both backends in one pass

Why direct Cypher is useful
---------------------------
When LightRAG query fails, you often still need to answer a simpler question:
"Does the graph actually contain this bird, and what 1-hop facts are attached to it?"
Direct Cypher is the fastest way to answer that.

Typical usage
-------------
python kg_probe.py --bird "Emberiza sahari"
python kg_probe.py --bird "White-browed Meadowlark" --backend both --dataset Bird-Con
python kg_probe.py --bird "Emberiza sahari" --backend cypher --out probe.json
"""

import argparse
import asyncio
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(override=True)

# ---------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "") or None
WORKING_DIR = os.getenv("LIGHTRAG_WORKING_DIR", "./bird_graph_storage")

CANDIDATE_NAME_PROPS = [
    "entity_id",
    "name",
    "id",
    "common_name",
    "species",
    "scientific_name",
    "title",
]


def sanitize_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    return text[:80] if text else "probe"


def to_preview(value: Any, limit: int = 1200) -> str:
    if value is None:
        return "<None>"
    text = str(value)
    return text if len(text) <= limit else text[:limit] + " ...[truncated]"


def compact_props(props: Dict[str, Any], max_items: int = 12, max_len: int = 180) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for i, (k, v) in enumerate(props.items()):
        if i >= max_items:
            out["..."] = f"{len(props) - max_items} more fields"
            break
        text = str(v)
        out[k] = text if len(text) <= max_len else text[:max_len] + " ...[truncated]"
    return out


# ---------------------------------------------------------------------
# Cypher helpers
# ---------------------------------------------------------------------

def _neo4j_session(driver):
    if NEO4J_DATABASE:
        return driver.session(database=NEO4J_DATABASE)
    return driver.session()


def _exact_match_where(alias: str = "n") -> str:
    clauses = [f"toLower(coalesce({alias}.{prop}, '')) = toLower($bird)" for prop in CANDIDATE_NAME_PROPS]
    return " OR ".join(clauses)


def _contains_match_where(alias: str = "n") -> str:
    clauses = [f"toLower(coalesce({alias}.{prop}, '')) CONTAINS toLower($bird)" for prop in CANDIDATE_NAME_PROPS]
    return " OR ".join(clauses)


def cypher_run(driver, query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = params or {}
    try:
        with _neo4j_session(driver) as session:
            result = session.run(query, **params)
            records = [r.data() for r in result]
        return {
            "ok": True,
            "query": query,
            "params": params,
            "count": len(records),
            "records": records,
            "preview": to_preview(records[:5]),
        }
    except Exception as exc:
        return {
            "ok": False,
            "query": query,
            "params": params,
            "count": 0,
            "records": [],
            "preview": f"<EXCEPTION> {type(exc).__name__}: {exc}",
        }


def run_cypher_probes(bird: str) -> List[Dict[str, Any]]:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    probes: List[Dict[str, Any]] = []
    try:
        probes.append({
            "label": "health_check",
            **cypher_run(driver, "RETURN 1 AS ok, currentDatabase() AS database")
        })

        probes.append({
            "label": "exact_node_match",
            **cypher_run(
                driver,
                f"""
                MATCH (n)
                WHERE {_exact_match_where('n')}
                RETURN labels(n) AS labels, properties(n) AS props
                LIMIT 20
                """,
                {"bird": bird},
            )
        })

        probes.append({
            "label": "contains_node_match",
            **cypher_run(
                driver,
                f"""
                MATCH (n)
                WHERE {_contains_match_where('n')}
                RETURN labels(n) AS labels, properties(n) AS props
                LIMIT 20
                """,
                {"bird": bird},
            )
        })

        # Full-text lookup is useful because LightRAG log showed a full-text index on entity_id.
        probes.append({
            "label": "fulltext_entity_id_search",
            **cypher_run(
                driver,
                """
                CALL db.index.fulltext.queryNodes('entity_id_fulltext_idx_base', $query)
                YIELD node, score
                RETURN score, labels(node) AS labels, properties(node) AS props
                LIMIT 20
                """,
                {"query": f'"{bird}" OR {bird}'},
            )
        })

        one_hop_query = f"""
        MATCH (n)-[r]-(m)
        WHERE {_exact_match_where('n')} OR {_contains_match_where('n')}
        RETURN
            labels(n) AS src_labels,
            properties(n) AS src_props,
            type(r) AS rel_type,
            labels(m) AS nbr_labels,
            properties(m) AS nbr_props
        LIMIT 80
        """
        probes.append({
            "label": "one_hop_neighbors",
            **cypher_run(driver, one_hop_query, {"bird": bird})
        })

        count_query = f"""
        MATCH (n)-[r]-()
        WHERE {_exact_match_where('n')} OR {_contains_match_where('n')}
        RETURN count(r) AS degree
        """
        probes.append({
            "label": "neighbor_count",
            **cypher_run(driver, count_query, {"bird": bird})
        })

        # Provide a friendlier condensed summary for JSON output.
        for probe in probes:
            condensed = []
            for row in probe.get("records", [])[:10]:
                condensed_row = {}
                for key, value in row.items():
                    if isinstance(value, dict):
                        condensed_row[key] = compact_props(value)
                    else:
                        condensed_row[key] = value
                condensed.append(condensed_row)
            probe["condensed_records"] = condensed
            probe["preview"] = to_preview(condensed)

    finally:
        driver.close()

    return probes


# ---------------------------------------------------------------------
# Optional LightRAG backend
# ---------------------------------------------------------------------

def build_probe_queries(dataset: str, bird_name: str, build_kg_query, get_query_mode) -> List[Dict[str, str]]:
    dataset_query = build_kg_query(dataset, bird_name)
    default_mode = get_query_mode(dataset)
    return [
        {"label": "dataset_query", "query": dataset_query, "mode": default_mode},
        {"label": "name_only_local", "query": bird_name, "mode": "local"},
        {"label": "name_only_mix", "query": bird_name, "mode": "mix"},
        {"label": "simple_summary_local", "query": f"Summarize key facts about {bird_name}.", "mode": "local"},
        {"label": "simple_summary_mix", "query": f"Summarize key facts about {bird_name}.", "mode": "mix"},
        {"label": "simple_summary_global", "query": f"Summarize key facts about {bird_name}.", "mode": "global"},
    ]


def run_lightrag_query(rag, query: str, mode: str) -> Dict[str, Any]:
    try:
        result = rag.query(query, param=__import__("lightrag").QueryParam(mode=mode))
        return {
            "ok": True,
            "query": query,
            "mode": mode,
            "python_type": type(result).__name__,
            "is_none": result is None,
            "preview": to_preview(result),
            "raw_result": result,
        }
    except Exception as exc:
        return {
            "ok": False,
            "query": query,
            "mode": mode,
            "python_type": "Exception",
            "is_none": False,
            "preview": f"<EXCEPTION> {type(exc).__name__}: {exc}",
            "raw_result": None,
        }


def run_lightrag_probes(bird: str, dataset: str) -> List[Dict[str, Any]]:
    # Lazy import so Cypher-only mode does not depend on benchmark_complete or LightRAG query compatibility.
    from lightrag import LightRAG
    from benchmark_complete import (
        llm_model_func,
        my_embedding_func,
        my_rerank_func,
        build_kg_query,
        get_query_mode,
    )

    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=llm_model_func,
        embedding_func=my_embedding_func,
        kv_storage="PGKVStorage",
        vector_storage="PGVectorStorage",
        graph_storage="Neo4JStorage",
        rerank_model_func=my_rerank_func,
    )

    async def _init_and_finalize(probe_fn):
        await rag.initialize_storages()
        try:
            return probe_fn()
        finally:
            try:
                await rag.finalize_storages()
            except Exception:
                pass

    def _probe_body():
        probes = []
        for probe in build_probe_queries(dataset, bird, build_kg_query, get_query_mode):
            probes.append({"label": probe["label"], **run_lightrag_query(rag, probe["query"], probe["mode"])})
        return probes

    return asyncio.run(_init_and_finalize(_probe_body))


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Probe the bird KG via Cypher and/or LightRAG.")
    parser.add_argument("--bird", required=True, help="Bird name to probe, e.g. 'Emberiza sahari'")
    parser.add_argument("--dataset", default="Bird-Con", help="Dataset name for optional LightRAG probes")
    parser.add_argument("--backend", choices=["cypher", "lightrag", "both"], default="cypher")
    parser.add_argument("--out", default=None, help="Optional JSON output path")
    args = parser.parse_args()

    report: Dict[str, Any] = {
        "bird": args.bird,
        "dataset": args.dataset,
        "backend": args.backend,
        "neo4j_uri": NEO4J_URI,
        "neo4j_database": NEO4J_DATABASE,
        "working_dir": WORKING_DIR,
        "cypher_results": [],
        "lightrag_results": [],
    }

    print("=" * 80)
    print(f"KG probe for bird={args.bird!r} | dataset={args.dataset!r} | backend={args.backend!r}")
    print(f"Neo4j URI: {NEO4J_URI}")
    print(f"Neo4j database: {NEO4J_DATABASE}")
    print(f"LightRAG working_dir: {WORKING_DIR}")
    print("=" * 80)

    if args.backend in {"cypher", "both"}:
        print("\n--- Running direct Cypher probes ---")
        report["cypher_results"] = run_cypher_probes(args.bird)
        for result in report["cypher_results"]:
            print(f"\n[{result['label']}] ok={result['ok']} count={result.get('count', 0)}")
            print(result["preview"])

    if args.backend in {"lightrag", "both"}:
        print("\n--- Running LightRAG probes ---")
        report["lightrag_results"] = run_lightrag_probes(args.bird, args.dataset)
        for result in report["lightrag_results"]:
            print(f"\n[{result['label']}] mode={result['mode']} ok={result['ok']} type={result['python_type']} is_none={result['is_none']}")
            print(result["preview"])

    out_path = args.out or f"kg_probe_{sanitize_filename(args.bird)}_{sanitize_filename(args.dataset)}_{args.backend}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print("\nSaved probe report to:", os.path.abspath(out_path))
    print("\nInterpretation tips:")
    print("- If direct Cypher exact/contains/fulltext finds nodes, the graph DOES contain your bird in some form.")
    print("- If one_hop_neighbors is empty but node match exists, the node may be isolated or schema differs from expectation.")
    print("- If Cypher works but LightRAG fails, the problem is in the LightRAG query pipeline, not the graph contents.")
    print("- If exact match fails but fulltext/contains works, normalize the bird identifier used in your benchmark.")


if __name__ == "__main__":
    main()
