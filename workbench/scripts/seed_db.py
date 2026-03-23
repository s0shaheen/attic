#!/usr/bin/env python
"""Seed the local database with realistic test data.

Usage:
    python workbench/scripts/seed_db.py

Requires: Supabase reachable (cloud or local) and src/backend/.env configured
Creates: test user, sample upload, 80 diverse media_events, pipeline run
Idempotent: safe to run multiple times.
"""
import asyncio
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / "src" / "backend" / ".env")

import httpx
import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.media_event import MediaEvent
from app.models.upload import Upload
from app.models.upload_pipeline_run import UploadPipelineRun
from app.models.user import User
from app.services.ontology import FACET_NAMES, ONTOLOGY_V1

# Fixed IDs for idempotency
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_UPLOAD_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
TEST_PIPELINE_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
TEST_EMAIL = "test@attic.to"
TEST_PASSWORD = "testpassword123"

# Realistic sample data for generating media events
SAMPLE_CREATORS = [
    ("@homecookemily", "Emily Chen"), ("@fitnesswithkai", "Kai Johnson"),
    ("@comedydan", "Dan Murphy"), ("@techsarah", "Sarah Kim"),
    ("@petloversam", "Sam Rodriguez"), ("@diyqueen", "DIY Queen"),
    ("@bookwormjess", "Jessica Patel"), ("@travelmax", "Max Taylor"),
    ("@beautybymia", "Mia Williams"), ("@gamerpro", "Alex Lee"),
    ("@musicmaker", "Jordan Davis"), ("@fashionista_j", "Jamie Brooks"),
    ("@sciencenerd", "Dr. Nerd"), ("@artstudio", "Studio Art"),
    ("@dancemoves", "Dance Academy"),
]

SAMPLE_CAPTIONS = {
    "food": [
        "this pasta recipe changed my life fr fr 🍝", "the BEST chocolate chip cookies ever 🍪",
        "5 minute meals for when you're lazy", "trying the viral feta pasta hack",
        "my grandma's secret soup recipe 🍲", "meal prep sunday let's gooo",
    ],
    "fashion": [
        "fall outfit inspo 🍂", "thrift haul that went crazy", "how to style one blazer 5 ways",
        "GRWM for date night ✨", "sustainable fashion brands you need to know",
    ],
    "comedy": [
        "when your mom calls during a meeting 😭", "POV: you're the last one in the group chat",
        "things that make NO sense", "every uber driver ever", "my cat judging my life choices",
    ],
    "education": [
        "things they don't teach you in school", "how compound interest actually works 📈",
        "the psychology behind procrastination", "learn Python in 60 seconds",
    ],
    "fitness": [
        "10 min ab workout no equipment needed", "why you're not seeing gains (real talk)",
        "stretches for desk workers 💻", "marathon training week 8 update",
    ],
    "pets": [
        "my dog's reaction to coming home 🐕", "cat vs cucumber experiment",
        "adopting a senior dog changed everything", "parrot learns to say bruh",
    ],
    "technology": [
        "iPhone hack you didn't know about", "is AI taking over? let's talk",
        "my desk setup tour 2026", "apps that saved my productivity",
    ],
    "travel": [
        "hidden gems in Tokyo nobody talks about 🗼", "budget travel tips Europe",
        "van life day 47", "airport hack that saves hours",
    ],
}

SAMPLE_MUSIC = [
    "original sound", "Flowers - Miley Cyrus", "Espresso - Sabrina Carpenter",
    "Levitating - Dua Lipa", "As It Was - Harry Styles", "Anti-Hero - Taylor Swift",
    "Calm Down - Rema", "Unholy - Sam Smith", "About Damn Time - Lizzo",
    "Bad Habit - Steve Lacy",
]


def generate_classification(topic: str) -> dict:
    """Generate a realistic cached_classifications dict for a given topic."""
    tier1 = {}
    tier2 = {}
    confidence = {}

    for facet in FACET_NAMES:
        labels = ONTOLOGY_V1[facet]
        if facet == "topic":
            tier1[facet] = topic
        else:
            tier1[facet] = random.choice(labels)
        confidence[facet] = round(random.uniform(0.6, 0.95), 2)
        # Some facets get tier-2 micro-labels
        if random.random() > 0.5:
            tier2[facet] = [f"{tier1[facet]}_specific_{random.randint(1,5)}"]

    return {"tier1": tier1, "tier2": tier2, "confidence": confidence}


