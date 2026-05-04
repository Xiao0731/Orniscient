from __future__ import annotations


def append_context_to_prompt(base_prompt: str, rendered_context: str) -> str:
    context = str(rendered_context or "").strip()
    if not context:
        return base_prompt
    return f"{base_prompt.rstrip()}\n\n{context}"


def build_bird_id_prompt(question: str, clue_text: str, rendered_context: str) -> str:
    return "\n".join(
        [
            "You are solving a masked bird identification task.",
            "Do not assume the target species name is known.",
            "Use only the visible clues and candidate evidence below.",
            "Return strict JSON only.",
            '{"answer": ["guess1", "guess2", "guess3", "guess4", "guess5"]}',
            "",
            rendered_context.strip() or "No candidate context was retrieved.",
            "",
            "[Question]",
            str(question or "").strip(),
            "",
            "[Clue text]",
            str(clue_text or "").strip(),
        ]
    )
