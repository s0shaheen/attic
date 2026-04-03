"""Tests for pipeline completion email notification."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.user import User


class TestSendCompletionEmail:
    """Test _send_completion_email from pipeline.py."""

    def _make_mock_session(self, user_email: str | None = "test@test.com"):
        """Create a mock session that returns a user with the given email."""
        session = MagicMock()
        if user_email is not None:
            mock_user = MagicMock(spec=User)
            mock_user.email = user_email
            session.get.return_value = mock_user
        else:
            session.get.return_value = None
        return session

    @patch("app.services.pipeline.RESEND_API_KEY", "re_test_key")
    @patch("app.services.pipeline.httpx")
    def test_sends_success_email(self, mock_httpx):
        from app.services.pipeline import _send_completion_email

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.post.return_value = mock_resp

        session = self._make_mock_session()
        _send_completion_email(session, str(uuid4()), 42)

        mock_httpx.post.assert_called_once()
        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1]["json"]
        assert "ready" in payload["subject"].lower()
        assert "42 items" in payload["html"]
        assert payload["to"] == ["test@test.com"]

    @patch("app.services.pipeline.RESEND_API_KEY", "re_test_key")
    @patch("app.services.pipeline.httpx")
    def test_sends_failure_email(self, mock_httpx):
        from app.services.pipeline import _send_completion_email

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.post.return_value = mock_resp

        session = self._make_mock_session()
        _send_completion_email(session, str(uuid4()), 0, failed=True)

        mock_httpx.post.assert_called_once()
        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1]["json"]
        assert "snag" in payload["subject"].lower()

    @patch("app.services.pipeline.RESEND_API_KEY", "")
    @patch("app.services.pipeline.httpx")
    def test_skips_when_no_api_key(self, mock_httpx):
        from app.services.pipeline import _send_completion_email

        session = self._make_mock_session()
        _send_completion_email(session, str(uuid4()), 10)

        mock_httpx.post.assert_not_called()

    @patch("app.services.pipeline.RESEND_API_KEY", "re_test_key")
    @patch("app.services.pipeline.httpx")
    def test_skips_when_no_user(self, mock_httpx):
        from app.services.pipeline import _send_completion_email

        session = self._make_mock_session(user_email=None)
        _send_completion_email(session, str(uuid4()), 10)

        mock_httpx.post.assert_not_called()

    @patch("app.services.pipeline.RESEND_API_KEY", "re_test_key")
    @patch("app.services.pipeline.httpx")
    def test_does_not_raise_on_httpx_error(self, mock_httpx):
        """Email failure must not break the pipeline."""
        from app.services.pipeline import _send_completion_email

        mock_httpx.post.side_effect = Exception("network error")

        session = self._make_mock_session()
        # Should not raise
        _send_completion_email(session, str(uuid4()), 10)

    @patch("app.services.pipeline.RESEND_API_KEY", "re_test_key")
    @patch("app.services.pipeline.httpx")
    def test_logs_warning_on_non_200(self, mock_httpx, caplog):
        from app.services.pipeline import _send_completion_email

        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_httpx.post.return_value = mock_resp

        session = self._make_mock_session()
        _send_completion_email(session, str(uuid4()), 10)

        # Should not raise, just log
        mock_httpx.post.assert_called_once()
