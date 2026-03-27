#!/usr/bin/env python
"""Generate synthetic test cases for classification evaluation.

Usage:
    python workbench/tools/generate_test_data.py "cooking videos with emoji captions"
    python workbench/tools/generate_test_data.py "edit TikToks with song lyrics" --count 10
    python workbench/tools/generate_test_data.py "diverse mix" --count 20 --output workbench/data/sample-videos.json
"""
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import os
import anthropic
from app.services.ontology import format_ontology_for_prompt


async def generate(scenario: str, count: int = 5) -> list[dict]:
    """Generate synthetic TikTok metadata using Claude."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in workbench/.env")
        sys.exit(1)

    client = anthropic.AsyncAnthropic(api_key=api_key)

    ontology = format_ontology_for_prompt()

    prompt = f"""Generate {count} realistic synthetic TikTok video metadata items for this scenario: "{scenario}"

Each item must have:
- caption: realistic TikTok caption (with emoji, slang, hashtags inline)
- hashtags: list of hashtags (without # prefix)
- creator: realistic username (with @)
- music: music/sound name
- subtitle: subtitle text (what's said in the video), or null if no speech
- expected: correct classification using ONLY valid tier-1 labels from the ontology below

Ontology (use ONLY these tier-1 labels in the "expected" field):
{ontology}

The "expected" field should include at least: affect, topic, genre. Include other facets when clearly determinable.

Return a JSON array. No markdown, no explanation, just the array.

Example item:
{{
  "caption": "this pasta recipe changed my life fr fr 🍝",
  "hashtags": ["pasta", "cooking", "recipe", "foodtiktok"],
  "creator": "@homecookemily",
  "music": "original sound - homecookemily",
  "subtitle": "okay so first you boil the water and add a ton of salt",
  "expected": {{"affect": "satisfying", "topic": "food", "genre": "recipe", "communicative_intent": "inform", "presentation_style": "talking_head"}}
}}"""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Handle potential markdown wrapping
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    items = json.loads(text)

    # Add UUIDs
    for item in items:
        item["id"] = str(uuid.uuid4())

    return items


async def main():
    if len(sys.argv) < 2:
        print('Usage: python generate_test_data.py "scenario description" [--count N] [--output path]')
        sys.exit(1)

    scenario = sys.argv[1]
    count = 5
    output_path = Path(__file__).resolve().parents[1] / "data" / "sample-videos.json"

    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--count" and i + 1 < len(sys.argv):
            count = int(sys.argv[i + 1])
        if arg == "--output" and i + 1 < len(sys.argv):
            output_path = Path(sys.argv[i + 1])

    print(f'Generating {count} items for scenario: "{scenario}"...')
    items = await generate(scenario, count)

    # Append to existing file
    existing = []
    if output_path.exists():
        existing = json.loads(output_path.read_text())

    existing.extend(items)
    output_path.write_text(json.dumps(existing, indent=2))

    print(f"Generated {len(items)} items. Total in {output_path.name}: {len(existing)}")
    for item in items:
        topic = item.get("expected", {}).get("topic", "?")
        affect = item.get("expected", {}).get("affect", "?")
        print(f"  {item['id'][:8]}  {topic:15s} {affect:15s} {(item.get('caption') or '')[:50]}")


if __name__ == "__main__":
    asyncio.run(main())
