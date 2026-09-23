# Command Reference

All commands accept `--help` for detailed option descriptions.

## Scaffolding

| Command                               | Description                 |
| ------------------------------------- | --------------------------- |
| [`newmod`](scaffolding.md#newmod)     | Scaffold a new OOT project  |
| [`newgroup`](scaffolding.md#newgroup) | Add a block group directory |

## Block Lifecycle

| Command                                  | Description                                      |
| ---------------------------------------- | ------------------------------------------------ |
| [`newblock`](blocks.md#newblock)         | Generate a block header, test, and build entries |
| [`newparam`](blocks.md#newparam)         | Add an `Annotated<>` parameter to a block        |
| [`newbench`](blocks.md#newbench)         | Generate a throughput benchmark                  |
| [`add-test`](testing.md#add-test)        | Generate a test for a block that has none        |
| [`cp`](blocks.md#cp)                     | Copy a block to a new name                       |
| [`mv`](blocks.md#mv)                     | Move a block to a different group                |
| [`rename`](blocks.md#rename)             | Rename a block everywhere (whole-word)           |
| [`rename-block`](blocks.md#rename-block) | Rename a block within its group                  |
| [`rename-group`](blocks.md#rename-group) | Rename a group and update all references         |
| [`rm`](blocks.md#rm)                     | Remove a block and its files                     |

## Project Health

| Command                                   | Description                                                    |
| ----------------------------------------- | -------------------------------------------------------------- |
| [`init`](project.md#init)                 | Adopt an existing project (scans groups and blocks)            |
| [`check`](project.md#check)               | Audit for out-of-sync state                                    |
| [`sync`](project.md#sync)                 | Fix out-of-sync state (generates stubs, updates build entries) |
| [`info`](project.md#info)                 | List groups and blocks; `--verbose` shows ports/params         |
| [`show`](project.md#show)                 | Display a block's source with syntax highlighting              |
| [`status`](project.md#status)             | Project health dashboard (blocks, tests, CI, tools)            |
| [`doctor`](quality.md#doctor)             | Check that the environment has all required tools              |
| [`version-bump`](project.md#version-bump) | Bump or set the project version across all build files         |

## Building & Testing

| Command                           | Description                                                |
| --------------------------------- | ---------------------------------------------------------- |
| [`build`](building.md#build)      | Configure and build (CMake)                                |
| [`test`](testing.md#test)         | Run one block's test without rebuilding                    |
| [`coverage`](testing.md#coverage) | Build with coverage flags, run tests, generate HTML report |
| [`format`](building.md#format)    | Run clang-format over headers and test sources             |
| [`tidy`](building.md#tidy)        | Run clang-tidy on block headers                            |

## Developer Environment

| Command                                  | Description                                     |
| ---------------------------------------- | ----------------------------------------------- |
| [`vscode`](devenv.md#vscode)             | Write `.vscode/settings.json` and `launch.json` |
| [`devcontainer`](devenv.md#devcontainer) | Write `.devcontainer/` with Docker setup        |
| [`completion`](devenv.md#completion)     | Print shell completion setup line               |
| [`templates`](devenv.md#templates)       | Manage project-local Jinja2 template overrides  |

## CI / Code Quality

| Command                                   | Description                                                |
| ----------------------------------------- | ---------------------------------------------------------- |
| [`ci`](quality.md#ci)                     | Write GitHub Actions workflows (coverage, release, matrix) |
| [`presets`](quality.md#presets)           | Write `CMakePresets.json` and sanitizer CI                 |
| [`pre-commit`](quality.md#pre-commit)     | Write `.pre-commit-config.yaml`                            |
| [`lint-headers`](quality.md#lint-headers) | Check block headers for missing macros and port mismatches |

## Documentation, Dependencies, Registry & Migration

| Command                           | Description                                        |
| --------------------------------- | -------------------------------------------------- |
| [`docs`](ecosystem.md#docs)       | Write a Doxyfile or print a Markdown block catalog |
| [`add-dep`](ecosystem.md#add-dep) | Add a library dependency to CMake build files      |
| [`search`](ecosystem.md#search)   | Search GitHub for published GNURadio 4 OOT modules |
| [`port`](ecosystem.md#port)       | Port a GNURadio 3.x Python block to a gr4 header   |
