"""Graph retrieval with local JSONL fallback for KG V2."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from kg_v2.schema.ontology_v2 import JSONL_DIR, load_jsonl

ENTITY_FIELDS = ("species_name", "common_name", "name", "family_name")
FACT_KEYWORDS = {
    "INHABITS": ("habitat", "live", "inhabit"),
    "FOUND_IN": ("where", "range", "distribution", "found"),
    "PREYS_ON": ("diet", "food", "eat", "foraging"),
    "EXHIBITS": ("behavior", "migrat", "nest", "breed"),
    "THREATENED_BY": ("threat", "risk", "decline", "conservation"),
    "HAS_STATUS": ("iucn", "status", "endangered", "vulnerable", "concern"),
}


class Neo4jRetriever:
    def __init__(
        self,
        nodes_path: str | Path = JSONL_DIR / "all_nodes.jsonl",
        edges_path: str | Path = JSONL_DIR / "all_edges.jsonl",
    ):
        self.nodes = {row["id"]: row for row in load_jsonl(nodes_path)}
        self.edges = load_jsonl(edges_path)
        self.out_edges: dict[str, list[dict]] = defaultdict(list)
        for edge in self.edges:
            self.out_edges[edge["source"]].append(edge)

    def find_entities(self, query: str, limit: int = 5) -> list[dict]:
        lowered = query.lower()
        matches: list[dict] = []
        for node in self.nodes.values():
            if node["label"] not in {"Species", "Family", "Genus", "Order"}:
                continue
            props = node.get("properties", {})
            names = [str(props.get(field, "") or "") for field in ENTITY_FIELDS]
            if any(name and name.lower() in lowered for name in names):
                matches.append(node)
        return matches[:limit]

    def detect_fact_type(self, query: str) -> str | None:
        lowered = query.lower()
        for fact_type, keywords in FACT_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return fact_type
        return None

    def retrieve(self, query: str, entity_name: str | None = None, fact_type: str | None = None, limit: int = 10) -> dict:
        matched_nodes = self.find_entities(entity_name or query, limit=5)
        target_fact_type = fact_type or self.detect_fact_type(query)

        results = {
            "matched_entities": [
                {"id": node["id"], "label": node["label"], "properties": node.get("properties", {})} for node in matched_nodes
            ],
            "facts": [],
            "paths": [],
            "evidence_chunks": [],
        }
        evidence_seen = set()

        for node in matched_nodes:
            if node["label"] == "Species":
                for edge in self.out_edges.get(node["id"], []):
                    if edge["type"] != "HAS_FACT":
                        continue
                    fact_node = self.nodes.get(edge["target"])
                    if not fact_node:
                        continue
                    fact_props = fact_node.get("properties", {})
                    if target_fact_type and fact_props.get("fact_type") != target_fact_type:
                        continue
                    object_nodes = []
                    evidence_nodes = []
                    for fact_edge in self.out_edges.get(fact_node["id"], []):
                        target_node = self.nodes.get(fact_edge["target"])
                        if not target_node:
                            continue
                        if fact_edge["type"] == "OBJECT":
                            object_nodes.append(target_node)
                        elif fact_edge["type"] == "SUPPORTED_BY":
                            evidence_nodes.append(target_node)
                            if target_node["id"] not in evidence_seen:
                                evidence_seen.add(target_node["id"])
                                results["evidence_chunks"].append(target_node)
                    results["facts"].append({"fact": fact_node, "objects": object_nodes, "evidence": evidence_nodes})
                    results["paths"].append(
                        {
                            "subject": node.get("properties", {}),
                            "fact": fact_props,
                            "objects": [obj.get("properties", {}) for obj in object_nodes],
                            "evidence_chunk_ids": [item.get("properties", {}).get("chunk_id") for item in evidence_nodes],
                        }
                    )
            elif node["label"] == "Family":
                for edge in self.out_edges.get(node["id"], []):
                    target_node = self.nodes.get(edge["target"])
                    if not target_node:
                        continue
                    if edge["type"] in {"HAS_ASPECT", "HAS_DERIVED_SUMMARY"}:
                        results["paths"].append(
                            {
                                "family": node.get("properties", {}),
                                "relation_type": edge["type"],
                                "target": target_node.get("properties", {}),
                            }
                        )
                        if edge["type"] == "HAS_ASPECT":
                            for aspect_edge in self.out_edges.get(target_node["id"], []):
                                if aspect_edge["type"] != "SUPPORTED_BY":
                                    continue
                                evidence_node = self.nodes.get(aspect_edge["target"])
                                if evidence_node and evidence_node["id"] not in evidence_seen:
                                    evidence_seen.add(evidence_node["id"])
                                    results["evidence_chunks"].append(evidence_node)

        results["facts"] = results["facts"][:limit]
        results["paths"] = results["paths"][:limit]
        results["evidence_chunks"] = results["evidence_chunks"][:limit]
        return results
