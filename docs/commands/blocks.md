# Block Lifecycle

## newblock

Generate a block header, test file, and build entries.

```bash
gr4_modtool newblock [OPTIONS]
```

| Option                      | Description                                                   |
| --------------------------- | ------------------------------------------------------------- |
| `--group TEXT`              | Target group                                                  |
| `--template / -T ARCHETYPE` | Pre-fill ports and style from an archetype                    |
| `--simd`                    | Generate a SIMD-vectorization-friendly `processBulk` skeleton |
| `--project-dir PATH`        | Project root                                                  |
| `--yes / -y`                | Skip confirmation                                             |

### Archetypes

Use `--template` to skip the port/style prompts with a sensible default:

| Archetype      | Ports            | Style         |
| -------------- | ---------------- | ------------- |
| `source`       | — → `out:T`      | `processBulk` |
| `sink`         | `in:T` → —       | `processBulk` |
| `filter`       | `in:T` → `out:T` | `processOne`  |
| `decimator`    | `in:T` → `out:T` | `processBulk` |
| `interpolator` | `in:T` → `out:T` | `processBulk` |
| `custom`       | interactive      | interactive   |

```bash
gr4_modtool newblock --group dsp --template filter
```

### Interactive prompts

Without `--template`, you are asked for: block name, description, template parameters, input/output ports, processing style (`processOne` or `processBulk`), type list, and whether to generate a test.

**Generated files:**

- `blocks/<group>/include/gnuradio-4.0/<group>/<Name>.hpp`
- `blocks/<group>/test/qa_<Name>.cpp` (if `gen_test`)
- Updated `blocks/<group>/test/CMakeLists.txt`

### SIMD / vectorization hints

`--simd` forces `processBulk` and generates a loop skeleton that a modern C++ compiler can auto-vectorize:

```bash
gr4_modtool newblock --group dsp --template filter --simd
```

The generated body uses `#pragma GCC ivdep` to tell GCC there are no loop-carried dependencies, and names `n` explicitly so the loop bound is invariant:

```cpp
[[nodiscard]] gr::work::Status processBulk(
    std::span<const T> in, std::span<T> out) noexcept {
    // SIMD-vectorizable: loop body has no cross-iteration dependencies.
    const std::size_t n = in.size();
#pragma GCC ivdep
    for (std::size_t i = 0; i != n; ++i) {
        out[i] = in[i]; // TODO: implement
    }
    return gr::work::Status::OK;
}
```

Tips for keeping the loop vectorizable:

- Avoid branches inside the loop body — use `std::clamp` or ternary expressions.
- Keep the element stride at 1 (sequential access).
- Do not call virtual functions or non-inline helpers inside the loop.
- If ports use different template types (e.g. `std::complex<T>`) verify that the compiler supports SIMD for that type.

### Spec file

`--spec <file.yaml>` skips all interactive prompts and reads block definitions from a YAML file. The file may define a single block (mapping) or multiple blocks (list of mappings).

```bash
gr4_modtool newblock --spec blocks.yaml
gr4_modtool newblock --spec shared/filter.yaml --group channel   # --group overrides spec
gr4_modtool newblock --spec module_seed.yaml --simd              # apply --simd to all entries
```

**Single-block spec:**

```yaml
group: basic
block_name: MyFilter
description: "A bandpass filter"
template_params: [T]
in_ports:
  - { name: in, type: T }
out_ports:
  - { name: out, type: T }
processing_style: processOne
type_list: "float, double"
gen_test: true
```

**Multi-block spec:**

```yaml
- group: basic
  block_name: MyFilter
  archetype: filter # shorthand: fills in_ports/out_ports/processing_style
  type_list: "float, double"

- group: dsp
  block_name: MySource
  archetype: source
  type_list: "float, std::complex<float>"
  gen_test: false
```

**`archetype` shorthand** pre-fills `in_ports`, `out_ports`, and `processing_style` from the same archetypes as `--template`. Explicit keys in the YAML override the archetype values.

