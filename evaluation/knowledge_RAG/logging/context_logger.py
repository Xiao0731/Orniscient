from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.retrievers.base import RetrievalRequest, RetrievalResult
from evaluation.knowledge_RAG.routing.route_configs import dataset_group_for


def context_log_row(config: KnowledgeRAGConfig, request: RetrievalRequest, result: RetrievalResult) -> dict[str, Any]:
    return {
        "question_id": request.question_id,
        "dataset": request.dataset,
        "dataset_group": dataset_group_for(request.dataset, request.type),
        "knowledge_mode": config.knowledge_mode,
        "kg_backend": config.kg_backend,
        "kg_version": config.kg_version,
        "kg_query_mode": config.query_mode,
        "embedding_model": config.embedding_model,
        "embedding_dim": config.embedding_dim,
        "reranker_model": config.reranker_model,
        "reranker_enabled": config.enable_reranker,
        "route": result.route,
        "status": result.status,
        "initial_retrieval_count": result.debug.get("initial_retrieval_count", len(result.items)),
        "reranked_count": result.debug.get("reranked_count", len(result.items)),
        "items": [
            {
                "item_type": item.item_type,
                "fact_id": item.fact_id,
                "predicate": item.metadata.get("predicate", ""),
                "object_text": item.metadata.get("object_name") or item.metadata.get("value_text", ""),
                "retrieval_score": item.score,
                "rerank_score": item.metadata.get("rerank_score"),
                "rank_before": item.metadata.get("rank_before"),
                "rank_after": item.metadata.get("rank_after"),
                "evidence_quote": item.text[:500],
                "source_chunk_id": item.chunk_id,
                "source": item.source,
            }
            for item in result.items
        ],
    }


def append_context_log(path: str | Path, row: dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
