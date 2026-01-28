#!/usr/bin/env python3
"""
Generate fully synthetic TikTok export data for multi-user testing scenarios.

Creates:
- user_alice.json: Power user (500 likes, 2000 watch history)
- user_bob.json: Casual user (50 likes, 100 watch history)

All data is completely synthetic - no real PII involved.

Usage:
    python tests/tools/generate_synthetic.py
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# Output directory
SYNTHETIC_DIR = Path("tests/fixtures/tiktok-exports/synthetic")

# Seed for reproducibility
random.seed(42)


def random_date(start_year: int = 2022, end_year: int = 2025) -> str:
    """Generate a random date string."""
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    random_seconds = random.randint(0, 86399)
    dt = start + timedelta(days=random_days, seconds=random_seconds)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def random_tiktok_url() -> str:
    """Generate a random TikTok video URL."""
    video_id = random.randint(1000000000000000000, 9999999999999999999)
    return f"https://www.tiktokv.com/share/video/{video_id}"


def generate_likes(count: int) -> dict:
    """Generate synthetic like list."""
    items = []
    for _ in range(count):
        items.append({
            "date": random_date(),
            "link": random_tiktok_url()
        })
    return {
        "Like List": {
            "ItemFavoriteList": items
        }
    }


def generate_favorites(count: int) -> dict:
    """Generate synthetic favorites."""
    items = []
    for _ in range(count):
        items.append({
            "date": random_date(),
            "link": random_tiktok_url()
        })
    return {
        "Favorite Videos": {
            "FavoriteVideoList": items
        }
    }


def generate_watch_history(count: int) -> dict:
    """Generate synthetic watch history."""
    items = []
    for _ in range(count):
        items.append({
            "Date": random_date(),
            "Link": random_tiktok_url()
        })
    return {
        "Watch History": {
            "VideoList": items
        }
    }


def generate_comments(count: int, username: str) -> dict:
    """Generate synthetic comments."""
    comment_templates = [
        "This is amazing!",
        "Love this content",
        "So true",
        "Facts",
        "Underrated",
        "This made my day",
        "W",
        "L take",
        "Respect",
        "Need more of this",
        "This is it",
        "Incredible",
        "Mind blown",
        "Game changer",
        "Pure gold",
    ]

    items = []
    for _ in range(count):
        items.append({
            "date": random_date(),
            "comment": random.choice(comment_templates),
            "photo": "N/A",
            "url": random_tiktok_url()
        })

    return {
        "Comments": {
            "App": 1,
            "CommentsList": items
        }
    }


def generate_profile(
    username: str,
    first_name: str,
    last_name: str,
    email: str,
    follower_count: int = 100,
    following_count: int = 200
) -> dict:
    """Generate synthetic profile."""
    return {
        "Autofill": {
            "PhoneNumber": f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            "Email": email,
            "FirstName": first_name,
            "LastName": last_name,
            "Address": f"{random.randint(100, 9999)} Test Street",
            "ZipCode": f"{random.randint(10000, 99999)}",
            "Unit": "",
            "City": "Testville",
            "State": "CA",
            "Country": "US"
        },
        "Block List": {"BlockList": []},
        "Follower": {
            "FollowerList": [
                {"Date": random_date(), "UserName": f"follower_{i}"}
                for i in range(min(follower_count, 50))  # Cap at 50 for file size
            ]
        },
        "Following": {
            "FollowingList": [
                {"Date": random_date(), "UserName": f"following_{i}"}
                for i in range(min(following_count, 50))  # Cap at 50 for file size
            ]
        },
        "Profile Info": {
            "App": 1,
            "ProfileMap": {
                "PlatformInfo": [{"key": "device", "value": "iPhone"}],
                "bioDescription": f"Synthetic test user {username}",
                "birthDate": f"{random.randint(1985, 2005)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                "emailAddress": email,
                "likesReceived": str(random.randint(100, 10000)),
                "profilePhoto": "",
                "profileVideo": "",
                "telephoneNumber": "",
                "userName": username
            }
        },
        "Settings": {}
    }


def generate_login_history(count: int) -> dict:
    """Generate synthetic login history."""
    items = []
    for i in range(count):
        items.append({
            "Date": random_date(),
            "IP": f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}",
            "DeviceModel": random.choice(["iPhone 14", "iPhone 13", "Pixel 7", "Galaxy S23"]),
            "DeviceSystem": random.choice(["iOS 17", "iOS 16", "Android 14", "Android 13"]),
            "NetworkType": random.choice(["WiFi", "Mobile", "WiFi"]),
            "Carrier": random.choice(["", "Verizon", "AT&T", "T-Mobile"])
        })
    return {
        "Login History": {
            "LoginHistoryList": items
        }
    }


def generate_searches(count: int) -> dict:
    """Generate synthetic search history."""
    search_terms = [
        "cooking tips", "workout routine", "travel vlog", "music remix",
        "funny cats", "life hacks", "tech review", "fashion trends",
        "motivation", "study tips", "art tutorial", "gaming highlights"
    ]

    items = []
    for _ in range(count):
        items.append({
            "Date": random_date(),
            "SearchTerm": random.choice(search_terms)
        })

    return {
        "Searches": {
            "SearchList": items
        }
    }


def generate_synthetic_user(
    username: str,
    first_name: str,
    last_name: str,
    email: str,
    likes_count: int,
    favorites_count: int,
    watch_history_count: int,
    comments_count: int,
    follower_count: int,
    following_count: int
) -> dict:
    """Generate a complete synthetic user export."""

    likes_data = generate_likes(likes_count)
    favorites_data = generate_favorites(favorites_count)

    return {
        "Comment": generate_comments(comments_count, username),
        "Direct Message": {
            "Direct Messages": {
                "ChatHistory": {}
            }
        },
        "Income+ Wallet": {
            "Transaction History": {
                "TransactionList": []
            }
        },
        "Likes and Favorites": {
            "Favorite Collection": {},
            "Favorite Effects": {"FavoriteEffectsList": []},
            "Favorite Hashtags": {"FavoriteHashtagList": []},
            "Favorite Location": {},
            "Favorite Sounds": {"FavoriteSoundList": []},
            **favorites_data,
            **likes_data
        },
        "Location Review": {
            "Location Reviews": {"LocationReviewList": []}
        },
        "Post": {
            "Posts": {"PostList": []},
            "Recently Deleted Posts": {"DeletedPostList": []}
        },
        "Profile And Settings": generate_profile(
            username, first_name, last_name, email,
            follower_count, following_count
        ),
        "TikTok Live": {
            "Go Live History": {"GoLiveList": []},
            "Go Live Settings": {},
            "Watch Live History": {"WatchLiveList": []},
            "Watch Live Settings": {}
        },
        "TikTok Shop": {
            "Communication With Shops": {},
            "Current Payment Information": {},
            "Customer Support History": {},
            "Order Dispute History": {},
            "Order History": {}
        },
        "Your Activity": {
            "Ad Interests": {"AdInterestList": []},
            "Instant Form Ads Responses": {},
            **generate_login_history(min(50, watch_history_count // 20)),
            "Off TikTok Activity": {},
            "Purchases": {"PurchaseList": []},
            **generate_searches(min(100, watch_history_count // 10)),
            "Share History": {"ShareList": []},
            "Status": {},
            **generate_watch_history(watch_history_count)
        }
    }


def main():
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    # User Alice: Power user
    print("Generating user_alice.json (power user)...")
    alice = generate_synthetic_user(
        username="alice_power",
        first_name="Alice",
        last_name="Power",
        email="alice.power@example.com",
        likes_count=500,
        favorites_count=200,
        watch_history_count=2000,
        comments_count=150,
        follower_count=5000,
        following_count=1000
    )
    alice_path = SYNTHETIC_DIR / "user_alice.json"
    with open(alice_path, "w", encoding="utf-8") as f:
        json.dump(alice, f, indent=2, ensure_ascii=False)
    print(f"  Written: {alice_path}")

    # User Bob: Casual user
    print("Generating user_bob.json (casual user)...")
    bob = generate_synthetic_user(
        username="bob_casual",
        first_name="Bob",
        last_name="Casual",
        email="bob.casual@example.com",
        likes_count=50,
        favorites_count=20,
        watch_history_count=100,
        comments_count=10,
        follower_count=150,
        following_count=300
    )
    bob_path = SYNTHETIC_DIR / "user_bob.json"
    with open(bob_path, "w", encoding="utf-8") as f:
        json.dump(bob, f, indent=2, ensure_ascii=False)
    print(f"  Written: {bob_path}")

    print(f"\nGenerated 2 synthetic user files in {SYNTHETIC_DIR}")


if __name__ == "__main__":
    main()
