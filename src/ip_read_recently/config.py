# ABOUTME: Loads configuration from TOML file and environment variables.
# ABOUTME: Env vars take precedence over file values; file values over defaults.

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _xdg_config_home() -> Path:
    """Return XDG_CONFIG_HOME or its default (~/.config)."""
    env = os.environ.get("XDG_CONFIG_HOME")
    if env:
        return Path(env)
    return Path.home() / ".config"


def default_config_path() -> Path:
    """Return the default config file path."""
    return _xdg_config_home() / "ip-read-recently" / "config.toml"


@dataclass
class Config:
    """Application configuration with all settings."""

    # Instapaper credentials
    consumer_key: str = ""
    consumer_secret: str = ""
    username: str = ""
    password: str = ""
    oauth_token: str = ""
    oauth_token_secret: str = ""

    # Folder names
    source_folder: str = "read-post"
    dest_folder: str = "posted"

    # Output settings
    template: str = "default"
    date_format: str = "range"


def _deep_get(data: dict[str, Any], *keys: str, default: str = "") -> str:
    """Traverse nested dicts by key path, return default if missing."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return str(current) if current is not None else default


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from TOML file and environment variables.

    Precedence (highest to lowest):
      1. Environment variables (INSTAPAPER_*)
      2. TOML config file values
      3. Dataclass defaults
    """
    file_data: dict[str, Any] = {}

    path = config_path or default_config_path()
    if path.is_file():
        with open(path, "rb") as f:
            file_data = tomllib.load(f)

    def _resolve(env_var: str, *toml_keys: str, default: str = "") -> str:
        """Return env var if set, else TOML value, else default."""
        env_val = os.environ.get(env_var)
        if env_val is not None:
            return env_val
        toml_val = _deep_get(file_data, *toml_keys)
        return toml_val if toml_val else default

    return Config(
        consumer_key=_resolve("INSTAPAPER_CONSUMER_KEY", "instapaper", "consumer_key"),
        consumer_secret=_resolve("INSTAPAPER_CONSUMER_SECRET", "instapaper", "consumer_secret"),
        username=_resolve("INSTAPAPER_USERNAME", "instapaper", "username"),
        password=_resolve("INSTAPAPER_PASSWORD", "instapaper", "password"),
        oauth_token=_resolve("INSTAPAPER_OAUTH_TOKEN", "instapaper", "oauth_token"),
        oauth_token_secret=_resolve(
            "INSTAPAPER_OAUTH_TOKEN_SECRET", "instapaper", "oauth_token_secret"
        ),
        source_folder=_resolve(
            "INSTAPAPER_SOURCE_FOLDER", "folders", "source", default="read-post"
        ),
        dest_folder=_resolve(
            "INSTAPAPER_DEST_FOLDER", "folders", "destination", default="posted"
        ),
        template=_resolve("INSTAPAPER_TEMPLATE", "output", "template", default="default"),
        date_format=_resolve(
            "INSTAPAPER_DATE_FORMAT", "output", "date_format", default="range"
        ),
    )
