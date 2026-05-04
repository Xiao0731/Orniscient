# PROJECT_STRUCTURE

## 主目录树

```text
Generation/
├── question/                         # 正式题库 JSONL
├── data/                             # 原始/辅助数据表
│   ├── BOW/                          # Birds of the World 分批 Excel
│   ├── BIRDBASE.xlsx                 # 结构化鸟类表格知识库
│   ├── Order.xlsx                    # 目/科级 BOW 辅助表
│   ├── AviList-v2025-11Jun-extended.xlsx
│   └── Clements_v2025-October-2025.xlsx
├── kg_v2/                            # KG V2/V3 构建、导出与检索底座
│   ├── Step1_taxonomy/               # V3 canonical taxonomy backbone
│   ├── Step2_attachment/             # BOW record/chunk 到 canonical taxon 挂接
│   ├── Step3_extraction/             # Claim/Fact/Evidence 抽取
│   ├── Step4_graph/                  # V3 图谱 smoke、LightRAG docs/ingest
│   ├── builders/parsers/extractors/   # 历史 V2 构图与兼容构件
│   ├── rag/                          # V2 vector/Neo4j/LightRAG 辅助检索
│   └── outputs/                      # 中间产物、jsonl、smoke graph、Neo4j CSV
├── evaluation/
│   ├── objective_eval.py             # Vanilla objective evaluation
│   ├── run_subjective_pipeline.py    # Vanilla subjective answer->judge->aggregate
│   ├── structured_eval.py            # Vanilla structured evaluation
│   ├── text_RAG/                     # Text-RAG baseline
│   ├── kg_RAG/                       # KG/KB compatibility layer
│   ├── knowledge_RAG/                # 统一 CLI/配置/路由层
│   ├── model_registry.py             # 模型 alias、base_url、key env 映射
│   └── fewshot_examples/             # subjective few-shot examples
├── scripts/                          # 可视化、采样、审计、归档辅助脚本
├── reports/                          # smoke/audit/doctor 类报告
├── tests/                            # 小型回归测试
├── used/                             # 历史脚本与旧实验材料
└── *.py at repo root                 # 早期题目生成/实验脚本
```

完整核心目录树另见 `reports/project_tree.txt`，已排除 `.env`、`.venv`、`__pycache__`、`evaluation/output` 大体积结果、模型缓存等。

## 目录角色

| 路径 | 用途 | 状态 |
|---|---|---|
| `question/` | 正式题库，每个 dataset 一个目录，主文件为 `{dataset}_questions.jsonl`。 | 正式流程输入 |
| `question/*_accepted.jsonl`, `*_rejected.jsonl` | 生成过程筛选痕迹，如 `Bird-Taxonomy`、`Bird-Con`。 | 历史/审计辅助 |
| `question_sample_seed*/` | 固定随机种子的题库子集，用于公平比较。 | 实验样本输入 |
| `data/` | BOW、BIRDBASE、AviList、Clements、Order 等源表。 | 正式数据源 |
| `kg_v2/Step1_taxonomy` 至 `Step4_graph` | 当前 V3 KG 构建主线。 | 正式 KG pipeline |
| `kg_v2/builders`, `kg_v2/extractors`, `kg_v2/parsers`, `kg_v2/rag` | V2 构图与导出逻辑，部分产物仍被 V3 smoke、LightRAG 导出、Text-RAG 使用。 | 历史兼容/辅助 |
| `evaluation/objective_eval.py` | 无外部知识的 objective baseline。 | 正式 baseline |
| `evaluation/run_subjective_pipeline.py` | 无外部知识的 subjective pipeline。 | 正式 baseline |
| `evaluation/structured_eval.py` | 无外部知识的 structured pipeline。 | 正式 baseline |
| `evaluation/text_RAG/` | 基于 BOW chunk 的 Text-RAG。不能标为废弃。 | baseline |
| `evaluation/kg_RAG/` | 旧 KG/KB 入口，保留 DIRECTED V1、Table-KB、Bird-ID reverse retrieval、LightRAG adapter 等。不能标为废弃。 | compatibility layer |
| `evaluation/knowledge_RAG/` | 统一 CLI、manifest、配置和 routing 层，封装 `none/text_rag/kg_v1/kg_v3/hybrid` 名称。 | 新统一入口 |
| `scripts/` | 采样、taxonomy 图可视化、unused audit、归档。 | 辅助工具 |
| `reports/` | 已生成的 smoke/audit 报告。 | 运行记录 |
| `used/` | 早期 notebook/脚本/可视化输出。 | 历史兼容文件 |

## text_RAG、kg_RAG、knowledge_RAG 关系

| 目录 | 定位 | 与正式评测关系 |
|---|---|---|
| `evaluation/text_RAG/` | Text-RAG baseline，直接检索 `kg_v2/outputs/intermediate/species_chunks.jsonl` 与 `family_chunks.jsonl`。 | 用于与 Vanilla、KG-RAG、Hybrid 比较。 |
| `evaluation/kg_RAG/` | KG/KB compatibility layer。包含 V1 DIRECTED Neo4j、Bird-ID reverse KG、BIRDBASE/Order Table-KB、LightRAG V3 adapter。 | 统一 CLI 当前仍会委派到这里的 legacy scripts。 |
| `evaluation/knowledge_RAG/` | 统一配置/路由/manifest/CLI；内部有 `V3FactGraphRetriever` 和 `HybridRetriever`。 | 设计上是新入口，但若运行 CLI 的非 dry-run，实际会调用 `evaluation/kg_RAG/*.py` 或 `evaluation/text_RAG/*.py` legacy 脚本。 |

重要审计结论：`knowledge_RAG` 中的 `V3FactGraphRetriever` 已实现，但当前 `run_objective.py/run_subjective.py/run_structured.py` 的非 dry-run 调用链通过 `cli/common.py::base_legacy_cmd()` 委派到 legacy 脚本；其中 objective、subjective 的 KG 脚本仍调用 `evaluation/kg_RAG/neo4j_direct_retriever.py` 的 `DIRECTED` 查询。

## scripts 与 reports

| 路径 | 作用 |
|---|---|
| `scripts/visualize_taxonomy_backbone.py` | 从 Step1 artifacts 或 AviList/Clements xlsx fallback 生成 taxonomy tree 与 checklist crosswalk 图。 |
| `scripts/make_question_sample.py` | 生成固定 seed 的采样题库，输出 `sample_manifest.csv`、`sample_summary.csv`、`sample_config.json`。 |
| `scripts/audit_unused_files.py` | 静态审计可能未使用文件，只写 `reports/unused_file_audit.*`，不移动文件。 |
| `scripts/archive_unused_files.py` | 按 audit report 归档高置信缓存/临时文件；默认 dry-run，`--execute` 才移动。 |
| `reports/smoke_v3_kg_e2e_report.*` | V3 最小图谱 smoke 结果。 |
| `reports/unused_file_audit.*` | unused file audit 结果。 |
| `evaluation/knowledge_RAG/cli/doctor.py` | doctor 是诊断 CLI；当前没有固定 doctor report 文件，若需要归档可将终端输出重定向到 `reports/doctor_*.txt`。 |
