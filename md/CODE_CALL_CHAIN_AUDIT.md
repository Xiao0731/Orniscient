# CODE_CALL_CHAIN_AUDIT

## 结论摘要

| 问题 | 结论 |
|---|---|
| `knowledge_RAG` 中是否实现了 `V3FactGraphRetriever`？ | 是，位于 `evaluation/knowledge_RAG/retrievers/v3_fact_graph_retriever.py`。 |
| 当前统一 CLI 非 dry-run 的 `kg_v3` 是否一定使用它？ | 否。CLI 通过 `base_legacy_cmd()` 委派 legacy scripts。 |
| objective `kg_v3` 是否仍可能走旧 V1 DIRECTED？ | 会。`kg_objective_eval.py` 直接调用 `neo4j_direct_retriever.retrieve_kg_context()`，其 Cypher 使用 `MATCH (s)-[r:DIRECTED]-(o)`。 |
| subjective `kg_v3` 是否仍可能走旧 V1 DIRECTED？ | 会。`kg_subjective_answer.py` 同样调用 `neo4j_direct_retriever.retrieve_kg_context()`。 |
| structured `kg_v3` 是否使用 V3FactGraphRetriever？ | 否。`kg_structured_eval.py` 使用 BIRDBASE/Order Table-KB 和 Bird-ID reverse DIRECTED query。 |
| smoke 是否检查了 V3FactGraphRetriever？ | 只有不加 `--skip-neo4j` 且 Neo4j import 成功后才检查；当前报告显示 skipped。 |

## 1. `run_objective.py --knowledge-mode kg_v3`

```text
evaluation/knowledge_RAG/cli/run_objective.py
  -> write_manifest_for_args()
     -> logging/run_manifest.py
  -> base_legacy_cmd(args, "objective", out_dir)
     -> legacy_script_for("objective", "kg_v3")
        -> evaluation/kg_RAG/kg_objective_eval.py
  -> subprocess.call(...)
```

`kg_objective_eval.py` 内部链路：

```text
main()
  -> load dataset via objective_eval.discover_dataset_file/load_jsonl
  -> enabled_specs()/build_client()
  -> run_dataset_for_model()
     -> evaluate_item_with_kg()
        -> KGContextCache.get_or_retrieve()
           -> neo4j_direct_retriever.retrieve_kg_context()
              -> EDGE_CYPHER: MATCH (s)-[r:DIRECTED]-(o)
        -> kg_prompting.build_kg_augmented_prompt()
        -> objective_eval.run_one()
        -> objective_eval.score_answer()
```

审计结论：会调用旧 V1 `DIRECTED` retriever；不会调用 `V3FactGraphRetriever`。`--kg-version v3_fact_graph` 被 argparse 接收，但当前文件未据此分支。

## 2. `run_subjective.py --knowledge-mode kg_v3`

```text
evaluation/knowledge_RAG/cli/run_subjective.py
  -> write_manifest_for_args()
  -> base_legacy_cmd(args, "subjective", out_dir)
     -> legacy_script_for("subjective", "kg_v3")
        -> evaluation/kg_RAG/kg_subjective_answer.py
```

`kg_subjective_answer.py` 内部链路：

```text
main()
  -> load_subjective_dataset_with_target()
  -> subjective_candidate_specs()/build_client()
  -> run_mode_dataset()
     -> answer_one()
        -> prepare_candidate_question()
        -> KGContextCache.get_or_retrieve()
           -> neo4j_direct_retriever.retrieve_kg_context()
              -> EDGE_CYPHER: MATCH (s)-[r:DIRECTED]-(o)
        -> sanitize_subjective_kg_context()
        -> kg_prompting.build_kg_subjective_prompt()
        -> build_kg_candidate_messages()
        -> call_with_retries()
  -> writes answers/context_logs
```

审计结论：会调用旧 V1 `DIRECTED` retriever；不会调用 `V3FactGraphRetriever`。当前 `run_subjective.py` 对 KG 模式不会继续调用 judge/aggregate，只生成 KG answers；judge/aggregate 需后续单独安排或使用非 KG minimal pipeline。

## 3. `run_structured.py --knowledge-mode kg_v3`

```text
evaluation/knowledge_RAG/cli/run_structured.py
  -> write_manifest_for_args()
  -> base_legacy_cmd(args, "structured", out_dir)
     -> legacy_script_for("structured", "kg_v3")
        -> evaluation/kg_RAG/kg_structured_eval.py
  -> append --birdbase-xlsx/--order-xlsx/--list-global-direct-output
```

