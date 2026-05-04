"""LightRAG ingest for V2.1 controlled docs using the existing V1 runtime."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.schema.ontology_v2 import INTERMEDIATE_DIR, LOGS_DIR, load_jsonl


def _load_v1_runtime_helpers():
    from test_LightRAG import INSERT_FLUSH_SIZE, build_lightrag_runtime, ingest_named_docs

    return INSERT_FLUSH_SIZE, build_lightrag_runtime, ingest_named_docs


async def ingest_controlled_docs_async(
    docs_path=INTERMEDIATE_DIR / "controlled_docs.jsonl",
    *,
    working_dir: str = "./bird_graph_storage",
    processed_log: Path | None = LOGS_DIR / "processed_controlled_docs.log",
    flush_size: int | None = None,
) -> dict:
    INSERT_FLUSH_SIZE, build_lightrag_runtime, ingest_named_docs = _load_v1_runtime_helpers()
    effective_flush_size = flush_size or INSERT_FLUSH_SIZE
    rag = build_lightrag_runtime(working_dir=working_dir)
    docs = load_jsonl(docs_path)
    named_docs = [(row["doc_id"], row["content"]) for row in docs if row.get("content")]

    await rag.initialize_storages()
    try:
        result = await ingest_named_docs(
            rag,
            named_docs,
            processed_log=processed_log,
            flush_size=effective_flush_size,
        )
    finally:
        try:
            await rag.finalize_storages()
        except Exception:
            pass
    return {
        "docs_path": str(docs_path),
        "doc_count": len(named_docs),
        "ingest_result": result,
        "working_dir": working_dir,
    }


def ingest_controlled_docs(
    docs_path=INTERMEDIATE_DIR / "controlled_docs.jsonl",
    *,
    working_dir: str = "./bird_graph_storage",
    processed_log: Path | None = LOGS_DIR / "processed_controlled_docs.log",
    flush_size: int | None = None,
) -> dict:
    return asyncio.run(
        ingest_controlled_docs_async(
            docs_path=docs_path,
            working_dir=working_dir,
            processed_log=processed_log,
            flush_size=flush_size,
        )
    )


if __name__ == "__main__":
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    result = ingest_controlled_docs()
    (LOGS_DIR / "lightrag_ingest_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
