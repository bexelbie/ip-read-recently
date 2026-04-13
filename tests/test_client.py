# ABOUTME: Tests for the Instapaper client layer.
# ABOUTME: Verifies retry logic, folder lookup, article assembly, and error handling.

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from instapyper.exceptions import RateLimitError, InstapaperError
from instapyper.models import Bookmark, Folder, Highlight

from ip_read_recently.client import Client, Article, ArticleHighlight, AuthError
from ip_read_recently.config import Config


def _make_config(**overrides) -> Config:
    """Build a Config with test credentials."""
    defaults = {
        "consumer_key": "test_ck",
        "consumer_secret": "test_cs",
        "username": "user@test.com",
        "password": "pass123",
    }
    defaults.update(overrides)
    return Config(**defaults)


def _make_folder(folder_id: int = 100, title: str = "read-post") -> MagicMock:
    """Create a mock Folder object."""
    folder = MagicMock(spec=Folder)
    folder.folder_id = folder_id
    folder.title = title
    return folder


def _make_bookmark(
    bookmark_id: int = 1,
    title: str = "Test Article",
    url: str = "https://example.com",
    description: str = "A test article",
    time: int = 1712345678,
) -> MagicMock:
    """Create a mock Bookmark object."""
    bm = MagicMock(spec=Bookmark)
    bm.bookmark_id = bookmark_id
    bm.title = title
    bm.url = url
    bm.description = description
    bm.time = time
    return bm


def _make_highlight(
    highlight_id: int = 1,
    text: str = "highlighted passage",
    position: int = 0,
    time: int = 1712345700,
    bookmark_id: int = 1,
) -> MagicMock:
    """Create a mock Highlight object."""
    h = MagicMock(spec=Highlight)
    h.highlight_id = highlight_id
    h.text = text
    h.position = position
    h.time = time
    h.bookmark_id = bookmark_id
    return h


class TestAuthentication:
    """Authentication path selection."""

    @patch("ip_read_recently.client.Instapaper")
    def test_auth_with_tokens(self, mock_cls):
        mock_api = mock_cls.return_value
        cfg = _make_config(oauth_token="tok", oauth_token_secret="sec")
        client = Client(cfg)
        client.authenticate()
        mock_api.login_with_token.assert_called_once_with("tok", "sec")
        mock_api.login.assert_not_called()

    @patch("ip_read_recently.client.Instapaper")
    def test_auth_with_username_password(self, mock_cls):
        mock_api = mock_cls.return_value
        cfg = _make_config(oauth_token="", oauth_token_secret="")
        client = Client(cfg)
        client.authenticate()
        mock_api.login.assert_called_once_with("user@test.com", "pass123")

    @patch("ip_read_recently.client.Instapaper")
    def test_auth_raises_when_no_credentials(self, mock_cls):
        cfg = _make_config(
            username="", password="", oauth_token="", oauth_token_secret=""
        )
        client = Client(cfg)
        with pytest.raises(AuthError, match="No credentials configured"):
            client.authenticate()


class TestFolderLookup:
    """Finding and creating folders."""

    @patch("ip_read_recently.client.Instapaper")
    def test_find_folder_by_name_found(self, mock_cls):
        mock_api = mock_cls.return_value
        target = _make_folder(100, "read-post")
        other = _make_folder(200, "other")
        mock_api.get_folders.return_value = [other, target]

        client = Client(_make_config())
        result = client.find_folder_by_name("read-post")
        assert result.folder_id == 100

    @patch("ip_read_recently.client.Instapaper")
    def test_find_folder_by_name_not_found(self, mock_cls):
        mock_api = mock_cls.return_value
        mock_api.get_folders.return_value = [_make_folder(200, "other")]

        client = Client(_make_config())
        result = client.find_folder_by_name("read-post")
        assert result is None

    @patch("ip_read_recently.client.Instapaper")
    def test_ensure_folder_creates_when_missing(self, mock_cls):
        mock_api = mock_cls.return_value
        mock_api.get_folders.return_value = []
        created = _make_folder(300, "new-folder")
        mock_api.create_folder.return_value = created

        client = Client(_make_config())
        result = client.ensure_folder("new-folder")
        assert result.folder_id == 300
        mock_api.create_folder.assert_called_once_with("new-folder")

    @patch("ip_read_recently.client.Instapaper")
    def test_ensure_folder_returns_existing(self, mock_cls):
        mock_api = mock_cls.return_value
        existing = _make_folder(100, "read-post")
        mock_api.get_folders.return_value = [existing]

        client = Client(_make_config())
        result = client.ensure_folder("read-post")
        assert result.folder_id == 100
        mock_api.create_folder.assert_not_called()


