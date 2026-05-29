# Question Placeholder Replacement Summary

- Question root: `question`
- Backup root: `question_anonymized_backup`
- Backup status: `existing`
- Replacement scope: `question` and `answer` fields only.
- Leakage-sensitive tasks are skipped by design.

| Dataset | Total rows | Replaced rows | Skipped rows | Rows still containing placeholders | Warnings |
|---|---:|---:|---:|---:|---:|
| Bird-Classify | 500 | 0 | 500 | 0 | 0 |
| Bird-Comp | 986 | 985 | 1 | 0 | 0 |
| Bird-Con | 217 | 217 | 0 | 0 | 0 |
| Bird-Eco | 216 | 216 | 0 | 0 | 0 |
| Bird-Geo | 448 | 448 | 0 | 0 | 0 |
| Bird-ID | 990 | 0 | 990 | 0 | 0 |
| Bird-Life | 446 | 446 | 0 | 0 | 0 |
| Bird-Plan | 63 | 63 | 0 | 0 | 0 |
| Bird-Reason | 219 | 219 | 0 | 0 | 0 |
| Bird-Taxonomy | 840 | 836 | 4 | 4 | 0 |
| List-Global | 200 | 0 | 200 | 0 | 0 |
| QA-MC | 1235 | 1235 | 0 | 0 | 0 |
| QA-SA | 1232 | 1232 | 0 | 0 | 0 |
| QA-SC | 2450 | 2421 | 29 | 26 | 0 |

## Before/After Examples

### Bird-Comp

- `bird_comp_0001` target=`Nothoprocta taczanowskii`

  Before question:
  > Based on the provided text, how can [the bird] be distinguished from the form described as 'N. godmani' in terms of its taxonomic relationship and morphological characteristics?

  After question:
  > Based on the provided text, how can Nothoprocta taczanowskii be distinguished from the form described as 'N. godmani' in terms of its taxonomic relationship and morphological characteristics?

  Before answer:
  > [The bird] is distinguished from the form described as 'N. godmani' primarily through taxonomic classification and life stage differences. According to the text, 'N. godmani' is considered an immature form of [the bird], indicating that it is not a separate species but rather a younger version of the same species. Morphologically, this suggests that 'N. godmani' likely exhibits characteristics typical of immature individuals, such as browner chest and upperparts, light brown flacks with black spotting, and more ochraceous bars on the remiges, as described for immature [the bird]. In contrast, adult [the bird] has a distinctive long curved bill, dull breast, pale abdomen, and specific plumage

  After answer:
  > Nothoprocta taczanowskii is distinguished from the form described as 'N. godmani' primarily through taxonomic classification and life stage differences. According to the text, 'N. godmani' is considered an immature form of Nothoprocta taczanowskii, indicating that it is not a separate species but rather a younger version of the same species. Morphologically, this suggests that 'N. godmani' likely exhibits characteristics typical of immature individuals, such as browner chest and upperparts, light brown flacks with black spotting, and more ochraceous bars on the remiges, as described for immature Nothoprocta taczanowskii. In contrast, adult Nothoprocta taczanowskii has a distinctive long curv

- `bird_comp_0002` target=`Nothura boraquira`

  Before question:
  > Based on the Identification section, how can [the bird] be distinguished from N. maculosa in terms of morphological features?

  After question:
  > Based on the Identification section, how can Nothura boraquira be distinguished from N. maculosa in terms of morphological features?

  Before answer:
  > [The bird] can be distinguished from N. maculosa by the arrangement of streaks over the neck, where [the bird] has three visible rows or stripes: one on the central hindneck, a second and often boldest row from the ear-coverts to the sides of the lower neck, and a usually less obvious third along the mid-foreneck. Additionally, [the bird] differs from congeners in having lesser underwing-coverts barred, which is a specific feature not mentioned for N. maculosa in this context.

  After answer:
  > Nothura boraquira can be distinguished from N. maculosa by the arrangement of streaks over the neck, where Nothura boraquira has three visible rows or stripes: one on the central hindneck, a second and often boldest row from the ear-coverts to the sides of the lower neck, and a usually less obvious third along the mid-foreneck. Additionally, Nothura boraquira differs from congeners in having lesser underwing-coverts barred, which is a specific feature not mentioned for N. maculosa in this context.

