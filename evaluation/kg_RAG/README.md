# KG-RAG V3 Configuration

`evaluation/kg_RAG/` remains a compatibility entry point for KG/KB-enhanced evaluation. New experiments should prefer `evaluation/knowledge_RAG/`, which provides unified `knowledge_mode` naming and output manifests.

This directory is not deprecated and must not be archived automatically. It preserves old KG/KB logic, compatibility wrappers, V1 DIRECTED graph retrieval, V3 fact graph utilities, Table-KB retrieval, Bird-ID reverse retrieval, and family-table retrieval.

## Default Configuration

- LLM: `DEEPSEEK_MODEL=deepseek-chat` via `DEEPSEEK_API_KEY` and `DEEPSEEK_BASE_URL`.
- Embedding: `EMBEDDING_MODEL=BAAI/bge-m3`, `EMBEDDING_DIM=1024`.
- Reranker: `RERANKER_MODEL=BAAI/bge-reranker-v2-m3`.
- LightRAG query mode: `mix`, because reranked LightRAG retrieval works best when local/global graph signals are combined before compression.

No OpenAI API key is required by default. DeepSeek is used for chat/generation, answer generation, and judge calls. It is not used as an embedding model.

For API-compatible BGE retrieval, the local `.env` can point to SiliconFlow:

```env
EMBEDDING_PROVIDER=api_compatible
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=

RERANKER_PROVIDER=api_compatible
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_API_BASE=https://api.siliconflow.cn/v1
RERANKER_API_KEY=
```

Keep real keys only in `.env`; `.env.example` is a template and must not contain secrets.

## Backends

- `--kg-backend neo4j`: V3 fact/evidence graph retrieval. This is the controlled, explainable main path.
- `--kg-backend lightrag`: LightRAG mix retrieval over controlled V3 docs.
- `--kg-backend hybrid`: Neo4j fact/evidence retrieval plus LightRAG mix, followed by reranking.

Bird-ID uses no-gold reverse retrieval and reranking. List-Global should use deterministic BIRDBASE filtering; the LLM may explain but must not change the final set.

Historical scripts named `run_remaining_four_eval.py` or `kg_run_remaining_four_eval.py` are kept for reproducibility. The formal grouping for new runs is `objective`, `subjective`, and `structured`; `remaining_four` should not be used as a paper concept.

## Useful Commands

```powershell
python evaluation/knowledge_RAG/cli/run_objective.py --knowledge-mode kg_v3 --kg-backend neo4j --models deepseek --datasets QA-SC QA-MC QA-SA
```

```powershell
python evaluation/knowledge_RAG/cli/run_subjective.py --knowledge-mode hybrid --models deepseek glm --datasets Bird-Life Bird-Con Bird-Eco
```

```powershell
python evaluation/knowledge_RAG/cli/run_structured.py --knowledge-mode hybrid --datasets List-Global Bird-ID Bird-Classify
```

If `--kg-backend lightrag` or `hybrid` is selected, embeddings must be available. If reranker loading fails, the runtime logs:

```text
[WARN] Reranker unavailable; falling back to retrieval score only.
```
