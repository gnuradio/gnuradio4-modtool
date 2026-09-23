"""E2E: search command — query GitHub for OOT modules.

Uses unittest.mock.patch to intercept urllib.request.urlopen so no real
network calls are made.  Tests cover happy-path output, empty results,
verbose mode, and network-error handling.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from gr4_modtool.cli import cli

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_REPOS = [
    {
        "full_name": "alice/gr4-dsp",
        "stargazers_count": 42,
        "description": "DSP blocks for GNURadio 4",
        "updated_at": "2024-11-01T12:00:00Z",
        "html_url": "https://github.com/alice/gr4-dsp",
    },
    {
        "full_name": "bob/gr4-sdr",
        "stargazers_count": 7,
        "description": "SDR utilities",
        "updated_at": "2024-10-15T08:30:00Z",
        "html_url": "https://github.com/bob/gr4-sdr",
    },
]


class _FakeResponse:
    """Minimal urllib response context-manager fake."""

    def __init__(self, items: list[dict]) -> None:
        self._body = json.dumps({"items": items}).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _run_search(*extra_args: str) -> object:
    runner = CliRunner()
    return runner.invoke(cli, ["search", "--no-cache", *extra_args])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_search_returns_repo_names() -> None:
    """search prints the full_name of each returned repository."""
    with patch(
        "gr4_modtool.commands.search.urllib.request.urlopen",
        return_value=_FakeResponse(_FAKE_REPOS),
    ):
        result = _run_search()

    assert result.exit_code == 0, result.output
    assert "alice/gr4-dsp" in result.output
    assert "bob/gr4-sdr" in result.output


def test_search_no_results_prints_message() -> None:
    """search prints a 'No modules found' message when the registry is empty."""
    with patch(
        "gr4_modtool.commands.search.urllib.request.urlopen",
        return_value=_FakeResponse([]),
    ):
        result = _run_search()

    assert result.exit_code == 0, result.output
    assert "No modules found" in result.output


def test_search_network_error_exits_nonzero() -> None:
    """search exits nonzero when the network call fails."""
    import urllib.error

    mock_urlopen = MagicMock(side_effect=urllib.error.URLError("connection refused"))
    with patch("gr4_modtool.commands.search.urllib.request.urlopen", mock_urlopen):
        result = _run_search()

    assert result.exit_code != 0


def test_search_verbose_shows_url() -> None:
    """search --verbose adds a URL column header to the output."""
    with patch(
        "gr4_modtool.commands.search.urllib.request.urlopen",
        return_value=_FakeResponse(_FAKE_REPOS[:1]),
    ):
        result = _run_search("--verbose")

    assert result.exit_code == 0, result.output
    # Rich may wrap the URL across lines; check for the column header and URL prefix
    assert "URL" in result.output
    assert "https://" in result.output or "https:/" in result.output
