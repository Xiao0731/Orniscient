"""JSON and JSONL helpers shared across kg_v2 steps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_jsonl(path: str | Path) -> list[dict]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    rows: list[dict] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, records: Iterable[dict]) -> Path:
    file_path = Path(path)
    _ensure_dir(file_path.parent)
    with file_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return file_path


def write_json(path: str | Path, payload: dict | list) -> Path:
    file_path = Path(path)
    _ensure_dir(file_path.parent)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return file_path

