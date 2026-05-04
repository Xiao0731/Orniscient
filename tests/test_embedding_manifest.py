from evaluation.kg_RAG.embedding_adapter import validate_embedding_manifest


def test_bge_m3_manifest_dim_1024(tmp_path):
    manifest = validate_embedding_manifest(
        tmp_path,
        embedding_provider="bge_m3",
        embedding_model="BAAI/bge-m3",
        embedding_dim=1024,
        index_name="bird_kg_v3_bge_m3",
    )
    assert manifest["embedding_model"] == "BAAI/bge-m3"
    assert manifest["embedding_dim"] == 1024

