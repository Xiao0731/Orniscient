from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class RetrievalRequest:
    question_id: str
    dataset: str
    question: str
    target_entity: str = ""
    options: dict[str, str] | None = None
    answer: Any = None
    mode: str = "zero_shot"
    type: str = ""
    raw_item: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalItem:
    item_type: str
    text: str
    score: float = 0.0
    source: str = ""
    taxon_id: str = ""
    taxon_name: str = ""
    fact_id: str = ""
    evidence_id: str = ""
    chunk_id: str = ""
    source_chapter: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    status: str
    knowledge_mode: str
    route: str
    items: list[RetrievalItem]
    rendered_context: str
    debug: dict[str, Any] = field(default_factory=dict)


class BaseRetriever(Protocol):
    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        ...
