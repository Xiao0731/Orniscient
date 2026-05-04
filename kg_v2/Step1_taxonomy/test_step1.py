#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步骤1的测试文件 分类学主干质量检查
检查内容
--------------
    A. 从canonical_taxon_nodes.jsonl中随机抽取10个物种进行验证：
    - 等级 == 物种
    - 学名 / 英文主要名称 / 康奈尔物种代码 / Avibase ID
    - 是否存在Clements交叉映射
    - 父属/科/目链是否内部一致

    B. 随机抽取20个未解决的交叉映射/冲突案例，并分类可能的原因：
    - 外部ID缺失
    - 代码缺失
    - 亚种或群等级
    - 检查表漂移注释
    - 可能的名称不匹配
    - 未知

    C. 对100个采样物种名称进行BOW可附加性预检查：
    - 与标准分类法直接学名匹配
    - 若不直接匹配，则基于别名/交叉映射进行补救
    - 未解决比例

从kg_v2/根目录运行：
python Step1_taxonomy/test_step1.py
可选：
python Step1_taxonomy/test_step1.py --bow-sample-size 150 --species-sample-size 12 --unresolved-sample-size 30
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator
import re

import pandas as pd


# ---------- IO helpers ----------

def read_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


# ---------- name normalization ----------

def norm_text(value: object) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() == "nan":
        return ""
    return " ".join(s.split())

def norm_sci(value: object) -> str:
    return norm_text(value)

