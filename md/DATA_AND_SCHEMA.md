# DATA_AND_SCHEMA

## 题库组织方式

| Dataset | 主文件 | 行数 | 任务类型 |
|---|---:|---:|---|
| `QA-SC` | `question/QA-SC/QA-SC_questions.jsonl` | 2450 | objective / single-choice |
| `QA-MC` | `question/QA-MC/QA-MC_questions.jsonl` | 1235 | objective / multi-choice |
| `QA-SA` | `question/QA-SA/QA-SA_questions.jsonl` | 1232 | objective / short-answer |
| `Bird-Geo` | `question/Bird-Geo/Bird-Geo_questions.jsonl` | 448 | objective / single-choice |
| `Bird-Taxonomy` | `question/Bird-Taxonomy/Bird-Taxonomy_questions.jsonl` | 840 | objective / short-answer |
| `Bird-Life` | `question/Bird-Life/Bird-Life_questions.jsonl` | 446 | subjective |
| `Bird-Eco` | `question/Bird-Eco/Bird-Eco_questions.jsonl` | 216 | subjective |
| `Bird-Con` | `question/Bird-Con/Bird-Con_questions.jsonl` | 217 | subjective |
| `Bird-Comp` | `question/Bird-Comp/Bird-Comp_questions.jsonl` | 986 | subjective |
| `Bird-Reason` | `question/Bird-Reason/Bird-Reason_questions.jsonl` | 219 | subjective |
| `Bird-Plan` | `question/Bird-Plan/Bird-Plan_questions.jsonl` | 63 | subjective |
| `List-Global` | `question/List-Global/List-Global_questions.jsonl` | 200 | structured / table list retrieval |
| `Bird-ID` | `question/Bird-ID/Bird-ID_questions.jsonl` | 990 | structured / masked species ID |
| `Bird-Classify` | `question/Bird-Classify/Bird-Classify_questions.jsonl` | 500 | structured 或 subjective，按 `type` 分流 |

`Bird-Classify` subtype 分布：`Feature-to-Family` 167，`Taxonomic Hierarchy` 169，`Taxon-to-Feature` 164。

## 题目 JSON 字段

| 字段 | 常见性 | 含义 |
|---|---|---|
| `question_id` | 全部正式题 | 稳定题号。 |
| `dataset` | 全部正式题 | 数据集名。 |
| `knowledge_domain` | 多数题 | 知识领域标签，如 conservation、taxonomy、identification。 |
| `type` | 全部正式题 | 题型/subtype；`Bird-Classify` 依赖此字段路由。 |
| `target_entity` | 除 `List-Global` 外常见 | 目标鸟种或目标分类单元；Bird-ID 中是 gold identity，检索时必须避免泄露。 |
| `question` | 全部正式题 | 题干。 |
| `options` | 选择题 | 选项字典，见 `QA-SC`、`QA-MC`、`Bird-Geo`。 |
| `answer` | 全部正式题 | gold answer；`List-Global` 与 Bird-ID 评测会按 list 处理。 |
| `provenance` | 全部正式题 | 来源库、章节、引用、生成理由或检索条件。 |
| `clue_text` | `Bird-ID` | masked ID 的可见线索正文，评测和 reverse retrieval 应使用它而不是 `target_entity`。 |
| `constraint_applied` | `Bird-Plan` | 计划类问题的约束条件。 |
| `order`, `family`, `sample_key` | `Bird-Classify` | Feature-to-Family gold 分类与样本键。 |

## 三类任务字段差异

| 任务类 | 数据集 | 输入字段重点 | 输出/评分 |
|---|---|---|---|
| objective | `QA-SC`, `QA-MC`, `QA-SA`, `Bird-Geo`, `Bird-Taxonomy` | `question`, `options`, `answer`, `target_entity`, `type` | 单选 exact match，多选 set-F1/EM，短答 token-F1/EM。 |
| subjective | `Bird-Life`, `Bird-Eco`, `Bird-Con`, `Bird-Comp`, `Bird-Reason`, `Bird-Plan`, `Bird-Classify` open types | `question`, `answer`, `target_entity`, `type`, `knowledge_domain` | 候选答案由 LLM-as-a-Judge 按 rubric 打分。 |
| structured | `List-Global`, `Bird-ID`, `Bird-Classify__Feature-to-Family` | `List-Global.answer` 为 list；`Bird-ID.clue_text`；`Bird-Classify.order/family/type` | List precision/recall/F1/set-EM；Bird-ID top1/top5/weighted top5；Classify order/family/hierarchical accuracy。 |

