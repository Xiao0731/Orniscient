# Demo Fact Quality Audit Sample

This is a read-only manual audit sample generated from `demo_data/sample_100_taxa`. No LLM was called, and no demo data files were modified.

- Random seed: `20260529`
- Sample size: `80` facts (`10` per fact domain)
- Source directory: `demo_data/sample_100_taxa`

Manual checks for each row:

1. Does the predicate match the evidence?
2. Is `object_text` supported by the evidence quote?
3. Is the evidence from the same taxon as the fact subject?
4. Is the chunk preview relevant?
5. Are there obvious duplicates or fact/evidence mismatches?

Automated hints are non-judgmental string/metadata checks only; final quality judgment should be manual.

## ConservationAndResearch

### ConservationAndResearch-01

- fact_id: `fact_13216fbe23f2924605c26b36e001abd7`
- subject: Swainson's Hawk / `Buteo swainsoni`
- domain: `ConservationAndResearch`
- predicate: `THREATENED_BY`
- object_text: urban development
- evidence_id: `evidence_d0b84d76b81323f6`
- source_chunk_id: `Buteo swainsoni::138`
- source_chapter: `Conservation`
- automated_same_taxon_hint: `YES` (subject scientific=`Buteo swainsoni`, evidence chunk taxon=`Buteo swainsoni`, chunk taxon=`Buteo swainsoni`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `THREATENED_BY::urban development::Buteo swainsoni::138`

evidence_quote:

> Proposed conservation measures, including habitat conservation plans, usually focus on retention of some portion of existing foraging and nesting habitats while allowing other areas to be lost to urban development.

chunk_preview:

> Proposed conservation measures, including habitat conservation plans, usually focus on retention of some portion of existing foraging and nesting habitats while allowing other areas to be lost to urban development. As economic conversion of agricultural areas to commercial and residential real estate continues, impacts on Swainson's Hawk populations should be monitored to determine population trends. Disturbance of breeding pairs and destruction of nest trees need to be prevented (Sharp 1986b Sharp, B. (1986b). Management guidelines for the Swainson's Hawk. Portland, OR: U.S. Fish Wildl. Serv.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### ConservationAndResearch-02

- fact_id: `fact_f407206c4e4a4b1089a793f5cb97ea1e`
- subject: Least Auklet / `Aethia pusilla`
- domain: `ConservationAndResearch`
- predicate: `INTERACTS_WITH_HUMANS`
- object_text: Non-invasive research
- evidence_id: `evidence_91d2fb5b00a78bde`
- source_chunk_id: `Aethia pusilla::118`
- source_chapter: `Conservation`
- automated_same_taxon_hint: `YES` (subject scientific=`Aethia pusilla`, evidence chunk taxon=`Aethia pusilla`, chunk taxon=`Aethia pusilla`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `INTERACTS_WITH_HUMANS::non-invasive research::Aethia pusilla::118`

evidence_quote:

> although nests can be checked visually with a small light without apparent effects on hatching success

chunk_preview:

> Human disturbance likely negligible because of species' remote breeding and wintering areas. Nests likely to be abandoned if adults or eggs handled at nest site by researchers during incubation period, although nests can be checked visually with a small light without apparent effects on hatching success (Hipfner and Byrd 1993 Hipfner, J. M. and G. V. Byrd. . Breeding biology of the Parakeet Auklet compared to other crevice nesting species at Buldir Island, Alaska. Colonial Waterbirds 16:128-138.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### ConservationAndResearch-03

- fact_id: `fact_6e41c951ff850a75510b2932516efc6e`
- subject: California Condor / `Gymnogyps californianus`
- domain: `ConservationAndResearch`
- predicate: `HAS_CONSERVATION_ACTION`
- object_text: multiple-clutching of wild pairs
- evidence_id: `evidence_ea87a44c2ea39cf5`
- source_chunk_id: `Gymnogyps californianus::118`
- source_chapter: `Conservation`
- automated_same_taxon_hint: `YES` (subject scientific=`Gymnogyps californianus`, evidence chunk taxon=`Gymnogyps californianus`, chunk taxon=`Gymnogyps californianus`)
- automated_object_overlap_hint: `3` shared object/evidence tokens
- duplicate_scan_key: `HAS_CONSERVATION_ACTION::multiple-clutching of wild pairs::Gymnogyps californianus::118`

evidence_quote:

> multiple-clutching of wild pairs was rapidly allowing establishment of a captive population

chunk_preview:

> Early Release Plan: Releases of captive California Condors to the wild were first proposed by the Condor Recovery Team in 1983-1984, when there was still an extant wild population of 15-19 birds and when clear evidence for excessive mortality in the wild population was still not in hand, but when multiple-clutching of wild pairs was rapidly allowing establishment of a captive population. In essence, the Recovery Team proposed splitting the benefits of continued multiple-clutching of wild pairs between continued establishment of a captive flock and attempts to sustain the existing wild population with deliberate releases of some of the progeny produced. Specifically, once pairs were represent

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### ConservationAndResearch-04

- fact_id: `fact_e754d31f8e314abcdb3eb18917afeb2b`
- subject: Aplomado Falcon / `Falco femoralis`
- domain: `ConservationAndResearch`
- predicate: `INTERACTS_WITH_HUMANS`
- object_text: 
- evidence_id: `evidence_13660dcaf528dd96`
- source_chunk_id: `Falco femoralis::127`
- source_chapter: `Conservation`
- automated_same_taxon_hint: `YES` (subject scientific=`Falco femoralis`, evidence chunk taxon=`Falco femoralis`, chunk taxon=`Falco femoralis`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `INTERACTS_WITH_HUMANS::::Falco femoralis::127`

evidence_quote:

> Because of their greater height, nests in palms, tropical live oaks, and ceibas, relatively secure from destruction by fire.

chunk_preview:

> One nestling possibly killed by fire in eastern Mexico (J. Langford, personal communication). At least two other nests nearly destroyed by fire in eastern Mexico (DKH). In eastern Mexico, Aplomados nest during the dry season when grass fires are frequent. Because of their greater height, nests in palms, tropical live oaks, and ceibas, relatively secure from destruction by fire. In areas where typical nest sites are close to the ground, fire may be a significant cause of egg and nestling loss, however, periodic fire in all typical habitat types, but especially tropical lowland sites, essential to maintenance of appropriate habitat physiognomy.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### ConservationAndResearch-05

- fact_id: `fact_8468999cffc55a25c6bde07a31a54c09`
- subject: Eurasian Skylark / `Alauda arvensis`
- domain: `ConservationAndResearch`
- predicate: `HAS_POPULATION_TREND`
- object_text: Declining
- evidence_id: `evidence_b66c5256da95fba6`
- source_chunk_id: `Alauda arvensis::135`
- source_chapter: `Demography`
- automated_same_taxon_hint: `YES` (subject scientific=`Alauda arvensis`, evidence chunk taxon=`Alauda arvensis`, chunk taxon=`Alauda arvensis`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_POPULATION_TREND::declining::Alauda arvensis::135`

evidence_quote:

> these exceed 50% in many countries, e.g. populations on lowland farmland in Britain declined by more than 54% from 1969 to 1991 ... numbers in Germany reduced by 60% ... and in Netherlands by at least 75%

chunk_preview:

> Although still very numerous, is currently listed by BirdLife International as a "Species of Conservation Concern in Europe", owing to massive declines, particularly in W Europe, since 1960s (mainly since mid-1980s); these exceed 50% in many countries, e.g. populations on lowland farmland in Britain declined by more than 54% from 1969 to 1991 (representing loss of c. 1,500,000 breeding pairs), and numbers in Germany reduced by 60% (with some local extinctions) and in Netherlands by at least 75%; declines largely a result of intensification of agriculture, and recent research indicates that changes in management of cereal-growing and grassland (leading to reduced nesting and foraging opportun

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### ConservationAndResearch-06

- fact_id: `fact_f49ca7f1401e6f9655c10238f92926f4`
- subject: Cape Weaver / `Ploceus capensis`
- domain: `ConservationAndResearch`
- predicate: `INTERACTS_WITH_HUMANS`
- object_text: public interest in birdwatching
- evidence_id: `evidence_4eda108be8380df9`
- source_chunk_id: `Ploceus capensis::136`
- source_chapter: `HumanRelations`
- automated_same_taxon_hint: `YES` (subject scientific=`Ploceus capensis`, evidence chunk taxon=`Ploceus capensis`, chunk taxon=`Ploceus capensis`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `INTERACTS_WITH_HUMANS::public interest in birdwatching::Ploceus capensis::136`

evidence_quote:

> People are fascinated by weavers, and the Cape Weaver sometimes nests in parks where its nest building and frantic displays are watched with interest.

chunk_preview:

> People are fascinated by weavers, and the ​Cape Weaver​ sometimes nests in parks where its nest building and frantic displays are watched with interest. Gardeners often dislike weavers, including the Cape Weaver, because they strip leaves from the trees they nest in. Some farmers dislike weavers as they are minor pests of fruit trees and grain crops. Economic and Utilitarian Significance Use by Humans Information needed. Harm Inflicted by Focal Species The Cape Weaver eats seeds from a wide variety of plants, including crops like barley grains (Hordeum vulgare) and maize grains (Zea mays) (6 Elliott, C. C. H. . The biology of the Cape Weaver Ploceus capensis with special reference to its pol

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### ConservationAndResearch-07

- fact_id: `fact_dc539a4d2d474f07a221fdbd55d5209f`
- subject: Lapland Longspur / `Calcarius lapponicus`
- domain: `ConservationAndResearch`
- predicate: `THREATENED_BY`
- object_text: lighted structures
- evidence_id: `evidence_81f92499929a1e76`
- source_chunk_id: `Calcarius lapponicus::127`
- source_chapter: `Conservation`
- automated_same_taxon_hint: `YES` (subject scientific=`Calcarius lapponicus`, evidence chunk taxon=`Calcarius lapponicus`, chunk taxon=`Calcarius lapponicus`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `THREATENED_BY::lighted structures::Calcarius lapponicus::127`

evidence_quote:

> Action needed to reduce kills at lighted structures

chunk_preview:

> ). There is clear need for winter monitoring program directed at this and other species (e.g., Snow Bunting, Smith's Longspur, and Harris's Sparrow [Zonotrichia querula]) that winter in s. Canada and the U.S. and breed mainly north of regions covered by the Breeding Bird Survey (134 Dunn, E. H. . Setting priorities for conservation, research and monitoring of Canada's landbirds. Ottawa, ON: Can. Wildl. Serv. ). Since comprehensive population monitoring on breeding range is impractical, useful supplement would be long-term monitoring at several selected sites across the breeding range (e.g., 132 Pattie, D. L. . A 16-year record of summer birds on Truelove Lowland, Devon Island, Northwest Terr

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### ConservationAndResearch-08

- fact_id: `fact_6228262fc8defa8fc563395c59178c8d`
- subject: Bluethroat / `Luscinia svecica`
- domain: `ConservationAndResearch`
- predicate: `HAS_POPULATION_TREND`
- object_text: Netherlands (1930-1970)
- evidence_id: `evidence_7ea53ec7998a6517`
- source_chunk_id: `Luscinia svecica::137`
- source_chapter: `Demography`
- automated_same_taxon_hint: `YES` (subject scientific=`Luscinia svecica`, evidence chunk taxon=`Luscinia svecica`, chunk taxon=`Luscinia svecica`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_POPULATION_TREND::netherlands (1930-1970)::Luscinia svecica::137`

evidence_quote:

> major decline in Netherlands in 1930-1970 seemingly explicable by natural succession, reed-cutting and farming practices

chunk_preview:

> Fluctuations in populations in temperate Europe in 20th century essentially unexplained: major decline in Netherlands in 1930-1970 seemingly explicable by natural succession, reed-cutting and farming practices, but recovery since 1970 (800 pairs) to 1990 (5500-7500 pairs) took place without reversal of these circumstances. Breeding-range expansions now also in France, Belgium, Germany, Austria, Czech Republic and Slovakia, suggesting that conditions outside Europe may be responsible. In Germany, however, growth in numbers in Coburg (Bavaria) due to colonization of vegetation around washponds in gravel plants and of reeds and scrub in farmland drainage ditches; population will collapse unless

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### ConservationAndResearch-09

- fact_id: `fact_de603529b75f174fee111c7fc0b062e0`
- subject: Little Blue Heron / `Egretta caerulea`
- domain: `ConservationAndResearch`
- predicate: `HAS_CONSERVATION_ACTION`
- object_text: Migratory Bird Treaty Act protection
- evidence_id: `evidence_d77594e586064a31`
- source_chunk_id: `Egretta caerulea::131`
- source_chapter: `Conservation`
- automated_same_taxon_hint: `YES` (subject scientific=`Egretta caerulea`, evidence chunk taxon=`Egretta caerulea`, chunk taxon=`Egretta caerulea`)
- automated_object_overlap_hint: `5` shared object/evidence tokens
- duplicate_scan_key: `HAS_CONSERVATION_ACTION::migratory bird treaty act protection::Egretta caerulea::131`

evidence_quote:

> The Reddish Egret receives no specific protection in the United States other than legal protection afforded by the Migratory Bird Treaty Act

chunk_preview:

> Measures Proposed and Taken The Reddish Egret receives no specific protection in the United States other than legal protection afforded by the Migratory Bird Treaty Act, the Migratory Bird and Game Management Treaty between Mexico and the United States , and state-threatened status in Texas and Florida and species of greatest conservation need in Louisiana. The Reddish Egret Working Group was formed in 2005 and published the first rangewide conservation action plan (2 Wilson, T. E., J. Wheeler, M. C. Green, and E. Palacios. . Reddish Egret Conservation Action Plan. Unpublished report, Reddish Egret Conservation Planning Workshop, October 2012. Corpus Christi, TX, USA.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### ConservationAndResearch-10

- fact_id: `fact_99888f76a492ee8a636e5450a53d7678`
- subject: Swainson's Hawk / `Buteo swainsoni`
- domain: `ConservationAndResearch`
- predicate: `HAS_POPULATION_TREND`
- object_text: declining
- evidence_id: `evidence_9afe70aaf3103e9b`
- source_chunk_id: `Buteo swainsoni::132`
- source_chapter: `Conservation`
- automated_same_taxon_hint: `YES` (subject scientific=`Buteo swainsoni`, evidence chunk taxon=`Buteo swainsoni`, chunk taxon=`Buteo swainsoni`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_POPULATION_TREND::declining::Buteo swainsoni::132`

evidence_quote:

> evidence from egg collections suggests that this population has been reduced by as much as 90% from its estimated historical levels (Bloom 1980)

chunk_preview:

> ), e. Oregon (Gabrielson and Jewett 1940 Gabrielson, I. N., and S. G. Jewett . The Birds of Oregon. Oregon State College Press, Corvallis, OR, USA. ), and California (Remsen 1978a Remsen, J. V., Jr. . Bird species of special concern in California. In California Deptartment of Fish and Game, Wildlife Management Branch. , Bloom 1980 Bloom, P. H. . The status of the Swainson's Hawk in California, 1979. Sacramento, CA: Wildl. Mgmt. Branch, Calif. Dep. Fish Game. ). Now reduced in numbers or distribution throughout its range and considered to be declining in Utah, Nevada, and Oregon; listed as Species of Special Concern in Utah, Nevada, Oregon, and Washington, and as Threatened in California (Lit

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

## DistributionAndMovement

### DistributionAndMovement-01

- fact_id: `fact_794000a9b2ede17d42e1e14526567711`
- subject: Laysan Albatross / `Phoebastria immutabilis`
- domain: `DistributionAndMovement`
- predicate: `BREEDS_IN`
- object_text: Hawaiian Islands
- evidence_id: `evidence_9d57dbaf0e8941da`
- source_chunk_id: `Phoebastria immutabilis::29`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Phoebastria immutabilis`, evidence chunk taxon=`Phoebastria immutabilis`, chunk taxon=`Phoebastria immutabilis`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `BREEDS_IN::hawaiian islands::Phoebastria immutabilis::29`

evidence_quote:

> birds leave the Hawaiian Is. area

chunk_preview:

> See Migration and Distribution: marine range. During the non-breeding season, birds leave the Hawaiian Is. area from approximately July to October and concentrate north of 40ºN near the Aleutians Is. and in the Bering Sea, and as far east as 156ºW (Sanger 1974b Sanger, G. A. (1974b). Laysan Albatross (Diomedea immutabilis). Smithson. Contrib. Zool. 158:129-153.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### DistributionAndMovement-02

- fact_id: `fact_9b5f9f59959e3127ff382975ed76a885`
- subject: Orange-crowned Warbler / `Leiothlypis celata`
- domain: `DistributionAndMovement`
- predicate: `BREEDS_IN`
- object_text: North America
- evidence_id: `evidence_4d6d926af6fec929`
- source_chunk_id: `Leiothlypis celata::1`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Leiothlypis celata`, evidence chunk taxon=`Leiothlypis celata`, chunk taxon=`Leiothlypis celata`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `BREEDS_IN::north america::Leiothlypis celata::1`

evidence_quote:

> breeds widely over much of western and northern North America, and east across Canada

chunk_preview:

> The Orange-crowned Warbler, Leiothlypis celata, breeds widely over much of western and northern North America, and east across Canada. Authorities recognize four subspecies, which differ to varying extents in their plumage, molt patterns, breeding distributions, and migratory routes, among other things. This species prefers habitats with shrubs and low vegetation, often in patchy oak or aspen forest, or in riparian areas or chaparral. Wooded habitat provides suitable conditions for the warbler's nest, placed on or near the ground. Like other members of its genus, the Orange-crown gleans insects from leaves, blossoms, and the tips of boughs, but it also eats some berries and fruit and is attr

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### DistributionAndMovement-03

- fact_id: `fact_019a382760f075fe8f220462e30052ce`
- subject: Surfbird / `Calidris virgata`
- domain: `DistributionAndMovement`
- predicate: `HAS_DISTRIBUTION_NOTE`
- object_text: 
- evidence_id: `evidence_7011af81679944bf`
- source_chunk_id: `Calidris virgata::2`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Calidris virgata`, evidence chunk taxon=`Calidris virgata`, chunk taxon=`Calidris virgata`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_DISTRIBUTION_NOTE::::Calidris virgata::2`

evidence_quote:

> Distribution within area described above determined by presence of suitable rocky habitat.

chunk_preview:

> 23-26 cm; wingspan 58-60 cm (1 Roberts, T. J. . The Birds of Pakistan, Volume 1: Non-Passeriformes. Oxford University Press, Karachi, Pakistan.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### DistributionAndMovement-04

- fact_id: `fact_1c2567bb4b1fd4dd6069407be828fa99`
- subject: American White Pelican / `Pelecanus erythrorhynchos`
- domain: `DistributionAndMovement`
- predicate: `OCCURS_IN`
- object_text: British Columbia
- evidence_id: `evidence_6db8ffb2604170d6`
- source_chunk_id: `Pelecanus erythrorhynchos::33`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Pelecanus erythrorhynchos`, evidence chunk taxon=`Pelecanus erythrorhynchos`, chunk taxon=`Pelecanus erythrorhynchos`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `OCCURS_IN::british columbia::Pelecanus erythrorhynchos::33`

evidence_quote:

> ranging from south-central British Columbia

chunk_preview:

> The American White Pelican ranges from south-central British Columbia, northern Alberta, northeastern Saskatchewan, central Manitoba, Ontario, eastern Wisconsin, northern Ohio, west through Minnesota, the Dakotas, northern Montana, Wyoming, northern Colorado, Idaho, and northern Utah to western Nevada, northern California, Oregon, and southern Washington (5 Sidle, J. G., W. H. Koonz, and K. Roney . Status of the American White Pelican: an update. American Birds 39:859-864.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### DistributionAndMovement-05

- fact_id: `fact_a026375434dd72fc6ee7e567fb2f42e9`
- subject: Blue-gray Gnatcatcher / `Polioptila caerulea`
- domain: `DistributionAndMovement`
- predicate: `WINTERS_IN`
- object_text: Cuba
- evidence_id: `evidence_444be15a3278bb48`
- source_chunk_id: `Polioptila caerulea::31`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Polioptila caerulea`, evidence chunk taxon=`Polioptila caerulea`, chunk taxon=`Polioptila caerulea`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `WINTERS_IN::cuba::Polioptila caerulea::31`

evidence_quote:

> In Cuba, a common winter resident, virtually island-wide - in varied lowland and mid-elevation habitats from forests to gardens - as well as on the larger cays

chunk_preview:

> Figure 1. Extensive winter range from the Coastal Plain of the se. US south through Cuba and Mexico to n. Central America (Honduras). Christmas Bird Count (CBC) and Ebird data show this species widely distributed in the s. US in early winter, with centers of concentration in s. Florida, the Gulf Coast from Mississippi to the Rio Grande Valley of Texas, and s. California ( ). Very rare north to Delaware (Hess et al. 2000) and even coastal Massachusetts (Viet and Petersen 1993) in December, with increasing (but still low) winter numbers in the Carolinas (Potter et al. 2006). Given the influx of spring/fall migrants along the Gulf Coast (see Migration), it appears that most individuals winter s

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### DistributionAndMovement-06

- fact_id: `fact_ea1fc7d2ec61234bfa4401915bece6bf`
- subject: Parasitic Jaeger / `Stercorarius parasiticus`
- domain: `DistributionAndMovement`
- predicate: `BREEDS_IN`
- object_text: 
- evidence_id: `evidence_20f139b0c58a2e50`
- source_chunk_id: `Stercorarius parasiticus::32`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Stercorarius parasiticus`, evidence chunk taxon=`Stercorarius parasiticus`, chunk taxon=`Stercorarius parasiticus`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `BREEDS_IN::::Stercorarius parasiticus::32`

evidence_quote:

> In Alaska, often present during summer from Yukon delta northward along coast and on St. Lawrence I. Breeds along arctic coast and in Yukon delta

chunk_preview:

> Erratic breeding, coinciding with peaks in lemming populations, makes it difficult to determine breeding status in many places; reports often provide information for only one year's observations, which more often than not miss a peak for lemmings. Birds also wander widely in the Arctic during summer, so presence in an area does not necessarily indicate breeding. In Alaska, often present during summer from Yukon delta northward along coast and on St. Lawrence I. Breeds along arctic coast and in Yukon delta (Brandt 1942 Brandt, H. . Alaska Bird Trails: An Expedition by Dog Sled to the Delta of the Yukon River at Hooper Bay. The Bird Research Foundation, Cleveland, OH, USA.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### DistributionAndMovement-07

- fact_id: `fact_8fa39fd6657533efb3472c57b07e53dc`
- subject: California Condor / `Gymnogyps californianus`
- domain: `DistributionAndMovement`
- predicate: `HAS_DISTRIBUTION_NOTE`
- object_text: 
- evidence_id: `evidence_4c4e76de239f9509`
- source_chunk_id: `Gymnogyps californianus::2`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Gymnogyps californianus`, evidence chunk taxon=`Gymnogyps californianus`, chunk taxon=`Gymnogyps californianus`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_DISTRIBUTION_NOTE::::Gymnogyps californianus::2`

evidence_quote:

> Pleistocene fossils indicate additional occurrences in ne. Mexico (Nuevo León) and across Southwestern states from California to Texas. Pleistocene fossils were also found in several Florida locations and in a single location in upstate Ne…

chunk_preview:

> , Robinson 1940 Robinson, C. S. . Notes on the California Condor, collected on Los Padres National Forest, California. Santa Barbara, CA: U.S. Forest Serv. ), Koford (Koford 1953 Koford, C. B. . The California Condor. Natl. Audubon Soc. Res. Rep. 4:1-154. ), Miller et al. (Miller et al. 1965 Miller, A. H., I. McMillan and E. McMillan. . The current status and welfare of the California Condor. Natl. Audubon Soc. Res. Rep. 6:1-61. ), Sibley (Sibley 1968 Sibley, F. C. . The life history, ecology and management of the California Condor (Gymnogyps californianus). Patuxent, MD: U.S. Fish Wildl. Serv. , Sibley 1969 Sibley, F. C. . Effects of the Sespe Creek Project on the California Condor. Laurel,

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### DistributionAndMovement-08

- fact_id: `fact_f013aeb1be1e10232ffd8d0c7249c190`
- subject: Redpoll / `Acanthis flammea`
- domain: `DistributionAndMovement`
- predicate: `OCCURS_IN`
- object_text: North America
- evidence_id: `evidence_a1b0b038965c7e8f`
- source_chunk_id: `Acanthis flammea::3`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Acanthis flammea`, evidence chunk taxon=`Acanthis flammea`, chunk taxon=`Acanthis flammea`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `OCCURS_IN::north america::Acanthis flammea::3`

evidence_quote:

> In North America, their distribution shows significant overlap with human populations only in winter, and then only in alternating irruption years.

chunk_preview:

> During the summer, Common Redpolls are found in boreal and taiga regions of both the Old and New World Arctic, where they are often among the most common breeding passerines. In North America, their distribution shows significant overlap with human populations only in winter, and then only in alternating irruption years. The irruption cycle displayed by the Common Redpoll is driven by widespread failure in seed-crop production among high-latitude tree species-especially spruce (Picea spp.) and birch (Betula spp.)-which forces these birds to winter farther south (6 Bock, C. E., and L. W. Lepthien (1976f). Synchronous eruptions of boreal seed-eating birds. American Naturalist 110:559-571. Limi

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### DistributionAndMovement-09

- fact_id: `fact_3bbc4b5e75b5aeb32f3fff54cc93f092`
- subject: Marsh Warbler / `Acrocephalus palustris`
- domain: `DistributionAndMovement`
- predicate: `MIGRATES_VIA`
- object_text: northern Somalia
- evidence_id: `evidence_b036e7026bbd739b`
- source_chunk_id: `Acrocephalus palustris::33`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Acrocephalus palustris`, evidence chunk taxon=`Acrocephalus palustris`, chunk taxon=`Acrocephalus palustris`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `MIGRATES_VIA::northern somalia::Acrocephalus palustris::33`

evidence_quote:

> Return migration is on a narrow front, almost entirely through eastern Kenya (peak in mid-April), and then across northern Somalia (late April to mid-May).

chunk_preview:

> The Marsh Warbler is migratory, with its nonbreeding grounds in southeastern Africa. Southward migration is in two stages. Populations from northwestern and central Europe head initially southeast through the Middle East and then south across Arabia. In Africa, the main migration route is along the Red Sea coast of Sudan and northern Eritrea from mid-August to late September. Birds remain for two or three months in Ethiopia, where most apparently undergo a partial molt. After this stopover, migration follows a narrow route across eastern Kenya, east of the highlands. Migration follows the rains to take advantage of flushes of plant growth and arthropod abundance; migration continues to Zambi

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### DistributionAndMovement-10

- fact_id: `fact_59fa5bd43d4765a06e3b3c573bf972dd`
- subject: Gray Vireo / `Vireo vicinior`
- domain: `DistributionAndMovement`
- predicate: `WINTERS_IN`
- object_text: western Texas
- evidence_id: `evidence_d29ccfcbaf5b4119`
- source_chunk_id: `Vireo vicinior::2`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Vireo vicinior`, evidence chunk taxon=`Vireo vicinior`, chunk taxon=`Vireo vicinior`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `WINTERS_IN::western texas::Vireo vicinior::2`

evidence_quote:

> Birds wintering in western Texas feed predominantly on insects and actively defend winter territories

chunk_preview:

> ). Coues (Coues 1878d Coues, E. . The Birds of the Colorado Valley: A Repository of Scientific and Popular Information Concerning North American Ornithology, Part I. Goverment Printing Office, Washington, DC, USA. ) named the bird "Gray Greenlet." Its Latin name, from vicinis, means neighboring or related, and refers to the close resemblance of this species to other species of small gray birds. As he encountered no other individuals of this species at the time, Coues believed the bird to be rare. Nine years passed before new reports were made by Henshaw (Henshaw 1875c Henshaw, H. W. . Report upon the ornithological collections made in portions of Nevada, Utah, California, Colorado, New Mexic

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

## EcologyAndDiet

### EcologyAndDiet-01

- fact_id: `fact_1a0acae4b915e8cbf4e6e4582e1081d5`
- subject: Orange-crowned Warbler / `Leiothlypis celata`
- domain: `EcologyAndDiet`
- predicate: `HAS_PREDATOR`
- object_text: nest predators
- evidence_id: `evidence_3ffa52f752fe81a2`
- source_chunk_id: `Leiothlypis celata::133`
- source_chapter: `MortalityPredationParasites`
- automated_same_taxon_hint: `YES` (subject scientific=`Leiothlypis celata`, evidence chunk taxon=`Leiothlypis celata`, chunk taxon=`Leiothlypis celata`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_PREDATOR::nest predators::Leiothlypis celata::133`

evidence_quote:

> Nest predation accounted for nearly all L. c. lutescens nest failures in central inner-coastal California

chunk_preview:

> Nest predation accounted for 80% of failed L. c. orestera nests in Arizona (data given for Orange-crowned and Virginia's warblers combined; Zyskowski 1993). Predation rates on orestera eggs and nestlings about equal in Arizona (Martin et al. 2000), and there is increased nest predation associated with breeding sympatrically with Virginia's Warblers (Martin and Martin, 2001a; see Behavior: social and interspecific behavior). Also, increased nest predation rates result from abiotic and biotic interactions associated with annual and long-term climate changes (Martin 2001, 2007; see Demography and populations: population regulation). Nest predation accounted for nearly all L. c. lutescens nest f

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### EcologyAndDiet-02

- fact_id: `fact_359c5ea5f9b327c72f987a864e77156c`
- subject: Bluethroat / `Luscinia svecica`
- domain: `EcologyAndDiet`
- predicate: `EATS_ITEM`
- object_text: caterpillars
- evidence_id: `evidence_fe0cb84a889631a0`
- source_chunk_id: `Luscinia svecica::59`
- source_chapter: `DietAndForaging`
- automated_same_taxon_hint: `YES` (subject scientific=`Luscinia svecica`, evidence chunk taxon=`Luscinia svecica`, chunk taxon=`Luscinia svecica`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `EATS_ITEM::caterpillars::Luscinia svecica::59`

evidence_quote:

> Stomachs of 47 breeding birds from Kirghizstan held ants (in 25), caterpillars, and mostly adult beetles; moth caterpillars brought to nest in Sweden; In India, recorded winter food water-beetles, water-snails, weevils, caterpillars and fl…

chunk_preview:

> Stomachs of 47 breeding birds from Kirghizstan held ants (in 25), caterpillars, and mostly adult beetles; beetles, large dipterans and hymenopterans taken in Alaska and E Siberia. Food brought to nestlings in Russia mainly beetles, spiders and larval sawflies (c. 20% by number of each), and further sampling in same area yielded 23% larval sawflies, 23% tipulid flies, 19% flies, 14% lepidopterans, remainder unknown; moth caterpillars brought to nest in Sweden, and in Belgium mainly earthworms but also tipulid flies, probably small crustaceans and two young Rana frogs. In India, recorded winter food water-beetles, water-snails, weevils, caterpillars and flies. Food Selection and Storage No inf

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### EcologyAndDiet-03

- fact_id: `fact_08c865508c726991a9feca5589b99515`
- subject: Little Blue Heron / `Egretta caerulea`
- domain: `EcologyAndDiet`
- predicate: `FORAGES_IN_STRATUM`
- object_text: 
- evidence_id: `evidence_11998336ca99d7a1`
- source_chunk_id: `Egretta caerulea::45`
- source_chapter: `DietAndForaging`
- automated_same_taxon_hint: `YES` (subject scientific=`Egretta caerulea`, evidence chunk taxon=`Egretta caerulea`, chunk taxon=`Egretta caerulea`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `FORAGES_IN_STRATUM::::Egretta caerulea::45`

evidence_quote:

> Little Blue Herons nesting on Lake Okeechobee, Florida, forage in spike rush (Eleocharis cellulosa) and grass- (Panicum spp.) dominated shallow marshes more frequently than expected based on availability (Smith 1994a)

chunk_preview:

> ), Zacco, Rhinogobius, Cobitis (108 Nota, Y. . Effects of body size and sex on foraging territoriality of the Little Egret (Egretta garzetta) in Japan. Auk 120 :791-798. ), Gambusia, Leuciscus, Perca, Cyprinus, Carassius, Gasterosteus, Anguilla, Gobius, Tinca, Mugil, Eupomotis, and Atherina (4 Kushlan, J. A., and J. A. Hancock . The Herons. Oxford University Press, New York, NY, USA. ), usually under 1 gram (Africa) or 20 grams (Israel), and most commonly 1 to 4 centimeters long, but sometimes up to 10 centimeters (4 Kushlan, J. A., and J. A. Hancock . The Herons. Oxford University Press, New York, NY, USA. , 24 del Hoyo, J., A. Elliott, and J. Sargatal, Editors . Handbook of the Birds of th

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### EcologyAndDiet-04

- fact_id: `fact_a1d1fe193ae2da9b832dd22c327dbb31`
- subject: Wood Stork / `Mycteria americana`
- domain: `EcologyAndDiet`
- predicate: `FORAGES_IN_STRATUM`
- object_text: 15.0-50.0 cm
- evidence_id: `evidence_4f63648399337d5e`
- source_chunk_id: `Mycteria americana::34`
- source_chapter: `DietAndForaging`
- automated_same_taxon_hint: `YES` (subject scientific=`Mycteria americana`, evidence chunk taxon=`Mycteria americana`, chunk taxon=`Mycteria americana`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `FORAGES_IN_STRATUM::15.0-50.0 cm::Mycteria americana::34`

evidence_quote:

> In s. Florida, obtains most food from water 15-50 cm deep (Kahl 1964).

chunk_preview:

> , Ogden et al. 1978 Ogden, J. C., J. A. Kushlan and J. T. Tilmant. . The food habits and nesting success of Wood Storks in Everglades National Park, 1974. U.S. Natl. Park Serv. Nat. Resour. Publ. 16. , Depkin et al. 1992 Depkin, F. C., M. C. Coulter and Jr. Bryan, A. L. . Food of nestling Wood Storks in east-central Georgia. Colonial Waterbirds 15:219-225. ). Most often takes live prey, but also dead fish at fish kills. In Venezuela, during dry season feeds almost exclusively on fish; from Jun through Oct fish constitute about 50% of diet, crabs about 35%, and insects and frogs almost equally the remaining 15% (Gonzalez 1997 Gonzalez, J. A. . Seasonal variation in the foraging ecology of the

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### EcologyAndDiet-05

- fact_id: `fact_c68d5a2aa885f25b310cc82ea44530b7`
- subject: Red-tailed Tropicbird / `Phaethon rubricauda`
- domain: `EcologyAndDiet`
- predicate: `FORAGES_BY`
- object_text: 
- evidence_id: `evidence_ae732a6667b5b965`
- source_chunk_id: `Phaethon rubricauda::1`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Phaethon rubricauda`, evidence chunk taxon=`Phaethon rubricauda`, chunk taxon=`Phaethon rubricauda`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `FORAGES_BY::::Phaethon rubricauda::1`

evidence_quote:

> A plunge-diver that feeds solitarily

chunk_preview:

> Red-tailed Tropicbirds, first described by Boddaert from Mauritius, are the rarest of the three tropicbird species in North America, nesting in the Hawaiian Islands and dispersing widely across the central and south Pacific during the nonbreeding season. Individuals are sighted off the coast of California and Mexico on rare occasions. There are four large breeding colonies in the Hawaiian Islands (Kure, Midway, Laysan, and Lisianski) and one on Johnston Atoll to the southwest. Smaller groups breed on several other islands in the Hawaiian chain. Most of these islands are protected as U.S. Fish and Wildlife Service refuges, and the populations nest successfully in spite of some rat predation.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### EcologyAndDiet-06

- fact_id: `fact_0b2909b7e8ab50cee4bc77d244b85cb6`
- subject: Common Hoopoe / `Upupa epops`
- domain: `EcologyAndDiet`
- predicate: `EATS_ITEM`
- object_text: Scarabaeidae
- evidence_id: `evidence_75e64f976146ade2`
- source_chunk_id: `Upupa epops::49`
- source_chapter: `DietAndForaging`
- automated_same_taxon_hint: `YES` (subject scientific=`Upupa epops`, evidence chunk taxon=`Upupa epops`, chunk taxon=`Upupa epops`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `EATS_ITEM::scarabaeidae::Upupa epops::49`

evidence_quote:

> followed by beetle (Scarabaeidae) larvae at 24.6% of items and 8.8% of mass

chunk_preview:

> In one study from northeastern Slovenia, the European mole cricket (Gryllotalpa gryllotalpa) constituted 35.4% of items and 81.3% of dry biomass fed to chicks, followed by beetle (Scarabaeidae) larvae at 24.6% of items and 8.8% of mass, Lepidoptera larvae at 15.3% of items and 4.9% of mass, the European field cricket (Gryllus campestris) at 2.8% of items and 2.5% of mass, and fly (Diptera) larvae at 13.7% of items and 1.1% of mass (140 Podletnik, M., and D. Denac . Selection of foraging habitat and diet of the Hoopoe Upupa epops in the mosaic-like cultural landscape of Goričko (NE Slovenia). Acrocephalus 36:109-132.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### EcologyAndDiet-07

- fact_id: `fact_46e0c72bea1ab4a55a58a5dd2b092ecb`
- subject: Osprey / `Pandion haliaetus`
- domain: `EcologyAndDiet`
- predicate: `INTERACTS_WITH_HUMANS`
- object_text: 
- evidence_id: `evidence_7e92e6d0511c9578`
- source_chunk_id: `Pandion haliaetus::60`
- source_chapter: `MortalityPredationParasites`
- automated_same_taxon_hint: `YES` (subject scientific=`Pandion haliaetus`, evidence chunk taxon=`Pandion haliaetus`, chunk taxon=`Pandion haliaetus`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `INTERACTS_WITH_HUMANS::::Pandion haliaetus::60`

evidence_quote:

> Competes with Bald Eagle for nest sites

chunk_preview:

> Few data. Bald Eagles are known predators of nestlings (Flemming and Bancroft 1990 Flemming, S. P. and R. P. Bancroft. . Bald Eagle attacks Osprey nestling. Journal of Raptor Research 24:26-27. Predators on adults include Great Horned Owls, at least one case of a Peregrine Falcon (Falco peregrinus), and probably caiman; predators on nestlings include Bald Eagles and raccoons (see Behavior: Predation , above). Competition with Other Species Little information. Competes with Bald Eagle for nest sites (see Ogden 1975 Ogden, J. C. . Effects of Bald Eagle territoriality on nesting Ospreys. Wilson Bulletin 87:496-505.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### EcologyAndDiet-08

- fact_id: `fact_b1bb9039f67618565335adf6fdfc2f8c`
- subject: Cape Weaver / `Ploceus capensis`
- domain: `EcologyAndDiet`
- predicate: `EATS_ITEM`
- object_text: peanut butter
- evidence_id: `evidence_b0f13f19b484911a`
- source_chunk_id: `Ploceus capensis::57`
- source_chapter: `Other`
- automated_same_taxon_hint: `YES` (subject scientific=`Ploceus capensis`, evidence chunk taxon=`Ploceus capensis`, chunk taxon=`Ploceus capensis`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `EATS_ITEM::peanut butter::Ploceus capensis::57`

evidence_quote:

> peanut butter, and suet at garden feeders (G. D. Engelbrecht, unpublished observations)

chunk_preview:

> ), and it also readily eats bread (54 Skead, C. J. . Life-History Notes on East Cape Bird Species, 1940-1990. Volume 2. Algoa Regional Services Council, Port Elizabeth, South Africa. ), peanut butter, and suet at garden feeders (G. D. Engelbrecht, unpublished observations). A male and female feeding on bread at a restaurant. © Barbara Kroening Western Cape, South Africa 30 Jul 2016 ML 213571181eBirdS65462228 ). Overall, however, the species is a mixed feeder, with invertebrates and vegetable matter consumed in nearly equal proportions (6 Elliott, C. C. H. . The biology of the Cape Weaver Ploceus capensis with special reference to its polygynous mating system. Ph.D. thesis, University of Cape

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### EcologyAndDiet-09

- fact_id: `fact_7fed4ffa6670835bd632cea044435b4e`
- subject: Aplomado Falcon / `Falco femoralis`
- domain: `EcologyAndDiet`
- predicate: `FORAGES_BY`
- object_text: flight hunting
- evidence_id: `evidence_ab7a08af2febd581`
- source_chunk_id: `Falco femoralis::45`
- source_chapter: `DietAndForaging`
- automated_same_taxon_hint: `YES` (subject scientific=`Falco femoralis`, evidence chunk taxon=`Falco femoralis`, chunk taxon=`Falco femoralis`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `FORAGES_BY::flight hunting::Falco femoralis::45`

evidence_quote:

> while flying at fast pace just above or through dense shrubs and trees

chunk_preview:

> Searches for prey from observation posts in trees or other perches, while soaring, or while flying at fast pace just above or through dense shrubs and trees (Wetmore 1926a, DKH). Hunts near watering holes along desert streams (H. McElroy, personal communication), riparian woodlands, tidal flats, marshlands, and probably also desert playas (145 Todd, W. E. C., and M. A. Carriker The birds of the Santa Marta region of Colombia: a study in altitudinal distribution. Annals of the Carnegie Museum 14.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### EcologyAndDiet-10

- fact_id: `fact_63bf537d5404c36bcad4c7de8fba77e9`
- subject: Roseate Spoonbill / `Platalea ajaja`
- domain: `EcologyAndDiet`
- predicate: `FORAGES_IN_STRATUM`
- object_text: mangrove estuary
- evidence_id: `evidence_5dfdf17503f5d48e`
- source_chunk_id: `Platalea ajaja::40`
- source_chapter: `DietAndForaging`
- automated_same_taxon_hint: `YES` (subject scientific=`Platalea ajaja`, evidence chunk taxon=`Platalea ajaja`, chunk taxon=`Platalea ajaja`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `FORAGES_IN_STRATUM::mangrove estuary::Platalea ajaja::40`

evidence_quote:

> In Florida Bay, primarily mangrove estuary of mainland bordering bay

chunk_preview:

> , Howell 1932 Howell, A. H. . Florida Bird Life. Coward-McCann, New York, NY, USA. , Coues 1874a Coues, E. . Birds of the Northwest: A handbook of the ornithology of the region drained by the Missouri River and its tributaries. U.S. Department of the Interior, U.S. Geological Survey, Miscellaneous Publication 3. Washington, DC, USA. , Allen 1942 Allen, R. P. . The Roseate Spoonbill. New York: Natl. Audubon Soc. Res. Rep. no. 2. , Friedmann and Smith 1950 Friedmann, H., and F. D. Smith . A contribution to the ornithology of northeastern Venezuela. Proceedings of the United States National Museum 100:411-538. , Haverschmidt 1968 Haverschmidt, F. . Birds of Surinam. Oliver and Boyd, Edinburgh,

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

## Habitat

### Habitat-01

- fact_id: `fact_aeb23c9d1af4a367c5e74674ac8d94fe`
- subject: Parasitic Jaeger / `Stercorarius parasiticus`
- domain: `Habitat`
- predicate: `INHABITS_BIOME`
- object_text: Arctic tundra
- evidence_id: `evidence_7fb9ac6026d2aec3`
- source_chunk_id: `Stercorarius parasiticus::34`
- source_chapter: `Habitat`
- automated_same_taxon_hint: `YES` (subject scientific=`Stercorarius parasiticus`, evidence chunk taxon=`Stercorarius parasiticus`, chunk taxon=`Stercorarius parasiticus`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `INHABITS_BIOME::arctic tundra::Stercorarius parasiticus::34`

evidence_quote:

> Largely confined to low-lying wet coastal Arctic tundra

chunk_preview:

> Habitat in Breeding Range Largely confined to low-lying wet coastal Arctic tundravideo , usually marshy areas with numerous small lakes and cyclic peaks in abundance of brown lemmings (Schaaning 1916 Schaaning, H. T. L. . Bidrag til Novaja Semljas fauna. Dansk Ornithologisk Forenings Tidsskrift 10:145-190.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### Habitat-02

- fact_id: `fact_c0cbf599db4810f4ad64f9c0616cba61`
- subject: Brown Booby / `Sula leucogaster`
- domain: `Habitat`
- predicate: `INHABITS_BIOME`
- object_text: Tropical Waters (24-30°C, 32.65-35.35‰)
- evidence_id: `evidence_494e6a162535df5d`
- source_chunk_id: `Sula leucogaster::37`
- source_chapter: `Habitat`
- automated_same_taxon_hint: `YES` (subject scientific=`Sula leucogaster`, evidence chunk taxon=`Sula leucogaster`, chunk taxon=`Sula leucogaster`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `INHABITS_BIOME::tropical waters (24-30°c, 32.65-35.35‰)::Sula leucogaster::37`

evidence_quote:

> Nonbreeding Brown Booby near Christmas Island and over the continental shelf off north-western Australia were found mostly in waters with a sea-surface temperature of 24.0-29.9°C and salinity of 32.65-35.35%

chunk_preview:

> For roosting and breeding , exclusively smaller oceanic islands (especially flat, unforested terrain) within 30° of the Equator. Breeding colonies: on coral sand beach (Latham, west Indian Ocean); on pampa-like vegetation consisting of Eragrostis variabilis, Boerhavia diffusa, Lepidium owaihiense, Tribulus cistoides, Ipomea indica, Solanum nelsoni, and Verbesina encelioides (Kure, Hawaiian Is.). Typically avoids nesting directly on vegetation or on steep slopes or cliffs. Favors locations near cliff edges or high spots that facilitate taking flight (Duffy 1984 Duffy, D. C. . Nest site selection by Masked and Blue-footed boobies on Isla Española, Galápagos. Condor 86:302-304.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### Habitat-03

- fact_id: `fact_34e209d9d92bec1db3948fdfb69fbeca`
- subject: Bobolink / `Dolichonyx oryzivorus`
- domain: `Habitat`
- predicate: `INHABITS_BIOME`
- object_text: riparian grassland
- evidence_id: `evidence_4661265cdccdc82a`
- source_chunk_id: `Dolichonyx oryzivorus::29`
- source_chapter: `Habitat`
- automated_same_taxon_hint: `YES` (subject scientific=`Dolichonyx oryzivorus`, evidence chunk taxon=`Dolichonyx oryzivorus`, chunk taxon=`Dolichonyx oryzivorus`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `INHABITS_BIOME::riparian grassland::Dolichonyx oryzivorus::29`

evidence_quote:

> Also breeds in habitats similar to grass-sedge fields along river bottomland habitat in Wisconsin

chunk_preview:

> ). Most of this area came under intensive agriculture more than a century ago, but by that time the vast deciduous forests of the e. U.S. had been cleared, providing habitat in hay fields and meadows. Bobolinks continue to use and may prefer fields in e. U.S. comprised of a mixture of grasses and broad-leaved forbs (e.g., red clover [Trifolium pratense], dandelion [Taraxacum officinale]). Specifically, density is significantly greater in fields in w.-central New York with relatively low amounts of total vegetative cover, low alfalfa (Medicago sativa) cover, and low total legume cover but with high litter cover and high grass-to-legume ratios relative to other nearby fields (Bollinger 1988b B

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### Habitat-04

- fact_id: `fact_1e6eb1a9c082988277668cad8fba78db`
- subject: Hoatzin / `Opisthocomus hoazin`
- domain: `Habitat`
- predicate: `INHABITS_BIOME`
- object_text: flooded forest
- evidence_id: `evidence_ce901bfd462b3ce1`
- source_chunk_id: `Opisthocomus hoazin::33`
- source_chapter: `Habitat`
- automated_same_taxon_hint: `YES` (subject scientific=`Opisthocomus hoazin`, evidence chunk taxon=`Opisthocomus hoazin`, chunk taxon=`Opisthocomus hoazin`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `INHABITS_BIOME::flooded forest::Opisthocomus hoazin::33`

evidence_quote:

> In another study site in the Amazon Basin in Ecuador, the Hoatzin was found in patches of flooded forest that surrounded lakes and creeks

chunk_preview:

> , 22 Domínguez-Bello, M. G., F. Michelangeli, M. C. Ruiz, A. García, and E. Rodriguez . Ecology of the folivorous Hoatzin (Opisthocomus hoazin) on the Venezuelan plains. Auk 111 :643-651. ). It forages entirely in trees and bushes, and it requires dense vegetation. At a study site in the Venezuelan llanos, the Hoatzin was mostly found in dense gallery forests along rivers and creeks that were interspersed among open palm savanna and patches of woodland (14 Strahl, S. D. . The social organization and behavior of the Hoatzin Opisthocomus hoazin in central Venezuela. Ibis 130 :483-502. ). In another area of the Venezuelan llanos, the top five tree species found along transects in gallery forest

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### Habitat-05

- fact_id: `fact_88d9021506684567972344b51d645fcb`
- subject: Orange-crowned Warbler / `Leiothlypis celata`
- domain: `Habitat`
- predicate: `INHABITS_BIOME`
- object_text: oak woodland/mixed chaparral
- evidence_id: `evidence_3c01150905f9df49`
- source_chunk_id: `Leiothlypis celata::37`
- source_chapter: `Habitat`
- automated_same_taxon_hint: `YES` (subject scientific=`Leiothlypis celata`, evidence chunk taxon=`Leiothlypis celata`, chunk taxon=`Leiothlypis celata`)
- automated_object_overlap_hint: `4` shared object/evidence tokens
- duplicate_scan_key: `INHABITS_BIOME::oak woodland/mixed chaparral::Leiothlypis celata::37`

evidence_quote:

> wintering L. c. lutescens most numerous around extensive plantings of exotic trees/shrubs, riparian growth, and oak woodland/mixed chaparral habitats

chunk_preview:

> ). A single wintering L. c. celata encountered in central Ohio was in old field area overgrown with shrubs and small trees (WMG). In s. California, wintering L. c. lutescens most numerous around extensive plantings of exotic trees/shrubs, riparian growth, and oak woodland/mixed chaparral habitats (Grinnell and Miller 1944 Grinnell, J., and A. H. Miller . The distribution of birds of California. Pacific Coast Avifauna 27:1-608. , Cody 1974 Cody, M. L. . Competition and Structure of Bird Communities. Princeton University Press, Princeton, NJ, USA. , Garrett and Dunn 1981 Garrett, K., and J. Dunn . Birds of Southern California: Status and Distribution. Los Angeles Audubon Society, Los Angeles,

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### Habitat-06

- fact_id: `fact_0c533efb588fe88367c3ae00dfa60dc5`
- subject: Herald Petrel / `Pterodroma heraldica`
- domain: `Habitat`
- predicate: `USES_MICROHABITAT`
- object_text: upwelling zone
- evidence_id: `evidence_14d77661e022802e`
- source_chunk_id: `Pterodroma heraldica::41`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Pterodroma heraldica`, evidence chunk taxon=`Pterodroma heraldica`, chunk taxon=`Pterodroma heraldica`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `USES_MICROHABITAT::upwelling zone::Pterodroma heraldica::41`

evidence_quote:

> Marine habitat during breeding season ... Natividad, San Benito, and off-shore rocks of Guadalupe Islands are located in strong, year-round upwelling

chunk_preview:

> ; B.S. Keitt, personal observation). All current nesting islands are under 200 m in elevation; majority of nest sites are at elevations under 50 m (B.S. Keitt, personal observation). Black-vented Shearwater breeding site - Natividad Island, Baja California.Aerial view of Natividad Island (looking northwest) - the largest Black-vented Shearwater nesting colony. Note airstrip in the foreground, and the town at left; the colony encompasses all of the lighter areas (i.e., not in darker areas showing mountain ranges). by the Cooperative Buzos y Pescadores. Marine habitat during breeding season Natividad, San Benito, and off-shore rocks of Guadalupe Islands are located in strong, year-round upwell

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### Habitat-07

- fact_id: `fact_3064ac65bdba80b34b6b6c2401947e1e`
- subject: Surfbird / `Calidris virgata`
- domain: `Habitat`
- predicate: `INHABITS_BIOME`
- object_text: 
- evidence_id: `evidence_c4616e1362877e65`
- source_chunk_id: `Calidris virgata::31`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Calidris virgata`, evidence chunk taxon=`Calidris virgata`, chunk taxon=`Calidris virgata`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `INHABITS_BIOME::::Calidris virgata::31`

evidence_quote:

> The Indian Courser also occurs in gravelly desert, plowed and harvested fields, bare pasture, and overgrazed areas... In Kachchh (Gujarat), it used saline grasslands, as well as areas of the Naliya Grassland, with dominant grasses includin…

chunk_preview:

> ). The Indian Courser also occurs in gravelly desert, plowed and harvested fields, bare pasture, and overgrazed areas (e.g., ). In Kachchh (Gujarat), it used saline grasslands, as well as areas of the Naliya Grassland, with dominant grasses including Cymbopogon sp., Aristida sp., and Dichanthium sp. (23 Munjpara, S. B., and I. R. Gadhvi . Threats to foraging habitat of Indian Courser Cursorius coromandelicus in Abdasa Taluka, Kachchh, Gujarat, India. Journal of the Bombay Natural History Society 106 :339-340. , 24 Munjpara, S. B., and I. R. Gadhvi . Feeding ecology of Indian Courser Cursorius coromandelicus. Indian Journal of Life Sciences 3 :91-96 ). In Sri Lanka it prefers arid plains near

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### Habitat-08

- fact_id: `fact_39f39d0660b6c658046e5bbbeb459ab5`
- subject: Limpkin / `Aramus guarauna`
- domain: `Habitat`
- predicate: `INHABITS_BIOME`
- object_text: Cattail Marsh
- evidence_id: `evidence_d132bebdeb2d3cff`
- source_chunk_id: `Aramus guarauna::31`
- source_chapter: `Habitat`
- automated_same_taxon_hint: `YES` (subject scientific=`Aramus guarauna`, evidence chunk taxon=`Aramus guarauna`, chunk taxon=`Aramus guarauna`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `INHABITS_BIOME::cattail marsh::Aramus guarauna::31`

evidence_quote:

> In Everglades, apple snails found in all habitat types (sawgrass, prairie, slough, and cattail); higher densities more likely in prairie or cattail habitats in some sites

chunk_preview:

> ). Specific habitat quantification not published. Typical trees and shrubs in these habitats include bald cypress (Taxodium distichum), cabbage palm (Sabal palmetto), live oak (Quercus virginiana), red maple (Acer rubrum), southern willow (Salix caroliniana), wax myrtle (Myrica cerifera), and dahoon holly (Ilex cassine). Shrubs important for nesting are frequently draped in vines, typically climbing hempweed (Mikania scandens), poison ivy (Rhus radicans), grape (Vitis spp.), and Virginia creeper (Parthenocissus quinquefolia). Aquatic plants in these habitats typically include natives like duckweed (Sagittaria lancifolia), spatterdock (Nuphar luteum), pickerelweed (Pontedaria spp.), cattail (

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### Habitat-09

- fact_id: `fact_6205dc9f75096ecbbcd412f3c76ff03f`
- subject: Mourning Dove / `Zenaida macroura`
- domain: `Habitat`
- predicate: `INHABITS_BIOME`
- object_text: 
- evidence_id: `evidence_fbc87ec967495a0d`
- source_chunk_id: `Zenaida macroura::50`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Zenaida macroura`, evidence chunk taxon=`Zenaida macroura`, chunk taxon=`Zenaida macroura`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `INHABITS_BIOME::::Zenaida macroura::50`

evidence_quote:

> Granivorous habitat generalist that opportunistically takes advantage of seasonally available food resources among a wide variety of habitats that vary across its extensive range.

chunk_preview:

> Granivorous habitat generalist that opportunistically takes advantage of seasonally available food resources among a wide variety of habitats that vary across its extensive range. Diet consists mostly (99%) of seeds from cultivated or wild plants with insignificant amounts of animal matter and leafy vegetation incidentally ingested (Mirarchi 1993c Mirarchi, R. E. (1993c). "Energetics, metabolism and reproductive physiology." In Ecology and management of the Mourning Dove, edited by T. S. Baskett, M. W. Sayre, R. E. Tomlinson and R. E. Mirarchi, 143-160. Harrisburg, PA: Stackpole Books.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### Habitat-10

- fact_id: `fact_75b42db490a9a1df11f12552002b7f99`
- subject: Tree Swallow / `Tachycineta bicolor`
- domain: `Habitat`
- predicate: `INHABITS_BIOME`
- object_text: constructed wetland
- evidence_id: `evidence_efa2174b58327409`
- source_chunk_id: `Tachycineta bicolor::36`
- source_chapter: `Habitat`
- automated_same_taxon_hint: `YES` (subject scientific=`Tachycineta bicolor`, evidence chunk taxon=`Tachycineta bicolor`, chunk taxon=`Tachycineta bicolor`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `INHABITS_BIOME::constructed wetland::Tachycineta bicolor::36`

evidence_quote:

> Hartzell et al. documented the complete absence of Tree Swallows from created wetlands

chunk_preview:

> Habitat in Breeding Range Tends to breed near bodies of water over which individuals can forage for flying insects (See: Food Habits). Thus, common habitat includes fields, marshes, shorelines, and wooded swamps with standing dead trees. In the east, historical association with beavers that flooded big tracts of forest likely provided an abundance of dead trees where cavities were generated. As secondary cavity-nesters, many of the habitat requirements for breeding Tree Swallows overlap substantially with those of primary cavity-nesters, such as Red-naped Sapsuckers (Sphyrapicus nuchalis) and Northern Flickers (Colaptes auratus; Dobkin et al. 1995, Lawler and Edwards Jr. 2002). However, Tree

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

## LifeHistoryAndBreeding

### LifeHistoryAndBreeding-01

- fact_id: `fact_6edfa281eb1b0e08d1de2fc0d1bf3e62`
- subject: Northern Jacana / `Jacana spinosa`
- domain: `LifeHistoryAndBreeding`
- predicate: `BREEDS_DURING`
- object_text: 
- evidence_id: `evidence_3b2695cb4b5f6fec`
- source_chunk_id: `Jacana spinosa::67`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Jacana spinosa`, evidence chunk taxon=`Jacana spinosa`, chunk taxon=`Jacana spinosa`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `BREEDS_DURING::::Jacana spinosa::67`

evidence_quote:

> Rising water levels associated with beginning of rainy season trigger reproductive activities.

chunk_preview:

> Rising water levels associated with beginning of rainy season trigger reproductive activities. Increases in sexual interactions and nest-building behavior lead to female's producing a clutch for 1 of her males. Then she lays replacement clutch for the male or first clutch for one of her other males, starting 7-50 d (average 22) after completing first clutch. Egg loss is common, and replacement clutches are common. Females often lay 2-3 clutches or more for each of their mates during single breeding season or period. Interclutch interval is quite variable and depends on females' ability to produce eggs, as well as availability of motivated males. At seasonal locations, stable or falling water

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### LifeHistoryAndBreeding-02

- fact_id: `fact_a1eeb1dfe425a085f43f640293479f99`
- subject: Cuckoo-roller / `Leptosomus discolor`
- domain: `LifeHistoryAndBreeding`
- predicate: `HAS_FLEDGING_PERIOD`
- object_text: 30 days
- evidence_id: `evidence_c097b4d7d800ee69`
- source_chunk_id: `Leptosomus discolor::18`
- source_chapter: `BreedingPhenology`
- automated_same_taxon_hint: `YES` (subject scientific=`Leptosomus discolor`, evidence chunk taxon=`Leptosomus discolor`, chunk taxon=`Leptosomus discolor`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_FLEDGING_PERIOD::30 days::Leptosomus discolor::18`

evidence_quote:

> fledging c. 30 days

chunk_preview:

> ) in Madagascar, but probably much longer on Anjouan at least, where 3-4-week-old juvenile found in late Apr (1 Safford, R. J., and A. F. A. Hawkins, Editors . The Birds of Africa. Volume 8. The Malagasy Region. Christopher Helm, London, UK. ). Presumed to be monogamous and territorial, with pairs observed year-round (1 Safford, R. J., and A. F. A. Hawkins, Editors . The Birds of Africa. Volume 8. The Malagasy Region. Christopher Helm, London, UK. ). Obvious aerial displays, sometimes performed in groups, once involving c. 10 individuals, and on another occasion four males (one of them subadult) displayed to a single female perched in a tree (5 Goodman, S. M., M. Pidgeon, A. F. A. Hawkins, a

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### LifeHistoryAndBreeding-03

- fact_id: `fact_2eeda10ed30e669063288f83e5ef1556`
- subject: Cape Weaver / `Ploceus capensis`
- domain: `LifeHistoryAndBreeding`
- predicate: `NESTS_AT`
- object_text: 10.0 m
- evidence_id: `evidence_8bf23a765033888b`
- source_chunk_id: `Ploceus capensis::91`
- source_chapter: `Introduction`
- automated_same_taxon_hint: `YES` (subject scientific=`Ploceus capensis`, evidence chunk taxon=`Ploceus capensis`, chunk taxon=`Ploceus capensis`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `NESTS_AT::10.0 m::Ploceus capensis::91`

evidence_quote:

> They are usually placed relatively high, up to 10 m, above ground, although some nests are much lower

chunk_preview:

> Nests in trees are suspended from the tips of branches. They are usually placed relatively high, up to 10 m, above ground, although some nests are much lower (114 Hockey, P. A. R., L. G. Underhill, and M. Neatherway . Atlas of the Birds of the Southwestern Cape. Cape Bird Club, Cape Town, South Africa.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### LifeHistoryAndBreeding-04

- fact_id: `fact_d84129f72f59aa4a60611ecc99e49cbd`
- subject: Java Sparrow / `Padda oryzivora`
- domain: `LifeHistoryAndBreeding`
- predicate: `HAS_FLEDGING_PERIOD`
- object_text: 24-32 days
- evidence_id: `evidence_4c58ce6c0d44c38e`
- source_chunk_id: `Padda oryzivora::96`
- source_chapter: `IncubationAndParentalCare`
- automated_same_taxon_hint: `YES` (subject scientific=`Padda oryzivora`, evidence chunk taxon=`Padda oryzivora`, chunk taxon=`Padda oryzivora`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_FLEDGING_PERIOD::24-32 days::Padda oryzivora::96`

evidence_quote:

> Under captive conditions, young fledge 24-32 d after hatching (67 Dorn, J. . Brutbeobachtungen an reisfinken. Die Gefierderte Welt 90:227-228.)

chunk_preview:

> ). , 46 Seller, T. J. . Observations on the sexual behaviour of Java Sparrows Padda oryzivora. Avic. Mag. 80:172-176. , 10 Clunie, F. . Birds of the Fiji bush. Suva, Fiji: Fiji Mus. ). In Fiji, crop contents of chicks consisted of ripening grass seeds (61 Langham, N. P. E. . The annual cycle of the Avadavat Amandava amandava in Fiji. Emu 87:232-243. ). ). Under captive conditions, young fledge 24-32 d after hatching (67 Dorn, J. . Brutbeobachtungen an reisfinken. Die Gefierderte Welt 90:227-228. , 43 Tsuneki, K. . Studies on the social ecology and behaviour of the domesticated Java Sparrow in a cage. Etizenia 12:1-24. , L. Baptista unpubl. data). At time of departure, wings and tail are much

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### LifeHistoryAndBreeding-05

- fact_id: `fact_c112576892f023b2ecf3e07a7c1bab9a`
- subject: Mountain Quail / `Oreortyx pictus`
- domain: `LifeHistoryAndBreeding`
- predicate: `HAS_DEMOGRAPHIC_NOTE`
- object_text: Demographic research need
- evidence_id: `evidence_ee4ab5a0ab82cba1`
- source_chunk_id: `Oreortyx pictus::113`
- source_chapter: `Demography`
- automated_same_taxon_hint: `YES` (subject scientific=`Oreortyx pictus`, evidence chunk taxon=`Oreortyx pictus`, chunk taxon=`Oreortyx pictus`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_DEMOGRAPHIC_NOTE::demographic research need::Oreortyx pictus::113`

evidence_quote:

> Needs study, especially given potential for simultaneous double-clutching (see Phenology, above) and possibility of subsequent brood coalescence.

chunk_preview:

> See Eggs, above. Needs study, especially given potential for simultaneous double-clutching (see Phenology, above) and possibility of subsequent brood coalescence. Brood size of 12-15 (65 Rahm, N. M. . Quail range extension in the San Bernardino National Forest- Progress report, 1937. California Fish and Game 24:133-158.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### LifeHistoryAndBreeding-06

- fact_id: `fact_049abb1320900649bfaeca5bdd25e7bf`
- subject: Black-necked Stilt / `Himantopus mexicanus`
- domain: `LifeHistoryAndBreeding`
- predicate: `HAS_DEMOGRAPHIC_NOTE`
- object_text: 
- evidence_id: `evidence_5e52bc0f5ac82e05`
- source_chunk_id: `Himantopus mexicanus::120`
- source_chapter: `Demography`
- automated_same_taxon_hint: `YES` (subject scientific=`Himantopus mexicanus`, evidence chunk taxon=`Himantopus mexicanus`, chunk taxon=`Himantopus mexicanus`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_DEMOGRAPHIC_NOTE::::Himantopus mexicanus::120`

evidence_quote:

> A pair of Hawaiian Stilts fledged one brood and laid a second clutch, so two broods per year possible in Hawaiian Is.

chunk_preview:

> One. A pair of Hawaiian Stilts fledged one brood and laid a second clutch, so two broods per year possible in Hawaiian Is. (M. Morin unpubl. data). Proportion Of Total Females That Rear At Least One Brood To Nest-Leaving Or Independence Estimate not available because of difficulty in estimating total number of females in breeding area. Available studies only marked a portion of females and observed significant movement of both marked and unmarked individuals into and out of study area during breeding season. Life Span and Survivorship Sufficient banding and long-term monitoring has not been conducted. However, based on records for R. americana and R. avosetta at least 10 yr would be expected

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### LifeHistoryAndBreeding-07

- fact_id: `fact_e72c4e298d36ff5781f489893b4d0d5a`
- subject: Red-throated Loon / `Gavia stellata`
- domain: `LifeHistoryAndBreeding`
- predicate: `HAS_PARENTAL_ROLE`
- object_text: Parental carrying of young
- evidence_id: `evidence_eebbf73244e59bd2`
- source_chunk_id: `Gavia stellata::100`
- source_chapter: `Demography`
- automated_same_taxon_hint: `YES` (subject scientific=`Gavia stellata`, evidence chunk taxon=`Gavia stellata`, chunk taxon=`Gavia stellata`)
- automated_object_overlap_hint: `3` shared object/evidence tokens
- duplicate_scan_key: `HAS_PARENTAL_ROLE::parental carrying of young::Gavia stellata::100`

evidence_quote:

> Chicks 9-16 d old may ride on the back of a parent

chunk_preview:

> Nest abandoned within 1 d after last chick hatches. Small bits of eggshells remain behind in nest, which may be reused in subsequent years. Parental Carrying of Young Chicks 9-16 d old may ride on the back of a parent (2 Sjölander, S., and G. Ågren . Reproductive behavior of the Yellow-billed Loon Gavia adamsii. Condor 78:454-463.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### LifeHistoryAndBreeding-08

- fact_id: `fact_c66d03fb3c913f4b1b2d10e1327bf102`
- subject: Surfbird / `Calidris virgata`
- domain: `LifeHistoryAndBreeding`
- predicate: `HAS_NEST_STRUCTURE`
- object_text: nest parasitism
- evidence_id: `evidence_821cd4f873b147bc`
- source_chunk_id: `Calidris virgata::87`
- source_chapter: `NestAndEggs`
- automated_same_taxon_hint: `YES` (subject scientific=`Calidris virgata`, evidence chunk taxon=`Calidris virgata`, chunk taxon=`Calidris virgata`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_NEST_STRUCTURE::nest parasitism::Calidris virgata::87`

evidence_quote:

> Occasionally use nest cups of other pairs (if other birds not present), or even those of other species such as Dunlin, Red-necked Phalarope, Horned Lark (Eremophila alpestris), and Savannah Sparrow (Passerculus sandwichensis; Gratto et al.…

chunk_preview:

> Previous year's nest cup commonly reused if young successfully hatched there. Old nest cups often rescraped but not reused. Occasionally use nest cups of other pairs (if other birds not present), or even those of other species such as Dunlin, Red-necked Phalarope, Horned Lark (Eremophila alpestris), and Savannah Sparrow (Passerculus sandwichensis; Gratto et al. 1985 Gratto, C. L., R. I. G. Morrison and F. Cooke. . Philopatry, site tenacity, and mate fidelity in the Semipalmated Sandpiper. Auk 102:16-24.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### LifeHistoryAndBreeding-09

- fact_id: `fact_61f9b6dcc60c9d2824d5cb19f4e06f1f`
- subject: Orange-crowned Warbler / `Leiothlypis celata`
- domain: `LifeHistoryAndBreeding`
- predicate: `HAS_CLUTCH_SIZE`
- object_text: Leiothlypis celata sordida
- evidence_id: `evidence_acea565e6946490b`
- source_chunk_id: `Leiothlypis celata::128`
- source_chapter: `Demography`
- automated_same_taxon_hint: `YES` (subject scientific=`Leiothlypis celata`, evidence chunk taxon=`Leiothlypis celata`, chunk taxon=`Leiothlypis celata`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_CLUTCH_SIZE::leiothlypis celata sordida::Leiothlypis celata::128`

evidence_quote:

> L. c. sordida mean clutch size = 3.3 ± 0.6 (range = 3-4, n = 3 nests) on Channel Is.

chunk_preview:

> , Bent 1953b Bent, A. C. . Life Histories of North American Wood Warblers. Bulletin of the United States National Museum 203. , WFVZ, CNR); arctic regions 4-6 eggs/clutch (Baird et al. 1874b Baird, S. F., T. M. Brewer, and R. Ridgway . A History of North American Birds. Land Birds. Volume 2. Little, Brown, and Company, Boston, MA, USA. , WFVZ). Based on 200 nest records (WFVZ, CNR), no significant pattern of decreasing clutch size with latitude, except reduced clutch size (3-4 eggs/clutch) in insular southern race (L. c. sordida). Mean clutch size for cent. Inner-coastal California L. c. lutescens = 4.6 eggs/clutch (± 0.1, n = 59 nests, range = 3-6; WMG). L. c. sordida mean clutch size = 3.3

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### LifeHistoryAndBreeding-10

- fact_id: `fact_94b944977630a10d4816ad6a98f34647`
- subject: Bluethroat / `Luscinia svecica`
- domain: `LifeHistoryAndBreeding`
- predicate: `HAS_PARENTAL_ROLE`
- object_text: brooding
- evidence_id: `evidence_5ac8e95e95eb369b`
- source_chunk_id: `Luscinia svecica::120`
- source_chapter: `IncubationAndParentalCare`
- automated_same_taxon_hint: `YES` (subject scientific=`Luscinia svecica`, evidence chunk taxon=`Luscinia svecica`, chunk taxon=`Luscinia svecica`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_PARENTAL_ROLE::brooding::Luscinia svecica::120`

evidence_quote:

> Only females observed brooding young in Alaska (BJM)

chunk_preview:

> ). Only females observed brooding young in Alaska (BJM), but based on limited number of nests. ). ). On Seward Peninsula, fledge mid-Jul; earliest at Serpentine Hot Springs 3-4 Jul (Kessel 1989 Kessel, B. . Birds of the Seward Peninsula, Alaska: Their Biogeography, Seasonality and Natural History. University of Alaska Press, Fairbanks, AK, USA. ). In Alaska, either or both sexes may feed young up to a week postfledging (BJM). Young fed as late as 22 Jul on Seward Peninsula and 20 Jul at Cape Romanzof (Kessel 1989 Kessel, B. . Birds of the Seward Peninsula, Alaska: Their Biogeography, Seasonality and Natural History. University of Alaska Press, Fairbanks, AK, USA. , BJM). In double-brooded Eu

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

## MorphologyAndIdentification

### MorphologyAndIdentification-01

- fact_id: `fact_b9138565eb46ef1502a4bb6604599f31`
- subject: Hawaiian Crow / `Corvus hawaiiensis`
- domain: `MorphologyAndIdentification`
- predicate: `HAS_MOLT_PATTERN`
- object_text: definitive prebasic molt
- evidence_id: `evidence_4a9dc728db112db6`
- source_chunk_id: `Corvus hawaiiensis::12`
- source_chapter: `PlumageAndMolt`
- automated_same_taxon_hint: `YES` (subject scientific=`Corvus hawaiiensis`, evidence chunk taxon=`Corvus hawaiiensis`, chunk taxon=`Corvus hawaiiensis`)
- automated_object_overlap_hint: `3` shared object/evidence tokens
- duplicate_scan_key: `HAS_MOLT_PATTERN::definitive prebasic molt::Corvus hawaiiensis::12`

evidence_quote:

> Definitive Prebasic molt presumably complete. Both adults and immatures molt flight feathers (presumably also contour feathers) mainly during Jul-Oct, but as early as mid-Jun and as late as Dec (see Figure 7). Variation between individuals…

chunk_preview:

> Definitive Prebasic molt presumably complete. Both adults and immatures molt flight feathers (presumably also contour feathers) mainly during Jul-Oct, but as early as mid-Jun and as late as Dec (see Figure 7 ). Variation between individuals, sexes, and age classes in timing, duration, and sequence of molt not described, but nonbreeding birds molt earlier than breeding birds. Breeding birds begin molt soon after nesting. Overall appearance dull (not iridescent) Sepia (119; also see Distinguishing characteristics, above). Distal end of contour feathers Sepia; proximal end Medium Neutral Gray but hidden by distal ends of overlying feathers. Primaries range from Vandyke Brown when fresh to Hair

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### MorphologyAndIdentification-02

- fact_id: `fact_6026b7fc9b4894aade3b651e05e0803d`
- subject: Double-crested Cormorant / `Nannopterum auritum`
- domain: `MorphologyAndIdentification`
- predicate: `HAS_BODY_MASS`
- object_text: Double-crested Cormorant
- evidence_id: `evidence_2c85d718713f84f3`
- source_chunk_id: `Nannopterum auritum::97`
- source_chapter: `Measurements`
- automated_same_taxon_hint: `YES` (subject scientific=`Nannopterum auritum`, evidence chunk taxon=`Nannopterum auritum`, chunk taxon=`Nannopterum auritum`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `HAS_BODY_MASS::double-crested cormorant::Nannopterum auritum::97`

evidence_quote:

> 46.1 g (n = 20; 139 ... or 44.9 g (n = 448; 136 ... This amount is 2.7% of adult mass

chunk_preview:

> ). ), later stained brown from feces and dirt. Calcite layer is chalky in texture, giving irregular surface, and is excluded from the "true" thickness presented in Table 1. ), 46.1 g (n = 20; 139 Mitchell, R. M. . Breeding biology of the Double-crested Cormorant on Utah lake. Great Basin Naturalist 37:1-23. ), or 44.9 g (n = 448; 136 Brechtel, S. H. . The reproductive ecology of Double-crested Cormorants in southern Alberta. M. Sc. thesis, Univ. of Alberta, Edmonton. ). This amount is 2.7% of adult mass, which is small compared to other seabirds (modal clutch weighs 10.7% of adult). ). Double-crested Cormorant was one of the first species to show DDE-induced eggshell-thinning after commercia

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### MorphologyAndIdentification-03

- fact_id: `fact_540c1c1ee74b2cbe9059663956f277a3`
- subject: King Rail / `Rallus elegans`
- domain: `MorphologyAndIdentification`
- predicate: `HAS_STRUCTURE_TRAIT`
- object_text: tail length
- evidence_id: `evidence_642789587f958f10`
- source_chunk_id: `Rallus elegans::7`
- source_chapter: `PlumageAndMolt`
- automated_same_taxon_hint: `YES` (subject scientific=`Rallus elegans`, evidence chunk taxon=`Rallus elegans`, chunk taxon=`Rallus elegans`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_STRUCTURE_TRAIT::tail length::Rallus elegans::7`

evidence_quote:

> the tail is short

chunk_preview:

> King Rails have 10 functional primaries, 9 secondaries (including 3 tertials), and 12 rectrices. The wings are rounded (p5 or p6 is the longest primary), the tail is short, and the legs and feet are strong. Geographic variation in appearance is slight. The following molt and plumage descriptions pertain to the widespread nominate North American subspecies R. e. elegans; see Systematics: Geographic Variation for variation in appearance of other recognized subspecies in Cuba and Mexico. No geographic or sex-specific variation in molt strategies reported, although variation in timing and extent likely in temperate vs. subtropical breeding populations, responding to variable environmental constr

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### MorphologyAndIdentification-04

- fact_id: `fact_6d42423cd38c8832ff3c8eae264f2117`
- subject: Northern Shrike / `Lanius borealis`
- domain: `MorphologyAndIdentification`
- predicate: `HAS_BILL_LENGTH`
- object_text: 
- evidence_id: `evidence_fc02a948e34186d3`
- source_chunk_id: `Lanius borealis::5`
- source_chapter: `Identification`
- automated_same_taxon_hint: `YES` (subject scientific=`Lanius borealis`, evidence chunk taxon=`Lanius borealis`, chunk taxon=`Lanius borealis`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_BILL_LENGTH::::Lanius borealis::5`

evidence_quote:

> Loggerhead Shrike ... with a smaller bill that is entirely black

chunk_preview:

> Loggerhead Shrike is similar, but smaller (< 60 g, wing length < 106 mm), usually darker gray above, with a smaller bill that is entirely black and only rarely slightly paler at base of lower mandible (Northern Shrike has a black bill in summer, but the base of the lower mandible is pale in winter when the species may co-occur with Loggerhead Shrike). Best distinguishing characters of adult Northern Shrike are narrower black mask, especially through the lores, which are paler than on Loggerhead Shrike; whitish nasal tufts (blackish in Loggerhead Shrike), and lack of black across base of forehead; broader, more prominent white supercilium above mask, especially behind eye, where white is abse

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### MorphologyAndIdentification-05

- fact_id: `fact_2c90294300f4423a13a217b3cdd705cf`
- subject: Anhinga / `Anhinga anhinga`
- domain: `MorphologyAndIdentification`
- predicate: `HAS_SEXUAL_DIMORPHISM`
- object_text: null
- evidence_id: `evidence_80f65cf66505ef63`
- source_chunk_id: `Anhinga anhinga::6`
- source_chapter: `PlumageAndMolt`
- automated_same_taxon_hint: `YES` (subject scientific=`Anhinga anhinga`, evidence chunk taxon=`Anhinga anhinga`, chunk taxon=`Anhinga anhinga`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_SEXUAL_DIMORPHISM::null::Anhinga anhinga::6`

evidence_quote:

> Male. Entire plumage black ... Female. Head, neck, and upper portion of breast and back tawny buff ... with rich chestnut band across breast

chunk_preview:

> and on examination of specimens, unless otherwise stated. ). ); silver-gray markings on wings and upperparts may be apparent while down is still present on breast. "Head down to upper breast cinnamon buff, becoming darker brownish on rest of underparts; back feathers dusky, bordered lighter brownish; wings and tail mostly dusky, some rather diffuse silvery-gray markings on wing coverts, scapulars, possibly upper back"; sexes alike (Palmer 1962a Palmer, R. S., Editor . Handbook of North American Birds. Volume 1: Loons Through Flamingos. Yale University Press, New Haven, CT, USA. ). : 359) suggests that in Basic I plumage the back feathers probably lack the "brownish edges" found in Juvenile p

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### MorphologyAndIdentification-06

- fact_id: `fact_e0bcd63d807393e981f4910c045461e5`
- subject: Brown Booby / `Sula leucogaster`
- domain: `MorphologyAndIdentification`
- predicate: `HAS_MOLT_PATTERN`
- object_text: Staffelmauser (stepwise molt) pattern
- evidence_id: `evidence_e2ef1287c4042327`
- source_chunk_id: `Sula leucogaster::16`
- source_chapter: `PlumageAndMolt`
- automated_same_taxon_hint: `YES` (subject scientific=`Sula leucogaster`, evidence chunk taxon=`Sula leucogaster`, chunk taxon=`Sula leucogaster`)
- automated_object_overlap_hint: `3` shared object/evidence tokens
- duplicate_scan_key: `HAS_MOLT_PATTERN::staffelmauser (stepwise molt) pattern::Sula leucogaster::16`

evidence_quote:

> outer 3-7 juvenile primaries (among p4-p10) and corresponding primary coverts, juvenile secondaries (among s3-s4 and s10-s19), and/or 1-8 juvenile rectrices (among r2-r7) typically retained to commence Staffelmauser (stepwise) replacement…

chunk_preview:

> Incomplete, year round, occurs entirely at sea. Commences 7-9 months post fledging, often in Mar-Jul of second year in North American and Hawaiian populations, and taking variable length of time to complete; may essentially be continuous with Third Prebasic Molt (below). Body molt begins about a month after onset of flight feather molt. Primaries replaced at rate of a little less than one per month. Sequence of flight-feather replacement as in Definitive Prebasic Molt; outer 3-7 juvenile primaries (among p4-p10) and corresponding primary coverts, juvenile secondaries (among s3-s4 and s10-s19), and/or 1-8 juvenile rectrices (among r2-r7) typically retained to commence Staffelmauser (stepwise)

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### MorphologyAndIdentification-07

- fact_id: `fact_235cc158c7d5cd3301511620422edcb1`
- subject: Common Chiffchaff / `Phylloscopus collybita`
- domain: `MorphologyAndIdentification`
- predicate: `HAS_PLUMAGE_TRAIT`
- object_text: 
- evidence_id: `evidence_af067e8efe19a152`
- source_chunk_id: `Phylloscopus collybita::12`
- source_chapter: `PlumageAndMolt`
- automated_same_taxon_hint: `YES` (subject scientific=`Phylloscopus collybita`, evidence chunk taxon=`Phylloscopus collybita`, chunk taxon=`Phylloscopus collybita`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_PLUMAGE_TRAIT::::Phylloscopus collybita::12`

evidence_quote:

> Underwing coverts are whitish washed dull to bright, yellowish to yellow-olive

chunk_preview:

> Often equated with "adult non-breeding" or "adult winter" plumage in life-cycle terminology. Present primarily September-February. Plumage rather variable, both between and within subspecific populations. Upperparts and upperwing coverts rather uniform in coloration, varying from dull olive-green to brown or gray-brown with an olive wash. Fresh basic feathers can be fringed yellowish. Rectrices and remiges dusky, fringed with similar coloration as the upperparts. Sides of head with narrow and usually somewhat indistinct, dull to bright yellow to buff or whitish supercilium and a dark-olive eyeline extending from through the lores and becoming diffuse behind the eye; auriculars dull olive-gra

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### MorphologyAndIdentification-08

- fact_id: `fact_e938eeb0b9e4dbe526e7160d3bbb8efc`
- subject: Common Potoo / `Nyctibius griseus`
- domain: `MorphologyAndIdentification`
- predicate: `HAS_PLUMAGE_TRAIT`
- object_text: 
- evidence_id: `evidence_6f2da7d9cd066bce`
- source_chunk_id: `Nyctibius griseus::4`
- source_chapter: `PlumageAndMolt`
- automated_same_taxon_hint: `YES` (subject scientific=`Nyctibius griseus`, evidence chunk taxon=`Nyctibius griseus`, chunk taxon=`Nyctibius griseus`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_PLUMAGE_TRAIT::::Nyctibius griseus::4`

evidence_quote:

> Juvenile: Similar to the immature, but whiter, and boldly spotted with blackish brown along the scapulars.

chunk_preview:

> The following description is based on Cleere and refers to nominate griseus; see also Geographic Variation: Adult: Sexes similar. Gray morph: Forecrown, crown, and nape grayish brown, broadly streaked with blackish brown. Back grayish brown, speckled with brown, and streaked and spotted with blackish brown. Scapulars grayish brown mottled with whitish, streaked and spotted with blackish brown. Rump grayish brown speckled with brown, streaked and spotted with blackish brown. Uppertail coverts brown, barred with grayish brown. Rectrices brown, broadly barred with grayish brown or grayish white. Lesser wing coverts blackish brown; median wing coverts grayish brown, often tinged buffy or tawny,

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### MorphologyAndIdentification-09

- fact_id: `fact_936d21262e5d26d169f3a978993b3154`
- subject: Northern Mockingbird / `Mimus polyglottos`
- domain: `MorphologyAndIdentification`
- predicate: `HAS_MOLT_PATTERN`
- object_text: Juvenile plumage present May to September
- evidence_id: `evidence_dace4d00850e9c47`
- source_chunk_id: `Mimus polyglottos::6`
- source_chapter: `PlumageAndMolt`
- automated_same_taxon_hint: `YES` (subject scientific=`Mimus polyglottos`, evidence chunk taxon=`Mimus polyglottos`, chunk taxon=`Mimus polyglottos`)
- automated_object_overlap_hint: `4` shared object/evidence tokens
- duplicate_scan_key: `HAS_MOLT_PATTERN::juvenile plumage present may to september::Mimus polyglottos::6`

evidence_quote:

> Juvenile (First Basic) Plumage Present May-Sep.

chunk_preview:

> Present Apr-Jun. Pale sepia brown (Dwight 1900). Juvenile (First Basic) Plumage Present May-Sep. Ssimilar to Definitive Basic Plumage but with obvious brownish to black spots and streaks on brownish-gray to whitish breast feathers. Crown, nape, mantle, and back plain brownish gray with indistinct brown streaks to back feathers, lacking in later plumages; pale gray superciliary stripe may be a lighter and less distinct; wing and tail as in Definitive Basic Plumage but feathers average subtly narrower, more rounded at tips, and irregularly patterned and spotted. Juvenile primary coverts average narrower and less distinct shaft streaks, expanding less at feather tip than in definitive feathers.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### MorphologyAndIdentification-10

- fact_id: `fact_541af0ae11aa26ecf71c737bb1762db7`
- subject: Roseate Spoonbill / `Platalea ajaja`
- domain: `MorphologyAndIdentification`
- predicate: `HAS_BODY_LENGTH`
- object_text: bill length
- evidence_id: `evidence_312e0eee82345780`
- source_chunk_id: `Platalea ajaja::3`
- source_chapter: `Identification`
- automated_same_taxon_hint: `YES` (subject scientific=`Platalea ajaja`, evidence chunk taxon=`Platalea ajaja`, chunk taxon=`Platalea ajaja`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `HAS_BODY_LENGTH::bill length::Platalea ajaja::3`

evidence_quote:

> bill length 15-18 cm

chunk_preview:

> Medium-sized, pink wading bird with distinctive bill that is narrow at the base but broadens and flattens distally, appearing spoon-shaped; becoming rough in texture as bird matures. Stands about 80 cm tall; body length 71-86 cm; bill length 15-18 cm; mass 1.2-1.8 kg; wing span 1.2-1.3 m (Howell 1932 Howell, A. H. . Florida Bird Life. Coward-McCann, New York, NY, USA.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

## TaxonomyAndPhylogeny

### TaxonomyAndPhylogeny-01

- fact_id: `fact_5f990b2523099194c0a6c067c9ebdfa2`
- subject: Greater Flamingo / `Phoenicopterus roseus`
- domain: `TaxonomyAndPhylogeny`
- predicate: `HAS_CLASSIFICATION_HISTORY`
- object_text: 1.07-4.06 mya
- evidence_id: `evidence_4e9f65fa93b27044`
- source_chunk_id: `Phoenicopterus roseus::32`
- source_chapter: `SubspeciesAndVariation`
- automated_same_taxon_hint: `YES` (subject scientific=`Phoenicopterus roseus`, evidence chunk taxon=`Phoenicopterus roseus`, chunk taxon=`Phoenicopterus roseus`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_CLASSIFICATION_HISTORY::1.07-4.06 mya::Phoenicopterus roseus::32`

evidence_quote:

> Based on a combined dataset that included both nuclear and mitochondrial DNA, the extant species of Phoenicopterus possibly diverged about 2.29 million years ago (95% confidence interval: 1.07-4.06 million years ago). The divergence betwee…

chunk_preview:

> ) and genetic (55 Sibley, C. G., and J. E. Ahlquist . Phylogeny and Classification of Birds: A Study in Molecular Evolution. Yale University Press, New Haven, Connecticut, USA. , 56 Torres, C. R., L. M. Ogawa, M. A. F. Gillingham, B. Ferrari, and M. van Tuinen . A multi-locus inference of the evolutionary diversification of extant flamingos (Phoenicopteridae). BMC Evolutionary Biology 14 :1-9. , 57 Torres, C. R., and M. Van Tuinen . The evolution of flamingos. In Flamingos: Behavior, Biology, and Relationships with Humans (M. J. Anderson, Editor), Nova Publishers, New York. pp. 29-53. , 58 Frias-Soler, R. C., A. Bauer, M. A. Grohme, G. Espinosa López, M. Gutiérrez Costa, A. Llanes-Quevedo, F

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### TaxonomyAndPhylogeny-02

- fact_id: `fact_1e818144b5a7c35b9f73e0d344f81b3e`
- subject: Brown Booby / `Sula leucogaster`
- domain: `TaxonomyAndPhylogeny`
- predicate: `HAS_SUBSPECIES`
- object_text: Sula leucogaster rogersi
- evidence_id: `evidence_9045fc91e75f16d4`
- source_chunk_id: `Sula leucogaster::20`
- source_chapter: `Systematics`
- automated_same_taxon_hint: `YES` (subject scientific=`Sula leucogaster`, evidence chunk taxon=`Sula leucogaster`, chunk taxon=`Sula leucogaster`)
- automated_object_overlap_hint: `3` shared object/evidence tokens
- duplicate_scan_key: `HAS_SUBSPECIES::sula leucogaster rogersi::Sula leucogaster::20`

evidence_quote:

> Synonyms: Sula leucogaster rogersi Mathews, 1913, Austral Avian Record 1:189.-Bedout Island, West Australia.

chunk_preview:

> Dark brown in chicks, but lightens to lead gray in juveniles, and finally to adult-like yellowphoto or orange yellow by end of second cycle at 15-20 mo of age (remains brown in some subspecies or individuals of Tasman Sea and Indian Ocean).

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### TaxonomyAndPhylogeny-03

- fact_id: `fact_d0416da0360c77c8b0417b630f7323d8`
- subject: Roseate Spoonbill / `Platalea ajaja`
- domain: `TaxonomyAndPhylogeny`
- predicate: `HAS_SUBSPECIES`
- object_text: absent
- evidence_id: `evidence_0fd26566b5728129`
- source_chunk_id: `Platalea ajaja::25`
- source_chapter: `SubspeciesAndVariation`
- automated_same_taxon_hint: `YES` (subject scientific=`Platalea ajaja`, evidence chunk taxon=`Platalea ajaja`, chunk taxon=`Platalea ajaja`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_SUBSPECIES::absent::Platalea ajaja::25`

evidence_quote:

> Monotypic.

chunk_preview:

> Monotypic.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### TaxonomyAndPhylogeny-04

- fact_id: `fact_26a22cd9967ce05e4aceef492f669f7c`
- subject: Coppery-tailed Trogon / `Trogon ambiguus`
- domain: `TaxonomyAndPhylogeny`
- predicate: `RELATED_TO`
- object_text: Trogon elegans
- evidence_id: `evidence_7a5385d4231962c5`
- source_chunk_id: `Trogon ambiguus::19`
- source_chapter: `Systematics`
- automated_same_taxon_hint: `YES` (subject scientific=`Trogon ambiguus`, evidence chunk taxon=`Trogon ambiguus`, chunk taxon=`Trogon ambiguus`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `RELATED_TO::trogon elegans::Trogon ambiguus::19`

evidence_quote:

> The Coppery-tailed Trogon has long been considered conspecific with the Elegant Trogon (Trogon elegans) under an expanded Trogon elegans

chunk_preview:

> The Coppery-tailed Trogon has long been considered conspecific with the Elegant Trogon (Trogon elegans) under an expanded Trogon elegans (e.g., 22 Peters, J. L. . Check-list of birds of the world. Vol. V. Cambridge, MA: Harvard Univ. Press. Trogon elegans canescens van Rossem, 1934, Bulletin of the Museum of Comparative Zoology 77:441.-San Javier, Sonora, Mexico. (34 Van Rossem, A. J. . Critical notes on Middle American birds. Bulletin of the Museum of Comparative Zoology 77:387-490. Trogon ambiguus goldmani Nelson, 1898, Proceedings of the Biological Society of Washington 12:8.-María Madre Island, Mexico. (31 Nelson, E. W. Descriptions of new birds from the Tres Marias Islands, western Mexi

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### TaxonomyAndPhylogeny-05

- fact_id: `fact_14b91b637fbc7c647b25e6bb1155c2c0`
- subject: Greater Rhea / `Rhea americana`
- domain: `TaxonomyAndPhylogeny`
- predicate: `HAS_SUBSPECIES`
- object_text: Rhea americana albescens
- evidence_id: `evidence_ae4adc1012e0a62b`
- source_chunk_id: `Rhea americana::19`
- source_chapter: `Systematics`
- automated_same_taxon_hint: `YES` (subject scientific=`Rhea americana`, evidence chunk taxon=`Rhea americana`, chunk taxon=`Rhea americana`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `HAS_SUBSPECIES::rhea americana albescens::Rhea americana::19`

evidence_quote:

> Several subspecies are poorly known, and their listed ranges remain somewhat provisional; birds in eastern Bolivia and Mato Grosso do Sul (west-central Brazil), which are currently listed for subspecies araneipes, may instead be referable…

chunk_preview:

> , 11 SACC . Proposal (#348) to South American Classification Committee: Incluir Pterocnemia dentro de Rhea. URL: http://www.museum.lsu.edu/~Remsen/SACCprop348.htm (download July 2013). ). The Greater Rhea has hybridized with the Lesser Rhea (R. pennata) in captivity. Several subspecies are poorly known, and their listed ranges remain somewhat provisional; birds in eastern Bolivia and Mato Grosso do Sul (west-central Brazil), which are currently listed for subspecies araneipes, may instead be referable to albescens (12 Folch, A. . Rheidae (rheas). In Handbook of the Birds of the World. Volume 1 (J. del Hoyo, A. Elliott, and J. Sargatal, Editors), Lynx Edicions, Barcelona, Spain. pp. 84-89. ).

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### TaxonomyAndPhylogeny-06

- fact_id: `fact_c0720efddb95c10d8e13f4e26f0be25e`
- subject: Monk Parakeet / `Myiopsitta monachus`
- domain: `TaxonomyAndPhylogeny`
- predicate: `HAS_SUBSPECIES_DISTRIBUTION`
- object_text: 
- evidence_id: `evidence_f5224b910a20364a`
- source_chunk_id: `Myiopsitta monachus::22`
- source_chapter: `Systematics`
- automated_same_taxon_hint: `YES` (subject scientific=`Myiopsitta monachus`, evidence chunk taxon=`Myiopsitta monachus`, chunk taxon=`Myiopsitta monachus`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_SUBSPECIES_DISTRIBUTION::::Myiopsitta monachus::22`

evidence_quote:

> Cliff Parakeet ... cliff-nesting versus tree-nesting habit

chunk_preview:

> , 32 Dickinson, E. C., and J. V. Remsen, Editors . The Howard and Moore Complete Checklist of the Birds of the World, Volume 1. 4th edition. Aves Press, Eastbourne, UK. , 33 Clements, J. F., P. C. Rasmussen, T. S. Schulenberg, M. J. Iliff, T. A. Fredericks, J. A. Gerbracht, D. Lepage, A. Spencer, S. M. Billerman, B. L. Sullivan, M. Smith, and C. L. Wood . The eBird/Clements Checklist of Birds of the World: v2024. Cornell Laboratory of Ornithology, Ithaca, NY, USA. ), but has sometimes been treated as a separate species on the basis of distinctive morphology, differences in nest placement, and genetic divergence (34 Cory, C. B. . Catalogue of birds of the Americas. Part 2, No. 1. Zoological S

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### TaxonomyAndPhylogeny-07

- fact_id: `fact_8d06fc0b4f67f81da0deab5980287d5d`
- subject: Cuckoo-roller / `Leptosomus discolor`
- domain: `TaxonomyAndPhylogeny`
- predicate: `HAS_SUBSPECIES_TRAIT`
- object_text: 
- evidence_id: `evidence_5ad336e9ba4f7cef`
- source_chunk_id: `Leptosomus discolor::4`
- source_chapter: `Systematics`
- automated_same_taxon_hint: `YES` (subject scientific=`Leptosomus discolor`, evidence chunk taxon=`Leptosomus discolor`, chunk taxon=`Leptosomus discolor`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_SUBSPECIES_TRAIT::::Leptosomus discolor::4`

evidence_quote:

> crown barred blackish and chestnut-buff vs crown with blackish-green, glossier cap

chunk_preview:

> Editor's Note: This article requires further editing work to merge existing content into the appropriate Subspecies sections. Please bear with us while this update takes place.Race gracilis sometimes considered a separate species on basis of differences in size, plumage and voice; intermedius, however, appears intermediate in plumage and may thus link the other two. Proposed race anjouanensis synonymous with intermedius. Males of all three taxa are very similar in plumage, but females distinctive. Female gracilis differs from female intermedius in having pale buff head sides, and underparts with relatively sparse dark brown broad spots vs chestnut-tinged head sides to breast shading paler on

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### TaxonomyAndPhylogeny-08

- fact_id: `fact_049104255fcc73d57ff7846438e07e3a`
- subject: Swainson's Hawk / `Buteo swainsoni`
- domain: `TaxonomyAndPhylogeny`
- predicate: `HYBRIDIZES_WITH`
- object_text: Variable Hawk
- evidence_id: `evidence_a21163b41a75276d`
- source_chunk_id: `Buteo swainsoni::30`
- source_chapter: `SubspeciesAndVariation`
- automated_same_taxon_hint: `YES` (subject scientific=`Buteo swainsoni`, evidence chunk taxon=`Buteo swainsoni`, chunk taxon=`Buteo swainsoni`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `HYBRIDIZES_WITH::variable hawk::Buteo swainsoni::30`

evidence_quote:

> a presumed escaped B. polyosoma (Variable Hawk) interbred with B. swainsoni in multiple years (Wheeler 1988).

chunk_preview:

> ), but in each case putative geographic variation was attributable to color morphs, age, or individual variation. Buteo swainsoni Bonaparte, 1838 is itself a replacement name for B. vulgaris Audubon, 1837. Additional junior synonyms of B. swainsoni include B. montana Nuttall, 1840, B. bairdii Cassin, 1852, B. gutturalis Wied, 1858, and B. fuliginosus Sclater, 1858. ). Within the genus Buteo, Mayr and Short (Mayr and Short 1970 Mayr, E., and L. L. Short . Species taxa of North American birds: A contribution to comparative systematics. Publications of the Nuttall Ornithological Club 9, Cambridge, MA, USA. ) posited that B. swainsoni was closely related to the B. albicaudatus superspecies, whic

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### TaxonomyAndPhylogeny-09

- fact_id: `fact_27648dd13605866d88c56a1303a225e9`
- subject: Eurasian Skylark / `Alauda arvensis`
- domain: `TaxonomyAndPhylogeny`
- predicate: `HAS_SUBSPECIES`
- object_text: 7-16 subspecies
- evidence_id: `evidence_e2786d3874134eb2`
- source_chunk_id: `Alauda arvensis::27`
- source_chapter: `SubspeciesAndVariation`
- automated_same_taxon_hint: `YES` (subject scientific=`Alauda arvensis`, evidence chunk taxon=`Alauda arvensis`, chunk taxon=`Alauda arvensis`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_SUBSPECIES::7-16 subspecies::Alauda arvensis::27`

evidence_quote:

> Various authorities recognize 7-16 subspecies (Meinertzhagen 1951a)

chunk_preview:

> Various authorities recognize 7-16 subspecies (Meinertzhagen 1951a Meinertzhagen, R. (1951a). Review of the Alaudidae. Proc. Zool. Soc. London 121:81-132.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### TaxonomyAndPhylogeny-10

- fact_id: `fact_da783b6f8d8c8e4d6c80c629c49b87db`
- subject: Bluethroat / `Luscinia svecica`
- domain: `TaxonomyAndPhylogeny`
- predicate: `HAS_SUBSPECIES`
- object_text: 
- evidence_id: `evidence_590a618da6d58920`
- source_chunk_id: `Luscinia svecica::33`
- source_chapter: `SubspeciesAndVariation`
- automated_same_taxon_hint: `YES` (subject scientific=`Luscinia svecica`, evidence chunk taxon=`Luscinia svecica`, chunk taxon=`Luscinia svecica`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_SUBSPECIES::::Luscinia svecica::33`

evidence_quote:

> Geographical variation marked, but considerable intergradation of races; phylogenetic analysis reveals considerable genetic variation, with S all-blue and white-spotted forms ancestral to N red-spotted races

chunk_preview:

> and references therein for detailed description). Geographical variation marked, but considerable intergradation of races; phylogenetic analysis reveals considerable genetic variation, with S all-blue and white-spotted forms ancestral to N red-spotted races Johnsen et al. 2006 Johnsen, A., Andersson, S., Garcia Fernandez, J., Kempenaers, B., Pavel, V., Questiau, S., Raess, M., Rindal, E. and Lifjeld, J.T. . Molecular and phenotypic divergence in the Bluethroat (Luscinia svecica) subspecies complex. Mol. Ecol. 15: 4033-4047. . Chief differences include throat pattern of Alternate-plumage male, some populations having entirely blue throat, others having rusty-red spot, of varying shape and siz

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

## VocalAndBehavior

### VocalAndBehavior-01

- fact_id: `fact_4b69e016854925edcbdab92c33a16a41`
- subject: Gray Vireo / `Vireo vicinior`
- domain: `VocalAndBehavior`
- predicate: `HAS_AGONISTIC_BEHAVIOR`
- object_text: High-intensity Threat Display
- evidence_id: `evidence_f01b3e05c03e6a9e`
- source_chunk_id: `Vireo vicinior::64`
- source_chapter: `Locomotion`
- automated_same_taxon_hint: `YES` (subject scientific=`Vireo vicinior`, evidence chunk taxon=`Vireo vicinior`, chunk taxon=`Vireo vicinior`)
- automated_object_overlap_hint: `3` shared object/evidence tokens
- duplicate_scan_key: `HAS_AGONISTIC_BEHAVIOR::high-intensity threat display::Vireo vicinior::64`

evidence_quote:

> Maximum High-intensity Threat Display (i.e., bird singing, wings caped, thorax ruffled, and tail feathers fanned) is also used in response to playback.

chunk_preview:

> Breeding territory actively defended by male and female. When not involved in territorial chase, defending male fluffs body feathers, hunches shoulders, and holds wings slightly out with slightly spread tail. The Aggressive Threat Posture (i.e., spreading and closing of tail, breast and back feathers puffed, and crest erected) used during territorial defense. Female gives rapid, low volume Scolding Call against intruding conspecifics from adjacent breeding territories, or may watch as male attacks interloper. On one occasion, incubating female seen to chase a silent conspecific that approached the nest. Conspecifics also excluded from winter territory, although incidence of territorial dispu

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### VocalAndBehavior-02

- fact_id: `fact_38ec1d781cb6da0a504eec11727d4564`
- subject: Oilbird / `Steatornis caripensis`
- domain: `VocalAndBehavior`
- predicate: `HAS_LOCOMOTION_STYLE`
- object_text: maneuvering flight
- evidence_id: `evidence_f513a75e81fbe9a0`
- source_chunk_id: `Steatornis caripensis::60`
- source_chapter: `Locomotion`
- automated_same_taxon_hint: `YES` (subject scientific=`Steatornis caripensis`, evidence chunk taxon=`Steatornis caripensis`, chunk taxon=`Steatornis caripensis`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_LOCOMOTION_STYLE::maneuvering flight::Steatornis caripensis::60`

evidence_quote:

> Oilbird wings combine low wing loading ... with an extremely low aspect ratio ... enabling birds to ... maneuver easily

chunk_preview:

> Living in completely dark caves, the Oilbird must be able to fly very slowly and hover within narrow galleries. Collecting fruit on the wing also demands the ability to fly slowly and hover. In turn, flying for tens of kilometers to collect and carry bulky fruits demands high-speed transportation of heavy loads. Oilbird wings combine low wing loading (body mass/wing area) with an extremely low aspect ratio (wing span/mean wing width), enabling birds to fly slowly, maneuver easily, and carry large loads (3 Snow, D. W. . The natural history of the Oilbird Steatornis caripensis, in Trinidad, W.I. Part 1. General behavior and breeding habits. Zoologica 46:27-48.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### VocalAndBehavior-03

- fact_id: `fact_0e869c66d82e72d62abd3cf8412faf65`
- subject: Willow Tit / `Poecile montanus`
- domain: `VocalAndBehavior`
- predicate: `HAS_VOCALIZATION_TYPE`
- object_text: subsong
- evidence_id: `evidence_b40154aeffdbea9a`
- source_chunk_id: `Poecile montanus::42`
- source_chapter: `VocalBehavior`
- automated_same_taxon_hint: `YES` (subject scientific=`Poecile montanus`, evidence chunk taxon=`Poecile montanus`, chunk taxon=`Poecile montanus`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_VOCALIZATION_TYPE::subsong::Poecile montanus::42`

evidence_quote:

> During the post-fledging period, juveniles begin to produce babbling vocalizations, often referred to as subsong, which initially consist of unstructured notes.

chunk_preview:

> ). During the post-fledging period, juveniles begin to produce babbling vocalizations, often referred to as subsong, which initially consist of unstructured notes. As development progresses, recognizable Willow Tit calls emerge and become increasingly refined over time. The repertoire is similar to that of adults by around 50 days of age (130 Haftorn, S. . Ontogeny of the vocal repertoire in the Willow Tit Parus montanus. Ornis Scandinavica 24 :267-289. ). Learning appears to have a role in the maintenance of local dialects within populations of Willow Tit. A particular pure-tone note, found only in the population at Venabu, Norway, is suggested to be maintained via learning rather than gene

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### VocalAndBehavior-04

- fact_id: `fact_f78c1b12865933638d0cc32217790d90`
- subject: Surfbird / `Calidris virgata`
- domain: `VocalAndBehavior`
- predicate: `HAS_COURTSHIP_BEHAVIOR`
- object_text: parental care
- evidence_id: `evidence_2f7afb6a90d9ee33`
- source_chunk_id: `Calidris virgata::60`
- source_chapter: `VocalBehavior`
- automated_same_taxon_hint: `YES` (subject scientific=`Calidris virgata`, evidence chunk taxon=`Calidris virgata`, chunk taxon=`Calidris virgata`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_COURTSHIP_BEHAVIOR::parental care::Calidris virgata::60`

evidence_quote:

> Both the parents clean the nest by carrying the broken eggshells and other remains and disposing them far away

chunk_preview:

> ), the period of incubation is not definitively known, but one study suggested it is at least 35 d; one monitored egg hatched 34 d after it was found, but it is unknown exactly when the egg was laid (33 Arya, A. . Indian Courser Cursorius coromandelicus breeding at Sultanpur, Haryana, India. BirdingASIA 16:81-85. ).Adult incubating.Adult on nest.Adult on nest. ). Parental Assistance and Disposal of Eggshells Both the parents clean the nest by carrying the broken eggshells and other remains and disposing them far away (41 Sureja, N. J., H. R. Radadia, J. B. Patel, and S. K. Chovatiya . Notes on the breeding behaviour of Indian Courser Cursorius coromandelicus from Khijadiya, Jamnagar District

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### VocalAndBehavior-05

- fact_id: `fact_915d1b54f028a27fbc4392a8ec5dd3b7`
- subject: Temminck's Courser / `Cursorius temminckii`
- domain: `VocalAndBehavior`
- predicate: `HAS_VOCALIZATION_TYPE`
- object_text: tuc call
- evidence_id: `evidence_d11c20ce6d1de7de`
- source_chunk_id: `Cursorius temminckii::57`
- source_chapter: `VocalBehavior`
- automated_same_taxon_hint: `YES` (subject scientific=`Cursorius temminckii`, evidence chunk taxon=`Cursorius temminckii`, chunk taxon=`Cursorius temminckii`)
- automated_object_overlap_hint: `2` shared object/evidence tokens
- duplicate_scan_key: `HAS_VOCALIZATION_TYPE::tuc call::Cursorius temminckii::57`

evidence_quote:

> tuc call (mean duration of 0.03 s, range 0.02-0.03 s, n = 12 calls; mean peak frequency of 1,273.44 Hz ± 74.34 SD, range 1,125.00-1,406.25 Hz, n = 12 calls)

chunk_preview:

> ), are usually given in flight but also on the ground. Ground-based contact calls are associated with agitated adults when their chicks are threatened. In-flight and ground-based contact calls differ sufficiently for several parameters to regard them as subtypes. It is unknown whether both calls form part of an individual's vocal repertoire or if they are age- or sex-specific calls (2 Engelbrecht, D. . Notes on the behaviour and breeding biology of Temminck's Courser Cursorius temminckii. The Lark 58:79-86. ). The err calls are plaintive, metallic, somewhat grating, calls delivered as err-err-errrr or err-err-err-errrr, likened to a rusty door hinge (121 Skead, C. J. . Life-history Notes on

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### VocalAndBehavior-06

- fact_id: `fact_81fa1ec29e6424b09401fdcf91e5c9d5`
- subject: Least Auklet / `Aethia pusilla`
- domain: `VocalAndBehavior`
- predicate: `CALLS_DURING`
- object_text: night
- evidence_id: `evidence_d9cebd06b3adb309`
- source_chunk_id: `Aethia pusilla::40`
- source_chapter: `VocalBehavior`
- automated_same_taxon_hint: `YES` (subject scientific=`Aethia pusilla`, evidence chunk taxon=`Aethia pusilla`, chunk taxon=`Aethia pusilla`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `CALLS_DURING::night::Aethia pusilla::40`

evidence_quote:

> Rarely, vocalizations (particularly Whinney) are given in nesting crevices at night.

chunk_preview:

> Most vocalization at breeding colonies takes place during the day (see Behavior: colony attendance, below); vocal displays appear to be given throughout the nesting season, particularly by unmated individuals. Rarely, vocalizations (particularly Whinney) are given in nesting crevices at night.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### VocalAndBehavior-07

- fact_id: `fact_c4ff24875ae33be607b5db6fc5522ba0`
- subject: Oilbird / `Steatornis caripensis`
- domain: `VocalAndBehavior`
- predicate: `HAS_VOCALIZATION_TYPE`
- object_text: begging call
- evidence_id: `evidence_2a6fe7f62778546b`
- source_chunk_id: `Steatornis caripensis::52`
- source_chapter: `VocalBehavior`
- automated_same_taxon_hint: `YES` (subject scientific=`Steatornis caripensis`, evidence chunk taxon=`Steatornis caripensis`, chunk taxon=`Steatornis caripensis`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_VOCALIZATION_TYPE::begging call::Steatornis caripensis::52`

evidence_quote:

> When begging, large nestlings utter a chorus of shrill but hoarse squeaks.

chunk_preview:

> ). By age 20 days, it develops into a loud, rather coarse squeak, which becomes louder as the chick grows. When begging, large nestlings utter a chorus of shrill but hoarse squeaks. By the time it is well-feathered, it begins to utter the harsh screams of the adult (3 Snow, D. W. . The natural history of the Oilbird Steatornis caripensis, in Trinidad, W.I. Part 1. General behavior and breeding habits. Zoologica 46:27-48. ). , 4 Hilty, S. L. . Birds of Venezuela. Princeton University Press, Princeton, NJ, USA. ), which are frequently produced in flight when foraging outside caves, as well as in roosting cavesaudio . These calls include a loud, rough, and raspy, krr, krr audio , probably for c

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### VocalAndBehavior-08

- fact_id: `fact_05cad712eeb512b8848ba09a7fbed778`
- subject: Indigo Bunting / `Passerina cyanea`
- domain: `VocalAndBehavior`
- predicate: `HAS_SOCIAL_BEHAVIOR`
- object_text: song learning by matching neighbor
- evidence_id: `evidence_b7c5558a0f9d661a`
- source_chunk_id: `Passerina cyanea::48`
- source_chapter: `VocalBehavior`
- automated_same_taxon_hint: `YES` (subject scientific=`Passerina cyanea`, evidence chunk taxon=`Passerina cyanea`, chunk taxon=`Passerina cyanea`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_SOCIAL_BEHAVIOR::song learning by matching neighbor::Passerina cyanea::48`

evidence_quote:

> The first-year males then change from the first song to another song in their first breeding season. This later song usually matches the song of a neighboring territorial male.

chunk_preview:

> Song: Development In late summer a few independent juvenile males give variable subsong. On arrival in the next spring the first-year males sometimes give variable subsong, as do a few older adult males. The first songs of spring are short and the notes morph from first to last within a series. In males banded as nestlings in the previous year, the early songs are not like the songs of their father, or of another male on a nearby territory during the natal year. The first-year males then change from the first song to another song in their first breeding season. This later song usually matches the song of a neighboring territorial male. Males usually keep their definitive (last-sung) song the

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### VocalAndBehavior-09

- fact_id: `fact_699bdffb817a4412bbc976ad595ef51e`
- subject: Hawaiian Duck / `Anas wyvilliana`
- domain: `VocalAndBehavior`
- predicate: `HAS_AGONISTIC_BEHAVIOR`
- object_text: 
- evidence_id: `evidence_8df8f170d4409fb4`
- source_chunk_id: `Anas wyvilliana::57`
- source_chapter: `Locomotion`
- automated_same_taxon_hint: `YES` (subject scientific=`Anas wyvilliana`, evidence chunk taxon=`Anas wyvilliana`, chunk taxon=`Anas wyvilliana`)
- automated_object_overlap_hint: `0` shared object/evidence tokens
- duplicate_scan_key: `HAS_AGONISTIC_BEHAVIOR::::Anas wyvilliana::57`

evidence_quote:

> male defends mate through open bill-pointing, head-out rushes, and pecking

chunk_preview:

> During nonbreeding season, pairs and small groups engage in chasing, pecking while foraging. During breeding season, male defends mate through open bill-pointing, head-out rushes, and pecking, similar to that reported for Mallard (Drilling et al. 2002 Drilling, N., R. Titman, and F. McKinney. 2002. Mallard (Anas platyrhynchos). In The Birds of North America, No. 658 (A. Poole and F. Gill, eds.). The Birds of North America, Inc., Philadelphia, PA.

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

### VocalAndBehavior-10

- fact_id: `fact_ecdb89ad3e39fdbb6e701761bf8357b0`
- subject: Golden-crowned Kinglet / `Regulus satrapa`
- domain: `VocalAndBehavior`
- predicate: `HAS_VOCALIZATION_TYPE`
- object_text: Nestling Calls
- evidence_id: `evidence_13585abe20b6b4f2`
- source_chunk_id: `Regulus satrapa::45`
- source_chapter: `VocalBehavior`
- automated_same_taxon_hint: `YES` (subject scientific=`Regulus satrapa`, evidence chunk taxon=`Regulus satrapa`, chunk taxon=`Regulus satrapa`)
- automated_object_overlap_hint: `1` shared object/evidence tokens
- duplicate_scan_key: `HAS_VOCALIZATION_TYPE::nestling calls::Regulus satrapa::45`

evidence_quote:

> Two calls given by nestlings. Tseek is barely audible and given when nestlings are 2 d old. Tsipping starts by 6 d and continues until birds disperse.

chunk_preview:

> , RG). Development of song needs study. Probably sing by first breeding season. , Naugler 1993 Naugler, C. T. . Vocalizations of the Golden-crowned Kinglet in eastern North America. Journal of Field Ornithology 64:346-351. ). Primary Song.Figure 2A . Simple song is series of up to 14 ascending notes lasting up to 2 s. Complex song, described as " tsooo-tsooo-tsooo-tsooo-tsooo-tsooo-whip-lipalip !" or " tsee-tsee-tsee-tsee-teet-leetle followed by a trill" (Jewett et al. 1953 Jewett, S. G., W. P. Taylor, and J. W. Aldrich . Birds of Washington State. University of Washington Press, Seattle, WA, USA. ), starts as simple song and ends in musical warble lasting up to 3 s, dropping an octave or mo

Manual judgment: predicate_match=[ ] object_supported=[ ] same_taxon=[ ] chunk_relevant=[ ] duplicate_or_mismatch=[ ] notes=

## Sample-Level Automated Repeat Hints

- No exact duplicate `(predicate, object_text, source_chunk_id)` keys found within this 80-fact sample.
