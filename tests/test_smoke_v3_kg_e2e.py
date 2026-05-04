from pathlib import Path

from kg_v2.Step4_graph.smoke_v3_kg_e2e import build_smoke_graph


def test_smoke_v3_kg_e2e_skip_neo4j_builds_schema(tmp_path):
    graph_dir = tmp_path / "graph_v3_smoke"
    result = build_smoke_graph(Path("kg_v2/outputs/intermediate"), graph_dir, sample_size=5)
    assert result["status"] == "ok"
    assert (graph_dir / "nodes.jsonl").exists()
    assert (graph_dir / "edges.jsonl").exists()
    assert result["node_counts"]["Taxon"] > 0
    assert result["node_counts"]["Fact"] > 0
    assert result["node_counts"]["Evidence"] > 0
    assert result["node_counts"]["Chunk"] > 0
    assert result["edge_counts"]["HAS_FACT"] > 0
    assert result["edge_counts"]["SUPPORTED_BY"] > 0
    assert result["edge_counts"]["DERIVED_FROM"] > 0
