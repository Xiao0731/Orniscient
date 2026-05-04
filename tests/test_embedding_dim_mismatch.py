import pytest

from evaluation.kg_RAG.embedding_adapter import EmbeddingManifestError, validate_embedding_manifest


def test_embedding_dim_mismatch_requires_rebuild(tmp_path):
    validate_embedding_manifest(
        tmp_path,
        embedding_provider="bge_m3",
        embedding_model="BAAI/bge-m3",
        embedding_dim=1024,
        index_name="bird_kg_v3_bge_m3",
    )
    with pytest.raises(EmbeddingManifestError, match="--rebuild-vector-index"):
        validate_embedding_manifest(
            tmp_path,
            embedding_provider="bge_m3",
            embedding_model="other/model",
            embedding_dim=768,
            index_name="bird_kg_v3_other",
        )

