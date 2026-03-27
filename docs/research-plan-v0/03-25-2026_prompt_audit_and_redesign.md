# Attic Prompt Audit & Production Redesign

**Date**: 2026-03-25
**Scope**: All prompts across production app (`gemini.py`, `prompts.py`, `ontology.py`) and workbench experiment (`vision_v2_experiment.py`)
**Context**: Day 2 experiment scored 21% wow rate (10/47 items ≥14/18). Target: 75%+.

---

## Part I: Audit of Current Prompts

### 1. Production `gemini.py:classify()` — Rating: 3/10

**Current prompt (reconstructed):**

```
## Classification Ontology (Tier-1 Labels)

**Affect**: funny, wholesome, sad, angry, nostalgic, inspiring, cringe, satisfying, scary, relaxing, shocking, neutral
**Topic**: food, fashion, beauty, fitness, travel, music, ...
[...all 8 facets listed with no definitions...]

For each facet, pick exactly one tier-1 label.
You may also suggest micro-labels (tier-2) for nuance.
Return JSON with facet names as keys, each containing: "label" (tier-1), "micro_labels" (list), "confidence" (0-1).

## Content to Classify

Caption: [caption]
Transcript: [subtitle]
Hashtags: [hashtags]
Creator: @[username]
Music: [music_name]

Classify this TikTok content. Return ONLY valid JSON, no markdown fences.
```

**Problems:**

1. **No label definitions.** The model has no idea what "education" means in Attic's ontology vs. its own pre-training definition. Everything becomes "education" or "fitness" because these are broad, safe categories.
2. **No negative examples.** No guidance on what each label does NOT include. This is why "inspiring" gets assigned to 45-53% of content — it's the safest positive-affect label.
3. **No disambiguation rules.** When a TikTok about grilled cheese has a music track tagged "gym vibes," nothing tells the model to prioritize visual/caption content over music metadata for topic classification.
4. **No role framing.** The model doesn't know this classification drives a personal search/browse system. It classifies like a generic content tagger, not like a user organizing their saved collection.
5. **Text-only input.** No visual signal at all. Caption + hashtags + music metadata is insufficient for 40%+ of TikTok content where meaning lives in pixels.
6. **Single-label forced choice.** Forces one affect label when most content blends 2-3 emotional tones.

**Empirical damage:** 53% of items classified as "fitness" by text-only, 84% of those are wrong. 45% classified as "inspiring" by vision, majority are actually informative/neutral.

---

### 2. Production `gemini.py:analyze_visual()` — Rating: 5/10

**Current prompt (GENERAL focus):**

```
Analyze this TikTok thumbnail/image. Provide:
1. A brief description of what's shown
2. Key objects, people, or products visible
3. Any text detected in the image (OCR)

Return JSON with keys: description (str), objects (list of str), text_detected (str or null).
Return ONLY valid JSON, no markdown fences.
```

**Strengths:**

- VisionFocus enum (GENERAL, BOOKS, SCENES, PLACES, TEXT, PRODUCTS) is architecturally sound — specialized prompts per entity type is the right idea
- Google Search grounding enabled via `"tools": [{"googleSearch": {}}]`
- Clean Result-style dataclass return pattern

**Problems:**

1. **Thumbnail-only.** One image for a 60-second video or 10-slide carousel. Experiment proved this is insufficient.
2. **Prompts too short.** GENERAL is 4 lines. Compare to workbench VIDEO_PERCEPTION_PROMPT at 45 lines. Production prompts are at ~20% of needed detail.
3. **Output schema too simple.** `description`, `objects`, `text_detected` — no entity types, no confidence levels, no source attribution, no structured extraction.
4. **No context passing.** The caption is optionally prepended, but no other metadata (hashtags, comments, music, subtitles) is available to ground the visual analysis.

---

### 3. Production `prompts.py` (Agent System Prompt) — Rating: 7/10

**Strengths:**

- 5 query plan templates (entity retrieval, creator aggregation, simple filter, interpretive/vibe, ambiguous/broad) — well-structured, actionable
- Recall check instruction — smart ("analyze_visual on low-text items after entity searches")
- Cost awareness rules — practical ("prefer cheap tools first, limit vision calls")
- Disambiguation rules — reasonable defaults
- Formatting guidelines — clear

**Problems:**

1. **Assumes correct cached classifications.** "When query_items returns results with cached classifications, use that data" — but cached classifications are wrong 50%+ of the time for text-only classified items.
2. **Entity retrieval plan assumes entities exist.** "resolve_entity for each match that mentions a specific entity name" — but the current pipeline barely extracts entities at all.
3. **No awareness of data quality tiers.** The agent doesn't know which items have been fully processed (vision + entity extraction) vs. only text-processed. It treats all results as equally reliable.
4. **No instruction to use comments.** Comments are stored but the agent has no guidance on using them for context, cultural interpretation, or entity identification.

