from __future__ import annotations

from evaluation.kg_RAG.reranker_adapter import RerankerAdapter, RerankerConfigError
from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.formatting.context_formatter import result_from_items
from evaluation.knowledge_RAG.retrievers.base import RetrievalItem, RetrievalRequest, RetrievalResult
from evaluation.knowledge_RAG.retrievers.lightrag_retriever import LightRAGRetriever
from evaluation.knowledge_RAG.retrievers.table_kb_retriever import TableKBRetriever
from evaluation.knowledge_RAG.retrievers.v3_fact_graph_retriever import V3FactGraphRetriever
from evaluation.knowledge_RAG.routing.dataset_router import route_dataset


class HybridRetriever:
    def __init__(self, config: KnowledgeRAGConfig) -> None:
        self.config = config
        self.graph = V3FactGraphRetriever(config)
        self.light = LightRAGRetriever(config)
        self.table = TableKBRetriever(config)
        self.reranker = None
        if config.enable_reranker:
            try:
                self.reranker = RerankerAdapter(provider=config.reranker_provider, model=config.reranker_model)
            except RerankerConfigError:
                print("[WARN] Reranker unavailable; falling back to retrieval score only.")

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        route = route_dataset(request.dataset, request.type, "hybrid")
        if route.use_table_kb and request.dataset in {"List-Global", "Bird-Classify"}:
            return self.table.retrieve(request)

        graph_result = self.graph.retrieve(request)
        light_result = self.light.retrieve(request)
        items = [*graph_result.items, *light_result.items]
        initial_count = len(items)

        if self.reranker and self.reranker.enabled and items:
            docs = [
                {
                    "text": self._rerank_text(item),
                    "score": item.score,
                    "item_type": item.item_type,
                    "_item": item,
                }
                for item in items
            ]
            ranked = self.reranker.rerank(request.question, docs, text_key="text", top_n=self.config.reranker_top_n)
            items = []
            for row in ranked:
                item = row.pop("_item")
                item.metadata.update(
                    {
                        "rerank_score": row.get("rerank_score"),
                        "rank_before": row.get("rank_before"),
                        "rank_after": row.get("rank_after"),
                        "reranker_model": row.get("reranker_model"),
                    }
                )
                items.append(item)
        else:
            items = sorted(items, key=lambda item: item.score, reverse=True)[: self.config.reranker_top_n]

        return result_from_items(
            status="ok" if items else "empty",
            knowledge_mode="hybrid",
            route=route.route,
            items=items,
            target=request.target_entity,
            context_style=route.context_style,
            max_chars=self.config.max_context_chars,
            debug={
                "kg_backend": "hybrid",
                "kg_query_mode": self.config.query_mode,
                "initial_retrieval_count": initial_count,
                "reranked_count": len(items),
                "graph_status": graph_result.status,
                "lightrag_status": light_result.status,
            },
        )

    @staticmethod
    def _rerank_text(item: RetrievalItem) -> str:
        if item.item_type == "fact":
            meta = item.metadata
            return " | ".join(
                str(part)
                for part in [
                    meta.get("predicate"),
                    meta.get("object_name"),
                    meta.get("value_text"),
                    meta.get("qualifiers"),
                    item.text[:1000],
                ]
                if part
            )
        return item.text[:1000]