- `bird_comp_0003` target=`Mareca marecula`

  Before question:
  > Based on the systematics history, what is the taxonomic relationship of [the bird] to other species, and what major physical distinctions are implied from its classification?

  After question:
  > Based on the systematics history, what is the taxonomic relationship of Mareca marecula to other species, and what major physical distinctions are implied from its classification?

  Before answer:
  > [The bird] is described as monotypic, meaning it has no recognized subspecies and is considered a distinct species without close phylogenetic relatives mentioned in the text. This classification implies that it lacks sister species or subspecies for direct comparison, and its major physical distinctions are not detailed in the provided text, as it is treated as a unique entity in its systematics.

  After answer:
  > Mareca marecula is described as monotypic, meaning it has no recognized subspecies and is considered a distinct species without close phylogenetic relatives mentioned in the text. This classification implies that it lacks sister species or subspecies for direct comparison, and its major physical distinctions are not detailed in the provided text, as it is treated as a unique entity in its systematics.

### Bird-Con

- `bird_con_0001` target=`Rhynchotus maculicollis`

  Before question:
  > What is the current IUCN conservation status and overall population trend for [the bird]?

  After question:
  > What is the current IUCN conservation status and overall population trend for Rhynchotus maculicollis?

- `bird_con_0002` target=`Hymenolaimus malacorhynchos`

  Before question:
  > Based on the provided monograph, what are the primary anthropogenic and environmental threats to [the bird]?

  After question:
  > Based on the provided monograph, what are the primary anthropogenic and environmental threats to Hymenolaimus malacorhynchos?

  Before answer:
  > The key threats to [the bird] include: 1. Predation by introduced mammals, especially stoats, which cause high nest failure and adult mortality, particularly during beech mast years. 2. Habitat degradation from hydroelectric schemes and mining activities, which alter clear, fast-flowing water systems. 3. Historical habitat loss due to grazing and clearance of riparian vegetation, reducing water quality. 4. Potential competition from introduced trout and habitat quality reduction from introduced algae like Didymo. 5. Increased frequency of major floods due to anthropogenic climate change, which destroy nests, reduce food resources, and displace juveniles.

  After answer:
  > The key threats to Hymenolaimus malacorhynchos include: 1. Predation by introduced mammals, especially stoats, which cause high nest failure and adult mortality, particularly during beech mast years. 2. Habitat degradation from hydroelectric schemes and mining activities, which alter clear, fast-flowing water systems. 3. Historical habitat loss due to grazing and clearance of riparian vegetation, reducing water quality. 4. Potential competition from introduced trout and habitat quality reduction from introduced algae like Didymo. 5. Increased frequency of major floods due to anthropogenic climate change, which destroy nests, reduce food resources, and displace juveniles.

- `bird_con_0003` target=`Mareca marecula`

  Before question:
  > What historical events led to the extinction of [the bird], and when was it last reported?

  After question:
  > What historical events led to the extinction of Mareca marecula, and when was it last reported?

  Before answer:
  > The [the bird] was hunted to extinction by whalers and sealers, with its last report from St Paul I in 1793.

  After answer:
  > The Mareca marecula was hunted to extinction by whalers and sealers, with its last report from St Paul I in 1793.

### Bird-Eco

