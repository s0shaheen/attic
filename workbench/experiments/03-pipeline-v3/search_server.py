#!/usr/bin/env python
"""Lightweight search server for testing retrieval on the golden set.

Serves a browser UI where you can type queries and see ranked results
from both embedding variants (raw vs enriched) side-by-side. Supports
filtering by topic, genre, and affect.

Usage:
    python workbench/experiments/03-pipeline-v3/search_server.py
    # Opens http://localhost:8899
"""
import json
import math
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / "workbench" / ".env")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"
AGENT_MODEL = "claude-haiku-4-5-20251001"

SCRIPT_DIR = Path(__file__).resolve().parent
INDEX_PATH = SCRIPT_DIR / "results" / "search_index.json"
PORT = 8899


def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_query(text: str) -> list[float]:
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={"input": text, "model": EMBEDDING_MODEL},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def search(query_embedding: list[float], items: list[dict],
           variant: str, top_k: int = 20,
           topic_filter: str | None = None,
           genre_filter: str | None = None) -> list[dict]:
    key = f"embedding_{variant}"
    results = []
    for item in items:
        emb = item.get(key)
        if not emb:
            continue

        # Apply filters
        if topic_filter and item.get("topic_primary") != topic_filter:
            continue
        if genre_filter and item.get("genre") != genre_filter:
            continue

        score = cosine_sim(query_embedding, emb)
        results.append({**item, "_score": score})

    results.sort(key=lambda x: x["_score"], reverse=True)
    return results[:top_k]


# ── Agent ──────────────────────────────────────────────────────────────────

AGENT_TOOLS = [
    {
        "name": "search_items",
        "description": "Semantic search across saved TikToks. Returns items ranked by relevance to the query. Use this as your primary search tool. You can optionally filter by topic or genre.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query — describe what you're looking for"},
                "topic_filter": {"type": "string", "description": "Optional: filter to a specific topic (food, fashion, fitness, travel, music, technology, sports, movies_tv, career, health, comedy, art, politics, etc.)"},
                "genre_filter": {"type": "string", "description": "Optional: filter to a specific genre (tutorial, edit, recipe, review, vlog, ranking, skit, workout, etc.)"},
                "top_k": {"type": "integer", "description": "Number of results to return (default 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_item_details",
        "description": "Get full details for a specific item by ID — entities, structured content, subtitles, scene breakdowns, all classification facets. Use after search to dig deeper into a specific result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "The video ID to look up"},
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "get_collection_stats",
        "description": "Get aggregate statistics about the saved content — topic distribution, genre distribution, top creators, collection sizes. Use for broad questions about the user's library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stat_type": {
                    "type": "string",
                    "enum": ["topics", "genres", "collections", "creators", "affects"],
                    "description": "What kind of stats to return",
                },
            },
            "required": ["stat_type"],
        },
    },
]

AGENT_SYSTEM = """You are Attic, a personal content assistant for a TikTok saved library. The user has 106 saved TikToks that have been analyzed with perception, entity extraction, and classification.

Your job is to help users find specific videos, browse their collection, and answer questions about their saved content.

## Query Handling

- SPECIFIC RECALL ("that spider-man edit", "the grilled cheese video"): Use search_items with a descriptive query. Return the top match with its summary, entities, and a link.
- FILTERED BROWSING ("show me all food videos", "what cooking content do I have"): Use search_items with a topic/genre filter. Summarize what you find.
- AGGREGATION ("what topics do I save most", "how many fitness videos"): Use get_collection_stats first, then search if needed.
- DETAIL REQUESTS ("what restaurants were in that travel video", "what song was playing"): Use search_items to find the item, then get_item_details for full entity/audio info.
- LOCATION/ENTITY QUERIES ("things to do in Chicago", "Italian restaurants"): Search by the entity name directly — content is indexed by entities extracted from videos, not just by topic. A Chicago restaurant video is in the Food collection, not Travel. Always search broadly first before concluding nothing exists.

## Search Strategy

- ALWAYS try at least one broad search WITHOUT topic/genre filters first. Entity-rich content often crosses topic boundaries.
- If the first search returns low-relevance results (scores below 0.3), try rephrasing with different keywords.
- Use filters only to narrow down, not as your primary search strategy.
- When a query is broad (restaurants, shoes, movies), do MULTIPLE searches to cover different angles — e.g. search "restaurant recommendations" AND "food review" AND "best places to eat".

## Response Format — CRITICAL

Structure your response as JSON inside a <response> tag. The frontend parses this to render rich UI.

FORMAT:
<response>
{
  "intro": "Brief 1-sentence summary of what you found",
  "sections": [
    {
      "heading": "Section title — group by theme/context, not by video",
      "items": [
        {
          "text": "**Entity Name** — brief factual description of what this is and why it was recommended",
          "source_ids": ["video_id_1"],
          "source_label": "from @creator's video title/description"
        }
      ]
    }
  ],
  "follow_ups": [
    "Suggested follow-up query 1",
    "Suggested follow-up query 2",
    "Suggested follow-up query 3"
  ]
}
</response>

## Response Rules

1. ENTITY-FIRST: Structure around the THINGS (shoes, restaurants, movies, exercises), not the videos. The user saved videos for the reference content inside them.

2. GROUP BY CONTEXT: If you find restaurants, group by "Steakhouses", "Casual dining", "From food critics" — not "Video 1", "Video 2". If you find movies, group by "Directly recommended", "Featured in edits", "Referenced in commentary".

3. OBJECTIVE TONE: Be factual and structured. "Lardon (Logan Square) — Michelin-recognized charcuterie and sandwich shop, all meats cured in-house" not "This is an amazing place you'll love!"

4. SOURCE ATTRIBUTION: Each item has a source_label crediting the TikTok creator. Keep it brief: "from @creator's Chicago food guide" or "featured in @creator's ranking".

5. FOLLOW-UP SUGGESTIONS: Always include 3 follow-up queries. If the original query was broad, suggest narrower explorations. If specific, suggest related topics. These should be natural questions the user might ask next.

6. SOURCE IDS: Always include source_ids array with the video IDs so the frontend can build the gallery view. Each item can reference 1+ videos.

7. When the user asks about a specific video or creator (not entities), still use the same JSON format but structure sections around the video content.

8. If you only find 1-2 results, still use the format but with a single section. Include follow-ups that suggest broader searches."""


