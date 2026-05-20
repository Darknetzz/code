import json
from unittest.mock import MagicMock, patch

from mafibot.alerts import notify_assist, notify_session_stop, post_webhook


@patch("mafibot.alerts.request.urlopen")
def test_post_webhook_uses_json(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    assert post_webhook("https://example.com/hook", "hello")
    _req = mock_urlopen.call_args[0][0]
    body = json.loads(_req.data.decode())
    assert body["content"] == "hello"


@patch("mafibot.alerts.post_webhook", return_value=True)
def test_notify_session_stop_empty_url_skips(mock_post):
    notify_session_stop("", "ranker", "stopped")
    mock_post.assert_not_called()


@patch("mafibot.alerts.post_webhook", return_value=True)
def test_notify_assist(mock_post):
    notify_assist("https://example.com/hook", "ranker", "war")
    mock_post.assert_called_once()
    assert "assist" in mock_post.call_args[0][1]