- `bird_eco_0001` target=`Apteryx mantelli`

  Before question:
  > Based on the provided monograph, categorize the primary diet of [the bird] and list the specific taxonomic groups of invertebrates it consumes.

  After question:
  > Based on the provided monograph, categorize the primary diet of Apteryx mantelli and list the specific taxonomic groups of invertebrates it consumes.

  Before answer:
  > The primary diet of [the bird] is insectivorous and invertivorous, as it predominantly feeds on invertebrates from soil and leaf litter, with a minor inclusion of plant material. Specific taxonomic groups of invertebrates consumed include insects such as bugs (Hemiptera), larval and adult beetles (Coleoptera), and cranefly larvae (Tipulidae), as well as earthworms (Oligochaeta), spiders (Araneae), snails (Mollusca), amphipods, millipedes (Diplopoda), and centipedes (Chilopoda).

  After answer:
  > The primary diet of Apteryx mantelli is insectivorous and invertivorous, as it predominantly feeds on invertebrates from soil and leaf litter, with a minor inclusion of plant material. Specific taxonomic groups of invertebrates consumed include insects such as bugs (Hemiptera), larval and adult beetles (Coleoptera), and cranefly larvae (Tipulidae), as well as earthworms (Oligochaeta), spiders (Araneae), snails (Mollusca), amphipods, millipedes (Diplopoda), and centipedes (Chilopoda).

- `bird_eco_0002` target=`Stictonetta naevosa`

  Before question:
  > Based on the provided monograph, what is the primary dietary niche of [the bird], and what specific food items does it consume according to the text?

  After question:
  > Based on the provided monograph, what is the primary dietary niche of Stictonetta naevosa, and what specific food items does it consume according to the text?

  Before answer:
  > The primary dietary niche of [the bird] is herbivorous, specifically categorized as vegetarian with a focus on plant-based materials. According to the text, it consumes algae, seeds, and green parts of aquatic plants and grasses, along with minor quantities of aquatic invertebrates such as insects.

  After answer:
  > The primary dietary niche of Stictonetta naevosa is herbivorous, specifically categorized as vegetarian with a focus on plant-based materials. According to the text, it consumes algae, seeds, and green parts of aquatic plants and grasses, along with minor quantities of aquatic invertebrates such as insects.

- `bird_eco_0003` target=`Taoniscus nanus`

  Before question:
  > Based on its diet, what ecological role does [the bird] play in its ecosystem, and what specific evidence from its feeding behavior supports this role?

  After question:
  > Based on its diet, what ecological role does Taoniscus nanus play in its ecosystem, and what specific evidence from its feeding behavior supports this role?

  Before answer:
  > [The bird] plays a role in natural pest control and potentially seed dispersal within its ecosystem. Its diet includes various arthropods, particularly termites (Isoptera), which it actively digs out of their mounds, indicating it helps regulate termite populations. Additionally, it consumes seeds, such as those from grasses, suggesting it may contribute to seed dispersal, though the text does not specify if seeds are dispersed intact. The combination of insectivory and granivory positions [the bird] as an omnivore that influences both invertebrate populations and plant dynamics.

  After answer:
  > Taoniscus nanus plays a role in natural pest control and potentially seed dispersal within its ecosystem. Its diet includes various arthropods, particularly termites (Isoptera), which it actively digs out of their mounds, indicating it helps regulate termite populations. Additionally, it consumes seeds, such as those from grasses, suggesting it may contribute to seed dispersal, though the text does not specify if seeds are dispersed intact. The combination of insectivory and granivory positions Taoniscus nanus as an omnivore that influences both invertebrate populations and plant dynamics.

### Bird-Geo

- `bird_geo_0001` target=`Dendrocygna javanica`

  Before question:
  > Based on its distribution, which of the following best describes the primary geographic range of [the bird]?

  After question:
  > Based on its distribution, which of the following best describes the primary geographic range of Dendrocygna javanica?

- `bird_geo_0002` target=`Anas bernieri`

  Before question:
  > Based on its habitat description, which of the following best characterizes the primary breeding and non-breeding habitats of [the bird]?

  After question:
  > Based on its habitat description, which of the following best characterizes the primary breeding and non-breeding habitats of Anas bernieri?

