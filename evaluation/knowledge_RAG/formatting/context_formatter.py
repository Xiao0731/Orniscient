from __future__ import annotations

from typing import Iterable

from evaluation.knowledge_RAG.retrievers.base import RetrievalItem, RetrievalResult


def _clip(text: str, max_chars: int) -> str:
    text = str(text or "").strip()
    return text if len(text) <= max_chars else text[:max_chars].rstrip() + "..."


def format_context(
    *,
    knowledge_mode: str,
    route: str,
    target: str = "",
    items: Iterable[RetrievalItem],
    context_style: str = "compact",
    max_chars: int = 9000,
) -> str:
    grouped: dict[str, list[RetrievalItem]] = {}
    for item in items:
        grouped.setdefault(item.item_type, []).append(item)

    lines = [
        "[Knowledge Context]",
        f"Mode: {knowledge_mode}",
        f"Route: {route}",
    ]
    if target:
        lines.append(f"Target: {target}")

    sections = [
        ("fact", "[Facts]"),
        ("evidence", "[Evidence]"),
        ("chunk", "[Chunks]"),
        ("lightrag_doc", "[LightRAG Mix Results]"),
        ("table", "[Table Results]"),
        ("candidate", "[Candidate Species]"),
        ("taxonomy", "[Taxonomy]"),
    ]
    for item_type, title in sections:
        rows = grouped.get(item_type, [])
        if not rows:
            continue
        lines.extend(["", title])
        for idx, item in enumerate(rows, start=1):
            prefix = f"{idx}."
            score_bits = []
            if item.score:
                score_bits.append(f"score={item.score:.3f}")
            rerank_score = item.metadata.get("rerank_score")
            if rerank_score is not None:
                try:
                    score_bits.append(f"rerank={float(rerank_score):.3f}")
                except Exception:
                    pass
            suffix = f" ({'; '.join(score_bits)})" if score_bits else ""
            lines.append(f"{prefix} {_clip(item.text, 1200)}{suffix}")
            source_bits = [part for part in [item.source_chapter, item.source, item.chunk_id] if part]
            if source_bits:
                lines.append(f"   Source: {' | '.join(source_bits)}")

    rendered = "\n".join(lines).strip()
    if context_style == "deterministic_list":
        return _clip(rendered, max_chars)
    return _clip(rendered, max_chars)


def result_from_items(
    *,
    status: str,
    knowledge_mode: str,
    route: str,
    items: list[RetrievalItem],
    target: str = "",
    context_style: str = "compact",
    max_chars: int = 9000,
    debug: dict | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        status=status,
        knowledge_mode=knowledge_mode,
        route=route,
        items=items,
        rendered_context=format_context(
            knowledge_mode=knowledge_mode,
            route=route,
            target=target,
            items=items,
            context_style=context_style,
            max_chars=max_chars,
        ),
        debug=debug or {},
    )
