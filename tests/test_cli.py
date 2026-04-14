# ABOUTME: Tests for CLI argument parsing and subcommand dispatch.
# ABOUTME: Validates parser behavior, exit codes, and subcommand routing.

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from ip_read_recently.cli import _build_parser, main, _default_output_filename
from ip_read_recently.client import Article, ArticleHighlight


class TestParser:
    """Argument parsing for all subcommands."""

    def test_generate_defaults(self):
        parser = _build_parser()
        args = parser.parse_args(["generate"])
        assert args.command == "generate"
        assert args.output is None
        assert args.no_move is False
        assert args.template is None

    def test_generate_with_all_flags(self):
        parser = _build_parser()
        args = parser.parse_args([
            "generate", "--output", "out.md", "--no-move", "--template", "custom.j2"
        ])
        assert args.output == "out.md"
        assert args.no_move is True
        assert args.template == "custom.j2"

    def test_list_command(self):
        parser = _build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_setup_command(self):
        parser = _build_parser()
        args = parser.parse_args(["setup"])
        assert args.command == "setup"

    def test_move_posted_with_ids(self):
        parser = _build_parser()
        args = parser.parse_args(["move-posted", "123", "456"])
        assert args.command == "move-posted"
        assert args.bookmark_ids == [123, 456]
        assert args.all is False

    def test_move_posted_with_all(self):
        parser = _build_parser()
        args = parser.parse_args(["move-posted", "--all"])
        assert args.command == "move-posted"
        assert args.all is True
        assert args.bookmark_ids == []

    def test_move_posted_requires_ids_or_all(self):
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["move-posted"])

    def test_no_command_fails(self):
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_global_config_flag(self):
        parser = _build_parser()
        args = parser.parse_args(["--config", "/path/to/config.toml", "list"])
        assert str(args.config) == "/path/to/config.toml"

    def test_verbose_flag(self):
        parser = _build_parser()
        args = parser.parse_args(["-v", "list"])
        assert args.verbose is True


class TestDefaultFilename:
    """Output filename generation."""

    def test_format(self):
        name = _default_output_filename()
        # Should match YYYY-MM-DD-things-i-read.md
        assert name.endswith("-things-i-read.md")
        parts = name.split("-things-i-read.md")[0].split("-")
        assert len(parts) == 3  # YYYY, MM, DD