- `bird_geo_0003` target=`Asarcornis scutulata`

  Before question:
  > Based on the provided text, what is the primary migration pattern of [the bird]?

  After question:
  > Based on the provided text, what is the primary migration pattern of Asarcornis scutulata?

### Bird-Life

- `bird_life_0001` target=`Bernier's Teal`

  Before question:
  > Based on the provided monograph, describe the courtship and mating system of [the bird], including details on sexual behaviors, vocalizations, and pair-bond dynamics.

  After question:
  > Based on the provided monograph, describe the courtship and mating system of Bernier's Teal, including details on sexual behaviors, vocalizations, and pair-bond dynamics.

  Before answer:
  > The courtship and mating system of [the bird] is characterized by monogamy with persistent pair-bonds, specific vocalizations, and territorial defense. [The bird] is monogamous, with pairs likely remaining together throughout the year, and the pair-bond persists across multiple seasons, indicating long-term commitment. During the breeding season, which starts as early as September with copulation observed in July, the male exhibits distinct vocalizations as part of courtship behavior: he gives short, quiet, multisyllabic whistles consisting of 3–10 notes over 2–5 seconds, described as 'crik-crik-crik', and also produces a loud 'whee-oo' call while standing or swimming. In contrast, the femal

  After answer:
  > The courtship and mating system of Bernier's Teal is characterized by monogamy with persistent pair-bonds, specific vocalizations, and territorial defense. Bernier's Teal is monogamous, with pairs likely remaining together throughout the year, and the pair-bond persists across multiple seasons, indicating long-term commitment. During the breeding season, which starts as early as September with copulation observed in July, the male exhibits distinct vocalizations as part of courtship behavior: he gives short, quiet, multisyllabic whistles consisting of 3–10 notes over 2–5 seconds, described as 'crik-crik-crik', and also produces a loud 'whee-oo' call while standing or swimming. In contrast, t

- `bird_life_0002` target=`Swan Goose`

  Before question:
  > Based on the breeding timeline of [the bird], describe the key phenological events from the start of the breeding season through to when most young have fledged, including the typical months for egg-laying and hatching.

  After question:
  > Based on the breeding timeline of Swan Goose, describe the key phenological events from the start of the breeding season through to when most young have fledged, including the typical months for egg-laying and hatching.

  Before answer:
  > The breeding season of [the bird] begins in the latter half of April, sometimes extending to late May, marking the onset of egg-laying. Hatching primarily occurs in late May and June, following an incubation period of approximately 28 days. By late August, most young have fledged, completing the breeding cycle. This timeline indicates that breeding activities are concentrated from mid-spring through late summer, with peak hatching in early summer and fledging by the end of summer.

  After answer:
  > The breeding season of Swan Goose begins in the latter half of April, sometimes extending to late May, marking the onset of egg-laying. Hatching primarily occurs in late May and June, following an incubation period of approximately 28 days. By late August, most young have fledged, completing the breeding cycle. This timeline indicates that breeding activities are concentrated from mid-spring through late summer, with peak hatching in early summer and fledging by the end of summer.

