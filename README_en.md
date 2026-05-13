# Orniscient

**Orniscient** is a bird ecology knowledge reasoning project that integrates a domain-specific benchmark, a multi-source knowledge base prototype, and a knowledge-enhanced evaluation harness for large language models.

> **Orniscient = Ornithology + Omniscient**  
> The goal is to build a verifiable, traceable, and extensible infrastructure for bird ecology knowledge reasoning.

<div align="center">

[English](./README_en.md) | [简体中文](./README.md)

</div>

---

## Overview

Orniscient is organized around a **Benchmark–Knowledge Base–Harness** framework. It builds a multi-level benchmark for bird ecology reasoning, organizes multi-source knowledge resources, and provides a unified evaluation harness for comparing vanilla and knowledge-enhanced LLM settings.

This repository is associated with the undergraduate thesis **“Species Knowledge Base Construction and Reasoning with LLM Agents.”** The project is conducted in collaboration with the Cornell bird-related research/data side and has obtained research-use authorization for **Birds of the World (BOW)**. Due to data licensing restrictions, raw BOW texts, full derived chunks, complete knowledge base artifacts, and large-scale evaluation logs are not redistributed in this repository.

![Framework Overview](docs/assets/framework_overview.png)

---

## Background

Large language models have shown strong capabilities in general question answering, text generation, and complex reasoning. However, in specialized domains such as bird ecology, models still face several challenges:

- **Outdated knowledge**: bird taxonomy, nomenclature, and conservation status may change with updated checklists and authoritative databases;
- **Factual hallucination**: models may generate plausible but unsupported statements;
- **Taxonomic confusion**: closely related species, subspecies, families, and historical taxonomic changes are difficult to distinguish;
- **Insufficient evidence utilization**: models may fail to correctly use provided textual evidence;
- **Long-context instability**: natural history descriptions are often long and distributed across multiple chapters;
- **Structured-task difficulty**: tasks such as global set enumeration, reverse species identification, and constrained conservation planning cannot be solved reliably by free-form generation alone.

Bird ecology knowledge is inherently complex. It involves strict taxonomic hierarchies, dynamic checklists, geographic distributions, migration, habitats, ecological functions, and long-form natural history texts. Orniscient is therefore not merely a question set. It is designed as a systematic framework that connects data organization, benchmark design, knowledge base construction, and automated evaluation.

---

## Core Contributions

The current version of Orniscient contains four major components:

1. **Bird Ecology Benchmark**  
   A 14-dataset benchmark for evaluating LLM capabilities across knowledge retrieval, domain reasoning, and complex logical reasoning.

2. **Multi-source Knowledge Base Prototype**  
   A knowledge organization pipeline that includes a canonical taxonomy backbone, BOW text evidence store, Claim–Fact–Evidence–Qualifier factual evidence chain, BIRDBASE table knowledge, and a Taxon–Fact–Evidence–Chunk graph structure.

3. **knowledge_RAG Harness**  
   A unified knowledge-enhanced evaluation framework for objective tasks, open-ended generation tasks, and structured tasks.

4. **Evaluation-driven Analysis**  
   Multi-model comparison under vanilla and knowledge-enhanced settings, with analysis of when knowledge access helps, when it fails, and how the effect depends on knowledge coverage, retrieval recall, context construction, and model evidence utilization.

---

## Repository Structure

