import json

from evaluation.kg_RAG.embedding_adapter import validate_embedding_manifest
from evaluation.kg_RAG.lightrag_v3_adapter import LightRAGV3Adapter


def test_lightrag_mix_mode_returns_result(tmp_path):
    validate_embedding_manifest(
        tmp_path,
        embedding_provider="bge_m3",
        embedding_model="BAAI/bge-m3",
        embedding_dim=1024,
        index_name="bird_kg_v3_bge_m3",
    )
    row = {
        "doc_id": "taxon1::DistributionAndMovement",
        "title": "Test bird | DistributionAndMovement",
        "content": "Facts:\n- OCCURS_IN: sub-Saharan Africa\nEvidence: wetland range",
        "metadata": {"taxon_id": "taxon1", "scientific_name": "Test bird", "source_chapters": ["Distribution"]},
    }
    (tmp_path / "docs.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    adapter = LightRAGV3Adapter(working_dir=tmp_path, enable_reranker=False)
    results = adapter.query("Where does it occur in Africa?", mode="mix", top_k=5)
    assert results
    assert results[0].metadata["doc_id"] == "taxon1::DistributionAndMovement"

