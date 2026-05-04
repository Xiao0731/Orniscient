from __future__ import annotations

import importlib.util
import json
import os
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _suffix(value: str) -> str:
    return f"...{value[-4:]}" if value else "<missing>"


def _print(status: str, label: str, detail: str = "") -> None:
    print(f"[{status}] {label}{(': ' + detail) if detail else ''}")


def _exists(path: str, *, error: bool = False) -> bool:
    ok = (PROJECT_ROOT / path).exists()
    _print("OK" if ok else ("ERROR" if error else "WARN"), path, "exists" if ok else "missing")
    return ok


def _package(import_name: str, label: str | None = None, *, required: bool = False) -> bool:
    ok = importlib.util.find_spec(import_name) is not None
    _print("OK" if ok else ("ERROR" if required else "WARN"), label or import_name, "installed" if ok else "not installed")
    return ok


def _suggestions(results: dict[str, bool], env_values: dict[str, str]) -> list[str]:
    commands: list[str] = []
    if not results.get("lightrag_docs", True):
        commands.append(
            "python kg_v2/Step4_graph/export_lightrag_docs.py --graph-dir kg_v2/outputs/intermediate/truth_artifacts --out kg_v2/outputs/lightrag_v3/docs.jsonl"
        )
    if not results.get("lightrag_manifest", True):
        commands.append(
            "python kg_v2/Step4_graph/lightrag_ingest_v3.py --docs kg_v2/outputs/lightrag_v3/docs.jsonl --working-dir kg_v2/outputs/lightrag_v3 --embedding-model BAAI/bge-m3 --embedding-dim 1024 --llm-provider deepseek --llm-model deepseek-chat --query-mode mix --enable-reranker"
        )
    if not results.get("pytest", True):
        commands.append("python -m pip install pytest")
    if not results.get("neo4j", True):
        commands.append("python -m pip install neo4j")
    if not results.get("embedding_config", True):
        commands.append("Set EMBEDDING_API_BASE and EMBEDDING_API_KEY in .env")
    if not results.get("reranker_config", True):
        commands.append("Set RERANKER_API_BASE and RERANKER_API_KEY in .env")
    embedding_api_intent = env_values.get("EMBEDDING_PROVIDER", "").strip() == "api_compatible" or bool(env_values.get("EMBEDDING_API_KEY", "").strip())
    if not embedding_api_intent and not results.get("local_embedding", True):
        commands.append("python -m pip install sentence-transformers  # or: python -m pip install FlagEmbedding")
    return commands


def _check_embedding_api(env_values: dict[str, str]) -> bool:
    try:
        from evaluation.kg_RAG.embedding_adapter import EmbeddingAdapter, EmbeddingAdapterConfig

        adapter = EmbeddingAdapter(
            EmbeddingAdapterConfig(
                provider="api_compatible",
                model=env_values.get("EMBEDDING_MODEL", "BAAI/bge-m3"),
                dim=int(env_values.get("EMBEDDING_DIM", "1024")),
                api_base=env_values.get("EMBEDDING_API_BASE", ""),
                api_key=env_values.get("EMBEDDING_API_KEY", ""),
            )
        )
        vector = adapter.embed_query("short connectivity test")
        _print("OK", "embedding API connectivity", f"dim={len(vector)}")
        return True
    except Exception as exc:
        _print("ERROR", "embedding API connectivity", str(exc))
        return False


