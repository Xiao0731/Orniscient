from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRUTH_DIR = ROOT / "kg_v2" / "outputs" / "intermediate" / "truth_artifacts"
DEFAULT_OUT = ROOT / "kg_v2" / "outputs" / "lightrag_v3" / "docs.jsonl"

DOMAIN_BY_CHAPTER = {
    "distribution": "DistributionAndMovement",
    "movement": "DistributionAndMovement",
    "migration": "DistributionAndMovement",
    "habitat": "HabitatAndEcology",
    "diet": "DietAndForaging",
    "foraging": "DietAndForaging",
    "breeding": "BreedingAndLifeHistory",
    "nest": "BreedingAndLifeHistory",
    "egg": "BreedingAndLifeHistory",
    "conservation": "Conservation",
    "status": "Conservation",
    "identification": "Identification",
    "systematics": "Taxonomy",
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _domain_for_fact(props: dict[str, Any]) -> str:
    chapter = _clean(props.get("source_chapter")).lower()
    predicate = _clean(props.get("predicate") or props.get("fact_type")).lower()
    haystack = f"{chapter} {predicate}"
    for key, domain in DOMAIN_BY_CHAPTER.items():
        if key in haystack:
            return domain
    return "GeneralFacts"


def _fact_value(props: dict[str, Any]) -> str:
    if _clean(props.get("object_name")):
        return _clean(props.get("object_name"))
    if _clean(props.get("value_text")):
        return _clean(props.get("value_text"))
    lo = props.get("value_min")
    hi = props.get("value_max")
    unit = _clean(props.get("unit"))
    if lo not in ("", None) and hi not in ("", None):
        return f"{lo}-{hi} {unit}".strip()
    if lo not in ("", None):
        return f"{lo} {unit}".strip()
    return ""


def _truncate(text: str, max_chars: int) -> str:
    text = _clean(text)
    return text[:max_chars].rstrip()


def _index_evidence(edges: list[dict[str, Any]], evidences: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    evidence_by_id = {row.get("id"): row for row in evidences}
    by_fact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        if edge.get("type") not in {"SUPPORTED_BY", "EVIDENCED_BY", "HAS_EVIDENCE"}:
            continue
        fact_id = str(edge.get("source", ""))
        evidence = evidence_by_id.get(edge.get("target"))
        if evidence:
            by_fact[fact_id].append(evidence)
    return by_fact


def export_lightrag_docs(graph_dir: str | Path, out: str | Path, *, max_facts_per_doc: int = 40) -> list[dict[str, Any]]:
    graph_path = Path(graph_dir)
    if (graph_path / "truth_artifacts").exists():
        graph_path = graph_path / "truth_artifacts"
    if not graph_path.exists():
        graph_path = DEFAULT_TRUTH_DIR

    facts = _load_jsonl(graph_path / "fact_nodes.jsonl")
    evidences = _load_jsonl(graph_path / "evidence_nodes.jsonl")
    edges = _load_jsonl(graph_path / "edges.jsonl")
    evidence_by_fact = _index_evidence(edges, evidences)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        props = dict(fact.get("properties") or {})
        species = _clean(props.get("species") or props.get("subject_name"))
        if not species:
            continue
        domain = _domain_for_fact(props)
        grouped[(species, domain)].append(fact)

    docs: list[dict[str, Any]] = []
    for (species, domain), rows in sorted(grouped.items()):
        first_props = dict(rows[0].get("properties") or {})
        family = _clean(first_props.get("family"))
        order = _clean(first_props.get("order_name"))
        title = f"{species} | {domain}"
        lines = [
            f"# {title}",
            "",
            "Taxonomy:",
            " > ".join(part for part in [order, family, species] if part),
            "",
            "Facts:",
        ]
        chapters: set[str] = set()
        for fact in rows[:max(1, int(max_facts_per_doc))]:
            props = dict(fact.get("properties") or {})
            predicate = _clean(props.get("predicate") or props.get("fact_type"))
            value = _fact_value(props)
            chapter = _clean(props.get("source_chapter"))
            if chapter:
                chapters.add(chapter)
            lines.append(f"- {predicate}: {value}".rstrip())
            evid_rows = evidence_by_fact.get(fact.get("id"), [])
            evidence_text = ""
            chunk_id = ""
            if evid_rows:
                eprops = dict(evid_rows[0].get("properties") or {})
                evidence_text = _truncate(eprops.get("cleaned_text") or eprops.get("raw_text") or "", 500)
                chunk_id = _clean(eprops.get("chunk_id"))
            if evidence_text:
                lines.append(f"  Evidence: {evidence_text}")
            if chapter or chunk_id:
                lines.append(f"  Source: BOW | {chapter or 'Unknown'} | chunk_id={chunk_id}")

        doc_id = f"{species}::{domain}"
        docs.append(
            {
                "doc_id": doc_id,
                "title": title,
                "content": "\n".join(lines).strip(),
                "metadata": {
                    "taxon_id": species,
                    "rank": "species",
                    "scientific_name": species,
                    "english_name_primary": "",
                    "fact_domain": domain,
                    "source_chapters": sorted(chapters),
                },
            }
        )

    _write_jsonl(Path(out), docs)
    return docs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export controlled V3 Fact/Evidence docs for LightRAG.")
    parser.add_argument("--graph-dir", type=str, default=str(DEFAULT_TRUTH_DIR))
    parser.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--max-facts-per-doc", type=int, default=40)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    docs = export_lightrag_docs(args.graph_dir, args.out, max_facts_per_doc=args.max_facts_per_doc)
    print(json.dumps({"out": args.out, "doc_count": len(docs)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
