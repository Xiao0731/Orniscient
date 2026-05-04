"""Graph budget validator for V2.1 species graphs."""

from __future__ import annotations

from collections import Counter, defaultdict

from kg_v2.schema.ontology_v2 import JSONL_DIR, load_jsonl, write_jsonl


def validate_graph_budget(
    species_nodes_path=JSONL_DIR / "species_nodes.jsonl",
    species_edges_path=JSONL_DIR / "species_edges.jsonl",
    output_path=JSONL_DIR.parent / "logs" / "graph_budget_report.jsonl",
) -> list[dict]:
    nodes = {row["id"]: row for row in load_jsonl(species_nodes_path)}
    edges = load_jsonl(species_edges_path)
    out_edges: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        out_edges[edge["source"]].append(edge)

    reports: list[dict] = []
    for node in nodes.values():
        if node["label"] != "Species":
            continue
        species_id = node["id"]
        fact_ids = [edge["target"] for edge in out_edges.get(species_id, []) if edge["type"] == "HAS_FACT"]
        connected_nodes = {species_id}
        evidence_links = 0
        category_counts: Counter = Counter()
        for fact_id in fact_ids:
            connected_nodes.add(fact_id)
            for edge in out_edges.get(fact_id, []):
                connected_nodes.add(edge["target"])
                if edge["type"] == "SUPPORTED_BY":
                    evidence_links += 1
                target = nodes.get(edge["target"])
                if edge["type"] == "OBJECT" and target:
                    category_counts[target["label"]] += 1
        warnings: list[str] = []
        failures: list[str] = []
        if len(connected_nodes) > 150:
            failures.append("connected_nodes > 150")
        if len(fact_ids) > 55:
            failures.append("fact_nodes > 55")
        if evidence_links > 80:
            failures.append("evidence_links > 80")
        if category_counts["Habitat"] > 4:
            warnings.append("habitat nodes > 4")
        if category_counts["Geography"] > 4:
            warnings.append("geography nodes > 4")
        if category_counts["Food"] > 4:
            warnings.append("diet nodes > 4")
        if category_counts["Species"] > 3:
            warnings.append("similar species > 3")
        reports.append(
            {
                "species_name": node.get("properties", {}).get("species_name"),
                "connected_nodes": len(connected_nodes),
                "fact_nodes": len(fact_ids),
                "evidence_links": evidence_links,
                "category_counts": dict(category_counts),
                "warnings": warnings,
                "failures": failures,
                "status": "fail" if failures else "warn" if warnings else "pass",
            }
        )
    write_jsonl(output_path, reports)
    return reports
