# Project Health

## init

Bootstrap `.gr4modtool.toml` for an existing GNURadio 4 OOT project that doesn't have one.

```bash
gr4_modtool init [OPTIONS]
```

| Option               | Description                                        |
| -------------------- | -------------------------------------------------- |
| `--project-dir PATH` | Project root (default: current directory)          |
| `--yes / -y`         | Accept all auto-detected values without prompting  |
| `--dry-run`          | Print detected structure without writing any files |
| `--force`            | Overwrite an existing `.gr4modtool.toml`           |

Auto-detects from the directory tree:

- **Project name** and **version** from `CMakeLists.txt` `project(NAME VERSION x.y.z)` call
- **Groups** and **block names** from subdirectory structure
- **GR4 include prefix** (e.g. `gnuradio-4.0`) from the include directory layout
- **Build systems** (CMake) from file presence

Three directory layouts are recognised automatically:

| Layout       | Pattern                                                      |
| ------------ | ------------------------------------------------------------ |
| Standard     | `blocks/<group>/include/<prefix>/<group>/*.hpp`              |
| `src/blocks` | `src/blocks/<group>/include/<prefix>/<group>/*.hpp`          |
| Flat include | `include/<prefix>/<group>/*.hpp` (no `blocks/` subdirectory) |

**Example output:**

```
Detected project at: /path/to/mymod
  Name:    mymod  (from CMakeLists.txt)
  Version: 0.1.0
  Prefix:  gnuradio-4.0
  Build:   cmake

  Groups and blocks found:
    basic        (14 blocks): AGC, Converters, Copy, DCBlocker, …
    channel       (3 blocks): FlatFadingChannel, RayleighFadingChannel, …

Created .gr4modtool.toml
  2 group(s) registered: basic, channel
  17 block(s) found total
  Run 'gr4_modtool info' to verify.
```

Use `--dry-run` to preview detection without writing anything:

```bash
gr4_modtool init --dry-run
```

Use `--force` to update an existing config (e.g. after adding groups manually):

```bash
gr4_modtool init --force --yes
```

---

## check

Audit the project for out-of-sync state between headers, test sources, and build files.

```bash
gr4_modtool check [OPTIONS]
```

| Option               | Description                                 |
| -------------------- | ------------------------------------------- |
| `--group TEXT`       | Audit only this group                       |
| `--json`             | Output results as JSON (for CI / scripting) |
| `--project-dir PATH` | Project root                                |

**Issues reported:**

| Severity | Condition                                     |
| -------- | --------------------------------------------- |
| warning  | Header has no matching `qa_*.cpp` test source |
| warning  | Header is missing `GR_REGISTER_BLOCK` macro   |
| error    | Test source has no CMake entry                |
| error    | CMake entry has no matching test source       |

Exit code 1 if any errors are found. Example JSON output:

```json
{
  "issues": [
    {
      "group": "dsp",
      "block": "Ghost",
      "issue": "CMake entry has no test source",
      "severity": "error"
    }
  ],
  "error_count": 1,
  "warning_count": 0
}
```

---

## info

List all groups and blocks in the project.

```bash
gr4_modtool info [OPTIONS]
```

| Option               | Description                               |
| -------------------- | ----------------------------------------- |
| `--verbose / -v`     | Show port and parameter details per block |
| `--catalog`          | Print a Markdown block catalog table      |
| `--json`             | Output as JSON                            |
| `--project-dir PATH` | Project root                              |

With `--verbose`, each block is shown in a Rich panel with its input/output ports, processing style, and `Annotated<>` parameters.

With `--catalog`, outputs a Markdown table suitable for pasting into a README:

```markdown
# Block Catalog — myfilters

| Group | Block         | Ports In | Ports Out | Style      | Parameters        |
| ----- | ------------- | -------- | --------- | ---------- | ----------------- |
| dsp   | LowPassFilter | in:T     | out:T     | processOne | cutoff_freq:float |
```

---

## show

Display a block's header or test file with C++ syntax highlighting.

