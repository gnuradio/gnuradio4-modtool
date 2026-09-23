# CI & Code Quality

## ci

Write GitHub Actions workflow files for CI quality gates.

```bash
gr4_modtool ci [OPTIONS]
```

| Option                   | Description                            |
| ------------------------ | -------------------------------------- |
| `--coverage`             | Write `.github/workflows/coverage.yml` |
| `--release`              | Write `.github/workflows/release.yml`  |
| `--matrix / --no-matrix` | Write `.github/workflows/matrix.yml`   |
| `--project-dir PATH`     | Project root                           |

At least one of `--coverage`, `--release`, or `--matrix` must be specified.

### `--coverage`

Builds with `gcovr`, uploads an HTML report as an artifact, and fails the job if line coverage drops below a configurable threshold.

### `--release`

Triggers on `v*.*.*` tags and uses `softprops/action-gh-release` to create a GitHub Release with a source tarball.

### `--matrix`

Generates a build matrix across two compilers and two build types:

```yaml
strategy:
  matrix:
    compiler: [gcc, clang]
    build_type: [Debug, Release]
```

Each combination sets `CC`/`CXX` environment variables via `include:` entries.

---

## presets

Write `CMakePresets.json` and optionally a sanitizer CI workflow.

```bash
gr4_modtool presets [OPTIONS]
```

| Option               | Description                                                           |
| -------------------- | --------------------------------------------------------------------- |
| `--init`             | Write both `CMakePresets.json` and `.github/workflows/sanitizers.yml` |
| `--presets-only`     | Write only `CMakePresets.json`                                        |
| `--project-dir PATH` | Project root                                                          |

**CMakePresets.json** defines five presets:

| Preset    | Purpose                            |
| --------- | ---------------------------------- |
| `default` | Standard Debug build               |
| `release` | Optimised Release build            |
| `asan`    | AddressSanitizer + Debug           |
| `ubsan`   | UndefinedBehaviorSanitizer + Debug |
| `tsan`    | ThreadSanitizer + Debug            |

Use presets directly:

```bash
cmake --preset asan
cmake --build --preset asan
```

**`sanitizers.yml`** (with `--init`) runs `asan` and `ubsan` presets as separate CI jobs.

---

## pre-commit

Write a `.pre-commit-config.yaml` with local C++ quality hooks.

```bash
gr4_modtool pre-commit [OPTIONS]
```

| Option               | Description       |
| -------------------- | ----------------- |
| `--project-dir PATH` | Project root      |
| `--yes / -y`         | Skip confirmation |

The generated config installs two local hooks that run on every commit:

| Hook           | Command                           | Files                   |
| -------------- | --------------------------------- | ----------------------- |
| `clang-format` | `clang-format --dry-run --Werror` | `*.cpp`, `*.hpp`, `*.h` |
| `gr4-tidy`     | `gr4_modtool tidy`                | `*.hpp`                 |

**Install pre-commit and activate:**

```bash
pip install pre-commit
pre-commit install
```

After activation, both hooks run automatically on `git commit`. Run manually with:

```bash
pre-commit run --all-files
```

---

## lint-headers

Check block headers for common content issues.

```bash
gr4_modtool lint-headers [OPTIONS]
```

| Option               | Description                                       |
| -------------------- | ------------------------------------------------- |
| `--group TEXT`       | Check only this group                             |
| `--strict`           | Treat warnings as errors (exit 1 if any warnings) |
| `--json`             | Output results as JSON                            |
| `--project-dir PATH` | Project root                                      |

**Checks performed:**

| Severity | Condition                                                                     |
| -------- | ----------------------------------------------------------------------------- |
| error    | Header is missing `GR_REGISTER_BLOCK` macro                                   |
| error    | Header is missing `GR_MAKE_REFLECTABLE` macro                                 |
| error    | A port declared in the struct is absent from `GR_MAKE_REFLECTABLE`            |
| warning  | `GR_REGISTER_BLOCK` has an empty type list                                    |
| warning  | Block description (`Doc<"...">`) is empty                                     |
| warning  | An `Annotated<>` parameter has no `Doc<>` description                         |
| warning  | A name listed in `GR_MAKE_REFLECTABLE` is not declared as a port or parameter |

Exit code 1 if any errors are found. With `--strict`, warnings also cause exit 1.

**Example JSON output:**

```json
{
  "issues": [
    {
      "group": "dsp",
      "block": "LowPassFilter",
      "issue": "port 'in' is declared but absent from GR_MAKE_REFLECTABLE",
      "severity": "error"
    }
  ],
  "error_count": 1,
  "warning_count": 0
}
```

---

## doctor

Check that the environment has everything `gr4_modtool` needs.

```bash
gr4_modtool doctor [OPTIONS]
```

| Option               | Description                                                   |
| -------------------- | ------------------------------------------------------------- |
| `--json`             | Output results as JSON                                        |
| `--project-dir PATH` | Project root (scopes build-system checks to configured tools) |

Probes the system for required and optional tools, reporting each as pass, warn, or fail.

**Required checks:**

| Check             | Minimum version                   |
| ----------------- | --------------------------------- |
| Python            | 3.11                              |
| CMake             | 3.20 (only if project uses CMake) |
| ninja             | any                               |
| pkg-config        | any                               |
| C++ compiler      | g++ or clang++                    |
| gnuradio4 headers | detected via pkg-config           |

**Optional checks** (warn if absent, do not affect exit code):

| Tool           | Used for                          |
| -------------- | --------------------------------- |
| `gcovr`        | HTML coverage reports             |
| `llvm-cov`     | LLVM-based coverage reports       |
| `clang-tidy`   | Static analysis (`tidy` command)  |
| `clang-format` | C++ formatting (`format` command) |
| `watchdog`     | `test --watch` mode               |

Exit code 0 when all required checks pass.
