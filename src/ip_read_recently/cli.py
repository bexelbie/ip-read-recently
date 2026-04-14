# ABOUTME: Command-line interface for ip-read-recently.
# ABOUTME: Provides generate, list, setup, and move-posted subcommands.

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from .client import Article, AuthError, Client
from .config import Config, load_config
from .generator import render

logger = logging.getLogger(__name__)


def _default_output_filename() -> str:
    """Return YYYY-MM-DD-things-i-read.md using today's date."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    return f"{today}-things-i-read.md"


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="ip-read-recently",
        description="Generate Markdown reading-list drafts from Instapaper bookmarks.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file (default: XDG_CONFIG_HOME/ip-read-recently/config.toml)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate
    gen_parser = subparsers.add_parser(
        "generate",
        help="Fetch bookmarks and generate a Markdown draft",
    )
    gen_parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help=f"Output file path (default: {_default_output_filename()})",
    )
    gen_parser.add_argument(
        "--no-move",
        action="store_true",
        help="Don't move bookmarks to destination folder after generating",
    )
    gen_parser.add_argument(
        "--template", "-t",
        type=str,
        default=None,
        help="Path to a custom Jinja2 template file",
    )

    # list
    subparsers.add_parser(
        "list",
        help="List candidate bookmarks without generating",
    )

    # setup
    subparsers.add_parser(
        "setup",
        help="Check and create source/destination folders",
    )

    # move-posted
    move_parser = subparsers.add_parser(
        "move-posted",
        help="Move specific bookmarks to the destination folder",
    )
    move_selection = move_parser.add_mutually_exclusive_group(required=True)
    move_selection.add_argument(
        "--all",
        action="store_true",
        help="Move every bookmark from the configured source folder",
    )
    move_selection.add_argument(
        "bookmark_ids",
        nargs="*",
        type=int,
        help="Bookmark IDs to move",
    )

    return parser


def _connect(config: Config) -> Client:
    """Create and authenticate an API client."""
    client = Client(config)
    client.authenticate()
    return client


def _cmd_generate(args: argparse.Namespace, config: Config) -> int:
    """Execute the generate subcommand."""
    client = _connect(config)

    # Find source folder
    source = client.find_folder_by_name(config.source_folder)
    if source is None:
        print(
            f"Error: Source folder '{config.source_folder}' not found. "
            f"Run 'ip-read-recently setup' to create it.",
            file=sys.stderr,
        )
        return 1

    # Fetch articles
    articles = client.fetch_articles(source.folder_id)
    if not articles:
        print(f"No candidates found in folder '{config.source_folder}'. Nothing to generate.")
        return 0

    # Render output
    template_path = args.template or (
        config.template if config.template != "default" else None
    )
    output = render(articles, template_path=template_path)

    # Write file
    output_path = args.output or _default_output_filename()
    Path(output_path).write_text(output, encoding="utf-8")
    print(f"Draft written to {output_path}")

    # Move bookmarks unless --no-move
    if not args.no_move:
        dest = client.ensure_folder(config.dest_folder)
        # Re-fetch raw bookmarks for moving
        bookmarks = client.get_bookmarks(source.folder_id)
        success, errors = client.move_bookmarks(bookmarks, dest.folder_id)
        print(f"Moved {success}/{len(bookmarks)} bookmarks to '{config.dest_folder}'")
        for err in errors:
            print(f"  Warning: {err}", file=sys.stderr)

    print(f"Summary: {len(articles)} articles processed, output: {output_path}")
    return 0


def _cmd_list(args: argparse.Namespace, config: Config) -> int:
    """Execute the list subcommand."""
    client = _connect(config)

    source = client.find_folder_by_name(config.source_folder)
    if source is None:
        print(
            f"Error: Source folder '{config.source_folder}' not found. "
            f"Run 'ip-read-recently setup' to create it.",
            file=sys.stderr,
        )
        return 1

    articles = client.fetch_articles(source.folder_id)
    if not articles:
        print(f"No candidates in folder '{config.source_folder}'.")
        return 0

    for article in articles:
        highlight_count = len(article.highlights)
        highlights_info = f" ({highlight_count} highlight{'s' if highlight_count != 1 else ''})" if highlight_count else ""
        print(f"  [{article.bookmark_id}] {article.title}{highlights_info}")
        print(f"           {article.url}")

    print(f"\n{len(articles)} article(s) ready for generate.")
    return 0


def _cmd_setup(args: argparse.Namespace, config: Config) -> int:
    """Execute the setup subcommand."""
    client = _connect(config)

    for folder_name in [config.source_folder, config.dest_folder]:
        folder = client.find_folder_by_name(folder_name)
        if folder is not None:
            print(f"  ✓ Folder '{folder_name}' exists (id: {folder.folder_id})")
        else:
            created = client.create_folder(folder_name)
            print(f"  ✓ Folder '{folder_name}' created (id: {created.folder_id})")

    print("Setup complete.")
    return 0


def _cmd_move_posted(args: argparse.Namespace, config: Config) -> int:
    """Execute the move-posted subcommand."""
    client = _connect(config)

    dest = client.ensure_folder(config.dest_folder)

    if args.all:
        source = client.find_folder_by_name(config.source_folder)
        if source is None:
            print(
                f"Error: Source folder '{config.source_folder}' not found. "
                f"Run 'ip-read-recently setup' to create it.",
                file=sys.stderr,
            )
            return 1

        bookmarks = client.get_bookmarks(source.folder_id)
        if not bookmarks:
            print(f"No bookmarks found in folder '{config.source_folder}'.")
            return 0

        success, errors = client.move_bookmarks(bookmarks, dest.folder_id)
        print(f"Moved {success}/{len(bookmarks)} bookmarks to '{config.dest_folder}'")
        for err in errors:
            print(f"  Warning: {err}", file=sys.stderr)
        return 0 if not errors else 1

    # Move each bookmark by ID
    success = 0
    errors: list[str] = []
    for bid in args.bookmark_ids:
        try:
            # Get the bookmark's raw instapyper object to call move on it
            # We need to use the underlying API directly for individual IDs
            client._api.move_bookmark(bid, dest.folder_id)
            success += 1
            print(f"  Moved bookmark {bid}")
        except Exception as e:
            msg = f"Failed to move bookmark {bid}: {e}"
            errors.append(msg)
            print(f"  Error: {msg}", file=sys.stderr)

    print(f"Moved {success}/{len(args.bookmark_ids)} bookmarks to '{config.dest_folder}'")
    return 0 if not errors else 1


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    config = load_config(config_path=args.config)

    commands = {
        "generate": _cmd_generate,
        "list": _cmd_list,
        "setup": _cmd_setup,
        "move-posted": _cmd_move_posted,
    }

    try:
        return commands[args.command](args, config)
    except AuthError as e:
        print(f"Authentication error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


def cli() -> None:
    """Entry point that calls sys.exit with the return code."""
    sys.exit(main())
