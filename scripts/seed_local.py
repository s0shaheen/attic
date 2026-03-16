"""Seed local Supabase with test data from user_bob.json fixture.

Usage: cd src/backend && uv run python ../../scripts/seed_local.py

This script:
1. Creates a test user in the users table
2. Creates an upload record
3. Parses the fixture JSON to extract video URLs
4. Inserts media_events with fake restaurant/food captions
5. Generates real embeddings via OpenAI
6. Marks everything as 'complete'
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ------ Config ------

FIXTURE_PATH = Path(__file__).parent.parent / "tests/fixtures/tiktok-exports/synthetic/user_bob.json"
TEST_USER_ID = "9e9019d7-62a7-4518-853c-e420f41cad5c"  # matches local Supabase test user
TEST_EMAIL = "test@attic.dev"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:54322/postgres")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Fake enriched data — mix of restaurant/food content and other content
# so the agent can find restaurants when asked
FAKE_ENRICHMENTS = [
    {
        "caption": "Best tacos in Austin TX 🌮 this place is INSANE #food #tacos #austin #foodie",
        "hashtags": ["food", "tacos", "austin", "foodie"],
        "creator": "foodie_sarah",
        "creator_name": "Sarah Eats",
    },
    {
        "caption": "Rating the top 5 sushi restaurants in NYC 🍣 #sushi #nyc #foodreview #restaurant",
        "hashtags": ["sushi", "nyc", "foodreview", "restaurant"],
        "creator": "nycfoodie",
        "creator_name": "NYC Foodie",
    },
    {
        "caption": "This hidden gem Italian restaurant changed my life 🍝 #italian #pasta #hiddenGem #restaurant",
        "hashtags": ["italian", "pasta", "hiddenGem", "restaurant"],
        "creator": "pastaking",
        "creator_name": "The Pasta King",
    },
    {
        "caption": "POV: you find the best ramen shop in Tokyo 🍜 #ramen #tokyo #japan #foodtravel",
        "hashtags": ["ramen", "tokyo", "japan", "foodtravel"],
        "creator": "travelwithben",
        "creator_name": "Travel With Ben",
    },
    {
        "caption": "Trying the viral pizza place everyone's talking about 🍕 #pizza #viral #restaurant #foodtiktok",
        "hashtags": ["pizza", "viral", "restaurant", "foodtiktok"],
        "creator": "slicereview",
        "creator_name": "Slice Review",
    },
    {
        "caption": "My morning routine for productivity ☀️ #morning #routine #productivity #grwm",
        "hashtags": ["morning", "routine", "productivity", "grwm"],
        "creator": "dailyvibe",
        "creator_name": "Daily Vibe",
    },
    {
        "caption": "How to train your dog to sit in 3 days 🐕 #dogtok #training #pets",
        "hashtags": ["dogtok", "training", "pets"],
        "creator": "dogtrainer_mike",
        "creator_name": "Mike the Dog Trainer",
    },
    {
        "caption": "This BBQ spot in Texas has the best brisket I've ever had 🥩 #bbq #texas #brisket #restaurant",
        "hashtags": ["bbq", "texas", "brisket", "restaurant"],
        "creator": "bbqhunter",
        "creator_name": "BBQ Hunter",
    },
    {
        "caption": "3 books that changed my perspective on life 📚 #booktok #reading #selfimprovement",
        "hashtags": ["booktok", "reading", "selfimprovement"],
        "creator": "bookworm_anna",
        "creator_name": "Anna Reads",
    },
    {
        "caption": "The brunch spot you NEED to visit in LA 🥞 #brunch #la #losangeles #restaurant #foodie",
        "hashtags": ["brunch", "la", "losangeles", "restaurant", "foodie"],
        "creator": "brunchwithme",
        "creator_name": "Brunch With Me",
    },
]


async def main():
    if not OPENAI_API_KEY:
        print("ERROR: Set OPENAI_API_KEY in your environment")
        sys.exit(1)

    print(f"Connecting to {DATABASE_URL.split('@')[1]}...")
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. Create test user (upsert)
        print("Creating test user...")
        await db.execute(text("""
            INSERT INTO users (id, email, name, auth_provider, auth_provider_id, subscription_tier)
            VALUES (:id, :email, 'Test User', 'email', :email, 'free')
            ON CONFLICT (id) DO NOTHING
        """), {"id": TEST_USER_ID, "email": TEST_EMAIL})

        # Also insert into auth.users if not exists (Supabase FK)
        await db.execute(text("""
            INSERT INTO auth.users (id, email, role, instance_id, aud, created_at, updated_at)
            VALUES (CAST(:id AS uuid), :email, 'authenticated', '00000000-0000-0000-0000-000000000000', 'authenticated', now(), now())
            ON CONFLICT (id) DO NOTHING
        """), {"id": TEST_USER_ID, "email": TEST_EMAIL})

        # 2. Create upload record
        upload_id = str(uuid4())
        print(f"Creating upload record {upload_id[:8]}...")
        await db.execute(text("""
            INSERT INTO uploads (id, user_id, scope, status, total_items, processed_items, consent_given, consent_version, consent_at)
            VALUES (:id, :user_id, 'both', 'complete', :total, :total, true, '1.0', now())
        """), {"id": upload_id, "user_id": TEST_USER_ID, "total": len(FAKE_ENRICHMENTS)})

        # 3. Parse fixture to get real URLs
        print("Parsing fixture JSON...")
        with open(FIXTURE_PATH) as f:
            data = json.load(f)

        urls = []
        liked = data.get("Likes and Favorites", {}).get("Liked Videos", {}).get("VideoList", [])
        for v in liked:
            url = v.get("Link") or v.get("link") or v.get("url")
            if url:
                urls.append(url)

        if not urls:
            # Try alternate structure
            browsing = data.get("Browsing", {}).get("VideoList", [])
            for v in browsing:
                url = v.get("Link") or v.get("link")
                if url:
                    urls.append(url)

        print(f"Found {len(urls)} URLs in fixture")

        # 4. Insert media_events with fake enrichments
        print("Inserting media_events...")
        event_ids = []
        texts_for_embedding = []

        for i, enrichment in enumerate(FAKE_ENRICHMENTS):
            event_id = str(uuid4())
            event_ids.append(event_id)
            url = urls[i] if i < len(urls) else f"https://www.tiktok.com/@user/video/{1000000000 + i}"
            platform_id = str(1000000000 + i)

            full_text = f"{enrichment['caption']} | {' '.join('#' + h for h in enrichment['hashtags'])} | by @{enrichment['creator']}"
            texts_for_embedding.append(full_text)

            await db.execute(text("""
                INSERT INTO media_events (
                    id, user_id, upload_id, platform, platform_id, canonical_url,
                    interaction_type, interaction_at, processing_state,
                    caption_text, hashtags, creator_username, creator_name,
                    media_type, full_text
                ) VALUES (
                    :id, :user_id, :upload_id, 'tiktok', :platform_id, :url,
                    'liked', :ts, 'complete',
                    :caption, :hashtags, :creator, :creator_name,
                    'video', :full_text
                )
                ON CONFLICT (user_id, platform, platform_id) DO UPDATE SET
                    caption_text = EXCLUDED.caption_text,
                    hashtags = EXCLUDED.hashtags,
                    full_text = EXCLUDED.full_text,
                    processing_state = 'complete'
            """), {
                "id": event_id,
                "user_id": TEST_USER_ID,
                "upload_id": upload_id,
                "platform_id": platform_id,
                "url": url,
                "ts": datetime(2025, 6, 15 + i, tzinfo=timezone.utc),
                "caption": enrichment["caption"],
                "hashtags": enrichment["hashtags"],
                "creator": enrichment["creator"],
                "creator_name": enrichment["creator_name"],
                "full_text": full_text,
            })

        await db.commit()
        print(f"Inserted {len(event_ids)} media_events")

        # 5. Generate embeddings via OpenAI
        print("Generating embeddings via OpenAI...")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": texts_for_embedding,
                    "model": "text-embedding-3-small",
                    "dimensions": 1536,
                },
                timeout=60,
            )
            resp.raise_for_status()
            embeddings = sorted(resp.json()["data"], key=lambda d: d["index"])

        # 6. Update media_events with embeddings
        print("Writing embeddings to DB...")
        for i, event_id in enumerate(event_ids):
            vector = embeddings[i]["embedding"]
            vector_str = "[" + ",".join(str(v) for v in vector) + "]"
            await db.execute(text("""
                UPDATE media_events
                SET embedding_vector = CAST(:vec AS vector)
                WHERE id = CAST(:id AS uuid)
            """), {"vec": vector_str, "id": event_id})

        await db.commit()
        print(f"Embeddings written for {len(event_ids)} events")

    await engine.dispose()
    print("\n✅ Seed complete! Test user and 10 media_events ready.")
    print("   - 7 restaurant/food items (tacos, sushi, italian, ramen, pizza, bbq, brunch)")
    print("   - 3 non-food items (productivity, dog training, books)")
    print(f"   - User: {TEST_EMAIL} ({TEST_USER_ID})")
    print("\nRestart your backend and try: 'pull all the restaurants ive liked'")


if __name__ == "__main__":
    asyncio.run(main())
