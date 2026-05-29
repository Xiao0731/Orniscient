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
python evaluation/knowledge_RAG/cli/run_objective.py --models deepseek --datasets QA-MC
```

```powershell
python evaluation/knowledge_RAG/cli/run_subjective.py --models deepseek --datasets Bird-Life --modes zero_shot
```

```powershell
python evaluation/knowledge_RAG/cli/run_structured.py --models deepseek --datasets Bird-ID
```

The default question root is `question/`, and the default knowledge mode is `none` for vanilla evaluation. Use `--knowledge-mode kg_v3` or `--knowledge-mode hybrid` for knowledge-enhanced runs; those modes require local KG artifacts that are not redistributed in the public repository. Structured tasks default to `data/BIRDBASE.xlsx` and `data/Order.xlsx`; override them with `--birdbase-xlsx` and `--order-xlsx` if needed.

Knowledge-enhanced objective example:

```powershell
python evaluation/knowledge_RAG/cli/run_objective.py --models deepseek --datasets Bird-Geo --knowledge-mode kg_v3
```

Larger paper-scale runs can still pass advanced options such as `--question-root`, `--out-root`, `--resume`, `--save-predictions`, `--kg-backend`, `--query-mode`, `--embedding-provider`, and reranker settings.

```powershell
python evaluation/knowledge_RAG/cli/run_all.py --knowledge-mode hybrid --models deepseek glm doubao hunyuan wenxin minimax --resume
```

`run_all.py` dispatches the three formal groups in order: objective, subjective, structured. You can run a smoke check without API calls:

```powershell
python evaluation/knowledge_RAG/cli/run_objective.py --datasets QA-SC --limit 1 --dry-run
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

For a one-question public demo preview without API:

```powershell
python evaluation/knowledge_RAG/demo_compare.py `
  --question "What are the main threats to the Southern Cassowary?" `
  --no-api
```

Full API mode generates both vanilla and KG-augmented answers:

```powershell
python evaluation/knowledge_RAG/demo_compare.py `
  --question "What are the main threats to the Southern Cassowary?"
```

Use an explicit target when the question does not uniquely name a demo taxon:

```powershell
python evaluation/knowledge_RAG/demo_compare.py `
  --question "What does it eat?" `
  --target "Southern Cassowary"
```

Use API diagnostics without printing full keys:

```powershell
python evaluation/knowledge_RAG/demo_compare.py `
  --question "What are the main threats to the Southern Cassowary?" `
  --debug-api-config `
  --ping-api
```

`demo_compare.py` is not a formal evaluation script: it does not score, judge, or aggregate. It is a one-question interface demo that prints the planner result, resolved target, vanilla answer, KG-augmented answer, retrieved facts/evidence/chunks, and the evidence-grounded prompt. Defaults are `--demo-data demo_data/sample_100_taxa`, `--model deepseek-chat`, and `--top-k 6`. Public demo-data mode covers only the 100 taxa listed in `sample_taxa.jsonl`; chunk previews are truncated excerpts and are not complete BOW raw text. If the question does not name a taxon in the demo subset, pass `--target` or choose one of the listed demo taxa.

In demo-data mode, `--planner deterministic` is the default. It resolves the target, routes the intent, chooses domains/predicates/chapters, and then the script performs deterministic graph retrieval. `--planner llm` asks the model only for query-planning JSON and validates it before deterministic graph retrieval. The planner does not receive gold answers or evaluation metadata, does not access files directly, and does not answer the question. Advanced options include `--demo-data`, `--model`, `--top-k`, `--planner`, `--target`, and `--max-evidence-per-chunk`.

The retrieved evidence trace is always printed after answer generation. If the API call fails, the command prints `[API Error]`, the sanitized error message, and then the retrieved evidence/chunks so target resolution and KG retrieval can still be debugged.

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