`kg_structured_eval.py` 内部链路：

```text
main()
  -> DATASET_CONFIGS
     List-Global -> build_list_global_context()
        -> list_global_table_retriever.retrieve_list_global_table_context()
        -> BIRDBASE Table-KB
     Bird-ID -> build_bird_id_context()
        -> bird_id_reverse_retriever.retrieve_bird_id_candidates()
        -> REVERSE_BIRD_ID_CYPHER: MATCH (s)-[r:DIRECTED]-(o)
     Bird-Classify__Feature-to-Family -> build_feature_to_family_context()
        -> family_table_retriever.retrieve_family_table_context()
        -> Order.xlsx Table-KB
  -> prompt_builder
  -> call_model()
  -> parser/scorer/summarizer from structured_eval.py
```

审计结论：不会调用 `V3FactGraphRetriever`。`Bird-ID` 会调用旧 `DIRECTED` reverse retrieval，但它按代码注释不使用 `target_entity` 或 gold answer；`List-Global` 与 `Bird-Classify__Feature-to-Family` 走 Table-KB。

## 4. `run_all.py --knowledge-mode hybrid`

```text
evaluation/knowledge_RAG/cli/run_all.py
  -> run_command(run_objective.py --knowledge-mode hybrid ...)
  -> run_command(run_subjective.py --knowledge-mode hybrid ...)
  -> run_command(run_structured.py --knowledge-mode hybrid ...)
```

随后三条链路与上文相同：

| 子命令 | 实际 legacy 脚本 | V3FactGraphRetriever | DIRECTED |
|---|---|---:|---:|
| objective | `evaluation/kg_RAG/kg_objective_eval.py` | 否 | 是 |
| subjective | `evaluation/kg_RAG/kg_subjective_answer.py` | 否 | 是 |
| structured | `evaluation/kg_RAG/kg_structured_eval.py` | 否 | Bird-ID 是；Table-KB 否 |

审计结论：`run_all.py --knowledge-mode hybrid` 当前不是完整 `KnowledgeRAGRuntime.HybridRetriever` 链路，而是 legacy KG/KB 组合链路。`evaluation/knowledge_RAG/retrievers/hybrid_retriever.py` 中的 V3 graph + LightRAG + reranker 只有直接通过 runtime/registry 使用时才会进入。

## 5. `smoke_v3_kg_e2e.py`

```text
kg_v2/Step4_graph/smoke_v3_kg_e2e.py
  -> build_smoke_graph()
     -> discover_artifacts()
     -> load facts/evidences/links/chunks
     -> build Taxon/Fact/Evidence/Chunk nodes
     -> write graph_v3_smoke/nodes.jsonl, edges.jsonl
  -> if not --skip-neo4j:
     -> import_neo4j()
        -> MERGE smoke-tagged Taxon/Fact/Evidence/Chunk graph
     -> run_retriever_smoke()
        -> assert "DIRECTED" not in V3 FACT_QUERY
        -> KnowledgeRAGConfig.from_env(knowledge_mode="kg_v3", kg_backend="neo4j")
        -> V3FactGraphRetriever.retrieve()
  -> write reports/smoke_v3_kg_e2e_report.json/md
```

当前报告状态：

| 项 | 报告值 |
|---|---|
| smoke graph | pass |
| Neo4j | `enabled=false`, `status=skipped` |
| retriever | `context_status=skipped` |
| `used_v1_directed` | false，但这是 skipped 场景，不等于完整检索已验证 |

## Compatibility / fallback 点

| 文件 | fallback/compatibility |
|---|---|
| `evaluation/knowledge_RAG/cli/common.py` | 统一 CLI 委派 legacy scripts。 |
| `evaluation/kg_RAG/neo4j_direct_retriever.py` | V1 DIRECTED compatibility retriever。 |
| `evaluation/knowledge_RAG/retrievers/v3_fact_graph_retriever.py` | Neo4j 不可用或无密码时回退读取 local `truth_artifacts/fact_nodes.jsonl`，但 local fallback 没有完整 evidence/chunk。 |
| `evaluation/kg_RAG/lightrag_v3_adapter.py` | 本地 `docs.jsonl` 词面检索 fallback，可接 reranker。 |
| `kg_v2/Step4_graph/lightrag_ingest_v3.py` | 真实 LightRAG ingest 失败时保留 `local_docs_only` 或 `fallback_local_docs`。 |
