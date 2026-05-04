from __future__ import annotations

from .route_configs import RouteConfig


def route_dataset(dataset: str, subtype: str = "", knowledge_mode: str = "kg_v3") -> RouteConfig:
    ds = (dataset or "").strip()
    subtype = (subtype or "").strip()
    if ds in {"QA-SC", "QA-SA"}:
        return RouteConfig("target_fact_evidence", "compact", max_facts=8, max_chunks=4)
    if ds == "QA-MC":
        return RouteConfig("conservative_evidence", "compact", max_facts=5, max_chunks=3)
    if ds == "Bird-Geo":
        return RouteConfig("geo_fact_evidence", "compact", ["Distribution", "Movement", "Habitat"], max_facts=8)
    if ds == "Bird-Life":
        return RouteConfig("life_history_evidence", "evidence_rich", ["Breeding", "Life history", "Parental care"], max_facts=12)
    if ds == "Bird-Con":
        return RouteConfig("conservation_evidence", "evidence_rich", ["Conservation", "Threat", "Population"], max_facts=12)
    if ds == "Bird-Eco":
        return RouteConfig("ecology_evidence", "evidence_rich", ["Diet", "Foraging", "Habitat"], max_facts=12)
    if ds == "Bird-Comp":
        return RouteConfig("comparison_evidence", "evidence_rich", ["Identification", "Morphology", "Sound"], max_facts=12)
    if ds == "Bird-Reason":
        return RouteConfig("multi_domain_graph", "evidence_rich", max_facts=14, max_chunks=6)
    if ds == "Bird-Plan":
        return RouteConfig("conservation_planning", "evidence_rich", ["Conservation", "Habitat", "Threat"], max_facts=14)
    if ds == "List-Global":
        return RouteConfig("table_kb_filtering", "deterministic_list", use_table_kb=True)
    if ds == "Bird-ID":
        return RouteConfig("bird_id_reverse_rerank", "candidate_list", use_reverse_retrieval=True, forbid_gold=True, max_facts=30)
    subtype_lower = subtype.lower()
    if ds in {"Bird-Classify__Feature-to-Family", "Bird-Classify-Type2"} or "feature-to-family" in subtype_lower or "order-family" in subtype_lower:
        return RouteConfig("family_table_taxonomy", "compact", use_table_kb=True, max_chunks=6)
    if ds in {"Bird-Classify", "Bird-Classify-Type1"}:
        return RouteConfig("family_feature_evidence", "evidence_rich", ["Identification", "Morphology", "Taxonomy"], max_facts=10)
    return RouteConfig("generic_knowledge", "compact", max_facts=8, max_chunks=5)