- `bird_life_0003` target=`Blue Duck`

  Before question:
  > Based on the provided monograph, describe the nest ecology of [the bird], including details on nest site selection, construction materials, and the physical structure of the nest.

  After question:
  > Based on the provided monograph, describe the nest ecology of Blue Duck, including details on nest site selection, construction materials, and the physical structure of the nest.

  Before answer:
  > The nest ecology of [the bird] involves specific site selection, minimal construction materials, and a simple physical structure. Nest sites are typically located in damp depressions on the ground, natural cavities, hollow logs, crevices among rocks, dense vegetation such as fern clumps, or on cliff ledges, usually within 30 meters of a river edge. The nest is constructed with only a little down added to ground debris, sometimes supplemented with soft grass and twigs, resulting in a basic structure that relies on the natural substrate. The same nest site may be reused for up to seven years, indicating a preference for stable and secure locations.

  After answer:
  > The nest ecology of Blue Duck involves specific site selection, minimal construction materials, and a simple physical structure. Nest sites are typically located in damp depressions on the ground, natural cavities, hollow logs, crevices among rocks, dense vegetation such as fern clumps, or on cliff ledges, usually within 30 meters of a river edge. The nest is constructed with only a little down added to ground debris, sometimes supplemented with soft grass and twigs, resulting in a basic structure that relies on the natural substrate. The same nest site may be reused for up to seven years, indicating a preference for stable and secure locations.

### Bird-Plan

- `bird_plan_0001` target=`Crypturellus boucardi`

  Before question:
  > The [Target Species] faces severe population decline primarily due to habitat loss from deforestation and conversion to agriculture, as indicated in its conservation status. In a critical region, 90% of the remaining suitable habitat is on privately owned land, making traditional protected area establishment impossible. As a conservation biologist, draft a specific conservation plan that addresses the core threat of habitat loss while working within this severe constraint of predominantly private land ownership.

  After question:
  > The Crypturellus boucardi faces severe population decline primarily due to habitat loss from deforestation and conversion to agriculture, as indicated in its conservation status. In a critical region, 90% of the remaining suitable habitat is on privately owned land, making traditional protected area establishment impossible. As a conservation biologist, draft a specific conservation plan that addresses the core threat of habitat loss while working within this severe constraint of predominantly private land ownership.

  Before answer:
  > Gold Standard Rubric for LLM-as-a-Judge Evaluation: - [Threat Priority]: The #1 deadliest threat to tackle first is habitat loss from deforestation and conversion to agriculture, as this directly reduces the forest floor habitat with dense understory that [Target Species] requires for foraging and nesting. - [Constraint Satisfaction]: The plan must utilize voluntary landowner agreements, conservation easements, or incentive-based programs (e.g., payments for ecosystem services) rather than government acquisition or protected area designation, to work within the 90% private land ownership constraint. - [Biological Specificity]: The plan must account for [Target Species]'s unique biological tr

  After answer:
  > Gold Standard Rubric for LLM-as-a-Judge Evaluation: - [Threat Priority]: The #1 deadliest threat to tackle first is habitat loss from deforestation and conversion to agriculture, as this directly reduces the forest floor habitat with dense understory that Crypturellus boucardi requires for foraging and nesting. - [Constraint Satisfaction]: The plan must utilize voluntary landowner agreements, conservation easements, or incentive-based programs (e.g., payments for ecosystem services) rather than government acquisition or protected area designation, to work within the 90% private land ownership constraint. - [Biological Specificity]: The plan must account for Crypturellus boucardi's unique bio

- `bird_plan_0002` target=`Penelope ortoni`

  Before question:
  > The [Target Species] is an endangered bird severely threatened by hunting, as it does not flee from human approach and is easily shot. Its habitat in the Chocó region includes steep slopes, making traditional ground-based predator control methods challenging. Given the constraint of inaccessible steep terrain, draft a specific conservation plan to address the hunting threat while accounting for the bird's unique biological traits.

  After question:
  > The Penelope ortoni is an endangered bird severely threatened by hunting, as it does not flee from human approach and is easily shot. Its habitat in the Chocó region includes steep slopes, making traditional ground-based predator control methods challenging. Given the constraint of inaccessible steep terrain, draft a specific conservation plan to address the hunting threat while accounting for the bird's unique biological traits.

  Before answer:
  > Gold Standard Rubric: - [Threat Priority]: The #1 deadliest threat to tackle first is hunting, as the species is easily shot due to its behavior of not fleeing from human approach, leading to direct mortality. - [Constraint Satisfaction]: To address inaccessible steep terrain, the plan must avoid ground-based patrols or physical barriers that require extensive on-foot access. Instead, implement aerial surveillance (e.g., drones) or community-based monitoring from accessible vantage points to detect and deter hunters. - [Biological Specificity]: The plan must account for the [Target Species]'s reliance on tall primary forest and its foraging behavior in the upper strata for fruits, particular

  After answer:
  > Gold Standard Rubric: - [Threat Priority]: The #1 deadliest threat to tackle first is hunting, as the species is easily shot due to its behavior of not fleeing from human approach, leading to direct mortality. - [Constraint Satisfaction]: To address inaccessible steep terrain, the plan must avoid ground-based patrols or physical barriers that require extensive on-foot access. Instead, implement aerial surveillance (e.g., drones) or community-based monitoring from accessible vantage points to detect and deter hunters. - [Biological Specificity]: The plan must account for the Penelope ortoni's reliance on tall primary forest and its foraging behavior in the upper strata for fruits, particularl

