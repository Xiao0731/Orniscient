from __future__ import annotations

from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.formatting.context_formatter import result_from_items
from evaluation.knowledge_RAG.retrievers.base import RetrievalItem, RetrievalRequest, RetrievalResult


class V1DirectedKGRetriever:
    def __init__(self, config: KnowledgeRAGConfig) -> None:
        self.config = config

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        from evaluation.kg_RAG.neo4j_direct_retriever import retrieve_kg_context

        context = retrieve_kg_context(
            target_entity=request.target_entity,
            question=request.question,
            limit=self.config.kg_top_k,
            neighbor_limit=max(80, self.config.kg_top_k * 4),
            context_style="relation_plus_node_brief",
        )
        status = "ok" if context and not context.startswith("[NO_") else "empty"
        item = RetrievalItem(item_type="fact", text=context, score=1.0, taxon_name=request.target_entity)
        return result_from_items(
            status=status,
            knowledge_mode="kg_v1",
            route="v1_directed_one_hop",
            items=[item] if status == "ok" else [],
            target=request.target_entity,
            max_chars=self.config.max_context_chars,
            debug={"legacy_context": context},
        )

