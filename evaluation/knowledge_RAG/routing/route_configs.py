from __future__ import annotations

from dataclasses import dataclass, field


DATASET_GROUPS: dict[str, list[str]] = {
    "objective": ["QA-SC", "QA-MC", "QA-SA", "Bird-Geo", "Bird-Taxonomy"],
    "subjective": [
        "Bird-Life",
        "Bird-Eco",
        "Bird-Con",
        "Bird-Comp",
        "Bird-Reason",
        "Bird-Plan",
        "Bird-Classify-Type1",
    ],
    "structured": [
        "List-Global",
        "Bird-ID",
        "Bird-Classify__Feature-to-Family",
        "Bird-Classify-Type2",
    ],
}
DATASET_GROUPS["all"] = [
    *DATASET_GROUPS["objective"],
    *DATASET_GROUPS["subjective"],
    *DATASET_GROUPS["structured"],
]


def dataset_group_for(dataset: str, subtype: str = "") -> str:
    dataset = (dataset or "").strip()
    subtype = (subtype or "").strip().lower()
    if dataset in DATASET_GROUPS["objective"]:
        return "objective"
    if dataset in {"List-Global", "Bird-ID", "Bird-Classify__Feature-to-Family", "Bird-Classify-Type2"}:
        return "structured"
    if dataset in {"Bird-Classify", "Bird-Classify-Type1"}:
        if "feature-to-family" in subtype or "order-family" in subtype or "identify" in subtype:
            return "structured"
        return "subjective"
    if dataset in DATASET_GROUPS["subjective"]:
        return "subjective"
    return "unknown"


@dataclass(frozen=True)
class RouteConfig:
    route: str
    context_style: str = "compact"
    preferred_domains: list[str] = field(default_factory=list)
    max_facts: int = 8
    max_chunks: int = 5
    use_table_kb: bool = False
    use_reverse_retrieval: bool = False
    forbid_gold: bool = False