- `bird_plan_0003` target=`Columba torringtoniae`

  Before question:
  > The [Target Species] in Sri Lanka's hill country is declining primarily due to habitat loss and degradation, with native forests being replaced by unsuitable monocultures. As a conservation planner, you must design an intervention plan under the severe constraint that 90% of the land in its range is privately owned, limiting direct habitat protection. Draft a specific conservation plan that addresses this threat while working within this land ownership constraint.

  After question:
  > The Columba torringtoniae in Sri Lanka's hill country is declining primarily due to habitat loss and degradation, with native forests being replaced by unsuitable monocultures. As a conservation planner, you must design an intervention plan under the severe constraint that 90% of the land in its range is privately owned, limiting direct habitat protection. Draft a specific conservation plan that addresses this threat while working within this land ownership constraint.

  Before answer:
  > Gold Standard Rubric: - [Threat Priority]: The #1 deadliest threat to tackle first is habitat loss and degradation, specifically the replacement of native evergreen and moist deciduous forests by monocultures unsuitable for the species, as this is identified as the chief cause of decline. - [Constraint Satisfaction]: To satisfy the constraint that 90% of land is privately owned, the plan must avoid relying on direct habitat acquisition or government-led protection. Instead, it should focus on incentivizing private landowners through conservation easements, agroforestry programs that incorporate fruiting trees, or community-based management agreements to preserve or restore suitable habitat o

  After answer:
  > Gold Standard Rubric: - [Threat Priority]: The #1 deadliest threat to tackle first is habitat loss and degradation, specifically the replacement of native evergreen and moist deciduous forests by monocultures unsuitable for the species, as this is identified as the chief cause of decline. - [Constraint Satisfaction]: To satisfy the constraint that 90% of land is privately owned, the plan must avoid relying on direct habitat acquisition or government-led protection. Instead, it should focus on incentivizing private landowners through conservation easements, agroforestry programs that incorporate fruiting trees, or community-based management agreements to preserve or restore suitable habitat o

### Bird-Reason

- `bird_reason_0001` target=`Apteryx australis`

  Before question:
  > Hypothetically, if a severe drought were to drastically reduce the soil moisture and leaf litter in the habitats of [This Bird], predict the ecological consequence for its population viability based on its specific foraging traits and dietary needs.

  After question:
  > Hypothetically, if a severe drought were to drastically reduce the soil moisture and leaf litter in the habitats of Apteryx australis, predict the ecological consequence for its population viability based on its specific foraging traits and dietary needs.

  Before answer:
  > The ecological consequence would likely be a significant decline in population viability due to reduced prey availability and foraging efficiency. [This Bird] is a nocturnal, flightless bird that detects prey mainly by smell and forages on invertebrates from soil and leaf litter, including insects, earthworms, spiders, snails, amphipods, millipedes, and centipedes. A severe drought reducing soil moisture and leaf litter would desiccate and diminish these invertebrate populations, directly impacting [This Bird]'s primary food source. This could lead to malnutrition, reduced reproductive success (e.g., lower clutch survival or fewer replacement clutches), and increased mortality, particularly 

  After answer:
  > The ecological consequence would likely be a significant decline in population viability due to reduced prey availability and foraging efficiency. Apteryx australis is a nocturnal, flightless bird that detects prey mainly by smell and forages on invertebrates from soil and leaf litter, including insects, earthworms, spiders, snails, amphipods, millipedes, and centipedes. A severe drought reducing soil moisture and leaf litter would desiccate and diminish these invertebrate populations, directly impacting Apteryx australis's primary food source. This could lead to malnutrition, reduced reproductive success (e.g., lower clutch survival or fewer replacement clutches), and increased mortality, p

