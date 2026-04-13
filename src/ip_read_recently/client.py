# ABOUTME: Instapaper API operations for reading-list generation.
# ABOUTME: Handles auth, folder lookup, bookmark/highlight fetching, and bookmark moves.

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from instapyper import Instapaper
from instapyper.exceptions import InstapaperError, RateLimitError
from instapyper.models import Bookmark, Folder, Highlight

from .config import Config

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0


@dataclass
class ArticleHighlight:
    """A single highlight passage, cleaned for output."""

    text: str
    position: int
    time: int


@dataclass
class Article:
    """A bookmark with its associated highlights, ready for template rendering."""

    bookmark_id: int
    title: str
    url: str
    description: str
    time: int
    highlights: list[ArticleHighlight] = field(default_factory=list)


class Client:
    """Coordinates Instapaper API calls for reading-list generation."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._api = Instapaper(config.consumer_key, config.consumer_secret)

    def authenticate(self) -> None:
        """Log in using saved tokens or username/password."""
        if self._config.oauth_token and self._config.oauth_token_secret:
            self._api.login_with_token(
                self._config.oauth_token, self._config.oauth_token_secret
            )
            logger.info("Authenticated with saved OAuth tokens")
        elif self._config.username and self._config.password:
            self._api.login(self._config.username, self._config.password)
            logger.info("Authenticated with username/password")
        else:
            raise AuthError(
                "No credentials configured. Provide oauth_token/oauth_token_secret "
                "or username/password in config file or environment variables."
            )

    def get_folders(self) -> list[Folder]:
        """Return all user-created folders."""
        return self._retry(lambda: self._api.get_folders())

    def find_folder_by_name(self, name: str) -> Folder | None:
        """Find a folder by its title, or None if not found."""
        folders = self.get_folders()
        for folder in folders:
            if folder.title == name:
                return folder
        return None

    def create_folder(self, name: str) -> Folder:
        """Create a folder and return it."""
        return self._retry(lambda: self._api.create_folder(name))

    def ensure_folder(self, name: str) -> Folder:
        """Find a folder by name, creating it if it doesn't exist."""
        folder = self.find_folder_by_name(name)
        if folder is not None:
            return folder
        logger.info("Folder '%s' not found, creating it", name)
        return self.create_folder(name)

    def get_bookmarks(self, folder_id: int, limit: int = 500) -> list[Bookmark]:
        """Fetch bookmarks from a folder."""
        return self._retry(lambda: self._api.get_bookmarks(folder=folder_id, limit=limit))

    def get_highlights(self, bookmark: Bookmark) -> list[Highlight]:
        """Fetch highlights for a single bookmark."""
        return self._retry(lambda: bookmark.get_highlights())

    def move_bookmark(self, bookmark: Bookmark, folder_id: int) -> None:
        """Move a bookmark to a different folder."""
        self._retry(lambda: bookmark.move(folder_id))

    def fetch_articles(self, folder_id: int) -> list[Article]:
        """Fetch all bookmarks from a folder and collect their highlights.

        Returns Article objects sorted by save date (oldest first).
        """
        bookmarks = self.get_bookmarks(folder_id)
        articles: list[Article] = []

        for bm in bookmarks:
            highlights = self._fetch_highlights_safe(bm)
            article = Article(
                bookmark_id=bm.bookmark_id,
                title=bm.title,
                url=bm.url,
                description=bm.description,
                time=bm.time,
                highlights=[
                    ArticleHighlight(text=h.text, position=h.position, time=h.time)
                    for h in highlights
                ],
            )
            articles.append(article)

        articles.sort(key=lambda a: a.time)
        return articles

    def move_bookmarks(
        self, bookmarks: list[Bookmark], dest_folder_id: int
    ) -> tuple[int, list[str]]:
        """Move bookmarks to destination folder.

        Returns (success_count, list of error messages for failures).
        """
        success = 0
        errors: list[str] = []
        for bm in bookmarks:
            try:
                self.move_bookmark(bm, dest_folder_id)
                success += 1
            except (InstapaperError, RateLimitError) as e:
                msg = f"Failed to move bookmark {bm.bookmark_id} ({bm.title!r}): {e}"
                logger.warning(msg)
                errors.append(msg)
        return success, errors

    def _fetch_highlights_safe(self, bookmark: Bookmark) -> list[Highlight]:
        """Fetch highlights for a bookmark, returning empty list on failure."""
        try:
            return self.get_highlights(bookmark)
        except (InstapaperError, RateLimitError) as e:
            logger.warning(
                "Failed to fetch highlights for bookmark %d (%r): %s",
                bookmark.bookmark_id,
                bookmark.title,
                e,
            )
            return []

    def _retry(self, fn: callable, max_retries: int = MAX_RETRIES) -> any:
        """Execute fn with exponential backoff on rate limit errors."""
        backoff = INITIAL_BACKOFF_SECONDS
        for attempt in range(max_retries + 1):
            try:
                return fn()
            except RateLimitError:
                if attempt == max_retries:
                    raise
                logger.warning(
                    "Rate limited, retrying in %.1f seconds (attempt %d/%d)",
                    backoff,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(backoff)
                backoff *= 2


class AuthError(Exception):
    """Raised when authentication credentials are missing or invalid."""
