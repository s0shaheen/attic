# Attic Research Initiative: A First-Principles Crash Course

## Building a Personal Content Intelligence System for Short-Form Video

---

# Part I: Problem Definition & Research Framing

## 1.1 The Root Problem (Scientific Framing)

**Research question**: Can a system automatically transform an individual's unstructured archive of short-form video interactions (saves, likes, shares) into a structured, queryable, semantically-rich personal knowledge base — and do so with sufficient accuracy, speed, and cost-efficiency to be commercially viable?

**Hypothesis**: A two-tier processing architecture — lightweight metadata indexing at ingest time, followed by on-demand multimodal deep analysis at query time — can achieve classification accuracy above 80% F1 across core content facets while keeping per-user processing costs under $5 for initial onboarding of up to 1,000 items.

**The gap this addresses**: Short-form video platforms (TikTok, Instagram Reels, YouTube Shorts) have become primary information consumption channels. Users save content — recipes, product recommendations, educational tutorials, creative inspiration — with the vague intention of returning to it. But the platforms provide no semantic organization. A user with 800 saved TikToks has no way to answer "what was that pasta recipe I saved in October?" or "show me all the home office setup ideas I've been collecting." The content is accessible only by manual scrolling through a reverse-chronological feed.

This is an information retrieval problem applied to personal multimedia archives. The research challenge is that the source material — short-form video — is among the hardest content types to classify automatically:

- **Text signals are sparse or absent.** Captions are often emoji-only, inside jokes, or intentionally cryptic. Hashtags are gamed for reach, not descriptive accuracy. Subtitles exist only when the platform's ASR system generated them.
- **The meaningful information lives in pixels and audio.** A 15-second cooking video communicates its content almost entirely through visual and auditory channels — what's being cooked, what technique is used, what the kitchen looks like.
- **Content types are heterogeneous.** A single user's saved collection might span tutorials, memes, product reviews, fan edits, ambient videos, and news commentary — each requiring different analytical approaches.
- **The relationship between content and personal relevance is subjective.** Two identical videos might be saved for completely different reasons by different users — one for the recipe, another because they recognized the kitchen from a different creator.

