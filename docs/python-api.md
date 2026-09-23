# Python API

Everything the CLI does is available as a Python library through
`gr4_modtool.api`. Import from `gr4_modtool.api` only — paths into internal
command modules are not a supported surface.

There are two layers:

- **Functions** — take a `ProjectConfig` (or plain paths) and return data or
  the `list[Path]` they wrote. Best for scripts that already manage a config.
- **`Project` facade** — one object per project, one method per CLI command.
  Best for interactive use and tools built on top of gr4_modtool.

## Quick start

```python
from gr4_modtool.api import Project

# Scaffold a new OOT module (the `newmod` command)
proj = Project.create("/tmp/gr4_demo", "gr4_demo", first_group="dsp", gen_presets=True)

# ...or load an existing one (walks upward from the path, like the CLI)
proj = Project.load("~/work/gr4_demo")

# Add a block (the `newblock` command). Only block_name (and group_name,
# for grouped projects) is required; ports and processing style default
# from the archetype ("sync" unless overridden).
proj.new_block(
    block_name="Gain",
    group_name="dsp",
    description="Multiplies samples by a constant.",
)

# The keywords match the spec-entry shape, so a spec dict applies
# directly with ** unpacking:
entry = {
    "group_name": "dsp",
    "block_name": "Squelch",
    "description": "Gates samples below a power threshold.",
    "in_ports": [{"name": "in", "type": "T"}],
    "out_ports": [{"name": "out", "type": "T"}],
    "processing_style": "processOne",
}
proj.new_block(**entry)

# Audit and build
issues = proj.audit()            # `check`
exit_code = proj.build(run_tests=True)  # `build --test`
```

The same operations with the functional layer:

```python
from pathlib import Path
from gr4_modtool.api import load_config, write_block_files, audit_project

cfg = load_config(Path("~/work/gr4_demo").expanduser())
write_block_files(cfg, entry)
issues = audit_project(cfg)
```

A complete runnable walkthrough — scaffold, blocks, lifecycle, sync, audit —
lives in the `examples/gr4_modtool_python_api/` directory in the repository:

```bash
python3 examples/gr4_modtool_python_api/build_project.py
```

## Command → API mapping

