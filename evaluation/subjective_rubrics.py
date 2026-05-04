from __future__ import annotations

from typing import Dict

DEFAULT_SUBJECTIVE_DATASET_ORDER = [
    "Bird-Comp",
    "Bird-Life",
    "Bird-Eco",
    "Bird-Plan",
    "Bird-Reason",
    "Bird-Con",
    "Bird-Classify",
]


SUBJECTIVE_RUBRICS: Dict[str, Dict[str, int]] = {
    "Bird-Comp": {
        "factual_accuracy": 40,
        "coverage_of_differences": 35,
        "hallucination_control": 25,
    },
    "Bird-Life": {
        "key_point_recall": 40,
        "numerical_accuracy": 35,
        "temporal_logic": 25,
    },
    "Bird-Eco": {
        "ecological_correctness": 40,
        "reasoning_logicality": 35,
        "impact_plausibility_and_grounding": 25,
    },
    "Bird-Plan": {
        "threat_priority": 40,
        "constraint_satisfaction": 35,
        "biological_specificity": 25,
    },
    "Bird-Reason": {
        "evidence_usage": 40,
        "reasoning_coherence": 35,
        "conclusion_correctness": 25,
    },
    "Bird-Con": {
        "factual_status_and_history_accuracy": 40,
        "key_point_coverage": 35,
        "grounding_and_hallucination_control": 25,
    },
    "Bird-Classify": {
        "taxonomic_accuracy": 40,
        "defining_trait_coverage": 35,
        "grounding_and_hallucination_control": 25,
    },
}


RUBRIC_DIMENSION_GUIDANCE: Dict[str, Dict[str, str]] = {
    "Bird-Comp": {
        "factual_accuracy": "Score factual correctness against the gold answer and evidence.",
        "coverage_of_differences": "Score whether the answer covers the key comparison points requested.",
        "hallucination_control": "Penalize unsupported claims or invented distinctions.",
    },
    "Bird-Life": {
        "key_point_recall": "Score recall of the important life-history facts needed by the question.",
        "numerical_accuracy": "Score correctness of quantities, durations, counts, and stated values.",
        "temporal_logic": "Score ordering and timing of biological events.",
    },
    "Bird-Eco": {
        "ecological_correctness": "Score correctness of ecological interpretation and categorization.",
        "reasoning_logicality": "Score the internal logic connecting traits, mechanisms, or effects.",
        "impact_plausibility_and_grounding": "Score whether predicted impacts stay plausible and grounded in the text.",
    },
    "Bird-Plan": {
        "threat_priority": "Score whether the plan targets the deadliest threat first.",
        "constraint_satisfaction": "Score whether the plan obeys the explicit scenario constraint.",
        "biological_specificity": "Score whether the plan is biologically specific to the species and evidence.",
    },
    "Bird-Reason": {
        "evidence_usage": "Score how well the answer uses the provided evidence and gold answer.",
        "reasoning_coherence": "Score the quality of the reasoning chain.",
        "conclusion_correctness": "Score whether the final conclusion is correct.",
    },
    "Bird-Con": {
        "factual_status_and_history_accuracy": "Score correctness of conservation status, trend, and historical facts.",
        "key_point_coverage": "Score whether the answer covers the key threats, trends, or historical drivers required by the question.",
        "grounding_and_hallucination_control": "Penalize unsupported claims and reward evidence-grounded answers.",
    },
    "Bird-Classify": {
        "taxonomic_accuracy": "Score correctness of order, family, and hierarchy-related statements.",
        "defining_trait_coverage": "Score whether the answer covers the defining traits requested by the question.",
        "grounding_and_hallucination_control": "Penalize unsupported taxonomy or invented family-level traits.",
    },
}


def get_rubric(dataset: str) -> Dict[str, int]:
    if dataset not in SUBJECTIVE_RUBRICS:
        raise KeyError(f"Unsupported subjective dataset: {dataset}")
    return SUBJECTIVE_RUBRICS[dataset]


def format_rubric_block(dataset: str) -> str:
    rubric = get_rubric(dataset)
    guidance = RUBRIC_DIMENSION_GUIDANCE[dataset]
    lines = ["Rubric dimensions (sum to 100):"]
    for dimension, max_score in rubric.items():
        lines.append(f"- {dimension}: 0-{max_score}. {guidance[dimension]}")
    return "\n".join(lines)
