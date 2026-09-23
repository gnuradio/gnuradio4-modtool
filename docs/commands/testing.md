# Testing & Benchmarks

## add-test

Generate `qa_<Block>.cpp` for a block that has no test yet.

```bash
gr4_modtool add-test [BLOCK_NAME] [OPTIONS]
```

| Option               | Description                |
| -------------------- | -------------------------- |
| `--group TEXT`       | Group containing the block |
| `--project-dir PATH` | Project root               |
| `--yes / -y`         | Skip confirmation          |

Parses the block header via regex to recover template parameters, ports, type list, and processing style, then renders `qa_block.cpp.j2` and adds the entry to CMakeLists.txt.

---

## newbench

Generate a throughput benchmark for an existing block.

```bash
gr4_modtool newbench [BLOCK_NAME] [OPTIONS]
```

| Option               | Description                                         |
| -------------------- | --------------------------------------------------- |
| `--group TEXT`       | Group containing the block                          |
| `--wire-build`       | Add CMake entries for the benchmark                 |
| `--plot`             | Also generate a `plot_<Block>.py` matplotlib script |
| `--project-dir PATH` | Project root                                        |
| `--yes / -y`         | Skip confirmation                                   |

Creates `blocks/<group>/benchmarks/bench_<Name>.cpp` with `<chrono>` timing over 2²⁰ samples and CSV output (`block,config,N,throughput_MSas`).

When `--wire-build` is set:

- Creates `blocks/<group>/benchmarks/CMakeLists.txt` if it doesn't exist
- Adds the executable entry
- Wraps the `add_subdirectory(benchmarks)` call in an `if(ENABLE_BENCHMARKING)` guard in the group CMakeLists.txt

When `--plot` is set, a Python script is written that runs the benchmark binary and renders a throughput bar chart:

```bash
python blocks/<group>/benchmarks/plot_<Name>.py ./build/blocks/<group>/benchmarks/bench_<Name>
# Saves bench_<Name>.png
```

---

## test

Run a single block's test binary inside an existing build directory.

```bash
gr4_modtool test BLOCK_NAME [OPTIONS]
```

| Option               | Description                             |
| -------------------- | --------------------------------------- |
| `--build-dir PATH`   | Build directory (default: `build`)      |
| `--verbose / -v`     | Pass `--verbose` to ctest               |
| `--watch / -w`       | Rebuild and retest on every `.hpp` save |
| `--project-dir PATH` | Project root                            |

For CMake projects runs:

```bash
ctest --test-dir <build_dir> -R qa_<BLOCK_NAME> --output-on-failure
```

### Watch mode

```bash
gr4_modtool test MyFilter --watch
```

Watches the block's include directory for `.hpp` modifications. On each save it runs an incremental rebuild targeting only `qa_<BLOCK_NAME>` (faster than a full build), then re-runs the test:

```
Watching blocks/dsp/include/gnuradio-4.0/dsp for .hpp changes (Ctrl+C to stop)
── 14:32:05 — rebuilding ──────────────────────────────────────
  $ cmake --build build --target qa_MyFilter
  $ ctest --test-dir build -R qa_MyFilter --output-on-failure
100% tests passed
```

Rapid saves are debounced (1-second cooldown) to avoid double-fires from editor temp-file patterns. Requires the `watchdog` package (`pip install watchdog`).

At the start of each rebuild cycle, `lint-headers` runs automatically against the block's header and prints any issues (errors and warnings) before attempting to compile. This gives immediate feedback on macro and port consistency without waiting for a build.

### Coverage in watch mode

```bash
gr4_modtool test MyFilter --watch --coverage
```

When `--coverage` is set, watch mode uses a pre-configured coverage build directory instead of the regular build directory. After each passing test run the HTML coverage report is regenerated automatically so the browser view stays up to date as you edit.

Run `gr4_modtool coverage` once first to create and configure the coverage build:

```bash
gr4_modtool coverage --build-dir build-coverage   # one-time setup
gr4_modtool test MyFilter --watch --coverage       # then iterate
```

| Option                   | Description                                                           |
| ------------------------ | --------------------------------------------------------------------- |
| `--coverage`             | Enable coverage regeneration on each passing run (requires `--watch`) |
| `--coverage-dir PATH`    | Coverage build directory to use (default: `build-coverage`)           |
| `--coverage-output PATH` | Directory for the HTML report (default: `coverage`)                   |
| `--coverage-tool CHOICE` | `auto`, `gcovr`, or `llvm-cov` (default: `auto`)                      |

---

## coverage

Build the project with coverage instrumentation, run all tests, and generate an HTML coverage report.

```bash
gr4_modtool coverage [OPTIONS]
```

| Option               | Description                                                             |
| -------------------- | ----------------------------------------------------------------------- |
| `--build-dir PATH`   | Coverage build directory (default: `build-coverage`)                    |
| `--output-dir PATH`  | HTML report output directory (default: `coverage`)                      |
| `--tool CHOICE`      | `auto`, `gcovr`, or `llvm-cov` (default: `auto`)                        |
| `--open / --no-open` | Open the report in the default browser after generation (default: open) |
| `-j INT`             | Parallel build jobs                                                     |
| `--project-dir PATH` | Project root                                                            |

Creates a dedicated build directory configured with coverage flags, builds the full project, runs all tests, then generates an HTML report:

```bash
gr4_modtool coverage                         # auto-detect gcovr or llvm-cov
gr4_modtool coverage --tool gcovr            # force gcovr
gr4_modtool coverage --output-dir html_cov   # custom report location
gr4_modtool coverage --no-open               # skip browser launch
```

**Tool selection** — `auto` tries `gcovr` first, then falls back to `llvm-cov`. Install one with:

```bash
pip install gcovr
# or install llvm via your package manager (provides llvm-cov)
```

The report is written to `<output-dir>/index.html`. Exit code mirrors the test suite: non-zero if any tests fail.