**Dependent variables** (what we're measuring):
1. Classification accuracy per ontology facet (precision, recall, F1)
2. Retrieval quality (recall@5, recall@10 for natural language queries)
3. Processing cost per item (USD, broken down by pipeline step)
4. Processing latency (wall-clock time from upload to agent-ready state)
5. User satisfaction with agent responses (qualitative, post-MVP)

**Independent variables** (what we're manipulating):
1. Input modality: text-only vs. thumbnail vs. full video
2. Embedding strategy: text-only vs. visual-only vs. hybrid
3. Ontology design: number of facets, label granularity
4. Processing architecture: batch-all-upfront vs. two-tier lazy evaluation
5. Model selection: Gemini Flash vs. Pro, CLIP variant, embedding model

## 1.2 Why This Problem Is Hard (And Why Existing Approaches Fail)

**Existing content classification systems and their limitations:**

| System | Domain | Approach | Why It Doesn't Solve Our Problem |
|--------|--------|----------|----------------------------------|
| IAB Content Taxonomy | Advertising | 700+ categories, designed for page-level web content classification | Optimized for ad targeting, not personal relevance. Treats "cooking" as a single category — no distinction between "recipe I want to try" and "food content I watch for entertainment" |
| IPTC NewsCodes | Journalism | Hierarchical subject codes for news media | Assumes professional editorial content. No concept of user-generated content, memes, or social media-native formats |
| YouTube Content ID | Copyright | Audio/video fingerprinting for rights management | Identifies *what* content is (this specific song, this specific movie clip) but not *what it's about* or *why someone saved it* |
| TikTok's internal recommendation | Advertising/Engagement | Collaborative filtering + content embeddings | Optimized for "what to show next," not "help the user organize what they already saved." The signals (watch time, replay, share) measure engagement, not semantic category |
| Spotify Wrapped / YouTube Recap | Analytics | Aggregate consumption statistics | Descriptive statistics about consumption patterns, not semantic organization of individual items |

The gap: no system exists that combines multimodal content understanding (what is this video about?), personal context (why did this person save it?), and queryable organization (find me X from my collection) for short-form video at the individual user level.

This is the space Attic occupies.

---

# Part II: Foundational Concepts

This section builds from the ground up. Each concept is introduced with its formal definition, intuitive explanation, and direct mapping to how it applies to the Attic pipeline.

## 2.1 Machine Learning Fundamentals

### 2.1.1 What Machine Learning Actually Is

Machine learning is function approximation from data. You have inputs (features) and desired outputs (labels or predictions). You use data to learn a function that maps inputs to outputs, and then apply that function to new inputs you haven't seen before.

**The three paradigms:**

**Supervised learning**: You provide labeled examples — "this video is a cooking tutorial, this one is a dance video" — and the model learns to predict labels for new, unseen videos. This is what classification is.

**Unsupervised learning**: You provide data without labels, and the model finds structure — groups, patterns, anomalies. This is what clustering is. When you embed 1,000 TikToks and look for natural groupings, you're doing unsupervised learning.

**Self-supervised learning**: The model creates its own labels from the data's structure. This is how modern language models (GPT, Claude) and vision models (CLIP) are trained. CLIP learns by predicting which caption goes with which image across millions of image-text pairs. It never receives explicit labels like "this is a cat" — it learns semantic understanding from the structure of co-occurrence.

**For Attic**: We're primarily doing supervised classification (assigning ontology labels to content) using pre-trained models (Gemini, CLIP) that were trained via self-supervised learning. We don't train any models ourselves — we use them as tools. This is sometimes called "zero-shot" or "few-shot" classification: the model has never seen our specific labels during training, but its general understanding of language and vision is sufficient to apply them.

### 2.1.2 Embeddings: The Universal Representation

**Formal definition**: An embedding is a learned mapping from a high-dimensional, discrete input space (words, images, videos) to a low-dimensional, continuous vector space where semantic similarity is preserved as geometric proximity.

**Intuitive explanation**: Imagine you had to describe every TikTok you've ever saved using exactly 1,536 numbers. Not categories, not tags — just numbers. And the rule is: videos that are *about* similar things should get similar numbers. A cooking tutorial and a recipe video would get nearly identical numbers. A cooking tutorial and a skateboarding trick would get very different numbers.

That's what an embedding model does. It compresses the rich, complex meaning of content into a fixed-size numerical fingerprint.

**Why this matters**: Numbers can be compared mathematically. Once everything is represented as vectors, "find me videos similar to this query" becomes "find the vectors closest to this query vector" — a purely mathematical operation (cosine similarity) that databases can execute in milliseconds over millions of items.

**The embedding pipeline for Attic**:

```
Raw content → Feature extraction → Embedding model → Vector (numbers) → Vector database → Search
```

Three types of embeddings are relevant:

1. **Text embeddings** (OpenAI text-embedding-3-small): Input is a string of text. Output is a 1,536-dimensional vector. Used for: searching content by text queries.

2. **Visual embeddings** (CLIP ViT-B/32): Input is an image. Output is a 512-dimensional vector. Used for: finding visually similar content, cross-modal search (text query → visual results).

3. **Multimodal embeddings**: Input is text + image together. Output is a single vector capturing both modalities. Used for: unified search across text and visual features.

**Key mathematical operation — Cosine Similarity**:

Given two vectors A and B, cosine similarity = (A · B) / (|A| × |B|). This measures the angle between the two vectors, ignoring magnitude. Result ranges from -1 (opposite meaning) to 1 (identical meaning). In practice, most similar items score between 0.6–0.9.

In pgvector (which Attic uses via Supabase), the operator `<=>` computes cosine *distance* (1 - similarity), so lower distance = more similar.

**Further reading:**
- [Jay Alammar — The Illustrated Word2vec](https://jalammar.github.io/illustrated-word2vec/) — visual, intuitive explanation of how embeddings work
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings) — practical API usage
- [Lilian Weng — Generalized Visual Language Models](https://lilianweng.github.io/posts/2022-06-09-vlm/) — deep dive on how CLIP and similar models learn multimodal representations

### 2.1.3 Classification: Assigning Labels to Content

**Formal definition**: Classification is the task of assigning one or more categorical labels to an input from a predefined set of possible labels.

**Types relevant to Attic:**

- **Multi-class classification**: Each item gets exactly one label from a set (e.g., Topic: one of {food, fashion, comedy, ...}). The labels are mutually exclusive.
- **Multi-label classification**: Each item can get multiple labels simultaneously (e.g., a cooking comedy video gets both Topic:food AND Affect:funny).
- **Multi-task classification**: Multiple independent classification problems applied to the same input. This is exactly what Attic's ontology is — each facet (Topic, Genre, Affect, Presentation Style, Content Provenance) is its own classification task with its own label set.

**How LLMs do classification (no training required):**

Traditional ML classification requires training a model on labeled examples. With LLMs (Gemini, GPT, Claude), you can classify "zero-shot" — describe the task and the labels in a prompt, and the model applies its pre-trained knowledge to assign labels.

```
Prompt: "Classify this TikTok into one of these topics: food, fashion, comedy, ..."
+ content metadata and visual description
→ Model outputs: {"topic": "food", "confidence": 0.92}
```

This is what Attic does. No model training, no labeled training set needed. The tradeoff: you're dependent on the model's pre-trained understanding, and you have less control over edge cases.

**Evaluation metrics:**

- **Precision** = (correct positive predictions) / (all positive predictions). Of the videos I labeled "cooking," what percentage actually are cooking videos? High precision = few false positives.
- **Recall** = (correct positive predictions) / (all actual positives). Of all the actual cooking videos, what percentage did I correctly label? High recall = few false negatives.
- **F1 Score** = 2 × (precision × recall) / (precision + recall). Harmonic mean of precision and recall. Balances both concerns. This is the primary metric for classification quality.

For a search/retrieval product, **recall matters more than precision**. Missing a relevant item (false negative) is worse than including a marginally relevant one (false positive), because the user expects the system to find things they know they saved.

**Further reading:**
- [Google ML Crash Course — Classification](https://developers.google.com/machine-learning/crash-course/classification) — fundamentals with interactive exercises
- [Scikit-learn — Classification Metrics](https://scikit-learn.org/stable/modules/model_evaluation.html#classification-metrics) — comprehensive metric reference

### 2.1.4 Vector Search and Retrieval

**Formal definition**: Vector search (also called approximate nearest neighbor search, or ANN) is the task of finding the k vectors in a database that are most similar to a query vector, measured by a distance metric (typically cosine distance or Euclidean distance).

**How it works in Attic:**

1. At upload time, each media event gets embedded into a vector (1,536 numbers for text, 512 for visual)
2. These vectors are stored in Supabase's pgvector extension
3. When the user asks "show me cooking videos," the query text gets embedded into the same vector space
4. pgvector finds the stored vectors closest to the query vector using an index (HNSW or IVFFlat)
5. The corresponding media events are returned, ranked by similarity

**Index types (pgvector):**

- **IVFFlat**: Partitions the vector space into clusters, then searches only the nearest clusters. Fast build, approximate results. Good for < 100K vectors.
- **HNSW** (Hierarchical Navigable Small World): Builds a graph structure connecting similar vectors. Slower build, better recall. The standard choice for production systems. Attic should use this (it's in the roadmap as issue #66).

**The retrieval pipeline** (what happens when the agent searches):

```
User query: "Spider-Man fan edits"
     ↓
Text embedding: embed("Spider-Man fan edits") → [0.023, -0.041, ...]
     ↓
Vector search: SELECT * FROM media_events ORDER BY embedding_vector <=> query_vector LIMIT 50
     ↓
Candidate set: 50 items ranked by cosine similarity
     ↓
(Optional) Re-rank: Agent applies additional filtering/logic
     ↓
Results: Top items returned to user
```

**The fundamental limitation of vector search**: It can only find things that are *semantically similar in the embedding space*. If a video's embedding doesn't encode the concept "Spider-Man" (because the caption was just emojis and the text embedding captured nothing useful), vector search will never find it, no matter how good the query embedding is. This is why enriching the embedding input (adding vision descriptions, classification labels) is so critical — it puts more semantic signal into the vector.

### 2.1.5 Clustering: Finding Natural Groups

**Formal definition**: Clustering is the task of partitioning a set of data points into groups (clusters) such that points within the same group are more similar to each other than to points in other groups.

**Algorithms relevant to Attic:**

- **K-means**: Requires specifying the number of clusters (k) in advance. Fast, simple. Works well when clusters are roughly spherical and evenly sized. Limitation: you must choose k, and real data rarely has a "correct" number of clusters.
- **HDBSCAN** (Hierarchical Density-Based Spatial Clustering of Applications with Noise): Does not require specifying k. Finds clusters of varying density and size. Can label points as "noise" (not belonging to any cluster). Better for exploratory analysis. This is the recommended algorithm for Attic's use case because you don't know in advance how many natural content groupings a user's collection has.

**Application in Attic:**

1. **Visual clustering**: Embed all thumbnails with CLIP, cluster the visual embeddings. Discovers visual archetypes in a user's collection — "talking head videos," "overhead cooking shots," "text-on-background memes," "outdoor nature footage." These are presentation styles the ontology might not fully capture.

2. **Semantic clustering**: Cluster the text embeddings. Discovers topical groupings — a user might have a "home renovation" cluster, a "Korean street food" cluster, a "startup advice" cluster. These could inform personalized ontology labels.

3. **Cross-modal clustering**: Cluster on combined text + visual features. Discovers richer groupings that neither modality captures alone.

**Visualization**: High-dimensional clusters can be visualized in 2D using dimensionality reduction techniques:
- **t-SNE** (t-distributed Stochastic Neighbor Embedding): Preserves local structure well. Good for visualization. Non-deterministic — different runs give different layouts.
- **UMAP** (Uniform Manifold Approximation and Projection): Faster than t-SNE, better preserves global structure. Generally preferred for production use.

**Further reading:**
- [StatQuest — t-SNE Clearly Explained](https://www.youtube.com/watch?v=NEaUSP4YerM) — visual, intuitive explanation
- [HDBSCAN Documentation](https://hdbscan.readthedocs.io/) — the clustering algorithm best suited for Attic's use case
- [Lilian Weng — Learning with not Enough Data](https://lilianweng.github.io/posts/2021-12-05-semi-supervised/) — relevant for understanding how to work with limited labeled data

## 2.2 Large Language Models as Tools

### 2.2.1 How LLMs Work (The Mental Model You Need)

You do not need to understand transformer architectures or attention mechanisms to build with LLMs effectively. You need to understand this:

**An LLM is a function**: text in → text out. The function has been trained on vast amounts of text (and in multimodal models, images/video/audio) to produce outputs that are statistically likely given the input. When you ask Gemini to classify a TikTok, it's not "understanding" the content in a human sense — it's producing output tokens that, given its training, are the most probable completion of your prompt.

**The implications for Attic:**

1. **Prompts are programs.** The prompt you write determines the quality of the output more than the model you choose. A well-crafted prompt on a cheap model (Gemini Flash) will outperform a vague prompt on an expensive model (GPT-4o). Prompt engineering is the primary skill for working with LLMs.

2. **LLMs are stochastic.** The same input can produce different outputs across runs (controlled by the "temperature" parameter). At temperature 0, outputs are nearly deterministic. At temperature 1, they're creative/variable. For classification, you want low temperature (0.1–0.3) for consistency.

3. **LLMs hallucinate.** They produce confidently wrong outputs. For classification, this means they'll happily assign labels that aren't in your ontology, invent categories, or produce valid-looking JSON with fabricated confidence scores. You must validate every output — which is exactly what Attic's `validate_classification()` function does.

4. **Structured output is fragile.** Asking an LLM to return JSON works ~95% of the time. The other 5%, you get malformed JSON, markdown fences around the JSON, extra text before/after, or creative interpretation of the schema. Always wrap JSON parsing in try/catch and have fallback behavior.

### 2.2.2 Vision-Language Models (VLMs)

**What they are**: Models that can process both text and images (and in newer versions, video and audio) as input and produce text output. Gemini Flash, GPT-4o, and Claude all have this capability.

**How they process video**: Video is not understood as a continuous stream. It's sampled into frames and processed as a sequence of images plus an audio track. When you send a video to Gemini, the model internally:
1. Samples frames at a fixed rate (the 263 tokens/second rate we discussed)
2. Encodes each frame through its vision encoder
3. Processes the sequence of encoded frames along with any text input
4. Generates a text response

**The critical capability for Attic**: VLMs can describe what they see in natural language. A frame showing a person in a kitchen chopping vegetables becomes: "A person stands at a kitchen counter chopping vegetables. A cutting board with diced onions is visible. The kitchen has white tile backsplash and stainless steel appliances." This description, once generated, becomes text that can be embedded, searched, and classified using all the text-based tools described above.

This is the **grounding** step — converting visual information into textual representations that the rest of the pipeline can work with.

### 2.2.3 CLIP: Bridging Vision and Language

**CLIP** (Contrastive Language-Image Pre-training, OpenAI, 2021) is the foundational model for visual embeddings.

**How it was trained**: CLIP was trained on 400 million image-text pairs from the internet. The training objective: given an image and its associated caption, learn representations where the image embedding and the text embedding are close together in vector space. Given an image and an *unrelated* caption, learn representations where they're far apart.

**Why this matters for Attic**: CLIP learned a shared embedding space for images and text. This means:
- You can embed a TikTok thumbnail → get a visual vector
- You can embed the text "cooking tutorial" → get a text vector
- These vectors are directly comparable using cosine similarity
- If the thumbnail shows cooking, the similarity score will be high

This enables **cross-modal search**: a text query can find images, and an image query can find text descriptions. No other type of embedding model can do this.

**Practical details:**
- CLIP ViT-B/32 produces 512-dimensional vectors (much smaller than OpenAI's 1,536-dim text embeddings)
- It runs on CPU (slower) or GPU (faster). For Attic's workbench experiments, CPU is fine. For production at scale, consider GPU or using an API service.
- The open-source implementation is available via the `open-clip-torch` Python package.

**Limitations**: CLIP was trained on static images and text. It has no temporal understanding — it can't understand that frame 1 shows raw ingredients and frame 10 shows a finished dish, and that the video is therefore a cooking tutorial. For temporal reasoning, you need either keyframe extraction + sequential analysis, or a native video model like Gemini.

**Further reading:**
- [OpenAI CLIP Paper](https://arxiv.org/abs/2103.00020) — the original paper
- [Lilian Weng — Contrastive Representation Learning](https://lilianweng.github.io/posts/2021-05-31-contrastive/) — the broader framework CLIP belongs to

### 2.2.4 Agentic AI: LLMs That Use Tools

**What an agent is**: An LLM that can, in addition to generating text, invoke external tools (functions, APIs, databases) to gather information or take actions, then use the results to continue its reasoning.

**The agent loop (Attic's architecture):**

```
User query → LLM reads query + system prompt
    ↓
LLM decides: "I need to search the user's content"
    ↓
LLM generates a tool call: search_similar(query_text="Spider-Man fan edits")
    ↓
System executes the tool, returns results to LLM
    ↓
LLM reads results, decides: "I need deeper analysis on these 5 items"
    ↓
LLM generates another tool call: deep_analyze(media_event_ids=[...])
    ↓
System executes, returns enriched data
    ↓
LLM synthesizes everything into a response to the user
```

**Attic's agent architecture**: Claude Haiku handles orchestration (deciding which tools to call, in what order, and how to synthesize results). Gemini handles vision and classification (when the agent triggers visual analysis). OpenAI handles embeddings. This multi-model architecture uses each model for what it's best at.

**The tool set** (current + planned):
- `query_items`: Structured metadata filtering (creator, hashtag, topic, etc.)
- `search_similar`: Semantic vector search over text embeddings
- `classify`: On-demand ontology classification via Gemini
- `analyze_visual`: Vision analysis of thumbnails via Gemini
- `resolve_entity`: Entity identification via external APIs (Google Maps, TMDB, etc.)
- `stats_overview` / `stats_creator_details`: Aggregate analytics
- **NEW** `deep_analyze`: The Tier 2 processing tool — downloads video, runs Gemini vision, classifies, re-embeds, and caches results
- **NEW** `search_visual`: Vector search over CLIP visual embeddings

## 2.3 Data Engineering Fundamentals

### 2.3.1 Data Pipelines

**Formal definition**: A data pipeline is a sequence of processing steps that transforms raw input data into a structured, enriched output suitable for downstream consumption.

**Attic's pipeline** (two-tier architecture):

**Tier 1 — Upload-time light pass:**
```
ZIP file → Parse URLs → Apify enrichment → Thumbnail download → Text embedding → CLIP visual embedding → READY
```
Every item goes through this. Cost: ~$0.003-0.005/item. Time: ~2-3 minutes for 100 items.

**Tier 2 — Query-time deep pass (agent-triggered):**
```
Media event IDs → Video download → Gemini video/vision analysis → Classification → Enriched re-embedding → Cache to DB
```
Only items the agent identifies as relevant to a query. Cost: ~$0.005-0.02/item. Time: ~1-3 seconds/item.

**Key design principles:**

- **Idempotency**: Every step can be re-run safely. If the pipeline crashes mid-step and restarts, it won't duplicate data or corrupt state. Achieved through upserts with deterministic IDs and processing_state gating.
- **Graceful degradation**: If Apify fails on some items, the pipeline continues with what it has. If Gemini times out, the agent falls back to text-only analysis. No single failure blocks the entire pipeline.
- **Progressive enrichment**: Items start with minimal data and get progressively richer as they're processed. The agent can work with whatever level of enrichment is available.

### 2.3.2 Data Validation and Profiling

**Data profiling** is systematically measuring the quality, completeness, and distribution of your data. Before you can build any ML system, you need to know what your data actually looks like.

**What to measure for Attic's Apify data:**
- **Fill rate**: What percentage of items have each field populated? (caption_text, thumbnail_url, video_url, subtitles, hashtags, creator, music, etc.)
- **Distribution**: What are the most common values for categorical fields? (media types, caption lengths, hashtag counts)
- **Failure rate**: What percentage of Apify requests fail? Under what conditions?
- **Edge cases**: What does "missing" look like for each field? (null, empty string, "N/A", etc.)

This is your Day 1 task. Every decision downstream depends on understanding the data.

### 2.3.3 Evaluation Infrastructure

**The golden set**: A manually labeled collection of items with known correct answers. This is the most important single artifact in any ML system. Without it, you cannot measure whether your system is improving or degrading.

**For Attic, the golden set contains:**
1. 50-100 media events with hand-labeled ontology facets (the "correct" classification)
2. 20-30 natural language queries with expected results (the "correct" retrieval)
3. Diversity across content types, caption styles, and edge cases

**The evaluation loop:**
```
Change something (prompt, model, embedding strategy, ontology)
     ↓
Run the pipeline over the golden set
     ↓
Measure metrics (F1, recall@k)
     ↓
Compare to previous baseline
     ↓
Accept or reject the change based on data
```

This is the scientific method applied to ML engineering. No change ships without measurement.

---

# Part III: Content Analysis Philosophy

## 3.1 How Should Social Media Content Be Analyzed?

This is not purely a technical question. It sits at the intersection of computer science, media studies, psychology, and sociology. Different disciplines approach it differently, and the design of Attic's ontology must synthesize these perspectives.

### 3.1.1 The Media Researcher's View

Academic media studies has decades of work on content classification. The dominant frameworks:

**Uses and Gratifications Theory** (Katz, Blumler & Gurevitch, 1973): People consume media to satisfy specific needs — information seeking, entertainment, social interaction, personal identity, escapism. This maps directly to Attic's "Viewer Orientation" and "Communicative Intent" facets. The limitation: this theory was developed for broadcast media and assumes relatively passive consumption. Social media blurs the line between consumer and creator.

**Genre Theory** (media studies broadly): Content belongs to genres — recognizable patterns of form and convention. A "tutorial" has different structural conventions than a "vlog" or a "skit." Genres are not fixed — they emerge, evolve, and hybridize. TikTok has spawned entirely new genres (duet reaction chains, stitch debates, "POV" narratives) that don't map cleanly to pre-existing taxonomies.

**Affect Theory** (Massumi, Tomkins, and in computational form, Russell's Circumplex Model): Content produces emotional responses along measurable dimensions. Russell's model maps emotions to two axes: valence (positive/negative) and arousal (high/low energy). "Funny" = positive valence, moderate arousal. "Satisfying" = positive valence, low arousal. "Shocking" = varies in valence, high arousal. This is the grounding for Attic's Affect facet.

**What a researcher would say about Attic's ontology**: "You need to distinguish between properties of the content itself (what it depicts, its format, its production quality) and properties of the consumption experience (why someone saved it, how it made them feel). These are different analytical layers, and conflating them produces unreliable classification."

This is a valid and important critique. Attic's ontology attempts to address it by separating content-intrinsic facets (Topic, Genre, Presentation Style, Content Provenance) from consumption-context facets (Affect, Viewer Orientation). Whether these can be classified from the content alone — without behavioral data about the specific user — is an open empirical question that the evaluation framework will answer.

### 3.1.2 The Power User's View

A heavy social media user has an intuitive, folksonomy-style mental model of their saved content. If you asked them to organize their saved TikToks, they would not use academic categories. They would use labels like:

- "Recipes I actually want to try"
- "Funny stuff to send to Jake"
- "Home inspo"
- "That one video with the song I liked"
- "Workout stuff"
- "Things I saved at 2am and don't remember why"

**Key insights from this perspective:**

1. **Personal salience > objective categories.** The user doesn't care if something is technically a "tutorial" or a "review." They care that it's "the video where the guy explains how to fix the squeaky door."

2. **Entities matter more than categories.** Users remember specific things — a restaurant name, a book title, a product, a creator, a song. Entity recognition and resolution is potentially more valuable than categorical classification.

3. **Temporal and contextual memory.** Users remember *when* they saved something ("it was during that trip to Chicago") or *how* they found it ("someone sent it in the group chat") more than what category it belongs to.

4. **The "vibe" dimension.** There's a quality to content that resists categorical description — the aesthetic, the mood, the energy. This is partially captured by Affect and Presentation Style, but there's a residual "vibe" that current ontologies don't fully capture. Visual embeddings (CLIP) may capture this implicitly — visually similar content tends to have similar "vibes."

### 3.1.3 The Casual User's View

A casual social media user saves content rarely and has a simpler mental model:

- "Things I liked"
- "Funny videos"
- "Useful stuff"
- "Things I want to buy"

**Implication for Attic:** The ontology needs to work at multiple levels of specificity. A casual user should be able to ask "show me the funny stuff" and get useful results. A power user should be able to ask "show me the avant-garde cooking tutorials that use unusual techniques" and get *different* useful results. The ontology's tier-1 labels serve the casual user; the tier-2 micro-labels and semantic search serve the power user.

### 3.1.4 The AI Scientist's View

An AI researcher approaches content classification as an optimization problem with specific constraints:

**Orthogonality**: Facets should be as independent from each other as possible. If knowing the Topic perfectly predicts the Genre (e.g., Topic:food always implies Genre:recipe), those facets are not orthogonal — one of them is redundant. Orthogonal facets maximize the information captured per classification call.

**Measurability**: Every label in the ontology must be classifiable from available inputs with above-chance accuracy. If a facet can't be reliably classified (e.g., Viewer Orientation requires knowing the user's internal state, which isn't observable from the video), it shouldn't be in the automated classification pipeline — it should be inferred from user behavior or asked directly.

**Granularity tradeoff**: More labels = more precise classification but lower per-label accuracy (less training signal per class). Fewer labels = higher accuracy but coarser organization. The sweet spot depends on the downstream use case — search benefits from finer granularity, aggregate statistics benefit from coarser labels.

**Evolvability**: The ontology must accommodate new content types that don't exist yet. TikTok's content landscape changes rapidly — "AI slop" didn't exist two years ago, "unhinged corporate TikTok" is recent, new challenge formats emerge weekly. A rigid ontology becomes stale. A good design has:
- Fixed tier-1 labels that change rarely (annual review)
- Open tier-2 micro-labels that the model assigns freely, which accumulate into a corpus of emerging categories
- A process for "promoting" frequently occurring micro-labels to tier-1 status

### 3.1.5 Synthesis: The Attic Approach

Attic's ontology design must navigate between these perspectives. Here's the novel synthesis:

**Layer 1: Content-Intrinsic Properties** (what the video *is*)
These can be classified from the content alone, without knowing anything about the user:
- **Topic**: What subject matter does this content address? (food, fashion, tech, etc.)
- **Genre**: What communicative format is used? (tutorial, vlog, meme, etc.)
- **Presentation Style**: How is it visually/editorially constructed? (talking head, text overlay, etc.)
- **Content Provenance**: What is the content's origin? (original, duet, stitch, edit, etc.)

**Layer 2: Interpretive Properties** (what the video *does*)
These require inferring intent or effect, which is harder and less reliable:
- **Affect**: What emotional response does the content produce? (funny, satisfying, etc.)

**Layer 3: User-Context Properties** (what the video means *to this user*)
These cannot be classified from the content alone — they depend on the user's history, behavior, and stated intent. They should NOT be in the automated classification pipeline. Instead, they should be inferred by the agent at query time:
- **Why they saved it** (viewer orientation/purpose): Inferred from the query context. If a user asks "what workouts have I saved?", the items returned are implicitly oriented toward "active learning" for fitness — the agent doesn't need a pre-assigned label to know this.
- **Personal relevance**: This is what the agent's intelligence layer provides beyond classification.

**Entity extraction as a first-class concern**: Alongside categorical classification, every item should have entities extracted — people, places, products, songs, books, movies, brands — with resolution against external knowledge bases. Users search for entities as often as categories ("that restaurant," "the book someone recommended," "videos with this song").

**The evolution mechanism**: Tier-2 micro-labels are free-form — the model generates whatever terms it finds most descriptive. Over time, these accumulate into a frequency-ranked vocabulary. When a micro-label appears across many users and many items, it's a candidate for promotion to tier-1. This creates a data-driven ontology evolution process rather than a top-down editorial one.

## 3.2 The Classification Methodology

### 3.2.1 Two-Stage Pipeline

The classification pipeline separates perception from judgment:

**Stage 1 — Perception (Vision Model, Expensive)**
Input: Video file or thumbnail image
Task: Describe what you see, literally and specifically
Output: Structured text description (scene descriptions, objects, text on screen, audio description, presentation style)
Model: Gemini Flash (with vision capability)

This stage does NOT classify. It translates visual information into text. The description becomes a reusable asset — once generated and cached, it never needs to be regenerated.

**Stage 2 — Judgment (Text Model, Cheap)**
Input: Stage 1 description + Apify metadata (caption, hashtags, creator, subtitles, engagement metrics)
Task: Classify across ontology facets, extract entities
Output: Structured JSON with labels, confidence scores, and entity list
Model: Gemini Flash (text-only mode)

This stage uses the rich text representation from Stage 1, combined with all available metadata, to make classification decisions. Because it's text-only, it's fast and cheap.

**Why separate them?** Because you can iterate on Stage 2 (prompt engineering, ontology revision, label adjustment) without re-running Stage 1. The visual description is a stable intermediate representation that insulates downstream processing from upstream changes.

### 3.2.2 What Gets Embedded

The embedding input template is the single highest-leverage design decision for retrieval quality. Here's the target template for Tier 1 and Tier 2:

**Tier 1 (upload-time, before visual analysis):**
```
@{creator_username} | {caption_text} | #{hashtag1} #{hashtag2} ... |
Subtitles: {subtitle_text} | Music: {music_name}
```

**Tier 2 (after deep processing, replaces Tier 1 embedding):**
```
@{creator_username} | {caption_text} | #{hashtag1} #{hashtag2} ... |
Subtitles: {subtitle_text} | Music: {music_name} |
Visual: {gemini_scene_summary} |
Classification: Topic:{topic}, Genre:{genre}, Affect:{affect}, Style:{presentation_style} |
Entities: {entity_1_name} ({entity_1_type}), {entity_2_name} ({entity_2_type}), ...
```

The Tier 2 embedding is dramatically richer — it encodes visual understanding, classification labels, and entities directly into the searchable vector. A video with an emoji-only caption but a detailed vision description becomes searchable by its actual content.

---

# Part IV: Technical Approach & Tradeoff Analysis

## 4.1 Architecture Options Evaluated

### 4.1.1 Processing Architecture

**Option A: Batch-All-Upfront (Rejected)**
Process every item through the full pipeline (including video download, vision analysis, classification, embedding) at upload time.
- Pros: Agent has maximum data quality from the first query. No cold-start problem.
- Cons: Upload takes 30-60 minutes for 500 items. First-upload cost of $15-25 for a power user. User must wait before they can start using the product.
- Rejected because: Latency and cost make the first-time experience unacceptable for a consumer product.

**Option B: Text-Only, No Vision (Rejected for V0)**
Process only text metadata (caption, hashtags, subtitles) — no video download or visual analysis.
- Pros: Fast, cheap, simple pipeline.
- Cons: ~25% of TikToks have emoji-only or empty captions. Dance, fashion, food, and edit content is largely visual — text-only classification accuracy drops below 70% for these categories. Retrieval fails for visually distinctive content.
- Rejected because: Text-only is insufficient for a visual medium. Would produce a V0 that feels broken for a significant percentage of queries.

**Option C: Two-Tier Lazy Evaluation (Selected)**
Light pass at upload time (metadata + thumbnails + basic embeddings). Deep pass on-demand (video download + vision + classification + re-embedding) triggered by agent at query time.
- Pros: Fast upload (2-3 min for 100 items). Low upfront cost (~$0.50 for 100 items). User can start chatting immediately. Deep processing costs amortized across queries and focused on content the user actually cares about.
- Cons: Cold-start quality risk — first queries rely on Tier 1 data only. Added architectural complexity — the agent must manage processing state.
- Mitigation: Background progressive processing after light pass completes. Over-retrieval at Tier 1 (top-50 instead of top-10) to reduce false negatives.
- Selected because: Best balance of user experience, cost, and quality for a consumer product.

### 4.1.2 Vision Analysis Strategy

**Option A: Thumbnail Only**
Send Apify's `coverUrl` (single static image) to Gemini.
- Pros: No video download needed. Simplest pipeline. Cheapest (~$0.0003/item).
- Cons: Single frame captures one moment — misses temporal content (transitions, steps in a recipe, scene changes). TikTok auto-selects thumbnails for click-through, not semantic representativeness. Edit videos' thumbnails are especially misleading.
- Accuracy estimate: 60-70% of full-video quality (assumption — needs empirical validation on golden set).

**Option B: Keyframe Extraction + Individual Frame Analysis**
Download video, extract keyframes via scene detection (FFmpeg + perceptual hashing), send 5-10 frames to Gemini.
- Pros: Captures temporal structure. Catches scene changes. Multiple frames provide redundancy.
- Cons: Requires video download pipeline. FFmpeg dependency. Scene detection tuning per content type. Multiple frames = higher token count (5-10 images × 258 tokens/image = 1,290-2,580 tokens, vs. video's 263 tokens/second).
- Key finding: For a 30-second video, keyframe extraction may actually produce *more* input tokens than sending the whole video, while losing temporal context.

**Option C: Native Video Input to Gemini (Selected for experimentation)**
Download video, upload to Gemini File API, send the entire video for analysis.
- Pros: Model handles its own frame sampling with temporal understanding. Captures motion, transitions, pacing, audio-visual synchronization. Simplest code — no FFmpeg, no scene detection. For 30-second videos, cost is ~$0.003-0.005/video on Gemini Flash (263 tokens/sec × 30 sec = 7,890 tokens + 960 audio tokens ≈ 8,850 tokens at $0.30-0.50/1M tokens).
- Cons: Requires video download (bandwidth + temp storage). Gemini File API upload adds latency. Less control over what the model attends to. Higher per-item cost than thumbnail-only.
- Selected for experimentation because: Cost is surprisingly low. Pipeline is simpler than keyframe extraction. Temporal understanding is a significant quality advantage. Empirical comparison against thumbnail-only on the golden set will determine the production choice.

**Experiment needed**: Run all three options over the golden set. Measure classification F1 per facet for each. If thumbnail-only achieves >85% of full-video quality, the cost/complexity savings may justify using it for Tier 1 with full-video reserved for Tier 2.

### 4.1.3 Embedding Strategy

**Option A: Text Embedding Only (Current State)**
Embed the fused text (caption + hashtags + subtitles + creator + music) using OpenAI text-embedding-3-small (1,536 dimensions).
- Pros: Simple. Cheap. One vector per item.
- Cons: Blind to visual content. Two visually identical cooking videos with different captions end up far apart. A video captioned "💀" with no subtitles gets an essentially meaningless embedding.

**Option B: Text Embedding + CLIP Visual Embedding (Dual Vector)**
Store two vectors per item: a text embedding AND a CLIP visual embedding from the thumbnail.
- Pros: Enables visual similarity search ("find more videos that look like this"). Cross-modal search (text query matches visual content). Visual clustering for content discovery.
- Cons: Two vector columns in the database. Two index builds. More complex retrieval logic (must search both and merge results). CLIP's 512-dimensional space is separate from OpenAI's 1,536-dimensional space — they're not directly comparable.
- Retrieval approach: "Late fusion" — search each embedding space independently, then merge and re-rank results. Simplest approach: interleave top-k from each, deduplicate.

**Option C: Single Multimodal Embedding**
Use a model that embeds text + image together into one vector space.
- Pros: One vector per item. Simpler retrieval. Captures cross-modal relationships jointly.
- Cons: Vendor dependency on the multimodal embedding model. Less flexibility to improve text and visual separately. Currently fewer proven options for production-quality multimodal embeddings.

**Selected approach**: Option B (dual vector) for maximum flexibility and experimentation surface. If empirical results show one vector dominates retrieval quality, simplify to single-vector in production.

### 4.1.4 Ontology Design

**Current state (V1)**: 8 facets with 9-29 labels each.

**Proposed revision for V0**: Reduce to 5 content-intrinsic facets. Remove facets that require user-context inference.

| Facet | Keep/Cut | Reasoning |
|-------|----------|-----------|
| **Topic** | KEEP | Core retrieval dimension. High text signal. 29 labels — consider reducing to 20 by merging low-frequency categories. |
| **Genre** | KEEP | Important for distinguishing format. 22 labels — appropriate granularity. |
| **Affect** | KEEP | Users think in emotional terms ("show me funny stuff"). 12 labels — good. |
| **Presentation Style** | KEEP | Strongly visual, high accuracy expected with vision analysis. 9 labels — good. |
| **Content Provenance** | KEEP | Critical for the "edit detection" use case. 8 labels — good. |
| **Communicative Intent** | CUT for V0 | High overlap with Genre (tutorial→inform, skit→entertain). Adds classification noise without proportional retrieval value. Revisit post-MVP. |
| **Creator Role** | CUT for V0 | Requires metadata not reliably available (follower count, verification). Better derived from Apify data heuristics than LLM classification. |
| **Viewer Orientation** | CUT for V0 | Cannot be classified from content alone — depends on user's intent, which varies. The agent infers this at query time from the query itself. |

**Experiment needed**: Compare 5-facet vs. 8-facet classification on the golden set. If the 3 removed facets consistently score below 60% F1, the cut is justified. If any scores above 75%, reconsider keeping it.

## 4.2 Model Selection Analysis

### 4.2.1 Vision / Classification Model

| Model | Input Cost (1M tokens) | Output Cost (1M tokens) | Video Support | Key Tradeoff |
|-------|----------------------|------------------------|---------------|-------------|
| Gemini 2.0 Flash | $0.10 | $0.40 | Yes (263 tok/s) | Cheapest. Deprecated June 2026. |
| Gemini 2.5 Flash | $0.30 | $2.50 | Yes | Good balance. Higher output cost due to reasoning. |
| Gemini 3 Flash | $0.50 | $3.00 | Yes | Best quality. Newest model. Moderate cost. |
| Gemini 3 Pro | $2.00 | $12.00 | Yes | Highest quality. 4-10x more expensive than Flash. |
| GPT-4o | ~$2.50 | ~$10.00 | Yes (via API) | Comparable quality to Gemini Pro. No Google Search grounding. |

**Recommendation**: Start experiments with **Gemini 3 Flash**. It's the best quality-to-cost ratio for a new model that won't be deprecated soon. If budget is a concern at scale, benchmark against Gemini 2.5 Flash — if quality difference is <5% on the golden set, use the cheaper model.

### 4.2.2 Embedding Model

| Model | Dimensions | Cost (1M tokens) | Key Property |
|-------|-----------|------------------|-------------|
| OpenAI text-embedding-3-small | 1,536 | $0.02 | Industry standard. Mature. Well-understood. |
| OpenAI text-embedding-3-large | 3,072 | $0.13 | Higher quality. 6.5x more expensive. Diminishing returns for most use cases. |
| Gemini text-embedding-004 | 768 | $0.00 (free tier) | Free for low volume. Smaller dimension = less storage. |

**Recommendation**: Stay with **text-embedding-3-small**. It's proven, cheap, and already integrated. Test Gemini's embedding model if you want to explore cost savings.

### 4.2.3 Visual Embedding Model

| Model | Dimensions | Cost | Key Property |
|-------|-----------|------|-------------|
| CLIP ViT-B/32 | 512 | Free (open source, local) | Standard baseline. Runs on CPU. |
| CLIP ViT-L/14 | 768 | Free (local) | Higher quality. Needs GPU for reasonable speed. |
| OpenCLIP ViT-G/14 (LAION-2B) | 1,024 | Free (local) | State of art for open CLIP. Heavy model. |

**Recommendation**: Start with **CLIP ViT-B/32** for experiments. It's the most widely tested, fastest to run, and sufficient for validating whether visual embeddings add value. Upgrade only if experiments show quality limitations.

---

# Part V: Execution Plan

## 5.1 Pre-Requisites Checklist

Before starting, ensure:
- [ ] Local dev environment running (FastAPI, Supabase, workbench)
- [ ] Apify API token active with sufficient credits
- [ ] Google AI Studio API key (for Gemini)
- [ ] OpenAI API key (for embeddings)
- [ ] Real TikTok data export available (your own, or a consenting test user's)
- [ ] Python environment with: `httpx`, `open-clip-torch`, `Pillow`, `numpy`, `pandas`, `scikit-learn`, `matplotlib`, `seaborn`, `hdbscan`
- [ ] FFmpeg installed (for optional keyframe experiments)

## 5.2 Day-by-Day Execution

### Day 1 (Monday): Data Profiling + Apify Validation

**Objective**: Establish empirical understanding of data quality and Apify reliability.

**Task 1.1 — Apify Data Profiler Script**
File: `workbench/scripts/apify_profiler.py`

Process 50-100 real TikTok URLs through Apify. For each response, record:
- Fill rate per field (caption, hashtags, creator, thumbnail_url, video_url, subtitle_links, music, play_count, like_count, comment_count, share_count, media_type)
- Caption length distribution (histogram)
- Hashtag count distribution
- Percentage with empty/emoji-only captions (regex: `^[\p{Emoji}\s]*$`)
- Percentage with video_url populated (critical for media download)
- Percentage with subtitle_links populated

**Task 1.2 — Scale Test**
Run 200 URLs, then 500 URLs. Measure:
- Wall-clock time per batch of 50
- Failure rate (URLs that return no data)
- Any rate limiting or timeout behavior
- Actual Apify cost from dashboard

**Task 1.3 — Video URL Stability Test**
For 10 items with video_urls, download the video immediately, then try again 1 hour later, then 6 hours later. Do the URLs expire? This determines whether you can decouple Apify enrichment from media download or must do them in the same pipeline step.

**Deliverables:**
- `workbench/data/apify_profile_report.json` — structured quality metrics
- `workbench/data/apify_raw_samples/` — 10-20 raw Apify responses for reference
- Written notes on findings and any surprises

### Day 2 (Tuesday): Vision Analysis Experimentation

**Objective**: Validate Gemini's ability to understand TikTok content from video and thumbnails.

**Task 2.1 — Gemini Video Analysis Prototype**
File: `workbench/scripts/gemini_video_analyzer.py`

For 15 diverse videos (curate for diversity: cooking, dance, meme, edit, talking head, slideshow, product review, comedy skit, educational, nature/aesthetic, before-after, ASMR, workout, news commentary, book recommendation):

1. Download the video from Apify's video_url
2. Upload to Gemini File API
3. Send analysis prompt requesting structured JSON output:
   - scene_descriptions (array of timestamped scene descriptions)
   - overall_summary
   - visual_elements (objects, people, settings)
   - text_on_screen (OCR)
   - audio_description
   - presentation_style_guess
   - entities_detected (people, places, products, brands, titles)

Record Gemini's response, token usage, latency, and cost for each.

**Task 2.2 — Thumbnail-Only Comparison**
For the same 15 videos, run Gemini vision analysis on just the thumbnail. Compare output quality side-by-side:
- How much information is captured in thumbnail-only vs. full-video?
- Which content types lose the most from thumbnail-only?
- Where is full-video essential (hypothesis: edits, multi-scene content, recipe steps)?

**Task 2.3 — Keyframe Extraction Test (Optional)**
For 5 of the 15 videos, extract keyframes using FFmpeg scene detection:
```bash
ffmpeg -i video.mp4 -vf "select='gt(scene,0.3)',showinfo" -vsync vfn frame_%04d.jpg
```
Compare: how many keyframes are extracted? Do they match the scene boundaries Gemini identified in full-video mode? Is the token count for N keyframe images greater or less than 263 × duration_seconds (the native video token cost)?

**Deliverables:**
- `workbench/data/vision_analysis_samples/` — JSON outputs for 15 videos (full-video + thumbnail-only)
- `workbench/data/vision_comparison_notes.md` — your qualitative assessment
- Cost and latency measurements

### Day 3 (Wednesday): Classification Pipeline + Ontology Revision

**Objective**: Build the classification system and validate/revise the ontology based on real data.

**Task 3.1 — Ontology Revision**
Based on Day 2's vision analysis outputs, evaluate each facet:
- Can Gemini reliably distinguish the labels within each facet?
- Are there content types in your 15 samples that don't fit any existing label?
- Which facets have high inter-label ambiguity (multiple labels seem equally valid)?

Produce a revised ontology (V2). Recommended starting point: 5 facets (Topic, Genre, Affect, Presentation Style, Content Provenance).

**Task 3.2 — Classification Prompt Engineering**
File: `workbench/scripts/classify_with_vision.py`

Build the two-stage classification:
1. Input: Gemini vision description (from Day 2) + Apify metadata
2. Classification prompt that includes the ontology definition, the vision description, and all text metadata
3. Gemini Flash text-only call for classification
4. Validate output through `validate_classification()`

Iterate on the prompt. Run on all 15 samples. Inspect every output manually. Adjust wording when the model misclassifies.

**Task 3.3 — Text-Only vs. Vision-Informed Comparison**
For the same 15 items, run classification with text-only input (no vision description). Compare per-facet accuracy. This quantifies the value of visual analysis for classification.

**Deliverables:**
- Updated `ONTOLOGY_V2` definition
- Classification script with validated prompt
- Comparison spreadsheet: text-only vs. vision-informed per facet per item

### Day 4 (Thursday): Embedding Architecture

**Objective**: Build dual-embedding pipeline (text + CLIP visual) and test retrieval quality.

**Task 4.1 — CLIP Visual Embedding Utility**
File: `workbench/scripts/clip_embedder.py`

```python
import open_clip
import torch
from PIL import Image

model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
tokenizer = open_clip.get_tokenizer('ViT-B-32')

def embed_image(image_path: str) -> list[float]:
    image = preprocess(Image.open(image_path)).unsqueeze(0)
    with torch.no_grad():
        features = model.encode_image(image)
        features /= features.norm(dim=-1, keepdim=True)
    return features[0].tolist()

def embed_text_clip(text: str) -> list[float]:
    tokens = tokenizer([text])
    with torch.no_grad():
        features = model.encode_text(tokens)
        features /= features.norm(dim=-1, keepdim=True)
    return features[0].tolist()
```

Test on your 15 sample thumbnails. Compute pairwise cosine similarity matrix. Verify: do visually similar content types cluster together?

**Task 4.2 — Enriched Text Embedding**
File: `workbench/scripts/enriched_embedder.py`

Build the enriched text fusion function that includes vision descriptions and classification labels. Generate embeddings for all 15 samples with both the basic fusion (Tier 1) and enriched fusion (Tier 2).

**Task 4.3 — Retrieval Quality Comparison**
Define 10 test queries with expected results from your 15 samples:
- "cooking tutorials" → should return cooking videos
- "funny animal content" → should return comedy pet videos
- "that video with the blue kitchen" → tests cross-modal (visual) retrieval
- "book recommendations" → tests entity-type retrieval
- etc.

Run each query against three retrieval configurations:
1. Basic text embedding only (Tier 1)
2. Enriched text embedding (Tier 2)
3. Hybrid: enriched text + CLIP visual (Tier 1 + Tier 2)

Measure recall@5 for each.

**Deliverables:**
- CLIP embedding utility
- Enriched text fusion function
- Retrieval comparison results (table of recall@5 per query per configuration)
- Similarity matrices and visualizations

### Day 5 (Friday): Golden Set + Evaluation Framework

**Objective**: Build the measurement infrastructure.

**Task 5.1 — Golden Set Construction**
File: `workbench/data/golden_set.json`

Select 50 items. For each, hand-label:
```json
{
  "media_event_id": "...",
  "platform_id": "...",
  "caption": "...",
  "thumbnail_url": "...",
  "expected_labels": {
    "topic": "food",
    "genre": "recipe",
    "affect": "satisfying",
    "presentation_style": "voiceover",
    "content_provenance": "original"
  },
  "expected_entities": [
    {"name": "Trader Joe's", "type": "brand"},
    {"name": "pasta carbonara", "type": "dish"}
  ],
  "test_queries": [
    "cooking tutorials",
    "pasta recipes",
    "that carbonara video"
  ]
}
```

Ensure diversity: at least 2-3 items per major topic, at least 1 per genre, at least 3 "hard cases" (emoji-only captions, fan edits, ambiguous content).

**Task 5.2 — Evaluation Harness**
File: `workbench/scripts/evaluate_pipeline.py`

Automated script that:
1. Runs classification pipeline over all golden set items
2. Computes per-facet precision, recall, F1
3. Runs all test queries, computes recall@5 and recall@10
4. Outputs a scorecard as JSON and human-readable markdown

**Task 5.3 — Baseline Measurement**
Run the evaluation harness with your current best configuration. This is your baseline scorecard. Every subsequent change is measured against this.

**Deliverables:**
- `workbench/data/golden_set.json` (50 labeled items)
- `workbench/scripts/evaluate_pipeline.py`
- `workbench/data/baseline_scorecard.md`

### Day 6 (Saturday): End-to-End Integration

**Objective**: Wire everything together and test the full two-tier pipeline.

**Task 6.1 — Tier 1 Pipeline Script**
File: `workbench/scripts/tier1_pipeline.py`

End-to-end Tier 1 processing for N items:
1. Parse URLs from export
2. Apify enrichment
3. Download thumbnails
4. Generate text embedding (basic fusion)
5. Generate CLIP visual embedding
6. Output structured results

Run on 50 items. Measure total time and cost.

**Task 6.2 — Deep Analyze Function (Tier 2 Prototype)**
File: `workbench/scripts/deep_analyze.py`

The function that will become the agent's `deep_analyze` tool:
1. Input: list of media_event_ids
2. Download videos
3. Gemini video analysis
4. Classification
5. Generate enriched text embedding
6. Return all results (ready for caching to DB)

Run on 15 items. Measure per-item time and cost.

**Task 6.3 — Agent Retrieval Integration Prototype**
Simulate the full two-tier agent flow:
1. User query → embed query (text + CLIP text encoder)
2. Tier 1 retrieval → search text embeddings + CLIP visual embeddings → candidate set
3. Filter candidates: already deep-processed? If not, run deep_analyze
4. Tier 2 re-rank: with enriched data, re-score candidates
5. Return final results

Test with 5 queries from the golden set. Does the two-tier flow produce better results than Tier 1 alone?

**Deliverables:**
- Tier 1 pipeline script with timing/cost report
- Deep analyze function with per-item metrics
- Agent flow prototype with end-to-end trace logs

### Day 7 (Sunday): Analysis, Decisions, Documentation

**Objective**: Synthesize all findings into production decisions.

**Task 7.1 — Compile All Scorecards**

You now have empirical data on:
- Apify data quality and reliability at scale
- Vision quality: thumbnail vs. full-video vs. keyframes
- Classification accuracy: text-only vs. vision-informed, 5-facet vs. 8-facet
- Embedding quality: basic vs. enriched vs. hybrid (text + CLIP)
- Retrieval quality: Tier 1 only vs. Tier 1 + Tier 2
- Cost per item for each pipeline step
- Latency per item for each pipeline step

**Task 7.2 — Make Production Decisions**

Based on the data, decide:
1. Which Gemini model for vision analysis? (Flash vs. Pro — quality vs. cost)
2. Full video or thumbnail for Tier 2? (Day 2 comparison answers this)
3. Thumbnail or skip visual for Tier 1? (depends on CLIP retrieval value)
4. Final ontology: which facets, how many labels?
5. Does CLIP visual embedding justify the added complexity? (Day 4 retrieval comparison)
6. What's the per-item cost model for credit pricing?
7. What's the target Tier 1 processing time for 100 items?

**Task 7.3 — Write Decision Document**
File: `docs/VISION_PIPELINE_DECISIONS.md`

For each decision: what was tested, what the data showed, what was decided, and why. This is your architectural decision record for the most complex part of the system.

**Task 7.4 — Port Plan**
Outline the work required to port the validated pipeline from workbench scripts into the production Lambda + agent architecture. Estimate: what's the remaining engineering work to ship this?

---

# Part VI: Success Criteria & Evaluation Standards

## 6.1 Quantitative Targets

| Metric | Target (V0) | How Measured |
|--------|------------|-------------|
| Classification F1 (Topic) | ≥ 0.80 | Golden set evaluation |
| Classification F1 (Genre) | ≥ 0.75 | Golden set evaluation |
| Classification F1 (Affect) | ≥ 0.70 | Golden set evaluation |
| Classification F1 (Presentation Style) | ≥ 0.80 | Golden set evaluation |
| Classification F1 (Content Provenance) | ≥ 0.70 | Golden set evaluation |
| Retrieval Recall@10 | ≥ 0.80 | Golden set test queries |
| Tier 1 processing time (100 items) | ≤ 3 minutes | Wall-clock measurement |
| Tier 1 cost per item | ≤ $0.005 | Apify + OpenAI + CLIP |
| Tier 2 cost per item | ≤ $0.02 | Gemini + OpenAI |
| Tier 2 latency per item | ≤ 5 seconds | Wall-clock (parallelized) |

## 6.2 Qualitative Targets

- Agent can answer "show me my [specific topic] content" and return relevant results for at least 8/10 test queries
- Agent can answer "what was that video about [specific entity]" and find the right item
- Agent can distinguish between content that is visually similar but topically different (e.g., a cooking video vs. a chemistry experiment, both showing someone mixing things in a bowl)
- Two-tier flow feels responsive — user doesn't notice the deep processing step as a significant delay

## 6.3 When to Stop Experimenting and Ship

The experiments in this plan are time-boxed to one week. At the end of the week, you ship with whatever configuration the data supports, even if it's not perfect. The Phase 1→2 gate is 20 users asking 5+ questions, not 95% F1 on all facets.

Perfectionism in the lab is the enemy of learning in production. Measure, decide, ship, iterate.

---

# Appendix A: Key References

**Foundational ML/AI:**
- Andrej Karpathy, "A Recipe for Training Neural Networks" (blog post, 2019) — the philosophical foundation for data-centric ML development
- Andrew Ng, "Data-Centric AI" (NeurIPS workshop, 2021) — the formal argument for prioritizing data quality over model sophistication

**Embeddings and Retrieval:**
- Radford et al., "Learning Transferable Visual Models From Natural Language Supervision" (CLIP paper, 2021) — the paper behind visual embeddings
- Johnson et al., "Billion-scale similarity search with GPUs" (FAISS paper, 2019) — the engineering of vector search at scale

**Content Classification:**
- IAB Tech Lab, "Content Taxonomy" (v3.0) — the advertising industry's content classification standard
- IPTC, "NewsCodes" — journalism's content classification standard
- Russell, "A Circumplex Model of Affect" (Journal of Personality and Social Psychology, 1980) — the model behind Attic's Affect facet

**Media Studies:**
- Katz, Blumler & Gurevitch, "Uses and Gratifications Research" (Public Opinion Quarterly, 1973) — why people consume media
- Jenkins, "Convergence Culture" (2006) — fan communities, remix culture, participatory media — relevant to understanding edits, duets, stitches

**Evaluation:**
- Manning, Raghavan & Schütze, "Introduction to Information Retrieval" (Cambridge, 2008) — Chapter 8 covers precision, recall, F-measure, and evaluation methodology for retrieval systems

# Appendix B: Glossary

| Term | Definition | Attic Context |
|------|-----------|---------------|
| **Embedding** | A fixed-size numerical vector representing the semantic content of an input | Text and visual embeddings are the foundation of Attic's search |
| **Cosine similarity** | Measure of angle between two vectors (1=identical, 0=unrelated) | Used by pgvector to rank search results |
| **F1 score** | Harmonic mean of precision and recall | Primary metric for classification quality |
| **Recall@k** | Percentage of relevant items appearing in the top-k search results | Primary metric for retrieval quality |
| **Golden set** | Manually labeled evaluation dataset with known correct answers | The "ruler" against which all pipeline changes are measured |
| **Tier 1 / Tier 2** | Light pass (upload time) vs. deep pass (query time) in the two-tier architecture | Attic's processing strategy |
| **VLM** | Vision-Language Model — processes both images and text | Gemini Flash is Attic's VLM |
| **CLIP** | Contrastive Language-Image Pre-training — creates shared embedding space for images and text | Powers Attic's visual similarity search |
| **Ontology** | A structured vocabulary of categories for classifying content | Attic's 5-facet classification system |
| **Facet** | One independent dimension of the ontology (e.g., Topic, Genre, Affect) | Each facet is a separate classification task |
| **Tier-1 label** | A validated label from the fixed ontology vocabulary | Drives collections, filtering, and aggregation |
| **Tier-2 micro-label** | A free-form label generated by the model, not in the fixed vocabulary | Drives discovery and ontology evolution |
| **Coarse-to-fine search** | Retrieval strategy that broadly filters first, then deeply analyzes the filtered set | Attic's two-tier query architecture |
| **Grounding** | Converting visual/audio information into text representations | Stage 1 of the classification pipeline |
| **Idempotent** | Safe to re-run without creating duplicates or corrupting state | Required for all pipeline steps |
