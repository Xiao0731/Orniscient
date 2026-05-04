#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step2 attachment QA check (fixed for current Step2 output format).

Run from kg_v2 root:
    python Step2_attachment/test_step2_fixed.py
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Iterator


def read_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def norm_text(value: object) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() == "nan":
        return ""
    return " ".join(s.split())


class Step2Tester:
    def __init__(self, taxonomy_dir: Path, attachment_dir: Path, sample_size: int, seed: int) -> None:
        self.taxonomy_dir = taxonomy_dir
        self.attachment_dir = attachment_dir
        self.sample_size = sample_size
        self.seed = seed

        self.required_files = {
            "canonical_taxon_nodes": taxonomy_dir / "canonical_taxon_nodes.jsonl",
            "species_links": attachment_dir / "species_taxonomy_links.jsonl",
            "species_chunk_links": attachment_dir / "species_chunk_taxonomy_links.jsonl",
            "family_links": attachment_dir / "family_taxonomy_links.jsonl",
            "family_chunk_links": attachment_dir / "family_chunk_taxonomy_links.jsonl",
            "species_unresolved": attachment_dir / "taxonomy_unresolved_species.jsonl",
            "family_unresolved": attachment_dir / "taxonomy_unresolved_family.jsonl",
            "summary": attachment_dir / "attachment_summary.json",
        }

    def check_required_files(self) -> dict:
        missing = [name for name, path in self.required_files.items() if not path.exists()]
        return {"ok": len(missing) == 0, "missing": missing}

    def load(self) -> None:
        self.nodes = list(read_jsonl(self.required_files["canonical_taxon_nodes"]))
        self.node_by_id = {n["taxon_id"]: n for n in self.nodes}

        self.species_links = list(read_jsonl(self.required_files["species_links"]))
        self.species_chunk_links = list(read_jsonl(self.required_files["species_chunk_links"]))
        self.family_links = list(read_jsonl(self.required_files["family_links"]))
        self.family_chunk_links = list(read_jsonl(self.required_files["family_chunk_links"]))
        self.species_unresolved_file = list(read_jsonl(self.required_files["species_unresolved"]))
        self.family_unresolved_file = list(read_jsonl(self.required_files["family_unresolved"]))
        self.summary = read_json(self.required_files["summary"])

    def _is_attached(self, row: dict) -> bool:
        return norm_text(row.get("resolution_status")).lower() == "attached"

    def _build_species_parent_lookup(self) -> dict[str, dict]:
        # current species_chunk_taxonomy_links.jsonl only carries species_name
        lookup = {}
        for row in self.species_links:
            key = norm_text(row.get("species_name"))
            if key and self._is_attached(row):
                lookup[key] = row
        return lookup

    def _build_family_parent_lookup(self) -> dict[tuple[str, str], dict]:
        lookup = {}
        for row in self.family_links:
            key = (norm_text(row.get("family_name")), norm_text(row.get("order_name")))
            if key[0] and self._is_attached(row):
                lookup[key] = row
        return lookup

    def check_summary_consistency(self) -> dict:
        s = self.summary
        errors = []

        species_attached = sum(1 for row in self.species_links if self._is_attached(row))
        species_unresolved = len(self.species_links) - species_attached

        family_attached = sum(1 for row in self.family_links if self._is_attached(row))
        family_unresolved = len(self.family_links) - family_attached

        species_chunk_attached = sum(1 for row in self.species_chunk_links if self._is_attached(row))
        family_chunk_attached = sum(1 for row in self.family_chunk_links if self._is_attached(row))

        expected_pairs = [
            ("species_record_total", len(self.species_links)),
            ("species_record_attached", species_attached),
            ("species_record_unresolved", species_unresolved),
            ("species_chunk_total", len(self.species_chunk_links)),
            ("species_chunk_attached", species_chunk_attached),
            ("family_record_total", len(self.family_links)),
            ("family_record_attached", family_attached),
            ("family_record_unresolved", family_unresolved),
            ("family_chunk_total", len(self.family_chunk_links)),
            ("family_chunk_attached", family_chunk_attached),
        ]

        for key, expected in expected_pairs:
            actual = s.get(key)
            if actual != expected:
                errors.append(f"{key}: summary={actual}, expected={expected}")

        if len(self.species_unresolved_file) != species_unresolved:
            errors.append(
                f"taxonomy_unresolved_species.jsonl count={len(self.species_unresolved_file)}, expected={species_unresolved}"
            )
        if len(self.family_unresolved_file) != family_unresolved:
            errors.append(
                f"taxonomy_unresolved_family.jsonl count={len(self.family_unresolved_file)}, expected={family_unresolved}"
            )

        return {"ok": len(errors) == 0, "errors": errors}

    def check_species_links(self) -> dict:
        valid_methods = {
            "DIRECT_SCI_MATCH",
            "ALIAS_MATCH",
            "CROSSWALK_MATCH",
            "FAMILY_ORDER_ASSISTED_MATCH",
            "UNRESOLVED",
        }
        errors = []

        for row in self.species_links:
            method = row.get("match_method")
            if method not in valid_methods:
                errors.append(f"Invalid species match_method: {method}")
                continue

            if not self._is_attached(row):
                # unresolved rows are allowed to have blank canonical ids
                continue

            taxon_id = row.get("canonical_taxon_id", "")
            node = self.node_by_id.get(taxon_id)
            if not taxon_id or not node:
                errors.append(f"Missing canonical species node for species link: {row.get('species_name')}")
                continue

            if node.get("rank") != "species":
                errors.append(f"Species link points to non-species node: {taxon_id} rank={node.get('rank')}")

            if row.get("canonical_scientific_name") and row.get("canonical_scientific_name") != node.get("scientific_name"):
                errors.append(
                    f"Canonical scientific name mismatch for species {row.get('species_name')}: "
                    f"link={row.get('canonical_scientific_name')} node={node.get('scientific_name')}"
                )

        return {"ok": len(errors) == 0, "errors": errors}

    def check_family_links(self) -> dict:
        valid_methods = {
            "DIRECT_FAMILY_MATCH",
            "ORDER_ASSISTED_FAMILY_MATCH",
            "ALIAS_MATCH",
            "UNRESOLVED",
        }
        errors = []

        for row in self.family_links:
            method = row.get("match_method")
            if method not in valid_methods:
                errors.append(f"Invalid family match_method: {method}")
                continue

            if not self._is_attached(row):
                continue

            taxon_id = row.get("canonical_family_id", "")
            node = self.node_by_id.get(taxon_id)
            if not taxon_id or not node:
                errors.append(f"Missing canonical family node for family link: {row.get('family_name')}")
                continue

            if node.get("rank") != "family":
                errors.append(f"Family link points to non-family node: {taxon_id} rank={node.get('rank')}")

            if row.get("canonical_family_name") and row.get("canonical_family_name") != node.get("scientific_name"):
                errors.append(
                    f"Canonical family name mismatch for family {row.get('family_name')}: "
                    f"link={row.get('canonical_family_name')} node={node.get('scientific_name')}"
                )

        return {"ok": len(errors) == 0, "errors": errors}

    def check_species_chunk_inheritance(self) -> dict:
        lookup = self._build_species_parent_lookup()
        errors = []

        for row in self.species_chunk_links:
            if not self._is_attached(row):
                continue

            key = norm_text(row.get("species_name"))
            parent = lookup.get(key)
            if not parent:
                errors.append(f"No attached parent species record link found for chunk {row.get('chunk_id')}")
                continue

            if row.get("canonical_taxon_id", "") != parent.get("canonical_taxon_id", ""):
                errors.append(
                    f"Species chunk {row.get('chunk_id')} drifted canonical id: "
                    f"chunk={row.get('canonical_taxon_id')} parent={parent.get('canonical_taxon_id')}"
                )

            if row.get("canonical_scientific_name", "") != parent.get("canonical_scientific_name", ""):
                errors.append(
                    f"Species chunk {row.get('chunk_id')} drifted canonical scientific name: "
                    f"chunk={row.get('canonical_scientific_name')} parent={parent.get('canonical_scientific_name')}"
                )

        return {"ok": len(errors) == 0, "errors": errors}

    def check_family_chunk_inheritance(self) -> dict:
        lookup = self._build_family_parent_lookup()
        errors = []

        for row in self.family_chunk_links:
            if not self._is_attached(row):
                continue

            key = (norm_text(row.get("family_name")), norm_text(row.get("order_name")))
            parent = lookup.get(key)
            if not parent:
                errors.append(f"No attached parent family record link found for chunk {row.get('chunk_id')}")
                continue

            if row.get("canonical_family_id", "") != parent.get("canonical_family_id", ""):
                errors.append(
                    f"Family chunk {row.get('chunk_id')} drifted canonical id: "
                    f"chunk={row.get('canonical_family_id')} parent={parent.get('canonical_family_id')}"
                )

            if row.get("canonical_family_name", "") != parent.get("canonical_family_name", ""):
                errors.append(
                    f"Family chunk {row.get('chunk_id')} drifted canonical family name: "
                    f"chunk={row.get('canonical_family_name')} parent={parent.get('canonical_family_name')}"
                )

        return {"ok": len(errors) == 0, "errors": errors}

    def sample_rows(self) -> dict:
        rnd = random.Random(self.seed)
        return {
            "species_link_samples": rnd.sample(self.species_links, min(self.sample_size, len(self.species_links))),
            "species_chunk_link_samples": rnd.sample(self.species_chunk_links, min(self.sample_size, len(self.species_chunk_links))),
            "family_link_samples": rnd.sample(self.family_links, min(self.sample_size, len(self.family_links))),
            "family_chunk_link_samples": rnd.sample(self.family_chunk_links, min(self.sample_size, len(self.family_chunk_links))),
            "species_unresolved_samples": rnd.sample(self.species_unresolved_file, min(self.sample_size, len(self.species_unresolved_file))),
            "family_unresolved_samples": rnd.sample(self.family_unresolved_file, min(self.sample_size, len(self.family_unresolved_file))),
        }

    def run(self) -> dict:
        file_check = self.check_required_files()
        if not file_check["ok"]:
            return {"summary": {"status": "fail"}, "file_check": file_check}

        self.load()

        summary_check = self.check_summary_consistency()
        species_check = self.check_species_links()
        family_check = self.check_family_links()
        species_chunk_check = self.check_species_chunk_inheritance()
        family_chunk_check = self.check_family_chunk_inheritance()

        all_ok = all([
            file_check["ok"],
            summary_check["ok"],
            species_check["ok"],
            family_check["ok"],
            species_chunk_check["ok"],
            family_chunk_check["ok"],
        ])

        return {
            "summary": {
                "status": "pass" if all_ok else "fail",
                "species_record_total": len(self.species_links),
                "species_attached": sum(1 for row in self.species_links if self._is_attached(row)),
                "species_unresolved": sum(1 for row in self.species_links if not self._is_attached(row)),
                "species_chunk_total": len(self.species_chunk_links),
                "family_record_total": len(self.family_links),
                "family_attached": sum(1 for row in self.family_links if self._is_attached(row)),
                "family_unresolved": sum(1 for row in self.family_links if not self._is_attached(row)),
                "family_chunk_total": len(self.family_chunk_links),
            },
            "file_check": file_check,
            "summary_check": summary_check,
            "species_link_check": species_check,
            "family_link_check": family_check,
            "species_chunk_inheritance_check": species_chunk_check,
            "family_chunk_inheritance_check": family_chunk_check,
            "samples": self.sample_rows(),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="QA test for Step2 taxonomy attachment.")
    parser.add_argument("--taxonomy-dir", type=Path, default=Path("outputs/intermediate/taxonomy"))
    parser.add_argument("--attachment-dir", type=Path, default=Path("outputs/intermediate/attachments"))
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("outputs/intermediate/attachments/step2_quality_check_report.json"))
    args = parser.parse_args()

    tester = Step2Tester(args.taxonomy_dir, args.attachment_dir, args.sample_size, args.seed)
    report = tester.run()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] report written to: {args.output}")
    print(f"[SUMMARY] status={report['summary']['status']}")

    if report["summary"]["status"] == "pass":
        print(
            f"[COUNTS] species={report['summary']['species_attached']}/{report['summary']['species_record_total']} "
            f"chunks={report['summary']['species_chunk_total']} | "
            f"family={report['summary']['family_attached']}/{report['summary']['family_record_total']} "
            f"chunks={report['summary']['family_chunk_total']}"
        )
    else:
        for section in (
            "file_check",
            "summary_check",
            "species_link_check",
            "family_link_check",
            "species_chunk_inheritance_check",
            "family_chunk_inheritance_check",
        ):
            payload = report.get(section, {})
            errs = payload.get("errors", [])
            if not payload.get("ok", True):
                print(f"[FAIL] {section}: {len(errs)} errors")
                for err in errs[:20]:
                    print("  -", err)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())