| Field                    | Required              | Default |
| ------------------------ | --------------------- | ------- |
| `block_name`             | yes                   | —       |
| `group`                  | yes (or `--group`)    | —       |
| `type_list`              | yes                   | —       |
| `archetype`              | no                    | —       |
| `description`            | no                    | `""`    |
| `template_params`        | no                    | `[T]`   |
| `in_ports` / `out_ports` | no (if archetype set) | —       |
| `processing_style`       | no (if archetype set) | —       |
| `gen_test`               | no                    | `true`  |
| `simd`                   | no                    | `false` |

Requires `PyYAML` (`pip install PyYAML`).

---

## newparam

Insert an `Annotated<>` parameter into an existing block header.

```bash
gr4_modtool newparam [BLOCK_NAME] [PARAM_NAME] [OPTIONS]
```

| Option               | Description                        |
| -------------------- | ---------------------------------- |
| `--group TEXT`       | Group containing the block         |
| `--type TEXT`        | C++ type (e.g. `float`, `int32_t`) |
| `--description TEXT` | Description for `Doc<"...">`       |
| `--default TEXT`     | C++ default value (e.g. `1.0f`)    |
| `--project-dir PATH` | Project root                       |
| `--yes / -y`         | Skip confirmation                  |

**Example:**

```bash
gr4_modtool newparam LowPass cutoff_freq --group dsp \
    --type float --description "Cutoff frequency in Hz" --default "1000.0f"
```

Inserts into the block struct (before `GR_MAKE_REFLECTABLE`):

```cpp
Annotated<float, "cutoff_freq", Doc<"Cutoff frequency in Hz">> cutoff_freq{1000.0f};
```

And updates:

```cpp
GR_MAKE_REFLECTABLE(LowPass, in, out, cutoff_freq);
```

---

## cp

Copy a block to a new name, optionally into a different group.

```bash
gr4_modtool cp SRC_NAME DST_NAME [OPTIONS]
```

| Option               | Description                                 |
| -------------------- | ------------------------------------------- |
| `--from-group TEXT`  | Source group (default: prompted)            |
| `--to-group TEXT`    | Destination group (default: same as source) |
| `--gen-test`         | Also generate a test for the copy           |
| `--project-dir PATH` | Project root                                |
| `--yes / -y`         | Skip confirmation                           |

All occurrences of `SrcName` in the header are replaced with `DstName` using whole-word substitution. Cross-group copies update the namespace.

---

## mv

Move a block (header, test, build entries) from one group to another.

```bash
gr4_modtool mv [BLOCK_NAME] [OPTIONS]
```

| Option               | Description       |
| -------------------- | ----------------- |
| `--from TEXT`        | Source group      |
| `--to TEXT`          | Destination group |
| `--project-dir PATH` | Project root      |
| `--yes / -y`         | Skip confirmation |

Updates namespace references in the header, `#include` paths in the test file, and removes/adds CMake entries in groups.

---

## rename

Rename a block everywhere using whole-word substitution.

```bash
gr4_modtool rename [OLD_NAME] [NEW_NAME] [OPTIONS]
```

| Option               | Description                |
| -------------------- | -------------------------- |
| `--group TEXT`       | Group containing the block |
| `--project-dir PATH` | Project root               |
| `--yes / -y`         | Skip confirmation          |

Renames: the header file, all symbol occurrences inside it (using `\bOldName\b` regex), the test file and its include, and CMake entries. Searches across all groups if `--group` is omitted.

---

## rename-block

Rename a block within its group.

```bash
gr4_modtool rename-block OLD_NAME NEW_NAME [OPTIONS]
```

| Option               | Description                                           |
| -------------------- | ----------------------------------------------------- |
| `--group TEXT`       | Group containing the block (auto-detected if omitted) |
| `--project-dir PATH` | Project root                                          |
| `--yes / -y`         | Skip confirmation                                     |

