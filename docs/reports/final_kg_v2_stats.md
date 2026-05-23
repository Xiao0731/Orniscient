# Final KG v2 Statistics

Read-only statistics generated from `claims_final_global_v2` and `facts_final_global_v2`. This report estimates the current core Taxon-Fact-Evidence-Chunk graph only; it excludes future Object/Concept nodes, full taxonomy backbone, aliases, crosswalks, vector indexes, and Neo4j materialization side effects.

## Overall Artifact Scale

| Metric | Count |
| --- | ---: |
| Processed BOW chunks | 309,369 |
| Species claims | 912,598 |
| Family claims | 8,563 |
| Total claims | 921,161 |
| Species facts | 883,500 |
| Family facts | 8,362 |
| Total facts | 891,862 |
| Evidences | 815,896 |
| Fact-Evidence links | 915,793 |
| Supplement accepted claims | 331,827 |
| Supplement covered chunks | 93,542 |
| Hit soft-cap chunks | 33,211 |
| Fact ID collisions | 0 |
| Extractor failures | 0 |

## Core Graph Size Estimate

| Node Label | Count |
| --- | ---: |
| Taxon | 11,122 |
| Fact | 891,862 |
| Evidence | 815,896 |
| Chunk | 309,369 |
| Total core nodes | 2,028,249 |

| Concept Edge Type | Actual Relation Name | Count |
| --- | --- | ---: |
| Taxon -> Fact | HAS_FACT | 891,862 |
| Fact -> Evidence | SUPPORTED_BY | 915,793 |
| Evidence -> Chunk | FROM_CHUNK | 815,896 |
| Total core edges |  | 2,623,551 |

## Fact Domain Distribution

| Fact Domain | Fact Count | Share |
| --- | ---: | ---: |
| MorphologyAndIdentification | 217,286 | 24.36% |
| LifeHistoryAndBreeding | 137,996 | 15.47% |
| EcologyAndDiet | 120,624 | 13.53% |
| DistributionAndMovement | 102,493 | 11.49% |
| ConservationAndResearch | 85,579 | 9.60% |
| TaxonomyAndPhylogeny | 77,600 | 8.70% |
| VocalAndBehavior | 76,755 | 8.61% |
| Habitat | 73,529 | 8.24% |

## Top Fact Predicates

| Predicate | Fact Count |
| --- | ---: |
| HAS_PLUMAGE_TRAIT | 88,726 |
| INHABITS_BIOME | 61,235 |
| OCCURS_IN | 49,913 |
| EATS_ITEM | 49,404 |
| HAS_VOCALIZATION_TYPE | 42,121 |
| HAS_SUBSPECIES | 31,396 |
| THREATENED_BY | 21,709 |
| HAS_NEST_STRUCTURE | 20,342 |
| HAS_DIAGNOSTIC_TRAIT | 19,945 |
| EATS_CATEGORY | 19,633 |
| HAS_PARENTAL_ROLE | 19,075 |
| FORAGES_IN_STRATUM | 18,980 |
| HAS_POPULATION_TREND | 18,817 |
| FORAGES_BY | 18,706 |
| HAS_STRUCTURE_TRAIT | 17,377 |
| HAS_SEXUAL_DIMORPHISM | 16,829 |
| HAS_BODY_LENGTH | 16,534 |
| BREEDS_DURING | 16,496 |
| HAS_BODY_MASS | 15,763 |
| HAS_DISTRIBUTION_NOTE | 15,370 |
| HAS_IUCN_STATUS | 15,166 |
| RELATED_TO | 14,646 |
| HAS_MIGRATION_PATTERN | 14,634 |
| HAS_DEMOGRAPHIC_NOTE | 13,663 |
| NESTS_AT | 13,002 |
| HAS_CONSERVATION_ACTION | 12,263 |
| USES_MICROHABITAT | 12,021 |
| HAS_TAXONOMIC_NOTE | 11,924 |
| HAS_MOLT_PATTERN | 11,839 |
| HAS_CLUTCH_SIZE | 11,635 |

## Controlled Fact Domain and Predicate Schema

| Fact Domain | Predicate Count | Representative Predicates |
| --- | ---: | --- |
| TaxonomyAndPhylogeny | 8 | HAS_SUBSPECIES, HAS_GEOGRAPHIC_VARIATION, HAS_SUBSPECIES_TRAIT, HAS_SUBSPECIES_DISTRIBUTION, HYBRIDIZES_WITH |
| MorphologyAndIdentification | 13 | HAS_BODY_LENGTH, HAS_BODY_MASS, HAS_WING_LENGTH, HAS_TAIL_LENGTH, HAS_BILL_LENGTH |
| DistributionAndMovement | 8 | OCCURS_IN, ENDEMIC_TO, BREEDS_IN, WINTERS_IN, MIGRATES_VIA |
| Habitat | 2 | INHABITS_BIOME, USES_MICROHABITAT |
| EcologyAndDiet | 5 | EATS_CATEGORY, EATS_ITEM, FORAGES_BY, FORAGES_IN_STRATUM, HAS_ECOLOGICAL_ROLE |
| VocalAndBehavior | 18 | HAS_VOCALIZATION_TYPE, CALLS_DURING, HAS_NONVOCAL_SOUND, HAS_SOUND_DIAGNOSTIC, HAS_SOCIAL_BEHAVIOR |
| LifeHistoryAndBreeding | 10 | BREEDS_DURING, NESTS_AT, HAS_NEST_STRUCTURE, HAS_EGG_TRAIT, HAS_CLUTCH_SIZE |
| ConservationAndResearch | 10 | HAS_IUCN_STATUS, HAS_POPULATION_TREND, THREATENED_BY, HAS_CONSERVATION_ACTION, INTERACTS_WITH_HUMANS |

## Supplementary Claim Extraction Summary

| Item | Count / Value |
| --- | ---: |
| Old official claims | 589,334 |
| Supplement raw claims | 331,940 |
| Supplement accepted claims | 331,827 |
| Strict duplicates dropped | 113 |
| Supplement covered chunks | 93,542 |
| Hit soft-cap chunks | 33,211 |
| Final merged claims | 921,161 |
| Possible near-duplicate audit rows | 12,178 |

The original Claim extraction policy had a 2/4 per-chunk claim cap. A total of 93,542 chunks were identified as high-risk at/over-cap chunks. The final supplementary strategy used a single-pass additional-6 extraction; 331,827 supplementary claims were accepted into Claim v2 after strict deduplication. Chunks that hit the soft cap are retained as a high-recall expansion list for future continuation passes.

## Fact Rebuild Policy and Integrity Checks

| Policy / Check | Status |
| --- | --- |
| Subject/domain quota | removed |
| Evidence max-2 cap | removed |
| Fact ID strategy | typed stable group key + 32-hex SHA1 |
| Fact ID collision | 0 |
| Integrity check | ok |
| final facts equal grouped candidates | ok |