class TestGenerateCommand:
    """Generate subcommand behavior."""

    @patch("ip_read_recently.cli._connect")
    def test_generate_empty_folder_exits_zero(self, mock_connect, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_folder = MagicMock()
        mock_folder.folder_id = 100
        mock_client.find_folder_by_name.return_value = mock_folder
        mock_client.fetch_articles.return_value = []

        result = main(["generate", "--no-move"])
        assert result == 0
        captured = capsys.readouterr()
        assert "No candidates found" in captured.out

    @patch("ip_read_recently.cli._connect")
    def test_generate_missing_folder_exits_one(self, mock_connect, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_client.find_folder_by_name.return_value = None

        result = main(["generate"])
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    @patch("ip_read_recently.cli._connect")
    def test_generate_writes_output_file(self, mock_connect, tmp_path, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_folder = MagicMock()
        mock_folder.folder_id = 100
        mock_client.find_folder_by_name.return_value = mock_folder
        mock_client.fetch_articles.return_value = [
            Article(
                bookmark_id=1,
                title="Test",
                url="https://example.com",
                description="desc",
                time=1712345678,
                highlights=[],
            )
        ]

        output_path = tmp_path / "output.md"
        result = main(["generate", "--output", str(output_path), "--no-move"])
        assert result == 0
        assert output_path.exists()
        content = output_path.read_text()
        assert "Test" in content

    @patch("ip_read_recently.cli._connect")
    def test_generate_moves_bookmarks_by_default(self, mock_connect, tmp_path, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client

        mock_source = MagicMock()
        mock_source.folder_id = 100
        mock_dest = MagicMock()
        mock_dest.folder_id = 200
        mock_client.find_folder_by_name.return_value = mock_source
        mock_client.ensure_folder.return_value = mock_dest
        mock_client.fetch_articles.return_value = [
            Article(
                bookmark_id=1, title="Test", url="https://example.com",
                description="", time=1712345678, highlights=[],
            )
        ]
        mock_client.get_bookmarks.return_value = [MagicMock()]
        mock_client.move_bookmarks.return_value = (1, [])

        output_path = tmp_path / "output.md"
        result = main(["generate", "--output", str(output_path)])
        assert result == 0
        mock_client.move_bookmarks.assert_called_once()

    @patch("ip_read_recently.cli._connect")
    def test_generate_no_move_skips_move(self, mock_connect, tmp_path, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_folder = MagicMock()
        mock_folder.folder_id = 100
        mock_client.find_folder_by_name.return_value = mock_folder
        mock_client.fetch_articles.return_value = [
            Article(
                bookmark_id=1, title="Test", url="https://example.com",
                description="", time=1712345678, highlights=[],
            )
        ]

        output_path = tmp_path / "output.md"
        result = main(["generate", "--output", str(output_path), "--no-move"])
        assert result == 0
        mock_client.move_bookmarks.assert_not_called()


class TestListCommand:
    """List subcommand behavior."""

    @patch("ip_read_recently.cli._connect")
    def test_list_shows_articles(self, mock_connect, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_folder = MagicMock()
        mock_folder.folder_id = 100
        mock_client.find_folder_by_name.return_value = mock_folder
        mock_client.fetch_articles.return_value = [
            Article(
                bookmark_id=42, title="Cool Article", url="https://example.com",
                description="", time=1712345678,
                highlights=[ArticleHighlight(text="hi", position=0, time=100)],
            )
        ]

        result = main(["list"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Cool Article" in captured.out
        assert "1 highlight" in captured.out
        assert "1 article(s)" in captured.out


class TestSetupCommand:
    """Setup subcommand behavior."""

    @patch("ip_read_recently.cli._connect")
    def test_setup_creates_missing_folders(self, mock_connect, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_client.find_folder_by_name.return_value = None
        mock_client.create_folder.return_value = MagicMock(folder_id=999)

        result = main(["setup"])
        assert result == 0
        assert mock_client.create_folder.call_count == 2
        captured = capsys.readouterr()
        assert "created" in captured.out
        assert "Setup complete" in captured.out

    @patch("ip_read_recently.cli._connect")
    def test_setup_reports_existing_folders(self, mock_connect, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_client.find_folder_by_name.return_value = MagicMock(folder_id=100)

        result = main(["setup"])
        assert result == 0
        captured = capsys.readouterr()
        assert "exists" in captured.out


class TestAuthError:
    """Authentication error handling."""

    @patch("ip_read_recently.cli._connect")
    def test_auth_error_prints_message(self, mock_connect, capsys):
        from ip_read_recently.client import AuthError
        mock_connect.side_effect = AuthError("No credentials")

        result = main(["list"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Authentication error" in captured.err


class TestMovePostedCommand:
    """move-posted subcommand behavior."""

    @patch("ip_read_recently.cli._connect")
    def test_move_posted_moves_specific_ids(self, mock_connect, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_dest = MagicMock()
        mock_dest.folder_id = 200
        mock_client.ensure_folder.return_value = mock_dest

        result = main(["move-posted", "123", "456"])

        assert result == 0
        assert mock_client._api.move_bookmark.call_count == 2
        mock_client._api.move_bookmark.assert_any_call(123, 200)
        mock_client._api.move_bookmark.assert_any_call(456, 200)
        mock_client.get_bookmarks.assert_not_called()

        captured = capsys.readouterr()
        assert "Moved 2/2 bookmarks" in captured.out

    @patch("ip_read_recently.cli._connect")
    def test_move_posted_all_moves_source_folder_bookmarks(self, mock_connect, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_source = MagicMock()
        mock_source.folder_id = 100
        mock_dest = MagicMock()
        mock_dest.folder_id = 200
        mock_client.find_folder_by_name.return_value = mock_source
        mock_client.ensure_folder.return_value = mock_dest
        bookmarks = [MagicMock(), MagicMock()]
        mock_client.get_bookmarks.return_value = bookmarks
        mock_client.move_bookmarks.return_value = (2, [])

        result = main(["move-posted", "--all"])

        assert result == 0
        mock_client.find_folder_by_name.assert_called_once()
        mock_client.get_bookmarks.assert_called_once_with(100)
        mock_client.move_bookmarks.assert_called_once_with(bookmarks, 200)
        mock_client._api.move_bookmark.assert_not_called()

        captured = capsys.readouterr()
        assert "Moved 2/2 bookmarks" in captured.out

    @patch("ip_read_recently.cli._connect")
    def test_move_posted_all_missing_source_folder_exits_one(self, mock_connect, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_client.find_folder_by_name.return_value = None

        result = main(["move-posted", "--all"])

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    @patch("ip_read_recently.cli._connect")
    def test_move_posted_all_empty_source_folder_exits_zero(self, mock_connect, capsys):
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        mock_source = MagicMock()
        mock_source.folder_id = 100
        mock_dest = MagicMock()
        mock_dest.folder_id = 200
        mock_client.find_folder_by_name.return_value = mock_source
        mock_client.ensure_folder.return_value = mock_dest
        mock_client.get_bookmarks.return_value = []

        result = main(["move-posted", "--all"])

        assert result == 0
        mock_client.move_bookmarks.assert_not_called()
        captured = capsys.readouterr()
        assert "No bookmarks found" in captured.out
