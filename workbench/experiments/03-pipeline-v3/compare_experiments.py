#!/usr/bin/env python
"""Compare two pipeline experiment runs side-by-side.

Analyzes Pass 1 (perception + entity extraction) and Pass 2 (classification)
results across two experiments, producing aggregate stats and a self-contained
HTML comparison UI.

Usage:
    python workbench/experiments/03-pipeline-v3/compare_experiments.py \\
        workbench/data/pipeline_v3/ \\
        workbench/data/pipeline_v3/exp_b/ \\
        --labels "A: gemini-3-flash (no grounding)" "B: gemini-2.5-flash (grounding)" \\
        --golden workbench/data/golden_set_template.json
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_results(exp_dir: Path) -> dict[str, dict]:
    """Load all pass1 + pass2 results keyed by item_id."""
    items: dict[str, dict] = {}
    p1_dir = exp_dir / "pass1_perception"
    p2_dir = exp_dir / "pass2_classification"

    if p1_dir.exists():
        for f in p1_dir.glob("*.json"):
            r = json.loads(f.read_text())
            iid = r["item_id"]
            if iid not in items:
                items[iid] = {}
            items[iid]["pass1"] = r

    if p2_dir.exists():
        for f in p2_dir.glob("*.json"):
            r = json.loads(f.read_text())
            iid = r["item_id"]
            if iid not in items:
                items[iid] = {}
            items[iid]["pass2"] = r

    return items


def get_po(result: dict) -> dict:
    """Safely extract parsed_output as a dict."""
    po = result.get("parsed_output") or {}
    return po if isinstance(po, dict) else {}


def extract_p1_stats(result: dict) -> dict:
    po = get_po(result)
    entities = po.get("entities") or []
    return {
        "entity_count": len(entities),
        "entity_names": [e.get("name", "?") for e in entities if isinstance(e, dict)],
        "entity_types": [e.get("type", "?") for e in entities if isinstance(e, dict)],
        "entity_relevance": [e.get("relevance", "?") for e in entities if isinstance(e, dict)],
        "takeaway_count": len(po.get("takeaways") or []),
        "takeaways": [t.get("statement", "") for t in (po.get("takeaways") or []) if isinstance(t, dict)],
        "summary": po.get("overall_summary") or "",
        "audio_actual": (po.get("audio_identification") or {}).get("actual_song"),
        "audio_match": (po.get("audio_identification") or {}).get("match"),
        "self_conf": (po.get("extraction_confidence") or {}).get("entities_complete"),
        "has_error": bool(po.get("_error") or po.get("_parse_error")),
        "grounding_count": len(result.get("grounding_sources") or []),
        "cost": result.get("metrics", {}).get("cost_usd", 0),
        "tokens": result.get("metrics", {}).get("total_tokens", 0),
        "latency": result.get("metrics", {}).get("latency_ms", 0),
    }


def extract_p2_stats(result: dict) -> dict:
    po = get_po(result)
    topic = po.get("topic") or {}
    affect = po.get("affect") or []
    genre = po.get("genre") or {}
    return {
        "topic_primary": topic.get("primary", "?") if isinstance(topic, dict) else "?",
        "topic_secondary": topic.get("secondary") if isinstance(topic, dict) else None,
        "genre": genre.get("label", "?") if isinstance(genre, dict) else "?",
        "affect_dominant": [a["label"] for a in affect if isinstance(a, dict) and a.get("tier") == "dominant"],
        "affect_secondary": [a["label"] for a in affect if isinstance(a, dict) and a.get("tier") == "secondary"],
        "viewer_orient": (po.get("viewer_orientation") or {}).get("label", "?"),
        "has_error": bool(po.get("_error") or po.get("_parse_error")),
        "cost": result.get("metrics", {}).get("cost_usd", 0),
    }


def print_aggregate(label: str, results: dict[str, dict], golden: list[dict] | None):
    """Print aggregate stats for one experiment."""
    coll_map = {}
    if golden:
        coll_map = {i["id"]: i["collection"] for i in golden}

    p1_stats = {}
    p2_stats = {}
    for iid, data in results.items():
        if "pass1" in data:
            p1_stats[iid] = extract_p1_stats(data["pass1"])
        if "pass2" in data:
            p2_stats[iid] = extract_p2_stats(data["pass2"])

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    # Pass 1
    p1_ok = [s for s in p1_stats.values() if not s["has_error"]]
    total_ent = sum(s["entity_count"] for s in p1_ok)
    total_take = sum(s["takeaway_count"] for s in p1_ok)
    audio_id = sum(1 for s in p1_ok if s["audio_actual"])
    audio_mismatch = sum(1 for s in p1_ok if s["audio_actual"] and s["audio_match"] is False)
    grounded = sum(1 for s in p1_ok if s["grounding_count"] > 0)
    total_cost_p1 = sum(s["cost"] for s in p1_stats.values())
    avg_latency = sum(s["latency"] for s in p1_ok) / len(p1_ok) if p1_ok else 0

    print(f"\n  PASS 1 — Perception + Entity Extraction")
    print(f"  Items: {len(p1_ok)} OK / {len(p1_stats)} total")
    print(f"  Entities: {total_ent} total, {total_ent/len(p1_ok):.1f} avg/item")
    print(f"  Takeaways: {total_take} total, {total_take/len(p1_ok):.1f} avg/item")
    print(f"  Audio identified: {audio_id}/{len(p1_ok)}")
    print(f"  Audio mismatch detected: {audio_mismatch}/{len(p1_ok)}")
    print(f"  Grounding triggered: {grounded}/{len(p1_ok)}")
    print(f"  Cost: ${total_cost_p1:.4f} (${total_cost_p1/len(p1_ok):.4f}/item)")
    print(f"  Avg latency: {avg_latency/1000:.1f}s")

    # Entity type distribution
    type_counts = Counter()
    for s in p1_ok:
        type_counts.update(s["entity_types"])
    print(f"  Entity types: {dict(type_counts.most_common(8))}")

    # Relevance distribution
    rel_counts = Counter()
    for s in p1_ok:
        rel_counts.update(s["entity_relevance"])
    print(f"  Relevance: {dict(rel_counts)}")

    # Pass 2
    p2_ok = [s for s in p2_stats.values() if not s["has_error"]]
    total_cost_p2 = sum(s["cost"] for s in p2_stats.values())

    print(f"\n  PASS 2 — Classification")
    print(f"  Items: {len(p2_ok)} OK / {len(p2_stats)} total")
    print(f"  Cost: ${total_cost_p2:.4f}")

    topic_counts = Counter(s["topic_primary"] for s in p2_ok)
    print(f"  Topics: {dict(topic_counts.most_common(10))}")

    has_secondary = sum(1 for s in p2_ok if s["topic_secondary"])
    print(f"  Secondary topic: {has_secondary}/{len(p2_ok)}")

    genre_counts = Counter(s["genre"] for s in p2_ok)
    print(f"  Genres: {dict(genre_counts.most_common(8))}")

    affect_dom = Counter()
    for s in p2_ok:
        affect_dom.update(s["affect_dominant"])
    print(f"  Dominant affect: {dict(affect_dom.most_common(8))}")

    inspiring = sum(1 for s in p2_ok if "inspiring" in s["affect_dominant"])
    informative = sum(1 for s in p2_ok if "informative" in s["affect_dominant"])
    print(f"  inspiring dominant: {inspiring}/{len(p2_ok)} ({inspiring/len(p2_ok):.0%})")
    print(f"  informative dominant: {informative}/{len(p2_ok)} ({informative/len(p2_ok):.0%})")

    print(f"\n  TOTAL COST: ${total_cost_p1 + total_cost_p2:.4f}")

    return p1_stats, p2_stats


def print_side_by_side(label_a: str, label_b: str,
                       results_a: dict, results_b: dict,
                       golden: list[dict] | None):
    """Print item-level side-by-side comparison for divergent items."""
    coll_map = {}
    if golden:
        coll_map = {i["id"]: i["collection"] for i in golden}

    common_ids = set(results_a.keys()) & set(results_b.keys())
    print(f"\n{'='*60}")
    print(f"  SIDE-BY-SIDE COMPARISON ({len(common_ids)} common items)")
    print(f"{'='*60}")

    # Compare topics
    topic_agree = 0
    topic_disagree = []
    for iid in common_ids:
        a_p2 = results_a[iid].get("pass2")
        b_p2 = results_b[iid].get("pass2")
        if not a_p2 or not b_p2:
            continue
        a_topic = (get_po(a_p2).get("topic") or {}).get("primary", "?")
        b_topic = (get_po(b_p2).get("topic") or {}).get("primary", "?")
        if a_topic == b_topic:
            topic_agree += 1
        else:
            topic_disagree.append((iid, coll_map.get(iid, "?"), a_topic, b_topic))

    print(f"\n  Topic agreement: {topic_agree}/{topic_agree + len(topic_disagree)} ({topic_agree/(topic_agree + len(topic_disagree)):.0%})")
    if topic_disagree:
        print(f"  Disagreements ({len(topic_disagree)}):")
        for iid, coll, a_t, b_t in topic_disagree[:15]:
            print(f"    {iid[:12]} ({coll:20s})  A={a_t:15s}  B={b_t}")

    # Compare genre
    genre_agree = 0
    genre_disagree = []
    for iid in common_ids:
        a_p2 = results_a[iid].get("pass2")
        b_p2 = results_b[iid].get("pass2")
        if not a_p2 or not b_p2:
            continue
        a_g = (get_po(a_p2).get("genre") or {}).get("label", "?")
        b_g = (get_po(b_p2).get("genre") or {}).get("label", "?")
        if a_g == b_g:
            genre_agree += 1
        else:
            genre_disagree.append((iid, coll_map.get(iid, "?"), a_g, b_g))

    print(f"\n  Genre agreement: {genre_agree}/{genre_agree + len(genre_disagree)} ({genre_agree/(genre_agree + len(genre_disagree)):.0%})")
    if genre_disagree:
        print(f"  Disagreements ({len(genre_disagree)}):")
        for iid, coll, a_g, b_g in genre_disagree[:15]:
            print(f"    {iid[:12]} ({coll:20s})  A={a_g:15s}  B={b_g}")

    # Compare dominant affect
    affect_agree = 0
    affect_disagree = []
    for iid in common_ids:
        a_p2 = results_a[iid].get("pass2")
        b_p2 = results_b[iid].get("pass2")
        if not a_p2 or not b_p2:
            continue
        a_aff = sorted([a["label"] for a in (get_po(a_p2).get("affect") or []) if isinstance(a, dict) and a.get("tier") == "dominant"])
        b_aff = sorted([a["label"] for a in (get_po(b_p2).get("affect") or []) if isinstance(a, dict) and a.get("tier") == "dominant"])
        if a_aff == b_aff:
            affect_agree += 1
        else:
            affect_disagree.append((iid, coll_map.get(iid, "?"), a_aff, b_aff))

    print(f"\n  Dominant affect agreement: {affect_agree}/{affect_agree + len(affect_disagree)} ({affect_agree/(affect_agree + len(affect_disagree)):.0%})")
    if affect_disagree:
        print(f"  Disagreements ({len(affect_disagree)}):")
        for iid, coll, a_a, b_a in affect_disagree[:15]:
            print(f"    {iid[:12]} ({coll:20s})  A={a_a}  B={b_a}")

    # Compare entity counts
    ent_diffs = []
    for iid in common_ids:
        a_p1 = results_a[iid].get("pass1")
        b_p1 = results_b[iid].get("pass1")
        if not a_p1 or not b_p1:
            continue
        a_ent = len((get_po(a_p1).get("entities") or []))
        b_ent = len((get_po(b_p1).get("entities") or []))
        if abs(a_ent - b_ent) >= 3:
            ent_diffs.append((iid, coll_map.get(iid, "?"), a_ent, b_ent))

    avg_a = sum(len(get_po(results_a[iid].get("pass1", {})).get("entities") or []) for iid in common_ids if results_a[iid].get("pass1")) / len(common_ids)
    avg_b = sum(len(get_po(results_b[iid].get("pass1", {})).get("entities") or []) for iid in common_ids if results_b[iid].get("pass1")) / len(common_ids)
    print(f"\n  Entity count: A avg={avg_a:.1f}, B avg={avg_b:.1f}")
    if ent_diffs:
        print(f"  Large differences (>=3): {len(ent_diffs)} items")
        for iid, coll, a_e, b_e in sorted(ent_diffs, key=lambda x: abs(x[2]-x[3]), reverse=True)[:10]:
            print(f"    {iid[:12]} ({coll:20s})  A={a_e}  B={b_e}  diff={b_e-a_e:+d}")

    # Audio identification comparison
    audio_only_a = 0
    audio_only_b = 0
    audio_diff = []
    for iid in common_ids:
        a_p1 = results_a[iid].get("pass1")
        b_p1 = results_b[iid].get("pass1")
        if not a_p1 or not b_p1:
            continue
        a_audio = (get_po(a_p1).get("audio_identification") or {}).get("actual_song")
        b_audio = (get_po(b_p1).get("audio_identification") or {}).get("actual_song")
        if a_audio and not b_audio:
            audio_only_a += 1
        elif b_audio and not a_audio:
            audio_only_b += 1
        elif a_audio and b_audio and a_audio != b_audio:
            audio_diff.append((iid, coll_map.get(iid, "?"), a_audio, b_audio))

    print(f"\n  Audio: only-A={audio_only_a}, only-B={audio_only_b}, different={len(audio_diff)}")
    for iid, coll, a_au, b_au in audio_diff[:5]:
        print(f"    {iid[:12]} ({coll:15s})")
        print(f"      A: {a_au}")
        print(f"      B: {b_au}")

    # Items where grounding was used in B
    grounded_items = []
    for iid in common_ids:
        b_p1 = results_b[iid].get("pass1")
        if b_p1 and b_p1.get("grounding_sources"):
            grounded_items.append(iid)

    if grounded_items:
        print(f"\n  Items where B used grounding ({len(grounded_items)}):")
        for iid in grounded_items:
            coll = coll_map.get(iid, "?")
            a_ent = len(get_po(results_a.get(iid, {}).get("pass1", {})).get("entities") or [])
            b_ent = len(get_po(results_b[iid]["pass1"]).get("entities") or [])
            b_sources = results_b[iid]["pass1"].get("grounding_sources", [])
            print(f"    {iid[:12]} ({coll:15s})  ent A={a_ent} B={b_ent}  sources={len(b_sources)}")
            for s in b_sources[:2]:
                print(f"      - {s.get('title', '?')[:50]}")


def generate_html(label_a: str, label_b: str,
                  results_a: dict, results_b: dict,
                  golden: list[dict] | None, output_path: Path):
    """Generate side-by-side HTML comparison UI."""
    coll_map = {}
    apify_map = {}
    if golden:
        coll_map = {i["id"]: i["collection"] for i in golden}
        apify_map = {i["id"]: i.get("apify", {}) for i in golden}

    common_ids = sorted(set(results_a.keys()) & set(results_b.keys()))

    items_json = []
    for iid in common_ids:
        a = results_a[iid]
        b = results_b[iid]
        apify = apify_map.get(iid, {})

        a_p1 = get_po(a.get("pass1", {}))
        b_p1 = get_po(b.get("pass1", {}))
        a_p2 = get_po(a.get("pass2", {}))
        b_p2 = get_po(b.get("pass2", {}))

        items_json.append({
            "id": iid,
            "collection": coll_map.get(iid, "?"),
            "caption": apify.get("caption") or "",
            "thumbnail": apify.get("thumbnail_url"),
            "url": f"https://www.tiktok.com/@x/video/{iid}",
            "a": {
                "summary": a_p1.get("overall_summary") or "",
                "entities": [{"name": e.get("name"), "type": e.get("type"), "rel": e.get("relevance")} for e in (a_p1.get("entities") or []) if isinstance(e, dict)],
                "audio": (a_p1.get("audio_identification") or {}).get("actual_song"),
                "takeaways": [t.get("statement", "")[:150] for t in (a_p1.get("takeaways") or []) if isinstance(t, dict)],
                "topic": (a_p2.get("topic") or {}).get("primary", "?"),
                "topic2": (a_p2.get("topic") or {}).get("secondary"),
                "genre": (a_p2.get("genre") or {}).get("label", "?"),
                "affect": [{"label": af.get("label"), "tier": af.get("tier")} for af in (a_p2.get("affect") or []) if isinstance(af, dict)],
                "cost": round((a.get("pass1", {}).get("metrics", {}).get("cost_usd", 0) + a.get("pass2", {}).get("metrics", {}).get("cost_usd", 0)), 5),
            },
            "b": {
                "summary": b_p1.get("overall_summary") or "",
                "entities": [{"name": e.get("name"), "type": e.get("type"), "rel": e.get("relevance")} for e in (b_p1.get("entities") or []) if isinstance(e, dict)],
                "audio": (b_p1.get("audio_identification") or {}).get("actual_song"),
                "takeaways": [t.get("statement", "")[:150] for t in (b_p1.get("takeaways") or []) if isinstance(t, dict)],
                "topic": (b_p2.get("topic") or {}).get("primary", "?"),
                "topic2": (b_p2.get("topic") or {}).get("secondary"),
                "genre": (b_p2.get("genre") or {}).get("label", "?"),
                "affect": [{"label": af.get("label"), "tier": af.get("tier")} for af in (b_p2.get("affect") or []) if isinstance(af, dict)],
                "grounding": len(b.get("pass1", {}).get("grounding_sources") or []),
                "cost": round((b.get("pass1", {}).get("metrics", {}).get("cost_usd", 0) + b.get("pass2", {}).get("metrics", {}).get("cost_usd", 0)), 5),
            },
        })

    data_json = json.dumps(items_json)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Experiment Comparison</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,sans-serif;background:#F8F7F4;color:#1C1B18;padding:16px}}
.hdr{{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:#fff;border:1px solid #E6E4DE;border-radius:8px;margin-bottom:12px}}
.nav{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}}
.pip{{width:24px;height:24px;border:1px solid #E6E4DE;border-radius:4px;background:#fff;cursor:pointer;font-size:10px;display:flex;align-items:center;justify-content:center}}
.pip:hover{{background:#F0EEE8}}.pip.active{{background:#2C2926;color:#fff}}
.pip.diff{{border-color:#A06840}}.pip.active.diff{{background:#A06840}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.card{{background:#fff;border:1px solid #E6E4DE;border-radius:8px;padding:14px}}
.card h3{{font-size:12px;color:#9C9890;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px}}
.meta{{text-align:center;margin-bottom:12px}}
.meta img{{max-height:200px;border-radius:6px}}
.tag{{display:inline-block;padding:2px 6px;border-radius:4px;font-size:11px;background:#F0EEE8;margin:1px}}
.tag.match{{background:#d4edda;color:#155724}}.tag.diff{{background:#f8d7da;color:#721c24}}
.tag.grounded{{background:#cce5ff;color:#004085}}
.ent{{font-size:12px;margin:2px 0}}.ent .type{{color:#9C9890;font-size:11px}}
.summary{{font-size:13px;line-height:1.5;color:#2C2926;margin:6px 0}}
.take{{font-size:12px;color:#2C2926;font-style:italic;margin:4px 0;padding-left:8px;border-left:2px solid #E6E4DE}}
.filter{{margin-bottom:8px;font-size:12px}}
select{{padding:4px 8px;border:1px solid #E6E4DE;border-radius:4px;font-size:12px}}
</style></head><body>
<div class="hdr"><div><b>Experiment Comparison</b><br>
<span style="font-size:12px;color:#9C9890">{label_a} vs {label_b}</span></div>
<div style="font-size:12px;color:#9C9890" id="prog"></div>
<div style="font-size:11px"><span style="background:#F0EEE8;padding:2px 6px;border-radius:3px">← →</span> navigate</div></div>
<div class="filter">Filter: <select id="filt" onchange="applyFilter()">
<option value="all">All items</option><option value="diff_topic">Different topic</option>
<option value="diff_genre">Different genre</option><option value="diff_affect">Different affect</option>
<option value="grounded">B used grounding</option></select>
<span id="filtCount" style="color:#9C9890;font-size:11px"></span></div>
<div class="nav" id="pips"></div>
<div id="content"></div>
<script>
const I={data_json};
let ci=0,filtered=I.map((_,i)=>i);
function isDiff(item,field){{
  if(field==='topic')return item.a.topic!==item.b.topic;
  if(field==='genre')return item.a.genre!==item.b.genre;
  if(field==='affect'){{
    const ad=item.a.affect.filter(a=>a.tier==='dominant').map(a=>a.label).sort().join(',');
    const bd=item.b.affect.filter(a=>a.tier==='dominant').map(a=>a.label).sort().join(',');
    return ad!==bd;
  }}
  return false;
}}
function applyFilter(){{
  const f=document.getElementById('filt').value;
  if(f==='all')filtered=I.map((_,i)=>i);
  else if(f==='diff_topic')filtered=I.map((_,i)=>i).filter(i=>isDiff(I[i],'topic'));
  else if(f==='diff_genre')filtered=I.map((_,i)=>i).filter(i=>isDiff(I[i],'genre'));
  else if(f==='diff_affect')filtered=I.map((_,i)=>i).filter(i=>isDiff(I[i],'affect'));
  else if(f==='grounded')filtered=I.map((_,i)=>i).filter(i=>I[i].b.grounding>0);
  ci=0;
  document.getElementById('filtCount').textContent=filtered.length+' items';
  renderPips();render();
}}
function renderPips(){{
  let h='';
  filtered.forEach((idx,fi)=>{{
    const item=I[idx];
    const d=isDiff(item,'topic')||isDiff(item,'genre')||isDiff(item,'affect');
    h+=`<button class="pip${{fi===ci?' active':''}}${{d?' diff':''}}" onclick="ci=${{fi}};render()">${{fi+1}}</button>`;
  }});
  document.getElementById('pips').innerHTML=h;
}}
function affStr(arr){{return arr.map(a=>`<span class="tag">${{a.label}} (${{a.tier}})</span>`).join(' ');}}
function render(){{
  if(!filtered.length){{document.getElementById('content').innerHTML='<p>No items match filter.</p>';return;}}
  const item=I[filtered[ci]];
  const tMatch=item.a.topic===item.b.topic;
  const gMatch=item.a.genre===item.b.genre;
  document.getElementById('prog').textContent=`${{ci+1}}/${{filtered.length}} (${{item.collection}})`;
  const h=`
  <div class="meta">
    ${{item.thumbnail?`<img src="${{item.thumbnail}}" alt="thumb">`:''}}
    <div style="margin-top:6px;font-size:13px">${{item.caption}}</div>
    <a href="${{item.url}}" target="_blank" style="font-size:11px;color:#A06840">Open TikTok</a>
  </div>
  <div class="grid">
    <div class="card"><h3>{label_a} — $\{{item.a.cost}}</h3>
      <div><span class="tag ${{tMatch?'match':'diff'}}">topic: ${{item.a.topic}}</span>
      ${{item.a.topic2?`<span class="tag">+${{item.a.topic2}}</span>`:''}}
      <span class="tag ${{gMatch?'match':'diff'}}">genre: ${{item.a.genre}}</span></div>
      <div style="margin:4px 0">${{affStr(item.a.affect)}}</div>
      <div style="margin-top:6px"><b style="font-size:11px;color:#9C9890">SUMMARY:</b></div>
      <div class="summary">${{item.a.summary}}</div>
      ${{item.a.takeaways.length?`<div style="margin-top:8px"><b style="font-size:11px;color:#9C9890">TAKEAWAYS:</b></div>`:''}}
      ${{item.a.takeaways.map(t=>`<div class="take">${{t}}</div>`).join('')}}
      <div style="margin-top:8px"><b style="font-size:11px">Entities (${{item.a.entities.length}}):</b>
      ${{item.a.entities.map(e=>`<div class="ent">${{e.name}} <span class="type">${{e.type}} · ${{e.rel}}</span></div>`).join('')}}</div>
      ${{item.a.audio?`<div style="margin-top:6px;font-size:12px">🎵 ${{item.a.audio}}</div>`:''}}
    </div>
    <div class="card"><h3>{label_b} — $\{{item.b.cost}} ${{item.b.grounding?`<span class="tag grounded">${{item.b.grounding}} grounding sources</span>`:''}}</h3>
      <div><span class="tag ${{tMatch?'match':'diff'}}">topic: ${{item.b.topic}}</span>
      ${{item.b.topic2?`<span class="tag">+${{item.b.topic2}}</span>`:''}}
      <span class="tag ${{gMatch?'match':'diff'}}">genre: ${{item.b.genre}}</span></div>
      <div style="margin:4px 0">${{affStr(item.b.affect)}}</div>
      <div style="margin-top:6px"><b style="font-size:11px;color:#9C9890">SUMMARY:</b></div>
      <div class="summary">${{item.b.summary}}</div>
      ${{item.b.takeaways.length?`<div style="margin-top:8px"><b style="font-size:11px;color:#9C9890">TAKEAWAYS:</b></div>`:''}}
      ${{item.b.takeaways.map(t=>`<div class="take">${{t}}</div>`).join('')}}
      <div style="margin-top:8px"><b style="font-size:11px">Entities (${{item.b.entities.length}}):</b>
      ${{item.b.entities.map(e=>`<div class="ent">${{e.name}} <span class="type">${{e.type}} · ${{e.rel}}</span></div>`).join('')}}</div>
      ${{item.b.audio?`<div style="margin-top:6px;font-size:12px">🎵 ${{item.b.audio}}</div>`:''}}
    </div>
  </div>`;
  document.getElementById('content').innerHTML=h;
  renderPips();scrollTo(0,0);
}}
document.addEventListener('keydown',e=>{{
  if(e.target.tagName==='SELECT')return;
  if(e.key==='ArrowLeft'&&ci>0){{ci--;render();}}
  if(e.key==='ArrowRight'&&ci<filtered.length-1){{ci++;render();}}
}});
applyFilter();
</script></body></html>"""

    output_path.write_text(html)
    print(f"\n  HTML comparison: {output_path}")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python compare_experiments.py <exp_a_dir> <exp_b_dir> [options]")
        print("  --labels 'Label A' 'Label B'")
        print("  --golden <golden_set.json>")
        sys.exit(1)

    dir_a = Path(sys.argv[1])
    dir_b = Path(sys.argv[2])

    label_a = "Experiment A"
    label_b = "Experiment B"
    golden = None

    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--labels" and i + 2 < len(sys.argv):
            label_a = sys.argv[i + 1]
            label_b = sys.argv[i + 2]
            i += 3
        elif sys.argv[i] == "--golden" and i + 1 < len(sys.argv):
            golden = json.loads(Path(sys.argv[i + 1]).read_text())
            i += 2
        else:
            i += 1

    results_a = load_results(dir_a)
    results_b = load_results(dir_b)

    print(f"Loaded: {len(results_a)} items from A, {len(results_b)} items from B")

    p1a, p2a = print_aggregate(label_a, results_a, golden)
    p1b, p2b = print_aggregate(label_b, results_b, golden)
    print_side_by_side(label_a, label_b, results_a, results_b, golden)

    # Generate HTML
    html_path = REPO_ROOT / "workbench" / "data" / "experiment_comparison.html"
    generate_html(label_a, label_b, results_a, results_b, golden, html_path)


if __name__ == "__main__":
    main()
