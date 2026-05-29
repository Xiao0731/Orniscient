# Orniscient 100-Taxon Demo Graph

This directory contains a compact Taxon-Fact-Evidence-Chunk demo graph for 100 selected bird taxa.

The demo is intended for interface testing and expert inspection. It is not a substitute for the full authorized local BOW-derived knowledge base.

Files:

- `sample_taxa.jsonl`: selected taxon nodes and name metadata.
- `sample_facts.jsonl`: all exported facts for the selected 100 taxa. Facts are not capped per taxon.
- `sample_evidences.jsonl`: evidence nodes linked to exported facts.
- `sample_fact_evidence_links.jsonl`: fact-to-evidence edges.
- `sample_chunks.jsonl`: chunk nodes with metadata and short text previews only.
- `sample_graph_summary.json`: export statistics and data-use note.
- `sample_questions.jsonl`: example free-form questions.

Data-use note:

Full BOW raw text is not redistributed here. Chunk nodes contain short previews capped at 700 characters, plus metadata needed to inspect the Taxon -> Fact -> Evidence -> Chunk path.

Example:

```powershell
python evaluation/knowledge_RAG/demo_compare.py --question "What are the main threats to the Southern Cassowary?" --demo-data demo_data/sample_100_taxa --top-k 5 --no-api
```
