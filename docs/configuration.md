# Configuration

gr4_modtool stores project metadata in `.gr4modtool.toml` at the project root. This file is created by `newmod` or `init` and read by all other commands.

## File format

```toml
[project]
name = "myfilters"
version = "0.1.0"
cpp_namespace = "gr::myfilters"
cmake_prefix = "gr4_myfilters"
gr4_include_prefix = "gnuradio-4.0"

[build]
cmake = true

[groups]
dsp = "blocks/dsp"
channel = "blocks/channel"
```

## Fields

### `[project]`

| Field                | Description                                        |
| -------------------- | -------------------------------------------------- |
| `name`               | Module name (snake_case)                           |
| `version`            | Semantic version string                            |
| `cpp_namespace`      | Root C++ namespace, e.g. `gr::myfilters`           |
| `cmake_prefix`       | CMake target prefix, e.g. `gr4_myfilters`          |
| `gr4_include_prefix` | Include prefix directory, typically `gnuradio-4.0` |

### `[build]`

| Field   | Description                    |
| ------- | ------------------------------ |
| `cmake` | Whether the project uses CMake |

Both can be `true` if the project supports both build systems.

### `[groups]`

A mapping from group name to relative path from the project root.

```toml
[groups]
dsp = "blocks/dsp"
```

## Template overrides

gr4_modtool searches for templates in three locations, in order:

1. **Per-project overrides** — `.gr4modtool/templates/` in the project root
2. **Plugin templates** — registered via the `gr4_modtool.templates` entry point
3. **Built-in templates** — shipped with the package

Place a `.j2` file with the same name as a built-in template in `.gr4modtool/templates/` to override it for a specific project. The `MODTOOL_TEMPLATE_DIR` environment variable can also point to a directory of overrides.

### Built-in templates

| File                         | Generated output                                    |
| ---------------------------- | --------------------------------------------------- |
| `block.hpp.j2`               | Block header (C++ struct, ports, GR_REGISTER_BLOCK) |
| `qa_block.cpp.j2`            | Block unit test source                              |
| `bench_block.cpp.j2`         | Throughput benchmark source                         |
| `plot_bench.py.j2`           | Benchmark matplotlib plot script                    |
| `group_CMakeLists.txt.j2`    | Group CMakeLists.txt                                |
| `test_CMakeLists.txt.j2`     | Test directory CMakeLists.txt                       |
| `bench_CMakeLists.txt.j2`    | Benchmarks CMakeLists.txt                           |
| `toplevel_CMakeLists.txt.j2` | Top-level CMakeLists.txt                            |
| `Doxyfile.j2`                | Doxygen configuration                               |
| `clang-format.j2`            | `.clang-format` style file                          |
| `clang-tidy.j2`              | `.clang-tidy` checks file                           |
| `cmake_presets.json.j2`      | `CMakePresets.json` (debug/release/asan/ubsan/tsan) |
| `vscode_settings.json.j2`    | `.vscode/settings.json`                             |
| `vscode_launch.json.j2`      | `.vscode/launch.json`                               |
| `devcontainer.json.j2`       | `.devcontainer/devcontainer.json`                   |
| `Dockerfile.devcontainer.j2` | `.devcontainer/Dockerfile`                          |
| `ci_coverage.yml.j2`         | `.github/workflows/coverage.yml`                    |
| `ci_release.yml.j2`          | `.github/workflows/release.yml`                     |
| `ci_matrix.yml.j2`           | `.github/workflows/matrix.yml`                      |
| `ci_sanitizers.yml.j2`       | `.github/workflows/sanitizers.yml`                  |
| `pre_commit_config.yaml.j2`  | `.pre-commit-config.yaml`                           |
| `gitignore.j2`               | `.gitignore`                                        |

## Logging

Commands print only their own summary by default. Global flags — placed **before**
the subcommand — control the log stream:

```bash
gr4_modtool -v newblock --group dsp             # files written, commands run
gr4_modtool -vv status                          # + config discovery, template resolution
gr4_modtool --quiet check                       # errors only
gr4_modtool --log-file gr4.log build            # full debug log to a file
```

| Flag            | Console level                                                                            |
| --------------- | ---------------------------------------------------------------------------------------- |
| _(none)_        | `WARNING`                                                                                |
| `-v`            | `INFO` — every file created/updated, every external command and its exit code            |
| `-vv`           | `DEBUG` — project discovery, template search path and which template won, render timings |
| `-q`, `--quiet` | `ERROR`                                                                                  |

`--log-file PATH` always records at `DEBUG`, independent of the console level, and
appends rather than truncating. Its directory is created if missing.

Defaults come from the environment when no flag is given:

| Variable                | Effect                                                                |
| ----------------------- | --------------------------------------------------------------------- |
| `GR4_MODTOOL_LOG_LEVEL` | Console level by name (`DEBUG`, `INFO`, `WARNING`, `ERROR`) or number |
| `GR4_MODTOOL_LOG_FILE`  | Default `--log-file` path                                             |

An explicit flag always beats the environment. `--quiet` and `-v` together are an error.

### From Python

Records are emitted on the `gr4_modtool` logger hierarchy, which has
`propagate = False` once configured, so importing gr4_modtool never adds output to
an application's own logging setup. Call `configure_logging()` to opt in:

```python
from gr4_modtool.api import configure_logging

configure_logging(verbose=1)                            # INFO to stderr
configure_logging(verbose=2, log_file="gr4.log")        # + full debug log
configure_logging(console=False, log_file="gr4.log")    # file only
```

Or wire the loggers into your own handlers instead, and never call
`configure_logging()` at all:

```python
import logging

logging.getLogger("gr4_modtool").addHandler(my_handler)
```

## Plugin system

Third-party packages can register additional commands and templates by declaring entry points in their `pyproject.toml`:

```toml
[project.entry-points."gr4_modtool.commands"]
my_command = "my_package.commands.my_cmd:cmd"

[project.entry-points."gr4_modtool.templates"]
my_templates = "my_package:get_template_dir"
```

Plugin commands appear alongside the built-in commands in `gr4_modtool --help`. Plugin templates are searched after per-project overrides but before built-in templates.
