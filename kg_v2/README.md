# KG V2 Bird Knowledge Base

`kg_v2/` is an independent V2 knowledge-base construction pipeline for the bird dataset in this repository.

It builds three explicitly controlled layers:

1. Taxonomy tree: `Order -> Family -> Genus -> Species`
2. Family graph:
   - direct family evidence from `data/Order.xlsx`
   - derived family summaries aggregated from species facts
3. Species fact graph:
   - `Species -> HAS_FACT -> Fact -> OBJECT -> ConceptNode`
   - `Fact -> SUPPORTED_BY -> EvidenceChunk`

The schema is manual and fixed in code. No external GraphRAG tool is allowed to decide the ontology.

## Input Data

- Species-level source: `data/BOW/*.xlsx`
- Family / order-level source: `data/Order.xlsx`

## Key Design Decisions

- Multi-row species and multi-row family records are handled explicitly.
- Chapter headings are preserved and normalized to canonical aspect taxonomies.
- Shared concept nodes never carry raw source text.
- Raw evidence is only stored on `EvidenceChunk`.
- Direct family evidence and derived family summaries are represented by different node types.

## Minimal V1 Closure

The first version prioritizes:

- rule-based structure construction
- Neo4j import readiness
- `EvidenceChunk` vector index
- hybrid retrieval over graph plus evidence chunks

The default vector index backend is a zero-dependency local hashing embedding so the pipeline can run without extra vector libraries. You can switch to an OpenAI-compatible embedding endpoint with environment variables if needed.

## Typical Run

From the project root:

```bash
python kg_v2/run_build_kb_v2.py --bow-limit-files 1 --species-limit 50
```

For a full run:

```bash
python kg_v2/run_build_kb_v2.py
```

## Outputs

All generated artifacts are written under `kg_v2/outputs/`:

- `intermediate/`: parsed records, chunks, candidate labels, facts, family summaries, vector index
- `jsonl/`: graph node and edge JSONL files
- `neo4j_csv/`: optional CSV export for Neo4j import/debugging
- `logs/`: build logs and pipeline summaries

## Step 1 Taxonomy Backbone

Step 1 lives in `kg_v2/Step1_taxonomy/`.

- Canonical taxonomy source: `AviList`
- Compatibility source: `Clements`

It writes taxonomy backbone artifacts to `kg_v2/outputs/intermediate/taxonomy/`, including:

- `avilist_rows.jsonl`
- `clements_rows.jsonl`
- `canonical_taxon_nodes.jsonl`
- `canonical_taxon_edges.jsonl`
- `taxonomy_crosswalks.jsonl`
- `taxonomy_aliases.jsonl`
- `taxonomy_conflicts.jsonl`
- `taxonomy_validation_report.json`
- `taxonomy_build_summary.json`

It also copies:

- `canonical_taxon_nodes.jsonl -> outputs/jsonl/taxonomy_nodes.jsonl`
- `canonical_taxon_edges.jsonl -> outputs/jsonl/taxonomy_edges.jsonl`

This step prepares the taxonomy backbone for later claim normalization, Neo4j import, and LightRAG-controlled entity grounding. It does not yet perform claim extraction, Neo4j import, or LightRAG ingest.

## Step 2 Taxonomy Attachment

Step 2 lives in `kg_v2/Step2_attachment/`.

It performs:

- taxonomy attachment from parsed BOW species records/chunks to canonical Step 1 species nodes
- taxonomy attachment from parsed family records/chunks to canonical Step 1 family nodes
- chunk-level evidence attachment by mapping each chunk to the resolved canonical taxonomy id of its parent record

It writes attachment artifacts to `kg_v2/outputs/intermediate/attachments/`, including:

- `species_taxonomy_links.jsonl`
- `species_chunk_taxonomy_links.jsonl`
- `family_taxonomy_links.jsonl`
- `family_chunk_taxonomy_links.jsonl`
- `taxonomy_unresolved_species.jsonl`
- `taxonomy_unresolved_family.jsonl`
- `attachment_summary.json`

This step does not perform claim extraction, final fact-graph construction, Neo4j import, or LightRAG ingest. Its outputs are the attachment layer consumed by later Step 3 claim extraction and retrieval stages.

## Step 3 Claim / Fact / Evidence Extraction

Step 3 lives in `kg_v2/Step3_extraction/`.

It consumes Step 2 attachment files and the original parsed chunks, then writes a compact structured layer to `kg_v2/outputs/intermediate/claims/`:

- `species_claims.jsonl`
- `family_claims.jsonl`
- `species_facts.jsonl`
- `family_facts.jsonl`
- `evidences.jsonl`
- `fact_evidence_links.jsonl`
- `extraction_summary.json`

The production path is LLM-first extraction with strict JSON output and hard predicate/domain validation in Python. The default OpenAI-compatible extraction model is DeepSeek V3.2 via the `deepseek-chat` API model alias unless overridden by `KG_LLM_MODEL` or `OPENAI_MODEL`; Step 3 loads `.env` automatically, uses extraction temperature `1.0`, and retries malformed JSON/schema violations up to 2 times. The local `--extractor mock` mode is only for smoke testing when no OpenAI-compatible API is configured.

Step 3 keeps the dual-channel design: structured facts for benchmark/retrieval use, and raw evidence chunks as the fallback text channel. It does not perform Neo4j import, LightRAG ingest, final QA, offset-level evidence, or heavy rule extraction.
