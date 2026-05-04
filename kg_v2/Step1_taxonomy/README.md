# Step 1 Taxonomy Backbone

This step builds the canonical taxonomy backbone for KG V3.

## Goal

- Use `AviList` as the canonical taxonomy source
- Use `Clements` as the Cornell-compatible external compatibility layer
- Produce reusable taxonomy artifacts for later:
  - BOW species attachment
  - claim extraction normalization
  - Neo4j taxonomy import
  - LightRAG entity normalization

## Inputs

- `data/AviList-v2025-11Jun-extended.xlsx`
- `data/Clements_v2025-October-2025.xlsx`

## Outputs

Written to `kg_v2/outputs/intermediate/taxonomy/`:

- `avilist_rows.jsonl`
- `clements_rows.jsonl`
- `canonical_taxon_nodes.jsonl`
- `canonical_taxon_edges.jsonl`
- `taxonomy_crosswalks.jsonl`
- `taxonomy_aliases.jsonl`
- `taxonomy_conflicts.jsonl`
- `taxonomy_validation_report.json`
- `taxonomy_build_summary.json`

Copied for later graph import under `kg_v2/outputs/jsonl/`:

- `taxonomy_nodes.jsonl`
- `taxonomy_edges.jsonl`

## Non-Goals

This step does not:

- extract claims
- import Neo4j
- ingest LightRAG

It only prepares the taxonomy backbone and compatibility artifacts those later steps will depend on.
