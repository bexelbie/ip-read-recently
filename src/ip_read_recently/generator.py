# ABOUTME: Builds template context from articles and renders Markdown via Jinja2.
# ABOUTME: Handles highlight text cleaning, date range calculation, and template loading.

from __future__ import annotations

import html
import re
from datetime import datetime, timezone, timedelta
from importlib import resources
from pathlib import Path
from typing import Any

import jinja2

from .client import Article, ArticleHighlight


def clean_highlight_text(raw: str) -> str:
    """Strip HTML tags, normalize whitespace, and unescape entities."""
    # Strip HTML tags first (these are real markup)
    text = re.sub(r"<[^>]+>", " ", raw)
    # Unescape HTML entities (e.g., &amp; → &) after tags are removed
    text = html.unescape(text)
    # Collapse whitespace runs and trim
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _format_timestamp(ts: int, fmt: str = "%Y-%m-%d") -> str:
    """Format a Unix timestamp as a date string in UTC."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(fmt)


def _date_range(articles: list[Article]) -> tuple[str, str]:
    """Return (start, end) ISO date strings from article timestamps."""
    if not articles:
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        return today, today
    times = [a.time for a in articles]
    return _format_timestamp(min(times)), _format_timestamp(max(times))


def _round_up_to_10min(dt: datetime) -> datetime:
    """Round a datetime up to the next 10-minute boundary, seconds always 00."""
    minute = dt.minute
    rounded = (minute + 9) // 10 * 10
    if rounded == 60:
        dt = dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    elif rounded != minute or dt.second != 0 or dt.microsecond != 0:
        dt = dt.replace(minute=rounded, second=0, microsecond=0)
    return dt


def _format_generation_date(tz_name: str = "Europe/Prague") -> str:
    """Return the current time rounded up to 10-min boundary, formatted for Jekyll.

    Format: YYYY-MM-DD HH:MM:00 +ZZZZ
    """
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(tz=ZoneInfo(tz_name))
    except (ImportError, KeyError):
        # Fall back to UTC if zoneinfo unavailable or timezone unknown
        now = datetime.now(tz=timezone.utc)

    rounded = _round_up_to_10min(now)
    offset = rounded.strftime("%z")
    # Format offset as +HHMM
    formatted_offset = offset if offset else "+0000"
    return rounded.strftime(f"%Y-%m-%d %H:%M:%S {formatted_offset}")


def _format_title_date_range(start: str, end: str) -> str:
    """Format a date range for the post title.

    Converts ISO dates to 'DD Mon' format: '01 Apr – 12 Apr 2026'
    """
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    if start == end:
        return end_dt.strftime("%d %b %Y")

    if start_dt.year == end_dt.year:
        return f"{start_dt.strftime('%d %b')} – {end_dt.strftime('%d %b %Y')}"
    return f"{start_dt.strftime('%d %b %Y')} – {end_dt.strftime('%d %b %Y')}"


def build_context(articles: list[Article]) -> dict[str, Any]:
    """Build the template context dict from a list of articles."""
    date_start, date_end = _date_range(articles)
    title_range = _format_title_date_range(date_start, date_end)

    article_dicts = []
    for article in articles:
        cleaned_highlights = [
            {
                "text": clean_highlight_text(h.text),
                "position": h.position,
                "time": h.time,
            }
            for h in article.highlights
        ]
        article_dicts.append(
            {
                "bookmark_id": article.bookmark_id,
                "title": article.title,
                "url": article.url,
                "description": article.description,
                "time": article.time,
                "time_formatted": _format_timestamp(article.time),
                "highlights": cleaned_highlights,
            }
        )

    return {
        "title": f"Things I Read: {title_range}",
        "date": _format_generation_date(),
        "date_range_start": date_start,
        "date_range_end": date_end,
        "count": len(articles),
        "articles": article_dicts,
    }


def _load_template(template_path: str | None = None) -> jinja2.Template:
    """Load a Jinja2 template from a path or the built-in default."""
    if template_path and Path(template_path).is_file():
        path = Path(template_path)
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(path.parent)),
            keep_trailing_newline=True,
        )
        return env.get_template(path.name)

    # Load built-in default template
    templates_dir = resources.files("ip_read_recently") / "templates"
    template_text = (templates_dir / "default.md.j2").read_text(encoding="utf-8")
    env = jinja2.Environment(keep_trailing_newline=True)
    return env.from_string(template_text)


def render(articles: list[Article], template_path: str | None = None) -> str:
    """Build context and render Markdown output."""
    context = build_context(articles)
    template = _load_template(template_path)
    return template.render(**context)
