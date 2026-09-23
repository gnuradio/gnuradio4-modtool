# Building & Formatting

## build

Configure and build the project using CMake. Does not require `.gr4modtool.toml`.

```bash
gr4_modtool build [OPTIONS]
```

| Option               | Description                                    |
| -------------------- | ---------------------------------------------- |
| `--build-dir PATH`   | Build directory (default: `build`)             |
| `--clean`            | Delete build directory before configuring      |
| `--test`             | Run tests after building                       |
| `--jobs / -j INT`    | Parallel build jobs (default: CPU count)       |
| `--reconfigure`      | Re-run cmake setup even if already configured  |
| `--cmake-args TEXT`  | Extra arguments passed to `cmake` (repeatable) |
| `--project-dir PATH` | Project root                                   |

Auto-detects the build system: CMake if `CMakeLists.txt` is present.

**CMake flow:**

```bash
cmake -B build [--cmake-args]
cmake --build build --parallel <jobs>
ctest --test-dir build --output-on-failure   # if --test
```

---

## format

Run `clang-format` over all block headers and test sources.

```bash
gr4_modtool format [OPTIONS]
```

| Option               | Description                                       |
| -------------------- | ------------------------------------------------- |
| `--group TEXT`       | Format only this group                            |
| `--check`            | Dry-run mode: exit 1 if any file needs formatting |
| `--style TEXT`       | clang-format style (`file`, `llvm`, `google`, …)  |
| `--project-dir PATH` | Project root                                      |

If `clang-format` is not installed, the command prints a warning and exits 0 (so it doesn't break CI on machines without it — add a separate CI step to enforce installation if needed).

**CI usage:**

```yaml
- name: Check C++ formatting
  run: gr4_modtool format --check --style file
```

---

## tidy

Run `clang-tidy` on block headers.

```bash
gr4_modtool tidy [OPTIONS]
```

| Option               | Description                                        |
| -------------------- | -------------------------------------------------- |
| `--group TEXT`       | Run only on this group                             |
| `--build-dir PATH`   | Build directory containing `compile_commands.json` |
| `--project-dir PATH` | Project root                                       |

Requires a build directory with `compile_commands.json` (use `cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON` or the `asan` preset from `gr4_modtool presets`).

If `clang-tidy` is not installed, the command prints a warning and exits 0.
