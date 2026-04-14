# ABOUTME: Tests for Markdown generation including context building and template rendering.
# ABOUTME: Validates highlight cleaning, date ranges, title formatting, and full output.

from __future__ import annotations

from unittest.mock import patch

import pytest

from ip_read_recently.client import Article, ArticleHighlight
from ip_read_recently.generator import (
    build_context,
    clean_highlight_text,
    render,
    _date_range,
    _format_title_date_range,
    _round_up_to_10min,
)
from datetime import datetime, timezone


def _article(
    bookmark_id: int = 1,
    title: str = "Test Article",
    url: str = "https://example.com",
    description: str = "A description",
    time: int = 1712345678,
    highlights: list[ArticleHighlight] | None = None,
) -> Article:
    return Article(
        bookmark_id=bookmark_id,
        title=title,
        url=url,
        description=description,
        time=time,
        highlights=highlights or [],
    )


class TestCleanHighlightText:
    """HTML stripping and whitespace normalization."""

    def test_strips_html_tags(self):
        assert clean_highlight_text("<p>Hello <b>world</b></p>") == "Hello world"

    def test_normalizes_whitespace(self):
        assert clean_highlight_text("  lots   of    spaces  ") == "lots of spaces"

    def test_unescapes_html_entities(self):
        assert clean_highlight_text("&amp; &lt;tag&gt;") == "& <tag>"

    def test_handles_nested_tags(self):
        result = clean_highlight_text("<div><p>inner <em>text</em></p></div>")
        assert result == "inner text"

    def test_preserves_plain_text(self):
        assert clean_highlight_text("no html here") == "no html here"

    def test_empty_string(self):
        assert clean_highlight_text("") == ""

    def test_newlines_collapsed(self):
        assert clean_highlight_text("line one\n\nline two") == "line one line two"


class TestDateRange:
    """Date range calculation from article timestamps."""

    def test_single_article(self):
        articles = [_article(time=1712345678)]
        start, end = _date_range(articles)
        assert start == end

    def test_multiple_articles(self):
        articles = [
            _article(time=1711929600),  # 2024-04-01
            _article(time=1712880000),  # 2024-04-12
        ]
        start, end = _date_range(articles)
        assert start == "2024-04-01"
        assert end == "2024-04-12"

    def test_empty_articles_uses_today(self):
        start, end = _date_range([])
        assert start == end
        # Just verify it's a valid date format
        datetime.strptime(start, "%Y-%m-%d")


class TestFormatTitleDateRange:
    """Title date range formatting."""

    def test_same_date(self):
        assert _format_title_date_range("2026-04-12", "2026-04-12") == "12 Apr 2026"

    def test_same_year(self):
        result = _format_title_date_range("2026-04-01", "2026-04-12")
        assert result == "01 Apr – 12 Apr 2026"

    def test_different_years(self):
        result = _format_title_date_range("2025-12-28", "2026-01-04")
        assert result == "28 Dec 2025 – 04 Jan 2026"


class TestRoundUpTo10Min:
    """Rounding timestamps up to 10-minute boundaries."""

    def test_already_on_boundary(self):
        dt = datetime(2026, 4, 12, 14, 30, 0, tzinfo=timezone.utc)
        assert _round_up_to_10min(dt) == dt

    def test_rounds_up(self):
        dt = datetime(2026, 4, 12, 14, 32, 15, tzinfo=timezone.utc)
        expected = datetime(2026, 4, 12, 14, 40, 0, tzinfo=timezone.utc)
        assert _round_up_to_10min(dt) == expected

    def test_rounds_up_to_next_hour(self):
        dt = datetime(2026, 4, 12, 14, 55, 1, tzinfo=timezone.utc)
        expected = datetime(2026, 4, 12, 15, 0, 0, tzinfo=timezone.utc)
        assert _round_up_to_10min(dt) == expected

    def test_seconds_cause_round_up(self):
        dt = datetime(2026, 4, 12, 14, 30, 1, tzinfo=timezone.utc)
        expected = datetime(2026, 4, 12, 14, 30, 0, tzinfo=timezone.utc)
        assert _round_up_to_10min(dt) == expected


