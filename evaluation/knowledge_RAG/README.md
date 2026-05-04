# Unified Knowledge-RAG Runtime

This directory adds a unified layer over the existing `evaluation/text_RAG/` and `evaluation/kg_RAG/` implementations. The old directories are not deleted: Text-RAG is an important baseline, and KG-RAG contains V1 DIRECTED graph retrieval, V3 fact graph retrieval, Table-KB, Bird-ID reverse retrieval, and family-table logic.

## Knowledge Modes

- `none`: Vanilla model evaluation with no external knowledge.
- `text_rag`: BOW species/family chunk retrieval from the old Text-RAG baseline.
- `kg_v1`: legacy Neo4j DIRECTED-edge KG-RAG.
- `kg_v3`: V3 Taxon-Fact-Evidence-Chunk graph retrieval.
- `hybrid`: V3 Neo4j fact graph + LightRAG mix + reranker + Table-KB where appropriate.

Paper naming can map these to Vanilla, Text-RAG, KG-RAG v1, KG-RAG v3, and Hybrid KG-RAG.

## API Roles

This project does not require an OpenAI API key by default. DeepSeek is used for LLM generation, answer generation, and judging. Embedding and reranking are separate services.

For the current API-compatible setup, use SiliconFlow for BGE models:

- `EMBEDDING_PROVIDER=api_compatible`, `EMBEDDING_MODEL=BAAI/bge-m3`, `EMBEDDING_API_BASE=https://api.siliconflow.cn/v1`
- `RERANKER_PROVIDER=api_compatible`, `RERANKER_MODEL=BAAI/bge-reranker-v2-m3`, `RERANKER_API_BASE=https://api.siliconflow.cn/v1`

`.env.example` is only a template. Keep real keys in local `.env` and do not commit them. `doctor.py` prints only API key suffixes.

## Dataset Groups

- `objective`: `QA-SC`, `QA-MC`, `QA-SA`, `Bird-Geo`, `Bird-Taxonomy`.
- `subjective`: `Bird-Life`, `Bird-Eco`, `Bird-Con`, `Bird-Comp`, `Bird-Reason`, `Bird-Plan`, plus `Bird-Classify-Type1` when the task asks for open feature details given a family/taxon.
- `structured`: `List-Global`, `Bird-ID`, `Bird-Classify__Feature-to-Family`, plus `Bird-Classify-Type2` when the task asks for order/family identification from a description.

`Bird-Con` belongs to the subjective pipeline and should be judged with LLM-as-a-Judge. `List-Global` and `Bird-ID` belong to the structured pipeline. `Bird-Classify` is routed by subtype: Feature-to-Family/order-family identification is structured, while feature-detail generation is subjective.

`remaining_four` is a historical engineering name only. Keep the old entry points for reproducibility, but do not use `remaining_four` as a formal paper grouping.

## Commands

```powershell
python evaluation/knowledge_RAG/cli/run_objective.py --question-root question --knowledge-mode kg_v3 --models deepseek qwen glm --datasets QA-SC QA-MC QA-SA Bird-Geo Bird-Taxonomy --save-predictions --resume
```

```powershell
python evaluation/knowledge_RAG/cli/run_subjective.py --question-root question --knowledge-mode kg_v3 --models deepseek glm --datasets Bird-Life Bird-Eco Bird-Con Bird-Comp Bird-Reason Bird-Plan --modes zero_shot few_shot cot --resume
```

```powershell
python evaluation/knowledge_RAG/cli/run_structured.py --question-root question --knowledge-mode kg_v3 --models deepseek glm --datasets List-Global Bird-ID Bird-Classify --birdbase-xlsx data/BIRDBASE.xlsx --order-xlsx data/Order.xlsx --resume
```

```powershell
python evaluation/knowledge_RAG/cli/run_all.py --question-root question --knowledge-mode hybrid --out-root evaluation/output --models deepseek glm doubao hunyuan wenxin minimax --resume
```

`run_all.py` dispatches the three formal groups in order: objective, subjective, structured. You can run a smoke check without API calls:

```powershell
python evaluation/knowledge_RAG/cli/run_objective.py --knowledge-mode kg_v3 --kg-backend neo4j --datasets QA-SC --limit 1 --dry-run
```

For environment diagnosis:

```powershell
python evaluation/knowledge_RAG/cli/doctor.py
```

Dry-run does not call embedding or reranker APIs. To explicitly test API connectivity with one short embedding request and one short rerank request:

```powershell
python evaluation/knowledge_RAG/cli/doctor.py --check-api
```

To validate the V3 Taxon -> Fact -> Evidence -> Chunk graph chain without Neo4j:

```powershell
python kg_v2/Step4_graph/smoke_v3_kg_e2e.py --skip-neo4j
```

## Output Layout

Unified commands write:

- `run_manifest.json`
- `context_logs/`
- `answers/`
- `judge_results/`
- `predictions/`
- `summaries/`
- `errors/`

Output names follow `evaluation/output/results_{task_type}_{knowledge_mode}_{question_root_tag}/`.

## Why Not Merge Old Directories

Text-RAG must remain a clean baseline. KG-RAG has several graph/table/reverse-retrieval paths that would become muddy if physically merged. The unified runtime keeps old implementations as compatibility layers while giving experiments one command-line interface, one manifest format, and consistent context logs.
