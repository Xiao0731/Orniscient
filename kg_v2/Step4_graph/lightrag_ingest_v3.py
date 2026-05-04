from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.kg_RAG.embedding_adapter import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    validate_embedding_manifest,
)


DEFAULT_WORKING_DIR = ROOT / "kg_v2" / "outputs" / "lightrag_v3"


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


async def _try_real_lightrag_ingest(docs: list[dict], working_dir: Path) -> dict | None:
    try:
        from kg_v2.rag.lightrag_ingest import ingest_controlled_docs_async
    except Exception:
        return None
    temp_docs = working_dir / "docs_for_ingest.jsonl"
    _write_jsonl(temp_docs, [{"doc_id": row["doc_id"], "content": row["content"]} for row in docs])
    try:
        return await ingest_controlled_docs_async(
            docs_path=temp_docs,
            working_dir=str(working_dir),
            processed_log=working_dir / "logs" / "processed_lightrag_v3_docs.log",
        )
    except Exception as exc:
        return {"status": "fallback_local_docs", "reason": str(exc)}


def ingest_lightrag_v3(
    *,
    docs_path: str | Path,
    working_dir: str | Path = DEFAULT_WORKING_DIR,
    embedding_provider: str = DEFAULT_EMBEDDING_PROVIDER,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
    llm_provider: str = "deepseek",
    llm_model: str = "deepseek-chat",
    query_mode: str = "mix",
    enable_reranker: bool = True,
    rebuild: bool = False,
) -> dict:
    if "reasoner" in llm_model.lower() or "reasoning" in llm_model.lower():
        raise RuntimeError("LightRAG indexing should use a chat model, not a reasoning model.")

    work = Path(working_dir)
    work.mkdir(parents=True, exist_ok=True)
    (work / "logs").mkdir(parents=True, exist_ok=True)
    docs = _load_jsonl(Path(docs_path))
    validate_embedding_manifest(
        work,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dim=embedding_dim,
        index_name="bird_kg_v3_bge_m3",
        rebuild=rebuild,
    )

    os.environ.setdefault("KG_LLM_MODEL", llm_model)
    if llm_provider == "deepseek":
        os.environ.setdefault("OPENAI_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
        os.environ.setdefault("OPENAI_BASE_URL", os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    os.environ["LIGHTRAG_QUERY_MODE"] = query_mode
    os.environ["LIGHTRAG_ENABLE_RERANKER"] = "true" if enable_reranker else "false"
    os.environ["EMBEDDING_MODEL"] = embedding_model
    os.environ["EMBEDDING_DIM"] = str(embedding_dim)

    # Keep a local copy so query/eval can still work if LightRAG runtime/storage is unavailable.
    _write_jsonl(work / "docs.jsonl", docs)
    ingest_result = asyncio.run(_try_real_lightrag_ingest(docs, work))
    summary = {
        "status": "ok",
        "docs_path": str(docs_path),
        "working_dir": str(work),
        "doc_count": len(docs),
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "embedding_dim": int(embedding_dim),
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "query_mode": query_mode,
        "enable_reranker": enable_reranker,
        "lightrag_ingest": ingest_result or {"status": "local_docs_only"},
    }
    (work / "logs" / "lightrag_v3_ingest_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest V3 controlled docs into LightRAG working directory.")
    parser.add_argument("--docs", type=str, required=True)
    parser.add_argument("--working-dir", type=str, default=str(DEFAULT_WORKING_DIR))
    parser.add_argument("--embedding-provider", type=str, default=DEFAULT_EMBEDDING_PROVIDER)
    parser.add_argument("--embedding-model", type=str, default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--embedding-dim", type=int, default=DEFAULT_EMBEDDING_DIM)
    parser.add_argument("--llm-provider", type=str, default="deepseek")
    parser.add_argument("--llm-model", type=str, default=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))
    parser.add_argument("--query-mode", type=str, default="mix")
    parser.add_argument("--enable-reranker", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = ingest_lightrag_v3(
        docs_path=args.docs,
        working_dir=args.working_dir,
        embedding_provider=args.embedding_provider,
        embedding_model=args.embedding_model,
        embedding_dim=args.embedding_dim,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        query_mode=args.query_mode,
        enable_reranker=args.enable_reranker,
        rebuild=args.rebuild,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