def run_agent_tool(tool_name: str, tool_input: dict, items: list[dict]) -> str:
    """Execute an agent tool and return the result as a string."""
    if tool_name == "search_items":
        q_emb = embed_query(tool_input["query"])
        results = search(
            q_emb, items, "enriched",
            top_k=tool_input.get("top_k", 10),
            topic_filter=tool_input.get("topic_filter"),
            genre_filter=tool_input.get("genre_filter"),
        )
        # Format for agent consumption — strip embeddings, include key fields
        formatted = []
        for r in results:
            formatted.append({
                "id": r["id"],
                "score": round(r["_score"], 4),
                "creator": r.get("creator"),
                "collection": r.get("collection"),
                "url": r.get("url"),
                "summary": r.get("summary", "")[:300],
                "takeaways": r.get("takeaways", [])[:2],
                "entities": [e for e in (r.get("entities") or []) if e.get("relevance") == "primary"][:6],
                "topic": r.get("topic_primary"),
                "genre": r.get("genre"),
                "affect": [a["label"] for a in (r.get("affect") or []) if a.get("tier") == "dominant"],
                "audio": r.get("audio_actual") if r.get("audio_match") else None,
                "duration": r.get("duration"),
                "thumbnail_url": r.get("thumbnail_url"),
            })
        return json.dumps(formatted, default=str)

    elif tool_name == "get_item_details":
        item_id = tool_input["item_id"]
        for item in items:
            if item["id"] == item_id:
                return json.dumps({
                    "id": item["id"],
                    "url": item.get("url"),
                    "creator": item.get("creator"),
                    "collection": item.get("collection"),
                    "caption": item.get("caption"),
                    "summary": item.get("summary"),
                    "takeaways": item.get("takeaways"),
                    "entities": item.get("entities"),
                    "structured_content": item.get("structured_content"),
                    "subtitle_text": (item.get("subtitle_text") or "")[:500],
                    "audio_actual": item.get("audio_actual"),
                    "audio_match": item.get("audio_match"),
                    "music_metadata": item.get("music_metadata"),
                    "topic_primary": item.get("topic_primary"),
                    "topic_secondary": item.get("topic_secondary"),
                    "genre": item.get("genre"),
                    "affect": item.get("affect"),
                    "viewer_orientation": item.get("viewer_orientation"),
                    "duration": item.get("duration"),
                    "thumbnail_url": item.get("thumbnail_url"),
                }, default=str)
        return json.dumps({"error": f"Item {item_id} not found"})

    elif tool_name == "get_collection_stats":
        from collections import Counter
        stat_type = tool_input["stat_type"]

        if stat_type == "topics":
            counts = Counter(i.get("topic_primary") for i in items if i.get("topic_primary"))
            return json.dumps({"topic_distribution": dict(counts.most_common())})
        elif stat_type == "genres":
            counts = Counter(i.get("genre") for i in items if i.get("genre"))
            return json.dumps({"genre_distribution": dict(counts.most_common())})
        elif stat_type == "collections":
            counts = Counter(i.get("collection") for i in items if i.get("collection"))
            return json.dumps({"collection_sizes": dict(counts.most_common())})
        elif stat_type == "creators":
            counts = Counter(i.get("creator") for i in items if i.get("creator"))
            return json.dumps({"top_creators": dict(counts.most_common(15))})
        elif stat_type == "affects":
            counts = Counter()
            for i in items:
                for a in (i.get("affect") or []):
                    if isinstance(a, dict) and a.get("tier") == "dominant":
                        counts[a["label"]] += 1
            return json.dumps({"dominant_affect_distribution": dict(counts.most_common())})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def run_agent(user_message: str, conversation: list[dict], items: list[dict]) -> dict:
    """Run the agent loop — Claude + tool use until final response."""
    messages = conversation + [{"role": "user", "content": user_message}]

    tool_calls_made = []
    max_turns = 6

    for _ in range(max_turns):
        # Retry with backoff on rate limits
        for attempt in range(5):
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": AGENT_MODEL,
                    "max_tokens": 2048,
                    "system": AGENT_SYSTEM,
                    "tools": AGENT_TOOLS,
                    "messages": messages,
                },
                timeout=60,
            )
            if resp.status_code == 429:
                import time
                retry_after = int(resp.headers.get("retry-after", (attempt + 1) * 10))
                print(f"    Rate limited, waiting {retry_after}s (attempt {attempt+1}/5)...")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            break
        else:
            return {"response": "Rate limited — please wait a moment and try again.", "tool_calls": [], "conversation": messages}
        result = resp.json()

        # Collect text and tool use blocks
        assistant_content = result.get("content", [])
        messages.append({"role": "assistant", "content": assistant_content})

        if result.get("stop_reason") == "end_turn":
            # Final response — extract text
            text = ""
            for block in assistant_content:
                if block.get("type") == "text":
                    text += block["text"]
            return {
                "response": text,
                "tool_calls": tool_calls_made,
                "conversation": messages,
            }

        # Handle tool use
        tool_results = []
        for block in assistant_content:
            if block.get("type") == "tool_use":
                tool_name = block["name"]
                tool_input = block["input"]
                tool_id = block["id"]

                tool_result = run_agent_tool(tool_name, tool_input, items)
                tool_calls_made.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "result_preview": tool_result[:200],
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": tool_result,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return {
        "response": "(Agent reached max turns without completing)",
        "tool_calls": tool_calls_made,
        "conversation": messages,
    }