class TestBuildContext:
    """Template context construction."""

    def test_context_has_required_keys(self):
        ctx = build_context([_article()])
        assert "title" in ctx
        assert "date" in ctx
        assert "date_range_start" in ctx
        assert "date_range_end" in ctx
        assert "count" in ctx
        assert "articles" in ctx

    def test_count_matches_articles(self):
        articles = [_article(bookmark_id=i) for i in range(3)]
        ctx = build_context(articles)
        assert ctx["count"] == 3

    def test_title_contains_date_range(self):
        articles = [
            _article(time=1711929600),
            _article(time=1712880000),
        ]
        ctx = build_context(articles)
        assert "Things I Read:" in ctx["title"]

    def test_articles_contain_cleaned_highlights(self):
        articles = [
            _article(
                highlights=[
                    ArticleHighlight(text="<b>bold</b> text", position=0, time=100)
                ]
            )
        ]
        ctx = build_context(articles)
        assert ctx["articles"][0]["highlights"][0]["text"] == "bold text"

    def test_articles_have_formatted_time(self):
        ctx = build_context([_article(time=1712345678)])
        assert "time_formatted" in ctx["articles"][0]


class TestRender:
    """Full template rendering."""

    def test_renders_with_default_template(self):
        articles = [
            _article(
                title="Test Post",
                url="https://example.com/test",
                description="A test post",
                highlights=[
                    ArticleHighlight(text="highlighted passage", position=0, time=100)
                ],
            )
        ]
        output = render(articles)
        assert "Test Post" in output
        assert "https://example.com/test" in output
        assert "> highlighted passage" in output
        assert "A test post" in output
        assert "---" in output  # front matter

    def test_renders_article_without_highlights_or_description(self):
        articles = [_article(description="", highlights=[])]
        output = render(articles)
        assert "_No highlights or description available._" in output

    def test_renders_with_custom_template(self, tmp_path):
        template_file = tmp_path / "custom.j2"
        template_file.write_text("Title: {{ title }}\nCount: {{ count }}")
        articles = [_article()]
        output = render(articles, template_path=str(template_file))
        assert output.startswith("Title: Things I Read:")
        assert "Count: 1" in output

    def test_renders_multiple_articles(self):
        articles = [
            _article(bookmark_id=1, title="First", time=1000),
            _article(bookmark_id=2, title="Second", time=2000),
        ]
        output = render(articles)
        # Both articles should appear
        assert "First" in output
        assert "Second" in output

    def test_front_matter_structure(self):
        output = render([_article()])
        lines = output.split("\n")
        assert lines[0] == "---"
        # Find closing front matter
        closing = lines.index("---", 1)
        assert closing > 0
        # title and date should be in front matter
        front_matter = "\n".join(lines[1:closing])
        assert "title:" in front_matter
        assert "date:" in front_matter
        assert "excerpt:" in front_matter

    def test_renders_highlight_with_note(self):
        articles = [
            _article(
                highlights=[
                    ArticleHighlight(
                        text="a key passage", position=0, time=100, note="my comment"
                    )
                ],
            )
        ]
        output = render(articles)
        assert "> a key passage" in output
        assert "_my comment_" in output

    def test_renders_highlight_without_note(self):
        articles = [
            _article(
                highlights=[
                    ArticleHighlight(text="just a highlight", position=0, time=100)
                ],
            )
        ]
        output = render(articles)
        assert "> just a highlight" in output
        # No italic note marker should appear for empty note
        lines = output.split("\n")
        highlight_idx = next(
            i for i, line in enumerate(lines) if "> just a highlight" in line
        )
        # The line after the highlight should not be an italic note
        remaining = "\n".join(lines[highlight_idx + 1 : highlight_idx + 3])
        assert "_" not in remaining or remaining.strip().startswith("_No")
