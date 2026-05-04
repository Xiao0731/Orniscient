from __future__ import annotations

import re

from evaluation.kg_RAG.reranker_adapter import RerankerAdapter, RerankerConfigError
from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.formatting.context_formatter import result_from_items
from evaluation.knowledge_RAG.retrievers.base import RetrievalItem, RetrievalRequest, RetrievalResult


def build_bird_id_safe_query(item: dict, question: str) -> str:
    return "\n".join(
        part
        for part in [
            str(question or "").strip(),
            str(item.get("clue_text", "") or "").strip(),
            str(item.get("description", "") or "").strip(),
        ]
        if part
    )


def assert_no_gold_leak(prompt: str, gold_answer: object) -> None:
    if not gold_answer:
        return
    gold_values: list[str]
    if isinstance(gold_answer, (list, tuple, set)):
        gold_values = [str(v) for v in gold_answer]
    else:
        gold_values = [str(gold_answer)]
    lowered = prompt.lower()
    for gold in gold_values:
        gold = re.sub(r"\s+", " ", gold or "").strip().lower()
        if gold and gold in lowered:
            raise AssertionError("Bird-ID prompt contains gold answer; aborting to prevent leakage.")


class BirdIDReverseRetriever:
    def __init__(self, config: KnowledgeRAGConfig) -> None:
        self.config = config
        self.reranker = None
        if config.enable_reranker:
            try:
                self.reranker = RerankerAdapter(provider=config.reranker_provider, model=config.reranker_model)
            except RerankerConfigError:
                print("[WARN] Reranker unavailable; falling back to retrieval score only.")

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        from evaluation.kg_RAG.bird_id_reverse_retriever import retrieve_bird_id_candidates

        query = build_bird_id_safe_query(request.raw_item, request.question)
        context = retrieve_bird_id_candidates(
            question=request.question,
            clue_text=str(request.raw_item.get("clue_text", "") or ""),
            top_k=80,
            evidence_per_species=3,
            kg_uri=self.config.neo4j_uri,
            kg_user=self.config.neo4j_username,
            kg_password=self.config.neo4j_password,
        )
        candidates = self._parse_candidates(context)
        initial_count = len(candidates)
        if self.reranker and self.reranker.enabled and candidates:
            docs = [
                {"text": item.text[:1000], "score": item.score, "species": item.taxon_name, "_item": item}
                for item in candidates
            ]
            ranked = self.reranker.rerank(query, docs, text_key="text", top_n=30)
            candidates = []
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
                candidates.append(item)
        else:
            candidates = candidates[:30]
        return result_from_items(
            status="ok" if candidates else "empty",
            knowledge_mode=self.config.knowledge_mode,
            route="bird_id_reverse_rerank",
            items=candidates,
            context_style="candidate_list",
            max_chars=self.config.max_context_chars,
            debug={
                "initial_retrieval_count": initial_count,
                "reranked_count": len(candidates),
                "gold_used": False,
            },
        )

    def _parse_candidates(self, context: str) -> list[RetrievalItem]:
        if not context or context.startswith("[NO_"):
            return []
        blocks = re.split(r"\n(?=\d+\.\s+Species:)", context)
        items: list[RetrievalItem] = []
        for rank, block in enumerate(blocks, start=1):
            match = re.search(r"Species:\s*(.+)", block)
            if not match:
                continue
            species = match.group(1).strip()
            items.append(
                RetrievalItem(
                    item_type="candidate",
                    text=block.strip(),
                    score=max(0.0, 100.0 - rank),
                    taxon_name=species,
                    metadata={"stage": "broad_candidate_retrieval", "rank_before": rank},
                )
            )
        return items