def clean_bow_species_name(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    raw = str(value).replace("\r", "\n")
    for line in raw.splitlines():
        line = " ".join(line.split()).strip()
        if not line:
            continue
        if "scientific name definitions" in line.lower():
            continue
        return line

    # 兜底：防止整格被压成一行
    text = " ".join(str(value).split()).strip()
    text = re.sub(r"\s+Scientific name definitions\s*$", "", text, flags=re.IGNORECASE)
    return text.strip()

def norm_code(value: object) -> str:
    return norm_text(value).lower()

def norm_ext_id(value: object) -> str:
    return norm_text(value).lower()

def extract_genus(scientific_name: str) -> str:
    scientific_name = norm_sci(scientific_name)
    return scientific_name.split()[0] if scientific_name else ""


# ---------- core checks ----------

@dataclass
class Paths:
    taxonomy_dir: Path
    jsonl_dir: Path
    bow_glob_dir: Path

    @property
    def canonical_nodes(self) -> Path:
        return self.taxonomy_dir / "canonical_taxon_nodes.jsonl"

    @property
    def canonical_edges(self) -> Path:
        return self.taxonomy_dir / "canonical_taxon_edges.jsonl"

    @property
    def crosswalks(self) -> Path:
        return self.taxonomy_dir / "taxonomy_crosswalks.jsonl"

    @property
    def aliases(self) -> Path:
        return self.taxonomy_dir / "taxonomy_aliases.jsonl"

    @property
    def conflicts(self) -> Path:
        return self.taxonomy_dir / "taxonomy_conflicts.jsonl"


def load_step1_outputs(paths: Paths):
    nodes = list(read_jsonl(paths.canonical_nodes))
    edges = list(read_jsonl(paths.canonical_edges))
    crosswalks = list(read_jsonl(paths.crosswalks))
    aliases = list(read_jsonl(paths.aliases))
    conflicts = list(read_jsonl(paths.conflicts))

    node_by_id = {n["taxon_id"]: n for n in nodes}
    children_by_src = defaultdict(list)
    for e in edges:
        children_by_src[e["src_id"]].append(e)

    parent_edge_by_dst = {}
    for e in edges:
        parent_edge_by_dst[e["dst_id"]] = e

    canonical_species = [n for n in nodes if n.get("rank") == "species"]

    crosswalks_by_canonical = defaultdict(list)
    unresolved_crosswalks = []
    for cw in crosswalks:
        crosswalks_by_canonical[cw.get("canonical_taxon_id", "")].append(cw)
        if cw.get("match_method") == "UNRESOLVED":
            unresolved_crosswalks.append(cw)

    aliases_by_value = defaultdict(list)
    for a in aliases:
        aliases_by_value[norm_text(a.get("alias_value", ""))].append(a)

    sci_to_species = defaultdict(list)
    code_to_species = defaultdict(list)
    extid_to_species = defaultdict(list)
    for n in canonical_species:
        sci_to_species[norm_sci(n.get("scientific_name"))].append(n)
        if n.get("cornell_species_code"):
            code_to_species[norm_code(n.get("cornell_species_code"))].append(n)
        if n.get("avibase_id"):
            extid_to_species[norm_ext_id(n.get("avibase_id"))].append(n)

    return {
        "nodes": nodes,
        "edges": edges,
        "crosswalks": crosswalks,
        "aliases": aliases,
        "conflicts": conflicts,
        "node_by_id": node_by_id,
        "children_by_src": children_by_src,
        "parent_edge_by_dst": parent_edge_by_dst,
        "canonical_species": canonical_species,
        "crosswalks_by_canonical": crosswalks_by_canonical,
        "unresolved_crosswalks": unresolved_crosswalks,
        "aliases_by_value": aliases_by_value,
        "sci_to_species": sci_to_species,
        "code_to_species": code_to_species,
        "extid_to_species": extid_to_species,
    }


def verify_parent_chain(species_node: dict, state: dict) -> dict:
    """Return chain validation result for one species node."""
    node_by_id = state["node_by_id"]
    parent_edge_by_dst = state["parent_edge_by_dst"]

    result = {
        "species_taxon_id": species_node["taxon_id"],
        "scientific_name": species_node.get("scientific_name", ""),
        "ok": True,
        "messages": [],
        "genus_node": None,
        "family_node": None,
        "order_node": None,
    }

    # species -> genus
    e_species = parent_edge_by_dst.get(species_node["taxon_id"])
    if not e_species or e_species.get("relation_type") != "CONTAINS_SPECIES":
        result["ok"] = False
        result["messages"].append("Missing or invalid parent edge from genus to species.")
        return result

    genus = node_by_id.get(e_species["src_id"])
    result["genus_node"] = genus
    if not genus or genus.get("rank") != "genus":
        result["ok"] = False
        result["messages"].append("Parent genus node missing or wrong rank.")
        return result

    expected_genus = extract_genus(species_node.get("scientific_name", ""))
    if expected_genus and genus.get("scientific_name") != expected_genus:
        result["ok"] = False
        result["messages"].append(
            f"Genus mismatch: species scientific_name implies genus '{expected_genus}', "
            f"but genus node is '{genus.get('scientific_name', '')}'."
        )

    # genus -> family
    e_genus = parent_edge_by_dst.get(genus["taxon_id"])
    if not e_genus or e_genus.get("relation_type") != "CONTAINS_GENUS":
        result["ok"] = False
        result["messages"].append("Missing or invalid parent edge from family to genus.")
        return result

    family = node_by_id.get(e_genus["src_id"])
    result["family_node"] = family
    if not family or family.get("rank") != "family":
        result["ok"] = False
        result["messages"].append("Parent family node missing or wrong rank.")
        return result

    if species_node.get("family_name") and family.get("scientific_name") != species_node.get("family_name"):
        result["ok"] = False
        result["messages"].append(
            f"Family mismatch: species family_name='{species_node.get('family_name')}', "
            f"family node scientific_name='{family.get('scientific_name', '')}'."
        )

    # family -> order
    e_family = parent_edge_by_dst.get(family["taxon_id"])
    if not e_family or e_family.get("relation_type") != "CONTAINS_FAMILY":
        result["ok"] = False
        result["messages"].append("Missing or invalid parent edge from order to family.")
        return result

    order = node_by_id.get(e_family["src_id"])
    result["order_node"] = order
    if not order or order.get("rank") != "order":
        result["ok"] = False
        result["messages"].append("Parent order node missing or wrong rank.")
        return result

    # order node stores order scientific_name/order_name depending on builder; compare permissively
    order_candidates = {order.get("scientific_name", ""), order.get("order_name", "")}
    if species_node.get("order_name") and species_node.get("order_name") not in order_candidates:
        result["ok"] = False
        result["messages"].append(
            f"Order mismatch: species order_name='{species_node.get('order_name')}', "
            f"order node values={order_candidates}."
        )

    return result


def sample_species_check(state: dict, sample_size: int, seed: int) -> dict:
    rnd = random.Random(seed)
    canonical_species = state["canonical_species"]
    sample = rnd.sample(canonical_species, min(sample_size, len(canonical_species)))

    rows = []
    failures = 0
    for n in sample:
        crosswalks = state["crosswalks_by_canonical"].get(n["taxon_id"], [])
        has_clements_mapping = any(cw.get("external_source") == "Clements" and cw.get("match_method") != "UNRESOLVED" for cw in crosswalks)
        chain = verify_parent_chain(n, state)
        ok = (
            n.get("rank") == "species"
            and chain["ok"]
        )
        if not ok:
            failures += 1
        rows.append({
            "taxon_id": n.get("taxon_id", ""),
            "rank": n.get("rank", ""),
            "scientific_name": n.get("scientific_name", ""),
            "english_name_primary": n.get("english_name_primary", ""),
            "cornell_species_code": n.get("cornell_species_code", ""),
            "avibase_id": n.get("avibase_id", ""),
            "has_clements_crosswalk": has_clements_mapping,
            "genus_node": chain["genus_node"].get("scientific_name", "") if chain["genus_node"] else "",
            "family_node": chain["family_node"].get("scientific_name", "") if chain["family_node"] else "",
            "order_node": chain["order_node"].get("scientific_name", "") if chain["order_node"] else "",
            "ok": ok,
            "messages": chain["messages"],
        })

    return {
        "sample_size": len(rows),
        "failure_count": failures,
        "rows": rows,
    }


def classify_unresolved(cw: dict, conflict_by_external: dict) -> str:
    ext_rank = cw.get("external_rank", "")
    ext_id = cw.get("external_id", "")
    ext_code = cw.get("external_code", "")
    ext_sci = cw.get("external_scientific_name", "")
    conflict_note = conflict_by_external.get(
        (cw.get("external_rank", ""), cw.get("external_scientific_name", ""), cw.get("external_code", ""), cw.get("external_id", "")),
        {}
    )

    if not ext_id:
        return "external_id_missing"
    if not ext_code:
        return "code_missing"
    if "subspecies" in ext_rank or "group" in ext_rank:
        return "subspecies_or_group_rank"
    if conflict_note:
        ctype = conflict_note.get("conflict_type", "")
        notes = (conflict_note.get("notes", "") or "").lower()
        ext_val = (conflict_note.get("external_value", "") or "").lower()
        if ctype == "SPLIT_LUMP_DRIFT" or "drift" in notes or "change" in ext_val:
            return "checklist_drift_note"
        if ctype in {"NAME_MISMATCH", "GENUS_MISMATCH", "FAMILY_MISMATCH"}:
            return "possible_name_mismatch"
    return "unknown"


def sample_unresolved_check(state: dict, sample_size: int, seed: int) -> dict:
    rnd = random.Random(seed + 1)
    unresolved = state["unresolved_crosswalks"]
    conflicts = state["conflicts"]

    conflict_by_external = {}
    for c in conflicts:
        # crude lookup, but enough for manual inspection
        key = (
            c.get("external_rank", c.get("notes", "")),
            c.get("external_scientific_name", c.get("external_value", "")),
            c.get("external_code", ""),
            c.get("external_id", ""),
        )
        conflict_by_external[key] = c

    sample = rnd.sample(unresolved, min(sample_size, len(unresolved)))

    categorized = []
    counts = Counter()
    for cw in sample:
        reason = classify_unresolved(cw, conflict_by_external)
        counts[reason] += 1
        categorized.append({
            "external_rank": cw.get("external_rank", ""),
            "external_scientific_name": cw.get("external_scientific_name", ""),
            "external_english_name": cw.get("external_english_name", ""),
            "external_code": cw.get("external_code", ""),
            "external_id": cw.get("external_id", ""),
            "inferred_reason": reason,
        })

    return {
        "sample_size": len(categorized),
        "reason_counts": dict(counts),
        "rows": categorized,
    }


# ---------- BOW precheck ----------

def find_bow_files(bow_dir: Path) -> list[Path]:
    return sorted(bow_dir.glob("*.xlsx"))

def load_bow_species_names(bow_dir: Path) -> list[dict]:
    files = find_bow_files(bow_dir)
    rows = []
    for fp in files:
        try:
            df = pd.read_excel(fp)
        except Exception:
            continue
        required = {"Species", "Common_name"}
        if not required.intersection(df.columns):
            continue
        for _, row in df.iterrows():
            sci = clean_bow_species_name(row.get("Species"))
            common = norm_text(row.get("Common_name"))
            family = norm_text(row.get("Family"))
            order = norm_text(row.get("Order"))
            if sci:
                rows.append({
                    "source_file": fp.name,
                    "scientific_name": sci,
                    "common_name": common,
                    "family_name": family,
                    "order_name": order,
                })
    # dedup by scientific name, keep first
    seen = set()
    deduped = []
    for r in rows:
        if r["scientific_name"] not in seen:
            seen.add(r["scientific_name"])
            deduped.append(r)
    return deduped

def bow_attachability_precheck(state: dict, bow_dir: Path, sample_size: int, seed: int) -> dict:
    rnd = random.Random(seed + 2)
    bow_species = load_bow_species_names(bow_dir)
    sample = rnd.sample(bow_species, min(sample_size, len(bow_species)))

    sci_to_species = state["sci_to_species"]
    code_to_species = state["code_to_species"]
    extid_to_species = state["extid_to_species"]
    aliases_by_value = state["aliases_by_value"]
    canonical_by_id = state["node_by_id"]

    rows = []
    rescue_count = 0
    direct_count = 0
    unresolved_count = 0

    for r in sample:
        sci = norm_sci(r["scientific_name"])
        direct_matches = sci_to_species.get(sci, [])
        if direct_matches:
            direct_count += 1
            rows.append({
                **r,
                "match_status": "DIRECT_SCI_MATCH",
                "canonical_taxon_id": direct_matches[0]["taxon_id"],
                "canonical_scientific_name": direct_matches[0]["scientific_name"],
            })
            continue

        rescued = None
        alias_candidates = aliases_by_value.get(sci, [])
        for alias in alias_candidates:
            cid = alias.get("canonical_taxon_id", "")
            node = canonical_by_id.get(cid)
            if node and node.get("rank") == "species":
                rescued = node
                break

        if rescued:
            rescue_count += 1
            rows.append({
                **r,
                "match_status": "ALIAS_RESCUE",
                "canonical_taxon_id": rescued["taxon_id"],
                "canonical_scientific_name": rescued["scientific_name"],
            })
        else:
            unresolved_count += 1
            rows.append({
                **r,
                "match_status": "UNRESOLVED",
                "canonical_taxon_id": "",
                "canonical_scientific_name": "",
            })

    total = len(rows)
    return {
        "sample_size": total,
        "direct_count": direct_count,
        "alias_rescue_count": rescue_count,
        "unresolved_count": unresolved_count,
        "unresolved_ratio": (unresolved_count / total) if total else 0.0,
        "rows": rows,
    }


# ---------- report ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="Quality check for Step1 taxonomy backbone.")
    parser.add_argument("--taxonomy-dir", type=Path, default=Path("outputs/intermediate/taxonomy"))
    parser.add_argument("--jsonl-dir", type=Path, default=Path("outputs/jsonl"))
    parser.add_argument("--bow-dir", type=Path, default=Path("data/BOW"))
    parser.add_argument("--species-sample-size", type=int, default=10)
    parser.add_argument("--unresolved-sample-size", type=int, default=20)
    parser.add_argument("--bow-sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("outputs/intermediate/taxonomy/step1_quality_check_report.json"))
    args = parser.parse_args()

    paths = Paths(args.taxonomy_dir, args.jsonl_dir, args.bow_dir)
    state = load_step1_outputs(paths)

    species_check = sample_species_check(state, args.species_sample_size, args.seed)
    unresolved_check = sample_unresolved_check(state, args.unresolved_sample_size, args.seed)
    bow_precheck = bow_attachability_precheck(state, args.bow_dir, args.bow_sample_size, args.seed)

    report = {
        "summary": {
            "canonical_species_total": len(state["canonical_species"]),
            "unresolved_crosswalk_total": len(state["unresolved_crosswalks"]),
            "species_sample_size": species_check["sample_size"],
            "species_sample_failures": species_check["failure_count"],
            "unresolved_sample_size": unresolved_check["sample_size"],
            "bow_precheck_sample_size": bow_precheck["sample_size"],
            "bow_precheck_unresolved_ratio": bow_precheck["unresolved_ratio"],
        },
        "A_species_sample_check": species_check,
        "B_unresolved_sample_check": unresolved_check,
        "C_bow_attachability_precheck": bow_precheck,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] report written to: {args.output}")
    print(f"[A] sampled species: {species_check['sample_size']} | failures: {species_check['failure_count']}")
    print(f"[B] sampled unresolved: {unresolved_check['sample_size']} | reason_counts: {unresolved_check['reason_counts']}")
    print(
        "[C] BOW precheck: "
        f"sample={bow_precheck['sample_size']} "
        f"direct={bow_precheck['direct_count']} "
        f"alias_rescue={bow_precheck['alias_rescue_count']} "
        f"unresolved={bow_precheck['unresolved_count']} "
        f"unresolved_ratio={bow_precheck['unresolved_ratio']:.2%}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
