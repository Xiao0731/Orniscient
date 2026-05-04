"""Build crosswalks and aliases from Clements into canonical taxonomy."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from kg_v2.Step1_taxonomy.common import stable_hash, write_jsonl
from kg_v2.Step1_taxonomy.schema.taxonomy_schema import TaxonomyAlias, TaxonomyCrosswalk
from kg_v2.Step1_taxonomy.schema.taxonomy_types import (
    AVIBASE_MATCH,
    CLEMENTS,
    CODE_MATCH,
    EXACT_MATCH,
    NAME_MATCH,
    UNRESOLVED,
)


def build_taxonomy_crosswalks(
    canonical_nodes: list[dict],
    clements_rows: list[dict],
    external_release: str,
    crosswalks_output_path: str | Path,
    aliases_output_path: str | Path,
) -> tuple[list[dict], list[dict]]:
    avibase_index = {node["avibase_id"]: node for node in canonical_nodes if node.get("avibase_id")}
    code_index = {node["cornell_species_code"]: node for node in canonical_nodes if node.get("cornell_species_code")}
    exact_name_index = {(node["rank"], node["scientific_name"]): node for node in canonical_nodes if node.get("scientific_name")}
    fallback_index: dict[tuple[str, str, str, str], dict] = {}
    for node in canonical_nodes:
        fallback_index[(node["rank"], node["scientific_name"], node.get("family_name", ""), node.get("order_name", ""))] = node

    crosswalks: list[dict] = []
    aliases: dict[tuple[str, str, str], dict] = {}

    def add_alias(canonical_taxon_id: str, value: str, alias_type: str) -> None:
        if not canonical_taxon_id or not value:
            return
        alias = TaxonomyAlias(
            alias_id=stable_hash(canonical_taxon_id, alias_type, value, CLEMENTS, external_release, prefix="alias_"),
            canonical_taxon_id=canonical_taxon_id,
            alias_value=value,
            alias_type=alias_type,
            alias_source=CLEMENTS,
            alias_release=external_release,
        ).to_dict()
        aliases[(canonical_taxon_id, alias_type, value)] = alias

    for row in clements_rows:
        canonical = None
        method = UNRESOLVED
        confidence = 0.0

        external_id = row.get("external_id", "")
        external_code = row.get("species_code", "")
        external_rank = row.get("rank", "")
        scientific_name = row.get("scientific_name", "")

        if external_id and external_id in avibase_index:
            canonical = avibase_index[external_id]
            method = AVIBASE_MATCH
            confidence = 1.0
        elif external_code and external_code in code_index:
            canonical = code_index[external_code]
            method = CODE_MATCH
            confidence = 0.97
        elif (external_rank, scientific_name) in exact_name_index:
            canonical = exact_name_index[(external_rank, scientific_name)]
            method = EXACT_MATCH
            confidence = 0.93
        else:
            key = (external_rank, scientific_name, row.get("family_name", ""), row.get("order_name", ""))
            if key in fallback_index:
                canonical = fallback_index[key]
                method = NAME_MATCH
                confidence = 0.85

        canonical_taxon_id = canonical["taxon_id"] if canonical else ""
        crosswalk = TaxonomyCrosswalk(
            crosswalk_id=stable_hash(
                external_release,
                external_rank,
                scientific_name,
                external_code,
                external_id,
                prefix="crosswalk_",
            ),
            canonical_taxon_id=canonical_taxon_id,
            external_source=CLEMENTS,
            external_release=external_release,
            external_rank=external_rank,
            external_scientific_name=scientific_name,
            external_english_name=row.get("english_name", ""),
            external_code=external_code,
            external_id=external_id,
            match_method=method,
            match_confidence=confidence,
        ).to_dict()
        crosswalks.append(crosswalk)

        add_alias(canonical_taxon_id, scientific_name, "scientific_name")
        add_alias(canonical_taxon_id, row.get("english_name", ""), "english_name")
        add_alias(canonical_taxon_id, external_code, "species_code")
        add_alias(canonical_taxon_id, external_id, "external_id")

    alias_rows = list(aliases.values())
    write_jsonl(crosswalks_output_path, crosswalks)
    write_jsonl(aliases_output_path, alias_rows)
    return crosswalks, alias_rows
