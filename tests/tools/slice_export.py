#!/usr/bin/env python3
"""
Generate sliced versions of TikTok export data for different test scenarios.

Creates:
- minimal.json: 1-5 items per category for fast unit tests
- likes_only.json: Just the Likes and Favorites section
- favorites_only.json: Just favorite videos
- watch_history_only.json: Just watch history
- comments_only.json: Just comments

Also generates edge case fixtures:
- empty_export.json: Valid structure with empty arrays
- missing_fields.json: Partial/incomplete export
- null_values.json: Categories with null values
- extra_fields.json: Unknown fields for forward compatibility
- malformed_json.txt: Invalid JSON for error handling

Usage:
    python tests/tools/slice_export.py [input_file]
    python tests/tools/slice_export.py  # Uses default anonymized file
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Output directories
SLICES_DIR = Path("tests/fixtures/tiktok-exports/slices")
EDGE_CASES_DIR = Path("tests/fixtures/tiktok-exports/edge_cases")


def slice_list(items: list, max_items: int = 5) -> list:
    """Take up to max_items from a list."""
    return items[:max_items]


def slice_dict_lists(obj: Any, max_items: int = 5) -> Any:
    """Recursively slice all lists in a nested structure."""
    if isinstance(obj, dict):
        return {k: slice_dict_lists(v, max_items) for k, v in obj.items()}
    elif isinstance(obj, list):
        sliced = slice_list(obj, max_items)
        return [slice_dict_lists(item, max_items) for item in sliced]
    else:
        return obj


def create_minimal_slice(data: dict) -> dict:
    """Create a minimal slice with 1-5 items per category."""
    return slice_dict_lists(data, max_items=5)


def create_likes_only_slice(data: dict) -> dict:
    """Extract just the Likes and Favorites section."""
    return {
        "Likes and Favorites": data.get("Likes and Favorites", {})
    }


def create_favorites_only_slice(data: dict) -> dict:
    """Extract just the Favorite Videos."""
    likes_section = data.get("Likes and Favorites", {})
    return {
        "Likes and Favorites": {
            "Favorite Videos": likes_section.get("Favorite Videos", {})
        }
    }


def create_watch_history_only_slice(data: dict) -> dict:
    """Extract just the Watch History."""
    activity = data.get("Your Activity", {})
    return {
        "Your Activity": {
            "Watch History": activity.get("Watch History", {})
        }
    }


def create_comments_only_slice(data: dict) -> dict:
    """Extract just the Comments section."""
    return {
        "Comment": data.get("Comment", {})
    }


def create_empty_export() -> dict:
    """Create a valid export structure with empty arrays."""
    return {
        "Comment": {
            "Comments": {
                "App": 1,
                "CommentsList": []
            }
        },
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
            "Favorite Videos": {"FavoriteVideoList": []},
            "Like List": {"ItemFavoriteList": []}
        },
        "Location Review": {
            "Location Reviews": {"LocationReviewList": []}
        },
        "Post": {
            "Posts": {"PostList": []},
            "Recently Deleted Posts": {"DeletedPostList": []}
        },
        "Profile And Settings": {
            "Autofill": {
                "PhoneNumber": "",
                "Email": "",
                "FirstName": "",
                "LastName": "",
                "Address": "",
                "ZipCode": "",
                "Unit": "",
                "City": "",
                "State": "",
                "Country": ""
            },
            "Block List": {"BlockList": []},
            "Follower": {"FollowerList": []},
            "Following": {"FollowingList": []},
            "Profile Info": {
                "App": 1,
                "ProfileMap": {
                    "PlatformInfo": [],
                    "bioDescription": "",
                    "birthDate": "",
                    "emailAddress": "",
                    "likesReceived": "0",
                    "profilePhoto": "",
                    "profileVideo": "",
                    "telephoneNumber": "",
                    "userName": ""
                }
            },
            "Settings": {}
        },
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
            "Login History": {"LoginHistoryList": []},
            "Off TikTok Activity": {},
            "Purchases": {"PurchaseList": []},
            "Searches": {"SearchList": []},
            "Share History": {"ShareList": []},
            "Status": {},
            "Watch History": {"VideoList": []}
        }
    }


def create_missing_fields_export() -> dict:
    """Create an export with missing expected fields."""
    return {
        "Comment": {
            # Missing Comments.CommentsList
            "Comments": {
                "App": 1
            }
        },
        "Likes and Favorites": {
            # Missing several subsections
            "Like List": {
                "ItemFavoriteList": [
                    {
                        # Missing 'date' field
                        "link": "https://www.tiktokv.com/share/video/123"
                    }
                ]
            }
        },
        # Missing Profile And Settings entirely
        "Your Activity": {
            # Missing Watch History
            "Login History": {
                "LoginHistoryList": []
            }
        }
    }


def create_null_values_export() -> dict:
    """Create an export with null values in various places."""
    return {
        "Comment": {
            "Comments": {
                "App": 1,
                "CommentsList": [
                    {
                        "date": None,
                        "comment": None,
                        "photo": "N/A",
                        "url": None
                    },
                    {
                        "date": "2024-01-01 12:00:00",
                        "comment": "Valid comment",
                        "photo": None,
                        "url": ""
                    }
                ]
            }
        },
        "Likes and Favorites": {
            "Like List": {
                "ItemFavoriteList": None  # Entire list is null
            },
            "Favorite Videos": {
                "FavoriteVideoList": [
                    {"date": None, "link": "https://example.com/video1"},
                    None,  # Null item in list
                    {"date": "2024-01-01", "link": None}
                ]
            }
        },
        "Profile And Settings": None,  # Entire section is null
        "Your Activity": {
            "Watch History": {
                "VideoList": [
                    {"Date": None, "Link": "https://example.com/v1"},
                    {"Date": "2024-01-01", "Link": None}
                ]
            }
        }
    }


def create_extra_fields_export() -> dict:
    """Create an export with extra/unknown fields for forward compatibility testing."""
    return {
        "Comment": {
            "Comments": {
                "App": 1,
                "CommentsList": [
                    {
                        "date": "2024-01-01 12:00:00",
                        "comment": "Test comment",
                        "photo": "N/A",
                        "url": "",
                        "unknown_field": "should be ignored",
                        "new_feature_data": {"nested": "data"}
                    }
                ],
                "NewMetadataField": "v2.0"
            }
        },
        "Likes and Favorites": {
            "Like List": {
                "ItemFavoriteList": [
                    {
                        "date": "2024-01-01 12:00:00",
                        "link": "https://example.com/video1",
                        "engagement_score": 0.95,  # New field
                        "ai_category": "entertainment"  # New field
                    }
                ]
            },
            "New Category": {  # Entirely new category
                "items": []
            }
        },
        "Profile And Settings": {
            "Profile Info": {
                "App": 1,
                "ProfileMap": {
                    "userName": "test_user",
                    "bioDescription": "Test bio",
                    "verificationStatus": "verified",  # New field
                    "creatorTier": "gold"  # New field
                }
            }
        },
        "New Top Level Section": {  # Entirely new section
            "data": []
        }
    }


def create_malformed_json() -> str:
    """Create invalid JSON for error handling tests."""
    return """{
    "Comment": {
        "Comments": {
            "CommentsList": [
                {"date": "2024-01-01", "comment": "unclosed string,
            ]
        }
    },
    "Likes and Favorites": {
        "Like List": {
            // This is not valid JSON - comments aren't allowed
            "items": [1, 2, 3,]  // trailing comma
        }
    }
    // Missing closing brace
"""


def generate_all_slices(input_file: Path) -> None:
    """Generate all slice files from the input export."""
    print(f"Reading: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    SLICES_DIR.mkdir(parents=True, exist_ok=True)

    slices = [
        ("minimal.json", create_minimal_slice(data)),
        ("likes_only.json", create_likes_only_slice(data)),
        ("favorites_only.json", create_favorites_only_slice(data)),
        ("watch_history_only.json", create_watch_history_only_slice(data)),
        ("comments_only.json", create_comments_only_slice(data)),
    ]

    for filename, slice_data in slices:
        output_path = SLICES_DIR / filename
        print(f"Writing: {output_path}")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(slice_data, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(slices)} slice files in {SLICES_DIR}")


def generate_edge_cases() -> None:
    """Generate all edge case fixture files."""
    EDGE_CASES_DIR.mkdir(parents=True, exist_ok=True)

    edge_cases = [
        ("empty_export.json", create_empty_export()),
        ("missing_fields.json", create_missing_fields_export()),
        ("null_values.json", create_null_values_export()),
        ("extra_fields.json", create_extra_fields_export()),
    ]

    for filename, data in edge_cases:
        output_path = EDGE_CASES_DIR / filename
        print(f"Writing: {output_path}")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # Write malformed JSON separately (it's a string, not valid JSON)
    malformed_path = EDGE_CASES_DIR / "malformed_json.txt"
    print(f"Writing: {malformed_path}")
    with open(malformed_path, "w", encoding="utf-8") as f:
        f.write(create_malformed_json())

    print(f"Generated {len(edge_cases) + 1} edge case files in {EDGE_CASES_DIR}")


def main():
    parser = argparse.ArgumentParser(description="Generate TikTok export slices and edge cases")
    parser.add_argument(
        "input_file",
        nargs="?",
        default="tests/fixtures/tiktok-exports/anonymized/full_anonymized.json",
        help="Input TikTok export JSON file (should be anonymized)"
    )
    parser.add_argument(
        "--slices-only",
        action="store_true",
        help="Only generate slices, not edge cases"
    )
    parser.add_argument(
        "--edge-cases-only",
        action="store_true",
        help="Only generate edge cases, not slices"
    )
    args = parser.parse_args()

    if args.edge_cases_only:
        generate_edge_cases()
    elif args.slices_only:
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}", file=sys.stderr)
            print("Run anonymize_export.py first to create the anonymized file.", file=sys.stderr)
            sys.exit(1)
        generate_all_slices(input_path)
    else:
        # Generate both
        input_path = Path(args.input_file)
        if input_path.exists():
            generate_all_slices(input_path)
        else:
            print(f"Warning: Input file not found: {input_path}", file=sys.stderr)
            print("Skipping slice generation. Run anonymize_export.py first.", file=sys.stderr)

        generate_edge_cases()

    print("Done!")


if __name__ == "__main__":
    main()