`Bird-Con` 归入 subjective，因为答案是开放式 conservation status/trend/history 叙述，代码在 `subjective_rubrics.py` 中定义三维 100 分 rubric。

## V3 知识库实体 schema

| 实体 | 主要字段 | 生成位置 |
|---|---|---|
| Taxon | `taxon_id`, `rank`, `scientific_name`, `english_name_primary`, `order_name`, `family_name`, `genus_name`, `parent_taxon_id`, `canonical_source`, `canonical_release`, `avibase_id`, `cornell_species_code`, `bow_url`, `iucn_status`, `taxonomy_status` | `kg_v2/Step1_taxonomy/schema/taxonomy_schema.py` |
| Chunk | `chunk_id`, `species_name` 或 `family_name`, `order_name`, `source_db`, `source_file`, `source_chapter`, `source_subchapter`, `source_chapter_raw`, `raw_text` | `kg_v2/parsers/parse_bow_species_xlsx.py`, `parse_order_family_xlsx.py` |
| Claim | `claim_id`, `subject_taxon_id`, `subject_rank`, `fact_domain`, `predicate`, `object_type`, `object_text`, `object_canonical_id`, `object_canonical_name`, `value_min`, `value_max`, `unit`, `qualifiers_raw`, source metadata, `evidence_quote`, `confidence`, `extraction_method` | `kg_v2/Step3_extraction/run_extract_claims_and_facts.py` |
| Fact | `fact_id`, `subject_taxon_id`, `subject_rank`, `fact_domain`, `predicate`, object/value fields, `qualifiers_norm`, `support_count`, `confidence`, `status` | `kg_v2/Step3_extraction/fact_builder.py` |
| Evidence | `evidence_id`, `source_db`, `source_release`, `source_doc_id`, `source_chunk_id`, `source_chapter`, `source_subchapter`, `evidence_quote`, `evidence_hash` | `kg_v2/Step3_extraction/evidence_builder.py` |
| Qualifier | `qualifiers_raw` / `qualifiers_norm`，固定键由 `QUALIFIER_KEYS` 管理 | `kg_v2/Step3_extraction/normalizers.py` |

最小链路：`Taxon` -`HAS_FACT`-> `Fact` -`SUPPORTED_BY`-> `Evidence` -`DERIVED_FROM`-> `Chunk`。

## 数据源用途

| 文件/目录 | 代码用途 |
|---|---|
| `data/BOW/*.xlsx` | species-level BOW 文本，解析为 `species_records.jsonl` 与 `species_chunks.jsonl`；Text-RAG、Step2、Step3、Bird-ID reverse 检索间接受益。 |
| `data/Order.xlsx` | family/order-level 辅助表，解析为 `family_records.jsonl`、`family_chunks.jsonl`；也用于 `Bird-Classify__Feature-to-Family` 的 Table-KB。 |
| `data/BIRDBASE.xlsx` | 结构化表格知识库，`List-Global` 通过条件检索候选行。表中有嵌入式表头，`table_kb_utils.load_excel_table()` 会合并顶层表头和首行表头。 |
| `data/AviList-v2025-11Jun-extended.xlsx` | Step1 canonical taxonomy source。 |
| `data/Clements_v2025-October-2025.xlsx` | Step1 Cornell/Clements compatibility layer，生成 crosswalk、alias、conflict。 |

## 特殊评分注意事项

| Dataset | 特殊字段 | 评分注意事项 |
|---|---|---|
| `Bird-ID` | `clue_text`, `target_entity` | `target_entity` 是答案身份，reverse retrieval 不能使用；评分用 gold answer 与 target aliases 构造 top1/top5/weighted top5。 |
| `List-Global` | `answer` list, `provenance.search_conditions` | 应按集合评分；Table-KB 候选来自 BIRDBASE 条件/问题 token。 |
| `Bird-Classify` | `type`, `order`, `family` | `Feature-to-Family` 走 structured；`Taxonomic Hierarchy`、`Taxon-to-Feature` 更适合 subjective。评分包括 order accuracy、family accuracy、hierarchical score。 |
