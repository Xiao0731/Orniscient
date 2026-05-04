def get_qa_sc_prompt():
    """
    QA-SC (单选题) 
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a high-level biological benchmark. Your task is to generate ONE highly accurate, single-choice question (4 options, only 1 correct) based strictly on the provided anonymized bird monograph.

The target bird's real names have been masked as "[the bird]". You MUST use "[the bird]" in your question to refer to the species.

The type of question you are going to give today is: [{type}]. If the question type is not General, please create a question based on this specific type and include "type" in the returned JSON: "{type}"

**Knowledge Domains (Choose ONE domain that is most strongly supported by the provided text):**
1. Morphology and Identification (e.g., weight, wingspan, plumage)
2. Taxonomy and Phylogeny (e.g., genus, family)
3. Geography and Distribution (e.g., realm, continent, elevation)
4. Ecology and Life History (e.g., incubation, clutch size)
5. Ecological Function and Diet (e.g., diet category, prey types)
6. Conservation Status (e.g., IUCN status, threats)
7. Sounds and Vocal Behavior (e.g., vocalization timing, song structure)
8. General Behavior (e.g., sociality, mating system)

**Allowed Source Chapters (You MUST select ONE of these exact strings for 'source_chapter'):**
[Introduction, Field Identification, Plumages, Molts, and Structure, Systematics, Distribution, Habitat, Movements and Migration, Diet and Foraging, Sounds and Vocal Behavior, Behavior, Breeding, Demography and Populations, Conservation and Management, Relationships with People, Priorities for Future Research, About the Author(s)]

**Strict Rules:**
1. The correct answer must be unambiguously supported by the text.
2. Provide exactly 4 options (A, B, C, D). The 3 distractors must be plausible but explicitly incorrect based on the text.
3. DO NOT use any external knowledge. All information must come from the provided text.
4. The `exact_quote` MUST be a COMPLETE, intact sentence (or multiple complete sentences) that provides full context. Do not extract tiny fragments. The quote must retain the "[the bird]" mask exactly as it appears in the text.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{
  "knowledge_domain": "<Select the matching domain name from the 8 options above>",
  "type": "<The type of question you get>",
  "question": "<The question text using '[the bird]'>",
  "options": {
    "A": "<Option A text>",
    "B": "<Option B text>",
    "C": "<Option C text>",
    "D": "<Option D text>"
  },
  "answer": "<A, B, C, or D>",
  "provenance": {
    "source_db": "BOW",
    "source_chapter": "<Select EXACTLY ONE chapter name from the Allowed Source Chapters list>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text>",
    "reasoning_chain": "<Briefly explain why the answer is correct and why distractors are wrong based on the quote>"
  }
}"""
    return system_prompt

def get_qa_mc_prompt():
    """
    QA-MC (多选题)
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a high-level biological benchmark. Your task is to generate ONE highly accurate, MULTIPLE-CHOICE question (5 options, containing multiple correct answers) based strictly on the provided anonymized bird monograph.

The target bird's real names have been masked as "[the bird]". You MUST use "[the bird]" in your question to refer to the species.

The type of question you are going to give today is: [{type}]. If the question type is not General, please create a question based on this specific type and include "type" in the returned JSON: "{type}"

**Knowledge Domains & Focus Areas (Choose ONE domain that is most strongly supported by the provided text):**
1. Morphology and Identification (Focus: Combinations of key traits across different body parts or plumages)
2. Taxonomy and Phylogeny (Focus: List of recognized subspecies or related clades)
3. Geography and Distribution (Focus: Collection of native countries, regions, or habitats)
4. Ecology and Life History (Focus: Inventory of nesting materials, breeding behaviors, etc.)
5. Ecological Function and Diet (Focus: Inventory of prey items or plant types consumed)
6. Conservation Status (Focus: Multiple anthropogenic and environmental threats)
7. Sounds and Vocal Behavior (Focus: Multiple types of vocalizations or mechanical sounds)
8. General Behavior (Focus: Multiple locomotion modes or social behaviors)

**Allowed Source Chapters (You MUST select ONE of these exact strings for 'source_chapter'):**
[Introduction, Field Identification, Plumages, Molts, and Structure, Systematics, Distribution, Habitat, Movements and Migration, Diet and Foraging, Sounds and Vocal Behavior, Behavior, Breeding, Demography and Populations, Conservation and Management, Relationships with People, Priorities for Future Research, About the Author(s)]

**Strict Rules:**
1. The correct answers must be unambiguously supported by the text.
2. Provide exactly 5 options (A, B, C, D, E). 
3. There MUST be AT LEAST ONE correct option and AT LEAST ONE incorrect option (distractor). Distractors must be plausible but explicitly incorrect or unmentioned based on the text.
4. DO NOT use any external knowledge. All information must come from the provided text.
5. The `exact_quote` MUST be a COMPLETE, intact sentence (or multiple complete sentences) that provides full context. Do not extract tiny fragments. The quote must retain the "[the bird]" mask exactly as it appears in the text.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{
  "knowledge_domain": "<Select the matching domain name from the 8 options above>",
  "type": "{type}",
  "question": "<The question text asking to select ALL correct descriptions, using '[the bird]'>",
  "options": {
    "A": "<Option A text>",
    "B": "<Option B text>",
    "C": "<Option C text>",
    "D": "<Option D text>",
    "E": "<Option E text>"
  },
  "answer": "<A string containing the correct option letters separated by commas, e.g., 'A, C, D'>",
  "provenance": {
    "source_db": "BOW",
    "source_chapter": "<Select EXACTLY ONE chapter name from the Allowed Source Chapters list>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text>",
    "reasoning_chain": "<Briefly explain why the chosen options are correct and why the distractors are wrong based on the quote>"
  }
}"""
    return system_prompt

