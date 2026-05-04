# evaluation

## Files
- `model_registry.py`: model/base_url/env mapping for the enabled providers.
- `objective_eval.py`: objective evaluation runner for `QA-SC`, `QA-MC`, `QA-SA`, `Bird-Geo`, `Bird-Taxonomy`.
- `structured_eval.py`: minimal structured evaluation for `List-Global`, `Bird-ID`, and `Bird-Classify__Feature-to-Family`.
- `subjective_answer.py`: minimal candidate-answer generation for the five subjective datasets.
- `subjective_judge.py`: minimal single-judge scoring with `qwen3-max`.
- `subjective_aggregate.py`: summary/table generation from minimal judge outputs.
- `subjective_common.py`: shared loader, prompt, retry, parsing, and I/O utilities for the minimal pipeline.
- `subjective_rubrics.py`: dataset-specific three-dimension 100-point rubrics for subjective judging.
- `run_remaining_four_eval.py`: unified runner for `List-Global`, `Bird-ID`, `Bird-Con`, and `Bird-Classify`.
- `fewshot_examples/`: per-dataset few-shot examples used by `few_shot` mode.

## Supported objective metrics
- `QA-SC`, `Bird-Geo`: Accuracy / Exact Match
- `QA-MC`: Exact Match + set-F1
- `QA-SA`, `Bird-Taxonomy`: Exact Match + token-F1

## Usage
```bash
python evaluation/objective_eval.py --question-root question --out-dir evaluation/results_objective --limit 20
```

Run specific models:
```bash
python evaluation/objective_eval.py --question-root question --models deepseek qwen kimi glm
```

Run specific datasets:
```bash
python evaluation/objective_eval.py --question-root question --datasets QA-SC QA-MC QA-SA Bird-Geo Bird-Taxonomy
```

## Subjective evaluation
The subjective pipeline is reset to a minimal three-stage format:
- `answers/<mode>/<model>/<dataset>.jsonl`: each row contains only `question_id` and `answer`
- `judge_qwen/<mode>/<model>/<dataset>.jsonl`: each row contains only `question_id`, three rubric dimensions, and `score_total`
- `summaries/*.csv`: aggregated `full` and `core` tables, kept column-compatible with the old dual-judge summaries

Generate candidate answers:
```bash
python evaluation/subjective_answer.py --question-root question --out-dir evaluation/results_subjective --modes zero_shot few_shot cot --resume
```

Run single-judge scoring with `qwen3-max`:
```bash
python evaluation/subjective_judge.py --question-root question --out-dir evaluation/results_subjective --resume
```

Aggregate summary tables:
```bash
python evaluation/subjective_aggregate.py --out-dir evaluation/results_subjective
```

Run the full subjective pipeline in one command while keeping the three stages separate:
```bash
python evaluation/run_subjective_pipeline.py --question-root question --out-dir evaluation/results_subjective --resume --answer-question-workers 4 --judge-question-workers 4 --judge-workers 2
```

## Remaining four datasets
Structured datasets:
- `List-Global`
- `Bird-ID`
- `Bird-Classify__Feature-to-Family`

Judge datasets:
- `Bird-Con`
- `Bird-Classify` open types only: `Taxonomic Hierarchy`, `Taxon-to-Feature`

Run the structured branch only:
```bash
python evaluation/structured_eval.py --question-root question --out-dir evaluation/results_structured --models deepseek --limit 20 --resume
```

Run the unified remaining-four runner:
```bash
python evaluation/run_remaining_four_eval.py --question-root question --models deepseek --limit 20 --resume
```
