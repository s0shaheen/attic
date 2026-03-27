#!/usr/bin/env python
"""Build search index: construct embedding text and generate embeddings.

Two variants:
  A (raw): caption + hashtags + music metadata only
  B (enriched): full pipeline v3 output + subtitles

Usage:
    python workbench/experiments/03-pipeline-v3/build_search_index.py
"""
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"

load_dotenv(REPO_ROOT / "workbench" / ".env")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
MAX_EMBEDDING_TOKENS = 500  # soft target — truncate from bottom of priority list

GOLDEN_SET_PATH = REPO_ROOT / "workbench" / "experiments" / "04-golden-set" / "results" / "golden_set_template.json"
P1_DIR = RESULTS_DIR / "pipeline_v3" / "pass1_perception"
P2_DIR = RESULTS_DIR / "pipeline_v3" / "pass2_classification"
SUBTITLES_PATH = REPO_ROOT / "workbench" / "experiments" / "04-golden-set" / "results" / "golden_set_subtitles.json"
OUTPUT_PATH = RESULTS_DIR / "search_index.json"


def get_po(path: Path) -> dict:
    if not path.exists():
        return {}
    r = json.loads(path.read_text())
    po = r.get("parsed_output") or {}
    return po if isinstance(po, dict) else {}


def build_raw_text(item: dict) -> str:
    """Variant A: raw metadata only."""
    apify = item.get("apify", {})
    parts = []

    caption = apify.get("caption") or ""
    if caption.strip():
        parts.append(caption.strip())

    hashtags = apify.get("hashtags") or []
    if hashtags:
        parts.append(" ".join(f"#{h}" for h in hashtags))

    music = apify.get("music_metadata") or ""
    if music and music.lower() not in ("original sound", "original sound -"):
        parts.append(f"Music: {music}")

    return "\n".join(parts)