def get_qa_sa_prompt():
    """
    QA-SA (填空/简答题) 
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a high-level biological benchmark. Your task is to generate ONE highly accurate, SHORT-ANSWER (fill-in-the-blank or direct Q&A) question based strictly on the provided anonymized bird monograph. No multiple-choice options should be provided.

The target bird's real names have been masked as "[the bird]". You MUST use "[the bird]" in your question to refer to the species.

The type of question you are going to give today is: [{type}]. If the question type is not General, please create a question based on this specific type and include "type" in the returned JSON: "{type}"

**Knowledge Domains & Focus Areas (Choose ONE domain that is most strongly supported by the provided text):**
1. Morphology and Identification (Focus: Specific coloration of head, body, bare parts, or plumage. E.g., What is the specific color of the orbital skin?)
2. Taxonomy and Phylogeny (Focus: Subspecies statistics. E.g., How many valid subspecies are recognized?)
3. Geography and Distribution (Focus: Elevational range. E.g., What is the maximum recorded elevation in meters?)
4. Ecology and Life History (Focus: Typical clutch size. E.g., What is the typical number of eggs?)
5. Ecological Function and Diet (Focus: Specific foraging technique. E.g., What specific foraging action term is primarily used?)
6. Conservation Status (Focus: Demography. E.g., What is the estimated global population size?)
7. Sounds and Vocal Behavior (Focus: Auditory ID. E.g., The call is described as sounding like what object?)
8. General Behavior (Focus: Sexual behavior. E.g., What is the name of the specific courtship display?)

**Allowed Source Chapters (You MUST select ONE of these exact strings for 'source_chapter'):**
[Introduction, Field Identification, Plumages, Molts, and Structure, Systematics, Distribution, Habitat, Movements and Migration, Diet and Foraging, Sounds and Vocal Behavior, Behavior, Breeding, Demography and Populations, Conservation and Management, Relationships with People, Priorities for Future Research, About the Author(s)]

**Strict Rules:**
1. The correct answer must be unambiguously supported by the text.
2. The `answer` MUST be extremely concise. It should be a single numerical value, a short phrase, a specific noun, or a color (e.g., "3-5", "Sally-glean", "Red", "Monotypic"). Do NOT output full sentences for the answer.
3. DO NOT use any external knowledge. All information must come from the provided text.
4. The `exact_quote` MUST be a COMPLETE, intact sentence (or multiple complete sentences) that provides full context. Do not extract tiny fragments. The quote must retain the "[the bird]" mask exactly as it appears in the text.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{
  "knowledge_domain": "<Select the matching domain name from the 8 options above>",
  "type": "{type}",
  "question": "<The short-answer question text using '[the bird]'>",
  "answer": "<A highly concise entity name, numerical value, or short phrase>",
  "provenance": {
    "source_db": "BOW",
    "source_chapter": "<Select EXACTLY ONE chapter name from the Allowed Source Chapters list>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text>",
    "reasoning_chain": "<Briefly explain how the exact quote directly provides the short answer>"
  }
}"""
    return system_prompt

def get_bird_taxonomy_prompt():
    """
    Bird-Taxonomy (分类学与系统发育)
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a high-level biological benchmark. Your task is to generate ONE highly accurate question evaluating taxonomic knowledge based strictly on the provided anonymized bird monograph.

The target bird's real names have been masked as "[the bird]". You MUST use "[the bird]" in your question to refer to the species.

**CRITICAL INSTRUCTION - QUESTION TYPE:**
The specific type of question you must generate today is: [{type}]. 
You must strictly follow the rule for this specific type to formulate your question:

1. If [{type}] is "Taxonomic Trap": 
   - Search the text for keywords like 'formerly', 'previously', 'split', 'lumped'.
   - Formulate a True/False question asking if [the bird] is CURRENTLY classified in a historical or former genus/family mentioned in the text. (The correct answer should be 'False' or explain the current vs historical status).
2. If [{type}] is "Subspecies Check": 
   - Ask a question to verify valid subspecies. E.g., provide a mix of valid and invalid/former taxa names found in the text and ask "Which of these are currently accepted as valid subspecies?"
3. If [{type}] is "Monotypic Verification": 
   - Ask "Does [the bird] have any recognized subspecies?" The answer must confirm it is "Monotypic" (if none) or provide the number/list of valid subspecies.
4. If [{type}] is "Sister/Similar Taxa": 
   - Ask about the phylogenetic relationship between [the bird] and a related/sister species mentioned in the text (e.g., "Are they conspecific or distinct species?").
5. If [{type}] is "Nomenclature & Etymology": 
   - Ask for the original describer, year of description, OR the etymological origin of its scientific/common name based on the text.

*(Note: If the text completely lacks the information needed for the requested type, adapt and create a question for one of the other taxonomic types listed above that the text DOES support).*

**Allowed Source Chapters (You MUST select ONE of these exact strings for 'source_chapter'):**
[Systematics History, Subspecies, Introduction] (Preferably Systematics History or Subspecies)

**Strict Rules:**
1. The correct answer must be unambiguously supported by the text.
2. The `answer` MUST be highly concise (e.g., "False", "Monotypic", a list of subspecies, a name, or a year). Do NOT output full sentences in the answer field.
3. DO NOT use any external knowledge. All information must come from the provided text.
4. The `exact_quote` MUST be a COMPLETE, intact sentence (or multiple complete sentences) that provides full context. The quote must retain the "[the bird]" mask exactly as it appears in the text.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{
  "knowledge_domain": "Taxonomy and Phylogeny",
  "type": "{type}",
  "question": "<The specific question text tailored to the requested type, using '[the bird]'>",
  "answer": "<A highly concise true/false, numerical value, entity list, or short phrase>",
  "provenance": {
    "source_db": "BOW",
    "source_chapter": "<Select EXACTLY ONE chapter name from the Allowed list>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text>",
    "reasoning_chain": "<Briefly explain the taxonomic logic, especially for traps or taxonomic changes>"
  }
}"""
    return system_prompt

