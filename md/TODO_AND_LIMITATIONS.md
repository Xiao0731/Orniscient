# TODO_AND_LIMITATIONS

## 已完成部分

| 模块 | 状态 |
|---|---|
| 题库组织 | `question/` 下正式 JSONL 已形成；objective/subjective/structured 数据集可被评测脚本发现。 |
| Text-RAG baseline | `evaluation/text_RAG/` 明确保留为 baseline，使用 KG-v2 pre-split BOW chunks。 |
| KG/KB compatibility | `evaluation/kg_RAG/` 保留 V1 DIRECTED、Table-KB、Bird-ID reverse、LightRAG adapter。 |
| 统一 CLI | `evaluation/knowledge_RAG/cli/` 能解析统一参数、写 manifest、执行 dry-run、调度 legacy scripts。 |
| Step1 taxonomy | AviList canonical backbone、Clements crosswalk/alias/conflict 构建逻辑完整。 |
| Step2 attachment | species/family records/chunks 到 canonical taxon 的挂接逻辑完整，并保留 unresolved。 |
| Step3 schema | Claim/Fact/Evidence/Qualifier 数据结构和 LLM/mock extraction orchestration 已实现。 |
| Step4 smoke graph | `--skip-neo4j` 的最小 Taxon-Fact-Evidence-Chunk smoke 报告为 pass。 |
| Table-KB | `List-Global` 使用 BIRDBASE；`Bird-Classify__Feature-to-Family` 使用 Order.xlsx。 |

## 只是骨架或 smoke 通过但未全量验证

| 项 | 限制 |
|---|---|
| V3 Neo4j retrieval | `V3FactGraphRetriever` 已实现，但当前 smoke 报告未验证真实 Neo4j 查询。 |
| Hybrid runtime | `evaluation/knowledge_RAG/retrievers/hybrid_retriever.py` 已实现 V3 graph + LightRAG + reranker 组合，但统一 CLI 非 dry-run 当前未真正走该 runtime。 |
| Step3 full extraction | 代码支持 LLM extraction；本地 `claims/` 产物规模很小，`family_claims.jsonl`/`family_facts.jsonl` 为空。 |
| LightRAG full ingest/query | `lightrag_ingest_v3.py` 支持真实 ingest，也有 local docs fallback；需要确认 `docs.jsonl` 与 `embedding_manifest.json` 完整存在且模型维度匹配。 |
| context_logger schema | 统一 schema 已定义，但 legacy scripts 不一定使用它。 |

## 需要安装 Neo4j 后再验证

| 验证项 | 建议命令/动作 |
|---|---|
| Python driver | `python -m pip install neo4j` |
| Neo4j 连接 | 配置 `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`。 |
| smoke import/query | 运行 `kg_v2/Step4_graph/smoke_v3_kg_e2e.py`，不要加 `--skip-neo4j`。 |
| V3 retriever | 检查 smoke report 中 `neo4j.status=ok`、`retriever.context_status=ok`、`fact_count/evidence_count/chunk_count > 0`。 |

## 需要完整 graph_v3 / Neo4j 导入后确认

| 项 | 当前不能夸大的点 |
|---|---|
| 完整 V3 图谱端到端 | 现有报告只证明小样本 local smoke graph 生成成功，不证明正式 V3 图谱已完整导入 Neo4j。 |
| `kg_v3` CLI 评测 | 当前 objective/subjective 的 `kg_v3` CLI 会走 legacy DIRECTED retriever，不是 V3 FactGraph。 |
| Hybrid KG-RAG 论文结果 | 需确认是否使用真正 `HybridRetriever`，还是 legacy `kg_RAG` 路径。 |
| Bird-ID no-leak | reverse retrieval 代码不使用 `target_entity`，已有测试名提示相关检查；仍建议在正式报告中保留 no-gold-leak 验证日志。 |

## 后续 TODO

| 优先级 | TODO |
|---|---|
| 高 | 修改或新增正式 CLI 链路，使 `--knowledge-mode kg_v3` 真正调用 `KnowledgeRAGRuntime` / `V3FactGraphRetriever`，避免误走 DIRECTED。 |
| 高 | 完整导入 V3 `Taxon-Fact-Evidence-Chunk` graph 到 Neo4j，并运行不带 `--skip-neo4j` 的 smoke。 |
| 高 | 对 objective、subjective、structured 各跑小样本 `kg_v3`，检查 context_logs 中确实有 Fact/Evidence/Chunk。 |
| 中 | 补齐 Step3 family-level claims/facts 或说明 family-level 仍由 Order.xlsx Table-KB 支撑。 |
| 中 | 为 `knowledge_RAG` 非 dry-run 接入统一 `context_logger.py`，减少 legacy 输出字段差异。 |
| 中 | 生成 LightRAG `docs.jsonl` 和 `embedding_manifest.json` 后，验证 query/reranker 真正工作。 |
| 低 | 清理或归档 `used/`、根目录早期脚本前，继续保留 `reports/unused_file_audit.md` 的人工复核步骤。 |
