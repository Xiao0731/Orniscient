from __future__ import annotations

from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.formatting.context_formatter import result_from_items
from evaluation.knowledge_RAG.retrievers.base import RetrievalItem, RetrievalRequest, RetrievalResult
from evaluation.knowledge_RAG.routing.dataset_router import route_dataset


class TextChunkRetriever:
    def __init__(self, config: KnowledgeRAGConfig) -> None:
        from evaluation.text_RAG.text_rag_runtime import TextRAGCorpus

        self.config = config
        self.corpus = TextRAGCorpus.from_paths(
            species_chunks_jsonl="kg_v2/outputs/intermediate/species_chunks.jsonl",
            family_chunks_jsonl="kg_v2/outputs/intermediate/family_chunks.jsonl",
            top_k=config.text_top_k,
            max_chars_per_chunk=1200,
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        from evaluation.text_RAG.text_rag_runtime import build_text_rag_bundle

        route = route_dataset(request.dataset, request.type, "text_rag")
        item = dict(request.raw_item)
        item.setdefault("question_id", request.question_id)
        item.setdefault("dataset", request.dataset)
        item.setdefault("question", request.question)
        item.setdefault("target_entity", request.target_entity)
        bundle = build_text_rag_bundle(
            self.corpus,
            item,
            top_k=self.config.text_top_k,
            max_total_chars=self.config.max_context_chars,
            restrict_to_target=None,
        )
        items = [
            RetrievalItem(
                item_type="chunk",
                text=result.chunk.text,
                score=float(result.score),
                source=result.chunk.source_file,
                taxon_name=result.chunk.species or result.chunk.family,
                chunk_id=result.chunk.chunk_id,
                source_chapter=result.chunk.chapter,
                metadata={"matched_on": result.matched_on},
            )
            for result in bundle.results
        ]
        return result_from_items(
            status=bundle.status,
            knowledge_mode="text_rag",
            route=bundle.retrieval_policy or route.route,
            items=items,
            target=bundle.target_entity or request.target_entity,
            context_style=route.context_style,
            max_chars=self.config.max_context_chars,
            debug={"legacy_context": bundle.context, "debug_rows": bundle.debug_rows},
        )
