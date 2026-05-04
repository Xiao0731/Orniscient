from __future__ import annotations

from typing import Any


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _get_nested_text(mapping: dict[str, Any], parent_key: str, child_keys: list[str]) -> str:
    nested = mapping.get(parent_key)
    if not isinstance(nested, dict):
        return ""
    for child_key in child_keys:
        value = _clean_text(nested.get(child_key))
        if value:
            return value
    return ""


def get_target_entity(row: dict[str, Any]) -> str:
    direct_keys = [
        "target_entity",
        "target_species",
        "common_name",
        "scientific_name",
        "species",
        "species_name",
    ]
    for key in direct_keys:
        value = _clean_text(row.get(key))
        if value:
            return value

    for parent_key in ["metadata", "meta", "provenance"]:
        value = _get_nested_text(
            row,
            parent_key,
            ["target_entity", "common_name", "scientific_name", "species_name"],
        )
        if value:
            return value
    return ""


def get_family_order(row: dict[str, Any]) -> tuple[str, str]:
    family = ""
    order = ""
    for key in ["family", "family_name"]:
        value = _clean_text(row.get(key))
        if value:
            family = value
            break
    for key in ["order", "order_name"]:
        value = _clean_text(row.get(key))
        if value:
            order = value
            break

    if not family or not order:
        for parent_key in ["metadata", "meta"]:
            nested = row.get(parent_key)
            if not isinstance(nested, dict):
                continue
            if not family:
                for key in ["family", "family_name"]:
                    value = _clean_text(nested.get(key))
                    if value:
                        family = value
                        break
            if not order:
                for key in ["order", "order_name"]:
                    value = _clean_text(nested.get(key))
                    if value:
                        order = value
                        break

    target = get_target_entity(row)
    if target and "|" in target and (not family or not order):
        parts = [_clean_text(part) for part in target.split("|")]
        if len(parts) >= 2:
            if not order:
                order = parts[0]
            if not family:
                family = parts[1]

    return family, order
