# OUTPUTS_AND_LOGS

## `evaluation/output/` 目录规范

统一 CLI 默认输出：

```text
evaluation/output/results_{task_type}_{knowledge_mode}_{question_root_tag}/
├── run_manifest.json
├── context_logs/
├── answers/
├── judge_results/
├── predictions/
├── summaries/
└── errors/
```

注意：历史脚本还存在旧目录名，如 `results_objective_kg_rag`、`results_subjective_text_rag_v2`、`results_structured_remaining_kb_*`、`results_all_remaining_kb_*`。这些是历史运行输出，不代表新的论文分组。

## `run_manifest.json`

由 `evaluation/knowledge_RAG/logging/run_manifest.py` 写入。

| 字段 | 含义 |
|---|---|
| `question_root` | 题库根目录。 |
| `knowledge_mode` | `none/text_rag/kg_v1/kg_v3/hybrid`。 |
| `kg_backend` | `neo4j/lightrag/hybrid`。 |
| `kg_version` | `v1_directed/v3_fact_graph`。 |
| `embedding_model`, `embedding_dim` | embedding 配置。 |
| `reranker_model`, `reranker_enabled` | reranker 配置。 |
| `models` | 候选模型 alias。 |
| `datasets` | 本次运行数据集。 |
| `dataset_group` | objective/subjective/structured。 |
| `modes` | subjective prompt modes。 |
| `created_at` | UTC ISO 时间。 |
| `git_commit` | 当前 git short hash，取不到则为空。 |

## `context_logs`

统一 schema 在 `evaluation/knowledge_RAG/logging/context_logger.py` 中定义，字段包括：

| 字段 | 含义 |
|---|---|
| `question_id`, `dataset`, `dataset_group` | 题目标识与分组。 |
| `knowledge_mode`, `kg_backend`, `kg_version`, `kg_query_mode` | 检索配置。 |
| `embedding_model`, `embedding_dim`, `reranker_model`, `reranker_enabled` | 向量与 rerank 配置。 |
| `route`, `status` | dataset-aware routing 结果与检索状态。 |
| `initial_retrieval_count`, `reranked_count` | 初检索数量与 rerank 后数量。 |
| `items` | 检索项列表，含 `item_type`, `fact_id`, `predicate`, `object_text`, `retrieval_score`, `rerank_score`, `rank_before`, `rank_after`, `evidence_quote`, `source_chunk_id`, `source`。 |

审计注意：当前非 dry-run CLI 多数委派 legacy scripts，legacy context log 字段可能只包含 `kg_context`、`context_type`、`context_status` 等，不一定完全符合统一 schema。

## 输出子目录作用

| 目录/文件 | 作用 |
|---|---|
| `predictions/` | objective 逐题预测，常见字段含 raw response、parsed answer、gold、EM/F1/correct、error。 |
| `answers/` | subjective/structured 模型答案。subjective 通常为 `answers/{mode}/{model}/{dataset}.jsonl`；structured 为 `answers/{model}/{dataset}.jsonl`。 |
| `judge_results/` 或 `judge_qwen/` | subjective judge 结果。当前 minimal pipeline 使用 `judge_qwen/`。 |
| `scored/` | structured 逐题评分。 |
| `summaries/` | 聚合 CSV/JSON，例如 `summary_structured.csv`、`summary_core_table.csv`。 |
| `errors/` | 统一 CLI 预留错误目录；legacy scripts 可能把错误写入行内 `error` 字段。 |
| `summary.json`, `summary_all.json` | objective/KG legacy 常见模型级、全模型汇总。 |

## Excel 可视化图与 `image/chap04/kb_compare/`

当前仓库中未发现 `image/chap04/kb_compare/` 目录。已存在的可视化产物主要在：

| 路径 | 来源 |
|---|---|
| `evaluation/figures/taxonomy/` | `scripts/visualize_taxonomy_backbone.py` 生成的 taxonomy tree 与 Clements crosswalk 图。 |
| `evaluation/figures/taxonomy_compact/` | compact 版本 taxonomy/crosswalk 图。 |
| `evaluation/output/**/summary*.csv` | 评测汇总表，可作为论文图表数据源。 |

若后续论文需要 `image/chap04/kb_compare/`，建议将从 `evaluation/output/**/summary*.csv` 或 Excel 生成的对比图复制/导出到该目录，并在论文构建脚本中显式引用。
