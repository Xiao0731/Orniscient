from __future__ import annotations

"""
export_final_questions.py
=========================

Strip generation-time / review-time fields from accepted jsonl files and export
only the clean benchmark schema used at evaluation time.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict


FINAL_TOP_LEVEL_KEYS = {
    "question_id",
    "dataset",
    "knowledge_domain",
    "type",
    "target_entity",
    "question",
    "options",
    "answer",
    "provenance",
}


def clean_item(item: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    # type defaults to General for single-type datasets if missing
    qtype = item.get("type") or item.get("question_type") or "General"

    out["question_id"] = item.get("question_id")
    out["dataset"] = item.get("dataset")
    out["knowledge_domain"] = item.get("knowledge_domain")
    out["type"] = qtype
    out["target_entity"] = item.get("scientific_name") or item.get("target_entity")
    out["question"] = item.get("question")

    if "options" in item:
        out["options"] = item["options"]

    out["answer"] = item.get("answer")

    provenance = item.get("provenance", {}) or {}
    cleaned_prov: Dict[str, Any] = {
        "source_db": provenance.get("source_db", "BOW")
    }

    # Preserve chapter/quote as lists if user wants list schema.
    source_chapter = provenance.get("source_chapter")
    exact_quote = provenance.get("exact_quote")

    if source_chapter is not None:
        cleaned_prov["source_chapter"] = source_chapter if isinstance(source_chapter, list) else [source_chapter]
    if exact_quote is not None:
        cleaned_prov["exact_quote"] = exact_quote if isinstance(exact_quote, list) else [exact_quote]
    if "reasoning_chain" in provenance:
        cleaned_prov["reasoning_chain"] = provenance["reasoning_chain"]

    out["provenance"] = cleaned_prov
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Accepted jsonl path")
    parser.add_argument("output", help="Clean exported jsonl path")
    args = parser.parse_args()

    inp = Path(args.input)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    with inp.open("r", encoding="utf-8") as fin, out.open("w", encoding="utf-8") as fout:
        for line in fin:
            item = json.loads(line)
            cleaned = clean_item(item)
            fout.write(json.dumps(cleaned, ensure_ascii=False) + "\n")

    print(f"Clean export written to: {out}")


if __name__ == "__main__":
    main()
