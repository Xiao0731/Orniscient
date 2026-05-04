from __future__ import annotations

from evaluation.kg_RAG.lightrag_v3_adapter import LightRAGV3Adapter
from evaluation.kg_RAG.reranker_adapter import RerankerAdapter, RerankerConfigError
from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.formatting.context_formatter import result_from_items
from evaluation.knowledge_RAG.retrievers.base import RetrievalItem, RetrievalRequest, RetrievalResult


class LightRAGRetriever:
    def __init__(self, config: KnowledgeRAGConfig) -> None:
        self.config = config
        reranker = None
        if config.enable_reranker:
            try:
                reranker = RerankerAdapter(provider=config.reranker_provider, model=config.reranker_model)
            except RerankerConfigError:
                print("[WARN] Reranker unavailable; falling back to retrieval score only.")
        self.adapter = LightRAGV3Adapter(
            working_dir=config.lightrag_working_dir,
            embedding_provider=config.embedding_provider,
            embedding_model=config.embedding_model,
            embedding_dim=config.embedding_dim,
            reranker=reranker,
            enable_reranker=bool(reranker and config.enable_reranker),
            rebuild_vector_index=config.rebuild_vector_index,
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        query = "\n".join(part for part in [request.question, request.target_entity] if part)
        items = self.adapter.query(query, mode=self.config.query_mode, top_k=self.config.lightrag_top_k)
        converted = [
            RetrievalItem(
                item_type=item.item_type,
                text=item.text,
                score=item.score,
                source=item.source,
                taxon_id=item.taxon_id,
                taxon_name=item.taxon_name,
                source_chapter=item.source_chapter,
                metadata=item.metadata,
            )
            for item in items
        ]
        return result_from_items(
            status="ok" if converted else "empty",
            knowledge_mode="kg_v3" if self.config.knowledge_mode == "kg_v3" else self.config.knowledge_mode,
            route=f"lightrag_{self.config.query_mode}",
            items=converted,
            target=request.target_entity,
            max_chars=self.config.max_context_chars,
            debug={"initial_retrieval_count": len(items), "kg_query_mode": self.config.query_mode},
        )