def _check_reranker_api(env_values: dict[str, str]) -> bool:
    try:
        from evaluation.kg_RAG.reranker_adapter import RerankerAdapter, RerankerAdapterConfig

        adapter = RerankerAdapter(
            RerankerAdapterConfig(
                provider="api_compatible",
                model=env_values.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
                api_base=env_values.get("RERANKER_API_BASE", ""),
                api_key=env_values.get("RERANKER_API_KEY", ""),
            )
        )
        rows = adapter.rerank("short bird query", [{"text": "short bird document", "score": 0.0}], top_n=1)
        ok = bool(rows and "rerank_score" in rows[0] and not adapter.last_fallback_reason)
        _print("OK" if ok else "ERROR", "reranker API connectivity", "returned score" if ok else f"fallback used: {adapter.last_fallback_reason}")
        return ok
    except Exception as exc:
        _print("ERROR", "reranker API connectivity", str(exc))
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose Knowledge-RAG environment.")
    parser.add_argument("--check-api", action="store_true", help="Actually call embedding/reranker APIs with one short request.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.chdir(PROJECT_ROOT)
    env_values = {**_load_env_file(PROJECT_ROOT / ".env.example"), **_load_env_file(PROJECT_ROOT / ".env")}
    print("[Knowledge-RAG Doctor]")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"CWD: {Path.cwd()}")
    print(f"Project root: {PROJECT_ROOT}")
    print("")

    results: dict[str, bool] = {}
    print("[Directories]")
    for path in [
        "question",
        "data",
        "evaluation/kg_RAG",
        "evaluation/text_RAG",
        "evaluation/knowledge_RAG",
        "kg_v2",
    ]:
        results[path] = _exists(path, error=True)

    print("\n[Key Files]")
    results["env"] = (PROJECT_ROOT / ".env").exists() or (PROJECT_ROOT / ".env.example").exists()
    _print("OK" if results["env"] else "ERROR", ".env or .env.example", "found" if results["env"] else "missing")
    for path in [
        "data/BIRDBASE.xlsx",
        "data/Order.xlsx",
        "kg_v2/outputs/intermediate/species_chunks.jsonl",
        "kg_v2/outputs/intermediate/family_chunks.jsonl",
    ]:
        results[path] = _exists(path)

    print("\n[Python Packages]")
    results["pandas"] = _package("pandas", required=True)
    results["openpyxl"] = _package("openpyxl", required=True)
    results["dotenv"] = _package("dotenv", "python-dotenv", required=True)
    results["neo4j"] = _package("neo4j", "neo4j (needed for kg_v3/hybrid graph retrieval)")
    embedding_provider = env_values.get("EMBEDDING_PROVIDER", "").strip()
    reranker_provider = env_values.get("RERANKER_PROVIDER", "").strip()
    embedding_api_intent = embedding_provider == "api_compatible" or bool(env_values.get("EMBEDDING_API_KEY", "").strip())
    reranker_api_intent = reranker_provider == "api_compatible" or bool(env_values.get("RERANKER_API_KEY", "").strip())
    if embedding_api_intent:
        base_ok = bool(env_values.get("EMBEDDING_API_BASE", "").strip())
        key_ok = bool(env_values.get("EMBEDDING_API_KEY", "").strip())
        results["embedding_config"] = base_ok and key_ok
        _print("OK" if results["embedding_config"] else "ERROR", "embedding api_compatible configured", f"base={env_values.get('EMBEDDING_API_BASE', '<missing>')} key={_suffix(env_values.get('EMBEDDING_API_KEY', ''))}")
        if embedding_provider != "api_compatible":
            _print("WARN", "EMBEDDING_PROVIDER", "API key/base detected; set EMBEDDING_PROVIDER=api_compatible to avoid local model checks.")
        results["local_embedding"] = True
    else:
        st = _package("sentence_transformers", "sentence_transformers (local embedding)")
        flag = _package("FlagEmbedding", "FlagEmbedding (local embedding/reranker)")
        results["local_embedding"] = st or flag
        results["embedding_config"] = results["local_embedding"]
    if reranker_api_intent:
        base_ok = bool(env_values.get("RERANKER_API_BASE", "").strip())
        key_ok = bool(env_values.get("RERANKER_API_KEY", "").strip())
        results["reranker_config"] = base_ok and key_ok
        _print("OK" if results["reranker_config"] else "ERROR", "reranker api_compatible configured", f"base={env_values.get('RERANKER_API_BASE', '<missing>')} key={_suffix(env_values.get('RERANKER_API_KEY', ''))}")
        if reranker_provider != "api_compatible":
            _print("WARN", "RERANKER_PROVIDER", "API key/base detected; set RERANKER_PROVIDER=api_compatible to avoid local model checks.")
    else:
        results["reranker_config"] = _package("FlagEmbedding", "FlagEmbedding (local reranker)")
    results["pytest"] = _package("pytest", "pytest (optional)")

    print("\n[.env Configuration]")
    deepseek_key = env_values.get("DEEPSEEK_API_KEY", "")
    _print("OK" if deepseek_key else "WARN", "DEEPSEEK_API_KEY", _suffix(deepseek_key))
    for key in [
        "DEEPSEEK_BASE_URL",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
        "EMBEDDING_DIM",
        "EMBEDDING_API_BASE",
        "RERANKER_PROVIDER",
        "RERANKER_MODEL",
        "RERANKER_API_BASE",
        "NEO4J_URI",
        "NEO4J_USERNAME",
        "NEO4J_DATABASE",
    ]:
        value = env_values.get(key, "")
        _print("OK" if value else "WARN", key, value or "<missing>")
    if env_values.get("EMBEDDING_API_KEY"):
        _print("OK", "EMBEDDING_API_KEY", _suffix(env_values.get("EMBEDDING_API_KEY", "")))
    if env_values.get("RERANKER_API_KEY"):
        _print("OK", "RERANKER_API_KEY", _suffix(env_values.get("RERANKER_API_KEY", "")))

    if args.check_api:
        print("\n[API Connectivity]")
        if embedding_api_intent:
            results["embedding_api"] = _check_embedding_api(env_values)
        else:
            _print("WARN", "embedding API connectivity", "skipped because EMBEDDING_PROVIDER is not api_compatible")
        if reranker_api_intent:
            results["reranker_api"] = _check_reranker_api(env_values)
        else:
            _print("WARN", "reranker API connectivity", "skipped because RERANKER_PROVIDER is not api_compatible")

    print("\n[LightRAG V3]")
    docs = PROJECT_ROOT / "kg_v2/outputs/lightrag_v3/docs.jsonl"
    manifest = PROJECT_ROOT / "kg_v2/outputs/lightrag_v3/embedding_manifest.json"
    results["lightrag_docs"] = docs.exists()
    results["lightrag_manifest"] = manifest.exists()
    _print("OK" if docs.exists() else "WARN", str(docs.relative_to(PROJECT_ROOT)), "exists" if docs.exists() else "missing")
    if manifest.exists():
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            _print("OK", str(manifest.relative_to(PROJECT_ROOT)), f"{payload.get('embedding_model')} dim={payload.get('embedding_dim')}")
        except Exception as exc:
            _print("ERROR", str(manifest.relative_to(PROJECT_ROOT)), str(exc))
            results["lightrag_manifest"] = False
    else:
        _print("WARN", str(manifest.relative_to(PROJECT_ROOT)), "missing")

    suggestions = _suggestions(results, env_values)
    if suggestions:
        print("\n[Next Commands]")
        for cmd in suggestions:
            print(f"- {cmd}")
    error_count = sum(1 for key in ["question", "data", "evaluation/kg_RAG", "evaluation/text_RAG", "evaluation/knowledge_RAG", "kg_v2"] if not results.get(key))
    print(f"\n[SUMMARY] errors={error_count} warnings={sum(1 for ok in results.values() if not ok) - error_count}")
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
