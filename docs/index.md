# gr4_modtool

**gr4_modtool** is a command-line tool for creating and managing [GNURadio 4](https://github.com/gnuradio/gnuradio) out-of-tree (OOT) block modules.

It handles the repetitive work of:

- Scaffolding new OOT projects and block groups
- Generating block headers, tests, and benchmarks from templates
- Keeping CMake build files in sync as blocks are added, moved, renamed, or removed
- Auditing project health (missing tests, orphaned build entries, etc.)

## Quick example

```bash
# Create a new OOT module
gr4_modtool newmod --name myfilters
cd myfilters

# Add a block group and a block
gr4_modtool newgroup --name dsp
gr4_modtool newblock --group dsp      # interactive prompts

# Check for issues
gr4_modtool check

# Build and test
gr4_modtool build --test
```

## Commands at a glance

| Command    | What it does                                         |
| ---------- | ---------------------------------------------------- |
| `newmod`   | Scaffold a new OOT project                           |
| `newgroup` | Add a block group directory                          |
| `newblock` | Generate a block header, test, and build entries     |
| `newparam` | Add an `Annotated<>` parameter to a block            |
| `newbench` | Generate a throughput benchmark                      |
| `add-test` | Generate a test for a block that has none            |
| `cp`       | Copy a block to a new name                           |
| `mv`       | Move a block to a different group                    |
| `rename`   | Rename a block everywhere                            |
| `rm`       | Remove a block and its files                         |
| `init`     | Adopt an existing project (write `.gr4modtool.toml`) |
| `check`    | Audit project for out-of-sync state                  |
| `info`     | List groups and blocks                               |
| `show`     | Display a block's source with syntax highlighting    |
| `build`    | Configure and build (CMake)                          |
| `test`     | Run one block's test without rebuilding              |
| `format`   | Run clang-format over headers and test sources       |

Every command is also available as a Python library — see the
[Python API](python-api.md).