def generate_media_event(index: int, user_id: uuid.UUID, upload_id: uuid.UUID) -> dict:
    """Generate a single realistic media event dict."""
    # Deterministic ID for idempotency
    event_id = uuid.UUID(f"10000000-0000-0000-0000-{index:012d}")
    platform_id = f"tiktok_{7000000000 + index}"

    topic = random.choice(list(SAMPLE_CAPTIONS.keys()))
    caption = random.choice(SAMPLE_CAPTIONS[topic])
    creator_username, creator_name = random.choice(SAMPLE_CREATORS)
    music = random.choice(SAMPLE_MUSIC)

    # Media type distribution: 70% video, 20% image, 10% slideshow
    r = random.random()
    if r < 0.7:
        media_type = "video"
        is_slideshow = False
        image_count = None
    elif r < 0.9:
        media_type = "image"
        is_slideshow = False
        image_count = None
    else:
        media_type = "slideshow"
        is_slideshow = True
        image_count = random.randint(2, 10)

    # Processing state: 80% complete, 10% pending, 10% failed
    r2 = random.random()
    if r2 < 0.8:
        processing_state = "complete"
    elif r2 < 0.9:
        processing_state = "pending"
    else:
        processing_state = "failed"

    # Hashtags from caption + topic
    hashtags = [topic, "fyp", "viral"]
    if "recipe" in caption.lower():
        hashtags.append("recipe")
    if "hack" in caption.lower():
        hashtags.append("lifehack")

    # Interaction date spread over last 6 months
    days_ago = random.randint(0, 180)
    interaction_at = datetime.now(timezone.utc) - timedelta(days=days_ago)

    event = {
        "id": event_id,
        "user_id": user_id,
        "upload_id": upload_id,
        "platform": "tiktok",
        "platform_id": platform_id,
        "canonical_url": f"https://www.tiktok.com/{creator_username}/video/{platform_id}",
        "interaction_type": random.choice(["liked", "favorited"]),
        "interaction_at": interaction_at,
        "processing_state": processing_state,
        "caption_text": caption,
        "hashtags": hashtags,
        "creator_username": creator_username,
        "creator_name": creator_name,
        "media_type": media_type,
        "is_slideshow": is_slideshow,
        "image_count": image_count,
        "music_name": music,
        "music_author": creator_name,
        "music_is_original": random.random() > 0.5,
        "thumbnail_url": f"https://p16-sign.tiktokcdn.com/obj/tos-placeholder-{index}.jpeg",
        "play_count": random.randint(1000, 50_000_000),
        "like_count": random.randint(100, 5_000_000),
        "comment_count": random.randint(10, 100_000),
        "share_count": random.randint(5, 50_000),
        "video_duration_seconds": random.randint(5, 180) if media_type == "video" else None,
        "video_created_at": interaction_at - timedelta(days=random.randint(0, 30)),
        "interaction_hour": interaction_at.hour,
        "interaction_day_of_week": interaction_at.weekday(),
        "hashtag_count": len(hashtags),
        "caption_length": len(caption),
    }

    # Complete items get classifications and optionally embeddings
    if processing_state == "complete":
        event["cached_classifications"] = generate_classification(topic)
        event["full_text"] = f"{caption} {' '.join(hashtags)} {creator_username}"
        # 60% of complete items get a random normalized embedding vector
        if random.random() < 0.6:
            vec = np.random.randn(1536).astype(np.float32)
            vec = vec / np.linalg.norm(vec)
            event["embedding_vector"] = vec.tolist()

    return event


async def create_test_user_via_api(supabase_url: str, service_key: str) -> None:
    """Create test user via Supabase Auth Admin API."""
    url = f"{supabase_url}/auth/v1/admin/users"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": "application/json",
    }
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "email_confirm": True,
        "user_metadata": {"name": "Test User"},
    }

    async with httpx.AsyncClient() as client:
        # Check if user exists
        resp = await client.get(url, headers=headers, params={"page": 1, "per_page": 50})
        if resp.status_code == 200:
            users = resp.json().get("users", [])
            for u in users:
                if u.get("email") == TEST_EMAIL:
                    print(f"  Test user already exists: {u['id']}")
                    return uuid.UUID(u["id"])

        # Create user
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code in (200, 201):
            user_data = resp.json()
            print(f"  Created test user: {user_data['id']}")
            return uuid.UUID(user_data["id"])
        else:
            print(f"  Warning: Could not create auth user ({resp.status_code}): {resp.text}")
            print("  Falling back to direct DB insert")
            return None


