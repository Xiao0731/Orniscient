from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from text_rag_runtime import RetrievalChunk, RetrievalResult, TextRAGCorpus, TextRAGResultBundle, build_family_chunks_from_order_xlsx, normalize_name, tokenize
except ModuleNotFoundError:
    from evaluation.text_RAG.text_rag_runtime import RetrievalChunk, RetrievalResult, TextRAGCorpus, TextRAGResultBundle, build_family_chunks_from_order_xlsx, normalize_name, tokenize


def _family_scored_results(corpus: TextRAGCorpus, query_text: str, top_k: int) -> list[RetrievalResult]:
    return corpus.retrieve_blind(query_text=query_text, dataset="Bird-Classify", source_type="family", top_k=top_k)


def _score_order_fallback_chunks(query_text: str, chunks: list[RetrievalChunk], top_k: int) -> list[RetrievalResult]:
    temp_corpus = TextRAGCorpus(chunks, top_k=top_k, max_chars_per_chunk=1200, default_restrict_to_target=False)
    return temp_corpus.retrieve_blind(query_text=query_text, dataset="Bird-Classify", source_type="family", top_k=top_k)


def _exact_named_family_chunks(corpus: TextRAGCorpus, family: str, order: str, target: str):
    family_norm = normalize_name(family)
    order_norm = normalize_name(order)
    chunks = [chunk for chunk in corpus.chunks if chunk.source_type == "family"]
    if family_norm:
        matched = [chunk for chunk in chunks if normalize_name(chunk.family) == family_norm]
        if matched:
            return matched
    if order_norm:
        matched = [chunk for chunk in chunks if normalize_name(chunk.order) == order_norm]
        if matched:
            return matched
    return corpus.exact_family_chunks(target, family=family, order=order)


def _format_family_candidates(grouped_rows: list[dict[str, Any]]) -> str:
    lines = [
        "[Candidate family evidence]",
    ]
    for idx, row in enumerate(grouped_rows, start=1):
        lines.append(f"{idx}. Order: {row['order'] or 'NA'}")
        lines.append(f"   Family: {row['family'] or 'NA'}")
        for evidence in row["evidence"]:
            lines.append(f"   Evidence: {evidence}")
    return "\n".join(lines)


