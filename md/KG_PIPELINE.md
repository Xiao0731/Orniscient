# KG_PIPELINE

## Step1: Taxonomy Backbone

| 项 | 内容 |
|---|---|
| 脚本 | `kg_v2/Step1_taxonomy/run_build_taxonomy_backbone.py` |
| 输入 | `data/AviList-v2025-11Jun-extended.xlsx`, `data/Clements_v2025-October-2025.xlsx` |
| 关键逻辑 | `parse_avilist_xlsx()` 读取 AviList；`build_taxonomy_backbone()` 以 AviList 生成 canonical order/family/genus/species/subspecies 节点和包含边；`parse_clements_xlsx()` 读取 Clements；`build_taxonomy_crosswalks()` 按 Avibase ID、Cornell species code、rank+scientific name、family/order fallback 建 crosswalk；`build_taxonomy_conflicts()` 记录 rank/family/genus/name/split-lump drift/unresolved 冲突。 |
| 中间产物 | `kg_v2/outputs/intermediate/taxonomy/*.jsonl/json` |
| 下游副本 | `kg_v2/outputs/jsonl/taxonomy_nodes.jsonl`, `taxonomy_edges.jsonl` |

主要输出：`avilist_rows.jsonl`、`clements_rows.jsonl`、`canonical_taxon_nodes.jsonl`、`canonical_taxon_edges.jsonl`、`taxonomy_crosswalks.jsonl`、`taxonomy_aliases.jsonl`、`taxonomy_conflicts.jsonl`、`taxonomy_validation_report.json`、`taxonomy_build_summary.json`。

## Step2: Attachment

| 项 | 内容 |
|---|---|
| 脚本 | `kg_v2/Step2_attachment/run_build_taxonomy_attachment.py` |
| 输入 | Step1 taxonomy artifacts；`species_records.jsonl`、`species_chunks.jsonl`、`family_records.jsonl`、`family_chunks.jsonl` |
| species 逻辑 | `species_attachment.py` 按 scientific name direct match、alias match、family/order assisted match 挂接到 canonical species。 |
| family 逻辑 | `family_attachment.py` 按 direct family match、alias match、order-assisted match 挂接到 canonical family。 |
| unresolved | 空名、歧义、未找到等写入 unresolved 文件，不静默丢弃。 |
| 输出 | `kg_v2/outputs/intermediate/attachments/` |

主要输出：`species_taxonomy_links.jsonl`、`species_chunk_taxonomy_links.jsonl`、`family_taxonomy_links.jsonl`、`family_chunk_taxonomy_links.jsonl`、`taxonomy_unresolved_species.jsonl`、`taxonomy_unresolved_family.jsonl`、`attachment_summary.json`。

## Step3: Claim / Fact / Evidence Extraction

| 项 | 内容 |
|---|---|
| 脚本 | `kg_v2/Step3_extraction/run_extract_claims_and_facts.py` |
| 输入 | Step2 attachments、species/family chunks、taxonomy nodes |
| extraction | `StructuredLLMExtractor` 走 OpenAI-compatible JSON schema；无配置时 `auto` 可回退到 `MockStructuredExtractor`。 |
| routing | `chapter_router.py` 根据 BOW 章节限制 `fact_domain` 和 `predicate`。 |
| claim 校验 | `_validate_wrapper()` 检查 domain、predicate、subject_taxon_id、evidence quote、confidence、object_type、qualifiers。 |
| fact merge | `fact_builder.py` 用 subject/predicate/object/value/unit/normalized qualifiers 分组；按 subject/domain quota 控制事实数量。 |
| evidence | `evidence_builder.py` 生成 chunk-level evidence，最多每 fact 绑定 2 条 evidence。 |
| 输出 | `kg_v2/outputs/intermediate/claims/` |

主要输出：`species_claims.jsonl`、`family_claims.jsonl`、`species_facts.jsonl`、`family_facts.jsonl`、`evidences.jsonl`、`fact_evidence_links.jsonl`、`extractor_failures.jsonl`、`extraction_summary.json`。