---

### 4. Workbench `VIDEO_PERCEPTION_PROMPT` — Rating: 7/10

**Strengths:**

- Detailed JSON schema with scene_timeline, entities, presentation_style, audio_profile
- Explicit critical instructions ("Name every identifiable person, place, product")
- VISIBLE/INFERRED distinction
- Specific entity types listed
- Verbatim transcription instruction

**Problems:**

1. **No token budget or priority ordering.** Long videos exhaust 8192 tokens with verbose scene descriptions, leaving no room for entities. 5 items (11%) had truncation parse errors.
2. **Contradictory framing.** "Do not classify or judge" conflicts with `topic_hints`, `affect_hints`, `genre_hints` fields which are classification-adjacent.
3. **No guidance on comments.** Comments are in the context but the prompt never says "use comments to identify entities, cultural references, or meme context."
4. **No audio identification guidance.** Doesn't say "identify the actual song playing, which may differ from the TikTok audio metadata."
5. **No output length management.** No instruction to be concise on scene descriptions and prioritize entity extraction.

---

### 5. Workbench `build_slideshow_prompt()` — Rating: 6/10

**Strengths:**

- Has `per_image` in JSON schema
- Different prompt for single image vs. carousel
- Entity extraction in schema

**Problems:**

1. **"Analyze each image carefully" is too vague.** 7/19 slideshow items got dinged for missing per-slide breakdowns. The model summarizes instead of extracting per-slide.
2. **No structured content extraction.** No instruction to extract recipes, product specs, rankings, or other list-type content that carousels typically contain.
3. **No guidance on common carousel types.** Restaurant recs, product lists, outfit ideas, song rankings — each needs different extraction.

---

### 6. Workbench Classification Prompts — Rating: 4/10

Same fundamental problem as production classify: ontology labels listed without definitions, examples, or disambiguation. The `build_ontology()` function produces:

```
**topic** — pick exactly ONE:
  food, fashion, beauty, fitness, ...

INSTRUCTIONS:
- For each facet, select the single best tier-1 label.
- Suggest 1-3 "micro_labels" for nuance.
- Confidence: 0.0-1.0.
- If content fits multiple labels, pick dominant one.
```

No definitions. No negative examples. No guidance on the 10+ known confusion cases from the eval.

---

### 7. `ontology.py` Label Set — Rating: 6/10

**Strengths:**

- 8 orthogonal facets covering content from multiple angles
- Two-tier system (fixed tier-1 + free-form tier-2) is architecturally sound
- Validation function handles edge cases well (case normalization, fallbacks)

**Problems:**

1. **Affect is missing "informative/practical."** This is the most common actual affect for saved TikToks but has no label. Model defaults to "inspiring" or "neutral."
2. **"Education" topic is too broad.** Chemistry experiments, career advice, coding tutorials, and general life tips all get lumped together.
3. **Genre is missing TikTok-native formats.** "POV", "transition", "edit/fan edit", "room tour", "outfit showcase", "ranking/list" are extremely common but not in the label set.
4. **No multi-label support for affect.** Forced single-label when most content blends emotions.
5. **No "funny" distinction between intentional comedy and ironic/meme humor.** Model misclassifies cultural irony and meme humor.

---

## Part II: The Meta-Pattern Missing Across All Prompts

Looking across all prompts, the biggest structural gap: **none of them tell the model WHY it's extracting this information or HOW the output will be used.**

Production-grade prompts from companies doing multimodal content understanding always include use-case framing:

```
You are processing TikTok content for a personal library system. Your output
will be used for:
1. SEARCH: Users will query "what was that grilled cheese recipe?" — your
   entities must contain "grilled cheese recipe" as a findable term.
2. BROWSE: Users will filter by topic/genre/affect labels to browse their
   collection. Labels must be useful for filtering, not just technically correct.
3. AGGREGATE: Labels power stats like "your top topics this month."
4. EXTERNAL: Entity search_query fields will be sent to Spotify, Google Maps,
   and Amazon APIs for direct linking.

Optimize your output for these use cases.
```

This single framing paragraph would prevent half the eval issues. The model would stop extracting "Reebok" (background brand, no one searches for this) and start extracting "Heaven Knows I'm Miserable Now — The Smiths" (the thing someone actually searches for).

---

## Part III: Redesigned 4-Pass Pipeline Prompts

### Architecture Overview

