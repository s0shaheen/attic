# Gemma 4 vs Gemini Flash — Tier 2 Benchmark Results

**Model A:** `gemini-3-flash-preview` (reference)
**Model B:** `gemma-4-31b-it` (challenger)
**Items:** 55

## 1. Classification Agreement (Model A as reference)

| Facet                | N   | Exact Match | Agreement % |
| -------------------- | --- | ----------- | ----------- |
| topic                | 26  | 20          | 76.9%       |
| genre                | 26  | 16          | 61.5%       |
| communicative_intent | 26  | 19          | 73.1%       |
| creator_role         | 26  | 13          | 50.0%       |
| viewer_orientation   | 26  | 18          | 69.2%       |
| content_provenance   | 26  | 21          | 80.8%       |
| affect               | 26  | 17          | 65.4%       |
| presentation_style   | 26  | 18          | 69.2%       |
| **Overall**          | 208 | 142         | **68.3%**   |

### Notable Disagreements

**topic:**

- `7418683486002842912`: gemini-3-flash-preview=sports, gemma-4-31b-it=comedy
- `7467647308981620011`: gemini-3-flash-preview=news, gemma-4-31b-it=travel
- `7485552618840935710`: gemini-3-flash-preview=movies_tv, gemma-4-31b-it=comedy

**genre:**

- `7283533643769777441`: gemini-3-flash-preview=compilation, gemma-4-31b-it=other
- `7319866290590502177`: gemini-3-flash-preview=ranking, gemma-4-31b-it=compilation
- `7394372442073976110`: gemini-3-flash-preview=compilation, gemma-4-31b-it=edit

**communicative_intent:**

- `7292204605306473729`: gemini-3-flash-preview=document, gemma-4-31b-it=inspire
- `7389315780392865066`: gemini-3-flash-preview=document, gemma-4-31b-it=inspire
- `7467647308981620011`: gemini-3-flash-preview=inform, gemma-4-31b-it=entertain

**creator_role:**

- `7292204605306473729`: gemini-3-flash-preview=professional, gemma-4-31b-it=amateur
- `7319866290590502177`: gemini-3-flash-preview=influencer, gemma-4-31b-it=amateur
- `7372382721848692014`: gemini-3-flash-preview=professional, gemma-4-31b-it=amateur

**viewer_orientation:**

- `7372382721848692014`: gemini-3-flash-preview=passive_consumption, gemma-4-31b-it=social_sharing
- `7418511628473355552`: gemini-3-flash-preview=emotional_regulation, gemma-4-31b-it=inspiration_saving
- `7467647308981620011`: gemini-3-flash-preview=passive_consumption, gemma-4-31b-it=social_sharing

**content_provenance:**

- `7283533643769777441`: gemini-3-flash-preview=clip, gemma-4-31b-it=original
- `7394372442073976110`: gemini-3-flash-preview=repost, gemma-4-31b-it=original
- `7405643343918599455`: gemini-3-flash-preview=original, gemma-4-31b-it=repost

**affect:**

- `7292204605306473729`: gemini-3-flash-preview=satisfying, gemma-4-31b-it=wholesome
- `7378272396303715589`: gemini-3-flash-preview=nostalgic, gemma-4-31b-it=satisfying
- `7394372442073976110`: gemini-3-flash-preview=nostalgic, gemma-4-31b-it=satisfying

**presentation_style:**

- `7283533643769777441`: gemini-3-flash-preview=voiceover, gemma-4-31b-it=text_overlay
- `7292204605306473729`: gemini-3-flash-preview=text_overlay, gemma-4-31b-it=slideshow
- `7372382721848692014`: gemini-3-flash-preview=cinematic, gemma-4-31b-it=text_overlay

## 2. Cost Comparison

| Metric         | Model A  | Model B  |
| -------------- | -------- | -------- |
| Perceive mean  | $0.00192 | $0.00000 |
| Classify mean  | $0.00074 | $0.00000 |
| Total run cost | $0.1415  | $0.0000  |

### Cost by Media Type

| Type             | Model A (P+C) | Model B (P+C) |
| ---------------- | ------------- | ------------- |
| tiktok_image     | $0.00111      | $0.00000      |
| tiktok_slideshow | $0.00289      | $0.00000      |
| tiktok_video     | $0.00261      | $0.00000      |

## 3. Latency Comparison

| Metric          | Model A | Model B  |
| --------------- | ------- | -------- |
| Perceive mean   | 30540ms | 73859ms  |
| Perceive median | 26774ms | 72502ms  |
| Perceive p95    | 55046ms | 111966ms |
| Classify mean   | 7141ms  | 42357ms  |
| Classify median | 7035ms  | 42434ms  |
| Classify p95    | 8852ms  | 48738ms  |

## 4. Schema Validity

| Metric                | Model A       | Model B        |
| --------------------- | ------------- | -------------- |
| Valid JSON + ontology | 53/55 (98.1%) | 28/28 (100.0%) |
| Perceive errors       | 2             | 0              |
| Classify errors       | 1             | 0              |
| Video upload rate     | 38/39         | 0/15           |

## 5. Token Usage

| Metric                          | Model A | Model B |
| ------------------------------- | ------- | ------- |
| Perceive input tokens (mean)    | 10290   | 2200    |
| Perceive output tokens (mean)   | 2227    | 1472    |
| Perceive thoughts tokens (mean) | 0       | 920     |
| Classify input tokens (mean)    | 4040    | 3593    |
| Classify output tokens (mean)   | 830     | 708     |
| Classify thoughts tokens (mean) | 0       | 817     |