| CLI command              | Function                                                               | `Project` method                                              |
| ------------------------ | ---------------------------------------------------------------------- | ------------------------------------------------------------- |
| `newmod`                 | `write_project`                                                        | `Project.create`                                              |
| `init`                   | `scan_project_dir`, `write_init_config`                                | —                                                             |
| `newgroup`               | `add_group`, `write_group_skeleton`                                    | `new_group`                                                   |
| `newblock`               | `write_block_files`, `load_spec`, `validate_spec_entry`                | `new_block`, `new_blocks_from_spec`                           |
| `newparam`               | `add_param`                                                            | `add_param`                                                   |
| `add-test`               | `write_test_for_block`                                                 | `add_test`                                                    |
| `newbench`               | `write_bench_file`, `write_plot_script`                                | `new_bench`                                                   |
| `cp`                     | `copy_block`                                                           | `copy_block`                                                  |
| `mv`                     | `move_block`                                                           | `move_block`                                                  |
| `rm`                     | `remove_block`                                                         | `remove_block`                                                |
| `rename`, `rename-block` | `rename_block`                                                         | `rename_block`                                                |
| `rename-group`           | `rename_group`                                                         | `rename_group`                                                |
| `port`                   | `port_gr3_block`, `parse_gr3_python`                                   | `port_gr3`                                                    |
| `check`                  | `audit_project`                                                        | `audit`                                                       |
| `validate`               | `validate_project`                                                     | `validate`                                                    |
| `lint-headers`           | `lint_headers`, `lint_header`                                          | `lint_headers`                                                |
| `status`                 | `gather_status`                                                        | `status`                                                      |
| `info`, `ls`, `list`     | `collect_inventory`                                                    | `inventory`                                                   |
| `show`                   | `show_block`                                                           | `show_block`                                                  |
| `export-spec`            | `export_spec`, `header_to_spec_entry`                                  | `export_spec`                                                 |
| `docs`                   | `build_catalog`, `write_doxyfile`                                      | `catalog`, `write_doxyfile`                                   |
| `sync`                   | `plan_sync`, `apply_sync`                                              | `sync_plan`, `sync_apply`                                     |
| `build`                  | `run_build`                                                            | `build`                                                       |
| `test`                   | `run_block_test`                                                       | `run_test`                                                    |
| `coverage`               | `run_coverage`, `detect_coverage_tool`                                 | `coverage`                                                    |
| `format`                 | `format_files`                                                         | `format`                                                      |
| `tidy`                   | `run_tidy`, `write_clang_config`, `write_ci_clang`                     | `tidy`, `write_clang_config`                                  |
| `presets`                | `write_cmake_presets`, `write_ci_sanitizers`                           | `write_cmake_presets`                                         |
| `ci`                     | `write_ci_coverage`, `write_ci_release`, `write_ci_matrix`             | `write_ci`                                                    |
| `devcontainer`           | `write_devcontainer`                                                   | `write_devcontainer`                                          |
| `vscode`                 | `write_vscode`                                                         | `write_vscode`                                                |
| `pre-commit`             | `write_precommit`                                                      | `write_precommit`                                             |
| `add-dep`                | `add_cmake_dep`                                                        | `add_dependency`                                              |
| `templates`              | `list_templates`, `init_template_override`, `check_template_overrides` | `list_templates`, `init_template_override`, `check_templates` |
| `doctor`                 | `run_doctor`                                                           | `doctor`                                                      |
| `publish`                | `pre_flight`                                                           | `pre_flight`                                                  |
| `search`                 | `search_registry`                                                      | — (not project-bound)                                         |
| `version-bump`           | `apply_version_bump`                                                   | `bump_version`                                                |

## Logging

The API never prints. To watch what it does, turn on logging once at start-up:

```python
from gr4_modtool.api import configure_logging

configure_logging(verbose=1)                        # INFO to stderr: every file written
configure_logging(verbose=2, log_file="gr4.log")    # + debug detail, and a full log file
configure_logging(console=False, log_file="gr4.log")  # file only, nothing on stderr
```

Records are emitted on the `gr4_modtool` logger hierarchy — one logger per module,
named after it (`gr4_modtool.project.cmake`, `gr4_modtool.templates`, …). If your
application already configures logging, skip `configure_logging()` and attach your
own handler instead:

```python
import logging

logging.getLogger("gr4_modtool").addHandler(my_handler)
logging.getLogger("gr4_modtool").setLevel(logging.INFO)
```

What lands at each level:

| Level | Records |
|-------|---------|
| `INFO` | Each file created or updated (with size), each external command and its exit code, the loaded project |
| `DEBUG` | Project discovery, template search path and which template won, render timings, build-file edits that found nothing to change |
| `WARNING` | Plugins that failed to load, missing external tools |

See [Configuration](configuration.md#logging) for the CLI flags and environment
variables that drive the same machinery.

## Conventions

- **File-writing calls return `list[Path]`** — every path created or modified,
  in write order. Nothing is printed (but see [Logging](#logging)).
- **Errors are exceptions, not exit codes**: `ValueError` for bad input or a
  missing block/group, `FileExistsError`/`FileNotFoundError` for filesystem
  conflicts. Only the process-running calls (`build`, `run_test`, `coverage`,
  `format`, `tidy`) return subprocess exit codes.
- **Interactive-only behavior stays in the CLI.** The API never prompts;
  anything the CLI asks interactively is a required argument here.
- Config mutations (e.g. `new_group`, `bump_version`) persist to
  `.gr4modtool.toml` immediately; `Project.save()` re-writes it after manual
  edits to `proj.cfg`.
