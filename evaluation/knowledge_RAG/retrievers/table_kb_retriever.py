from __future__ import annotations

from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.formatting.context_formatter import result_from_items
from evaluation.knowledge_RAG.retrievers.base import RetrievalItem, RetrievalRequest, RetrievalResult


class TableKBRetriever:
    def __init__(self, config: KnowledgeRAGConfig) -> None:
        self.config = config

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        if request.dataset == "List-Global":
            from evaluation.kg_RAG.list_global_table_retriever import retrieve_list_global_table_context

            context = retrieve_list_global_table_context(
                request.raw_item,
                birdbase_xlsx=self.config.birdbase_xlsx,
                top_k=80,
            )
            route = "table_kb_filtering"
        else:
            from evaluation.kg_RAG.family_table_retriever import retrieve_family_table_context

            context = retrieve_family_table_context(
                request.raw_item,
                order_xlsx=self.config.order_xlsx,
                top_k=12,
            )
            route = "family_table_taxonomy"
        status = "ok" if context and not context.startswith("[NO_") else "empty"
        items = [RetrievalItem(item_type="table", text=context, score=1.0, source="BIRDBASE/Order.xlsx")] if status == "ok" else []
        return result_from_items(
            status=status,
            knowledge_mode=self.config.knowledge_mode,
            route=route,
            items=items,
            context_style="deterministic_list" if request.dataset == "List-Global" else "compact",
            max_chars=self.config.max_context_chars,
            debug={"list_global_direct_output": self.config.list_global_direct_output},
        )
