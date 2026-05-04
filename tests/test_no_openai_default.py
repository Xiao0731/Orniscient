import pytest

from evaluation.kg_RAG.embedding_adapter import EmbeddingAdapter, EmbeddingConfigError


def test_deepseek_key_is_not_used_as_embedding_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-secret")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_API_BASE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(EmbeddingConfigError, match="EMBEDDING_API_BASE / EMBEDDING_API_KEY"):
        EmbeddingAdapter(provider="api_compatible", model="BAAI/bge-m3", dim=1024)