def build_feature_to_family_candidates(
    corpus: TextRAGCorpus,
    item: dict[str, Any],
    order_xlsx: str = "",
    top_k: int = 10,
) -> dict[str, Any]:
    query_text = "\n".join(
        [
            str(item.get("question", "")).strip(),
            str(item.get("type", "")).strip(),
            str(item.get("knowledge_domain", "")).strip(),
        ]
    )
    raw_results = _family_scored_results(corpus, query_text, top_k=top_k * 4)
    fallback_used = False
    if len(raw_results) < max(3, top_k // 2) and order_xlsx and Path(order_xlsx).exists():
        fallback_chunks = build_family_chunks_from_order_xlsx(order_xlsx, chunk_chars=1400, chunk_overlap=180)
        raw_results.extend(_score_order_fallback_chunks(query_text, fallback_chunks, top_k=top_k * 2))
        fallback_used = True
    grouped: dict[tuple[str, str], list[RetrievalResult]] = defaultdict(list)
    for result in raw_results:
        key = (str(result.chunk.order or "").strip(), str(result.chunk.family or "").strip())
        grouped[key].append(result)

    candidate_rows: list[dict[str, Any]] = []
    for (order_name, family_name), results in grouped.items():
        results.sort(key=lambda r: (-r.score, r.chunk.chunk_id))
        candidate_rows.append(
            {
                "order": order_name,
                "family": family_name,
                "score": round(sum(result.score for result in results[:3]), 4),
                "evidence": [result.chunk.text[:260].replace("\n", " ").strip() for result in results[:2]],
                "chunks": results[:3],
            }
        )
    candidate_rows.sort(key=lambda row: (-row["score"], row["order"], row["family"]))
    candidate_rows = candidate_rows[:top_k]
    gold_family = str(item.get("family", "")).strip()
    gold_family_norm = normalize_name(gold_family)
    gold_in_candidates = any(normalize_name(row["family"]) == gold_family_norm for row in candidate_rows if gold_family_norm)

    context = _format_family_candidates(candidate_rows) if candidate_rows else ""
    return {
        "context": context,
        "candidate_families": [
            {
                "order": row["order"],
                "family": row["family"],
                "score": row["score"],
                "is_gold_family": int(bool(gold_family_norm) and normalize_name(row["family"]) == gold_family_norm),
            }
            for row in candidate_rows
        ],
        "retrieved_chunk_ids": [chunk.chunk.chunk_id for row in candidate_rows for chunk in row["chunks"]],
        "retrieved_debug": [
            {
                "order": row["order"],
                "family": row["family"],
                "score": row["score"],
                "evidence": row["evidence"],
                "chunk_ids": [chunk.chunk.chunk_id for chunk in row["chunks"]],
                "is_gold_family": int(bool(gold_family_norm) and normalize_name(row["family"]) == gold_family_norm),
            }
            for row in candidate_rows
        ],
        "retrieval_policy": "feature_to_family_candidate_retrieval",
        "retrieved_context_status": "ok" if candidate_rows else "no_context",
        "gold_family_in_candidates": int(gold_in_candidates),
        "order_xlsx_fallback_used": int(fallback_used),
    }


def _score_exact_family_chunks(
    corpus: TextRAGCorpus,
    chunks,
    query_text: str,
    item: Any,
    top_k: int,
    systematics_priority: bool,
) -> list[RetrievalResult]:
    q_tokens = tokenize(query_text)
    q_set = set(q_tokens)
    family = str(getattr(item, "family", "") or item.get("family", "")).strip() if isinstance(item, dict) else str(getattr(item, "family", "")).strip()
    order = str(getattr(item, "order", "") or item.get("order", "")).strip() if isinstance(item, dict) else str(getattr(item, "order", "")).strip()
    target_norms = {normalize_name(value) for value in [family, order] if value}
    scored: list[RetrievalResult] = []
    for chunk in chunks:
        score, matched = corpus._score_by_text(chunk, q_tokens, q_set, target_norm="")  # type: ignore[attr-defined]
        if any(name in chunk.combined_entity_names for name in target_norms if name):
            score += 80.0
            matched.append("family_or_order_exact")
        labels = " ".join([chunk.chapter, chunk.source_chapter_raw, chunk.source_subchapter]).lower()
        if "introduction" in labels:
            score += 18.0
            matched.append("chapter:introduction")
        if systematics_priority and ("systematic" in labels or "history" in labels):
            score += 28.0
            matched.append("chapter:systematics")
        elif not systematics_priority and ("habitat" in labels or "diet" in labels or "breeding" in labels):
            score += 12.0
            matched.append("chapter:feature_context")
        if score > 0:
            scored.append(RetrievalResult(chunk=chunk, score=score, matched_on=matched))
    scored.sort(key=lambda r: (-r.score, r.chunk.chunk_id))
    return scored[:top_k]


def _bundle_from_family_results(
    corpus: TextRAGCorpus,
    item: Any,
    results: list[RetrievalResult],
    retrieval_policy: str,
    preface: str,
    max_context_chars: int,
) -> TextRAGResultBundle:
    if not results:
        target_entity = str(getattr(item, "target_entity", "") or item.get("target_entity", "")).strip() if isinstance(item, dict) else str(getattr(item, "target_entity", "")).strip()
        return TextRAGResultBundle(
            context="",
            results=[],
            retrieval_policy=retrieval_policy,
            target_entity=target_entity,
            status="no_context",
            debug_rows=[],
        )
    context_body = corpus.format_context(results, max_total_chars=max_context_chars, redact_identity=False)
    context = preface + "\n\n" + context_body
    debug_rows = []
    for rank, result in enumerate(results, start=1):
        debug_rows.append(
            {
                "rank": rank,
                "chunk_id": result.chunk.chunk_id,
                "family": result.chunk.family,
                "order": result.chunk.order,
                "source_chapter": result.chunk.chapter,
                "source_chapter_raw": result.chunk.source_chapter_raw,
                "source_subchapter": result.chunk.source_subchapter,
                "matched_on": list(result.matched_on),
                "score": round(float(result.score), 4),
            }
        )
    target_entity = str(getattr(item, "target_entity", "") or item.get("target_entity", "")).strip() if isinstance(item, dict) else str(getattr(item, "target_entity", "")).strip()
    return TextRAGResultBundle(
        context=context,
        results=results,
        retrieval_policy=retrieval_policy,
        target_entity=target_entity,
        status="ok",
        debug_rows=debug_rows,
    )


def build_taxon_to_feature_context(corpus: TextRAGCorpus, item: Any, top_k: int = 6, max_context_chars: int = 9000) -> TextRAGResultBundle:
    family = str(getattr(item, "family", "") or item.get("family", "")).strip() if isinstance(item, dict) else str(getattr(item, "family", "")).strip()
    order = str(getattr(item, "order", "") or item.get("order", "")).strip() if isinstance(item, dict) else str(getattr(item, "order", "")).strip()
    target = str(getattr(item, "target_entity", "") or item.get("target_entity", "")).strip() if isinstance(item, dict) else str(getattr(item, "target_entity", "")).strip()
    chunks = _exact_named_family_chunks(corpus, family, order, target)
    query_text = "\n".join([str(getattr(item, "question", "") or item.get("question", "")).strip(), str(getattr(item, "type", "") or item.get("type", "")).strip()])
    results = _score_exact_family_chunks(corpus, chunks, query_text, item, top_k, systematics_priority=False)
    preface = (
        "Retrieved evidence from family-level BOW chunks.\n"
        "This Bird-Classify item already exposes the taxon in the question, so family and order names are not redacted.\n"
        "Focus on morphology, ecology, systematics, and life-history traits when relevant."
    )
    return _bundle_from_family_results(corpus, item, results, "taxon_to_feature_family_exact_retrieval", preface, max_context_chars)


def build_taxonomic_hierarchy_context(corpus: TextRAGCorpus, item: Any, top_k: int = 6, max_context_chars: int = 9000) -> TextRAGResultBundle:
    family = str(getattr(item, "family", "") or item.get("family", "")).strip() if isinstance(item, dict) else str(getattr(item, "family", "")).strip()
    order = str(getattr(item, "order", "") or item.get("order", "")).strip() if isinstance(item, dict) else str(getattr(item, "order", "")).strip()
    target = str(getattr(item, "target_entity", "") or item.get("target_entity", "")).strip() if isinstance(item, dict) else str(getattr(item, "target_entity", "")).strip()
    chunks = _exact_named_family_chunks(corpus, family, order, target)
    query_text = "\n".join([str(getattr(item, "question", "") or item.get("question", "")).strip(), str(getattr(item, "type", "") or item.get("type", "")).strip()])
    results = _score_exact_family_chunks(corpus, chunks, query_text, item, top_k, systematics_priority=True)
    preface = (
        "Retrieved evidence from family-level BOW chunks.\n"
        "This is a taxonomic hierarchy question. Focus on the order-family relationship and supporting diagnostic traits if requested."
    )
    return _bundle_from_family_results(corpus, item, results, "taxonomic_hierarchy_family_exact_retrieval", preface, max_context_chars)
