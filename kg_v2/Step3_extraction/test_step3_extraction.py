#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step3 extraction QA test.

Run from kg_v2 root:
    python Step3_extraction/test_step3_extraction.py
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, List


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


ALLOWED_BY_CHAPTER = {
    "Systematics": {
        "HAS_SUBSPECIES", "HAS_GEOGRAPHIC_VARIATION", "HYBRIDIZES_WITH",
        "RELATED_TO", "HAS_CLASSIFICATION_HISTORY", "HAS_TAXONOMIC_NOTE",
    },
    "Field Identification": {
        "HAS_BODY_LENGTH", "HAS_BODY_MASS", "HAS_PLUMAGE_TRAIT", "HAS_MOLT_PATTERN",
        "HAS_SEXUAL_DIMORPHISM", "HAS_AGE_DIMORPHISM", "HAS_DIAGNOSTIC_TRAIT",
        "HAS_STRUCTURE_TRAIT",
    },
    "Plumages, Molts, and Structure": {
        "HAS_BODY_LENGTH", "HAS_BODY_MASS", "HAS_PLUMAGE_TRAIT", "HAS_MOLT_PATTERN",
        "HAS_SEXUAL_DIMORPHISM", "HAS_AGE_DIMORPHISM", "HAS_DIAGNOSTIC_TRAIT",
        "HAS_STRUCTURE_TRAIT",
    },
    "Distribution": {
        "OCCURS_IN", "ENDEMIC_TO", "BREEDS_IN", "WINTERS_IN",
        "MIGRATES_VIA", "HAS_MIGRATION_PATTERN", "HAS_ELEVATION_RANGE",
        "HAS_DISTRIBUTION_NOTE",
    },
    "Habitat": {
        "INHABITS_BIOME", "USES_MICROHABITAT",
        "EATS_CATEGORY", "EATS_ITEM", "FORAGES_BY", "FORAGES_IN_STRATUM", "HAS_ECOLOGICAL_ROLE",
    },
    "Movements and Migration": {
        "OCCURS_IN", "ENDEMIC_TO", "BREEDS_IN", "WINTERS_IN",
        "MIGRATES_VIA", "HAS_MIGRATION_PATTERN", "HAS_ELEVATION_RANGE",
        "HAS_DISTRIBUTION_NOTE",
    },
    "Diet and Foraging": {
        "EATS_CATEGORY", "EATS_ITEM", "FORAGES_BY", "FORAGES_IN_STRATUM", "HAS_ECOLOGICAL_ROLE",
    },
    "Sounds and Vocal Behavior": {
        "HAS_VOCALIZATION_TYPE", "CALLS_DURING", "HAS_NONVOCAL_SOUND", "HAS_SOUND_DIAGNOSTIC",
        "HAS_SOCIAL_BEHAVIOR", "HAS_TERRITORIAL_BEHAVIOR", "HAS_LOCOMOTION_STYLE",
        "HAS_DAILY_ACTIVITY_PATTERN", "HAS_COURTSHIP_BEHAVIOR", "HAS_AGONISTIC_BEHAVIOR",
    },
    "Behavior": {
        "HAS_VOCALIZATION_TYPE", "CALLS_DURING", "HAS_NONVOCAL_SOUND", "HAS_SOUND_DIAGNOSTIC",
        "HAS_SOCIAL_BEHAVIOR", "HAS_TERRITORIAL_BEHAVIOR", "HAS_LOCOMOTION_STYLE",
        "HAS_DAILY_ACTIVITY_PATTERN", "HAS_COURTSHIP_BEHAVIOR", "HAS_AGONISTIC_BEHAVIOR",
        "BREEDS_DURING", "NESTS_AT", "HAS_NEST_STRUCTURE", "HAS_EGG_TRAIT", "HAS_CLUTCH_SIZE",
        "HAS_INCUBATION_PERIOD", "HAS_FLEDGING_PERIOD", "HAS_PARENTAL_ROLE",
        "HAS_DEVELOPMENT_NOTE", "HAS_DEMOGRAPHIC_NOTE",
    },
    "Breeding": {
        "BREEDS_DURING", "NESTS_AT", "HAS_NEST_STRUCTURE", "HAS_EGG_TRAIT", "HAS_CLUTCH_SIZE",
        "HAS_INCUBATION_PERIOD", "HAS_FLEDGING_PERIOD", "HAS_PARENTAL_ROLE",
        "HAS_DEVELOPMENT_NOTE", "HAS_DEMOGRAPHIC_NOTE",
    },
    "Demography and Populations": {
        "BREEDS_DURING", "NESTS_AT", "HAS_NEST_STRUCTURE", "HAS_EGG_TRAIT", "HAS_CLUTCH_SIZE",
        "HAS_INCUBATION_PERIOD", "HAS_FLEDGING_PERIOD", "HAS_PARENTAL_ROLE",
        "HAS_DEVELOPMENT_NOTE", "HAS_DEMOGRAPHIC_NOTE",
        "HAS_IUCN_STATUS", "HAS_POPULATION_TREND", "THREATENED_BY",
        "HAS_CONSERVATION_ACTION", "INTERACTS_WITH_HUMANS", "REQUIRES_RESEARCH_ON",
    },
    "Conservation and Management": {
        "HAS_IUCN_STATUS", "HAS_POPULATION_TREND", "THREATENED_BY",
        "HAS_CONSERVATION_ACTION", "INTERACTS_WITH_HUMANS", "REQUIRES_RESEARCH_ON",
    },
    "Relationships with People": {
        "HAS_IUCN_STATUS", "HAS_POPULATION_TREND", "THREATENED_BY",
        "HAS_CONSERVATION_ACTION", "INTERACTS_WITH_HUMANS", "REQUIRES_RESEARCH_ON",
    },
    "Priorities for Future Research": {
        "HAS_IUCN_STATUS", "HAS_POPULATION_TREND", "THREATENED_BY",
        "HAS_CONSERVATION_ACTION", "INTERACTS_WITH_HUMANS", "REQUIRES_RESEARCH_ON",
    },
    "Introduction": None,
    "About the Author(s)": set(),
    "Unknown": None,
}


