# CLI_AND_CONFIG

## `.env.example` 与 `.env`

| 文件 | 作用 | 安全要求 |
|---|---|---|
| `.env.example` | 可提交模板，说明需要哪些变量。 | 不包含真实 key。本文档只引用该文件。 |
| `.env` | 本地真实配置，由代码通过 `python-dotenv` 读取。 | 不应提交，不应写入报告；doctor 只打印 key suffix。 |

## 主要配置项

| 类别 | 变量 | 默认/说明 |
|---|---|---|
| DeepSeek LLM | `DEEPSEEK_API_KEY` | DeepSeek chat/generation/judge key。 |
| DeepSeek LLM | `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` |
| DeepSeek LLM | `DEEPSEEK_MODEL` | `deepseek-chat` |
| Embedding | `EMBEDDING_PROVIDER` | `api_compatible` 或 local provider；`.env.example` 使用 `api_compatible`。 |
| Embedding | `EMBEDDING_MODEL` | `BAAI/bge-m3` |
| Embedding | `EMBEDDING_DIM` | `1024`；manifest 不匹配时需 rebuild。 |
| Embedding | `EMBEDDING_API_BASE` | SiliconFlow: `https://api.siliconflow.cn/v1` |
| Embedding | `EMBEDDING_API_KEY` | SiliconFlow embedding key。 |
| Reranker | `RERANKER_PROVIDER` | `api_compatible` 或 local。 |
| Reranker | `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` |
| Reranker | `RERANKER_API_BASE` | SiliconFlow: `https://api.siliconflow.cn/v1` |
| Reranker | `RERANKER_API_KEY` | SiliconFlow reranker key。 |
| LightRAG | `LIGHTRAG_WORKING_DIR` | `kg_v2/outputs/lightrag_v3` |
| LightRAG | `LIGHTRAG_QUERY_MODE` | `mix` |
| LightRAG | `LIGHTRAG_ENABLE_RERANKER` | `true` |
| LightRAG | `LIGHTRAG_TOP_K`, `LIGHTRAG_RERANK_TOP_N` | retrieval/rerank 数量。 |
| Neo4j | `NEO4J_URI` | 项目默认 `bolt://127.0.0.1:7688` |
| Neo4j | `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` | Neo4j 连接配置。 |

## 常用 CLI 参数

| 参数 | 作用 |
|---|---|
| `--question-root` | 题库根目录，如 `question` 或采样题库目录。 |
| `--out-root` / `--out-dir` | 输出根目录或指定输出目录。 |
| `--knowledge-mode` | `none`, `text_rag`, `kg_v1`, `kg_v3`, `hybrid`。 |
| `--kg-backend` | `neo4j`, `lightrag`, `hybrid`。 |
| `--kg-version` | `v1_directed`, `v3_fact_graph`；注意部分 legacy scripts 解析但未真正分支。 |
| `--query-mode` / `--kg-query-mode` | LightRAG query mode: `local/global/hybrid/mix`。 |
| `--embedding-provider/model/dim` | embedding 配置。 |
| `--reranker-provider/model/top-n` | reranker 配置。 |
| `--enable-reranker` / `--disable-reranker` | 是否启用 reranker。 |
| `--models` | 模型 alias，如 `deepseek glm`。 |
| `--datasets` | 指定 dataset 列表。 |
| `--limit` | 每个 dataset 截断数量，便于 smoke。 |
| `--resume` | 跳过已有答案/评分。 |
| `--dry-run` | 只检查路径/配置，不发起 LLM/API 调用。 |
| `--save-predictions` | objective 保存逐题预测。 |
| `--birdbase-xlsx`, `--order-xlsx` | structured/Table-KB 数据源。 |

## 常用命令

```powershell
python evaluation/knowledge_RAG/cli/doctor.py
python evaluation/knowledge_RAG/cli/doctor.py --check-api
```

```powershell
python evaluation/knowledge_RAG/cli/run_objective.py --question-root question --knowledge-mode kg_v3 --kg-backend neo4j --datasets QA-SC --limit 1 --dry-run
```

```powershell
python evaluation/knowledge_RAG/cli/run_objective.py --question-root question --knowledge-mode kg_v3 --models deepseek --datasets QA-SC QA-MC QA-SA Bird-Geo Bird-Taxonomy --save-predictions --resume
```

```powershell
python evaluation/knowledge_RAG/cli/run_subjective.py --question-root question --knowledge-mode kg_v3 --models deepseek --datasets Bird-Life Bird-Eco Bird-Con Bird-Comp Bird-Reason Bird-Plan --modes zero_shot few_shot cot --resume
```

```powershell
python evaluation/knowledge_RAG/cli/run_structured.py --question-root question --knowledge-mode kg_v3 --models deepseek --datasets List-Global Bird-ID Bird-Classify__Feature-to-Family --birdbase-xlsx data/BIRDBASE.xlsx --order-xlsx data/Order.xlsx --resume
```

```powershell
python evaluation/knowledge_RAG/cli/run_all.py --question-root question --knowledge-mode hybrid --out-root evaluation/output --models deepseek glm --resume
```

```powershell
python kg_v2/Step4_graph/smoke_v3_kg_e2e.py --intermediate-dir kg_v2/outputs/intermediate --graph-out-dir kg_v2/outputs/graph_v3_smoke --sample-size 20 --skip-neo4j
```

```powershell
python kg_v2/Step4_graph/export_lightrag_docs.py --graph-dir kg_v2/outputs/intermediate/truth_artifacts --out kg_v2/outputs/lightrag_v3/docs.jsonl
python kg_v2/Step4_graph/lightrag_ingest_v3.py --docs kg_v2/outputs/lightrag_v3/docs.jsonl --working-dir kg_v2/outputs/lightrag_v3 --embedding-model BAAI/bge-m3 --embedding-dim 1024 --llm-provider deepseek --llm-model deepseek-chat --query-mode mix --enable-reranker
```

## Windows pip launcher 建议

若 Windows 下 `pip` launcher 路径报错，优先使用：

```powershell
python -m pip install <package>
```

例如：

```powershell
python -m pip install neo4j pytest openpyxl python-dotenv
```