def build_enriched_text(item: dict, p1: dict, p2: dict, subtitle: str | None) -> str:
    """Variant B: full pipeline output, priority ordered."""
    apify = item.get("apify", {})
    sections: list[tuple[str, str]] = []  # (label, text) — priority order

    # 1. Takeaways
    takeaways = p1.get("takeaways") or []
    take_text = " ".join(t.get("statement", "") for t in takeaways if isinstance(t, dict))
    if take_text.strip():
        sections.append(("takeaway", take_text.strip()))

    # 2. Summary
    summary = p1.get("overall_summary") or ""
    if summary.strip():
        sections.append(("summary", summary.strip()))

    # 3. Scene descriptions (visual + audio + text_on_screen)
    scenes = p1.get("scene_timeline") or []
    scene_parts = []
    for s in scenes:
        if not isinstance(s, dict):
            continue
        vis = s.get("visual_description") or ""
        aud = s.get("audio_description") or ""
        tos = s.get("text_on_screen") or ""
        parts = [p for p in [vis, aud, tos] if p.strip() and p.lower() not in ("none", "null", "n/a")]
        if parts:
            scene_parts.append(" ".join(parts))
    if scene_parts:
        sections.append(("scenes", " | ".join(scene_parts)))

    # 4. Structured content items
    sc = p1.get("structured_content") or {}
    if isinstance(sc, dict) and sc.get("items"):
        sc_type = sc.get("type") or "list"
        item_strs = []
        for si in sc["items"]:
            if isinstance(si, dict):
                name = si.get("name") or ""
                details = si.get("details") or ""
                item_strs.append(f"{name}: {details}" if details else name)
        if item_strs:
            sections.append(("structured", f"{sc_type}: {', '.join(item_strs)}"))

    # 5. Primary entity names
    entities = p1.get("entities") or []
    primary_ents = [e.get("display_name") or e.get("name", "")
                    for e in entities if isinstance(e, dict) and e.get("relevance") == "primary"]
    supporting_ents = [e.get("display_name") or e.get("name", "")
                       for e in entities if isinstance(e, dict) and e.get("relevance") == "supporting"]
    if primary_ents:
        sections.append(("entities_primary", "Key subjects: " + ", ".join(primary_ents)))
    if supporting_ents:
        sections.append(("entities_supporting", "Also mentioned: " + ", ".join(supporting_ents)))

    # 6. Subtitle text
    if subtitle and subtitle.strip():
        sections.append(("subtitle", subtitle.strip()[:800]))

    # 7. Classification labels + micro_labels
    topic = p2.get("topic") or {}
    genre = p2.get("genre") or {}
    affect = p2.get("affect") or []
    label_parts = []
    if isinstance(topic, dict):
        t = topic.get("primary", "")
        if t:
            label_parts.append(f"Topic: {t}")
        t2 = topic.get("secondary")
        if t2:
            label_parts.append(f"Secondary: {t2}")
        micros = topic.get("micro_labels") or []
        if micros:
            label_parts.append(f"Tags: {', '.join(micros[:5])}")
    if isinstance(genre, dict) and genre.get("label"):
        label_parts.append(f"Genre: {genre['label']}")
        gmicros = genre.get("micro_labels") or []
        if gmicros:
            label_parts.append(f"Format: {', '.join(gmicros[:3])}")
    if affect:
        aff_labels = [a.get("label", "") for a in affect if isinstance(a, dict) and a.get("tier") == "dominant"]
        if aff_labels:
            label_parts.append(f"Mood: {', '.join(aff_labels)}")
    vo = p2.get("viewer_orientation") or {}
    if isinstance(vo, dict) and vo.get("label"):
        label_parts.append(f"Saved for: {vo['label']}")
    if label_parts:
        sections.append(("labels", " | ".join(label_parts)))

    # 8. Caption
    caption = (apify.get("caption") or "").strip()
    if caption:
        sections.append(("caption", caption))

    # 9. Comments
    comments = apify.get("comments_top10") or []
    if comments:
        comment_text = " | ".join(c[:100] for c in comments[:5] if c)
        if comment_text:
            sections.append(("comments", f"Comments: {comment_text}"))

    # 10. Audio (only if metadata-confirmed)
    audio = p1.get("audio_identification") or {}
    if audio.get("match") is True and audio.get("actual_song"):
        sections.append(("audio", f"Song: {audio['actual_song']}"))

    # 11. Hashtags
    hashtags = apify.get("hashtags") or []
    if hashtags:
        sections.append(("hashtags", " ".join(f"#{h}" for h in hashtags)))

    # Assemble with truncation — rough token estimate: 1 token ≈ 4 chars
    max_chars = MAX_EMBEDDING_TOKENS * 4
    result_parts = []
    char_count = 0
    for label, text in sections:
        if char_count + len(text) > max_chars:
            remaining = max_chars - char_count
            if remaining > 50:
                result_parts.append(text[:remaining])
            break
        result_parts.append(text)
        char_count += len(text) + 1  # +1 for newline

    return "\n".join(result_parts)


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API in batches."""
    all_embeddings = []
    batch_size = 50
    client = httpx.Client(timeout=60)

    # Replace empty strings with a placeholder to avoid API errors
    texts = [t if t.strip() else "(no content)" for t in texts]

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"input": batch, "model": EMBEDDING_MODEL},
        )
        resp.raise_for_status()
        data = resp.json()
        # Sort by index to maintain order
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        all_embeddings.extend([d["embedding"] for d in sorted_data])

        usage = data.get("usage", {})
        print(f"  Batch {i//batch_size + 1}: {len(batch)} items, "
              f"{usage.get('total_tokens', '?')} tokens")

    client.close()
    return all_embeddings


def main() -> None:
    golden = json.loads(GOLDEN_SET_PATH.read_text())
    subtitles = json.loads(SUBTITLES_PATH.read_text()) if SUBTITLES_PATH.exists() else {}

    print(f"Building search index for {len(golden)} items...")
    print(f"  Subtitles available: {len(subtitles)}")

    # Build text for both variants
    raw_texts = []
    enriched_texts = []
    index_items = []

    for item in golden:
        vid_id = item["id"]
        p1 = get_po(P1_DIR / f"{vid_id}.json")
        p2 = get_po(P2_DIR / f"{vid_id}.json")
        subtitle = subtitles.get(vid_id)

        raw = build_raw_text(item)
        enriched = build_enriched_text(item, p1, p2, subtitle)

        raw_texts.append(raw)
        enriched_texts.append(enriched)

        # Build metadata for search results display
        apify = item.get("apify", {})
        entities = p1.get("entities") or []
        topic = p2.get("topic") or {}
        affect = p2.get("affect") or []
        audio = p1.get("audio_identification") or {}

        index_items.append({
            "id": vid_id,
            "url": item.get("url", ""),
            "creator": item.get("creator", ""),
            "collection": item.get("collection", ""),
            "thumbnail_url": apify.get("thumbnail_url"),
            "caption": apify.get("caption") or "",
            "duration": apify.get("duration_seconds"),
            "music_metadata": apify.get("music_metadata"),
            "summary": p1.get("overall_summary") or "",
            "takeaways": [t.get("statement", "") for t in (p1.get("takeaways") or []) if isinstance(t, dict)],
            "entities": [{"name": e.get("name"), "type": e.get("type"), "relevance": e.get("relevance")}
                         for e in entities if isinstance(e, dict)],
            "structured_content": p1.get("structured_content"),
            "audio_actual": audio.get("actual_song"),
            "audio_match": audio.get("match"),
            "topic_primary": topic.get("primary") if isinstance(topic, dict) else None,
            "topic_secondary": topic.get("secondary") if isinstance(topic, dict) else None,
            "genre": (p2.get("genre") or {}).get("label"),
            "affect": [{"label": a.get("label"), "tier": a.get("tier")}
                       for a in affect if isinstance(a, dict)],
            "viewer_orientation": (p2.get("viewer_orientation") or {}).get("label"),
            "subtitle_text": subtitle,
            "raw_embedding_text": raw,
            "enriched_embedding_text": enriched,
        })

    # Stats
    raw_lengths = [len(t) for t in raw_texts]
    enriched_lengths = [len(t) for t in enriched_texts]
    print(f"\nRaw text: avg {sum(raw_lengths)/len(raw_lengths):.0f} chars, "
          f"range {min(raw_lengths)}-{max(raw_lengths)}")
    print(f"Enriched text: avg {sum(enriched_lengths)/len(enriched_lengths):.0f} chars, "
          f"range {min(enriched_lengths)}-{max(enriched_lengths)}")

    # Generate embeddings
    print(f"\nGenerating raw embeddings...")
    raw_embeddings = embed_batch(raw_texts)

    print(f"\nGenerating enriched embeddings...")
    enriched_embeddings = embed_batch(enriched_texts)

    # Attach embeddings to index
    for i, item in enumerate(index_items):
        item["embedding_raw"] = raw_embeddings[i]
        item["embedding_enriched"] = enriched_embeddings[i]

    # Save
    OUTPUT_PATH.write_text(json.dumps(index_items, indent=None))
    size_mb = OUTPUT_PATH.stat().st_size / 1024 / 1024
    print(f"\nSaved search index: {OUTPUT_PATH.relative_to(REPO_ROOT)} ({size_mb:.1f} MB)")
    print(f"  {len(index_items)} items, 2 embedding variants each")


if __name__ == "__main__":
    main()