class Step3Tester:
    def __init__(self, claims_dir: Path, intermediate_dir: Path, attachments_dir: Path, sample_size: int, seed: int) -> None:
        self.claims_dir = claims_dir
        self.intermediate_dir = intermediate_dir
        self.attachments_dir = attachments_dir
        self.sample_size = sample_size
        self.seed = seed

        self.required_files = {
            "species_claims": claims_dir / "species_claims.jsonl",
            "family_claims": claims_dir / "family_claims.jsonl",
            "species_facts": claims_dir / "species_facts.jsonl",
            "family_facts": claims_dir / "family_facts.jsonl",
            "evidences": claims_dir / "evidences.jsonl",
            "fact_evidence_links": claims_dir / "fact_evidence_links.jsonl",
            "summary": claims_dir / "extraction_summary.json",
            "species_chunks": intermediate_dir / "species_chunks.jsonl",
            "family_chunks": intermediate_dir / "family_chunks.jsonl",
            "species_attach": attachments_dir / "species_chunk_taxonomy_links.jsonl",
            "family_attach": attachments_dir / "family_chunk_taxonomy_links.jsonl",
        }

    def check_required_files(self) -> dict:
        missing = [name for name, path in self.required_files.items() if not path.exists()]
        return {"ok": len(missing) == 0, "missing": missing}

    def load(self) -> None:
        self.species_claims = list(read_jsonl(self.required_files["species_claims"]))
        self.family_claims = list(read_jsonl(self.required_files["family_claims"]))
        self.species_facts = list(read_jsonl(self.required_files["species_facts"]))
        self.family_facts = list(read_jsonl(self.required_files["family_facts"]))
        self.evidences = list(read_jsonl(self.required_files["evidences"]))
        self.fact_evidence_links = list(read_jsonl(self.required_files["fact_evidence_links"]))
        self.summary = read_json(self.required_files["summary"])

        self.species_chunks = list(read_jsonl(self.required_files["species_chunks"]))
        self.family_chunks = list(read_jsonl(self.required_files["family_chunks"]))
        self.species_attach = list(read_jsonl(self.required_files["species_attach"]))
        self.family_attach = list(read_jsonl(self.required_files["family_attach"]))

        self.chunk_by_id: Dict[str, dict] = {}
        for row in self.species_chunks + self.family_chunks:
            cid = norm_text(row.get("chunk_id"))
            if cid:
                self.chunk_by_id[cid] = row

        self.subject_taxon_ids = set()
        for row in self.species_attach:
            tid = norm_text(row.get("canonical_taxon_id"))
            if tid:
                self.subject_taxon_ids.add(tid)
        for row in self.family_attach:
            tid = norm_text(row.get("canonical_family_id")) or norm_text(row.get("canonical_taxon_id"))
            if tid:
                self.subject_taxon_ids.add(tid)

        self.fact_ids = {norm_text(r.get("fact_id")) for r in self.species_facts + self.family_facts if norm_text(r.get("fact_id"))}
        self.evidence_ids = {norm_text(r.get("evidence_id")) for r in self.evidences if norm_text(r.get("evidence_id"))}

    def _all_claims(self) -> List[dict]:
        return self.species_claims + self.family_claims

    def _all_facts(self) -> List[dict]:
        return self.species_facts + self.family_facts

    def check_summary_consistency(self) -> dict:
        s = self.summary
        errors = []

        computed_checks = {
            "species_claim_total": len(self.species_claims),
            "family_claim_total": len(self.family_claims),
            "species_fact_total": len(self.species_facts),
            "family_fact_total": len(self.family_facts),
            "evidence_total": len(self.evidences),
            "fact_evidence_link_total": len(self.fact_evidence_links),
        }
        for key, expected in computed_checks.items():
            actual = s.get(key)
            if actual != expected:
                errors.append(f"{key}: summary={actual}, expected={expected}")

        if s.get("species_fact_total", 0) > s.get("species_claim_total", 0):
            errors.append("species_fact_total > species_claim_total")
        if s.get("family_fact_total", 0) > s.get("family_claim_total", 0):
            errors.append("family_fact_total > family_claim_total")

        return {"ok": len(errors) == 0, "errors": errors}

    def check_claims_backtrace(self) -> dict:
        errors = []
        for row in self._all_claims():
            tid = norm_text(row.get("subject_taxon_id"))
            if not tid:
                errors.append(f"Claim missing subject_taxon_id: {row.get('claim_id')}")
            elif tid not in self.subject_taxon_ids:
                errors.append(f"Claim subject_taxon_id not found in Step2 attachments: {row.get('claim_id')} -> {tid}")

            cid = norm_text(row.get("source_chunk_id"))
            if not cid:
                errors.append(f"Claim missing source_chunk_id: {row.get('claim_id')}")
                continue

            chunk = self.chunk_by_id.get(cid)
            if chunk is None:
                errors.append(f"Claim source_chunk_id not found in original chunks: {row.get('claim_id')} -> {cid}")
                continue

            quote = norm_text(row.get("evidence_quote"))
            if not quote:
                errors.append(f"Claim missing evidence_quote: {row.get('claim_id')}")
            else:
                chunk_text = norm_text(chunk.get("text") or chunk.get("chunk_text") or chunk.get("content"))
                if quote and chunk_text and quote not in chunk_text:
                    errors.append(f"Claim evidence_quote not found in chunk text: {row.get('claim_id')}")

            chapter = norm_text(row.get("source_chapter"))
            predicate = norm_text(row.get("predicate"))
            allowed = ALLOWED_BY_CHAPTER.get(chapter)
            if allowed is not None and predicate not in allowed:
                errors.append(f"Predicate not allowed for chapter: claim={row.get('claim_id')} chapter={chapter} predicate={predicate}")

        return {"ok": len(errors) == 0, "errors": errors}

    def check_fact_links(self) -> dict:
        errors = []
        for row in self.fact_evidence_links:
            fid = norm_text(row.get("fact_id"))
            eid = norm_text(row.get("evidence_id"))
            if fid not in self.fact_ids:
                errors.append(f"fact_evidence_link references missing fact_id: {fid}")
            if eid not in self.evidence_ids:
                errors.append(f"fact_evidence_link references missing evidence_id: {eid}")

        link_counter = Counter(norm_text(r.get("fact_id")) for r in self.fact_evidence_links)
        for fid in self.fact_ids:
            if link_counter.get(fid, 0) == 0:
                errors.append(f"Fact has no supporting evidence link: {fid}")

        return {"ok": len(errors) == 0, "errors": errors}

    def check_evidences_backtrace(self) -> dict:
        errors = []
        for row in self.evidences:
            cid = norm_text(row.get("source_chunk_id"))
            if not cid:
                errors.append(f"Evidence missing source_chunk_id: {row.get('evidence_id')}")
                continue

            chunk = self.chunk_by_id.get(cid)
            if chunk is None:
                errors.append(f"Evidence source_chunk_id not found in original chunks: {row.get('evidence_id')} -> {cid}")
                continue

            quote = norm_text(row.get("evidence_quote"))
            if not quote:
                errors.append(f"Evidence missing evidence_quote: {row.get('evidence_id')}")
            else:
                chunk_text = norm_text(chunk.get("text") or chunk.get("chunk_text") or chunk.get("content"))
                if quote and chunk_text and quote not in chunk_text:
                    errors.append(f"Evidence quote not found in chunk text: {row.get('evidence_id')}")
        return {"ok": len(errors) == 0, "errors": errors}

    def sample_rows(self) -> dict:
        rnd = random.Random(self.seed)
        claims = self._all_claims()
        facts = self._all_facts()
        return {
            "claim_samples": rnd.sample(claims, min(self.sample_size, len(claims))),
            "fact_samples": rnd.sample(facts, min(self.sample_size, len(facts))),
            "evidence_samples": rnd.sample(self.evidences, min(self.sample_size, len(self.evidences))),
        }

    def run(self) -> dict:
        file_check = self.check_required_files()
        if not file_check["ok"]:
            return {"summary": {"status": "fail"}, "file_check": file_check}

        self.load()

        summary_check = self.check_summary_consistency()
        claim_check = self.check_claims_backtrace()
        fact_link_check = self.check_fact_links()
        evidence_check = self.check_evidences_backtrace()

        all_ok = all([
            file_check["ok"],
            summary_check["ok"],
            claim_check["ok"],
            fact_link_check["ok"],
            evidence_check["ok"],
        ])

        return {
            "summary": {
                "status": "pass" if all_ok else "fail",
                "species_claim_total": len(self.species_claims),
                "family_claim_total": len(self.family_claims),
                "species_fact_total": len(self.species_facts),
                "family_fact_total": len(self.family_facts),
                "evidence_total": len(self.evidences),
                "fact_evidence_link_total": len(self.fact_evidence_links),
            },
            "file_check": file_check,
            "summary_check": summary_check,
            "claim_backtrace_check": claim_check,
            "fact_link_check": fact_link_check,
            "evidence_backtrace_check": evidence_check,
            "samples": self.sample_rows(),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="QA test for Step3 extraction.")
    parser.add_argument("--claims-dir", type=Path, default=Path("outputs/intermediate/claims"))
    parser.add_argument("--intermediate-dir", type=Path, default=Path("outputs/intermediate"))
    parser.add_argument("--attachments-dir", type=Path, default=Path("outputs/intermediate/attachments"))
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("outputs/intermediate/claims/step3_quality_check_report.json"))
    args = parser.parse_args()

    tester = Step3Tester(args.claims_dir, args.intermediate_dir, args.attachments_dir, args.sample_size, args.seed)
    report = tester.run()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] report written to: {args.output}")
    print(f"[SUMMARY] status={report['summary']['status']}")
    if report["summary"]["status"] == "pass":
        print(
            f"[COUNTS] species_claims={report['summary']['species_claim_total']} "
            f"family_claims={report['summary']['family_claim_total']} "
            f"species_facts={report['summary']['species_fact_total']} "
            f"family_facts={report['summary']['family_fact_total']} "
            f"evidences={report['summary']['evidence_total']}"
        )
    else:
        for section in (
            "file_check",
            "summary_check",
            "claim_backtrace_check",
            "fact_link_check",
            "evidence_backtrace_check",
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