class TestRetryLogic:
    """Exponential backoff on rate limit errors."""

    @patch("ip_read_recently.client.time.sleep")
    @patch("ip_read_recently.client.Instapaper")
    def test_retries_on_rate_limit(self, mock_cls, mock_sleep):
        mock_api = mock_cls.return_value
        mock_api.get_folders.side_effect = [RateLimitError("slow down"), []]

        client = Client(_make_config())
        result = client.get_folders()
        assert result == []
        mock_sleep.assert_called_once_with(1.0)

    @patch("ip_read_recently.client.time.sleep")
    @patch("ip_read_recently.client.Instapaper")
    def test_exponential_backoff(self, mock_cls, mock_sleep):
        mock_api = mock_cls.return_value
        mock_api.get_folders.side_effect = [
            RateLimitError("1"),
            RateLimitError("2"),
            [],
        ]

        client = Client(_make_config())
        client.get_folders()
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 1.0
        assert mock_sleep.call_args_list[1][0][0] == 2.0

    @patch("ip_read_recently.client.time.sleep")
    @patch("ip_read_recently.client.Instapaper")
    def test_raises_after_max_retries(self, mock_cls, mock_sleep):
        mock_api = mock_cls.return_value
        mock_api.get_folders.side_effect = RateLimitError("always fails")

        client = Client(_make_config())
        with pytest.raises(RateLimitError):
            client.get_folders()
        assert mock_sleep.call_count == 3


class TestFetchArticles:
    """Building Article objects from bookmarks + highlights."""

    @patch("ip_read_recently.client.Instapaper")
    def test_builds_articles_sorted_oldest_first(self, mock_cls):
        mock_api = mock_cls.return_value
        bm_new = _make_bookmark(bookmark_id=1, title="New", time=2000)
        bm_old = _make_bookmark(bookmark_id=2, title="Old", time=1000)
        mock_api.get_bookmarks.return_value = [bm_new, bm_old]
        bm_new.get_highlights.return_value = []
        bm_old.get_highlights.return_value = []

        client = Client(_make_config())
        articles = client.fetch_articles(folder_id=100)
        assert len(articles) == 2
        assert articles[0].title == "Old"
        assert articles[1].title == "New"

    @patch("ip_read_recently.client.Instapaper")
    def test_collects_highlights(self, mock_cls):
        mock_api = mock_cls.return_value
        bm = _make_bookmark(bookmark_id=1)
        mock_api.get_bookmarks.return_value = [bm]
        h1 = _make_highlight(highlight_id=10, text="passage one", position=0)
        h2 = _make_highlight(highlight_id=11, text="passage two", position=1)
        bm.get_highlights.return_value = [h1, h2]

        client = Client(_make_config())
        articles = client.fetch_articles(folder_id=100)
        assert len(articles[0].highlights) == 2
        assert articles[0].highlights[0].text == "passage one"
        assert articles[0].highlights[1].text == "passage two"

    @patch("ip_read_recently.client.Instapaper")
    def test_highlight_failure_returns_empty_list(self, mock_cls):
        mock_api = mock_cls.return_value
        bm = _make_bookmark(bookmark_id=1)
        mock_api.get_bookmarks.return_value = [bm]
        bm.get_highlights.side_effect = InstapaperError("server error")

        client = Client(_make_config())
        articles = client.fetch_articles(folder_id=100)
        assert articles[0].highlights == []


class TestMoveBookmarks:
    """Moving bookmarks with partial failure handling."""

    @patch("ip_read_recently.client.Instapaper")
    def test_moves_all_successfully(self, mock_cls):
        mock_api = mock_cls.return_value
        bm1 = _make_bookmark(bookmark_id=1)
        bm2 = _make_bookmark(bookmark_id=2)
        bm1.move.return_value = bm1
        bm2.move.return_value = bm2

        client = Client(_make_config())
        success, errors = client.move_bookmarks([bm1, bm2], dest_folder_id=200)
        assert success == 2
        assert errors == []

    @patch("ip_read_recently.client.Instapaper")
    def test_continues_after_individual_failure(self, mock_cls):
        mock_api = mock_cls.return_value
        bm1 = _make_bookmark(bookmark_id=1, title="Fails")
        bm2 = _make_bookmark(bookmark_id=2, title="Succeeds")
        bm1.move.side_effect = InstapaperError("move failed")
        bm2.move.return_value = bm2

        client = Client(_make_config())
        success, errors = client.move_bookmarks([bm1, bm2], dest_folder_id=200)
        assert success == 1
        assert len(errors) == 1
        assert "bookmark 1" in errors[0]
