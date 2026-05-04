from evaluation.kg_RAG.reranker_adapter import RerankerAdapter


def test_reranker_changes_order_and_records_ranks():
    reranker = RerankerAdapter(provider="bge_reranker", model="BAAI/bge-reranker-v2-m3")
    docs = [
        {"text": "plain unrelated forest note", "score": 0.0},
        {"text": "red bill wetland migratory species evidence", "score": 0.0},
    ]
    ranked = reranker.rerank("red bill wetland", docs, top_n=2)
    assert ranked[0]["text"].startswith("red bill")
    assert ranked[0]["rank_before"] == 2
    assert ranked[0]["rank_after"] == 1
    assert "rerank_score" in ranked[0]