- `bird_reason_0002` target=`Asarcornis scutulata`

  Before question:
  > The text notes that [This Bird] exhibits an unusual pattern of seasonal habitat use, shifting from more open wetlands during wet seasons to secluded forest ditches in dry seasons, and is sometimes hardly seen at all in late dry seasons. What is the most likely biological cause for this specific distributional constraint and behavioral anomaly, given its physiological traits and ecological requirements?

  After question:
  > The text notes that Asarcornis scutulata exhibits an unusual pattern of seasonal habitat use, shifting from more open wetlands during wet seasons to secluded forest ditches in dry seasons, and is sometimes hardly seen at all in late dry seasons. What is the most likely biological cause for this specific distributional constraint and behavioral anomaly, given its physiological traits and ecological requirements?

  Before answer:
  > The most likely biological cause is [This Bird]'s dependence on secluded, permanent water sources for survival during dry periods, driven by its specific physiological and behavioral adaptations as a tropical forest duck. This species inhabits undisturbed, secluded pools and marshes in dense freshwater and peat swampy forests, and feeds by dabbling and head-dipping in shallow water on a diet including aquatic plants, molluscs, and small vertebrates. During wet seasons, abundant water allows use of more open wetlands, but as water levels recede in dry seasons, the bird must concentrate in the few remaining forest ditches that retain water. In late dry seasons, when even these become scarce, i

  After answer:
  > The most likely biological cause is Asarcornis scutulata's dependence on secluded, permanent water sources for survival during dry periods, driven by its specific physiological and behavioral adaptations as a tropical forest duck. This species inhabits undisturbed, secluded pools and marshes in dense freshwater and peat swampy forests, and feeds by dabbling and head-dipping in shallow water on a diet including aquatic plants, molluscs, and small vertebrates. During wet seasons, abundant water allows use of more open wetlands, but as water levels recede in dry seasons, the bird must concentrate in the few remaining forest ditches that retain water. In late dry seasons, when even these become 

- `bird_reason_0003` target=`Anas bernieri`

  Before question:
  > A claim states that [This Bird] primarily nests in open, treeless areas near deep freshwater lakes during the breeding season, which is a strategy to avoid predators and facilitate easy access to aquatic insects. Identify the physiological and ecological errors in this claim and correct them based on the provided text.

  After question:
  > A claim states that Anas bernieri primarily nests in open, treeless areas near deep freshwater lakes during the breeding season, which is a strategy to avoid predators and facilitate easy access to aquatic insects. Identify the physiological and ecological errors in this claim and correct them based on the provided text.

  Before answer:
  > The claim contains multiple errors. First, [This Bird] does not nest in open, treeless areas; it nests in holes in black mangrove (Avicennia marina) trees 1–3 m above the water line, always in larger trees, as stated in the text. This arboreal nesting strategy provides protection from ground predators and flooding, not open areas. Second, the breeding habitat is not near deep freshwater lakes but in seasonally flooded, non-tidal areas dominated by Avicennia marina mangrove on the landward side of littoral forest, which are shallow and saline or brackish. Third, the breeding season occurs during the W coast wet season (Dec–Mar), not in open areas, and nesting in trees aligns with monogamous p

  After answer:
  > The claim contains multiple errors. First, Anas bernieri does not nest in open, treeless areas; it nests in holes in black mangrove (Avicennia marina) trees 1–3 m above the water line, always in larger trees, as stated in the text. This arboreal nesting strategy provides protection from ground predators and flooding, not open areas. Second, the breeding habitat is not near deep freshwater lakes but in seasonally flooded, non-tidal areas dominated by Avicennia marina mangrove on the landward side of littoral forest, which are shallow and saline or brackish. Third, the breeding season occurs during the W coast wet season (Dec–Mar), not in open areas, and nesting in trees aligns with monogamous

