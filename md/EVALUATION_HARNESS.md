# EVALUATION_HARNESS

## 总体设计

`evaluation/knowledge_RAG/` 是统一层，目标是为 Vanilla、Text-RAG、KG-RAG V1、KG-RAG V3、Hybrid 提供统一参数、输出 manifest 和 dataset routing。

实际执行分两层：

| 层 | 文件 | 职责 |
|---|---|---|
| 统一 CLI 层 | `evaluation/knowledge_RAG/cli/*.py` | 解析 `knowledge_mode`、写 `run_manifest.json`、选择 legacy script、支持 dry-run。 |
| Retriever runtime 层 | `evaluation/knowledge_RAG/runtime.py`, `registry.py`, `retrievers/*` | 直接调用时可构造 `V3FactGraphRetriever`、`HybridRetriever`、`TextChunkRetriever` 等。 |
| Legacy execution 层 | `evaluation/objective_eval.py`, `evaluation/text_RAG/*.py`, `evaluation/kg_RAG/*.py` | 当前非 dry-run CLI 实际委派执行的位置。 |

## knowledge_mode 含义

| mode | 含义 | 当前非 dry-run CLI 实际落点 |
|---|---|---|
| `none` | 无外部知识 Vanilla。 | `objective_eval.py`、`run_subjective_pipeline.py`、`structured_eval.py` |
| `text_rag` | BOW raw/pre-split chunk 检索 baseline。 | `evaluation/text_RAG/*.py` |
| `kg_v1` | legacy Neo4j `DIRECTED` one-hop KG-RAG。 | `evaluation/kg_RAG/*.py` |
| `kg_v3` | 设计上是 V3 Taxon-Fact-Evidence-Chunk。 | CLI 仍委派到 `evaluation/kg_RAG/*.py`；objective/subjective 仍会走 DIRECTED。 |
| `hybrid` | 设计上是 V3 graph + LightRAG + reranker + Table-KB。 | CLI 仍委派到 `evaluation/kg_RAG/*.py`；`KnowledgeRAGRuntime` 直接调用时才会组合 V3 retriever 和 LightRAG retriever。 |

## 三类评测流程

| 类型 | 统一入口 | Legacy 执行 | 输出 |
|---|---|---|---|
| objective | `evaluation/knowledge_RAG/cli/run_objective.py` | `objective_eval.py` / `text_RAG/text_rag_objective_eval.py` / `kg_RAG/kg_objective_eval.py` | `predictions/*.jsonl`, `summary.json`, `summary_all.json` |
| subjective | `evaluation/knowledge_RAG/cli/run_subjective.py` | `run_subjective_pipeline.py` / `text_RAG/text_rag_run_subjective_pipeline.py` / `kg_RAG/kg_subjective_answer.py` | `answers/`, `judge_qwen/` 或 `judge_results/`, `summaries/`, `context_logs/` |
| structured | `evaluation/knowledge_RAG/cli/run_structured.py` | `structured_eval.py` / `text_RAG/text_rag_remaining_kb_structured_eval.py` / `kg_RAG/kg_structured_eval.py` | `answers/`, `scored/`, `summaries/summary_structured.csv`, `context_logs/` |

## Dataset-aware routing

| Group | Datasets |
|---|---|
| objective | `QA-SC`, `QA-MC`, `QA-SA`, `Bird-Geo`, `Bird-Taxonomy` |
| subjective | `Bird-Life`, `Bird-Eco`, `Bird-Con`, `Bird-Comp`, `Bird-Reason`, `Bird-Plan`, `Bird-Classify-Type1` |
| structured | `List-Global`, `Bird-ID`, `Bird-Classify__Feature-to-Family`, `Bird-Classify-Type2` |

`Bird-Con` 归入 subjective，因为它要求开放式保育状态、趋势、威胁和历史解释，`subjective_rubrics.py` 中有专门 rubric。

`Bird-Classify` 按 subtype 分流：

| subtype / dataset key | 分流 |
|---|---|
| `Feature-to-Family` 或 `Bird-Classify__Feature-to-Family` | structured，输出 `{"order": "...", "family": "..."}`。 |
| `Taxonomic Hierarchy`, `Taxon-to-Feature` | subjective，输出开放解释，由 judge 评分。 |

`remaining_four` 只是历史工程名，用于早期把 `List-Global`、`Bird-ID`、`Bird-Con`、`Bird-Classify` 合并调度；不应作为论文正式概念。

## context / prompt / scoring 调用链

| 环节 | 新统一 runtime | 当前 legacy KG 脚本 |
|---|---|---|
| request 构造 | `runtime.request_from_item()` | 各 legacy script 自行从 JSONL row 构造。 |
| context 构造 | `KnowledgeRAGRuntime.retrieve()` -> `registry.build_retriever()` | `kg_objective_eval.py`/`kg_subjective_answer.py` 调 `neo4j_direct_retriever.retrieve_kg_context()`；`kg_structured_eval.py` 调 table/reverse retriever。 |
| context 格式化 | `formatting/context_formatter.py` | legacy scripts 自己拼接 prompt 或 context block。 |
| prompt 组装 | `formatting/prompt_builder.py` 或 legacy prompt builder | objective: `kg_prompting.build_kg_augmented_prompt()`；subjective: `kg_prompting.build_kg_subjective_prompt()`；structured: dataset-specific prompt builder。 |
| answer 调用 | `model_registry.py` + OpenAI-compatible client | legacy scripts 同样使用 `model_registry.py` 或 shared helpers。 |
| 评分 | objective: EM/F1；subjective: judge；structured: dataset-specific | 同左，但由 legacy scripts 执行。 |
| 聚合 | `summary.json/csv` | objective `summary_all.json`；subjective `subjective_aggregate.py`；structured `summary_structured.csv`。 |
| 日志 | `logging/run_manifest.py`, `logging/context_logger.py` | manifest 由 CLI 写；legacy context logs 仅部分结构化，字段不完全等同 `context_logger.py`。 |

关键限制：`evaluation/knowledge_RAG/logging/context_logger.py` 定义了统一 context log schema，但当前 CLI 委派 legacy scripts 后，并不是所有 legacy 路径都会调用它。