| Pass                 | Input                                                                               | Output                                                     | Model        | Est. Cost    |
| -------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------------- | ------------ | ------------ |
| 1. Perception        | Video/images + all metadata + subtitles + comments                                  | Scene timeline, summary, audio profile, style, mood, hints | Gemini Flash | $0.005/item  |
| 2. Entity Extraction | Perception text + keyframes/images + all metadata (Google Search grounding enabled) | Structured entities with relevance, source, search queries | Gemini Flash | $0.004/item  |
| 3. Classification    | Perception summary + entities + all metadata (text-only)                            | Multi-label affect, topic, genre, style, provenance        | Gemini Flash | $0.001/item  |
| 4. Embedding         | Caption + summary + entities + thesis + classification labels                       | 1536-dim vector                                            | OpenAI       | $0.0002/item |

---

### Pass 1: Perception Prompt

#### Video Perception

```
ROLE: You are a precise content analyst for a personal media library. Your
perception report will be used downstream for entity extraction, classification,
and user search. Accuracy and completeness directly affect whether users can
find their saved content later.

CONTEXT (metadata from the post):
{context}

Watch the video carefully and return JSON with the following structure.

OUTPUT PRIORITY (allocate output tokens in this order):
1. Entities detected (30%) — most valuable. Be exhaustive.
2. Overall summary (15%) — 3-5 sentences: what, who, why, what's the point.
3. Scene timeline (25%) — major scenes only, 1-2 sentences each. Do NOT
   describe every hand movement or camera shift.
4. Audio profile (10%) — identify the ACTUAL song/audio playing, which may
   differ from TikTok metadata. Format: "Song Title — Artist".
5. Presentation style + mood (10%)
6. Classification hints (10%) — soft signals only.

If approaching output limits, TRUNCATE scene descriptions first. Never
truncate entity extraction.

{{
  "scene_timeline": [
    {{
      "time_range": "0:00-0:XX",
      "visual_description": "what is happening — semantic meaning, not literal
        movements. 'Creator demonstrates cable lateral raise technique' NOT
        'person lifts arm to the side'",
      "audio_description": "what is said or heard — transcribe key points, not
        every word",
      "text_on_screen": "transcribe ALL overlaid text verbatim",
      "key_objects": ["identifiable objects, products, brands in this segment"]
    }}
  ],
  "overall_summary": "3-5 sentence description: what is this video about, what
    happens, and what is the main point or takeaway? A user who saved this video
    should be able to identify it from this summary alone.",
  "people": [
    {{
      "description": "appearance, role, what they're doing",
      "is_creator": true,
      "speaking": true,
      "identified_as": "name if recognizable, null otherwise"
    }}
  ],
  "entities_detected": [
    {{
      "name": "specific name — never generic descriptions",
      "type": "person|place|product|brand|song|artist|book|movie|tv_show|app|
        restaurant|website|exercise|recipe|clothing|technique",
      "how_identified": "visual|audio|text_overlay|metadata|comments|inferred",
      "confidence": "high|medium|low"
    }}
  ],
  "presentation_style": {{
    "primary_format": "talking_head|voiceover|text_overlay|cinematic|
      tutorial_demo|skit|compilation|reaction|slideshow|before_after|pov|
      room_tour|outfit_showcase|edit|other",
    "camera_work": "static|handheld|panning|transitions|split_screen|
      overhead|selfie",
    "editing_style": "minimal|jump_cuts|heavy_effects|before_after|montage|
      slow_motion"
  }},
  "audio_profile": {{
    "speech": true,
    "speech_summary": "brief summary of what is said",
    "music": "none|background|featured|music_video",
    "music_identified": "ACTUAL song and artist if identifiable from audio
      (may differ from metadata). Format: 'Song Title — Artist'",
    "sound_effects": false
  }},
  "visual_mood": "emotional atmosphere: lighting, pacing, tone, energy level",
  "topic_hints": ["2-3 topic areas this content addresses"],
  "affect_hints": ["emotional tones present — how would a viewer FEEL?"],
  "genre_hints": ["content format — what KIND of TikTok is this?"]
}}

CRITICAL INSTRUCTIONS:
- Be SPECIFIC. Name every identifiable person, place, product, song, show, brand.
- AUDIO: Identify the actual song playing from the audio, not just metadata.
  TikTok audio metadata frequently does not match the actual audio. If you hear
  a different song than what metadata says, report what you HEAR.
- COMMENTS: The top comments often explain jokes, identify songs/places/products,
  or provide cultural context the video alone doesn't convey. Use them as a
  primary signal for entity identification and cultural references.
- TEXT ON SCREEN: Transcribe ALL overlaid text, including recipe steps, product
  specs, prices, dimensions, instructions.
- CELEBRITIES: If you recognize a person, NAME them. "Kai Cenat" not "another
  person at the table."
- CULTURAL CONTEXT: If this appears to be a meme, trend, or viral format, note
  it. If comments suggest cultural context you wouldn't otherwise know, include it.
- PRECISION: "Tony Soprano from The Sopranos" not "a man who appears to be a
  character."
- SCENE EFFICIENCY: Keep scene descriptions to 1-2 sentences of semantic
  meaning. "Creator explains why cable lateral raises are better than dumbbell
  for shoulder isolation" is better than "man stands next to cable machine,
  grips handle, pulls arm upward while speaking to camera."
```

