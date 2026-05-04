# V3 LightRAG Graph Export And Ingest

Step4 exports controlled V3 Fact/Evidence documents for LightRAG. Do not ingest all raw BOW chunks directly; use compact docs grouped by `taxon_id::fact_domain`.

## Roles

- DeepSeek is the default LLM for generation/extraction/indexing text. Use `deepseek-chat` for LightRAG indexing, not a reasoning model.
- Embedding defaults to `BAAI/bge-m3` with dimension `1024`. In the API-compatible setup, SiliconFlow serves this model via `EMBEDDING_API_BASE=https://api.siliconflow.cn/v1`.
- Reranker defaults to `BAAI/bge-reranker-v2-m3`. In the API-compatible setup, SiliconFlow serves this model via `RERANKER_API_BASE=https://api.siliconflow.cn/v1`.

OpenAI is not required by default. DeepSeek handles LLM generation; SiliconFlow BGE handles embedding and reranking when configured in `.env`.

## Why Fix The Embedding

Vector indexes are only valid for the embedding model and dimension that created them. If you switch from `BAAI/bge-m3` to another model, delete the old vector index or run with `--rebuild`; otherwise query vectors and stored vectors are not comparable.

## Commands

```powershell
python kg_v2/Step4_graph/export_lightrag_docs.py `
  --graph-dir kg_v2/outputs/intermediate/truth_artifacts `
  --out kg_v2/outputs/lightrag_v3/docs.jsonl
```

```powershell
python kg_v2/Step4_graph/lightrag_ingest_v3.py `
  --docs kg_v2/outputs/lightrag_v3/docs.jsonl `
  --working-dir kg_v2/outputs/lightrag_v3 `
  --embedding-model BAAI/bge-m3 `
  --embedding-dim 1024 `
  --llm-provider deepseek `
  --llm-model deepseek-chat `
  --query-mode mix `
  --enable-reranker
```

`embedding_manifest.json` is written in the LightRAG working directory. If it does not match the current embedding provider/model/dim, ingest stops unless `--rebuild` is provided.

## Neo4j

Set `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE` in `.env`. The default URI used by this project is `bolt://127.0.0.1:7688`.

Build/import the V3 graph with the existing KG build scripts, then export LightRAG docs from `kg_v2/outputs/intermediate/truth_artifacts`.

## V3 Smoke Test

Before full graph import, validate the Step3 artifact chain:

```powershell
python kg_v2/Step4_graph/smoke_v3_kg_e2e.py `
  --intermediate-dir kg_v2/outputs/intermediate `
  --graph-out-dir kg_v2/outputs/graph_v3_smoke `
  --sample-size 20 `
  --skip-neo4j
```

With Neo4j available:

```powershell
python kg_v2/Step4_graph/smoke_v3_kg_e2e.py `
  --intermediate-dir kg_v2/outputs/intermediate `
  --graph-out-dir kg_v2/outputs/graph_v3_smoke `
  --sample-size 20 `
  --neo4j-uri bolt://127.0.0.1:7688 `
  --neo4j-user neo4j `
  --neo4j-password $env:NEO4J_PASSWORD `
  --neo4j-database neo4j `
  --clear-smoke-graph
```

The smoke graph is tagged with `is_smoke=true` and `smoke_run_id`; it never deletes formal V3 or V1 graph data.
