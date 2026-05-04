from __future__ import annotations

from typing import Any


def format_options(options: Any) -> str:
    if not options:
        return ""

    lines: list[str] = []
    if isinstance(options, dict):
        for key, value in options.items():
            lines.append(f"{key}. {value}")
        return "\n".join(lines)

    if isinstance(options, list):
        for idx, value in enumerate(options):
            if isinstance(value, dict):
                label = value.get("label") or value.get("key") or chr(ord("A") + idx)
                text = value.get("text") or value.get("value") or value.get("option") or ""
                lines.append(f"{label}. {text}")
            else:
                lines.append(f"{chr(ord('A') + idx)}. {value}")
        return "\n".join(lines)

    return str(options).strip()


def _render_kg_context(kg_context: str) -> str:
    text = str(kg_context or "").strip()
    if not text or text.startswith("[NO_KG_CONTEXT"):
        return "No graph context was retrieved."
    return text


def build_kg_augmented_prompt(q: dict[str, Any], kg_context: str) -> str:
    question = str(q.get("question", "")).strip()
    dataset = str(q.get("dataset", "")).strip()
    options_block = format_options(q.get("options"))
    rendered_context = _render_kg_context(kg_context)

    parts = [
        "You are answering an ornithology benchmark question.",
        "",
        "Use the following Neo4j knowledge graph context as external evidence.",
        "The graph context consists of retrieved relation descriptions from a species knowledge graph.",
        "If the graph context is insufficient or irrelevant, rely on the question itself and avoid hallucination.",
        "",
        "[Knowledge Graph Context]",
        rendered_context,
        "",
        "[Question]",
        question,
    ]

    if options_block:
        parts.extend(
            [
                "",
                "[Options]",
                options_block,
                "",
                "Return only the final answer option letters.",
                "For multi-answer questions, separate letters with commas, such as A,C,E.",
            ]
        )
        if dataset != "QA-MC":
            parts[-2] = "Return only the final answer option letter, such as A, B, C, or D."
            parts[-1] = ""
    else:
        parts.extend(["", "Return a concise final answer."])

    return "\n".join(part for part in parts if part != "")


def build_kg_subjective_prompt(question: str, kg_context: str) -> str:
    rendered_context = _render_kg_context(kg_context)
    parts = [
        "You are answering an ornithology benchmark question.",
        "",
        "Use the following Neo4j knowledge graph context as external evidence.",
        "The graph context contains two parts:",
        "1. Graph relation facts: concise relation-level facts retrieved from the target species node.",
        "2. Brief related-node notes: short descriptions of neighboring graph nodes, included only as supplementary background.",
        "Use relation facts as primary evidence. Use node notes only when they are directly relevant.",
        "Please ground your answer in the graph context when it is relevant. If the graph context is insufficient, answer cautiously and avoid unsupported claims.",
        "",
        "[Knowledge Graph Context]",
        rendered_context,
        "",
        "[Question]",
        str(question or "").strip(),
        "",
        "Return a clear and concise answer.",
    ]
    return "\n".join(parts)