#### Slideshow/Image Perception

```
ROLE: You are a precise content analyst for a personal media library. This is
a TikTok {media_desc}. Your per-image extraction will be used for entity
search, classification, and external API lookups (Spotify, Google Maps, Amazon).

CONTEXT (metadata from the post):
{context}

Analyze {image_instruction} and return JSON.

MANDATORY: You MUST output one entry in "per_image" for EVERY image provided.
If there are 8 images, there must be exactly 8 entries. No exceptions. Do not
summarize multiple images into one entry. Do not skip any image.

{{
  "per_image": [
    {{
      "image_number": 1,
      "description": "what this specific image shows — be precise",
      "text_detected": "transcribe ALL readable text EXACTLY as written,
        including brand names, specs, dimensions, prices, model numbers",
      "primary_content": "what this slide represents if part of a list
        (e.g., 'Restaurant: Kasama, Filipino bakery, West Town')",
      "entities": [
        {{
          "name": "specific name",
          "type": "person|place|product|brand|song|artist|book|movie|tv_show|
            app|restaurant|clothing|exercise",
          "specifications": "any dimensions, specs, model numbers, sizes visible"
        }}
      ]
    }}
  ],
  "overall_summary": "3-5 sentences: what is this post about? What is the
    user likely saving it for?",
  "carousel_type": "recommendation_list|product_showcase|ranking|outfit_layout|
    recipe_steps|infographic|meme|screenshot|photo_dump|room_tour|
    text_cards|other",
  "narrative_thread": "what story, message, or recommendation do these images
    convey as a set?",
  "entities_detected": [
    {{
      "name": "specific name",
      "type": "person|place|product|brand|song|artist|book|movie|tv_show|app|
        restaurant|website|clothing|technique",
      "how_identified": "visual|text_overlay|metadata|comments|inferred",
      "slide_number": 1,
      "specifications": "dimensions, specs, model numbers if visible",
      "confidence": "high|medium|low"
    }}
  ],
  "presentation_style": {{
    "primary_format": "text_cards|photo_dump|product_showcase|infographic|
      meme|screenshot|recommendation_list|room_tour|outfit_layout|ranking|
      recipe_steps|other",
    "visual_style": "minimal|aesthetic|informational|meme|collage|professional"
  }},
  "visual_mood": "emotional atmosphere and aesthetic",
  "topic_hints": ["2-3 topic areas"],
  "affect_hints": ["how would a viewer FEEL looking at this?"],
  "genre_hints": ["what KIND of TikTok is this?"]
}}

CRITICAL INSTRUCTIONS:
- EVERY SLIDE MATTERS: For recommendation/list posts, each slide typically
  represents one item. Extract the specific item name, details, and any
  visible specifications PER SLIDE.

  Common carousel types and what to extract:
  * Restaurant recommendations → restaurant name, cuisine, location per slide
  * Product lists → product name, brand, model, specs, price per slide
  * Outfit showcases → clothing items, brands, sizes per slide
  * Song/album rankings → song title, artist per slide
  * Recipe steps → ingredients and instructions per slide
  * Tech setups → device name, brand, specs (RAM, storage, dimensions) per slide
  * Book lists → title, author per slide

- TEXT EXTRACTION IS CRITICAL: Transcribe ALL visible text in every image —
  menus, signs, labels, prices, dimensions ("60\"x30\""), specs ("1TB, 48GB RAM"),
  model numbers.
- Name every identifiable person, place, product, restaurant, brand, logo.
- COMMENTS provide crucial context for entity identification. Use them.
- Precision over hedging.
```

---

### Pass 2: Entity Extraction Prompt