# ── HTML UI ────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Attic Search Lab</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#F8F7F4;color:#1C1B18;padding:20px;max-width:1400px;margin:0 auto}
.header{margin-bottom:20px}
.header h1{font-size:20px;font-weight:500;margin-bottom:12px}
.tab-bar{display:flex;gap:4px;background:#F0EEE8;border-radius:6px;padding:2px;margin-bottom:16px;width:fit-content}
.tab-bar button{padding:8px 16px;border:none;background:none;border-radius:4px;cursor:pointer;font-size:13px;font-weight:500}
.tab-bar button.active{background:#2C2926;color:#fff}
.tab-content{display:none}.tab-content.active{display:block}
.search-bar{display:flex;gap:8px;margin-bottom:12px}
.search-bar input{flex:1;padding:10px 14px;border:1px solid #E6E4DE;border-radius:8px;font-size:14px;font-family:inherit}
.search-bar input:focus{outline:none;border-color:#2C2926}
.search-bar button{padding:10px 20px;background:#2C2926;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px}
.search-bar button:hover{background:#1C1B18}
.filters{display:flex;gap:12px;align-items:center;margin-bottom:16px;flex-wrap:wrap}
.filters label{font-size:12px;color:#9C9890}
.filters select{padding:4px 8px;border:1px solid #E6E4DE;border-radius:4px;font-size:12px}
.mode-toggle{display:flex;gap:4px;background:#F0EEE8;border-radius:6px;padding:2px}
.mode-toggle button{padding:6px 12px;border:none;background:none;border-radius:4px;cursor:pointer;font-size:12px}
.mode-toggle button.active{background:#2C2926;color:#fff}
.results-container{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.results-container.single{grid-template-columns:1fr}
.results-col h2{font-size:13px;color:#9C9890;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #E6E4DE}
.result{background:#fff;border:1px solid #E6E4DE;border-radius:8px;padding:14px;margin-bottom:8px;display:flex;gap:12px}
.result:hover{border-color:#2C2926}
.result .thumb{width:80px;height:80px;border-radius:6px;object-fit:cover;flex-shrink:0;background:#F0EEE8}
.result .body{flex:1;min-width:0}
.result .score{font-size:20px;font-weight:500;color:#2C2926;margin-bottom:2px}
.result .meta{font-size:11px;color:#9C9890;margin-bottom:4px}
.result .summary{font-size:13px;line-height:1.5;margin-bottom:6px}
.result .entities{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:4px}
.tag{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#F0EEE8}
.tag.topic{background:#E8F4FD;color:#1565C0}
.tag.genre{background:#F3E5F5;color:#7B1FA2}
.tag.affect{background:#FFF3E0;color:#E65100}
.tag.entity{background:#E8F5E9;color:#2E7D32}
.take{font-size:12px;color:#2C2926;font-style:italic;padding-left:6px;border-left:2px solid #E6E4DE;margin:4px 0}
a.tiktok{font-size:11px;color:#A06840;text-decoration:none}
.status{font-size:12px;color:#9C9890;margin-top:8px}
.comparison-badge{font-size:10px;padding:1px 5px;border-radius:3px;margin-left:4px}
.comparison-badge.better{background:#d4edda;color:#155724}
.comparison-badge.worse{background:#f8d7da;color:#721c24}
.comparison-badge.same{background:#F0EEE8;color:#9C9890}
.empty{text-align:center;padding:40px;color:#9C9890}
/* Chat styles */
.chat-container{max-width:800px;margin:0 auto}
.chat-messages{min-height:200px;max-height:70vh;overflow-y:auto;margin-bottom:12px;padding-bottom:12px}
.msg{margin-bottom:20px}
.msg.user .bubble{background:#2C2926;color:#fff;border-radius:12px 12px 4px 12px;padding:10px 14px;max-width:80%;margin-left:auto;font-size:14px}
.msg.assistant .content{max-width:100%}
.msg.assistant .intro{font-size:14px;color:#1C1B18;margin-bottom:12px;line-height:1.5}
.msg.assistant .section{background:#fff;border:1px solid #E6E4DE;border-radius:10px;padding:16px;margin-bottom:10px}
.msg.assistant .section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.msg.assistant .section h3{font-size:14px;font-weight:500;color:#1C1B18}
.gallery-btn{background:none;border:1px solid #E6E4DE;border-radius:6px;padding:4px 8px;cursor:pointer;display:flex;align-items:center;gap:4px;font-size:11px;color:#9C9890;transition:all 0.15s}
.gallery-btn:hover{border-color:#2C2926;color:#2C2926}
.gallery-btn svg{width:14px;height:14px}
.section-items{list-style:none}
.section-items li{padding:8px 0;border-bottom:1px solid #F0EEE8;font-size:13px;line-height:1.6}
.section-items li:last-child{border-bottom:none;padding-bottom:0}
.section-items li .source{font-size:11px;color:#9C9890;margin-top:2px}
.section-items li .source a{color:#A06840;text-decoration:none}
.follow-ups{display:flex;flex-wrap:wrap;gap:6px;margin-top:16px}
.follow-up{background:#F0EEE8;border:1px solid #E6E4DE;border-radius:20px;padding:6px 14px;font-size:12px;color:#2C2926;cursor:pointer;transition:all 0.15s}
.follow-up:hover{background:#E6E4DE;border-color:#2C2926}
.msg .tool-trace{font-size:11px;color:#9C9890;margin-top:8px}
.msg .tool-trace span{background:#F0EEE8;padding:1px 5px;border-radius:3px;margin-right:4px}
.chat-input{display:flex;gap:8px}
.chat-input input{flex:1;padding:10px 14px;border:1px solid #E6E4DE;border-radius:8px;font-size:14px;font-family:inherit}
.chat-input input:focus{outline:none;border-color:#2C2926}
.chat-input button{padding:10px 20px;background:#2C2926;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px}
.typing{color:#9C9890;font-size:13px;font-style:italic;padding:8px 0}
/* Gallery modal */
.gallery-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:1000;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity 0.2s}
.gallery-overlay.open{opacity:1;pointer-events:all}
.gallery-modal{background:#F8F7F4;border-radius:12px;width:90vw;max-width:900px;max-height:85vh;overflow-y:auto;padding:24px}
.gallery-modal h3{font-size:16px;font-weight:500;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center}
.gallery-modal .close-btn{background:none;border:none;font-size:20px;cursor:pointer;color:#9C9890;padding:4px 8px}
.gallery-modal .close-btn:hover{color:#1C1B18}
.gallery-section{margin-bottom:20px}
.gallery-section h4{font-size:13px;color:#9C9890;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px}
.gallery-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px}
.gallery-card{position:relative;border-radius:8px;overflow:hidden;aspect-ratio:9/16;background:#000;cursor:pointer;transition:transform 0.15s}
.gallery-card:hover{transform:scale(1.03)}
.gallery-card img{width:100%;height:100%;object-fit:cover}
.gallery-card .gc-label{position:absolute;bottom:0;left:0;right:0;background:linear-gradient(transparent,rgba(0,0,0,0.8));padding:8px;color:#fff;font-size:11px;line-height:1.3}
.gallery-card .gc-creator{opacity:0.7;font-size:10px}
/* Fallback plain text rendering */
.msg.assistant .bubble{background:#fff;border:1px solid #E6E4DE;border-radius:12px 12px 12px 4px;padding:14px;max-width:90%;font-size:14px;line-height:1.6}
.msg.assistant .bubble a{color:#A06840}
/* Mobile responsive */
@media(max-width:768px){
  body{padding:10px}
  .header h1{font-size:18px}
  .tab-bar button{padding:10px 14px;font-size:14px}
  .chat-container{max-width:100%}
  .chat-messages{max-height:60vh}
  .msg.user .bubble{max-width:90%;font-size:16px;padding:12px 16px}
  .msg.assistant .intro{font-size:16px}
  .msg.assistant .section{padding:14px}
  .msg.assistant .section h3{font-size:16px}
  .section-items li{padding:10px 0;font-size:15px;line-height:1.7}
  .section-items li .source{font-size:13px}
  .gallery-btn{padding:6px 10px;font-size:13px}
  .follow-ups{gap:8px;margin-top:20px}
  .follow-up{padding:10px 16px;font-size:14px}
  .chat-input{gap:6px}
  .chat-input input{padding:14px 16px;font-size:16px;border-radius:10px}
  .chat-input button{padding:14px 20px;font-size:16px;border-radius:10px}
  .gallery-modal{width:95vw;padding:16px;max-height:90vh}
  .gallery-grid{grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px}
  .gallery-card .gc-label{font-size:10px;padding:6px}
  .msg .tool-trace{font-size:10px}
  .filters{flex-direction:column;align-items:flex-start}
  .results-container{grid-template-columns:1fr}
}
</style>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
</head><body>
<div class="header">
  <h1>Attic Search Lab</h1>
  <div class="tab-bar">
    <button class="active" onclick="switchTab('agent')">Agent</button>
    <button onclick="switchTab('search')">Raw Search</button>
  </div>
</div>

<!-- Gallery overlay -->
<div class="gallery-overlay" id="gallery-overlay" onclick="if(event.target===this)closeGallery()">
  <div class="gallery-modal" id="gallery-content"></div>
</div>

<!-- Agent Tab -->
<div id="tab-agent" class="tab-content active">
  <div class="chat-container">
    <div class="chat-messages" id="chat-messages">
      <div class="msg assistant"><div class="content">
        <div class="intro">Hey! I'm Attic — I can help you find and explore your saved TikToks.</div>
        <div class="follow-ups">
          <button class="follow-up" onclick="sendFollowUp('What restaurants have I saved?')">What restaurants have I saved?</button>
          <button class="follow-up" onclick="sendFollowUp('Find shoe recommendations')">Find shoe recommendations</button>
          <button class="follow-up" onclick="sendFollowUp('Show me all movie recommendations')">Movie recommendations</button>
          <button class="follow-up" onclick="sendFollowUp('What topics do I save the most?')">What topics do I save most?</button>
          <button class="follow-up" onclick="sendFollowUp('That video about the robot in Miami')">That robot in Miami video</button>
        </div>
      </div></div>
    </div>
    <div class="chat-input">
      <input type="text" id="chat-query" placeholder="Ask about your saved TikToks..." autofocus>
      <button onclick="sendChat()">Send</button>
    </div>
  </div>
</div>

<!-- Search Tab -->
<div id="tab-search" class="tab-content">
  <div class="search-bar">
    <input type="text" id="query" placeholder="Search your saved TikToks...">
    <button onclick="doSearch()">Search</button>
  </div>
  <div class="filters">
    <div class="mode-toggle">
      <button id="mode-enriched" class="active" onclick="setMode('enriched')">Tier 2</button>
      <button id="mode-tier1" onclick="setMode('tier1')">Tier 1</button>
      <button id="mode-raw" onclick="setMode('raw')">Raw</button>
      <button id="mode-compare" onclick="setMode('compare')">T1 vs T2</button>
    </div>
    <label>Topic: <select id="f-topic"><option value="">All</option></select></label>
    <label>Genre: <select id="f-genre"><option value="">All</option></select></label>
    <span id="status" class="status"></span>
  </div>
</div>
<div id="results"></div>
</div><!-- end tab-search -->

<script>
let mode = 'enriched';
let lastResults = null;

document.getElementById('query').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});

function setMode(m) {
  mode = m;
  document.querySelectorAll('.mode-toggle button').forEach(b => b.classList.remove('active'));
  document.getElementById('mode-' + m).classList.add('active');
  if (lastResults) renderResults(lastResults);
}

async function doSearch() {
  const q = document.getElementById('query').value.trim();
  if (!q) return;
  const topic = document.getElementById('f-topic').value;
  const genre = document.getElementById('f-genre').value;
  document.getElementById('status').textContent = 'Searching...';

  const params = new URLSearchParams({q, mode: 'compare', top_k: '20'});
  if (topic) params.set('topic', topic);
  if (genre) params.set('genre', genre);

  const resp = await fetch('/search?' + params);
  const data = await resp.json();
  lastResults = data;
  document.getElementById('status').textContent =
    `T2:${data.enriched.length} / T1:${data.tier1.length} / Raw:${data.raw.length} — ${data.embed_ms}ms`;
  renderResults(data);
}

function renderResults(data) {
  const el = document.getElementById('results');

  if (mode === 'compare') {
    el.className = 'results-container';
    el.innerHTML = `
      <div class="results-col">
        <h2>Tier 1 (keyframes, $0.001/item)</h2>
        ${data.tier1.map((r, i) => resultCard(r, i, data.enriched)).join('')}
      </div>
      <div class="results-col">
        <h2>Tier 2 (full video, $0.003/item)</h2>
        ${data.enriched.map((r, i) => resultCard(r, i, data.tier1)).join('')}
      </div>`;
  } else {
    const items = mode === 'enriched' ? data.enriched : mode === 'tier1' ? data.tier1 : data.raw;
    const label = mode === 'enriched' ? 'Tier 2 (full video)' : mode === 'tier1' ? 'Tier 1 (keyframes)' : 'Raw (caption only)';
    el.className = 'results-container single';
    el.innerHTML = `
      <div class="results-col" style="max-width:800px">
        <h2>${label} — ${items.length} results</h2>
        ${items.length ? items.map((r, i) => resultCard(r, i)).join('') : '<div class="empty">No results</div>'}
      </div>`;
  }
}

function resultCard(item, rank, otherResults) {
  const score = (item._score * 100).toFixed(1);
  const entities = (item.entities || []).filter(e => e.relevance === 'primary').slice(0, 6);
  const affect = (item.affect || []).filter(a => a.tier === 'dominant');
  const takeaway = (item.takeaways || [])[0] || '';

  // Comparison badge
  let badge = '';
  if (otherResults) {
    const otherRank = otherResults.findIndex(r => r.id === item.id);
    if (otherRank === -1) badge = '<span class="comparison-badge better">unique</span>';
    else if (otherRank > rank + 3) badge = `<span class="comparison-badge better">+${otherRank - rank} spots</span>`;
    else if (otherRank < rank - 3) badge = `<span class="comparison-badge worse">${otherRank - rank} spots</span>`;
  }

  return `<div class="result">
    ${item.thumbnail_url ? `<img class="thumb" src="${item.thumbnail_url}" loading="lazy" onerror="this.style.display='none'">` : ''}
    <div class="body">
      <div class="score">${score}% ${badge}</div>
      <div class="meta">
        @${item.creator} · ${item.collection} · ${item.duration || '?'}s
        <a class="tiktok" href="${item.url}" target="_blank">Open TikTok</a>
      </div>
      <div class="entities">
        ${item.topic_primary ? `<span class="tag topic">${item.topic_primary}</span>` : ''}
        ${item.topic_secondary ? `<span class="tag topic">${item.topic_secondary}</span>` : ''}
        ${item.genre ? `<span class="tag genre">${item.genre}</span>` : ''}
        ${affect.map(a => `<span class="tag affect">${a.label}</span>`).join('')}
      </div>
      <div class="summary">${(item.summary || item.caption || '').substring(0, 200)}${(item.summary || '').length > 200 ? '...' : ''}</div>
      ${takeaway ? `<div class="take">${takeaway.substring(0, 150)}</div>` : ''}
      <div class="entities">
        ${entities.map(e => `<span class="tag entity">${e.name}</span>`).join('')}
      </div>
      ${item.audio_actual && item.audio_match ? `<div class="meta">♫ ${item.audio_actual}</div>` : ''}
    </div>
  </div>`;
}

// Populate filter dropdowns on load
fetch('/meta').then(r => r.json()).then(data => {
  const tSel = document.getElementById('f-topic');
  data.topics.forEach(t => { const o = document.createElement('option'); o.value = t; o.textContent = t; tSel.appendChild(o); });
  const gSel = document.getElementById('f-genre');
  data.genres.forEach(g => { const o = document.createElement('option'); o.value = g; o.textContent = g; gSel.appendChild(o); });
});

// Tab switching
function switchTab(tab) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-bar button').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  event.target.classList.add('active');
  if (tab === 'agent') document.getElementById('chat-query').focus();
  else document.getElementById('query').focus();
}

// Agent chat
let conversation = [];
let itemIndex = {}; // video_id -> item data for gallery

// Load item index for gallery thumbnails
fetch('/items').then(r=>r.json()).then(data=>{
  data.forEach(i=>{ itemIndex[i.id]=i; });
});

document.getElementById('chat-query').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

function sendFollowUp(q) {
  document.getElementById('chat-query').value = q;
  sendChat();
}

async function sendChat() {
  const input = document.getElementById('chat-query');
  const q = input.value.trim();
  if (!q) return;
  input.value = '';
  input.disabled = true;

  const msgs = document.getElementById('chat-messages');
  msgs.innerHTML += `<div class="msg user"><div class="bubble">${escHtml(q)}</div></div>`;
  msgs.innerHTML += `<div class="typing" id="typing">Searching your library...</div>`;
  msgs.scrollTop = msgs.scrollHeight;

  try {
    const resp = await fetch('/agent', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: q, conversation: conversation}),
    });
    if (!resp.ok) throw new Error('Server error: ' + resp.status);
    const data = await resp.json();
    document.getElementById('typing')?.remove();

    // Tool trace
    let trace = '';
    if (data.tool_calls && data.tool_calls.length) {
      trace = `<div class="tool-trace">${data.tool_calls.map(tc =>
        `<span>${tc.tool}(${Object.values(tc.input).filter(v=>typeof v==='string').join(', ').substring(0,40)})</span>`
      ).join(' &rarr; ')}</div>`;
    }

    // Try to parse structured response
    const structured = parseStructuredResponse(data.response);

    if (structured) {
      msgs.innerHTML += `<div class="msg assistant"><div class="content">${renderStructured(structured)}</div>${trace}</div>`;
    } else {
      // Fallback: plain text with markdown
      let html = markdownToHtml(data.response);
      msgs.innerHTML += `<div class="msg assistant"><div class="bubble">${html}</div>${trace}</div>`;
    }

    conversation = data.conversation || [];
  } catch (err) {
    document.getElementById('typing')?.remove();
    msgs.innerHTML += `<div class="msg assistant"><div class="bubble" style="color:#721c24;background:#fff">Error: ${err.message || 'Unknown error'}</div></div>`;
  }
  input.disabled = false;
  input.focus();
  msgs.scrollTop = msgs.scrollHeight;
}

function parseStructuredResponse(text) {
  // Extract JSON from <response> tags
  const start = text.indexOf('<response>');
  const end = text.indexOf('</response>');
  if (start === -1 || end === -1) return null;
  const inner = text.substring(start + 10, end).trim();
  try {
    return JSON.parse(inner);
  } catch(e) {
    // Try to fix common JSON issues
    try {
      const cleaned = inner.replace(/,\\s*}/g, '}').replace(/,\\s*]/g, ']');
      return JSON.parse(cleaned);
    } catch(e2) { return null; }
  }
}

const gallerySvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="10" rx="1.5"/><rect x="14" y="3" width="7" height="10" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/><rect x="14" y="16" width="7" height="5" rx="1.5"/></svg>`;

function renderStructured(data) {
  let html = '';

  // Intro
  if (data.intro) {
    html += `<div class="intro">${markdownToHtml(data.intro)}</div>`;
  }

  // Sections
  if (data.sections) {
    data.sections.forEach((section, si) => {
      const sectionIds = [];
      (section.items || []).forEach(item => {
        (item.source_ids || []).forEach(id => { if (!sectionIds.includes(id)) sectionIds.push(id); });
      });
      const galleryData = JSON.stringify(sectionIds).replace(/"/g, '&quot;');

      html += `<div class="section">
        <div class="section-head">
          <h3>${escHtml(section.heading || '')}</h3>
          ${sectionIds.length ? `<button class="gallery-btn" onclick='openGallery(${JSON.stringify(section.heading || "Sources").replace(/'/g,"\\'")},[${sectionIds.map(id=>`"${id}"`).join(",")}])'>
            ${gallerySvg} ${sectionIds.length} source${sectionIds.length>1?'s':''}
          </button>` : ''}
        </div>
        <ul class="section-items">
          ${(section.items || []).map(item => `<li>
            ${markdownToHtml(item.text || '')}
            ${item.source_label ? `<div class="source">${escHtml(item.source_label)}</div>` : ''}
          </li>`).join('')}
        </ul>
      </div>`;
    });
  }

  // Follow-ups
  if (data.follow_ups && data.follow_ups.length) {
    html += `<div class="follow-ups">
      ${data.follow_ups.map(f => `<button class="follow-up" onclick="sendFollowUp('${escHtml(f).replace(/'/g,"\\'")}')">${escHtml(f)}</button>`).join('')}
    </div>`;
  }

  return html;
}

function openGallery(title, ids) {
  const overlay = document.getElementById('gallery-overlay');
  const content = document.getElementById('gallery-content');

  let cards = ids.map(id => {
    const item = itemIndex[id];
    if (!item) return '';
    return `<a href="${item.url || '#'}" target="_blank" class="gallery-card" title="${escHtml(item.summary || '').substring(0,100)}">
      <img src="${item.thumbnail_url || ''}" onerror="this.parentElement.style.background='#2C2926'" loading="lazy">
      <div class="gc-label">
        <div>${escHtml((item.summary || item.caption || '').substring(0, 60))}${(item.summary||'').length>60?'...':''}</div>
        <div class="gc-creator">@${escHtml(item.creator || '?')}</div>
      </div>
    </a>`;
  }).filter(Boolean).join('');

  content.innerHTML = `
    <h3>${escHtml(title)} <button class="close-btn" onclick="closeGallery()">&times;</button></h3>
    <div class="gallery-grid">${cards || '<div class="empty">No sources available</div>'}</div>
  `;
  overlay.classList.add('open');
}

function closeGallery() {
  document.getElementById('gallery-overlay').classList.remove('open');
}

function markdownToHtml(text) {
  return escHtml(text)
    .replace(/\\n\\n/g, '<br><br>')
    .replace(/\\n/g, '<br>')
    .replace(/[*][*](.+?)[*][*]/g, '<b>$1</b>')
    .replace(/[*](.+?)[*]/g, '<em>$1</em>')
    .replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, '<a href="$2" target="_blank">$1</a>');
}

function escHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
</script></body></html>"""


# ── Server ─────────────────────────────────────────────────────────────────

def run_server():
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs

    print(f"Loading search index from {INDEX_PATH}...")
    items = json.loads(INDEX_PATH.read_text())
    print(f"  {len(items)} items loaded")

    # Precompute filter options
    topics = sorted(set(i.get("topic_primary") or "" for i in items if i.get("topic_primary")))
    genres = sorted(set(i.get("genre") or "" for i in items if i.get("genre")))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress request logs

        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def do_OPTIONS(self):
            self.send_response(200)
            self._cors()
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)

            if parsed.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self._cors()
                self.end_headers()
                self.wfile.write(HTML.encode())

            elif parsed.path == "/meta":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps({"topics": topics, "genres": genres}).encode())

            elif parsed.path == "/items":
                # Return lightweight item data for gallery rendering
                lite = [{
                    "id": i["id"],
                    "url": i.get("url"),
                    "creator": i.get("creator"),
                    "collection": i.get("collection"),
                    "thumbnail_url": i.get("thumbnail_url"),
                    "summary": (i.get("summary") or "")[:120],
                    "caption": (i.get("caption") or "")[:100],
                    "topic_primary": i.get("topic_primary"),
                    "genre": i.get("genre"),
                } for i in items]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps(lite).encode())

            elif parsed.path == "/search":
                params = parse_qs(parsed.query)
                query = params.get("q", [""])[0]
                top_k = int(params.get("top_k", ["20"])[0])
                topic = params.get("topic", [None])[0]
                genre = params.get("genre", [None])[0]

                if not query:
                    self.send_response(400)
                    self.end_headers()
                    return

                import time
                t0 = time.time()
                q_emb = embed_query(query)
                embed_ms = int((time.time() - t0) * 1000)

                enriched = search(q_emb, items, "enriched", top_k, topic, genre)
                tier1 = search(q_emb, items, "tier1", top_k, topic, genre)
                raw = search(q_emb, items, "raw", top_k, topic, genre)

                # Strip embeddings from response
                def strip(r):
                    return {k: v for k, v in r.items()
                            if not k.startswith("embedding_") and not k.endswith("_embedding_text")
                            and not k.endswith("_tier1") and k != "embedding_text_tier1"}

                result = {
                    "enriched": [strip(r) for r in enriched],
                    "tier1": [strip(r) for r in tier1],
                    "raw": [strip(r) for r in raw],
                    "embed_ms": embed_ms,
                }

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps(result, default=str).encode())

            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            parsed = urlparse(self.path)

            if parsed.path == "/agent":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                message = body.get("message", "")
                conv = body.get("conversation", [])

                if not message:
                    self.send_response(400)
                    self.end_headers()
                    return

                print(f"  Agent query: {message[:60]}")
                try:
                    result = run_agent(message, conv, items)
                except Exception as e:
                    result = {"response": f"Error: {str(e)[:200]}", "tool_calls": [], "conversation": []}
                print(f"  Agent tools: {[tc['tool'] for tc in result.get('tool_calls', [])]}")

                # Strip embeddings from conversation to keep payload small
                clean_conv = []
                for msg in result.get("conversation", []):
                    clean_conv.append(msg)

                result["conversation"] = clean_conv

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps(result, default=str).encode())
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    # Get local IP for phone access
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"
    print(f"\nSearch Lab running at:")
    print(f"  Local:   http://localhost:{PORT}")
    print(f"  Network: http://{local_ip}:{PORT}  (use this on your phone)")
    print("Press Ctrl+C to stop\n")

    import webbrowser
    webbrowser.open(f"http://localhost:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    run_server()