def get_bird_geo_prompt():
    """
    Bird-Geo (地理分布与迁徙)
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a high-level biological benchmark. Your task is to generate ONE highly accurate, single-choice question (4 options, 1 correct) focusing on geography, habitat, or migration, based strictly on the provided anonymized bird monograph.

The target bird's real names have been masked as "[the bird]". You MUST use "[the bird]" in your question to refer to the species.

**CRITICAL INSTRUCTION - QUESTION TYPE:**
The specific type of question you must generate today is: [{type}]. 
Follow these constraints for the chosen type:

1. If [{type}] is "Geographic Range":
   - Focus on political or physical geography (countries, continents, islands, or mountain ranges).
   - Distractor Strategy: Use "Geographic Displacement". If the bird is from the Neotropics, use Afrotropical or Indo-Malayan regions as plausible but incorrect distractors.
2. If [{type}] is "Habitat & Elevation":
   - Focus on macro-habitat (e.g., lowland rainforest) and vertical distribution (specific elevation ranges in meters).
   - Distractor Strategy: Swap the elevation (high vs. low) or the moisture regime (arid vs. humid) to test the model's precision.
3. If [{type}] is "Migration Pattern":
   - Focus on movement status (resident, migratory, nomadic) and specific routes or altitudinal shifts.
   - Distractor Strategy: Use "Behavioral Mismatch". If the bird is a long-distance migrant, offer "sedentary" or "altitudinal migrant" as distractors.

**Zoogeographic Context Awareness:**
When generating, consider the global distribution. Ensure the question reflects the specific realm (Palearctic, Nearctic, Afrotropical, Neotropical, Australasian, Indomalayan, or Oceanian) described in the text.

**Allowed Source Chapters (You MUST select ONE of these exact strings for 'source_chapter'):**
[Distribution, Habitat, Movements and Migration]

**Strict Rules:**
1. Provide exactly 4 options (A, B, C, D). Options must be distinct and non-overlapping.
2. The correct answer must be unambiguously supported by the text.
3. DO NOT use external knowledge. If the text says the bird lives at 500m, do not use your knowledge that it might also live at 700m.
4. Name Masking: If the text contains geographical adjectives in the bird's name (e.g., "African" in "African Pygmy-Kingfisher"), ensure it is masked as "[the bird]".

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{
  "knowledge_domain": "Geography and Distribution",
  "type": "{type}",
  "question": "<The question text using '[the bird]'>",
  "options": {
    "A": "<Option A>",
    "B": "<Option B>",
    "C": "<Option C>",
    "D": "<Option D>"
  },
  "answer": "<A, B, C, or D>",
  "provenance": {
    "source_db": "BOW",
    "source_chapter": "<Select EXACTLY ONE chapter name from the list>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text>",
    "reasoning_chain": "<Explain why the correct option is right and why the distractors are geographically or ecologically incorrect based on the text>"
  }
}"""
    return system_prompt

def get_bird_comp_prompt():
    """
    Bird-Comp (形态识别与对比) 
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a high-level biological benchmark. Your task is to generate ONE highly accurate comparative reasoning question based strictly on the provided anonymized bird monograph.

The target bird's real names have been masked as "[the bird]". You MUST use "[the bird]" in your question to refer to the species.

**CRITICAL INSTRUCTION - QUESTION TYPE:**
The specific type of question you must generate today is: [{type}]. 
You must strictly follow the rule for this specific type:

1. If [{type}] is "Similar Species ID":
   - Identify a "Similar Species" or "Distractor Species" mentioned in the "Identification" section.
   - Ask how [the bird] can be distinguished from that specific species in terms of morphology, size, or behavior.
2. If [{type}] is "Subspecies Variation":
   - Identify the "nominate race" and at least one other named "subspecies" mentioned in the text.
   - Ask for the specific differences (e.g., plumage shade, markings, size) between them.
3. If [{type}] is "Sister Taxa":
   - Identify the closest phylogenetic relatives or "Sister Species" mentioned in the "Systematics History".
   - Ask to summarize their taxonomic relationship and the major physical distinctions between them.

*(Note: If the text lacks a specific distractor or subspecies to compare, fallback to a general morphological description question focusing on unique diagnostic features that separate [the bird] from its genus).*

**Allowed Source Chapters (You MUST select ONE of these exact strings for 'source_chapter'):**
[Identification, Subspecies, Systematics History, Introduction]

**Strict Rules:**
1. The question must require the model to perform a detailed comparison.
2. The `answer` must be a high-quality analytical text (a few detailed sentences) based ONLY on the provided text. Do not provide multiple-choice options.
3. DO NOT use any external knowledge. If the text says the bird is "smaller than X", do not add that it has "yellower wings" unless the text says so.
4. The `exact_quote` MUST be a COMPLETE, intact sentence (or multiple sentences) containing the comparison logic.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{{
  "knowledge_domain": "Morphology and Identification",
  "type": "{type}",
  "question": "<The comparative question text using '[the bird]'>",
  "answer": "<A detailed analytical text summarizing the key differences/relationships>",
  "provenance": {{
    "source_db": "BOW",
    "source_chapter": "<Select EXACTLY ONE chapter name from the list>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text>",
    "reasoning_chain": "<Explain the logic used to derive the comparison from the quote>"
  }}
}}"""
    return system_prompt

