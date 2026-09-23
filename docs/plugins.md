# Extending gr4_modtool with plugins

gr4_modtool has two extension points that third-party packages can use:

| Extension point      | Entry-point group       | What it does                          |
| -------------------- | ----------------------- | ------------------------------------- |
| CLI commands         | `gr4_modtool.commands`  | Adds new subcommands to `gr4_modtool` |
| Template directories | `gr4_modtool.templates` | Injects additional Jinja2 templates   |

Both are discovered at startup via Python's standard `importlib.metadata` entry-point system — no patching, no configuration files, no imports in gr4_modtool itself.

---

## CLI command plugins

### What the loader expects

The entry point must resolve to a `click.BaseCommand` object — typically a function decorated with `@click.command()` or a `@click.group()`. gr4_modtool calls `ep.load()` and registers whatever it gets with `cli.add_command()`.

A minimal command plugin:

```python
# my_plugin/commands/hello.py
import click

@click.command("hello")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(project_dir: str | None) -> None:
    """Say hello from a plugin."""
    click.echo("Hello from my plugin!")
```

### Registering the command

In your package's `pyproject.toml`:

```toml
[project.entry-points."gr4_modtool.commands"]
hello = "my_plugin.commands.hello:cmd"
```

The key on the left (`hello`) is the entry-point name used in warning messages — it does not affect the command name shown in `gr4_modtool --help`. The command name comes from the `@click.command("...")` decorator.

After `pip install -e .` (or any normal install), running `gr4_modtool --help` will list your command alongside the built-ins.

### Accessing project state

Most useful commands need to read the project configuration. Use gr4_modtool's public discovery API:

```python
from pathlib import Path
import click
from gr4_modtool.project.discovery import discover_groups, load_config

@click.command("my-cmd")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(project_dir: str | None) -> None:
    """Example command that reads project state."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    groups = discover_groups(cfg)
    for group in groups:
        click.echo(f"{group.name}: {len(group.blocks)} block(s)")
```

`load_config` raises `FileNotFoundError` if no `.gr4modtool.toml` is found. Commands that need a project should handle that case:

```python
import sys

try:
    cfg = load_config(Path(project_dir) if project_dir else None)
except FileNotFoundError as exc:
    click.echo(f"Error: {exc}", err=True)
    sys.exit(1)
```

### Error handling during load

If your plugin raises an exception when `ep.load()` is called, gr4_modtool prints a warning to stderr and continues without your command:

```
[gr4_modtool] Warning: could not load command plugin 'hello': No module named 'my_plugin'
```

The rest of the CLI works normally. This means broken or missing plugins never prevent gr4_modtool itself from running.

### Command groups

Your entry point can also be a `@click.group()`, which nests a whole subcommand tree under a single name:

```python
@click.group("my-tools")
def cmd() -> None:
    """My plugin's tool group."""

@cmd.command("scan")
def scan() -> None:
    """Scan something."""
    ...

@cmd.command("fix")
def fix() -> None:
    """Fix something."""
    ...
```

```
gr4_modtool my-tools scan
gr4_modtool my-tools fix
```

---

## Template plugins

### How the template search order works

When gr4_modtool renders any template, it searches three layers in order and uses the first match:

```
1.  <project_root>/.gr4modtool/templates/   ← per-project user overrides
2.  Plugin template directories              ← registered via entry points
3.  gr4_modtool/templates/                  ← built-in defaults
```

A template plugin sits in slot 2: it can override built-in templates for all projects, while still being overridden per-project.

### What the loader expects

The entry point must resolve to a **callable** that takes no arguments and returns a path (as a `str` or `Path`) to a directory containing `.j2` template files.

```python
# my_plugin/templates.py
from pathlib import Path

def get_templates_dir() -> str:
    return str(Path(__file__).parent / "templates")
```

```toml
[project.entry-points."gr4_modtool.templates"]
my_plugin = "my_plugin.templates:get_templates_dir"
```

### Current limitation — built-in commands do not load plugin template dirs

`load_extra_template_dirs()` is available in `gr4_modtool.plugins` but **built-in commands do not call it**. They call `render(template_name, context, project_root)` without passing `extra_dirs`, so your plugin's template directory is never searched by commands like `newblock`, `add-test`, or `port`.

