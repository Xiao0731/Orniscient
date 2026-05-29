# Evaluation Compatibility After Question Update

## Findings
- No evaluated entry point was found to require literal [the bird] placeholders.
- Updated question and answer fields are still read through the same JSONL fields used before replacement.
- target_entity remains available for objective prompts, subjective target metadata, and target-aware retrieval.
- Subjective target-aware prompts may contain the target twice: once as Target entity metadata and once in the cleaned question. This is redundant but acceptable and does not change leakage behavior.
- Bird-ID, Bird-Classify reverse identification, and List-Global remain anonymous by design.
- The active knowledge_RAG entry points live under evaluation/knowledge_RAG/cli/, not directly under evaluation/knowledge_RAG/. README examples should use the cli paths.

## Entry Points
| Entry | Path | Exists | --help OK | Assumes literal placeholder |
|---|---|---:|---:|---:|
| knowledge_cli_objective | `evaluation\knowledge_RAG\cli\run_objective.py` | yes | yes | no |
| knowledge_cli_subjective | `evaluation\knowledge_RAG\cli\run_subjective.py` | yes | yes | no |
| knowledge_cli_structured | `evaluation\knowledge_RAG\cli\run_structured.py` | yes | yes | no |
| legacy_objective | `evaluation\objective_eval.py` | yes | no | no |
| legacy_subjective_pipeline | `evaluation\run_subjective_pipeline.py` | yes | no | no |
| legacy_subjective_answer | `evaluation\subjective_answer.py` | yes | no | no |
| legacy_structured | `evaluation\structured_eval.py` | yes | no | no |
| legacy_remaining_four | `evaluation\run_remaining_four_eval.py` | yes | no | no |
| requested_non_cli_objective | `evaluation\knowledge_RAG\run_objective.py` | no | no | no |
| requested_non_cli_subjective | `evaluation\knowledge_RAG\run_subjective.py` | no | no | no |
| requested_non_cli_structured | `evaluation\knowledge_RAG\run_structured.py` | no | no | no |

## Dataset Placeholder Compatibility
| Dataset | Rows | Rows with placeholders | Expected anonymous rows | Unexpected placeholder rows | Warning |
|---|---:|---:|---:|---:|---:|
| Bird-Classify | 500 | 0 | 0 | 0 | no |
| Bird-Comp | 986 | 0 | 0 | 0 | no |
| Bird-Con | 217 | 0 | 0 | 0 | no |
| Bird-Eco | 216 | 0 | 0 | 0 | no |
| Bird-Geo | 448 | 0 | 0 | 0 | no |
| Bird-ID | 990 | 0 | 0 | 0 | no |
| Bird-Life | 446 | 0 | 0 | 0 | no |
| Bird-Plan | 63 | 0 | 0 | 0 | no |
| Bird-Reason | 219 | 0 | 0 | 0 | no |
| Bird-Taxonomy | 840 | 4 | 4 | 0 | no |
| List-Global | 200 | 0 | 0 | 0 | no |
| QA-MC | 1235 | 0 | 0 | 0 | no |
| QA-SA | 1232 | 0 | 0 | 0 | no |
| QA-SC | 2450 | 26 | 26 | 0 | no |

## Prompt Preview Notes
### objective
```text
You are answering an ornithology benchmark question.
Answer using ONLY a compact JSON object.
Do not include markdown, explanation, or extra keys.
For species-identification style questions, if needed, answer with a specific species-level name rather than a genus/family or vague category.

Dataset: QA-MC
Target entity: Pink-headed Duck
Question: Based on historical records, which of the following modern-day countries or regions were part of Pink-headed Duck's known distribution?
Options:
A. India
B. Bangladesh
C. Myanmar
D. Nepal
E. Bhutan
```
### subjective
```text
You are answering an ornithology benchmark question. Return strict JSON only with exactly one key: answer.

Task: answer the following bird-related subjective question.
Dataset: Bird-Life
Question type: Courtship & Mating
Knowledge domain: Ecology and Life History
Target entity: Bernier's Teal
Question: Based on the provided monograph, describe the courtship and mating system of Bernier's Teal, including details on sexual behaviors, vocalizations, and pair-bond dynamics.
Return only: {"answer": "..."}
```
### structured
```text

```