def get_bird_life_prompt():
    """
    Bird-Life (生活史与繁殖) 
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a high-level biological benchmark. Your task is to generate ONE highly accurate analytical question regarding the reproductive life cycle of the bird, based strictly on the provided anonymized monograph.

The target bird's real names have been masked as "[the bird]". You MUST use "[the bird]" in your question to refer to the species.

**CRITICAL INSTRUCTION - QUESTION TYPE:**
The specific type of question you must generate today is: [{type}]. 
You must strictly follow the focus area for this specific type:

1. If [{type}] is "Courtship & Mating":
   - Focus on sexual behaviors: visual displays, vocalizations during pairing, mating systems (polygamy, monogamy), and courtship feeding.
2. If [{type}] is "Phenology":
   - Focus on the timeline: specific breeding seasons, peak months for egg-laying, and how they relate to environmental factors if mentioned.
3. If [{type}] is "Nest Ecology":
   - Focus on the nest: site selection (e.g., ground, canopy), construction materials, and the physical structure of the nest.
4. If [{type}] is "Development":
   - Focus on numerical metrics: clutch size (number of eggs), incubation period (days), and fledging period (days). This MUST include specific numbers.
5. If [{type}] is "Parental Care":
   - Focus on the division of labor: which sex builds the nest, incubates the eggs, or feeds the young. Mention nest defense if applicable.
6. If [{type}] is "Life Cycle Synthesis":
   - Provide a comprehensive narrative question covering the entire process from courtship displays through to the independence of the young.

**Allowed Source Chapters (You MUST select ONE or BOTH of these exact strings for 'source_chapter'):**
[Behavior, Breeding]

**Strict Rules:**
1. The `answer` must be a high-quality, comprehensive analytical text. It should include specific action descriptions, numerical indicators, and logical relationships (e.g., "After an incubation period of X days...").
2. DO NOT use any external knowledge. All data (especially numbers) must come from the provided text.
3. The `exact_quote` MUST be a COMPLETE, intact sentence (or sentences) that supports the answer.
4. Numerical Accuracy: For "Development" types, ensure the numbers in the answer exactly match the text.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{{
  "knowledge_domain": "Ecology and Life History",
  "type": "{type}",
  "question": "<The analytical question text using '[the bird]'>",
  "answer": "<A comprehensive narrative or analytical text providing accurate actions, metrics, and logic>",
  "provenance": {{
    "source_db": "BOW",
    "source_chapter": "<Select 'Behavior', 'Breeding', or 'Behavior and Breeding'>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text>",
    "reasoning_chain": "<Briefly explain the chronological or numerical logic behind the answer>"
  }}
}}"""
    return system_prompt

def get_bird_con_prompt():
    """
    Bird-Con (保护现状与管理) 
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a high-level biological benchmark. Your task is to generate ONE highly accurate question evaluating conservation knowledge based strictly on the provided anonymized bird monograph.

The target bird's real names have been masked as "[the bird]". You MUST use "[the bird]" in your question to refer to the species.

**CRITICAL INSTRUCTION - QUESTION TYPE:**
The specific type of question you must generate today is: [{type}]. 
You must strictly follow the focus area for this specific type:

1. If [{type}] is "Status & Trend":
   - Focus on the current official IUCN conservation status (e.g., Vulnerable, Critically Endangered) and the overall population trend (e.g., decreasing, stable, increasing).
2. If [{type}] is "Threat Analysis":
   - Identify specific anthropogenic or environmental threats (e.g., habitat fragmentation, invasive predators, climate change, pollution). 
   - The question should ask for a summary of these core threat factors.
3. If [{type}] is "Historical & Extinction":
   - Focus on historical population collapses, range contractions, or (if applicable) last sighted dates and events that triggered a decline for EX (Extinct) or EW (Extinct in the Wild) species.

=========================================
[KNOWLEDGE GRAPH TRUTH (YOUR ANCHOR)]
{kg_context}

**Rule:** You MUST anchor your question on the core threats or conservation status mentioned in the Knowledge Graph Truth above. Do not invent questions about minor threats not present in this graph summary.
=========================================

**Allowed Source Chapters (You MUST select ONE or BOTH of these exact strings for 'source_chapter'):**
[Conservation and Management, Demography and Populations, Introduction]

**Strict Rules:**
1. The `answer` must be highly structured. For threats, provide a concise list of key points. For status, provide the exact IUCN grade.
2. DO NOT use any external knowledge. If the text does not mention a specific IUCN status, do not guess based on your training data.
3. The `exact_quote` MUST be a COMPLETE, intact sentence (or sentences) that provides the ground truth for the status or threats.
4. Avoid "leakage": Ensure no citation markers (e.g., Smith 2020) or visual references (e.g., Plate 4) appear in the output.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{{
  "knowledge_domain": "Conservation Status",
  "type": "{type}",
  "question": "<The question text regarding status, threats, or history using '[the bird]'>",
  "answer": "<For 'Status & Trend': State the Grade and Trend. For 'Threat Analysis': Provide a structured summary of key points.>",
  "provenance": {{
    "source_db": "BOW",
    "source_chapter": "<Select 'Conservation and Management', 'Demography and Populations', or both>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text>",
    "reasoning_chain": "<Briefly map the keywords in the answer to the evidence in the exact quote>"
  }}
}}"""
    return system_prompt

