"""Tests for Gemini client (file upload/poll/delete).

NOTE: classify and analyze_visual tests were removed along with the functions —
the pipeline handles all classification and visual perception via its own sync code.
"""

from unittest.mock import MagicMock, patch

import httpx

from app.services.gemini import (
    DEFAULT_GEMINI_MODEL,
    delete_file_sync,
    wait_for_file_sync,
)


class TestConstants:
    def test_default_model_is_set(self):
        assert DEFAULT_GEMINI_MODEL == "gemini-3-flash-preview"


class TestWaitForFileSync:
    def test_returns_uri_on_active(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"state": "ACTIVE", "uri": "https://example.com/file"}

        with patch("app.services.gemini.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response

            result = wait_for_file_sync("test-key", "files/abc123", timeout=10)

        assert result == "https://example.com/file"

    def test_returns_none_on_failed(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"state": "FAILED"}

        with patch("app.services.gemini.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response

            result = wait_for_file_sync("test-key", "files/abc123", timeout=10)

        assert result is None


class TestDeleteFileSync:
    def test_delete_does_not_raise(self):
        with patch("app.services.gemini.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.delete.side_effect = httpx.HTTPError("connection failed")

            # Should not raise
            delete_file_sync("test-key", "files/abc123")
