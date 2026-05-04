from __future__ import annotations

import json
import math
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore


DEFAULT_RERANKER_PROVIDER = "bge_reranker"
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"


class RerankerConfigError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_repo_env() -> None:
    env_path = _repo_root() / ".env"
    if load_dotenv and env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z0-9\-]{2,}", str(text or "").lower())


def _clip_document_text(text: str, max_chars: int = 1000) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:max_chars].rstrip()


@dataclass(frozen=True)
class RerankerAdapterConfig:
    provider: str = DEFAULT_RERANKER_PROVIDER
    model: str = DEFAULT_RERANKER_MODEL
    api_base: str = ""
    api_key: str = ""
    device: str = "auto"
    batch_size: int = 8
    top_n: int = 20
    normalize: bool = True

    @classmethod
    def from_env(cls, *, provider: str | None = None, model: str | None = None) -> "RerankerAdapterConfig":
        load_repo_env()
        return cls(
            provider=provider or _env("RERANKER_PROVIDER", DEFAULT_RERANKER_PROVIDER),
            model=model or _env("RERANKER_MODEL", DEFAULT_RERANKER_MODEL),
            api_base=_env("RERANKER_API_BASE"),
            api_key=_env("RERANKER_API_KEY"),
            device=_env("RERANKER_DEVICE", "auto"),
            batch_size=int(_env("RERANKER_BATCH_SIZE", "8")),
            top_n=int(_env("RERANKER_TOP_N", "20")),
            normalize=_env("RERANKER_NORMALIZE", "true").lower() not in {"0", "false", "no"},
        )


class RerankerAdapter:
    def __init__(self, config: RerankerAdapterConfig | None = None, **overrides: Any) -> None:
        if config is None:
            config = RerankerAdapterConfig.from_env(
                provider=overrides.pop("provider", None),
                model=overrides.pop("model", None),
            )
        self.config = config
        self.provider = self._normalize_provider(config.provider)
        self.model_name = config.model
        self._model: Any = None
        self._local_backend_unavailable = False
        self.last_fallback_reason: str = ""
        if self.provider == "api_compatible" and (not config.api_base or not config.api_key):
            raise RerankerConfigError(
                "Missing .env or missing required key: RERANKER_API_BASE / RERANKER_API_KEY"
            )

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        provider = (provider or DEFAULT_RERANKER_PROVIDER).strip()
        if provider in {"bge_reranker", "local_bge_reranker"}:
            return "local_bge_reranker"
        if provider in {"api", "api_compatible"}:
            return "api_compatible"
        if provider == "disabled":
            return "disabled"
        raise RerankerConfigError(f"Unsupported reranker provider: {provider}")

    @property
    def enabled(self) -> bool:
        return self.provider != "disabled"

    @property
    def available(self) -> bool:
        return self.provider != "disabled" and not self._local_backend_unavailable

    def _load_local_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from FlagEmbedding import FlagReranker

            kwargs = {"use_fp16": False}
            if self.config.device and self.config.device != "auto":
                kwargs["device"] = self.config.device
            self._model = FlagReranker(self.model_name, **kwargs)
            return self._model
        except Exception:
            self._local_backend_unavailable = True
            return None

    def _normalize_score(self, score: float) -> float:
        if not self.config.normalize:
            return float(score)
        return float(1.0 / (1.0 + math.exp(-float(score))))

    def _lexical_scores(self, query: str, documents: list[dict[str, Any]], text_key: str) -> list[float]:
        query_tokens = set(_tokenize(query))
        scores: list[float] = []
        for doc in documents:
            doc_tokens = _tokenize(_clip_document_text(str(doc.get(text_key, ""))))
            if not doc_tokens or not query_tokens:
                scores.append(float(doc.get("score", doc.get("retrieval_score", 0.0)) or 0.0))
                continue
            overlap = sum(1 for token in doc_tokens if token in query_tokens)
            unique_overlap = len(set(doc_tokens) & query_tokens)
            scores.append(unique_overlap + 0.05 * overlap + float(doc.get("score", doc.get("retrieval_score", 0.0)) or 0.0))
        return scores

    def _local_scores(self, query: str, documents: list[dict[str, Any]], text_key: str) -> list[float]:
        model = self._load_local_model()
        if model is None:
            self.last_fallback_reason = "local FlagEmbedding reranker is unavailable"
            print("[WARN] Reranker unavailable; falling back to lexical/retrieval score only.", file=sys.stderr)
            return self._lexical_scores(query, documents, text_key)
        pairs = [[query, _clip_document_text(str(doc.get(text_key, "")))] for doc in documents]
        scores = model.compute_score(pairs, batch_size=self.config.batch_size)
        if isinstance(scores, (int, float)):
            scores = [scores]
        return [self._normalize_score(float(score)) for score in scores]

    def _api_scores(self, query: str, documents: list[dict[str, Any]], text_key: str) -> list[float]:
        base = self.config.api_base.rstrip("/")
        url = base if base.endswith("/rerank") or base.endswith("/rerankings") else f"{base}/rerank"
        payload = json.dumps(
            {
                "model": self.model_name,
                "query": query,
                "documents": [_clip_document_text(str(doc.get(text_key, ""))) for doc in documents],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
        if "results" in data:
            score_by_index = {int(row.get("index", idx)): float(row.get("relevance_score", row.get("score", 0.0))) for idx, row in enumerate(data["results"])}
            return [self._normalize_score(score_by_index.get(idx, 0.0)) for idx in range(len(documents))]
        if "scores" in data:
            return [self._normalize_score(float(score)) for score in data["scores"]]
        raise RerankerConfigError("Reranker API response must include results or scores.")

    def rerank(
        self,
        query: str,
        documents: list[dict],
        text_key: str = "text",
        top_n: int = 20,
    ) -> list[dict]:
        if not documents:
            return []

        base_docs: list[dict[str, Any]] = []
        for index, doc in enumerate(documents, start=1):
            row = dict(doc)
            row.setdefault("rank_before", index)
            base_docs.append(row)

        if self.provider == "disabled":
            sorted_docs = sorted(
                base_docs,
                key=lambda row: float(row.get("score", row.get("retrieval_score", 0.0)) or 0.0),
                reverse=True,
            )
            for index, row in enumerate(sorted_docs, start=1):
                row["rank_after"] = index
            return sorted_docs[: max(1, int(top_n))]

        try:
            scores = (
                self._api_scores(query, base_docs, text_key)
                if self.provider == "api_compatible"
                else self._local_scores(query, base_docs, text_key)
            )
        except Exception as exc:
            self.last_fallback_reason = str(exc)
            print(
                f"[WARN] Reranker unavailable; falling back to lexical/retrieval score only. reason={exc}",
                file=sys.stderr,
            )
            scores = self._lexical_scores(query, base_docs, text_key)
        for row, score in zip(base_docs, scores):
            row["rerank_score"] = float(score)
            row["reranker_model"] = self.model_name

        sorted_docs = sorted(
            base_docs,
            key=lambda row: (
                float(row.get("rerank_score", 0.0) or 0.0),
                float(row.get("score", row.get("retrieval_score", 0.0)) or 0.0),
            ),
            reverse=True,
        )
        for index, row in enumerate(sorted_docs, start=1):
            row["rank_after"] = index
        return sorted_docs[: max(1, int(top_n or self.config.top_n))]
