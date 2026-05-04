import pytest

from evaluation.knowledge_RAG.formatting.prompt_builder import build_bird_id_prompt
from evaluation.knowledge_RAG.retrievers.bird_id_reverse_retriever import assert_no_gold_leak


def test_bird_id_prompt_does_not_include_gold_answer():
    prompt = build_bird_id_prompt(
        "A masked bird has a red bill and wetland habits.",
        "red bill; wetland",
        "[Candidate Species]\n1. Candidate A\n2. Candidate B",
    )
    assert_no_gold_leak(prompt, "Gold species")


def test_bird_id_gold_leak_guard_fails_when_gold_present():
    with pytest.raises(AssertionError):
        assert_no_gold_leak("Candidate list includes Gold species", "Gold species")