**Template plugins therefore only work from commands you write yourself.** In your own command, explicitly wire in the plugin directories:

```python
from gr4_modtool.plugins import load_extra_template_dirs
from gr4_modtool.templates import render

content = render(
    "my_template.j2",
    context,
    project_root=cfg.root,
    extra_dirs=load_extra_template_dirs(),   # ← pulls in all plugin dirs
)
```

To override templates used by _built-in_ commands (e.g. the block header template), use the **per-project override** mechanism instead — copy the template into `.gr4modtool/templates/` in your project, which always takes priority and requires no plugin infrastructure:

```bash
gr4_modtool templates init block.hpp
# edit .gr4modtool/templates/block.hpp.j2
gr4_modtool templates check   # validate before committing
```

### Available built-in templates

| Template                        | Used by                        |
| ------------------------------- | ------------------------------ |
| `block.hpp.j2`                  | `newblock`, `cp`, `port`       |
| `qa_block.cpp.j2`               | `newblock`, `add-test`, `port` |
| `group_CMakeLists.txt.j2`       | `newgroup`                     |
| `test_CMakeLists.txt.j2`        | `newgroup`                     |
| `toplevel_CMakeLists.txt.j2`    | `newmod`                       |
| `flat_blocks_CMakeLists.txt.j2` | `newmod --flat`                |
| `bench_block.cpp.j2`            | `newbench`                     |
| `bench_CMakeLists.txt.j2`       | `newbench`                     |
| `ci_coverage.yml.j2`            | `ci --coverage`                |
| `ci_matrix.yml.j2`              | `ci --matrix`                  |
| `ci_release.yml.j2`             | `ci --release`                 |
| `ci_sanitizers.yml.j2`          | `presets --init`               |
| `ci_clang.yml.j2`               | `tidy --init`                  |
| `clang-format.j2`               | `tidy --init`                  |
| `clang-tidy.j2`                 | `tidy --init`                  |
| `cmake_presets.json.j2`         | `presets`                      |
| `Doxyfile.j2`                   | `docs`                         |
| `Dockerfile.devcontainer.j2`    | `devcontainer`                 |
| `devcontainer.json.j2`          | `devcontainer`                 |
| `gitignore.j2`                  | `newmod`                       |
| `pre_commit_config.yaml.j2`     | `pre-commit`                   |
| `vscode_settings.json.j2`       | `vscode`                       |
| `vscode_launch.json.j2`         | `vscode`                       |
| `plot_bench.py.j2`              | `newbench --plot`              |

Use `gr4_modtool templates list` to see which built-in templates exist and whether any are currently overridden in your project.

### Template context variables

Before overriding a template, inspect its context with `gr4_modtool templates list --verbose` and read the variable descriptions. All templates use `StrictUndefined` — every variable referenced in the template must be present in the context or rendering will fail.

Use `gr4_modtool templates check` to validate your override by rendering it with dummy values.

---

## Complete worked example

The `examples/gr4_modtool_example_plugin/` directory in the repository contains a minimal but fully installable plugin demonstrating both extension points:

```
gr4_modtool_example_plugin/
├── pyproject.toml
├── README.md
└── gr4_modtool_example_plugin/
    ├── __init__.py
    ├── commands/
    │   └── report.py          ← adds "gr4_modtool report" command
    └── templates/
        ├── __init__.py
        └── qa_block.cpp.j2    ← overrides the default test template
```

Install it alongside gr4_modtool:

```bash
pip install -e examples/gr4_modtool_example_plugin/
```

Then:

```bash
gr4_modtool report              # new command from the plugin
gr4_modtool templates list      # shows qa_block.cpp.j2 as "plugin" override
```

---

## Packaging checklist

- [ ] Command is a `click.BaseCommand` instance (decorated with `@click.command` or `@click.group`)
- [ ] Command includes `@click.option("--project-dir", ...)` for project-aware commands
- [ ] `FileNotFoundError` from `load_config` is caught and reported cleanly
- [ ] Entry point registered under `gr4_modtool.commands` in `pyproject.toml`
- [ ] Template callable returns a valid directory path
- [ ] Overridden templates validated with `gr4_modtool templates check`
- [ ] Template entry point registered under `gr4_modtool.templates` in `pyproject.toml`