```text
orniscient/
├── evaluation/                  # Evaluation pipelines and scoring scripts
│   ├── objective_eval.py         # Objective evaluation
│   ├── subjective_answer.py      # Open-ended answer generation
│   ├── subjective_judge.py       # LLM-as-a-Judge scoring
│   ├── subjective_aggregate.py   # Subjective score aggregation
│   ├── structured_eval.py        # Structured task evaluation
│   ├── run_subjective_pipeline.py
│   ├── run_remaining_four_eval.py
│   ├── text_RAG/                 # Text-RAG evaluation modules
│   ├── kg_RAG/                   # KG-RAG modules
│   ├── knowledge_RAG/            # Unified knowledge-enhanced harness
│   ├── fewshot_examples/         # Few-shot examples
│   └── figures/                  # Figures and visualizations
│
├── kg_v2/                        # Multi-source knowledge base construction
│   ├── Step1_taxonomy/           # Canonical taxonomy backbone construction
│   ├── Step2_attachment/         # BOW record attachment and chunk alignment
│   ├── Step3_extraction/         # Claim/Fact/Evidence/Qualifier extraction
│   ├── Step4_graph/              # Taxon-Fact-Evidence-Chunk graph construction
│   ├── builders/                 # KB building utilities
│   ├── extractors/               # Information extraction modules
│   ├── parsers/                  # Data parsers
│   ├── rag/                      # Knowledge-enhanced retrieval modules
│   ├── renderers/                # Rendering and export utilities
│   ├── schema/                   # Schema definitions
│   ├── utils/                    # Utility functions
│   ├── validators/               # Data validation modules
│   └── run_build_kb_v2.py        # KB construction entry point
│
├── question/                     # Benchmark question files
│   ├── QA-SC/
│   ├── QA-MC/
│   ├── QA-SA/
│   ├── Bird-Geo/
│   ├── Bird-Taxonomy/
│   ├── Bird-Life/
│   ├── Bird-Eco/
│   ├── Bird-Con/
│   ├── Bird-Comp/
│   ├── Bird-Reason/
│   ├── Bird-Plan/
│   ├── Bird-ID/
│   ├── List-Global/
│   └── Bird-Classify/
│
├── scripts/                      # Utility scripts
├── tests/                        # Test scripts
├── md/                           # Project notes and intermediate documents
├── reports/                      # Report materials and summaries
├── docs/assets/                  # Image assets used in README
├── prompt.py                     # Prompt templates and generation logic
├── benchmark_complete.py         # Benchmark construction script
├── kb_benchmark_queries.py       # KB-aware benchmark query utilities
├── docker-compose.yml            # Optional service configuration
├── .env.example                  # Environment variable template
├── .gitignore
├── README.md                     # English README
└── README_zh.md                  # Chinese README
```

---

## Benchmark Design

The Orniscient benchmark consists of **14 datasets** organized into three levels: **knowledge retrieval, domain reasoning and analysis, and complex logical reasoning**. The goal is not only to increase the number of questions, but also to characterize the capability boundaries of LLMs across different cognitive difficulties and bird ecology knowledge types.

### Knowledge Mind Maps

The following two figures illustrate the benchmark knowledge organization for knowledge acquisition and logical reasoning tasks.

![Knowledge Acquisition](docs/assets/Knowledge%20Acquisition.png)

![Logical Reasoning](docs/assets/Logical%20Reasoning.png)

### Level 1: Knowledge Retrieval

Level 1 evaluates whether models can retrieve and answer basic bird ecology facts. These tasks are usually grounded in local evidence from BOW or auxiliary data sources.

| Dataset | Description |
|---|---|
| `QA-SC` | Single-choice questions for basic factual recognition |
| `QA-MC` | Multiple-choice questions requiring multiple correct facts |
| `QA-SA` | Short-answer questions for factual answer generation |

Typical knowledge dimensions include morphology, diet, distribution, habitat, taxonomy, conservation status, breeding behavior, and ecological habits.

### Level 2: Domain Reasoning and Analysis

Level 2 evaluates domain-specific reasoning over taxonomy, geography, ecology, conservation, breeding biology, and fine-grained species comparison.

| Dataset | Description |
|---|---|
| `Bird-Geo` | Geographic distribution, habitat, migration, and spatial boundary reasoning |
| `Bird-Taxonomy` | Taxonomic hierarchy, nomenclature changes, split/lump reasoning |
| `Bird-Life` | Breeding biology, life-history patterns, and behavioral sequence reasoning |
| `Bird-Eco` | Diet, foraging strategy, ecological function, and causal reasoning |
| `Bird-Con` | Conservation status, threat analysis, and conservation risk reasoning |
| `Bird-Comp` | Fine-grained comparison between similar species or related taxa |
| `Bird-Classify` | Taxonomic classification or feature-to-family reasoning from descriptions |

The focus of this level is not textual repetition, but evidence-grounded summarization, comparison, judgment, and explanation.

### Level 3: Complex Logical Reasoning