```
ROLE: You are an entity extraction specialist for a personal media library.
Your entities will power:
1. USER SEARCH: "what was that standing desk?" → must find "UPLIFT Standing
   Desk 60x30"
2. EXTERNAL APIS: search_query fields will be sent to Spotify, Google Maps,
   Amazon, TMDB, Google Books for direct linking
3. CROSS-ITEM ANALYSIS: "what career advice themes keep coming up in my saves?"
4. STRUCTURED RECALL: "give me that grilled cheese recipe" → must return
   ingredients and steps

PERCEPTION ANALYSIS (from Stage 1):
{perception_summary}

METADATA:
Caption: {caption}
Hashtags: {hashtags}
Creator: @{creator} ({creator_display})
Music metadata: {music}
Duration: {duration}s
Engagement: {play_count} plays, {like_count} likes

Subtitle transcript: {subtitles}

Top comments:
{comments}

Extract ALL entities and return JSON:

{{
  "entities": [
    {{
      "name": "UPLIFT Standing Desk",
      "display_name": "UPLIFT Standing Desk 60\"x30\"",
      "type": "product",
      "subtype": "furniture",
      "relevance": "primary",
      "source": ["text_overlay", "voiceover"],
      "slide_number": null,
      "timestamp_range": null,
      "specifications": "60\" x 30\", standing desk",
      "search_query": "UPLIFT standing desk 60x30",
      "search_targets": ["amazon", "google_shopping"],
      "confidence": 0.95
    }}
  ],
  "takeaways": [
    {{
      "statement": "Cable lateral raises are superior to dumbbell for
        shoulder isolation because they maintain constant tension",
      "source": "voiceover",
      "confidence": 0.9
    }}
  ],
  "structured_content": {{
    "type": "recipe|workout|product_list|recommendation_list|ranking|
      instructions|null",
    "items": [
      {{
        "name": "item name",
        "details": "specs, ingredients, reps/sets, etc.",
        "slide_number": null
      }}
    ]
  }},
  "audio_identification": {{
    "actual_song": "Heaven Knows I'm Miserable Now — The Smiths",
    "metadata_song": "original sound — username",
    "match": false,
    "spotify_query": "Heaven Knows I'm Miserable Now The Smiths"
  }}
}}

ENTITY TYPES:
- person: Named individual (creator, celebrity, athlete, public figure)
- song: "Title — Artist" format for Spotify searchability
- artist: Music artist (separate from song for "all videos with The Smiths" queries)
- movie_or_show: Film, TV show, series
- book: Book title + author
- product: Specific product with specs (UPLIFT desk 60x30, MacBook M4 Pro 1TB/48GB)
- brand: Company or brand name
- place: Restaurant, venue, city, landmark (formatted for Google Maps)
- recipe: The dish being made (grilled cheese with tomato soup)
- ingredient: Recipe ingredients
- exercise: Specific workout movement with specs (cable lateral raise, 3x12)
- app_or_tool: Software, app, website (AlDente, FlipClock)
- clothing: Specific garment with brand (Nike ski mask, Logitech MX Master 3)
- takeaway: Core opinion, claim, or advice — the THESIS of the video
- technique: Method or approach being taught (backswing rotation, verbal fluency)
- trend_or_meme: Viral format, meme template, trend name
- cultural_reference: Non-meme cultural context

RELEVANCE TIERS:
- primary: This IS what the TikTok is about. The recipe being made, the main
  product reviewed, the person being discussed. If a user asks "what was that
  video about?", these entities are the answer.
- supporting: Mentioned meaningfully but not the focus. Recipe inspiration
  credit, secondary products, background song.
- background: Visible but incidental. Brand of shirt, stove manufacturer.
  Still capture — useful for niche queries ("what brands do my saved creators
  wear?") — but ranked lower.

CRITICAL RULES:
1. ALWAYS extract the TAKEAWAY/THESIS as an entity. "Real estate isn't the
   best wealth-building strategy" is an entity. "Make the first 45 minutes
   of work addicting with deep work blocks" is an entity.
2. AUDIO: Compare the actual audio (from perception) against TikTok metadata.
   If they differ, report both. Format the actual song as "Title — Artist"
   for Spotify searchability.
3. STRUCTURED CONTENT: If the video is a recipe, extract ingredients and steps.
   If it's a workout, extract exercises with reps/sets. If it's a product
   list, extract every product with specs. If it's a ranking, extract the
   ranked items in order.
4. COMMENTS: Mine comments for entity identification ("what restaurant is that?"
   → "it's Kasama"), song identification ("song is X by Y"), and cultural
   context ("THE SKI MASK 💀" → Nike ski mask cultural connotation).
5. SEARCH QUERIES: The search_query field should be optimized for the most
   likely external lookup. For songs: "Song Title Artist" (Spotify). For
   restaurants: "Restaurant Name City" (Google Maps). For products:
   "Brand Product Model Specs" (Amazon).
6. SPECIFICATIONS: Capture dimensions, model numbers, RAM/storage, reps/sets,
   prices, sizes — anything that makes the entity specifically identifiable
   and searchable.
```

---

### Pass 3: Classification Prompt

