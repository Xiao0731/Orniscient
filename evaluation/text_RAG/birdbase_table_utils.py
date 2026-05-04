from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def normalize_species_name(value: Any) -> str:
    text = normalize_text(value)
    return re.sub(r"[^A-Za-z0-9\- ]+", " ", text).strip().lower()


def yes_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "yes", "y"])


def no_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["0", "0.0", "false", "no", "n"])


def _dedupe_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    deduped: list[str] = []
    for col in columns:
        base = col or "Unnamed"
        if base not in seen:
            seen[base] = 0
            deduped.append(base)
        else:
            seen[base] += 1
            deduped.append(f"{base}__{seen[base]}")
    return deduped


def get_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    exact = {normalize_text(col).lower(): col for col in df.columns}
    for candidate in candidates:
        key = normalize_text(candidate).lower()
        if key in exact:
            return exact[key]
    normalized_columns = {re.sub(r"[^a-z0-9]+", "", normalize_text(col).lower()): col for col in df.columns}
    for candidate in candidates:
        key = re.sub(r"[^a-z0-9]+", "", normalize_text(candidate).lower())
        if key in normalized_columns:
            return normalized_columns[key]
    for candidate in candidates:
        key = normalize_text(candidate).lower()
        for col in df.columns:
            norm_col = normalize_text(col).lower()
            if key and (key in norm_col or norm_col in key):
                return col
    return None


def _build_column_map(df: pd.DataFrame) -> dict[str, str]:
    return {
        "latin_name": get_col(df, ["Latin (BirdLife > IOC > Clements>AviList)", "IOC World Bird List (v15.1)", "Species"]),
        "english_name": get_col(df, ["English Name (BirdLife > IOC > Clements>AviList)", "Common Name", "English Name"]),
        "order": get_col(df, ["Order"]),
        "family": get_col(df, ["Family IOC 15.1", "Family", "Family Clements v2024b"]),
        "genus": get_col(df, ["Genus"]),
        "species": get_col(df, ["Species"]),
        "iucn": get_col(df, ["2024 IUCN Red List category", "IUCN"]),
        "realm": get_col(df, ["RLM", "Realm", "Zoogeographic Realm"]),
        "island": get_col(df, ["ISL", "Island"]),
        "primary_habitat": get_col(df, ["Primary Habitat"]),
        "primary_diet": get_col(df, ["Primary Diet"]),
        "nest_type": get_col(df, ["Nest_Type", "Nest Type"]),
        "average_mass": get_col(df, ["Average Mass"]),
        "mig": get_col(df, ["Mig"]),
        "alt": get_col(df, ["Alt"]),
        "irreg": get_col(df, ["Irreg"]),
        "disp": get_col(df, ["Disp"]),
        "sed": get_col(df, ["Sed"]),
    }


@lru_cache(maxsize=4)
def load_birdbase_table(path: str) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_excel(path, header=0)
    raw.columns = [normalize_text(col) for col in raw.columns]
    first_row = raw.iloc[0].tolist()
    new_columns: list[str] = []
    for top, sub in zip(raw.columns, first_row):
        sub_text = normalize_text(sub)
        top_text = normalize_text(top)
        if sub_text and sub_text.lower() != "nan" and not sub_text.lower().startswith("unnamed"):
            new_columns.append(sub_text)
        else:
            new_columns.append(top_text)
    raw.columns = _dedupe_columns(new_columns)
    df = raw.iloc[1:].reset_index(drop=True).copy()
    df = df.fillna("")
    return df, _build_column_map(df)


def _column_unique_values(df: pd.DataFrame, column: str | None) -> list[str]:
    if not column or column not in df.columns:
        return []
    values = [normalize_text(value) for value in df[column].astype(str).tolist()]
    values = [value for value in values if value and value.lower() != "nan"]
    return sorted(set(values))


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _record_match(constraints: dict[str, Any], field: str, phrase: str, value: str = "") -> None:
    _record_match_with_source(constraints, field, phrase, value=value, source="manual_rule")


def _record_match_with_source(
    constraints: dict[str, Any],
    field: str,
    phrase: str,
    *,
    value: str = "",
    source: str = "",
) -> None:
    matched = constraints.setdefault("matched_phrases", {})
    phrases = matched.setdefault(field, [])
    sources = constraints.setdefault("constraint_sources", {})
    source_list = sources.setdefault(field, [])
    entry = {
        "phrase": normalize_text(phrase),
        "value": normalize_text(value),
        "source": normalize_text(source) or "manual_rule",
    }
    if entry["source"] not in source_list:
        source_list.append(entry["source"])
    if entry["phrase"] and entry not in phrases:
        phrases.append(entry)


