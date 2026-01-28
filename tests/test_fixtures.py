"""
Tests to verify TikTok export fixtures load and work correctly.

Run with: pytest tests/test_fixtures.py -v
"""


def test_minimal_fixture_loads(tiktok_export_minimal):
    """Verify minimal fixture loads and has expected structure."""
    assert isinstance(tiktok_export_minimal, dict)
    assert "Likes and Favorites" in tiktok_export_minimal
    assert "Comment" in tiktok_export_minimal


def test_minimal_fixture_has_limited_items(tiktok_export_minimal):
    """Verify minimal fixture has <= 5 items per list."""
    likes = tiktok_export_minimal.get("Likes and Favorites", {})
    like_list = likes.get("Like List", {}).get("ItemFavoriteList", [])
    assert len(like_list) <= 5


def test_full_anonymized_fixture_loads(tiktok_export_full_anonymized):
    """Verify full anonymized fixture loads."""
    assert isinstance(tiktok_export_full_anonymized, dict)
    # Check expected top-level sections
    expected_sections = [
        "Comment",
        "Direct Message",
        "Likes and Favorites",
        "Profile And Settings",
        "Your Activity"
    ]
    for section in expected_sections:
        assert section in tiktok_export_full_anonymized


def test_likes_only_fixture(tiktok_export_likes_only):
    """Verify likes-only fixture has only likes section."""
    assert "Likes and Favorites" in tiktok_export_likes_only
    # Should not have other sections
    assert "Comment" not in tiktok_export_likes_only
    assert "Profile And Settings" not in tiktok_export_likes_only


def test_empty_fixture(tiktok_export_empty):
    """Verify empty fixture has valid structure with empty arrays."""
    assert isinstance(tiktok_export_empty, dict)
    likes = tiktok_export_empty.get("Likes and Favorites", {})
    like_list = likes.get("Like List", {}).get("ItemFavoriteList", [])
    assert like_list == []


def test_missing_fields_fixture(tiktok_export_missing_fields):
    """Verify missing fields fixture has incomplete structure."""
    assert isinstance(tiktok_export_missing_fields, dict)
    # Should be missing some expected fields
    assert "Profile And Settings" not in tiktok_export_missing_fields


def test_null_values_fixture(tiktok_export_null_values):
    """Verify null values fixture contains nulls."""
    assert isinstance(tiktok_export_null_values, dict)
    # Profile section should be null
    assert tiktok_export_null_values.get("Profile And Settings") is None


def test_extra_fields_fixture(tiktok_export_extra_fields):
    """Verify extra fields fixture has unknown fields."""
    assert isinstance(tiktok_export_extra_fields, dict)
    # Should have a new top-level section
    assert "New Top Level Section" in tiktok_export_extra_fields


def test_synthetic_alice_fixture(tiktok_export_user_alice):
    """Verify synthetic alice fixture (power user)."""
    assert isinstance(tiktok_export_user_alice, dict)
    likes = tiktok_export_user_alice.get("Likes and Favorites", {})
    like_list = likes.get("Like List", {}).get("ItemFavoriteList", [])
    # Power user has 500 likes
    assert len(like_list) == 500


def test_synthetic_bob_fixture(tiktok_export_user_bob):
    """Verify synthetic bob fixture (casual user)."""
    assert isinstance(tiktok_export_user_bob, dict)
    likes = tiktok_export_user_bob.get("Likes and Favorites", {})
    like_list = likes.get("Like List", {}).get("ItemFavoriteList", [])
    # Casual user has 50 likes
    assert len(like_list) == 50


def test_export_builder_factory(tiktok_export_builder):
    """Verify export builder creates custom structures."""
    export = tiktok_export_builder(likes_count=3, comments_count=2)
    likes = export.get("Likes and Favorites", {}).get("Like List", {}).get("ItemFavoriteList", [])
    comments = export.get("Comment", {}).get("Comments", {}).get("CommentsList", [])
    assert len(likes) == 3
    assert len(comments) == 2


def test_liked_video_factory(tiktok_liked_video_factory):
    """Verify liked video factory creates valid entries."""
    video = tiktok_liked_video_factory(date="2024-06-15 12:00:00")
    assert video["date"] == "2024-06-15 12:00:00"
    assert "link" in video
    assert video["link"].startswith("https://")


def test_comment_factory(tiktok_comment_factory):
    """Verify comment factory creates valid entries."""
    comment = tiktok_comment_factory(text="Test comment", date="2024-01-01 00:00:00")
    assert comment["comment"] == "Test comment"
    assert comment["date"] == "2024-01-01 00:00:00"
    assert comment["photo"] == "N/A"
