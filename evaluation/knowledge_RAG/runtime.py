from __future__ import annotations

from typing import Any

from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.registry import build_retriever
from evaluation.knowledge_RAG.retrievers.base import RetrievalRequest, RetrievalResult


class KnowledgeRAGRuntime:
    def __init__(self, config: KnowledgeRAGConfig) -> None:
        self.config = config
        self.config.validate()
        self._retrievers: dict[str, Any] = {}

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        key = f"{self.config.knowledge_mode}:{request.dataset}:{self.config.kg_backend}"
        retriever = self._retrievers.get(key)
        if retriever is None:
            retriever = build_retriever(self.config, dataset=request.dataset)
            self._retrievers[key] = retriever
        return retriever.retrieve(request)


def request_from_item(item: dict[str, Any], *, mode: str = "zero_shot") -> RetrievalRequest:
    return RetrievalRequest(
        question_id=str(item.get("question_id") or item.get("qid") or ""),
        dataset=str(item.get("dataset") or ""),
        question=str(item.get("question") or ""),
        target_entity=str(item.get("target_entity") or item.get("species") or ""),
        options=item.get("options") if isinstance(item.get("options"), dict) else None,
        answer=item.get("answer"),
        mode=mode,
        type=str(item.get("type") or ""),
        raw_item=dict(item),
    )