def get_bird_eco_prompt():
    """
    Bird-Eco (生态功能与食性) 
    """
    system_prompt = """You are an expert ornithologist and an ecological researcher. Your task is to generate ONE highly accurate analytical question evaluating ecological knowledge based strictly on the provided anonymized bird monograph.

The target bird's real names have been masked as "[the bird]". You MUST use "[the bird]" in your question to refer to the species.

**CRITICAL INSTRUCTION - QUESTION TYPE:**
The specific type of question you must generate today is: [{type}]. 
You must strictly follow the focus area for this specific type:

1. If [{type}] is "Dietary Niche":
   - Focus on categorizing its primary diet (e.g., insectivorous, frugivorous) and identifying specific prey taxonomy mentioned in the text.
2. If [{type}] is "Foraging Strategy":
   - Focus on the "Where" and "How": Identify the foraging strata (canopy, ground, etc.) and specific behavioral techniques (e.g., sally-gleaning, hovering).
3. If [{type}] is "Ecological Role":
   - Analyze interspecific interactions. How does [the bird]'s diet lead to roles like seed dispersal, pollination, or natural pest control?
4. If [{type}] is "Impact Analysis":
   - Evaluate the potential trophic cascade. If [the bird] were to disappear, what would be the logical ecological consequence (e.g., overpopulation of specific insects, failure of plant reproduction)?

**Allowed Source Chapters (You MUST select ONE or BOTH of these exact strings for 'source_chapter'):**
[Diet and Foraging, General Habitat, Introduction]

**Strict Rules:**
1. The `answer` must demonstrate high logicality. For "Impact Analysis", the reasoning should follow a clear A -> B -> C causal chain.
2. DO NOT use any external knowledge. All food items and habitat details must come from the text.
3. The `exact_quote` MUST be a COMPLETE, intact sentence (or sentences) describing the diet or foraging behavior.
4. Name Masking: Ensure no species names leak in the question or answer.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{{
  "knowledge_domain": "Ecological Function and Diet",
  "type": "{type}",
  "question": "<The question regarding niche, strategy, or ecological impact using '[the bird]'>",
  "answer": "<A high-quality analytical response explaining the dietary categorization or ecological consequences>",
  "provenance": {{
    "source_db": "BOW",
    "source_chapter": "<Select 'Diet and Foraging', 'General Habitat', or both>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text>",
    "reasoning_chain": "<Detail the logical step-by-step inference from the diet to the ecological role or impact>"
  }}
}}"""
    return system_prompt

def get_bird_reason_prompt():
    """
    Bird-Reason (高级推理与多跳分析) 
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a Level-3 expert biological reasoning benchmark. Your task is to generate ONE highly complex reasoning question based strictly on the provided deeply anonymized bird monograph.

The target bird's real names and related sister taxa have been masked as "[This Bird]" or "[The Species]". You MUST use "[This Bird]" in your question.

**CRITICAL INSTRUCTION - REASONING TYPE:**
The specific type of reasoning question you must generate today is: [{type}]. 
You must strictly apply the following logic based on the requested type:

1. If [{type}] is "Prediction" (Counterfactual Reasoning):
   - Design a hypothetical scenario altering a specific survival condition (e.g., habitat destruction, prey extinction, climate shift). 
   - Ask to predict the ecological or behavioral consequence for [This Bird] based on its specific traits in the text. Use keywords like "Hypothetically...", "Predict the consequence...".
2. If [{type}] is "Attribution" (Abductive Reasoning):
   - Highlight an unusual physiological trait, behavioral anomaly, or specific distributional constraint from the text. 
   - Ask the model to deduce the most likely biological/evolutionary cause for this anomaly. Use keywords like "What is the most likely biological cause...".
3. If [{type}] is "Correction" (Fallacy Verification) - **SPECIAL INJECTION REQUIRED**:
   - Step 1: Select a key true fact from the text.
   - Step 2: Actively mutate it into a biological falsehood, logical inversion, or ecological role reversal.
   - Step 3: Present this mutated false statement as a claim in the question, and ask to identify the physiological/ecological error and correct it based on the text.
4. If [{type}] is "Multi-hop" (Relational Chaining):
   - Select at least two separate, non-adjacent facts from the text (e.g., wing morphology + specific diet).
   - Require the answer to connect these facts to derive a third hidden conclusion (e.g., migration capability or ecosystem service). 
5. If [{type}] is "Synthesis" (Holistic Profiling):
   - Ask a macro-level question that cannot be answered by a single paragraph. It must require synthesizing scattered information to construct a unified model of the bird's survival strategy.

**Strict Rules for Chain-of-Thought (CoT):**
1. The `reasoning_chain` MUST be explicitly structured with numbered steps (Step 1, Step 2, etc.).
2. The CoT must combine the provided text evidence with fundamental biological axioms, physical laws, or ecological rules to form a complete causal chain.
3. DO NOT use external factual knowledge about the specific bird, but YOU MUST apply general biological principles to connect the dots.

**Allowed Source Chapters:**
[Full Text Synthesis]

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{{
  "knowledge_domain": "Advanced Biological Reasoning",
  "type": "{type}",
  "question": "<The highly complex reasoning question using '[This Bird]'>",
  "answer": "<The comprehensive reference answer resolving the problem>",
  "provenance": {{
    "source_db": "BOW",
    "source_chapter": "Full Text Synthesis",
    "exact_quote": "<Copy the 1-3 distinct sentences from the text that serve as the fundamental evidence anchors>",
    "reasoning_chain": "<Explicit CoT: Step 1: [Identify evidence] -> Step 2: [Apply biological axiom] -> Step 3: [Derive conclusion]>"
  }}
}}"""
    return system_prompt