注意：当前本地 `claims/` 中 `family_claims.jsonl` 与 `family_facts.jsonl` 为空；已有 smoke 使用小规模 species facts/evidences。

## Step4: Graph / LightRAG / Smoke

| 项 | 内容 |
|---|---|
| LightRAG docs | `kg_v2/Step4_graph/export_lightrag_docs.py` 从 `truth_artifacts/fact_nodes.jsonl`、`evidence_nodes.jsonl`、`edges.jsonl` 分组导出 `kg_v2/outputs/lightrag_v3/docs.jsonl`。 |
| LightRAG ingest | `kg_v2/Step4_graph/lightrag_ingest_v3.py` 写入 local `docs.jsonl`，校验 `embedding_manifest.json`，可尝试调用真实 LightRAG ingest；失败时保留 local docs。 |
| smoke test | `kg_v2/Step4_graph/smoke_v3_kg_e2e.py` 从 Step3 claims 或 truth artifacts 抽样构造最小 graph，并可选导入 Neo4j 后运行 `V3FactGraphRetriever`。 |

V2/兼容构图脚本 `kg_v2/run_build_kb_v2.py` 仍负责解析 BOW、生成 `kg_v2/outputs/intermediate/*`、导出 `truth_artifacts` 和 `jsonl/all_nodes.jsonl`、`all_edges.jsonl`。这些产物是当前 Text-RAG 和部分 V3 smoke/LightRAG 导出的基础。

## 最小图谱链路

```text
Taxon
  -[HAS_FACT]->
Fact
  -[SUPPORTED_BY]->
Evidence
  -[DERIVED_FROM]->
Chunk
```

字段对应：

| 节点 | 关键字段 |
|---|---|
| Taxon | `taxon_id`, `scientific_name`, `rank`, `family_name`, `order_name` |
| Fact | `fact_id`, `subject_taxon_id`, `fact_domain`, `predicate`, `object_text/value_text`, `confidence` |
| Evidence | `evidence_id`, `source_chunk_id`, `source_chapter`, `evidence_quote` |
| Chunk | `chunk_id`, `source_chapter`, `cleaned_text/raw_text`, `canonical_taxon_id` |

## Neo4j / LightRAG / Table-KB 角色

| 组件 | 角色 |
|---|---|
| Neo4j | 图数据库后端。V1 使用 `DIRECTED` 边；V3 设计使用 `Taxon-HAS_FACT-Fact-SUPPORTED_BY-Evidence-DERIVED_FROM-Chunk`。 |
| LightRAG | 对 V3 controlled docs 做混合检索；默认 `mix` query mode，可接 reranker。 |
| Table-KB | BIRDBASE/Order 表格检索，用于 `List-Global` 与 `Bird-Classify__Feature-to-Family`；不是 Neo4j 图谱。 |

## smoke_v3_kg_e2e.py 验证范围

已验证：

| 报告 | 结论 |
|---|---|
| `reports/smoke_v3_kg_e2e_report.md` | `status: pass` |
| 节点 | Taxon 1, Fact 2, Evidence 2, Chunk 1 |
| 边 | HAS_FACT 2, SUPPORTED_BY 2, DERIVED_FROM 2 |
| 源 | `kg_v2/outputs/intermediate/claims/species_facts.jsonl` 与 `evidences.jsonl` |

尚未验证：

| 项 | 状态 |
|---|---|
| 不带 `--skip-neo4j` 的 smoke | 报告显示 `neo4j.enabled=false`, `status=skipped`。 |
| `V3FactGraphRetriever` 对真实 Neo4j V3 graph 的检索 | 报告显示 retriever `context_status=skipped`。 |
| 完整 graph_v3 / Neo4j 导入后 objective/subjective/structured 全量评测 | 未由现有报告证明。 |