```bash
gr4_modtool show BLOCK_NAME [OPTIONS]
```

| Option               | Description                              |
| -------------------- | ---------------------------------------- |
| `--group TEXT`       | Group containing the block               |
| `--test`             | Show the test file instead of the header |
| `--project-dir PATH` | Project root                             |

---

## status

Print a health summary of the current project.

```bash
gr4_modtool status [OPTIONS]
```

| Option               | Description  |
| -------------------- | ------------ |
| `--project-dir PATH` | Project root |

Scans the project on disk (no compilation) and displays a Rich dashboard covering:

- **Groups & Blocks** — per-group block count and test coverage ratio. Shown green when all blocks have a `qa_*.cpp`; yellow when any are missing.
- **CI workflows** — lists `.yml` files found under `.github/workflows/`.
- **Quality tools** — presence of `.clang-format`, `.clang-tidy`, `Doxyfile`, `.pre-commit-config.yaml`.
- **Warnings** — lists any blocks that have no test file.

Example output:

```
──────────────────── myfilters  v0.1.0 ─────────────────────
  /home/user/myfilters
  2 group(s) · 5 block(s) · cmake

   Group    Blocks    Tests
   basic         3    3/3
   dsp           2    1/2

  CI workflows
    ✓  ci.yml
    ✓  coverage.yml

  Quality tools
    ✓  .clang-format
    ✓  .clang-tidy
    ✗  Doxyfile
    ✗  .pre-commit-config.yaml

  ⚠  Warnings
    •  dsp/LowPassFilter — no test file
```

---

## sync

Reconcile headers, test sources, and build entries across all groups.

```bash
gr4_modtool sync [OPTIONS]
```

| Option               | Description                                              |
| -------------------- | -------------------------------------------------------- |
| `--group TEXT`       | Limit sync to this group (repeatable)                    |
| `--prune`            | Also remove stale build entries for deleted test sources |
| `--yes / -y`         | Apply without interactive confirmation                   |
| `--dry-run / -n`     | Show what would change without writing any files         |
| `--project-dir PATH` | Project root                                             |

By default, sync generates missing `qa_*.cpp` test stubs and adds missing CMake build entries. Use `--prune` to also clean up entries that point at test sources that no longer exist.

**Typical workflow:**

```bash
gr4_modtool sync --dry-run      # preview changes
gr4_modtool sync --yes          # apply immediately
gr4_modtool sync --prune --yes  # apply and remove stale entries
```

Sync is the automated counterpart to `check`: where `check` audits and reports, `sync` fixes.

---

## version-bump

Bump or set the project version across all version-bearing files.

```bash
gr4_modtool version-bump [OPTIONS]
```

| Option               | Description                                      |
| -------------------- | ------------------------------------------------ |
| `--major`            | Bump major version (`X+1.0.0`)                   |
| `--minor`            | Bump minor version (`X.Y+1.0`)                   |
| `--patch`            | Bump patch version (`X.Y.Z+1`)                   |
| `--set VERSION`      | Set to an exact `X.Y.Z` value                    |
| `--yes / -y`         | Apply without confirmation                       |
| `--dry-run / -n`     | Show what would change without writing any files |
| `--project-dir PATH` | Project root                                     |

Updates every version-bearing file that exists in the project root:

| File               | Pattern updated                  |
| ------------------ | -------------------------------- |
| `.gr4modtool.toml` | `version = "X.Y.Z"`              |
| `CMakeLists.txt`   | `project(... VERSION X.Y.Z ...)` |
| `Doxyfile`         | `PROJECT_NUMBER = "X.Y.Z"`       |

Files that don't exist are silently skipped. Only actually-changed files are reported.

```bash
gr4_modtool version-bump --patch --yes      # 1.2.3 → 1.2.4
gr4_modtool version-bump --minor --dry-run  # preview: 1.2.3 → 1.3.0
gr4_modtool version-bump --set 2.0.0 --yes  # set exactly
```

Without a flag, an interactive prompt asks which part to bump (`patch`, `minor`, or `major`).
