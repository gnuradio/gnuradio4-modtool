"""search command — query GitHub for published gr4 OOT modules."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from gr4_modtool.fileops import write_text

_DEFAULT_TOPIC = "gnuradio4-oot"
_GH_SEARCH_URL = "https://api.github.com/search/repositories"
_CACHE_DIR = Path.home() / ".cache" / "gr4_modtool" / "search"
_CACHE_TTL = 3600  # seconds


def _cache_path(query: str, topic: str) -> Path:
    import hashlib

    key = hashlib.sha1(f"{topic}:{query}".encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{key}.json"


def _fetch_from_github(query: str, topic: str, token: str | None, limit: int) -> list[dict]:
    q = f"topic:{topic}"
    if query:
        q += f" {query}"
    params = urllib.parse.urlencode(
        {
            "q": q,
            "per_page": min(limit, 30),
            "sort": "stars",
            "order": "desc",
        }
    )
    url = f"{_GH_SEARCH_URL}?{params}"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "gr4_modtool/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return data.get("items", [])[:limit]


def search_registry(
    query: str = "",
    topic: str = _DEFAULT_TOPIC,
    token: str | None = None,
    limit: int = 20,
    no_cache: bool = False,
) -> list[dict]:
    """Return a list of GitHub repository dicts matching topic + query.

    Results are cached locally for one hour unless *no_cache* is True.
    """
    cache_file = _cache_path(query, topic)

    if not no_cache and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if time.time() - cached["ts"] < _CACHE_TTL:
                return cached["items"]
        except (json.JSONDecodeError, KeyError):
            pass

    items = _fetch_from_github(query, topic, token, limit)

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    write_text(cache_file, json.dumps({"ts": time.time(), "items": items}))
    return items


def _render_table(items: list[dict], verbose: bool) -> None:
    console = Console()
    if not items:
        console.print("[yellow]No modules found.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Repository", style="bold", min_width=30)
    table.add_column("Stars", justify="right", min_width=5)
    table.add_column("Description", ratio=2)
    table.add_column("Updated", min_width=12)
    if verbose:
        table.add_column("URL")

    for item in items:
        updated = (item.get("updated_at") or "")[:10]
        stars = str(item.get("stargazers_count", 0))
        desc = item.get("description") or ""
        row = [item["full_name"], stars, desc, updated]
        if verbose:
            row.append(item.get("html_url", ""))
        table.add_row(*row)

    console.print(table)


@click.command("search")
@click.argument("query", default="")
@click.option(
    "--topic", default=_DEFAULT_TOPIC, show_default=True, help="GitHub topic tag to filter by."
)
@click.option("--limit", default=20, show_default=True, help="Max results to display.")
@click.option("--verbose", "-v", is_flag=True, help="Show full repository URL.")
@click.option(
    "--token",
    envvar="GR4_MODTOOL_GITHUB_TOKEN",
    default=None,
    help="GitHub personal access token (env: GR4_MODTOOL_GITHUB_TOKEN).",
)
@click.option("--no-cache", "no_cache", is_flag=True, help="Bypass the local result cache.")
def cmd(
    query: str,
    topic: str,
    limit: int,
    verbose: bool,
    token: str | None,
    no_cache: bool,
) -> None:
    """Search GitHub for published GNURadio 4 OOT modules."""
    try:
        items = search_registry(
            query=query, topic=topic, token=token, limit=limit, no_cache=no_cache
        )
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(f"Registry search failed: {exc}") from exc
    _render_table(items, verbose=verbose)
