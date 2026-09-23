# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
# Install for development
pipx install -e .          # or: python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# Run all tests
python3 -m pytest tests/ -q --tb=short

# Run a single test file
python3 -m pytest tests/test_newblock.py -v

# Run a single test by name
python3 -m pytest tests/test_newblock.py::test_newblock_creates_header -v

# Lint (check only)
ruff check .

# Lint with auto-fix
ruff check --fix .
```

## Architecture

### Entry point and command registration

`gr4_modtool/cli.py` is the Click entry point. It imports every command module and calls `cli.add_command(...)`. Plugin commands are loaded at the end via `plugins.load_extra_commands()`.

Each command lives in its own file under `gr4_modtool/commands/`. The pattern is:

- One or more `write_*(cfg: ProjectConfig) -> list[Path]` functions that do the actual file writing
- A `@click.command` function `cmd(...)` that loads config, calls the write functions, and prints results

### Project config and discovery

`gr4_modtool/project/discovery.py` is the source of truth for project state:

- `ProjectConfig` dataclass — holds all project metadata loaded from `.gr4modtool.toml`
- `load_config(project_dir)` — walks upward from cwd looking for `.gr4modtool.toml`, raises `FileNotFoundError` if absent
- `discover_groups(cfg)` — scans the filesystem (not just the config) to find `.hpp` files per group
- `save_config(cfg)` — writes TOML manually (stdlib `tomllib` is read-only)

All commands call `load_config()` at the top of `cmd()`. The `--project-dir` option is present on every command.

### Template system

`gr4_modtool/templates.py` builds a Jinja2 `Environment` with a three-level `ChoiceLoader`:

1. `<project_root>/.gr4modtool/templates/` — per-project overrides
2. Plugin dirs from `gr4_modtool.templates` entry points
3. `gr4_modtool/templates/*.j2` — built-in templates

All rendering goes through `render(template_name, context_dict, project_root)`. Templates use `StrictUndefined` so missing context keys raise immediately.

GitHub Actions `${{ }}` expressions must be wrapped in `{% raw %}...{% endraw %}` to avoid Jinja2 treating them as variable references.

### Build-system writers

`gr4_modtool/project/cmake.py` manipulate build files with line-based regex, not AST parsers. They append, remove, and rename test/benchmark entries surgically. Both modules follow the same function signatures: `append_test_entry`, `remove_test_entry`, `rename_test_entry`, `append_bench_entry`, etc.

### Logging and file mutations

`gr4_modtool/log.py` owns logging setup; `gr4_modtool/fileops.py` wraps the filesystem
mutations that should be visible in the log.

- Modules get a logger with `log = get_logger(__name__)` at module scope. Never call
  `logging.basicConfig`; `configure_logging()` (from the CLI group callback, or from a
  library caller) installs the handlers, and the `gr4_modtool` logger does not propagate.
- Write files with `fileops.write_text(path, text)`, not `path.write_text(text)`; likewise
  `remove_file`, `remove_tree`, `move_path`, and `ensure_dir`. These log at INFO, which is
  what `-v` shows, and they are the only reason a `write_*` function's output is visible
  to library callers.
- Before launching a subprocess call `log_run(log, cmd, cwd)`, and after it
  `log_exit(log, cmd, returncode)` — the existing `click.echo(f"  $ …")` lines stay, since
  they are user-facing output rather than log records.
- Level guide: INFO for things that changed on disk or ran externally, DEBUG for how the
  tool decided (config discovery, template search path, no-op build-file edits), WARNING
  for degraded behavior (missing tool, plugin that failed to load).

### Plugin system

`gr4_modtool/plugins.py` loads third-party extensions via Python entry points:

- `gr4_modtool.commands` group — returns `click.BaseCommand` instances added to the CLI
- `gr4_modtool.templates` group — returns callables that return a template directory path

### Test fixtures

`tests/conftest.py` provides two shared fixtures used by almost every test:

- `project` — a `tmp_path`-based `ProjectConfig` with one group (`basic`) and a full skeleton written to disk
- `project_two_groups` — same but with `basic` and `filter` groups

Tests that invoke CLI commands use `click.testing.CliRunner`. Tests that test pure logic call `write_*` and `parse_*` functions directly.

## Key conventions

- `write_*(cfg, ...) -> list[Path]` — every file-generating function returns the list of paths it wrote or modified. This is what the CLI both display.
- Block names are always **CamelCase**; group names are **snake_case**.
- The `GR_REGISTER_BLOCK` macro and `GR_MAKE_REFLECTABLE` are the two required GNURadio 4 macros. `check` and `add_test` parse headers with regex to detect their presence.
- Parameters in block headers are `Annotated<T, "name", Doc<"description">> name{default};` (the legacy `Annotated<T, Doc<"...">>` form is still parsed). `parse_annotated_params()` in `commands/add_test.py` extracts these for use by `info --verbose` and `docs --catalog`.
