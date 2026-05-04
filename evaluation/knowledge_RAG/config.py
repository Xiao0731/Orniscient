from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if load_dotenv and env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def key_suffix(value: str) -> str:
    return f"...{value[-4:]}" if value else "<empty>"


@dataclass(frozen=True)
class KnowledgeRAGConfig:
    knowledge_mode: str = "kg_v3"
    kg_backend: str = "hybrid"
    kg_version: str = "v3_fact_graph"
    retrieval_backend: str = "hybrid"
    query_mode: str = "mix"
    embedding_provider: str = "bge_m3"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    reranker_provider: str = "bge_reranker"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    enable_reranker: bool = True
    reranker_top_n: int = 12
    lightrag_working_dir: str = "kg_v2/outputs/lightrag_v3"
    rebuild_vector_index: bool = False
    neo4j_uri: str = "bolt://127.0.0.1:7688"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"
    text_top_k: int = 5
    kg_top_k: int = 30
    lightrag_top_k: int = 40
    max_context_chars: int = 9000
    birdbase_xlsx: str = "data/BIRDBASE.xlsx"
    order_xlsx: str = "data/Order.xlsx"
    list_global_direct_output: bool = True

    @classmethod
    def from_env(cls, **overrides) -> "KnowledgeRAGConfig":
        load_env()
        values = {
            "embedding_provider": env("EMBEDDING_PROVIDER", "bge_m3"),
            "embedding_model": env("EMBEDDING_MODEL", "BAAI/bge-m3"),
            "embedding_dim": int(env("EMBEDDING_DIM", "1024")),
            "reranker_provider": env("RERANKER_PROVIDER", "bge_reranker"),
            "reranker_model": env("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
            "reranker_top_n": int(env("RERANKER_TOP_N", "20")),
            "lightrag_working_dir": env("LIGHTRAG_WORKING_DIR", "kg_v2/outputs/lightrag_v3"),
            "query_mode": env("LIGHTRAG_QUERY_MODE", "mix"),
            "enable_reranker": env("LIGHTRAG_ENABLE_RERANKER", "true").lower() not in {"0", "false", "no"},
            "lightrag_top_k": int(env("LIGHTRAG_TOP_K", "40")),
            "neo4j_uri": env("NEO4J_URI", "bolt://127.0.0.1:7688"),
            "neo4j_username": env("NEO4J_USERNAME", "neo4j"),
            "neo4j_password": env("NEO4J_PASSWORD", ""),
            "neo4j_database": env("NEO4J_DATABASE", "neo4j"),
        }
        values.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**values)

    def validate(self) -> None:
        if self.knowledge_mode in {"kg_v3", "hybrid"} and self.kg_backend in {"lightrag", "hybrid"}:
            if self.embedding_provider == "disabled":
                raise RuntimeError("LightRAG/hybrid backend requires embedding; EMBEDDING_PROVIDER=disabled is not allowed.")
            missing = []
            if not self.embedding_model:
                missing.append("EMBEDDING_MODEL")
            if not self.neo4j_password and self.kg_backend in {"neo4j", "hybrid"}:
                missing.append("NEO4J_PASSWORD")
            if missing:
                raise RuntimeError("Missing .env or missing required key: " + " / ".join(missing))