```
ROLE: You are classifying TikTok content for a personal media library. Your
labels will be used for:
1. BROWSE FILTERS: Users filter their collection by topic, genre, affect
2. AGGREGATE STATS: "Your top topics this month", "affect breakdown"
3. SEARCH REFINEMENT: Narrowing search results by category

Classify based on how a USER would naturally categorize this content — not how
an academic media researcher would.

## Classification Ontology

### Topic — Primary subject matter (assign primary + optional secondary)

- food: Cooking, recipes, restaurants, food reviews, meal prep, food science
- fashion: Clothing, outfits, style advice, fashion shows, wardrobe content
- beauty: Makeup, skincare, haircare, beauty products, beauty routines
- fitness: Content where physical exercise is the VISIBLE PRIMARY SUBJECT. A
  person must be demonstrably exercising or discussing exercise technique.
  NOT: any content that merely has fitness hashtags or is by a fitness creator
  discussing non-fitness topics.
- travel: Destinations, travel tips, cultural experiences, travel vlogs
- music: Music performance, music discussion, artist spotlights, song rankings.
  NOT: videos that merely have background music.
- dance: Dance performance, choreography, dance tutorials
- comedy: Content whose primary purpose is humor. Skits, standup, observational
  comedy. NOT: informative content that happens to be funny.
- education: Structured knowledge transfer with clear pedagogical intent.
  NOT: general advice, opinions, product recommendations, or "life tips."
  A chemistry lesson is education. Career advice is career, not education.
- technology: Tech products, software, gadgets, tech industry, coding, AI
- gaming: Video games, game reviews, gaming culture, esports
- sports: Athletic events, sports commentary, team fandom, highlights
- pets: Animal content, pet care, animal behavior
- art: Visual art, illustration, photography, creative process, digital art
- books: Book recommendations, reading content, literary discussion
- movies_tv: Film/TV discussion, reviews, scene reactions, fan content
- news: Current events reporting, news commentary
- politics: Political commentary, policy discussion, civic engagement
- science: Scientific concepts, research, experiments, natural phenomena
- nature: Wildlife, landscapes, environmental content, outdoor activities
- diy: Home improvement, crafts, building, handmade projects
- finance: Personal finance, investing, economics, wealth building
- relationships: Dating, friendships, family dynamics, social skills
- parenting: Child-rearing, family life, parenthood experiences
- health: Medical information, mental health, wellness, nutrition science.
  NOT the same as fitness — health is about wellbeing, fitness is about exercise.
- career: Professional development, job advice, workplace dynamics,
  entrepreneurship, productivity methods
- real_estate: Property, housing, home buying/selling
- automotive: Cars, motorcycles, vehicle content, car culture
- other: Use when no label above fits. Always include a micro_label description.

### Genre — Content format (single label + confidence)

- tutorial: Step-by-step instruction with clear teaching intent
- review: Opinion/evaluation of a product, place, or experience
- vlog: Personal documentation of daily life or experiences
- skit: Scripted comedic or dramatic performance
- storytime: Narrative personal anecdote
- haul: Showing purchased items
- asmr: Autonomous sensory meridian response content
- challenge: Participating in a viral challenge or trend
- reaction: Responding to other content
- compilation: Collection of clips or items (montage, fan edit, ranking)
- before_after: Transformation content
- day_in_life: Documenting a typical or notable day
- get_ready_with_me: Preparation/getting ready content
- unboxing: Opening and revealing products
- recipe: Cooking demonstration with ingredients/steps
- workout: Exercise demonstration
- news_commentary: Discussion/opinion on current events
- interview: Conversation with a guest/subject
- timelapse: Time-compressed footage
- meme: Viral format, template-based humor, cultural reference
- duet: Side-by-side with another creator's content
- room_tour: Showing a space/environment
- outfit_showcase: Displaying clothing/style
- ranking: Ordered list of items by preference/quality
- edit: Fan-made creative compilation, usually with music
- pov: First-person perspective scenario
- other: Include description

### Affect — Viewer emotional experience (MULTI-LABEL with probability weights)

Assign probability weights to all applicable labels. Weights must sum to 1.0.
Include only labels with weight >= 0.15.

- funny: Makes the viewer laugh or smile. Comedy, satire, ironic juxtaposition,
  meme humor, dry wit. Includes subtle/cultural humor, not just obvious jokes.
- wholesome: Warm, heartfelt, emotionally tender content
- sad: Evokes sadness, grief, loss, melancholy
- angry: Provokes outrage, frustration, injustice
- nostalgic: Triggers memories, longing for the past, retro aesthetics
- inspiring: Makes the viewer feel motivated to change, improve, or overcome.
  Requires genuine emotional uplift — overcoming adversity, achievement,
  motivational speeches. NOT merely useful or informative content. NOT
  practical tips or advice. If the primary value is "this is useful info,"
  use informative instead.
- informative: Content primarily consumed for its factual or practical value.
  Tutorials, how-tos, tips, explainers, advice, recommendations. The viewer
  saves this to LEARN or REFERENCE, not to feel emotionally uplifted.
- cringe: Secondhand embarrassment, awkwardness
- satisfying: Sense of completion, order, sensory pleasure. Cleaning,
  organizing, precision, ASMR-like qualities.
- scary: Fear, suspense, horror, startling content
- relaxing: Calming, soothing, meditative, ambient
- shocking: Surprise, disbelief, unexpected twist
- neutral: No dominant emotional charge. Factual updates, straightforward
  documentation, product listings without emotional framing.

### Presentation Style — Visual format (multi-label, up to 2)

- talking_head: Person speaking directly to camera
- voiceover: Voice narration over visuals
- text_overlay: Significant on-screen text driving the content
- screen_recording: Captured screen/app footage
- slideshow: Multiple images/slides (carousel)
- cinematic: High production value, dramatic composition
- raw_footage: Unpolished, casual, handheld
- animation: Animated or motion graphics content
- mixed: Combination of multiple formats

### Content Provenance — Origin (single label)

- original: Creator's own content
- repost: Shared from another source
- duet: TikTok duet format
- stitch: TikTok stitch format
- remix: Modified version of existing content
- clip: Excerpt from longer content (TV, movie, podcast)
- ai_generated: AI-created content
- unknown: Cannot determine

---

## Content to Classify

Perception summary: {perception_summary}

Key entities identified:
{entities_summary}

Takeaway/thesis: {takeaway}

Caption: {caption}
Hashtags: {hashtags}
Creator: @{creator}
Music: {music}
Subtitles: {subtitles}
Comments: {comments}
Engagement: {play_count} plays, {like_count} likes

---

## Output Format

Return JSON:
{{
  "topic": {{
    "primary": "label",
    "secondary": "label or null",
    "micro_labels": ["specific refinements"],
    "confidence": 0.85
  }},
  "genre": {{
    "label": "label",
    "sub_genre": "free-form refinement or null",
    "micro_labels": [],
    "confidence": 0.9
  }},
  "affect": [
    {{"label": "informative", "weight": 0.65}},
    {{"label": "funny", "weight": 0.25}},
    {{"label": "satisfying", "weight": 0.10}}
  ],
  "presentation_style": ["talking_head", "text_overlay"],
  "content_provenance": {{
    "label": "original",
    "confidence": 0.95
  }}
}}

## Common Mistakes to Avoid

1. Do NOT classify as "fitness" based solely on hashtags or music metadata.
   The video must visually show exercise or explicitly discuss exercise technique.
2. Do NOT default to "inspiring" for useful or informative content. A recipe
   video is "informative + satisfying," not "inspiring." Career advice is
   "informative," not "inspiring." "Inspiring" requires genuine emotional uplift.
3. Do NOT classify as "education" for general advice, opinions, or commentary.
   "Education" requires structured pedagogical knowledge transfer.
4. When content is FUNNY, say so. Comedy, satire, and meme humor are frequently
   misclassified as "neutral" or "inspiring." If top comments contain 😂💀🤣 or
   "LMAO" variants, the content is almost certainly funny.
5. A video about food by a fitness creator is a FOOD video, not a fitness video.
   Classify by content, not by creator's niche.
6. "Satisfying" means sensory pleasure (ASMR, cleaning, organizing), not just
   "good content."
7. When uncertain, lower your confidence score. 0.4-0.6 is fine. Do not
   inflate confidence to appear decisive.
```

