"""Tests for the gr4_modtool search command."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from gr4_modtool.commands.search import (
    _DEFAULT_TOPIC,
    _cache_path,
    cmd,
    search_registry,
)

_SAMPLE_ITEMS = [
    {
        "full_name": "alice/gr4-dsp",
        "description": "DSP blocks for GNURadio 4",
        "stargazers_count": 42,
        "updated_at": "2024-01-15T10:00:00Z",
        "html_url": "https://github.com/alice/gr4-dsp",
        "topics": ["gnuradio4-oot", "dsp"],
    },
    {
        "full_name": "bob/gr4-filters",
        "description": "Filter blocks",
        "stargazers_count": 7,
        "updated_at": "2024-02-01T08:00:00Z",
        "html_url": "https://github.com/bob/gr4-filters",
        "topics": ["gnuradio4-oot"],
    },
]


class _FakeResponse:
    """Minimal urllib response mock that works as a context manager."""

    def __init__(self, items: list[dict]) -> None:
        self._payload = json.dumps({"items": items, "total_count": len(items)}).encode()

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _mock_urlopen(items: list[dict]):
    """Return a callable suitable for patching urllib.request.urlopen."""
    resp = _FakeResponse(items)
    return lambda *_args, **_kwargs: resp


# ---------------------------------------------------------------------------
# search_registry() unit tests
# ---------------------------------------------------------------------------


def test_search_returns_results(tmp_path: Path) -> None:
    with (
        patch("gr4_modtool.commands.search._CACHE_DIR", tmp_path),
        patch("urllib.request.urlopen", _mock_urlopen(_SAMPLE_ITEMS)),
    ):
        results = search_registry(query="dsp", no_cache=True)
    assert len(results) == 2
    assert results[0]["full_name"] == "alice/gr4-dsp"


def test_search_caches_results(tmp_path: Path) -> None:
    call_count = 0

    def counting_urlopen(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(_SAMPLE_ITEMS)

    with (
        patch("gr4_modtool.commands.search._CACHE_DIR", tmp_path),
        patch("urllib.request.urlopen", counting_urlopen),
    ):
        search_registry(query="dsp", no_cache=True)  # populates cache
        search_registry(query="dsp")  # should hit cache

    assert call_count == 1


def test_search_cache_ttl_expired(tmp_path: Path) -> None:
    """Expired cache entry triggers a fresh fetch."""
    call_count = 0

    def counting_urlopen(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(_SAMPLE_ITEMS)

    cache_file = _cache_path("dsp", _DEFAULT_TOPIC)
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    old_ts = time.time() - 7200  # 2 hours ago
    cache_file.write_text(json.dumps({"ts": old_ts, "items": _SAMPLE_ITEMS}))

    with (
        patch("gr4_modtool.commands.search._CACHE_DIR", tmp_path),
        patch("urllib.request.urlopen", counting_urlopen),
    ):
        search_registry(query="dsp")

    assert call_count == 1


def test_search_no_cache_bypasses(tmp_path: Path) -> None:
    """--no-cache always re-fetches even when a fresh cache exists."""
    call_count = 0

    def counting_urlopen(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(_SAMPLE_ITEMS)

    with (
        patch("gr4_modtool.commands.search._CACHE_DIR", tmp_path),
        patch("urllib.request.urlopen", counting_urlopen),
    ):
        search_registry(query="dsp", no_cache=False)  # warm cache
        search_registry(query="dsp", no_cache=True)  # bypass

    assert call_count == 2


def test_search_uses_token_in_header(tmp_path: Path) -> None:
    captured: list = []

    def capturing_urlopen(req, **_kwargs):
        captured.append(req)
        return _FakeResponse(_SAMPLE_ITEMS)

    with (
        patch("gr4_modtool.commands.search._CACHE_DIR", tmp_path),
        patch("urllib.request.urlopen", capturing_urlopen),
    ):
        search_registry(query="", token="mytoken", no_cache=True)

    assert len(captured) == 1
    auth = captured[0].get_header("Authorization")
    assert auth == "Bearer mytoken"


def test_search_no_token_omits_header(tmp_path: Path) -> None:
    captured: list = []

    def capturing_urlopen(req, **_kwargs):
        captured.append(req)
        return _FakeResponse([])

    with (
        patch("gr4_modtool.commands.search._CACHE_DIR", tmp_path),
        patch("urllib.request.urlopen", capturing_urlopen),
    ):
        search_registry(no_cache=True)

    assert captured[0].get_header("Authorization") is None


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


def test_search_cli_shows_repo_name(tmp_path: Path) -> None:
    runner = CliRunner()
    with (
        patch("gr4_modtool.commands.search._CACHE_DIR", tmp_path),
        patch("urllib.request.urlopen", _mock_urlopen(_SAMPLE_ITEMS)),
    ):
        result = runner.invoke(cmd, ["dsp", "--no-cache"])
    assert result.exit_code == 0, result.output
    assert "alice/gr4-dsp" in result.output


def test_search_cli_verbose_shows_url(tmp_path: Path) -> None:
    runner = CliRunner()
    with (
        patch("gr4_modtool.commands.search._CACHE_DIR", tmp_path),
        patch("urllib.request.urlopen", _mock_urlopen(_SAMPLE_ITEMS)),
    ):
        result = runner.invoke(cmd, ["dsp", "--verbose", "--no-cache"])
    assert result.exit_code == 0, result.output
    # Rich may truncate the full URL; verify the URL column is present at all.
    assert "URL" in result.output
    assert "https:/" in result.output


def test_search_cli_empty_results(tmp_path: Path) -> None:
    runner = CliRunner()
    with (
        patch("gr4_modtool.commands.search._CACHE_DIR", tmp_path),
        patch("urllib.request.urlopen", _mock_urlopen([])),
    ):
        result = runner.invoke(cmd, ["--no-cache"])
    assert result.exit_code == 0
    assert "No modules found" in result.output


def test_search_cli_network_error(tmp_path: Path) -> None:
    """Network failure exits with non-zero code and prints an error."""
    import urllib.error

    def failing_urlopen(*_args, **_kwargs):
        raise urllib.error.URLError("connection refused")

    runner = CliRunner()
    with (
        patch("gr4_modtool.commands.search._CACHE_DIR", tmp_path),
        patch("urllib.request.urlopen", failing_urlopen),
    ):
        result = runner.invoke(cmd, ["--no-cache"])
    assert result.exit_code != 0
