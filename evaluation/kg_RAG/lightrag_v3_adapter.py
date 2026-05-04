from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .embedding_adapter import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    validate_embedding_manifest,
)
from .reranker_adapter import RerankerAdapter


@dataclass
class KGContextItem:
    item_type: str
    text: str
    score: float = 0.0
    source: str = ""
    taxon_id: str = ""
    taxon_name: str = ""
    fact_id: str = ""
    evidence_id: str = ""
    chunk_id: str = ""
    source_chapter: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z0-9\-]{2,}", str(text or "").lower())


def _score_text(query: str, text: str) -> float:
    q = set(_tokenize(query))
    if not q:
        return 0.0
    tokens = _tokenize(text)
    return float(len(set(tokens) & q) + 0.02 * sum(1 for token in tokens if token in q))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


class LightRAGV3Adapter:
    def __init__(
        self,
        *,
        working_dir: str | Path = "kg_v2/outputs/lightrag_v3",
        embedding_provider: str = DEFAULT_EMBEDDING_PROVIDER,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
        reranker: RerankerAdapter | None = None,
        enable_reranker: bool = True,
        rebuild_vector_index: bool = False,
    ) -> None:
        self.working_dir = Path(working_dir)
        self.docs_path = self.working_dir / "docs.jsonl"
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model
        self.embedding_dim = int(embedding_dim)
        self.reranker = reranker
        self.enable_reranker = bool(enable_reranker)
        if self.working_dir.exists():
            validate_embedding_manifest(
                self.working_dir,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                embedding_dim=embedding_dim,
                index_name="bird_kg_v3_bge_m3",
                rebuild=rebuild_vector_index,
            )

    def _query_local_docs(self, query: str, top_k: int) -> list[KGContextItem]:
        rows = _load_jsonl(self.docs_path)
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            text = str(row.get("content") or row.get("text") or "")
            score = _score_text(query, text)
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        items: list[KGContextItem] = []
        for score, row in scored[: max(1, int(top_k))]:
            metadata = dict(row.get("metadata") or {})
            items.append(
                KGContextItem(
                    item_type="lightrag_doc",
                    text=str(row.get("content") or row.get("text") or "")[:3000],
                    score=score,
                    source=str(row.get("doc_id", "")),
                    taxon_id=str(metadata.get("taxon_id") or row.get("taxon_id") or ""),
                    taxon_name=str(metadata.get("scientific_name") or row.get("species_name") or ""),
                    source_chapter=", ".join(metadata.get("source_chapters", []) or []),
                    metadata={**metadata, "title": row.get("title", ""), "doc_id": row.get("doc_id", "")},
                )
            )
        return items

    def query(self, query: str, mode: str = "mix", top_k: int = 40) -> list[KGContextItem]:
        mode = mode or "mix"
        if mode != "mix":
            # LightRAG supports local/global/hybrid, but V3 defaults to mix with reranker.
            pass

        items = self._query_local_docs(query, top_k=top_k)
        if self.enable_reranker and self.reranker and self.reranker.enabled and items:
            docs = [
                {
                    "text": item.text,
                    "score": item.score,
                    "source": item.source,
                    "metadata": item.metadata,
                    "_item": item,
                }
                for item in items
            ]
            reranked = self.reranker.rerank(query, docs, text_key="text", top_n=min(len(docs), top_k))
            out: list[KGContextItem] = []
            for row in reranked:
                item = row.pop("_item")
                item.score = float(row.get("score", item.score))
                item.metadata.update(
                    {
                        "rerank_score": row.get("rerank_score"),
                        "rank_before": row.get("rank_before"),
                        "rank_after": row.get("rank_after"),
                        "reranker_model": row.get("reranker_model"),
                    }
                )
                out.append(item)
            return out
        return items
