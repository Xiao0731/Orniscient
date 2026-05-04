# Text-RAG v2 for Bird Benchmark

`evaluation/text_RAG/` is the Text-RAG baseline. It should not be deleted or archived. It is used to compare raw BOW chunk retrieval against V3 KG-RAG and hybrid KG-RAG.

This version uses the KG-v2 pre-split BOW chunks instead of rebuilding coarse chunks from XLSX/cache:

- `kg_v2/outputs/intermediate/species_chunks.jsonl`
- `kg_v2/outputs/intermediate/family_chunks.jsonl`

## Key policies

1. **Normal species-level tasks** use exact metadata matching on `target_entity` against `common_name` or `species_name`, then rank only that bird's chunks by dataset-level chapter hints. The retriever does **not** search the chunk body for the target name.
2. **Bird-ID** is leakage-sensitive because the species identity is the answer. It uses blind retrieval from species chunks based on the question/clue text and redacts entity names from the context.
3. **Bird-Classify** is also leakage-sensitive because the family/order is the answer. It uses blind retrieval from family chunks and redacts family/order metadata.
4. **List-Global** is skipped for Text-RAG because it is a BIRDBASE structured filtering task rather than a single-target BOW text task.

## Suggested subjective run

```powershell
python evaluation\text_RAG\text_rag_run_subjective_pipeline.py `
  --question-root question `
  --out-dir evaluation/results_subjective_text_rag_v2 `
  --fewshot-root evaluation/fewshot_examples `
  --models deepseek qwen kimi `
  --datasets Bird-Life Bird-Eco Bird-Con Bird-Comp Bird-Reason Bird-Plan `
  --modes zero_shot few_shot cot `
  --limit 50 `
  --species-chunks-jsonl kg_v2/outputs/intermediate/species_chunks.jsonl `
  --family-chunks-jsonl kg_v2/outputs/intermediate/family_chunks.jsonl `
  --top-k 10 `
  --max-context-chars 9000 `
  --answer-max-tokens 2048
```

For Bird-ID and Bird-Classify, report them separately as blind Text-RAG diagnostics rather than the main entity-aware Text-RAG comparison.