def get_bird_id_prompt():
    """
    Bird-ID (物种精准识别与诊断) 
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a Level-3 expert biological reasoning benchmark. Your task is to generate a challenging "Blind Identification" question based strictly on the provided bird monograph.

The target bird's real names (common and scientific), as well as its taxonomic family/order, must be strictly masked as "[The Bird]", "[Species]", "[Genus]", etc.

**CRITICAL INSTRUCTION - QUESTION TYPE:**
The specific type of identification question you must generate today is: [{type}]. 
You must strictly follow the focus area for this specific type to synthesize a "clue_text":

1. If [{type}] is "Morphological Diagnosis":
   - Focus on holistic plumage patterns and bare part specifics (e.g., bill/eye/leg coloration). 
   - If the text mentions closely related species, include them in the clue as masked distractors (e.g., "Unlike [Similar Species] which has red eyes, [The Bird] has yellow eyes").
2. If [{type}] is "Behavioral Fingerprint":
   - Focus on display mechanics, unique action sequences, specialized locomotion, or feeding habits.
3. If [{type}] is "Acoustic & Phenological ID":
   - Focus on vocal signatures (sound structures, frequencies, onomatopoeia), typically heard during specific seasonal or micro-habitat contexts.
4. If [{type}] is "Sex & Age Diagnosis":
   - Focus on identifying non-adult or non-male plumages in sexually dimorphic species. 
   - Provide a clue describing the female, juvenile, or specific molting stage, explicitly asking the test-taker to identify the species AND the specific sex/age described.

**Strict Anti-Leakage & Diagnostic Rules:**
1. **Geographic Blurring**: You MUST blur specific political borders, exact continents, or highly recognizable landmarks. Replace them with generic habitat descriptions (e.g., replace "Andes in Peru" with "high-altitude tropical mountain ranges"; replace "Madagascar" with "a large isolated tropical island").
2. **Diagnostic Sufficiency**: The `clue_text` MUST contain highly specific diagnostic feature words (measurements, specific colors, unique behaviors) from the text. It cannot be a generic description that applies to 100 different birds.
3. **DO NOT** output any citation markers (e.g., Smith 2020) or visual references (e.g., Fig 1, Plate 3).

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{{
  "knowledge_domain": "Species Identification",
  "type": "{type}",
  "clue_text": "<Synthesize a dense, deeply anonymized, geographically blurred paragraph containing the core diagnostic features>",
  "question": "<The instruction asking to identify the specific bird (and sex/age if applicable) based on the clue_text>",
  "answer": "<Provide the UNMASKED Common Name and Scientific Name of the target bird as the gold standard answer>",
  "provenance": {{
    "source_db": "BOW",
    "source_chapter": "<Select the primary chapter you extracted the features from>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text that form the basis of the clue>",
    "reasoning_chain": "<Briefly explain why these specific features are diagnostically unique enough to identify this exact species>"
  }}
}}"""
    return system_prompt