def _has_any_pattern(text: str, patterns: list[str]) -> tuple[bool, str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return True, normalize_text(match.group(0))
    return False, ""


def _extract_realm_code(search_conditions: str) -> str:
    text = normalize_text(search_conditions)
    match = re.search(r"Zoogeographic Realm:\s*([A-Za-z]+)", text, flags=re.IGNORECASE)
    return normalize_text(match.group(1)).upper() if match else ""


def _extract_field_value(search_conditions: str, field_name: str) -> str:
    text = normalize_text(search_conditions)
    match = re.search(rf"{re.escape(field_name)}:\s*([^;]+)", text, flags=re.IGNORECASE)
    return normalize_text(match.group(1)) if match else ""


def _lookup_actual_value(actual_values: list[str], raw_value: str, *, uppercase: bool = False) -> str:
    candidate = normalize_text(raw_value)
    if not candidate:
        return ""
    exact = {normalize_text(value): value for value in actual_values}
    if candidate in exact:
        return exact[candidate]
    lowered = {normalize_text(value).lower(): value for value in actual_values}
    key = candidate.lower()
    if key in lowered:
        return lowered[key]
    if uppercase:
        uppered = {normalize_text(value).upper(): value for value in actual_values}
        upper_key = candidate.upper()
        if upper_key in uppered:
            return uppered[upper_key]
    return ""


def _manual_iucn_aliases() -> dict[str, str]:
    return {
        "least concern": "LC",
        "near threatened": "NT",
        "vulnerable": "VU",
        "endangered": "EN",
        "critically endangered": "CR",
        "critically endangered possibly extinct": "CR (PE)",
        "critically endangered possibly extinct in the wild": "CR (PEW)",
        "extinct": "EX",
        "extinct in the wild": "EW",
        "data deficient": "DD",
    }


def _manual_habitat_aliases() -> dict[str, str]:
    return {
        "forest": "Forest",
        "forested": "Forest",
        "wetland": "Wetland",
        "wetlands": "Wetland",
        "marsh": "Wetland",
        "bog": "Wetland",
        "swamp": "Wetland",
        "grassland": "Grassland",
        "grasslands": "Grassland",
        "shrubland": "Shrub",
        "shrublands": "Shrub",
        "shrub": "Shrub",
        "woodland": "Woodland",
        "woodlands": "Woodland",
        "coastal": "Coastal",
        "shore": "Coastal",
        "mangrove": "Coastal",
        "sea": "Sea",
        "marine": "Sea",
        "pelagic": "Sea",
        "rocky": "Rocky",
        "riparian": "Riparian",
        "savanna": "Savanna",
        "savannah": "Savanna",
        "plains": "Plains",
        "plain": "Plains",
        "desert": "Desert",
        "artificial": "Artificial",
        "urban": "Artificial",
        "farmland": "Artificial",
        "bamboo": "Bamboo",
    }


def _manual_diet_aliases() -> dict[str, str]:
    return {
        "no information": "No Information",
        "no information recorded": "No Information",
        "no dietary information": "No Information",
        "invertebrate": "Invertebrate",
        "invertebrates": "Invertebrate",
        "arthropod": "Invertebrate",
        "arthropods": "Invertebrate",
        "insect": "Invertebrate",
        "insects": "Invertebrate",
        "fruit": "Fruit",
        "frugivorous": "Fruit",
        "frugivory": "Fruit",
        "seed": "Seed",
        "seeds": "Seed",
        "granivorous": "Seed",
        "granivory": "Seed",
        "nectar": "Nectar",
        "nectarivory": "Nectar",
        "fish": "Fish",
        "piscivorous": "Fish",
        "piscivory": "Fish",
        "vertebrate": "Vertebrate",
        "vertebrates": "Vertebrate",
        "mammal": "Vertebrate",
        "reptile": "Vertebrate",
        "amphibian": "Vertebrate",
        "omnivore": "Omnivore",
        "omnivorous": "Omnivore",
        "omnivory": "Omnivore",
        "herbivore": "Herbivore",
        "herbivorous": "Herbivore",
        "herbivory": "Herbivore",
        "plant": "Plant",
        "plant matter": "Plant",
        "carnivore": "Carnivore",
        "carnivorous": "Carnivore",
        "carnivory": "Carnivore",
        "scavenger": "Scavenger",
        "scavenging": "Scavenger",
        "carrion": "Scavenger",
        "egg": "Ovivore",
        "eggs": "Ovivore",
        "ovivore": "Ovivore",
        "beeswax": "Beeswax",
    }


def _manual_nest_aliases() -> dict[str, str]:
    return {
        "open nest": "O",
        "open nests": "O",
        "cavity": "CV",
        "cavities": "CV",
        "burrow": "BU",
        "burrows": "BU",
        "crevice": "CR",
        "crevices": "CR",
        "cup-shaped": "CP",
        "cup shaped": "CP",
        "cup": "CP",
        "platform": "PL",
        "platform nests": "PL",
        "scrape": "SC",
        "scrape nests": "SC",
        "domed": "DM",
        "domed nests": "DM",
        "half-cup": "HC",
        "half cup": "HC",
        "saucer": "SA",
        "saucer-shaped": "SA",
        "sphere": "SP",
        "sp-type": "SP",
        "do not build nests": "NO",
        "do not build": "NO",
        "old nests of other species": "O",
    }


def _manual_flag_aliases() -> dict[str, tuple[str, str]]:
    return {
        "island endemic": ("island", "yes"),
        "island endemics": ("island", "yes"),
        "insular": ("island", "yes"),
        "not island endemic": ("island", "no"),
        "non-island endemic": ("island", "no"),
        "migratory": ("mig", "yes"),
        "non-migratory": ("mig", "no"),
        "not migratory": ("mig", "no"),
        "sedentary": ("sed", "yes"),
        "resident": ("sed", "yes"),
        "altitudinal": ("alt", "yes"),
        "irregular": ("irreg", "yes"),
        "dispersive": ("disp", "yes"),
    }


def _extract_codes_in_parentheses(text: str) -> list[str]:
    codes: list[str] = []
    for raw in re.findall(r"\(([A-Z, ]{1,20})\)", text):
        for piece in raw.split(","):
            code = normalize_text(piece).upper()
            if code:
                _append_unique(codes, code)
    return codes


def _normalize_realm_phrase_key(text: str) -> str:
    phrase = normalize_text(text).lower()
    phrase = phrase.replace("realm", "")
    phrase = phrase.replace("zoogeographic", "")
    phrase = re.sub(r"\(([^)]*)\)", r" \1 ", phrase)
    phrase = phrase.replace("/", " ")
    phrase = phrase.replace("-", " ")
    phrase = re.sub(r"\s+", " ", phrase).strip(" ,;:.")
    return phrase


def _realm_phrase_variants(text: str) -> list[str]:
    base = normalize_text(text)
    variants = [base]
    lower = base.lower()
    if "(" in lower and ")" in lower:
        stripped = re.sub(r"\([^)]*\)", "", base).strip()
        inner = re.findall(r"\(([^)]*)\)", base)
        if stripped:
            variants.append(stripped)
        variants.extend(inner)
    if " or " in lower:
        variants.extend([piece.strip() for piece in re.split(r"\bor\b", base, flags=re.IGNORECASE) if piece.strip()])
    if "," in base:
        variants.extend([piece.strip() for piece in base.split(",") if piece.strip()])
    return [variant for variant in variants if variant]


def _extract_realm_phrases_from_question(question: str) -> list[str]:
    text = normalize_text(question)
    phrases: list[str] = []
    patterns = [
        r"Zoogeographic Realm:\s*([A-Za-z][A-Za-z ()'\-/,]+)",
        r"native to the ([A-Za-z][A-Za-z ()'\-/,]+?) zoogeographic realm",
        r"found in the ([A-Za-z][A-Za-z ()'\-/,]+?) zoogeographic realm",
        r"within the ([A-Za-z][A-Za-z ()'\-/,]+?) zoogeographic realm",
        r"exclusive(?:ly)? within the ([A-Za-z][A-Za-z ()'\-/,]+?) zoogeographic realm",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            captured = normalize_text(match.group(1) if match.lastindex else match.group(0))
            if captured:
                phrases.append(captured)
    if re.search(r"\bEastern Hemisphere(?:'s)?\b", text, flags=re.IGNORECASE):
        phrases.append("Eastern Hemisphere")
    return list(dict.fromkeys(phrases))


def _extract_nest_phrases_from_question(question: str) -> list[str]:
    text = normalize_text(question)
    phrases: list[str] = []
    patterns = [
        r"(?:build|construct) ([A-Za-z0-9 ()/\-]+? nests?)",
        r"use ([A-Za-z0-9 ()/\-]+?) as (?:their )?primary nest type",
        r"nests? that (?:are|is) (?:either )?([A-Za-z0-9 (),/\-]+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            captured = normalize_text(match.group(1))
            if captured:
                phrases.append(captured)
    return list(dict.fromkeys(phrases))


@lru_cache(maxsize=2)
def _nest_phrase_mapping_from_questions() -> dict[str, list[str]]:
    question_path = Path("question") / "List-Global" / "List-Global_questions.jsonl"
    mapping: dict[str, set[str]] = {}
    if not question_path.exists():
        return {}
    with question_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            search_conditions = str((obj.get("provenance") or {}).get("search_conditions", ""))
            value = _extract_field_value(search_conditions, "Nest Type")
            if not value:
                continue
            for phrase in _extract_nest_phrases_from_question(str(obj.get("question", ""))):
                key = normalize_text(phrase).lower()
                if key:
                    mapping.setdefault(key, set()).add(value)
    return {key: sorted(values) for key, values in mapping.items()}


def _resolve_question_nest_values(question: str, actual_nest_values: list[str]) -> tuple[list[str], list[str], list[str]]:
    actual_values = [normalize_text(value) for value in actual_nest_values]
    matched_values: list[str] = []
    matched_phrases: list[str] = []
    unresolved: list[str] = []

    direct_nest_value = _extract_field_value(question, "Nest Type")
    direct_match = _lookup_actual_value(actual_values, direct_nest_value)
    if direct_match:
        return [direct_match], [f"Nest Type: {direct_nest_value}"], []

    if re.search(r"\bnest", question, flags=re.IGNORECASE):
        inline_codes = [normalize_text(code).upper() for code in _extract_codes_in_parentheses(question)]
        if inline_codes:
            joined = ",".join(inline_codes)
            exact_joined = _lookup_actual_value(actual_values, joined)
            if exact_joined:
                return [exact_joined], [joined], []

    mapping = _nest_phrase_mapping_from_questions()
    for phrase in _extract_nest_phrases_from_question(question):
        key = normalize_text(phrase).lower()
        if key in {"their nest", "their nests", "the nest", "the nests"}:
            continue
        values = [_lookup_actual_value(actual_values, raw_value) for raw_value in mapping.get(key, [])]
        values = [value for value in values if value]
        if len(values) == 1:
            _append_unique(matched_values, values[0])
            _append_unique(matched_phrases, phrase)
        elif len(values) > 1:
            unresolved.append(f"nest_type:{phrase}=>{','.join(values)}")
        else:
            lowered_phrase = phrase.lower()
            ordered_matches: list[tuple[int, str]] = []
            for alias, code in _manual_nest_aliases().items():
                if alias in lowered_phrase:
                    position = lowered_phrase.index(alias)
                    ordered_matches.append((position, code))
            ordered_codes = [code for _, code in sorted(ordered_matches)]
            if ordered_codes:
                exact_joined = _lookup_actual_value(actual_values, ",".join(ordered_codes))
                if exact_joined:
                    _append_unique(matched_values, exact_joined)
                    _append_unique(matched_phrases, phrase)
                    continue
                if len(ordered_codes) == 1:
                    exact_single = _lookup_actual_value(actual_values, ordered_codes[0])
                    if exact_single:
                        _append_unique(matched_values, exact_single)
                        _append_unique(matched_phrases, phrase)
                        continue
            unresolved.append(f"nest_type:{phrase}")

    return matched_values, matched_phrases, unresolved


@lru_cache(maxsize=2)
def _realm_phrase_mapping_from_questions() -> dict[str, list[str]]:
    question_path = Path("question") / "List-Global" / "List-Global_questions.jsonl"
    mapping: dict[str, set[str]] = {}
    if not question_path.exists():
        return {}
    with question_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            provenance = obj.get("provenance") or {}
            code = _extract_realm_code(str(provenance.get("search_conditions", "")))
            if not code:
                continue
            for phrase in _extract_realm_phrases_from_question(str(obj.get("question", ""))):
                for variant in _realm_phrase_variants(phrase):
                    key = _normalize_realm_phrase_key(variant)
                    if not key:
                        continue
                    mapping.setdefault(key, set()).add(code)
    return {key: sorted(values) for key, values in mapping.items()}


def _resolve_question_realm_codes(
    question: str,
    actual_realm_values: list[str],
    *,
    ambiguous_realm_policy: str = "skip",
) -> tuple[list[str], list[str], list[str], list[str]]:
    actual_values = {normalize_text(value).upper() for value in actual_realm_values}
    matched_codes: list[str] = []
    matched_phrases: list[str] = []
    unresolved: list[str] = []
    applied_ambiguous_codes: list[str] = []

    explicit_code_patterns = [
        r"Zoogeographic Realm[: ]+([A-Z]{1,8})\b",
        r"\bRealm\s+([A-Z]{1,8})\b",
    ]
    for pattern in explicit_code_patterns:
        for match in re.finditer(pattern, question):
            code = normalize_text(match.group(1)).upper()
            if code in actual_values:
                _append_unique(matched_codes, code)
                _append_unique(matched_phrases, normalize_text(match.group(0)))
        if matched_codes:
            return matched_codes, matched_phrases, unresolved, applied_ambiguous_codes

    mapping = _realm_phrase_mapping_from_questions()
    for phrase in _extract_realm_phrases_from_question(question):
        codes: list[str] = []
        exact_key = _normalize_realm_phrase_key(phrase)
        exact_codes = [code for code in mapping.get(exact_key, []) if code in actual_values]
        if len(exact_codes) == 1:
            codes = list(exact_codes)
        else:
            for variant in _realm_phrase_variants(phrase):
                key = _normalize_realm_phrase_key(variant)
                for code in mapping.get(key, []):
                    if code in actual_values:
                        _append_unique(codes, code)
        if len(codes) == 1:
            _append_unique(matched_codes, codes[0])
            _append_unique(matched_phrases, phrase)
        elif len(codes) > 1:
            if ambiguous_realm_policy == "union":
                for code in codes:
                    _append_unique(matched_codes, code)
                    _append_unique(applied_ambiguous_codes, code)
                _append_unique(matched_phrases, phrase)
            else:
                unresolved.append(f"realm:{phrase}=>{','.join(codes)}")
        else:
            unresolved.append(f"realm:{phrase}")

    if matched_codes:
        return matched_codes, matched_phrases, unresolved, applied_ambiguous_codes

    return matched_codes, matched_phrases, unresolved, applied_ambiguous_codes


def parse_birdbase_constraints_from_text(
    question: str,
    column_map: dict,
    mode: str,
    *,
    text_source: str = "question",
    ambiguous_realm_policy: str = "skip",
) -> dict:
    text = normalize_text(question)
    lower = text.lower()
    constraints: dict[str, Any] = {
        "iucn": [],
        "primary_habitat": [],
        "primary_diet": [],
        "nest_type": [],
        "average_mass_filters": [],
        "order": [],
        "family": [],
        "realm": [],
        "flags_yes": [],
        "flags_no": [],
        "unresolved_constraints": [],
        "matched_phrases": {},
        "constraint_sources": {},
        "ambiguous_realm_policy": ambiguous_realm_policy,
        "applied_ambiguous_realm_codes": [],
        "raw_text": text,
        "mode": mode,
        "text_source": text_source,
    }

    actual_iucn_values = list(column_map.get("_iucn_values", []))
    actual_habitat_values = list(column_map.get("_habitat_values", []))
    actual_diet_values = list(column_map.get("_diet_values", []))
    actual_nest_values = list(column_map.get("_nest_type_values", []))

    iucn_patterns = [
        ("CR (PEW)", [r"critically endangered \(possibly extinct in the wild\)", r"(?<![A-Za-z])cr\s*\(pew\)(?![A-Za-z])"]),
        ("CR (PE)", [r"critically endangered \(possibly extinct\)", r"(?<![A-Za-z])cr\s*\(pe\)(?![A-Za-z])"]),
        ("EW", [r"\bextinct in the wild\b", r"\bew\b"]),
        ("EX", [r"\bextinct\b", r"\bex\b"]),
        ("CR", [r"\bcritically endangered\b", r"\bcr\b"]),
        ("EN", [r"\bendangered\b", r"\ben\b"]),
        ("VU", [r"\bvulnerable\b", r"\bvu\b"]),
        ("NT", [r"\bnear threatened\b", r"\bnt\b"]),
        ("LC", [r"\bleast concern\b", r"\blc\b"]),
        ("DD", [r"\bdata deficient\b", r"\bdd\b"]),
    ]
    for value, patterns in iucn_patterns:
        matched, phrase = _has_any_pattern(text, patterns)
        if matched:
            constraints["iucn"].append(value)
            _record_match_with_source(
                constraints,
                "iucn",
                phrase,
                value=value,
                source="provenance_pattern" if text_source == "provenance" else "manual_alias",
            )
            break
    direct_iucn_value = _lookup_actual_value(actual_iucn_values, _extract_field_value(text, "IUCN Status"))
    if direct_iucn_value:
        constraints["iucn"] = [direct_iucn_value]
        _record_match_with_source(
            constraints,
            "iucn",
            f"IUCN Status: {direct_iucn_value}",
            value=direct_iucn_value,
            source="search_condition_format",
        )

    habitat_map = {
        "Forest": ["forest", "forested"],
        "Wetland": ["wetland", "wetlands", "marsh", "bog", "swamp"],
        "Grassland": ["grassland", "grasslands"],
        "Shrub": ["shrub", "shrubland", "shrublands"],
        "Woodland": ["woodland", "woodlands"],
        "Coastal": ["coastal", "shore", "estuar", "mangrove"],
        "Sea": ["sea", "marine", "pelagic"],
        "Rocky": ["rocky", "cliff"],
        "Riparian": ["riparian", "riverine"],
        "Savanna": ["savanna", "savannah"],
        "Plains": ["plain", "plains"],
        "Desert": ["desert", "arid"],
        "Artificial": ["artificial", "urban", "farmland", "agricultural"],
        "Bamboo": ["bamboo"],
    }
    direct_habitat_value = _lookup_actual_value(actual_habitat_values, _extract_field_value(text, "Primary Habitat"))
    if direct_habitat_value:
        constraints["primary_habitat"].append(direct_habitat_value)
        _record_match_with_source(
            constraints,
            "primary_habitat",
            f"Primary Habitat: {direct_habitat_value}",
            value=direct_habitat_value,
            source="search_condition_format",
        )
    for canonical, patterns in habitat_map.items():
        matched_phrase = next((pattern for pattern in patterns if pattern in lower), "")
        actual_value = _lookup_actual_value(actual_habitat_values, canonical)
        if matched_phrase and actual_value:
            constraints["primary_habitat"].append(actual_value)
            _record_match_with_source(constraints, "primary_habitat", matched_phrase, value=actual_value, source="manual_alias")

    diet_map = {
        "No Information": ["no information recorded", "no information", "no dietary information"],
        "Invertebrate": ["invertebrate", "invertebrates", "arthropod", "insect"],
        "Fruit": ["fruit", "frugiv"],
        "Seed": ["seed", "seeds", "graniv"],
        "Nectar": ["nectar", "nectariv"],
        "Fish": ["fish", "pisciv"],
        "Vertebrate": ["vertebrate", "mammal", "reptile", "amphibian"],
        "Omnivore": ["omnivore", "omnivorous", "omnivory"],
        "Herbivore": ["herbivore", "herbivorous", "herbivory"],
        "Plant": ["plant matter", "plant-based", "plant"],
        "Carnivore": ["carnivore", "carnivorous", "carnivory"],
        "Scavenger": ["scavenger", "scavenging", "carrion"],
        "Ovivore": ["egg", "ovivore"],
        "Beeswax": ["beeswax"],
    }
    direct_diet_value = _lookup_actual_value(actual_diet_values, _extract_field_value(text, "Primary Diet"))
    if direct_diet_value:
        constraints["primary_diet"].append(direct_diet_value)
        _record_match_with_source(
            constraints,
            "primary_diet",
            f"Primary Diet: {direct_diet_value}",
            value=direct_diet_value,
            source="search_condition_format",
        )
    for canonical, patterns in diet_map.items():
        matched_phrase = next((pattern for pattern in patterns if pattern in lower), "")
        actual_value = _lookup_actual_value(actual_diet_values, canonical)
        if matched_phrase and actual_value:
            constraints["primary_diet"].append(actual_value)
            _record_match_with_source(constraints, "primary_diet", matched_phrase, value=actual_value, source="manual_alias")

    nest_values, nest_phrases, unresolved_nests = _resolve_question_nest_values(text, actual_nest_values)
    for nest_value in nest_values:
        constraints["nest_type"].append(nest_value)
    for nest_phrase in nest_phrases:
        target_value = nest_values[0] if len(nest_values) == 1 else ",".join(nest_values)
        source = "search_condition_format" if nest_phrase.startswith("Nest Type:") else "question_provenance_alignment"
        _record_match_with_source(constraints, "nest_type", nest_phrase, value=target_value, source=source)
    constraints["unresolved_constraints"].extend(unresolved_nests)
    if not nest_values:
        nest_aliases = _manual_nest_aliases()
        for phrase, code in nest_aliases.items():
            if phrase in lower:
                actual_value = _lookup_actual_value(actual_nest_values, code)
                if actual_value:
                    constraints["nest_type"].append(actual_value)
                    _record_match_with_source(constraints, "nest_type", phrase, value=actual_value, source="manual_alias")

    mass_match = re.search(
        r"(?:among the|top)\s+(heaviest|lightest)\s+(\d{1,2})%\s+(?:of all bird species\s+)?by average (?:body )?mass",
        lower,
        flags=re.IGNORECASE,
    )
    if mass_match:
        direction = normalize_text(mass_match.group(1)).lower()
        percentile = int(mass_match.group(2))
        quantile_lookup = {
            ("lightest", 5): 0.05,
            ("lightest", 10): 0.10,
            ("lightest", 20): 0.20,
            ("heaviest", 20): 0.80,
            ("heaviest", 10): 0.90,
            ("heaviest", 5): 0.95,
        }
        quantile = quantile_lookup.get((direction, percentile))
        if quantile is not None:
            constraints["average_mass_filters"].append(
                {
                    "direction": direction,
                    "percentile": percentile,
                    "quantile": quantile,
                    "phrase": normalize_text(mass_match.group(0)),
                }
            )
            _record_match_with_source(
                constraints,
                "average_mass_filters",
                normalize_text(mass_match.group(0)),
                value=f"{direction}_{percentile}",
                source="manual_pattern",
            )

    island_negative_patterns = [
        "not island endemic",
        "not an island endemic",
        "are not island endemics",
        "non-island endemic",
        "not island endemics",
    ]
    island_positive_patterns = [
        "island endemic",
        "island endemism",
        "insular",
        "island species",
    ]
    island_negative = next((pattern for pattern in island_negative_patterns if pattern in lower), "")
    island_positive = next((pattern for pattern in island_positive_patterns if pattern in lower), "")
    if island_negative:
        constraints["flags_no"].append("island")
        _record_match_with_source(constraints, "flags_no", island_negative, value="island", source="manual_alias")
    elif island_positive:
        constraints["flags_yes"].append("island")
        _record_match_with_source(constraints, "flags_yes", island_positive, value="island", source="manual_alias")

    movement_patterns = {
        "mig": ["migratory", "migrant", "migration"],
        "alt": ["altitudinal"],
        "irreg": ["irregular"],
        "disp": ["dispersive", "dispersal"],
        "sed": ["sedentary", "resident"],
    }
    migratory_negative_patterns = ["not migratory", "non-migratory", "not a migratory species"]
    migratory_negative = next((pattern for pattern in migratory_negative_patterns if pattern in lower), "")
    if migratory_negative:
        constraints["flags_no"].append("mig")
        _record_match_with_source(constraints, "flags_no", migratory_negative, value="mig", source="manual_alias")
    for flag_name, patterns in movement_patterns.items():
        if flag_name == "mig" and migratory_negative:
            continue
        matched_phrase = next((pattern for pattern in patterns if pattern in lower), "")
        if matched_phrase:
            constraints["flags_yes"].append(flag_name)
            _record_match_with_source(constraints, "flags_yes", matched_phrase, value=flag_name, source="manual_alias")

    # Taxonomy soft matches against actual values when question mentions them directly.
    actual_order_values = set(column_map.get("_order_values", []))
    actual_family_values = set(column_map.get("_family_values", []))
    for order_value in actual_order_values:
        if order_value and order_value.lower() in lower:
            constraints["order"].append(order_value)
            _record_match_with_source(constraints, "order", order_value, value=order_value, source="unique_value_match")
    for family_value in actual_family_values:
        if family_value and family_value.lower() in lower:
            constraints["family"].append(family_value)
            _record_match_with_source(constraints, "family", family_value, value=family_value, source="unique_value_match")

    if "zoogeographic realm" in lower or "realm" in lower:
        exact_realm_values = column_map.get("_realm_values", [])
        direct_realm_value = _lookup_actual_value(exact_realm_values, _extract_field_value(text, "Zoogeographic Realm"), uppercase=True)
        if direct_realm_value:
            realm_values = [direct_realm_value]
            matched_realm_phrases = [f"Zoogeographic Realm: {direct_realm_value}"]
            unresolved_realms = []
            applied_ambiguous_codes = []
        else:
            realm_values, matched_realm_phrases, unresolved_realms, applied_ambiguous_codes = _resolve_question_realm_codes(
                text,
                exact_realm_values,
                ambiguous_realm_policy=ambiguous_realm_policy,
            )
        for realm_value in realm_values:
            constraints["realm"].append(realm_value)
        constraints["applied_ambiguous_realm_codes"] = list(applied_ambiguous_codes)
        for phrase in matched_realm_phrases:
            target_value = realm_values[0] if len(realm_values) == 1 else ",".join(realm_values)
            source = "search_condition_format" if phrase.startswith("Zoogeographic Realm:") else (
                "provenance_pattern" if text_source == "provenance" else "question_provenance_alignment"
            )
            _record_match_with_source(constraints, "realm", phrase, value=target_value, source=source)
        constraints["unresolved_constraints"].extend(unresolved_realms)
        if not realm_values and not unresolved_realms:
            constraints["unresolved_constraints"].append("realm")

    for key in ["iucn", "primary_habitat", "primary_diet", "nest_type", "order", "family", "realm", "flags_yes", "flags_no"]:
        constraints[key] = list(dict.fromkeys(constraints[key]))
    constraints["unresolved_constraints"] = list(dict.fromkeys(constraints["unresolved_constraints"]))
    return constraints


def apply_birdbase_constraints(df: pd.DataFrame, column_map: dict, constraints: dict) -> tuple[pd.DataFrame, dict]:
    mask = pd.Series(True, index=df.index)
    debug: dict[str, Any] = {
        "filters": [],
        "rows_before": int(len(df)),
        "ambiguous_realm_policy": constraints.get("ambiguous_realm_policy", "skip"),
        "applied_ambiguous_realm_codes": list(constraints.get("applied_ambiguous_realm_codes", [])),
    }

    def _apply_equals_list(column_key: str, values: list[str], label: str) -> None:
        nonlocal mask
        column = column_map.get(column_key)
        if not column or column not in df.columns or not values:
            return
        series = df[column].astype(str).str.strip()
        local_mask = series.isin(values)
        debug["filters"].append({"field": label, "values": values, "matched_rows": int(local_mask.sum())})
        mask &= local_mask

    _apply_equals_list("iucn", constraints.get("iucn", []), "iucn")
    _apply_equals_list("primary_habitat", constraints.get("primary_habitat", []), "primary_habitat")
    _apply_equals_list("primary_diet", constraints.get("primary_diet", []), "primary_diet")
    _apply_equals_list("nest_type", constraints.get("nest_type", []), "nest_type")
    _apply_equals_list("order", constraints.get("order", []), "order")
    _apply_equals_list("family", constraints.get("family", []), "family")

    realm_values = constraints.get("realm", [])
    realm_col = column_map.get("realm")
    if realm_col and realm_values:
        realm_series = df[realm_col].astype(str).str.strip().str.upper()
        local_mask = pd.Series(False, index=df.index)
        for value in realm_values:
            local_mask |= realm_series == str(value).strip().upper()
        debug["filters"].append({"field": "realm", "values": realm_values, "matched_rows": int(local_mask.sum())})
        mask &= local_mask

    for flag in constraints.get("flags_yes", []):
        column = column_map.get(flag)
        if not column or column not in df.columns:
            continue
        if flag == "mig":
            local_mask = df[column].astype(str).str.strip().isin(["1", "1.0", "2", "2.0"])
        else:
            local_mask = yes_mask(df[column])
        debug["filters"].append({"field": flag, "values": ["yes"], "matched_rows": int(local_mask.sum())})
        mask &= local_mask

    for flag in constraints.get("flags_no", []):
        column = column_map.get(flag)
        if not column or column not in df.columns:
            continue
        local_mask = no_mask(df[column])
        debug["filters"].append({"field": flag, "values": ["no"], "matched_rows": int(local_mask.sum())})
        mask &= local_mask

    if constraints.get("average_mass_filters"):
        mass_col = column_map.get("average_mass")
        if mass_col and mass_col in df.columns:
            mass_series = pd.to_numeric(df[mass_col], errors="coerce")
            for mass_filter in constraints["average_mass_filters"]:
                quantile = mass_filter.get("quantile")
                direction = str(mass_filter.get("direction", "")).strip().lower()
                percentile = mass_filter.get("percentile")
                if quantile is None or direction not in {"heaviest", "lightest"}:
                    continue
                threshold = float(mass_series.quantile(float(quantile)))
                local_mask = mass_series >= threshold if direction == "heaviest" else mass_series <= threshold
                debug["filters"].append(
                    {
                        "field": "average_mass",
                        "values": [f"{direction}_{percentile}%"],
                        "matched_rows": int(local_mask.sum()),
                        "threshold": threshold,
                    }
                )
                mask &= local_mask

    matched_df = df[mask].copy()
    debug["rows_after"] = int(len(matched_df))
    debug["unresolved_constraints"] = list(constraints.get("unresolved_constraints", []))
    return matched_df, debug


def latin_species_list(df: pd.DataFrame, column_map: dict) -> list[str]:
    latin_col = column_map.get("latin_name")
    if not latin_col or latin_col not in df.columns:
        genus_col = column_map.get("genus")
        species_col = column_map.get("species")
        if genus_col and species_col and genus_col in df.columns and species_col in df.columns:
            values = [
                f"{normalize_text(genus)} {normalize_text(species)}".strip()
                for genus, species in zip(df[genus_col].tolist(), df[species_col].tolist())
            ]
        else:
            values = []
    else:
        values = [normalize_text(value) for value in df[latin_col].astype(str).tolist()]
    cleaned = sorted({value for value in values if value and value.lower() != "nan"})
    return cleaned


def enrich_column_map_with_values(df: pd.DataFrame, column_map: dict) -> dict:
    enriched = dict(column_map)
    enriched["_order_values"] = _column_unique_values(df, column_map.get("order"))
    enriched["_family_values"] = _column_unique_values(df, column_map.get("family"))
    enriched["_realm_values"] = sorted({normalize_text(value).upper() for value in _column_unique_values(df, column_map.get("realm")) if normalize_text(value)})
    enriched["_habitat_values"] = _column_unique_values(df, column_map.get("primary_habitat"))
    enriched["_diet_values"] = _column_unique_values(df, column_map.get("primary_diet"))
    enriched["_nest_type_values"] = _column_unique_values(df, column_map.get("nest_type"))
    enriched["_iucn_values"] = _column_unique_values(df, column_map.get("iucn"))
    return enriched