async def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set. Run ./scripts/setup-env.sh first.")
        sys.exit(1)

    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        print("ERROR: SUPABASE_URL not set. Run ./scripts/setup-env.sh first.")
        sys.exit(1)
    service_key = os.environ.get("SUPABASE_SECRET_KEY", "")

    # Supabase transaction pooler (port 6543) uses PgBouncer —
    # disable prepared statement caching for asyncpg compatibility
    connect_args = {}
    if "pooler.supabase.com" in database_url or ":6543/" in database_url:
        connect_args["statement_cache_size"] = 0

    engine = create_async_engine(database_url, echo=False, connect_args=connect_args)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("Seeding Attic database...")

    # 1. Create test user via Supabase Auth API
    auth_user_id = None
    if service_key:
        auth_user_id = await create_test_user_via_api(supabase_url, service_key)

    async with async_session() as session:
        # 2. Create/upsert application user
        existing_user = await session.execute(
            select(User).where(User.email == TEST_EMAIL)
        )
        user = existing_user.scalar_one_or_none()
        if user:
            print(f"  User already exists: {user.id}")
            user_id = user.id
        else:
            user_id = auth_user_id or TEST_USER_ID
            user = User(
                id=user_id,
                email=TEST_EMAIL,
                name="Test User",
                auth_provider="email",
                auth_provider_id=str(user_id),
            )
            session.add(user)
            await session.flush()
            print(f"  Created app user: {user_id}")

        # 3. Create/upsert upload
        existing_upload = await session.execute(
            select(Upload).where(Upload.id == TEST_UPLOAD_ID)
        )
        upload = existing_upload.scalar_one_or_none()
        if not upload:
            upload = Upload(
                id=TEST_UPLOAD_ID,
                user_id=user_id,
                source_platform="tiktok",
                scope="both",
                status="complete",
                total_items=80,
                processed_items=80,
                consent_given=True,
                consent_version="1.0",
                consent_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            session.add(upload)
            await session.flush()
            print("  Created upload")
        else:
            print("  Upload already exists")

        # 4. Create/upsert pipeline run
        existing_run = await session.execute(
            select(UploadPipelineRun).where(UploadPipelineRun.id == TEST_PIPELINE_RUN_ID)
        )
        run = existing_run.scalar_one_or_none()
        if not run:
            run = UploadPipelineRun(
                id=TEST_PIPELINE_RUN_ID,
                upload_id=TEST_UPLOAD_ID,
                user_id=user_id,
                status="complete",
                total_items=80,
                items_enriched=80,
                items_transcribed=56,  # ~70% video
                items_embedded=48,
                items_complete=64,
                items_failed=8,
                started_at=datetime.now(timezone.utc) - timedelta(hours=1),
                finished_at=datetime.now(timezone.utc),
            )
            session.add(run)
            await session.flush()
            print("  Created pipeline run")
        else:
            print("  Pipeline run already exists")

        # 5. Generate and upsert media events
        random.seed(42)  # Reproducible
        events_created = 0
        events_skipped = 0

        for i in range(80):
            event_data = generate_media_event(i, user_id, TEST_UPLOAD_ID)
            event_id = event_data.pop("id")

            existing = await session.execute(
                select(MediaEvent).where(MediaEvent.id == event_id)
            )
            if existing.scalar_one_or_none():
                events_skipped += 1
                continue

            event = MediaEvent(id=event_id, **event_data)
            session.add(event)
            events_created += 1

        await session.commit()

    print(f"\n  Media events: {events_created} created, {events_skipped} already existed")

    # Summary
    topic_counts = {}
    random.seed(42)
    for i in range(80):
        topic = random.choice(list(SAMPLE_CAPTIONS.keys()))
        topic_counts[topic] = topic_counts.get(topic, 0) + 1

    print(f"\nSeed complete!")
    print(f"  User: {TEST_EMAIL} / {TEST_PASSWORD}")
    print(f"  Upload: {TEST_UPLOAD_ID}")
    print(f"  Media events: 80 total")
    print(f"  Topic distribution: {json.dumps(topic_counts, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