def get_bird_plan_prompt():
    """
    Bird-Plan (保护干预规划) 的专属 System Prompt
    """
    system_prompt = """You are an expert conservation biologist and an exam designer for a Level-3 expert reasoning benchmark. Your task is to generate ONE highly challenging Conservation Planning question based strictly on the provided anonymized bird monograph.

The target bird's real names have been masked as "[Target Species]". You MUST use "[Target Species]" in your question to refer to the species.

**CRITICAL INSTRUCTION - QUESTION TYPE (TRACK):**
The specific conservation track you must generate today is: [{type}]. 
You must strictly follow the logic for this track to formulate a scenario and a specific constraint:

1. If [{type}] is "Predator Control":
   - Identify a severe predation or invasive species threat from the text.
   - Apply ONE of these constraints in the question: "Inaccessible steep terrain", "Strict legal ban on poisons/rodenticides", or "Severe budget cut preventing fence construction".
2. If [{type}] is "Habitat Rescue":
   - Identify a severe habitat loss, fragmentation, or climate threat from the text.
   - Apply ONE of these constraints in the question: "90% of land is privately owned", "Habitat restoration takes 20 years but the bird will go extinct in 5 years", or "The lowland habitat will inevitably be submerged by sea-level rise".
3. If [{type}] is "Population Intervention":
   - Identify a severe demographic threat (e.g., inbreeding, hunting, tiny population) from the text.
   - Apply ONE of these constraints in the question: "The species suffers from extreme capture stress/myopathy in captivity", "Local indigenous communities rely on this bird culturally/economically", or "The population is suffering from severe inbreeding depression at a single site".

**Allowed Source Chapters (You MUST select ONE or more of these exact strings for 'source_chapter'):**
[Conservation and Management, Breeding, General Habitat]

**Strict Rules for the Question & Answer:**
1. The `question` must explicitly state the core threat found in the text and the chosen severe constraint, asking the model to draft a specific conservation plan.
2. The `answer` MUST NOT be a generic essay. It must be a highly structured "Gold Standard Rubric" designed for an LLM-as-a-Judge evaluator, explicitly addressing three dimensions:
   - [Threat Priority]: What is the #1 deadliest threat to tackle first based on the text?
   - [Constraint Satisfaction]: What specific method must be used (or avoided) to satisfy the injected constraint?
   - [Biological Specificity]: What unique biological trait of [Target Species] (e.g., cavity-nesting, specific diet, flightless) MUST be utilized or accounted for in the plan?
3. DO NOT use external knowledge. The biological traits must come from the text.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{{
  "knowledge_domain": "Conservation Planning",
  "type": "{type}",
  "constraint_applied": "<Briefly state the specific constraint you selected>",
  "question": "<The scenario question detailing the situation, the constraint, and asking for a conservation plan>",
  "answer": "<The highly structured Gold Standard Rubric covering [Threat Priority], [Constraint Satisfaction], and [Biological Specificity]>",
  "provenance": {{
    "source_db": "BOW",
    "source_chapter": "<Select the relevant chapters used>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text detailing the threat and biological traits>",
    "reasoning_chain": "<Explain how the gold standard answer effectively combines the biological traits with the applied constraint>"
  }}
}}"""
    return system_prompt

    """
    Bird-Plan (保护干预规划) 的专属 System Prompt
    """
    system_prompt = """You are an expert conservation biologist and an exam designer for a Level-3 expert reasoning benchmark. Your task is to generate ONE highly challenging Conservation Planning question based strictly on the provided anonymized bird monograph.

The target bird's real names have been masked as "[Target Species]". You MUST use "[Target Species]" in your question to refer to the species.

**CRITICAL INSTRUCTION - QUESTION TYPE (TRACK):**
The specific conservation track you must generate today is: [{type}]. 
You must strictly follow the logic for this track to formulate a scenario and a specific constraint:

1. If [{type}] is "Predator Control":
   - Identify a severe predation or invasive species threat from the text.
   - Apply ONE of these constraints in the question: "Inaccessible steep terrain", "Strict legal ban on poisons/rodenticides", or "Severe budget cut preventing fence construction".
2. If [{type}] is "Habitat Rescue":
   - Identify a severe habitat loss, fragmentation, or climate threat from the text.
   - Apply ONE of these constraints in the question: "90% of land is privately owned", "Habitat restoration takes 20 years but the bird will go extinct in 5 years", or "The lowland habitat will inevitably be submerged by sea-level rise".
3. If [{type}] is "Population Intervention":
   - Identify a severe demographic threat (e.g., inbreeding, hunting, tiny population) from the text.
   - Apply ONE of these constraints in the question: "The species suffers from extreme capture stress/myopathy in captivity", "Local indigenous communities rely on this bird culturally/economically", or "The population is suffering from severe inbreeding depression at a single site".

**Allowed Source Chapters (You MUST select ONE or more of these exact strings for 'source_chapter'):**
[Conservation and Management, Breeding, General Habitat]

**Strict Rules for the Question & Answer:**
1. The `question` must explicitly state the core threat found in the text and the chosen severe constraint, asking the model to draft a specific conservation plan.
2. The `answer` MUST NOT be a generic essay. It must be a highly structured "Gold Standard Rubric" designed for an LLM-as-a-Judge evaluator, explicitly addressing three dimensions:
   - [Threat Priority]: What is the #1 deadliest threat to tackle first based on the text?
   - [Constraint Satisfaction]: What specific method must be used (or avoided) to satisfy the injected constraint?
   - [Biological Specificity]: What unique biological trait of [Target Species] (e.g., cavity-nesting, specific diet, flightless) MUST be utilized or accounted for in the plan?
3. DO NOT use external knowledge. The biological traits must come from the text.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{{
  "knowledge_domain": "Conservation Planning",
  "type": "{type}",
  "constraint_applied": "<Briefly state the specific constraint you selected>",
  "question": "<The scenario question detailing the situation, the constraint, and asking for a conservation plan>",
  "answer": "<The highly structured Gold Standard Rubric covering [Threat Priority], [Constraint Satisfaction], and [Biological Specificity]>",
  "provenance": {{
    "source_db": "BOW",
    "source_chapter": "<Select the relevant chapters used>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text detailing the threat and biological traits>",
    "reasoning_chain": "<Explain how the gold standard answer effectively combines the biological traits with the applied constraint>"
  }}
}}"""
    return system_prompt

