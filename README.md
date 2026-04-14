# ip-read-recently

Pull Instapaper bookmarks and highlights into a Markdown reading-list draft.

## What it does

1. Fetches all bookmarks from a designated Instapaper folder (e.g., `read-post`)
2. Retrieves highlights you made on each article
3. Generates a Markdown draft file with front matter and article entries
4. Moves processed bookmarks to a different folder (e.g., `posted`)

The output is a draft you edit by hand: sorting articles into thematic sections, adding commentary, trimming highlights.

## Prerequisites

You need an Instapaper API consumer key and secret. Apply at <https://www.instapaper.com/main/request_oauth_consumer_token> — the owner-only key (granted automatically) is sufficient.

## Installation

```bash
# Install globally (available from any directory)
git clone https://github.com/bexelbie/ip-read-recently.git
cd ip-read-recently
uv tool install .

# To upgrade after pulling changes
uv tool install . --force
```

## Configuration

Create a config file at `~/.config/ip-read-recently/config.toml`:

```toml
[instapaper]
consumer_key = "your-consumer-key"
consumer_secret = "your-consumer-secret"
username = "you@example.com"
password = "your-password"

[folders]
source = "read-post"        # folder to pull bookmarks from
destination = "posted"       # folder to move processed bookmarks to

[output]
template = "default"         # or path to a custom .j2 file
date_format = "range"        # "range", "today", or "custom"
```

All settings can be overridden with environment variables:

| Config key | Environment variable |
|---|---|
| `instapaper.consumer_key` | `INSTAPAPER_CONSUMER_KEY` |
| `instapaper.consumer_secret` | `INSTAPAPER_CONSUMER_SECRET` |
| `instapaper.username` | `INSTAPAPER_USERNAME` |
| `instapaper.password` | `INSTAPAPER_PASSWORD` |
| `folders.source` | `INSTAPAPER_SOURCE_FOLDER` |
| `folders.destination` | `INSTAPAPER_DEST_FOLDER` |

## Usage

### Initial setup

Create the source and destination folders in your Instapaper account:

```bash
ip-read-recently setup
```

### Generate a draft

```bash
# Full workflow: fetch → generate → move bookmarks to "posted"
ip-read-recently generate

# Write to a specific file
ip-read-recently generate --output _posts/2026-04-12-things-i-read.md

# Dry run: generate without moving bookmarks
ip-read-recently generate --no-move

# Use a custom Jinja2 template
ip-read-recently generate --template my-template.j2
```

### Preview candidates

```bash
ip-read-recently list
```

### Move specific bookmarks manually

```bash
ip-read-recently move-posted 12345 67890
```

## Workflow

1. Read articles in Instapaper, highlight passages
2. Move candidates to the `read-post` folder (in the Instapaper app)
3. Run `ip-read-recently generate`
4. Edit the draft: sort into sections, write summaries, trim highlights
5. Publish

## Custom templates

The tool uses Jinja2 templates with `trim_blocks` and `lstrip_blocks` enabled, so block tags (`{% if %}`, `{% for %}`, etc.) don't produce extra blank lines. Override the default template with `--template path/to/custom.j2`.

Template variables available:

| Variable | Description |
|---|---|
| `title` | Auto-generated title with date range |
| `date` | Generation timestamp |
| `date_range_start` | Earliest bookmark save date (ISO) |
| `date_range_end` | Latest bookmark save date (ISO) |
| `count` | Number of articles |
| `articles` | List of article dicts |

Each article has:

| Field | Description |
|---|---|
| `bookmark_id` | Instapaper bookmark ID |
| `title` | Article title |
| `url` | Original URL |
| `description` | Instapaper description (may be empty) |
| `time` | Unix timestamp (save date) |
| `time_formatted` | ISO date string |
| `highlights` | List of `{text, position, time, note}` dicts |

## Known limitations

- **No tags in template**: The instapyper fork parses tags from the API, but they are not yet exposed in the template context.
- **Rate limiting**: With many bookmarks, API calls may hit rate limits. The tool retries with exponential backoff (max 3 attempts).

## Development

```bash
uv sync
uv run pytest
uv run pytest -v  # verbose
```

## License

MIT
