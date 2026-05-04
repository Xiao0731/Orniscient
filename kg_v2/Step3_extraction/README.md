# Step 3: Claim / Fact / Evidence Extraction

Step 3 consumes the taxonomy-attached chunks produced by Step 2 and extracts a controlled, lightweight claim/fact/evidence layer.

It does not redo taxonomy alignment. Species and family canonical ids come from Step 2 attachment files.

## Layers

- `Claim`: close to the source chunk. It records the extracted predicate, object/value, qualifiers, source metadata, and a short evidence quote.
- `Fact`: a lightly merged claim group keyed by subject, predicate, object/value, and normalized qualifiers.
- `Evidence`: chunk-level evidence records containing source metadata and short quotes.

## Strategy

The intended production mode is LLM-first extraction with strict JSON output. The script handles orchestration only:

- chapter routing
- allowed predicate/domain validation
- schema checks
- lightweight qualifier normalization
- claim deduplication and fact merging
- evidence binding

For local smoke tests without API credentials, the runner also supports `--extractor mock`, which emits schema-compatible lightweight examples. Use `--extractor llm` for real OpenAI-compatible extraction.

The default OpenAI-compatible extraction model is DeepSeek V3.2 via the `deepseek-chat` API model alias unless `KG_LLM_MODEL` or `OPENAI_MODEL` overrides it. Step 3 loads the repository root `.env` automatically. The default extraction temperature is `1.0`, and malformed JSON or schema violations retry up to 2 times with the same temperature.

## Not In Scope

Step 3 does not perform:

- Neo4j import
- LightRAG ingest
- offset-level evidence
- heavy regex/rule extraction
- broad object ontology learning
- final QA or retrieval

## Dual Channel

The structured fact channel is intentionally compact and budgeted. Raw evidence chunks remain available as the fallback text channel for retrieval and long-form synthesis.

## Run

From `kg_v2/`:

```bash
python Step3_extraction/run_extract_claims_and_facts.py --extractor mock --max-species-chunks 200 --max-family-chunks 50
```

For real LLM extraction, configure `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and optionally `KG_LLM_MODEL`, then run:

```bash
python Step3_extraction/run_extract_claims_and_facts.py --extractor llm
```
