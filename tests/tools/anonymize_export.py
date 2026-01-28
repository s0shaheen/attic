#!/usr/bin/env python3
"""
Anonymize TikTok export data for safe use in tests.

Performs deterministic PII replacement:
- Names, emails, phones, addresses, IPs → fake but consistent data
- Usernames → mapped consistently across all sections
- URL tokens → stripped
- Dates → preserved (patterns matter for testing)

Usage:
    python tests/tools/anonymize_export.py <input_file> <output_file>
    python tests/tools/anonymize_export.py  # Uses default paths
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

# Deterministic fake data pools - indexed by hash of original value
FIRST_NAMES = [
    "Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry",
    "Iris", "Jack", "Kate", "Leo", "Maya", "Noah", "Olivia", "Paul",
    "Quinn", "Rose", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xavier",
    "Yara", "Zach"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez"
]

CITIES = [
    "Springfield", "Riverside", "Franklin", "Clinton", "Madison", "Georgetown",
    "Salem", "Bristol", "Fairview", "Manchester", "Milton", "Oxford"
]

STATES = ["CA", "TX", "NY", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]

STREETS = [
    "Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Pine Rd", "Elm St",
    "Park Ave", "Lake Blvd", "Hill Rd", "River St", "Forest Dr", "Valley Rd"
]


def deterministic_hash(value: str, salt: str = "") -> int:
    """Generate a deterministic integer from a string value."""
    h = hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()
    return int(h[:8], 16)


def anonymize_email(email: str) -> str:
    """Replace email with deterministic fake email."""
    if not email or email == "N/A":
        return email
    idx = deterministic_hash(email, "email")
    first = FIRST_NAMES[idx % len(FIRST_NAMES)].lower()
    last = LAST_NAMES[(idx >> 8) % len(LAST_NAMES)].lower()
    domain = ["example.com", "test.org", "sample.net"][idx % 3]
    return f"{first}.{last}@{domain}"


def anonymize_phone(phone: str) -> str:
    """Replace phone with deterministic fake phone."""
    if not phone or phone == "N/A":
        return phone
    idx = deterministic_hash(phone, "phone")
    area = 200 + (idx % 800)
    prefix = 200 + ((idx >> 10) % 800)
    line = idx % 10000
    return f"+1-{area}-{prefix}-{line:04d}"


def anonymize_name(name: str, salt: str = "name") -> str:
    """Replace name with deterministic fake name."""
    if not name or name == "N/A":
        return name
    idx = deterministic_hash(name, salt)
    first = FIRST_NAMES[idx % len(FIRST_NAMES)]
    last = LAST_NAMES[(idx >> 8) % len(LAST_NAMES)]
    return f"{first} {last}"


def anonymize_first_name(name: str) -> str:
    """Replace first name with deterministic fake first name."""
    if not name or name == "N/A":
        return name
    idx = deterministic_hash(name, "first")
    return FIRST_NAMES[idx % len(FIRST_NAMES)]


def anonymize_last_name(name: str) -> str:
    """Replace last name with deterministic fake last name."""
    if not name or name == "N/A":
        return name
    idx = deterministic_hash(name, "last")
    return LAST_NAMES[idx % len(LAST_NAMES)]


def anonymize_address(address: str) -> str:
    """Replace address with deterministic fake address."""
    if not address or address == "N/A":
        return address
    idx = deterministic_hash(address, "address")
    num = 100 + (idx % 9900)
    street = STREETS[idx % len(STREETS)]
    return f"{num} {street}"


def anonymize_city(city: str) -> str:
    """Replace city with deterministic fake city."""
    if not city or city == "N/A":
        return city
    idx = deterministic_hash(city, "city")
    return CITIES[idx % len(CITIES)]


def anonymize_state(state: str) -> str:
    """Replace state with deterministic fake state."""
    if not state or state == "N/A":
        return state
    idx = deterministic_hash(state, "state")
    return STATES[idx % len(STATES)]


def anonymize_zipcode(zipcode: str) -> str:
    """Replace zipcode with deterministic fake zipcode."""
    if not zipcode or zipcode == "N/A":
        return zipcode
    idx = deterministic_hash(zipcode, "zip")
    return f"{10000 + (idx % 90000)}"


def anonymize_ip(ip: str) -> str:
    """Replace IP with deterministic fake IP in 10.x.x.x range."""
    if not ip or ip == "N/A":
        return ip
    idx = deterministic_hash(ip, "ip")
    return f"10.{(idx >> 16) % 256}.{(idx >> 8) % 256}.{idx % 256}"


def anonymize_birthdate(birthdate: str) -> str:
    """Shift birthdate by deterministic offset while preserving format."""
    if not birthdate or birthdate == "N/A":
        return birthdate
    # Replace with generic date preserving format
    idx = deterministic_hash(birthdate, "birth")
    year = 1980 + (idx % 30)  # Born between 1980-2010
    month = 1 + (idx % 12)
    day = 1 + (idx % 28)
    return f"{year}-{month:02d}-{day:02d}"


# Username mapping cache for consistency across sections
_username_cache: dict[str, str] = {}


def anonymize_username(username: str) -> str:
    """Replace username with deterministic fake username, cached for consistency."""
    if not username or username == "N/A":
        return username

    if username in _username_cache:
        return _username_cache[username]

    idx = deterministic_hash(username, "user")
    first = FIRST_NAMES[idx % len(FIRST_NAMES)].lower()
    suffix = idx % 10000
    fake_username = f"{first}_{suffix}"
    _username_cache[username] = fake_username
    return fake_username


def strip_url_tokens(url: str) -> str:
    """Remove authentication tokens from URLs."""
    if not url or url == "N/A":
        return url
    # Remove common token patterns from TikTok URLs
    url = re.sub(r'\?.*', '', url)  # Remove query params
    url = re.sub(r'&.*', '', url)   # Remove additional params
    return url


def anonymize_comment_text(text: str) -> str:
    """Anonymize @mentions in comment text while preserving content."""
    if not text or text == "N/A":
        return text
    # Replace @mentions with anonymized usernames
    def replace_mention(match: re.Match) -> str:
        username = match.group(1)
        return f"@{anonymize_username(username)}"

    return re.sub(r'@(\w+)', replace_mention, text)


def anonymize_profile_and_settings(data: dict) -> dict:
    """Anonymize the Profile And Settings section."""
    result = {}

    for key, value in data.items():
        if key == "Autofill":
            result[key] = {
                "PhoneNumber": anonymize_phone(value.get("PhoneNumber", "")),
                "Email": anonymize_email(value.get("Email", "")),
                "FirstName": anonymize_first_name(value.get("FirstName", "")),
                "LastName": anonymize_last_name(value.get("LastName", "")),
                "Address": anonymize_address(value.get("Address", "")),
                "ZipCode": anonymize_zipcode(value.get("ZipCode", "")),
                "Unit": value.get("Unit", ""),  # Keep unit as-is (apt number)
                "City": anonymize_city(value.get("City", "")),
                "State": anonymize_state(value.get("State", "")),
                "Country": value.get("Country", ""),  # Keep country as-is
            }
        elif key == "Profile Info":
            profile_map = value.get("ProfileMap", {})
            result[key] = {
                "App": value.get("App", 1),
                "ProfileMap": {
                    "PlatformInfo": profile_map.get("PlatformInfo", []),
                    "bioDescription": profile_map.get("bioDescription", ""),
                    "birthDate": anonymize_birthdate(profile_map.get("birthDate", "")),
                    "emailAddress": anonymize_email(profile_map.get("emailAddress", "")),
                    "likesReceived": profile_map.get("likesReceived", ""),
                    "profilePhoto": strip_url_tokens(profile_map.get("profilePhoto", "")),
                    "profileVideo": strip_url_tokens(profile_map.get("profileVideo", "")),
                    "telephoneNumber": anonymize_phone(profile_map.get("telephoneNumber", "")),
                    "userName": anonymize_username(profile_map.get("userName", "")),
                }
            }
        elif key in ("Follower", "Following", "Block List"):
            # These are lists of users with UserName field
            if isinstance(value, dict):
                result[key] = {}
                for subkey, subvalue in value.items():
                    if isinstance(subvalue, list):
                        result[key][subkey] = [
                            {**item, "UserName": anonymize_username(item.get("UserName", ""))}
                            if isinstance(item, dict) else item
                            for item in subvalue
                        ]
                    else:
                        result[key][subkey] = subvalue
            else:
                result[key] = value
        elif key == "Settings":
            result[key] = value  # Settings don't contain PII
        else:
            result[key] = value

    return result


def anonymize_direct_messages(data: dict) -> dict:
    """Anonymize the Direct Message section."""
    result = {}

    dm_section = data.get("Direct Messages", {})
    result["Direct Messages"] = {}

    chat_history = dm_section.get("ChatHistory", {})
    anonymized_chats = {}

    for chat_name, messages in chat_history.items():
        # Anonymize the chat name (usually a username)
        anon_chat_name = anonymize_username(chat_name)

        if isinstance(messages, list):
            anon_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    anon_msg = dict(msg)
                    if "From" in msg:
                        anon_msg["From"] = anonymize_username(msg["From"])
                    if "Content" in msg:
                        anon_msg["Content"] = anonymize_comment_text(msg["Content"])
                    anon_messages.append(anon_msg)
                else:
                    anon_messages.append(msg)
            anonymized_chats[anon_chat_name] = anon_messages
        else:
            anonymized_chats[anon_chat_name] = messages

    result["Direct Messages"]["ChatHistory"] = anonymized_chats

    # Copy other DM fields
    for key, value in dm_section.items():
        if key != "ChatHistory":
            result["Direct Messages"][key] = value

    return result


def anonymize_comments(data: dict) -> dict:
    """Anonymize the Comment section."""
    result = {}

    comments_section = data.get("Comments", {})
    result["Comments"] = {
        "App": comments_section.get("App", 1),
        "CommentsList": []
    }

    for comment in comments_section.get("CommentsList", []):
        anon_comment = dict(comment)
        if "comment" in comment:
            anon_comment["comment"] = anonymize_comment_text(comment["comment"])
        result["Comments"]["CommentsList"].append(anon_comment)

    return result


def anonymize_your_activity(data: dict) -> dict:
    """Anonymize the Your Activity section."""
    result = {}

    for key, value in data.items():
        if key == "Login History":
            login_list = value.get("LoginHistoryList", [])
            result[key] = {
                "LoginHistoryList": [
                    {**item, "IP": anonymize_ip(item.get("IP", ""))}
                    if isinstance(item, dict) else item
                    for item in login_list
                ]
            }
        else:
            result[key] = value

    return result


def anonymize_tiktok_shop(data: dict) -> dict:
    """Anonymize the TikTok Shop section (addresses in orders)."""
    result = {}

    for key, value in data.items():
        if key in ("Order History", "Current Payment Information"):
            if isinstance(value, dict):
                result[key] = anonymize_nested_pii(value)
            elif isinstance(value, list):
                result[key] = [anonymize_nested_pii(item) for item in value]
            else:
                result[key] = value
        else:
            result[key] = value

    return result


def anonymize_nested_pii(obj: Any) -> Any:
    """Recursively anonymize common PII field names in nested structures."""
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            lower_key = key.lower()
            if "email" in lower_key:
                result[key] = anonymize_email(value) if isinstance(value, str) else anonymize_nested_pii(value)
            elif "phone" in lower_key or "telephone" in lower_key:
                result[key] = anonymize_phone(value) if isinstance(value, str) else anonymize_nested_pii(value)
            elif lower_key in ("name", "fullname", "full_name", "receiver"):
                result[key] = anonymize_name(value) if isinstance(value, str) else anonymize_nested_pii(value)
            elif lower_key in ("firstname", "first_name"):
                result[key] = anonymize_first_name(value) if isinstance(value, str) else anonymize_nested_pii(value)
            elif lower_key in ("lastname", "last_name"):
                result[key] = anonymize_last_name(value) if isinstance(value, str) else anonymize_nested_pii(value)
            elif lower_key in ("address", "street"):
                result[key] = anonymize_address(value) if isinstance(value, str) else anonymize_nested_pii(value)
            elif lower_key == "city":
                result[key] = anonymize_city(value) if isinstance(value, str) else anonymize_nested_pii(value)
            elif lower_key == "state":
                result[key] = anonymize_state(value) if isinstance(value, str) else anonymize_nested_pii(value)
            elif lower_key in ("zip", "zipcode", "zip_code", "postal"):
                result[key] = anonymize_zipcode(value) if isinstance(value, str) else anonymize_nested_pii(value)
            elif lower_key == "ip":
                result[key] = anonymize_ip(value) if isinstance(value, str) else anonymize_nested_pii(value)
            elif lower_key == "username":
                result[key] = anonymize_username(value) if isinstance(value, str) else anonymize_nested_pii(value)
            else:
                result[key] = anonymize_nested_pii(value)
        return result
    elif isinstance(obj, list):
        return [anonymize_nested_pii(item) for item in obj]
    else:
        return obj


def anonymize_export(data: dict) -> dict:
    """Anonymize an entire TikTok export."""
    global _username_cache
    _username_cache = {}  # Reset cache for fresh run

    result = {}

    for section, content in data.items():
        if section == "Profile And Settings":
            result[section] = anonymize_profile_and_settings(content)
        elif section == "Direct Message":
            result[section] = anonymize_direct_messages(content)
        elif section == "Comment":
            result[section] = anonymize_comments(content)
        elif section == "Your Activity":
            result[section] = anonymize_your_activity(content)
        elif section == "TikTok Shop":
            result[section] = anonymize_tiktok_shop(content)
        else:
            # For other sections, do a generic pass for common PII patterns
            result[section] = anonymize_nested_pii(content)

    return result


def main():
    parser = argparse.ArgumentParser(description="Anonymize TikTok export data")
    parser.add_argument(
        "input_file",
        nargs="?",
        default="tests/fixtures/tiktok-exports/real/user_data_tiktok.json",
        help="Input TikTok export JSON file"
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        default="tests/fixtures/tiktok-exports/anonymized/full_anonymized.json",
        help="Output anonymized JSON file"
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation (default: 2)"
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_file)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("Anonymizing...")
    anonymized = anonymize_export(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(anonymized, f, indent=args.indent, ensure_ascii=False)

    print(f"Done! Anonymized {len(data)} sections.")
    print(f"Username mappings created: {len(_username_cache)}")


if __name__ == "__main__":
    main()
