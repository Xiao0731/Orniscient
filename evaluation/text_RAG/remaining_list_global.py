from __future__ import annotations

from typing import Any

try:
    from birdbase_table_utils import (
        apply_birdbase_constraints,
        latin_species_list,
        parse_birdbase_constraints_from_text,
    )
except ModuleNotFoundError:
    from evaluation.text_RAG.birdbase_table_utils import (
        apply_birdbase_constraints,
        latin_species_list,
        parse_birdbase_constraints_from_text,
    )


def _has_effective_constraints(constraints: dict[str, Any]) -> bool:
    for key in ["iucn", "primary_habitat", "primary_diet", "nest_type", "average_mass_filters", "order", "family", "realm", "flags_yes", "flags_no"]:
        if constraints.get(key):
            return True
    return False


def answer_list_global_item(
    item: dict,
    birdbase_df,
    column_map: dict,
    constraint_source: str = "question",
    ambiguous_realm_policy: str = "skip",
) -> dict[str, Any]:
    provenance = item.get("provenance") or {}
    if constraint_source == "provenance":
        condition_text = str(provenance.get("search_conditions", "")).strip()
    else:
        condition_text = str(item.get("question", "")).strip()

    constraints = parse_birdbase_constraints_from_text(
        condition_text,
        column_map,
        mode="list_global",
        text_source=constraint_source,
        ambiguous_realm_policy=ambiguous_realm_policy,
    )
    matched_df, debug = apply_birdbase_constraints(birdbase_df, column_map, constraints)
    answer = latin_species_list(matched_df, column_map)
    status = "ok"
    if not _has_effective_constraints(constraints) or len(answer) == 0:
        status = "parse_failed_or_no_match"
    return {
        "question_id": str(item.get("question_id", "")).strip(),
        "answer": answer,
        "status": status,
        "kb_policy": "birdbase_rule_query",
        "constraint_source": constraint_source,
        "ambiguous_realm_policy": ambiguous_realm_policy,
        "applied_ambiguous_realm_codes": list(constraints.get("applied_ambiguous_realm_codes", [])),
        "condition_text": condition_text,
        "answer_preview": answer[:10],
        "parsed_constraints": constraints,
        "unresolved_constraints": list(constraints.get("unresolved_constraints", [])),
        "matched_rows": len(answer),
        "debug": debug,
    }
