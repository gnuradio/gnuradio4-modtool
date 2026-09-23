# gr4_modtool

A command-line tool for creating and managing [GNURadio 4](https://github.com/gnuradio/gnuradio) out-of-tree (OOT) block modules. It scaffolds projects, generates block headers and tests from templates, manages build-system wiring, and keeps everything in sync.

[![Tests](https://github.com/gnuradio/gnuradio4-modtool/actions/workflows/tests.yml/badge.svg)](https://github.com/gnuradio/gnuradio4-modtool/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

---

## Features

| Category                 | Commands                                                                           |
| ------------------------ | ---------------------------------------------------------------------------------- |
| Scaffolding              | `newmod`, `newgroup`                                                               |
| Block lifecycle          | `newblock`, `newparam`, `cp`, `mv`, `rename`, `rename-block`, `rename-group`, `rm` |
| Testing & benchmarking   | `add-test`, `test`, `newbench`                                                     |
| Project health           | `init`, `check`, `info`, `show`, `status`                                          |
| Building                 | `build`, `format`, `tidy`                                                          |
| Dev environment          | `vscode`, `devcontainer`, `completion`                                             |
| CI / quality             | `ci`, `presets`, `pre-commit`                                                      |
| Documentation & registry | `docs`, `add-dep`, `search`                                                        |
| Migration                | `port`                                                                             |

- **CMake** build systems supported side-by-side
- **Jinja2 templates** with per-project override support
- **Plugin system** — third-party packages can register extra commands and templates via entry-points

---

## Installation

```bash
pip install gr4_modtool
```

For development:

```bash
git clone https://github.com/gnuradio/gnuradio4-modtool
cd gr4_modtool
pip install -e ".[dev]"
```

---

## Quick Start

### Create a new OOT module

```bash
gr4_modtool newmod --name myfilters
cd myfilters
```

### Add a block group and a block

```bash
gr4_modtool newgroup --name dsp
gr4_modtool newblock --group dsp --template filter
# Interactive prompts: block name, ports, template params, …
```

### Check project health

```bash
gr4_modtool check           # Rich table of warnings/errors
gr4_modtool check --json    # Machine-readable output for CI
```

### View a block's header with syntax highlighting

```bash
gr4_modtool show MyFilter --group dsp
```

### Add a parameter to an existing block

```bash
gr4_modtool newparam MyFilter gain --group dsp \
    --type float --description "Linear gain" --default "1.0f"
```

### Copy or move blocks

```bash
gr4_modtool cp MyFilter MyFilter2 --from-group dsp --gen-test
gr4_modtool mv MyFilter --from dsp --to channel
```

### Generate a benchmark

```bash
gr4_modtool newbench MyFilter --group dsp --wire-build --plot
```

### Build the project

```bash
gr4_modtool build --test          # configure, build, run tests
gr4_modtool test MyFilter         # re-run one block's test only
gr4_modtool format --check        # lint C++ formatting (CI mode)
gr4_modtool tidy                  # run clang-tidy
```

### Adopt an existing project

```bash
cd /path/to/existing/gr4-oot-project
gr4_modtool init --yes            # auto-detect groups/blocks, write .gr4modtool.toml
gr4_modtool init --dry-run        # preview what would be detected without writing
gr4_modtool info --verbose        # show ports and parameters per block
gr4_modtool info --json           # list all blocks as JSON
```

### Port a GNURadio 3 block

```bash
gr4_modtool port old_module/python/my_filter.py --group dsp
```

### Set up developer tooling

```bash
gr4_modtool vscode               # write .vscode/settings.json and launch.json
gr4_modtool devcontainer         # write .devcontainer/ with Dockerfile
gr4_modtool presets --init       # write CMakePresets.json + sanitizer CI
gr4_modtool ci --coverage        # write GitHub Actions coverage workflow
gr4_modtool pre-commit --yes     # write .pre-commit-config.yaml
gr4_modtool completion --shell bash   # print shell completion setup
```

## Command Reference

See the [full documentation](https://gnuradio.github.io/gnuradio4-modtool) for detailed options.

### Scaffolding

| Command    | Description                           |
| ---------- | ------------------------------------- |
| `newmod`   | Scaffold a new GNURadio 4 OOT project |
| `newgroup` | Add a new block group directory       |

### Block lifecycle

| Command    | Description                                                    |
| ---------- | -------------------------------------------------------------- |
| `newblock` | Add a new block (header + test + build entries)                |
| `newparam` | Insert an `Annotated<>` parameter into an existing block       |
| `newbench` | Generate a throughput benchmark for a block                    |
| `add-test` | Generate a test file for a block that has none                 |
| `cp`       | Copy a block to a new name (optionally into a different group) |
| `mv`       | Move a block from one group to another                         |
| `rename`   | Rename a block everywhere (header, test, build files)          |
| `rm`       | Remove a block and all its associated files                    |

### Project health

| Command | Description                                                                    |
| ------- | ------------------------------------------------------------------------------ |
| `init`  | Bootstrap `.gr4modtool.toml` for an existing project (scans groups and blocks) |
| `check` | Audit the project for out-of-sync headers, tests, and build entries            |
| `info`  | List all groups and blocks; `--verbose` shows ports and parameters             |
| `show`  | Display a block's header or test file with syntax highlighting                 |

### Building

| Command  | Description                                         |
| -------- | --------------------------------------------------- |
| `build`  | Configure and build using CMake                     |
| `test`   | Run a single block's test binary without rebuilding |
| `format` | Run clang-format over headers and test sources      |
| `tidy`   | Run clang-tidy on block headers                     |

### Dev environment

| Command        | Description                                           |
| -------------- | ----------------------------------------------------- |
| `vscode`       | Write `.vscode/settings.json` and `launch.json`       |
| `devcontainer` | Write `.devcontainer/` with Docker setup              |
| `completion`   | Print shell completion setup line (bash / zsh / fish) |

### CI / quality

| Command      | Description                                                  |
| ------------ | ------------------------------------------------------------ |
| `ci`         | Write GitHub Actions workflows (coverage, release, matrix)   |
| `presets`    | Write `CMakePresets.json` and optional sanitizer CI workflow |
| `pre-commit` | Write `.pre-commit-config.yaml` (clang-format + tidy hooks)  |

### Documentation & dependencies

| Command   | Description                                          |
| --------- | ---------------------------------------------------- |
| `docs`    | Write a `Doxyfile` or print a Markdown block catalog |
| `add-dep` | Add a library dependency to CMake build files        |

### Migration

| Command | Description                                                        |
| ------- | ------------------------------------------------------------------ |
| `port`  | Parse a GNURadio 3.x Python block and scaffold a gr4 header + test |

---

## Configuration

gr4_modtool stores project metadata in `.gr4modtool.toml` at the project root:

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

### Logging

Every command is quiet by default and reports only its own summary. Global flags
(before the subcommand) open up what the tool is doing:

| Flag              | Effect                                                                     |
| ----------------- | -------------------------------------------------------------------------- |
| `-v`              | Log each file written, each build-file edit, and each external command run |
| `-vv`             | Add debug detail: config discovery, template resolution, render timings    |
| `-q` / `--quiet`  | Errors only                                                                |
| `--log-file PATH` | Append a full debug log to `PATH`, whatever the console level is           |

```bash
gr4_modtool -v newblock --group dsp          # see every file it touches
gr4_modtool -vv --log-file build.log build   # console detail plus a full log
```

Two environment variables set the defaults, so CI can turn logging on without
changing the command lines:

| Variable                | Effect                                                        |
| ----------------------- | ------------------------------------------------------------- |
| `GR4_MODTOOL_LOG_LEVEL` | Console level (`DEBUG`, `INFO`, …) when no `-v`/`-q` is given |
| `GR4_MODTOOL_LOG_FILE`  | Default `--log-file` path                                     |

Library users get the same stream by calling `configure_logging()` once — see
[Python API](docs/python-api.md). Records go to the `gr4_modtool` logger, which
does not propagate to the root logger, so importing gr4_modtool never disturbs
an application's own logging setup.

---

## License

MIT — see [LICENSE](LICENSE).