def get_bird_classify_prompt():
    """
    Bird-Classify (科/目级分类与特征推理) 
    """
    system_prompt = """You are an expert ornithologist and taxonomist designing a high-level biological benchmark. Your task is to generate ONE highly accurate question evaluating taxonomic classification and family/order-level traits based strictly on the provided monograph text.

**CRITICAL INSTRUCTION - QUESTION TYPE (TYPE A vs TYPE B):**
The specific type of question you must generate today is: [{type}]. 
You must strictly follow the distinct logic and masking rules for this specific type:

**[TYPE A - Blind Identification]**
1. If [{type}] is "Feature-to-Family":
   - **Masking Rule:** You MUST strictly mask the actual Order and Family names in the question/clue as "[Order]" and "[Family]".
   - **Question Generation:** Synthesize a detailed descriptive clue based on the unique anatomical features (bill/feet shape), typical behavioral patterns, or habitat mentioned in the text. Then ask the test-taker to identify BOTH the taxonomic Order and Family based on this description.
   - **Answer Format:** The `answer` MUST be strictly formatted as: "Order: <Unmasked Order Name> | Family: <Unmasked Family Name>". (This is critical for partial-credit scoring).

**[TYPE B - Feature Summarization]**
2. If [{type}] is "Taxon-to-Feature":
   - **Masking Rule:** Do NOT mask the target Family name. Use the actual unmasked Family name in your question.
   - **Question Generation:** Ask the test-taker to summarize the key characteristics of the specific family (e.g., "[Actual Family Name]"), focusing on their morphological overview, typical habitat, diet, or breeding strategies based on the text.
   - **Answer Format:** A structured, analytical summary of the key features.
3. If [{type}] is "Taxonomic Hierarchy":
   - **Masking Rule:** Do NOT mask the target Family name.
   - **Question Generation:** Ask the test-taker to identify which taxonomic Order the family "[Actual Family Name]" belongs to, AND to briefly describe the defining traits of this Order based on the text.
   - **Answer Format:** State the exact Order name followed by a structured summary of its defining traits.

**Allowed Source Chapters:**
[Introduction, General Habitat, Diet and Foraging, Breeding, Conservation Status, Systematics History]

**Strict Rules:**
1. DO NOT use external knowledge. All features and hierarchical relationships must come from the provided text.
2. The `exact_quote` MUST be a COMPLETE, intact sentence (or multiple sentences) that provides the ground truth for the features or taxonomic relationship. 
3. Avoid visual/citation leakage (e.g., remove "Fig. 1" or "Smith 2019" if they appear in your quotes).

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{{
  "knowledge_domain": "Taxonomy and Classification",
  "type": "{type}",
  "question": "<For Type A: The masked clue and question. For Type B: The direct question using the unmasked Family name.>",
  "answer": "<For Type A: 'Order: X | Family: Y'. For Type B: A highly structured summary.>",
  "provenance": {{
    "source_db": "BOW",
    "source_chapter": "<Select the relevant chapter(s)>",
    "exact_quote": "<Copy the complete, intact sentence(s) verbatim from the text>",
    "reasoning_chain": "<Briefly map the features or relationships in the answer to the provided quote>"
  }}
}}"""
    return system_prompt

def get_list_global_prompt():
    """
    List-Global (全库扫描与整合) 
    """
    system_prompt = """You are an expert ornithologist and an exam designer for a high-level biological benchmark. Your task is to generate ONE natural language question that requires retrieving a specific list of bird species from a global database, based on the provided conditions.

I will provide you with "Search Conditions" and a "Ground Truth Species List". 
Your job is to translate the "Search Conditions" into a challenging, natural-sounding academic exam question, and return the exact Ground Truth Species List as the answer.

**CRITICAL INSTRUCTION - QUESTION TYPE:**
The specific track you must generate today is: [{type}].

1. If [{type}] is "Conservation & Distribution":
   - Formulate a question asking to list all species that match the provided IUCN Status and Biogeographic Realm / Island Endemism.
2. If [{type}] is "Ecological Traits":
   - Formulate a question asking to list all species matching the provided Primary Diet and Primary Habitat.
3. If [{type}] is "Life History & Nesting":
   - Formulate a question asking to list all species matching the provided Nest Type and Migratory Status.
4. If [{type}] is "Extreme Values":
   - Formulate a question asking to list the top N species based on the provided extreme condition (e.g., heaviest/lightest body mass).

**Strict Rules:**
1. The `question` must sound natural, academic, and clear. Use phrases like "Enlist all the species that...", "List all bird species that...", or "Please enlist all...".
2. The `answer` MUST be an exact copy of the provided "Ground Truth Species List", formatted as a JSON array of strings. DO NOT add, modify, or remove any species.
3. Do NOT include the total count of species in the question itself (unless it's an Extreme Values question explicitly asking for "Top 10", "Top 20", etc.). The test-taking AI must figure out the total number on its own.

**Output JSON Schema:**
Return ONLY a valid JSON object matching this exact structure:
{{
  "knowledge_domain": "Global Avian Traits",
  "type": "{type}",
  "question": "<The natural language question based on the Search Conditions>",
  "answer": ["<Species 1>", "<Species 2>", "...copy the EXACT list provided>"],
  "provenance": {{
    "source_db": "BIRDBASE",
    "search_conditions": "<Copy the exact Search Conditions provided to you>"
  }}
}}"""
    return system_prompt