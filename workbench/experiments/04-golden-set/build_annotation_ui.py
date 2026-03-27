#!/usr/bin/env python
"""Generate a self-contained HTML annotation UI for the golden set.

Builds annotation templates from tiktok_favorites.json + apify_all_favorites.json
and produces an interactive annotation tool organized by collection.
Annotations save to localStorage and can be exported as JSON.

Usage:
    python workbench/experiments/04-golden-set/build_annotation_ui.py
    open workbench/data/golden_set_annotator.html
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "workbench" / "data"
FAVORITES_PATH = DATA_DIR / "tiktok_favorites.json"
APIFY_PATH = DATA_DIR / "apify_all_favorites.json"
OUTPUT_PATH = SCRIPT_DIR / "results" / "golden_set_annotator.html"

# Ontology labels for dropdowns
TOPIC_LABELS = [
    "", "food", "fashion", "beauty", "fitness", "travel", "music", "dance",
    "comedy", "education", "technology", "gaming", "sports", "pets", "art",
    "books", "movies_tv", "news", "politics", "science", "nature", "diy",
    "finance", "relationships", "parenting", "health", "career",
    "real_estate", "automotive", "other",
]

AFFECT_LABELS = [
    "", "funny", "wholesome", "sad", "angry", "nostalgic", "inspiring",
    "informative", "cringe", "satisfying", "scary", "relaxing", "shocking",
    "neutral",
]

GENRE_LABELS = [
    "", "tutorial", "review", "vlog", "skit", "storytime", "haul", "asmr",
    "challenge", "reaction", "compilation", "before_after", "day_in_life",
    "get_ready_with_me", "unboxing", "recipe", "workout", "news_commentary",
    "interview", "timelapse", "meme", "duet", "edit", "pov", "room_tour",
    "outfit_showcase", "ranking", "other",
]


# Collection config: difficulty, topic, affect, genre hints per collection
COLLECTION_CONFIG: dict[str, dict] = {
    "cooking":           {"difficulty": "easy",   "topic": "food",       "affect": "informative", "genre": "recipe",  "failure_modes": ["entity_extraction"]},
    "Food":              {"difficulty": "easy",   "topic": "food",       "affect": None,          "genre": None,      "failure_modes": ["entity_extraction"]},
    "Workout":           {"difficulty": "easy",   "topic": "fitness",    "affect": "informative", "genre": "workout", "failure_modes": ["entity_extraction"]},
    "startup building":  {"difficulty": "easy",   "topic": "career",     "affect": "informative", "genre": None,      "failure_modes": ["opinion_as_content"]},
    "Career":            {"difficulty": "easy",   "topic": "career",     "affect": "informative", "genre": None,      "failure_modes": ["opinion_as_content"]},
    "Edits":             {"difficulty": "hard",   "topic": None,         "affect": None,          "genre": "edit",    "failure_modes": ["audio_dependent", "low_text", "cultural_context"]},
    "music":             {"difficulty": "medium", "topic": "music",      "affect": None,          "genre": None,      "failure_modes": ["audio_dependent"]},
    "Art":               {"difficulty": "medium", "topic": "art",        "affect": None,          "genre": None,      "failure_modes": ["visual_only"]},
    "fight":             {"difficulty": "medium", "topic": None,         "affect": None,          "genre": None,      "failure_modes": ["visual_only"]},
    "Clothes":           {"difficulty": "medium", "topic": "fashion",    "affect": None,          "genre": None,      "failure_modes": ["visual_plus_entity"]},
    "Deep":              {"difficulty": "hard",   "topic": None,         "affect": None,          "genre": None,      "failure_modes": ["cultural_context", "opinion_as_content"]},
    "Cool":              {"difficulty": "hard",   "topic": None,         "affect": None,          "genre": None,      "failure_modes": ["multi_topic", "cultural_context"]},
    "Europe":            {"difficulty": "medium", "topic": "travel",     "affect": None,          "genre": None,      "failure_modes": ["entity_heavy"]},
    "Golf":              {"difficulty": "medium", "topic": "sports",     "affect": None,          "genre": None,      "failure_modes": ["sports_technique"]},
    "Tech":              {"difficulty": "medium", "topic": "technology", "affect": "informative", "genre": None,      "failure_modes": ["entity_heavy"]},
    "Movies TV n stuff": {"difficulty": "medium", "topic": "movies_tv",  "affect": None,          "genre": None,      "failure_modes": ["cultural_refs"]},
    "Hoops":             {"difficulty": "medium", "topic": "sports",     "affect": None,          "genre": None,      "failure_modes": ["sports"]},
    "attic":             {"difficulty": "hard",   "topic": None,         "affect": None,          "genre": None,      "failure_modes": ["meta_product_research"]},
}


def build_all_items() -> list[dict]:
    """Build annotation templates for all 394 items from raw sources."""
    favorites = json.loads(FAVORITES_PATH.read_text())
    apify_items = json.loads(APIFY_PATH.read_text())

    # Index Apify data by video ID
    apify_by_id: dict[str, dict] = {}
    for item in apify_items:
        vid_id = str(item.get("id", ""))
        if vid_id:
            apify_by_id[vid_id] = item

    all_items: list[dict] = []
    for coll_name, coll_data in favorites["collections"].items():
        config = COLLECTION_CONFIG.get(coll_name, {})
        difficulty = config.get("difficulty", "medium")
        topic_auto = config.get("topic")
        affect_auto = config.get("affect")
        genre_auto = config.get("genre")
        failure_modes = config.get("failure_modes", [])

        for video in coll_data["videos"]:
            vid_id = video["video_id"]
            apify = apify_by_id.get(vid_id, {})
            video_meta = apify.get("videoMeta") or {}
            music_meta = apify.get("musicMeta") or {}
            raw_hashtags = apify.get("hashtags") or []
            hashtags = [h["name"] if isinstance(h, dict) else str(h) for h in raw_hashtags]
            raw_comments = apify.get("comments") or []
            comments_top10 = [c.get("text", "") for c in raw_comments[:10]] if raw_comments else None

            item = {
                "id": vid_id,
                "url": video["url"],
                "creator": video["username"],
                "collection": coll_name,
                "apify": {
                    "caption": apify.get("text"),
                    "hashtags": hashtags if hashtags else None,
                    "music_metadata": music_meta.get("musicName"),
                    "duration_seconds": video_meta.get("duration"),
                    "is_slideshow": apify.get("isSlideshow", False),
                    "image_count": apify.get("imageCount"),
                    "subtitle_text": None,
                    "comments_top10": comments_top10,
                    "thumbnail_url": video_meta.get("coverUrl"),
                },
                "human": {
                    "description": "",
                    "search_queries": [],
                    "topic": topic_auto if topic_auto else "",
                    "affect": affect_auto if affect_auto else "",
                    "key_entities": [],
                    "save_reason": "",
                    "difficulty": difficulty,
                    "failure_modes": failure_modes,
                    "collection_source": coll_name,
                    "auto_topic": topic_auto,
                    "auto_genre": genre_auto,
                },
                "human_deep": None,
            }

            if difficulty == "hard":
                item["human_deep"] = {
                    "entities": [],
                    "per_slide": None,
                    "actual_audio": None,
                    "cultural_context": None,
                    "structured_type": None,
                    "structured_items": None,
                }

            all_items.append(item)

    return all_items


def main() -> None:
    items = build_all_items()
    items_json = json.dumps(items)
    topic_json = json.dumps(TOPIC_LABELS)
    affect_json = json.dumps(AFFECT_LABELS)
    genre_json = json.dumps(GENRE_LABELS)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Attic Golden Set Annotator</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'DM Sans', -apple-system, sans-serif; background: #F8F7F4; color: #1C1B18; display: flex; height: 100vh; overflow: hidden; }}

/* Sidebar */
.sidebar {{ width: 240px; background: #fff; border-right: 1px solid #E6E4DE; overflow-y: auto; flex-shrink: 0; }}
.sidebar h2 {{ padding: 16px; font-size: 15px; font-weight: 500; border-bottom: 1px solid #E6E4DE; position: sticky; top: 0; background: #fff; z-index: 1; }}
.coll-btn {{ display: flex; justify-content: space-between; align-items: center; width: 100%; padding: 10px 16px; border: none; background: none; cursor: pointer; font-size: 13px; text-align: left; border-bottom: 1px solid #F0EEE8; }}
.coll-btn:hover {{ background: #F0EEE8; }}
.coll-btn.active {{ background: #2C2926; color: #fff; }}
.coll-btn .count {{ font-size: 11px; opacity: 0.6; }}
.coll-btn .done {{ font-size: 11px; color: #4CAF50; font-weight: 500; }}
.coll-btn.active .done {{ color: #8f8; }}

/* Main */
.main {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}

/* Header */
.hdr {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: #fff; border-bottom: 1px solid #E6E4DE; flex-shrink: 0; }}
.hdr-left {{ display: flex; align-items: center; gap: 16px; }}
.prog {{ font-size: 13px; color: #9C9890; }}
.hdr-actions {{ display: flex; gap: 8px; }}
.btn {{ padding: 6px 14px; border: 1px solid #E6E4DE; border-radius: 6px; background: #fff; cursor: pointer; font-size: 13px; }}
.btn:hover {{ background: #F0EEE8; }}
.btn-primary {{ background: #2C2926; color: #fff; border-color: #2C2926; }}
.btn-primary:hover {{ background: #1C1B18; }}
.btn-sm {{ padding: 4px 10px; font-size: 12px; }}

/* Content */
.content {{ flex: 1; overflow-y: auto; padding: 20px; }}
.item-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 1200px; }}

/* Left: metadata */
.meta-col {{ display: flex; flex-direction: column; gap: 12px; }}
.card {{ background: #fff; border: 1px solid #E6E4DE; border-radius: 8px; padding: 16px; }}
.card h3 {{ font-size: 13px; color: #9C9890; margin-bottom: 8px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }}
.thumb {{ width: 100%; max-height: 300px; object-fit: contain; border-radius: 6px; background: #000; }}
.caption {{ font-size: 14px; line-height: 1.5; margin: 8px 0; }}
.meta-line {{ font-size: 12px; color: #9C9890; margin: 3px 0; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #F0EEE8; margin: 2px; }}
.tag.hard {{ background: #f8d7da; color: #721c24; }}
.tag.medium {{ background: #fff3cd; color: #856404; }}
.tag.easy {{ background: #d4edda; color: #155724; }}
.tiktok-link {{ display: inline-block; margin-top: 8px; padding: 6px 12px; background: #000; color: #fff; border-radius: 6px; font-size: 12px; text-decoration: none; }}
.tiktok-link:hover {{ background: #333; }}

/* Right: annotation */
.anno-col {{ display: flex; flex-direction: column; gap: 12px; }}
.field {{ margin-bottom: 12px; }}
.field label {{ display: block; font-size: 12px; font-weight: 500; margin-bottom: 4px; color: #2C2926; }}
.field .hint {{ font-size: 11px; color: #9C9890; margin-bottom: 4px; }}
.field input, .field textarea, .field select {{
  width: 100%; padding: 8px 10px; border: 1px solid #E6E4DE; border-radius: 6px;
  font-size: 13px; font-family: inherit; background: #fff;
}}
.field textarea {{ min-height: 60px; resize: vertical; }}
.field select {{ height: 34px; }}
.field input:focus, .field textarea:focus, .field select:focus {{
  outline: none; border-color: #2C2926;
}}
.auto-hint {{ font-size: 11px; color: #A06840; font-style: italic; }}
.annotated-indicator {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
.annotated-indicator.done {{ background: #4CAF50; }}
.annotated-indicator.empty {{ background: #E6E4DE; }}

/* Item nav within collection */
.item-nav {{ display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 16px; }}
.item-pip {{ width: 28px; height: 28px; border: 1px solid #E6E4DE; border-radius: 6px; background: #fff;
  cursor: pointer; font-size: 11px; display: flex; align-items: center; justify-content: center; }}
.item-pip:hover {{ background: #F0EEE8; }}
.item-pip.active {{ background: #2C2926; color: #fff; border-color: #2C2926; }}
.item-pip.annotated {{ border-color: #4CAF50; }}
.item-pip.active.annotated {{ background: #2E7D32; border-color: #2E7D32; }}

/* Deep annotation section */
.deep-section {{ border-top: 2px solid #f8d7da; padding-top: 12px; margin-top: 4px; }}
.deep-section h3 {{ color: #721c24; }}

/* Keyboard hints */
.kbd {{ display: inline-block; padding: 1px 5px; border: 1px solid #E6E4DE; border-radius: 3px; font-size: 11px; font-family: monospace; background: #F0EEE8; }}

/* Filter bar */
.filter-bar {{ display: flex; gap: 8px; align-items: center; }}
.filter-bar label {{ font-size: 12px; color: #9C9890; }}
</style>
</head>
<body>

<div class="sidebar" id="sidebar"></div>

<div class="main">
  <div class="hdr">
    <div class="hdr-left">
      <b>Golden Set Annotator</b>
      <span class="prog" id="prog"></span>
      <span style="font-size:11px;color:#9C9890">
        <span class="kbd">&larr;</span> <span class="kbd">&rarr;</span> navigate
        &nbsp;<span class="kbd">Cmd+S</span> export
      </span>
    </div>
    <div class="hdr-actions">
      <button class="btn" onclick="importAnnotations()">Import</button>
      <button class="btn btn-primary" onclick="exportAnnotations()">Export JSON</button>
    </div>
  </div>
  <div class="content" id="content"></div>
</div>

<input type="file" id="importFile" style="display:none" accept=".json" onchange="handleImport(event)">

<script>
const ITEMS = {items_json};
const TOPICS = {topic_json};
const AFFECTS = {affect_json};
const GENRES = {genre_json};

// Group items by collection
const COLLECTIONS = {{}};
ITEMS.forEach((item, idx) => {{
  const c = item.collection;
  if (!COLLECTIONS[c]) COLLECTIONS[c] = [];
  COLLECTIONS[c].push({{ ...item, _idx: idx }});
}});
const COLL_NAMES = Object.keys(COLLECTIONS);

// State
let currentColl = COLL_NAMES[0];
let currentItemIdx = 0;
let annotations = JSON.parse(localStorage.getItem('gs_annotations') || '{{}}');

function save() {{
  localStorage.setItem('gs_annotations', JSON.stringify(annotations));
}}

function getAnno(id) {{
  if (!annotations[id]) annotations[id] = {{}};
  return annotations[id];
}}

function isAnnotated(id) {{
  const a = annotations[id];
  return a && (a.description || a.search_queries || a.save_reason);
}}

function countAnnotated(collName) {{
  return COLLECTIONS[collName].filter(i => isAnnotated(i.id)).length;
}}

function totalAnnotated() {{
  return ITEMS.filter(i => isAnnotated(i.id)).length;
}}

// Render sidebar
function renderSidebar() {{
  const sb = document.getElementById('sidebar');
  let h = '<h2>Collections</h2>';
  COLL_NAMES.forEach(name => {{
    const items = COLLECTIONS[name];
    const done = countAnnotated(name);
    const active = name === currentColl ? ' active' : '';
    h += `<button class="coll-btn${{active}}" onclick="selectColl('${{name.replace(/'/g, "\\\\'")}}')">
      <span>${{name}}</span>
      <span>${{done ? `<span class="done">${{done}}/</span>` : ''}}<span class="count">${{items.length}}</span></span>
    </button>`;
  }});
  sb.innerHTML = h;
}}

function selectColl(name) {{
  currentColl = name;
  currentItemIdx = 0;
  renderSidebar();
  renderContent();
}}

function selectItem(idx) {{
  currentItemIdx = idx;
  renderContent();
}}

function renderContent() {{
  const items = COLLECTIONS[currentColl];
  const item = items[currentItemIdx];
  const anno = getAnno(item.id);
  const apify = item.apify || {{}};

  // Item pips
  let pips = '<div class="item-nav">';
  items.forEach((it, idx) => {{
    const active = idx === currentItemIdx ? ' active' : '';
    const ann = isAnnotated(it.id) ? ' annotated' : '';
    pips += `<button class="item-pip${{active}}${{ann}}" onclick="selectItem(${{idx}})" title="${{it.creator}}">${{idx + 1}}</button>`;
  }});
  pips += '</div>';

  // Thumbnail
  const thumbUrl = apify.thumbnail_url;
  const thumbHtml = thumbUrl
    ? `<img class="thumb" src="${{thumbUrl}}" alt="thumbnail" loading="lazy" onerror="this.style.display='none'">`
    : '<div style="height:100px;background:#F0EEE8;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#9C9890;font-size:12px">No thumbnail</div>';

  // Tags
  const diffClass = item.human.difficulty;
  const hashtags = (apify.hashtags || []).map(h => '#' + h).join(' ');
  const duration = apify.duration_seconds ? apify.duration_seconds + 's' : '?';
  const isSlideshow = apify.is_slideshow ? 'slideshow' : 'video';

  // Pre-fill hints
  const autoTopic = item.human.auto_topic;
  const autoGenre = item.human.auto_genre;
  const topicHint = autoTopic ? `Auto-filled: ${{autoTopic}} (verify or override)` : 'Needs manual — no auto-fill';
  const genreHint = autoGenre ? `Auto-filled: ${{autoGenre}} (verify or override)` : 'Optional — fill if obvious';
  const affectHint = item.human.affect ? `Hint: ${{item.human.affect}} (verify or override)` : 'Needs manual — no auto-fill';

  // Deep section
  let deepHtml = '';
  if (item.human_deep !== null) {{
    deepHtml = `
    <div class="card">
      <div class="deep-section">
        <h3>Deep Annotation (hard item)</h3>
        <div class="field">
          <label>Entities (detailed — name, type, relevance)</label>
          <div class="hint">List every identifiable entity: people, places, products, songs, brands, techniques, recipes, etc.</div>
          <textarea rows="4" data-field="deep_entities" oninput="updateField(this)">${{anno.deep_entities || ''}}</textarea>
        </div>
        <div class="field">
          <label>Per-slide content (if slideshow)</label>
          <textarea rows="3" data-field="deep_per_slide" oninput="updateField(this)">${{anno.deep_per_slide || ''}}</textarea>
        </div>
        <div class="field">
          <label>Actual audio (song/sound playing)</label>
          <textarea rows="2" data-field="deep_actual_audio" oninput="updateField(this)">${{anno.deep_actual_audio || ''}}</textarea>
        </div>
        <div class="field">
          <label>Cultural context (memes, trends, references)</label>
          <textarea rows="2" data-field="deep_cultural_context" oninput="updateField(this)">${{anno.deep_cultural_context || ''}}</textarea>
        </div>
        <div class="field">
          <label>Structured content type (recipe / list / tutorial steps / ranking)</label>
          <input type="text" data-field="deep_structured_type" oninput="updateField(this)" value="${{escAttr(anno.deep_structured_type || '')}}">
        </div>
        <div class="field">
          <label>Structured items (each item in the list/recipe/steps)</label>
          <textarea rows="3" data-field="deep_structured_items" oninput="updateField(this)">${{anno.deep_structured_items || ''}}</textarea>
        </div>
      </div>
    </div>`;
  }}

  const html = `
  ${{pips}}
  <div class="item-grid">
    <div class="meta-col">
      <div class="card">
        <h3>Item ${{currentItemIdx + 1}}/${{items.length}} — ${{currentColl}}</h3>
        ${{thumbHtml}}
        <div style="margin-top:8px">
          <span class="tag ${{diffClass}}">${{diffClass}}</span>
          <span class="tag">${{isSlideshow}}</span>
          <span class="tag">${{duration}}</span>
        </div>
        <a class="tiktok-link" href="${{item.url}}" target="_blank" rel="noopener">Open on TikTok &rarr;</a>
      </div>

      <div class="card">
        <h3>Apify Metadata</h3>
        <div class="caption">${{escHtml(apify.caption || '(no caption)')}}</div>
        <div class="meta-line"><b>Creator:</b> @${{item.creator}}</div>
        <div class="meta-line"><b>Hashtags:</b> ${{hashtags || '(none)'}}</div>
        <div class="meta-line"><b>Music:</b> ${{escHtml(apify.music_metadata || '(unknown)')}}</div>
        ${{apify.comments_top10 && apify.comments_top10.length ? `
        <div style="margin-top:8px">
          <b style="font-size:12px">Top Comments:</b>
          ${{apify.comments_top10.slice(0, 5).map(c => `<div class="meta-line" style="font-style:italic">"${{escHtml(c.substring(0, 120))}}"</div>`).join('')}}
        </div>` : ''}}
      </div>

      <div class="card">
        <h3>Failure Modes</h3>
        <div>${{(item.human.failure_modes || []).map(f => `<span class="tag">${{f}}</span>`).join('')}}</div>
      </div>
    </div>

    <div class="anno-col">
      <div class="card">
        <h3>Your Annotation</h3>

        <div class="field">
          <label>Description *</label>
          <div class="hint">2-3 sentences: what is this TikTok actually about? What's the point?</div>
          <textarea rows="3" data-field="description" oninput="updateField(this)">${{anno.description || ''}}</textarea>
        </div>

        <div class="field">
          <label>Search queries *</label>
          <div class="hint">1-3 queries you'd type to find this 6 months from now (comma-separated)</div>
          <input type="text" data-field="search_queries" oninput="updateField(this)"
            value="${{escAttr(anno.search_queries || '')}}" placeholder="e.g. grilled cheese recipe, that sandwich video">
        </div>

        <div class="field">
          <label>Topic</label>
          <div class="auto-hint">${{topicHint}}</div>
          <select data-field="topic" onchange="updateField(this)">
            ${{TOPICS.map(t => `<option value="${{t}}" ${{(anno.topic || item.human.topic) === t ? 'selected' : ''}}>${{t || '— select —'}}</option>`).join('')}}
          </select>
        </div>

        <div class="field">
          <label>Affect</label>
          <div class="auto-hint">${{affectHint}}</div>
          <select data-field="affect" onchange="updateField(this)">
            ${{AFFECTS.map(a => `<option value="${{a}}" ${{(anno.affect || item.human.affect) === a ? 'selected' : ''}}>${{a || '— select —'}}</option>`).join('')}}
          </select>
        </div>

        <div class="field">
          <label>Genre</label>
          <div class="auto-hint">${{genreHint}}</div>
          <select data-field="genre" onchange="updateField(this)">
            ${{GENRES.map(g => `<option value="${{g}}" ${{(anno.genre || item.human.auto_genre || '') === g ? 'selected' : ''}}>${{g || '— select —'}}</option>`).join('')}}
          </select>
        </div>

        <div class="field">
          <label>Key entities</label>
          <div class="hint">People, places, products, songs, brands mentioned (comma-separated)</div>
          <input type="text" data-field="key_entities" oninput="updateField(this)"
            value="${{escAttr(anno.key_entities || '')}}" placeholder="e.g. Gordon Ramsay, grilled cheese, sourdough">
        </div>

        <div class="field">
          <label>Save reason *</label>
          <div class="hint">Why did you save this? What would you come back for?</div>
          <textarea rows="2" data-field="save_reason" oninput="updateField(this)">${{anno.save_reason || ''}}</textarea>
        </div>
      </div>

      ${{deepHtml}}
    </div>
  </div>`;

  document.getElementById('content').innerHTML = html;
  document.getElementById('content').scrollTop = 0;
  updateProgress();
}}

function updateField(el) {{
  const item = COLLECTIONS[currentColl][currentItemIdx];
  const anno = getAnno(item.id);
  anno[el.dataset.field] = el.value;
  save();
  // Update pip annotation status
  const pip = document.querySelectorAll('.item-pip')[currentItemIdx];
  if (pip) {{
    if (isAnnotated(item.id)) pip.classList.add('annotated');
    else pip.classList.remove('annotated');
  }}
  updateProgress();
  renderSidebar();
}}

function updateProgress() {{
  const total = ITEMS.length;
  const done = totalAnnotated();
  document.getElementById('prog').textContent = `${{done}}/${{total}} annotated`;
}}

function escHtml(s) {{
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}}

function escAttr(s) {{
  return s.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}}

// Navigation
function prevItem() {{
  const items = COLLECTIONS[currentColl];
  if (currentItemIdx > 0) {{ currentItemIdx--; renderContent(); }}
  else {{
    // Go to previous collection
    const ci = COLL_NAMES.indexOf(currentColl);
    if (ci > 0) {{
      currentColl = COLL_NAMES[ci - 1];
      currentItemIdx = COLLECTIONS[currentColl].length - 1;
      renderSidebar();
      renderContent();
    }}
  }}
}}

function nextItem() {{
  const items = COLLECTIONS[currentColl];
  if (currentItemIdx < items.length - 1) {{ currentItemIdx++; renderContent(); }}
  else {{
    // Go to next collection
    const ci = COLL_NAMES.indexOf(currentColl);
    if (ci < COLL_NAMES.length - 1) {{
      currentColl = COLL_NAMES[ci + 1];
      currentItemIdx = 0;
      renderSidebar();
      renderContent();
    }}
  }}
}}

// Export: merge annotations back into template format
function exportAnnotations() {{
  const output = ITEMS.map(item => {{
    const anno = annotations[item.id] || {{}};
    const merged = JSON.parse(JSON.stringify(item));

    // Merge human fields
    if (anno.description) merged.human.description = anno.description;
    if (anno.search_queries) merged.human.search_queries = anno.search_queries.split(',').map(s => s.trim()).filter(Boolean);
    if (anno.topic) merged.human.topic = anno.topic;
    if (anno.affect) merged.human.affect = anno.affect;
    if (anno.genre) merged.human.genre = anno.genre;
    if (anno.key_entities) merged.human.key_entities = anno.key_entities.split(',').map(s => s.trim()).filter(Boolean);
    if (anno.save_reason) merged.human.save_reason = anno.save_reason;

    // Merge deep fields
    if (merged.human_deep !== null) {{
      if (anno.deep_entities) merged.human_deep.entities = anno.deep_entities.split('\\n').filter(Boolean);
      if (anno.deep_per_slide) merged.human_deep.per_slide = anno.deep_per_slide;
      if (anno.deep_actual_audio) merged.human_deep.actual_audio = anno.deep_actual_audio;
      if (anno.deep_cultural_context) merged.human_deep.cultural_context = anno.deep_cultural_context;
      if (anno.deep_structured_type) merged.human_deep.structured_type = anno.deep_structured_type;
      if (anno.deep_structured_items) merged.human_deep.structured_items = anno.deep_structured_items.split('\\n').filter(Boolean);
    }}

    return merged;
  }});

  const blob = new Blob([JSON.stringify(output, null, 2)], {{ type: 'application/json' }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'golden_set_annotated.json';
  a.click();
}}

// Import previous annotations
function importAnnotations() {{
  document.getElementById('importFile').click();
}}

function handleImport(event) {{
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {{
    try {{
      const data = JSON.parse(e.target.result);

      // Handle two formats: raw annotations dict or full template array
      if (Array.isArray(data)) {{
        // Full template — extract annotations from human fields
        data.forEach(item => {{
          const anno = {{}};
          const h = item.human || {{}};
          if (h.description) anno.description = h.description;
          if (h.search_queries && h.search_queries.length) anno.search_queries = h.search_queries.join(', ');
          if (h.topic && h.topic !== item.human?.auto_topic) anno.topic = h.topic;
          if (h.affect) anno.affect = h.affect;
          if (h.genre) anno.genre = h.genre;
          if (h.key_entities && h.key_entities.length) anno.key_entities = h.key_entities.join(', ');
          if (h.save_reason) anno.save_reason = h.save_reason;

          const d = item.human_deep;
          if (d) {{
            if (d.entities && d.entities.length) anno.deep_entities = d.entities.join('\\n');
            if (d.per_slide) anno.deep_per_slide = d.per_slide;
            if (d.actual_audio) anno.deep_actual_audio = d.actual_audio;
            if (d.cultural_context) anno.deep_cultural_context = d.cultural_context;
            if (d.structured_type) anno.deep_structured_type = d.structured_type;
            if (d.structured_items && d.structured_items.length) anno.deep_structured_items = d.structured_items.join('\\n');
          }}

          if (Object.keys(anno).length) annotations[item.id] = anno;
        }});
      }} else {{
        // Raw annotations dict
        Object.assign(annotations, data);
      }}

      save();
      renderSidebar();
      renderContent();
      alert(`Imported annotations for ${{Object.keys(annotations).length}} items`);
    }} catch (err) {{
      alert('Failed to parse JSON: ' + err.message);
    }}
  }};
  reader.readAsText(file);
}}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {{
  // Don't intercept when typing in inputs
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

  if (e.key === 'ArrowLeft') {{ e.preventDefault(); prevItem(); }}
  if (e.key === 'ArrowRight') {{ e.preventDefault(); nextItem(); }}
  if ((e.metaKey || e.ctrlKey) && e.key === 's') {{ e.preventDefault(); exportAnnotations(); }}
}});

// Init
renderSidebar();
renderContent();
</script>
</body>
</html>"""

    OUTPUT_PATH.write_text(html)
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {len(items)} items across {len(set(i['collection'] for i in items))} collections")
    print(f"\nOpen in browser:")
    print(f"  open {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