Renames the header file and replaces every occurrence of the old name inside it (`struct`, `Block<>`, `GR_MAKE_REFLECTABLE`, `GR_REGISTER_BLOCK`). Also renames the test file and updates its `#include`, suite variable names, and namespace references, and then patches `CMakeLists.txt` .

If `--group` is omitted and the block exists in exactly one group, that group is used automatically. An error is raised if the block appears in multiple groups.

```bash
# explicit group
gr4_modtool rename-block LowPass BandPass --group dsp --yes

# auto-detect group
gr4_modtool rename-block LowPass BandPass --yes
```

---

## rename-group

Rename a block group and update all references.

```bash
gr4_modtool rename-group OLD_NAME NEW_NAME [OPTIONS]
```

| Option               | Description       |
| -------------------- | ----------------- |
| `--project-dir PATH` | Project root      |
| `--yes / -y`         | Skip confirmation |

Performs the full rename cascade:

1. Moves `blocks/<old>/` → `blocks/<new>/`
2. Renames the include subdirectory (`include/<prefix>/<old>/` → `/<new>/`)
3. Updates `namespace ::<old>` → `::<new>` and `/<old>/` → `/<new>/` in all `.hpp` headers and `qa_*.cpp` test files
4. Rewrites CMake target names (`blocks_<old>_headers` → `blocks_<new>_headers`) in the group's own `CMakeLists.txt`
5. Updates `add_subdirectory(<old>)` → `add_subdirectory(<new>)` in `blocks/CMakeLists.txt`
6. Updates the group entry in `.gr4modtool.toml`

Group names must be `snake_case`. The new name must not already exist.

```bash
gr4_modtool rename-group basic dsp --yes
```

---

## rm

Remove a block and all its associated files.

```bash
gr4_modtool rm [BLOCK_NAME] [OPTIONS]
```

| Option               | Description                |
| -------------------- | -------------------------- |
| `--group TEXT`       | Group containing the block |
| `--project-dir PATH` | Project root               |
| `--yes / -y`         | Skip confirmation          |

Deletes the header, test source (if present), and removes CMake entries.

---

## export-spec

Scan an existing project's block headers and emit YAML spec files compatible with `newblock --spec`.

```bash
gr4_modtool export-spec [OPTIONS]
```

| Option                                     | Description                                        |
| ------------------------------------------ | -------------------------------------------------- |
| `--group TEXT`                             | Export only blocks from this group                 |
| `--output [per-block\|per-group\|project]` | Granularity of output files (default: `per-group`) |
| `--out-dir PATH`                           | Directory to write spec files (default: `specs/`)  |
| `--project-dir PATH`                       | Project root                                       |

### Output modes

| Mode        | Files written                                                |
| ----------- | ------------------------------------------------------------ |
| `per-group` | One `<group>_blocks.yaml` per group                          |
| `per-block` | One `<BlockName>.yaml` per block, under `<out-dir>/<group>/` |
| `project`   | Single `blocks.yaml` containing all blocks as a flat list    |

When the ports and processing style of a block exactly match a known archetype (`filter`, `source`, `sink`, `decimator`, `interpolator`), the YAML entry uses the `archetype:` shorthand instead of listing ports explicitly.

Headers that cannot be parsed as GNURadio 4 blocks are skipped with a warning.

### Example workflow

```bash
# Default: one YAML per group written to specs/
gr4_modtool export-spec

# Export only the dsp group
gr4_modtool export-spec --group dsp

# One file per block
gr4_modtool export-spec --output per-block --out-dir docs/specs

# Single file covering the whole project
gr4_modtool export-spec --output project --out-dir .

# Roundtrip: export then regenerate into a new module
gr4_modtool export-spec --output project
gr4_modtool newblock --spec specs/blocks.yaml --project-dir ../new_module
```

Requires `PyYAML` (`pip install PyYAML`).