### Bird-Taxonomy

- `bird_taxonomy_0001` target=`Asarcornis scutulata`

  Before question:
  > True or False: [the bird] is currently classified in the genus Cairina.

  After question:
  > True or False: Asarcornis scutulata is currently classified in the genus Cairina.

- `bird_taxonomy_0002` target=`Rhodonessa caryophyllacea`

  Before question:
  > Does [the bird] have any recognized subspecies?

  After question:
  > Does Rhodonessa caryophyllacea have any recognized subspecies?

- `bird_taxonomy_0003` target=`Tinamus guttatus`

  Before question:
  > Does [the bird] have any recognized subspecies?

  After question:
  > Does Tinamus guttatus have any recognized subspecies?

### QA-MC

- `qa_mc_0001` target=`Pink-headed Duck`

  Before question:
  > Based on historical records, which of the following modern-day countries or regions were part of [the bird]'s known distribution?

  After question:
  > Based on historical records, which of the following modern-day countries or regions were part of Pink-headed Duck's known distribution?

- `qa_mc_0002` target=`Choco Tinamou`

  Before question:
  > Based on the provided text, which of the following statements accurately describe the distribution or known localities of [the bird]?

  After question:
  > Based on the provided text, which of the following statements accurately describe the distribution or known localities of Choco Tinamou?

- `qa_mc_0003` target=`Swan Goose`

  Before question:
  > Based on the provided monograph, which of the following are documented threats to [the bird] populations? Select ALL correct options.

  After question:
  > Based on the provided monograph, which of the following are documented threats to Swan Goose populations? Select ALL correct options.

### QA-SA

- `qa_sa_0001` target=`Aythya ferina`

  Before question:
  > What is the maximum recorded elevation in meters for [the bird] in Ethiopia during winter?

  After question:
  > What is the maximum recorded elevation in meters for Aythya ferina in Ethiopia during winter?

- `qa_sa_0002` target=`Rhodonessa caryophyllacea`

  Before question:
  > How many valid subspecies are recognized for [the bird]?

  After question:
  > How many valid subspecies are recognized for Rhodonessa caryophyllacea?

- `qa_sa_0003` target=`Hymenolaimus malacorhynchos`

  Before question:
  > How many subspecies of [the bird] are recognized?

  After question:
  > How many subspecies of Hymenolaimus malacorhynchos are recognized?

### QA-SC

- `qa_sc_0001` target=`Yellow-legged Tinamou`

  Before question:
  > According to the text, what is the primary reason for the decline in [the bird]'s population throughout eastern Brazil?

  After question:
  > According to the text, what is the primary reason for the decline in Yellow-legged Tinamou's population throughout eastern Brazil?

- `qa_sc_0002` target=`White-headed Steamer-Duck`

  Before question:
  > According to the text, what is the primary geographic distribution of [the bird]?

  After question:
  > According to the text, what is the primary geographic distribution of White-headed Steamer-Duck?

- `qa_sc_0003` target=`Philippine Duck`

  Before question:
  > Based on the provided text, where is the primary distribution range of [the bird]?

  After question:
  > Based on the provided text, where is the primary distribution range of Philippine Duck?


## Warning Details

No warnings.
