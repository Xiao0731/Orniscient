# Step 2: Taxonomy Attachment + Evidence Attachment

Step 2 attaches parsed BOW species-level and family-level materials to the canonical taxonomy backbone built in Step 1.

It does two things only:

1. taxonomy attachment
   - map `species_records.jsonl` and `species_chunks.jsonl` to canonical species nodes
   - map `family_records.jsonl` and `family_chunks.jsonl` to canonical family nodes
2. evidence attachment
   - keep record-level and chunk-level mappings to canonical taxonomy ids
   - preserve unresolved cases explicitly for later review

This step does not perform claim extraction, final fact-graph construction, Neo4j import, or LightRAG ingest.

## Inputs

- `outputs/intermediate/taxonomy/canonical_taxon_nodes.jsonl`
- `outputs/intermediate/taxonomy/canonical_taxon_edges.jsonl`
- `outputs/intermediate/taxonomy/taxonomy_crosswalks.jsonl`
- `outputs/intermediate/taxonomy/taxonomy_aliases.jsonl`
- `outputs/intermediate/taxonomy/taxonomy_conflicts.jsonl`
- `outputs/intermediate/species_records.jsonl`
- `outputs/intermediate/species_chunks.jsonl`
- `outputs/intermediate/family_records.jsonl`
- `outputs/intermediate/family_chunks.jsonl`

## Outputs

Artifacts are written to `outputs/intermediate/attachments/`:

- `species_taxonomy_links.jsonl`
- `species_chunk_taxonomy_links.jsonl`
- `family_taxonomy_links.jsonl`
- `family_chunk_taxonomy_links.jsonl`
- `taxonomy_unresolved_species.jsonl`
- `taxonomy_unresolved_family.jsonl`
- `attachment_summary.json`

## Downstream Use

- Step 3 claim extraction can reuse canonical taxonomy ids directly without re-solving name alignment.
- Later retrieval or LightRAG stages can start from canonical taxon ids and fetch supporting BOW chunks through these attachment files.

