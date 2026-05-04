from __future__ import annotations

from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.retrievers.base import BaseRetriever
from evaluation.knowledge_RAG.retrievers.bird_id_reverse_retriever import BirdIDReverseRetriever
from evaluation.knowledge_RAG.retrievers.hybrid_retriever import HybridRetriever
from evaluation.knowledge_RAG.retrievers.lightrag_retriever import LightRAGRetriever
from evaluation.knowledge_RAG.retrievers.table_kb_retriever import TableKBRetriever
from evaluation.knowledge_RAG.retrievers.text_chunk_retriever import TextChunkRetriever
from evaluation.knowledge_RAG.retrievers.v1_directed_kg_retriever import V1DirectedKGRetriever
from evaluation.knowledge_RAG.retrievers.v3_fact_graph_retriever import V3FactGraphRetriever
from evaluation.knowledge_RAG.routing.route_configs import DATASET_GROUPS, dataset_group_for

__all__ = ["DATASET_GROUPS", "dataset_group_for", "build_retriever"]


class NoKnowledgeRetriever:
    def __init__(self, config: KnowledgeRAGConfig) -> None:
        self.config = config

    def retrieve(self, request):
        from evaluation.knowledge_RAG.formatting.context_formatter import result_from_items

        return result_from_items(
            status="empty",
            knowledge_mode="none",
            route="vanilla_no_knowledge",
            items=[],
        )


def build_retriever(config: KnowledgeRAGConfig, *, dataset: str = "") -> BaseRetriever:
    if dataset == "Bird-ID" and config.knowledge_mode in {"kg_v3", "hybrid"}:
        return BirdIDReverseRetriever(config)
    if dataset == "List-Global" and config.knowledge_mode in {"kg_v3", "hybrid"}:
        return TableKBRetriever(config)
    if dataset_group_for(dataset) == "structured" and dataset.startswith("Bird-Classify") and config.knowledge_mode in {"kg_v3", "hybrid"}:
        return TableKBRetriever(config)
    if config.knowledge_mode == "none":
        return NoKnowledgeRetriever(config)
    if config.knowledge_mode == "text_rag":
        return TextChunkRetriever(config)
    if config.knowledge_mode == "kg_v1":
        return V1DirectedKGRetriever(config)
    if config.knowledge_mode == "kg_v3":
        if config.kg_backend == "lightrag":
            return LightRAGRetriever(config)
        return V3FactGraphRetriever(config)
    if config.knowledge_mode == "hybrid":
        return HybridRetriever(config)
    raise ValueError(f"Unsupported knowledge_mode: {config.knowledge_mode}")