---

### Pass 4: Embedding Input Construction

Not a prompt per se, but a critical design spec for what text gets embedded:

```python
def build_embedding_text(
    caption: str,
    perception_summary: str,
    entities: list[dict],
    takeaways: list[dict],
    classification: dict,
    structured_content: dict | None,
) -> str:
    """Build the text blob for embedding generation.

    Priority order: caption → takeaway → primary entities → summary → labels.
    Keep under 500 tokens for embedding quality.
    """
    parts = []

    # 1. Caption (primary user-authored text)
    if caption and caption.strip():
        parts.append(caption.strip()[:300])

    # 2. Takeaways (the "point" of the video)
    for t in takeaways[:2]:
        parts.append(t["statement"][:200])

    # 3. Primary entities (what the video is about)
    primary = [e for e in entities if e.get("relevance") == "primary"]
    if primary:
        names = [e.get("display_name") or e["name"] for e in primary[:8]]
        parts.append("Subjects: " + ", ".join(names))

    # 4. Perception summary
    if perception_summary:
        parts.append(perception_summary[:300])

    # 5. Structured content summary
    if structured_content and structured_content.get("items"):
        sc_type = structured_content.get("type", "list")
        item_names = [i["name"] for i in structured_content["items"][:10]]
        parts.append(f"{sc_type}: {', '.join(item_names)}")

    # 6. Classification labels (for filtering alignment)
    topic = classification.get("topic", {})
    affect = classification.get("affect", [])
    if isinstance(topic, dict) and topic.get("primary"):
        label_str = f"Topic: {topic['primary']}"
        if topic.get("secondary"):
            label_str += f", {topic['secondary']}"
        parts.append(label_str)
    if affect and isinstance(affect, list):
        top_affect = sorted(affect, key=lambda a: a.get("weight", 0), reverse=True)
        parts.append("Mood: " + ", ".join(a["label"] for a in top_affect[:2]))

    return "\n".join(parts)
```

