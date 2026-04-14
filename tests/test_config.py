# ABOUTME: Tests for configuration loading from TOML files and environment variables.
# ABOUTME: Validates precedence (env > file > defaults) and edge cases.

from __future__ import annotations

from pathlib import Path

import pytest

from ip_read_recently.config import Config, load_config, default_config_path

CONFIG_ENV_VARS = [
    "INSTAPAPER_CONSUMER_KEY",
    "INSTAPAPER_CONSUMER_SECRET",
    "INSTAPAPER_USERNAME",
    "INSTAPAPER_PASSWORD",
    "INSTAPAPER_SOURCE_FOLDER",
    "INSTAPAPER_DEST_FOLDER",
    "INSTAPAPER_TEMPLATE",
    "INSTAPAPER_DATE_FORMAT",
]


class TestDefaults:
    """Config defaults when no file or env vars are present."""

    def test_defaults_returned_when_no_file_or_env(self, tmp_path, monkeypatch):
        for var in CONFIG_ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        cfg = load_config(config_path=tmp_path / "nonexistent.toml")
        assert cfg.consumer_key == ""
        assert cfg.consumer_secret == ""
        assert cfg.source_folder == "read-post"
        assert cfg.dest_folder == "posted"
        assert cfg.template == "default"
        assert cfg.date_format == "range"

    def test_default_config_path_uses_xdg(self, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        assert default_config_path() == Path("/custom/config/ip-read-recently/config.toml")

    def test_default_config_path_falls_back_to_home(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = default_config_path()
        assert result == Path.home() / ".config" / "ip-read-recently" / "config.toml"


class TestFileLoading:
    """Config loaded from TOML file."""

    def _write_config(self, path: Path, content: str) -> Path:
        path.write_text(content)
        return path

    def test_loads_all_sections(self, tmp_path, monkeypatch):
        # Clear env vars that would override
        for var in CONFIG_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        config_file = self._write_config(
            tmp_path / "config.toml",
            """\
[instapaper]
consumer_key = "ck_from_file"
consumer_secret = "cs_from_file"
username = "user@example.com"
password = "secret123"

[folders]
source = "my-reading"
destination = "my-posted"

[output]
template = "custom.j2"
date_format = "today"
""",
        )
        cfg = load_config(config_path=config_file)
        assert cfg.consumer_key == "ck_from_file"
        assert cfg.consumer_secret == "cs_from_file"
        assert cfg.username == "user@example.com"
        assert cfg.password == "secret123"
        assert cfg.source_folder == "my-reading"
        assert cfg.dest_folder == "my-posted"
        assert cfg.template == "custom.j2"
        assert cfg.date_format == "today"

    def test_partial_file_uses_defaults_for_missing(self, tmp_path, monkeypatch):
        for var in CONFIG_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        config_file = self._write_config(
            tmp_path / "config.toml",
            """\
[instapaper]
consumer_key = "ck_only"
""",
        )
        cfg = load_config(config_path=config_file)
        assert cfg.consumer_key == "ck_only"
        assert cfg.consumer_secret == ""
        assert cfg.source_folder == "read-post"


class TestEnvVarOverride:
    """Environment variables override file values."""

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.toml"
        config_file.write_text("""\
[instapaper]
consumer_key = "from_file"
""")
        monkeypatch.setenv("INSTAPAPER_CONSUMER_KEY", "from_env")
        cfg = load_config(config_path=config_file)
        assert cfg.consumer_key == "from_env"

    def test_env_overrides_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("INSTAPAPER_SOURCE_FOLDER", "env-folder")
        cfg = load_config(config_path=tmp_path / "nonexistent.toml")
        assert cfg.source_folder == "env-folder"

    def test_all_env_vars(self, tmp_path, monkeypatch):
        env_map = {
            "INSTAPAPER_CONSUMER_KEY": "ek",
            "INSTAPAPER_CONSUMER_SECRET": "es",
            "INSTAPAPER_USERNAME": "eu",
            "INSTAPAPER_PASSWORD": "ep",
            "INSTAPAPER_SOURCE_FOLDER": "esf",
            "INSTAPAPER_DEST_FOLDER": "edf",
            "INSTAPAPER_TEMPLATE": "etpl",
            "INSTAPAPER_DATE_FORMAT": "edt",
        }
        for k, v in env_map.items():
            monkeypatch.setenv(k, v)
        cfg = load_config(config_path=tmp_path / "nonexistent.toml")
        assert cfg.consumer_key == "ek"
        assert cfg.consumer_secret == "es"
        assert cfg.username == "eu"
        assert cfg.password == "ep"
        assert cfg.source_folder == "esf"
        assert cfg.dest_folder == "edf"
        assert cfg.template == "etpl"
        assert cfg.date_format == "edt"

    def test_empty_env_var_overrides_file(self, tmp_path, monkeypatch):
        """An explicitly set empty env var should still override."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""\
[instapaper]
consumer_key = "from_file"
""")
        monkeypatch.setenv("INSTAPAPER_CONSUMER_KEY", "")
        cfg = load_config(config_path=config_file)
        assert cfg.consumer_key == ""


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_missing_file_returns_defaults(self, tmp_path, monkeypatch):
        for var in CONFIG_ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        cfg = load_config(config_path=tmp_path / "does_not_exist.toml")
        assert cfg.consumer_key == ""
        assert cfg.consumer_secret == ""
        assert cfg.source_folder == "read-post"

    def test_empty_file_returns_defaults(self, tmp_path, monkeypatch):
        for var in CONFIG_ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        config_file = tmp_path / "config.toml"
        config_file.write_text("")
        cfg = load_config(config_path=config_file)
        assert cfg.consumer_key == ""
        assert cfg.consumer_secret == ""
        assert cfg.source_folder == "read-post"
