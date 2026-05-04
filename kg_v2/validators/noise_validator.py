"""Noise validator for graph nodes and evidence reuse."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from kg_v2.schema.ontology_v2 import JSONL_DIR, load_jsonl, write_jsonl

BAD_SINGLE_WORDS = {"large", "small", "dark", "bright", "close"}
SHORT_WHITELIST = {"lc", "nt", "vu", "en", "cr", "ew", "ex"}


def validate_noise(
    all_nodes_path=JSONL_DIR / "all_nodes.jsonl",
    all_edges_path=JSONL_DIR / "all_edges.jsonl",
    output_path=JSONL_DIR.parent / "logs" / "noise_report.jsonl",
) -> list[dict]:
    nodes = load_jsonl(all_nodes_path)
    edges = load_jsonl(all_edges_path)
    edge_counter: Counter = Counter(edge["target"] for edge in edges if edge["type"] == "SUPPORTED_BY")

    reports: list[dict] = []
    for node in nodes:
        props = node.get("properties", {})
        label = node.get("label")
        name = str(props.get("name") or props.get("object_name") or props.get("species_name") or "").strip()
        issues: list[str] = []
        lowered = name.lower()
        if lowered in BAD_SINGLE_WORDS:
            issues.append("adjective_or_ui_junk")
        if 0 < len(lowered) < 3 and lowered not in SHORT_WHITELIST:
            issues.append("too_short")
        if re.search(r"\b\d{4}\b", name):
            issues.append("citation_like_year")
        if re.search(r"\bet al\.?\b", lowered):
            issues.append("author_reference")
        if label == "EvidenceChunk" and edge_counter.get(node["id"], 0) > 12:
            issues.append("evidence_reused_too_many_times")
        if issues:
            reports.append({"node_id": node["id"], "label": label, "name": name, "issues": issues})
    write_jsonl(output_path, reports)
    return reports