---

## Part IV: Ontology Changes Required

### Add to Affect

- `informative` — Content primarily consumed for factual or practical value

### Add to Genre

- `room_tour` — Showing a space/environment
- `outfit_showcase` — Displaying clothing/style
- `ranking` — Ordered list of items by preference/quality
- `edit` — Fan-made creative compilation, usually with music
- `pov` — First-person perspective scenario

### Modify Affect Handling

- Change from single-label to multi-label with probability weights
- Require weights summing to 1.0, minimum weight 0.15
- Return as array of `{"label": str, "weight": float}` objects

### Modify Topic Handling

- Add `secondary` topic field (optional)
- Keep `primary` as required single label

### Entity Type Expansion

Add these entity types to the schema:

- `recipe`, `ingredient`, `exercise`, `clothing`, `app_or_tool`
- `takeaway` (core opinion/claim/advice)
- `technique` (method being taught)
- `trend_or_meme` (viral format reference)
- `cultural_reference` (non-meme cultural context)

---

## Part V: Measurement Plan

### Re-run Evaluation

After implementing the new 4-pass pipeline, re-run on the same 47 items and score using the same 6-dimension rubric:

| Metric                               | Current         | Target                                 |
| ------------------------------------ | --------------- | -------------------------------------- |
| Items ≥ 14/18 ("wow")                | 21% (10/47)     | 50%+                                   |
| Items < 10/18 ("poor")               | 26% (12/47)     | <10%                                   |
| Accuracy avg                         | 2.40            | 2.60+                                  |
| Completeness avg                     | 1.98            | 2.40+                                  |
| Specificity avg                      | 1.87            | 2.30+                                  |
| Entity Coverage avg                  | 1.60            | 2.30+                                  |
| Classification Signal avg            | 1.61            | 2.20+                                  |
| Vision Added Value avg               | 2.17            | 2.40+                                  |
| Parse errors                         | 5/47 (11%)      | 0/47                                   |
| "Inspiring" overassignment           | 45%             | <15%                                   |
| "Fitness" false positive (text-only) | 53%             | N/A (text-only classification removed) |
| Per-slide extraction miss            | 7/19 slideshows | 0/19                                   |

### Specific Regression Tests

1. **Item 31 (The Studio)**: Must correctly identify the show, not "This Is The End"
2. **Item 35 (grilled cheese)**: Must identify 21 Savage song, not "Food by Densky9"
3. **Item 43 (desk setup)**: Must extract MacBook M4 Pro specs, monitor size, desk dimensions
4. **Item 26 (Chicago restaurants)**: Must extract restaurant names from each slide
5. **Item 14 (George Clanton songs)**: Must extract individual songs per slide
6. **Item 32 (Nike ski mask)**: Must note cultural connotation of Nike ski mask
7. **Item 47 (Pakistani bus)**: Must classify as funny/ironic, not sad
8. **Item 46 (low back exercises)**: Must extract specific exercises with reps/sets

---

## Part VI: Implementation Sequence

### Days 3-4: Build and Test New Prompts

1. Implement perception prompt (video + slideshow variants)
2. Implement entity extraction prompt with visual input (keyframes/images)
3. Implement classification prompt with multi-label affect
4. Increase max output tokens to 16K for perception
5. Wire 4-pass pipeline together
6. Re-run on same 47 items
7. Re-score using 6-dimension rubric
8. Compare against targets above

### Day 5: 100 Questions Exercise

Write 100 user queries across 4 tiers:

- 40 specific recall queries
- 30 filtered browsing queries
- 15 aggregation/reflection queries
- 15 cross-item analysis queries

Write ideal responses for 25 of them. Trace backward to required data fields.

### Day 6: Thumbnail Tier 1 Experiment

Test thumbnail + caption → topic + genre only on 50 items. Determine if this gives acceptable Tier 1 labels at $0.0005/item for the upload processing stage.

### Day 7: End-to-End Agent Test

Query the 47 re-processed items through the actual agent. Test 25 of the 100 questions. Score agent responses, not just data quality.
