---
kind: code
purpose: Python CLI that pulls Instapaper bookmarks/highlights and generates a Markdown reading-list draft
visibility: public
---

# Project Context: ip-read-recently

## What this is

A Python CLI tool that pulls bookmarks and highlights from an Instapaper folder and generates a Markdown reading-list draft. Designed for periodic "things I read" blog posts.

## Tech stack

- **Language**: Python 3.10+
- **Package manager**: uv
- **API client**: instapyper (v0.0.3) — Instapaper Full API wrapper
- **Templating**: Jinja2
- **Config**: TOML (tomli for Python <3.11, stdlib tomllib for 3.11+)
- **CLI**: argparse
- **Testing**: pytest

## Build / Run / Test

```bash
# Install dependencies
uv sync

# Run the CLI
uv run ip-read-recently --help
uv run ip-read-recently generate --no-move

# Run tests
uv run pytest
uv run pytest -v          # verbose
uv run pytest tests/test_config.py  # single module
```

## Project layout

```
src/ip_read_recently/
├── __init__.py          # Package root
├── cli.py               # argparse CLI with subcommands
├── client.py            # Instapaper API operations (auth, folders, bookmarks, highlights)
├── config.py            # TOML + env var config loading
├── generator.py         # Markdown context building and Jinja2 rendering
├── py.typed             # PEP 561 marker
└── templates/
    └── default.md.j2    # Default Jekyll-compatible output template

tests/
├── test_cli.py          # CLI parsing and subcommand behavior
├── test_client.py       # Client operations (mocked instapyper boundary)
├── test_config.py       # Config loading and precedence
└── test_generator.py    # Template context, HTML cleaning, rendering
```

## Architecture decisions

- **instapyper over raw API**: OAuth 1.0a signing is non-trivial; instapyper handles it. Accepted trade-off: N+1 highlight API calls per bookmark (library discards batch highlights from bookmarks/list response).
- **Folders over tags**: Instapaper API has no tag update/remove endpoint. Folder membership IS the processing state — no external state file needed.
- **argparse over Click**: Simpler, no extra dependency. Four subcommands are manageable.
- **Config precedence**: env vars > TOML file > defaults. XDG_CONFIG_HOME respected.

## Configuration

Config file: `~/.config/ip-read-recently/config.toml`
Env vars: `INSTAPAPER_CONSUMER_KEY`, `INSTAPAPER_CONSUMER_SECRET`, etc.
See README.md for full reference.

## Releasing

GitHub Release notes are generated from the tagged commit message using `.github/workflows/release.yml`.

Flow: bump `version` in `pyproject.toml` → commit with release notes in message → tag with `v*` → push branch and tags.

```bash
git commit -m "v0.2.0 Release

- Added --all flag to move-posted
- Added --version flag to CLI"
git tag v0.2.0
git push origin main --tags
```

## Known limitations

- instapyper Bookmark model doesn't parse tags from API response
- Highlights require per-bookmark API calls (no batch)
- Live API testing requires Instapaper consumer credentials (human-reviewed application process)
