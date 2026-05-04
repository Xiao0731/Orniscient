from __future__ import annotations

from typing import Any

try:
    from text_rag_runtime import (
        RetrievalResult,
        TextRAGCorpus,
        TextRAGResultBundle,
        normalize_name,
        tokenize,
    )
except ModuleNotFoundError:
    from evaluation.text_RAG.text_rag_runtime import (
        RetrievalResult,
        TextRAGCorpus,
        TextRAGResultBundle,
        normalize_name,
        tokenize,
    )


def _chapter_bonus(chunk, item: Any) -> tuple[float, list[str]]:
    labels = " ".join(
        [
            str(getattr(chunk, "chapter", "") or ""),
            str(getattr(chunk, "source_chapter_raw", "") or ""),
            str(getattr(chunk, "source_subchapter", "") or ""),
        ]
    ).lower()
    item_type = str(getattr(item, "type", "") or getattr(item, "type", "")).lower()
    score = 0.0
    matched: list[str] = []
    if "conservation" in labels:
        score += 28.0
        matched.append("chapter:conservation")
    if "introduction" in labels:
        score += 18.0
        matched.append("chapter:introduction")

    if "status" in item_type:
        for token in ["population", "demography", "status", "conservation", "trend"]:
            if token in labels:
                score += 6.0
                matched.append(f"type_hint:{token}")
    elif "threat" in item_type:
        for token in ["conservation", "habitat", "management", "human", "threat"]:
            if token in labels:
                score += 6.0
                matched.append(f"type_hint:{token}")
    elif "historical" in item_type or "extinction" in item_type:
        for token in ["conservation", "introduction", "distribution", "history", "extinct"]:
            if token in labels:
                score += 6.0
                matched.append(f"type_hint:{token}")
    return score, matched


def build_bird_con_context(
    corpus: TextRAGCorpus,
    item: Any,
    top_k: int = 8,
    max_context_chars: int = 9000,
) -> TextRAGResultBundle:
    target_entity = str(getattr(item, "target_entity", "") or "").strip()
    if not target_entity:
        return TextRAGResultBundle(
            context="",
            results=[],
            retrieval_policy="bird_con_target_conservation_routing",
            target_entity="",
            status="missing_target_entity",
            debug_rows=[],
        )

    target_chunks = corpus.exact_species_chunks(target_entity)
    if not target_chunks:
        return TextRAGResultBundle(
            context="",
            results=[],
            retrieval_policy="bird_con_target_conservation_routing",
            target_entity=target_entity,
            status="no_target_match",
            debug_rows=[],
        )

    q_text = "\n".join(
        [
            str(getattr(item, "question", "")).strip(),
            str(getattr(item, "knowledge_domain", "")).strip(),
            str(getattr(item, "type", "")).strip(),
        ]
    )
    q_tokens = tokenize(q_text)
    q_set = set(q_tokens)
    target_norms = {normalize_name(target_entity)}
    scored: list[RetrievalResult] = []

    for chunk in target_chunks:
        score, matched = corpus._score_by_text(chunk, q_tokens, q_set, target_norm="")  # type: ignore[attr-defined]
        if any(name in chunk.combined_entity_names for name in target_norms if name):
            score += 80.0
            matched.append("target_metadata_exact")
        chapter_score, chapter_matched = _chapter_bonus(chunk, item)
        score += chapter_score
        matched.extend(chapter_matched)
        if score > 0:
            scored.append(RetrievalResult(chunk=chunk, score=score, matched_on=matched))

    scored.sort(key=lambda result: (-result.score, result.chunk.chunk_id))
    selected = scored[:top_k]
    if not selected:
        return TextRAGResultBundle(
            context="",
            results=[],
            retrieval_policy="bird_con_target_conservation_routing",
            target_entity=target_entity,
            status="no_context",
            debug_rows=[],
        )

    context_body = corpus.format_context(selected, max_total_chars=max_context_chars, redact_identity=False)
    iucn_values = []
    seen_iucn = set()
    for result in selected:
        value = str(result.chunk.iucn_status or "").strip()
        if value and value not in seen_iucn:
            seen_iucn.add(value)
            iucn_values.append(value)
    preface_lines = [
        "Retrieved evidence from the external BOW text corpus (Text-RAG remaining-four variant).",
        "The evidence is target-aware and conservation-focused, prioritizing Conservation and Introduction sections for Bird-Con questions.",
        "Use it as open-book reference only when directly relevant.",
        "Retrieval policy: bird_con_target_conservation_routing.",
    ]
    if iucn_values:
        preface_lines.append(f"Structured conservation fact: IUCN status mentioned in retrieved evidence = {', '.join(iucn_values)}.")
    context = "\n".join(preface_lines) + "\n\n[Conservation-focused BOW Evidence]\n" + context_body
    debug_rows = []
    for rank, result in enumerate(selected, start=1):
        debug_rows.append(
            {
                "rank": rank,
                "chunk_id": result.chunk.chunk_id,
                "source_type": result.chunk.source_type,
                "common_name": result.chunk.common_name,
                "species": result.chunk.species,
                "family": result.chunk.family,
                "order": result.chunk.order,
                "source_chapter": result.chunk.chapter,
                "source_chapter_raw": result.chunk.source_chapter_raw,
                "source_subchapter": result.chunk.source_subchapter,
                "iucn_status": result.chunk.iucn_status,
                "matched_on": list(result.matched_on),
                "score": round(float(result.score), 4),
            }
        )
    return TextRAGResultBundle(
        context=context,
        results=selected,
        retrieval_policy="bird_con_target_conservation_routing",
        target_entity=target_entity,
        status="ok",
        debug_rows=debug_rows,
    )
