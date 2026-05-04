"""Dataclasses for taxonomy backbone artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class CanonicalTaxonNode:
    taxon_id: str
    rank: str
    scientific_name: str
    english_name_primary: str
    order_name: str
    family_name: str
    genus_name: str
    parent_taxon_id: str
    canonical_source: str
    canonical_release: str
    avibase_id: str
    cornell_species_code: str
    bow_url: str
    iucn_status: str
    taxonomy_status: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CanonicalTaxonEdge:
    src_id: str
    dst_id: str
    relation_type: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TaxonomyCrosswalk:
    crosswalk_id: str
    canonical_taxon_id: str
    external_source: str
    external_release: str
    external_rank: str
    external_scientific_name: str
    external_english_name: str
    external_code: str
    external_id: str
    match_method: str
    match_confidence: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TaxonomyConflict:
    conflict_id: str
    canonical_taxon_id: str
    external_source: str
    conflict_type: str
    canonical_value: str
    external_value: str
    resolution_status: str
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TaxonomyAlias:
    alias_id: str
    canonical_taxon_id: str
    alias_value: str
    alias_type: str
    alias_source: str
    alias_release: str

    def to_dict(self) -> dict:
        return asdict(self)
