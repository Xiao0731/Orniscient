# V3 KG E2E Smoke Report

- status: pass
- graph_out_dir: `kg_v2\outputs\graph_v3_smoke`
- source facts: `kg_v2\outputs\intermediate\claims\species_facts.jsonl`
- source evidences: `kg_v2\outputs\intermediate\claims\evidences.jsonl`

## Node Counts
- Taxon: 1
- Fact: 2
- Evidence: 2
- Chunk: 1

## Edge Counts
- HAS_FACT: 2
- SUPPORTED_BY: 2
- DERIVED_FROM: 2

## Neo4j
- enabled: False
- status: skipped
- query_rows: 0

## Retriever
- name: V3FactGraphRetriever
- used_v1_directed: False
- context_status: skipped
- fact_count: 0
- evidence_count: 0
- chunk_count: 0

## Errors