Level 3 targets more complex tasks involving long-context reasoning, multi-hop inference, reverse identification, constrained planning, and global set enumeration.

| Dataset | Description |
|---|---|
| `Bird-Reason` | Cross-chapter and cross-evidence reasoning, including falsification and correction |
| `Bird-Plan` | Conservation planning under budget, terrain, legal, and threat constraints |
| `Bird-ID` | Reverse species identification from masked morphology, vocal, geographic, and ecological descriptions |
| `List-Global` | Global species set enumeration under structured constraints |

This level emphasizes factual consistency, evidence traceability, and reasoning stability under complex constraints.

---

## Knowledge Base

Orniscient adopts a hybrid multi-source knowledge organization strategy. Instead of forcing all information into a single graph, it combines text evidence, structured tables, a taxonomy backbone, and graph links according to task needs.

### Multi-source Knowledge Organization

The knowledge base prototype is built around the following resources:

- **Birds of the World (BOW)**: the core textual knowledge source for species-level and family-level natural history records;
- **AviList / Clements**: used for constructing and aligning the canonical taxonomy backbone;
- **BIRDBASE**: used for structured attribute filtering and candidate constraints;
- **Order-level and auxiliary taxonomy tables**: used for hierarchy validation and supplementary mapping.

Due to BOW licensing restrictions, raw BOW texts and full derived chunks are not redistributed in this repository.

### Claim–Fact–Evidence–Qualifier Modeling

On top of BOW chunks, the project defines four core knowledge objects:

| Object | Meaning |
|---|---|
| `Claim` | Natural-language assertions extracted from source text |
| `Fact` | Normalized structured factual units |
| `Evidence` | Source evidence and provenance supporting claims/facts |
| `Qualifier` | Contextual conditions such as geography, season, sex, age, subspecies scope, time, or uncertainty |

This layer is designed not as simple triple extraction, but as a factual evidence layer with grounding and contextual constraints.

### Taxon–Fact–Evidence–Chunk Graph

The graph structure links taxonomic entities, structured facts, evidence spans, and original text chunks:

```text
Taxon -> Fact -> Evidence -> Chunk
```

This makes it possible to trace structured facts back to source evidence and to perform task-aware retrieval by taxon, fact type, or evidence source.

### Knowledge Graph Subgraph Example

The following figure shows a local subgraph example from the bird ecology knowledge graph.

![Knowledge Graph Subgraph Example](docs/assets/kg_subgraph_example.png)

### Taxonomy Tree and Checklist Crosswalk Examples

The project also contains taxonomy tree and checklist crosswalk visualizations for demonstrating canonical taxonomy construction and compatibility-layer alignment across different checklists.

![Taxonomy Tree](docs/assets/taxonomy_tree_accipitriformes.svg)

![Checklist Crosswalk](docs/assets/checklist_crosswalk_accipitriformes.svg)

---

## Harness

The `knowledge_RAG` Harness connects benchmark questions, models, knowledge sources, prompt modes, retrievers, scorers, and result logs into a unified evaluation framework. It is not a single scoring script, but an engineering layer for organizing reproducible experiments.

### Supported Capabilities

- Unified multi-model invocation;
- Multi-dataset task routing;
- zero-shot / few-shot / CoT prompt modes;
- Vanilla vs. knowledge-enhanced comparison;
- Objective / subjective / structured evaluation workflows;
- Automatic scoring and LLM-as-a-Judge evaluation;
- Run manifests, context logs, resume logic, dry-run checks, and error tracking;
- Result aggregation and visualization.

### Evaluation Task Types

| Type | Datasets | Main Metrics |
|---|---|---|
| Objective tasks | `QA-SC`, `QA-MC`, `QA-SA`, `Bird-Geo`, `Bird-Taxonomy` | Accuracy, Exact Match, F1 |
| Open-ended tasks | `Bird-Life`, `Bird-Eco`, `Bird-Con`, `Bird-Comp`, `Bird-Reason`, `Bird-Plan` | LLM-as-a-Judge |
| Structured tasks | `Bird-ID`, `List-Global`, `Bird-Classify` | Recall, weighted top-5 accuracy, hierarchical accuracy |

### Knowledge Modes

The project supports or reserves several knowledge access modes:

| Mode | Meaning |
|---|---|
| `none` | Vanilla model without external knowledge |
| `text_rag` | Text retrieval over BOW chunks |
| `kg_v1` | Early knowledge graph prototype |
| `kg_v3` | Schema-driven knowledge graph prototype |
| `hybrid` | Hybrid access to text, graph, and table knowledge |

Knowledge enhancement is not assumed to monotonically improve all tasks. One goal of the harness is to analyze where knowledge access helps, where it fails, and whether failures are caused by knowledge coverage, retrieval recall, context construction, or model evidence utilization.

---

## Data Notice

This repository is intended for thesis review and research demonstration. The project has obtained research-use authorization for BOW, but due to licensing restrictions, public releases do not include:

- Raw Birds of the World texts;
- Full BOW-derived text chunks;
- API keys or local `.env` files;
- Complete knowledge base generated artifacts;
- Neo4j database dumps;
- LightRAG working caches;
- Full model outputs, judge logs, context logs, and large-scale evaluation results;
- Large model weights or checkpoints.

The repository may contain benchmark question files for thesis review. For public release, complete question files should be replaced with sanitized demo samples according to data licensing requirements.

To reproduce the full pipeline, users should prepare authorized data sources and configure local paths and API keys according to `.env.example`.

---

## Usage

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/orniscient.git
cd orniscient
```

### 2. Create a Python environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

If `requirements.txt` is provided:

```bash
pip install -r requirements.txt
```

If not, install the required packages manually according to the modules used in `evaluation/` and `kg_v2/`.

### 4. Configure environment variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then fill in local paths and model API keys in `.env`.

### 5. Run objective evaluation

```bash
python evaluation/objective_eval.py \
  --models deepseek qwen kimi \
  --datasets QA-SC QA-MC QA-SA Bird-Geo Bird-Taxonomy \
  --question-root question
```

### 6. Run open-ended evaluation pipeline

```bash
python evaluation/run_subjective_pipeline.py \
  --models deepseek qwen kimi \
  --datasets Bird-Life Bird-Eco Bird-Con Bird-Comp Bird-Reason Bird-Plan \
  --modes zero_shot few_shot cot \
  --question-root question \
  --fewshot-root evaluation/fewshot_examples
```

### 7. Run structured task evaluation

```bash
python evaluation/run_remaining_four_eval.py \
  --models deepseek qwen kimi \
  --datasets Bird-ID List-Global Bird-Classify Bird-Con \
  --question-root question
```

### 8. Build the knowledge base prototype

```bash
python kg_v2/run_build_kb_v2.py
```

Actual commands may vary depending on local data paths, model providers, knowledge modes, and experiment settings.

---

## Repository Status

Completed components:

- Bird ecology benchmark with 14 datasets;
- Multi-source knowledge base schema and construction pipeline;
- Canonical taxonomy backbone;
- BOW record attachment and chunk alignment;
- Claim–Fact–Evidence–Qualifier modeling;
- Taxon–Fact–Evidence–Chunk graph design;
- Objective / subjective / structured evaluation workflows;
- knowledge_RAG Harness;
- Vanilla vs. knowledge-enhanced model comparison;
- Project structure, execution flow, and reproducibility notes.

Future work:

- Full Neo4j graph deployment;
- LightRAG mix retrieval integration;
- Reranker ablation experiments;
- Bird-ID candidate recall optimization;
- Deterministic List-Global output improvement;
- LangGraph-based or similar bird expert agent prototype;
- Evaluation-driven system self-iteration.

---

## License and Data Access

The source code in this repository is intended for academic research and thesis demonstration.

Raw data and complete derived artifacts from restricted sources are not redistributed. Please ensure that any use of external data sources complies with their respective licenses and terms of use.

---

## Acknowledgements

Orniscient starts from a simple question: can bird ecology knowledge be organized not as scattered long-form texts, tables, and checklists, but as a verifiable, searchable, reason-able, and evaluable knowledge infrastructure?

By combining a benchmark, a knowledge base prototype, and an evaluation harness, this project aims to provide a reusable starting point for future bird ecology knowledge bases, knowledge-enhanced QA systems, and bird expert agents.
