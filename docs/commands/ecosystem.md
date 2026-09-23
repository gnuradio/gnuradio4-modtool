# Documentation, Dependencies, Registry & Migration

## search

Search GitHub for published GNURadio 4 OOT modules.

```bash
gr4_modtool search [QUERY] [OPTIONS]
```

| Option | Description |
|---|---|
| `QUERY` | Optional keyword to narrow results (searches repo name and description) |
| `--topic TEXT` | GitHub topic tag to filter by (default: `gnuradio4-oot`) |
| `--limit N` | Maximum results to display (default: 20) |
| `--verbose / -v` | Include the full repository URL in the output |
| `--token TEXT` | GitHub personal access token (env: `GR4_MODTOOL_GITHUB_TOKEN`) |
| `--no-cache` | Bypass the one-hour local result cache |

### Discovery convention

Modules are discovered via GitHub's topic search. To make your module discoverable, add the `gnuradio4-oot` topic to your GitHub repository (Settings → Topics).

### Examples

```bash
# All published gr4 OOT modules, sorted by stars
gr4_modtool search

# Narrow to DSP-related modules
gr4_modtool search dsp

# Show full repository URLs
gr4_modtool search --verbose

# Authenticated request (higher GitHub rate limit: 30 → 5000 req/hour)
export GR4_MODTOOL_GITHUB_TOKEN=ghp_...
gr4_modtool search

# Refresh stale cached results
gr4_modtool search --no-cache
```

### Output

```
Repository                   Stars  Description                         Updated
alice/gr4-dsp-blocks            42  DSP blocks for GNURadio 4           2024-01-15
bob/gr4-channel-models           7  Channel simulation blocks           2024-02-01
```

### Caching

Results are cached in `~/.cache/gr4_modtool/search/` for one hour. Each unique (query, topic) pair has its own cache file. Use `--no-cache` to force a fresh fetch without waiting for expiry.

### Rate limits

Without a token, GitHub's search API allows 10 requests per minute. With a token, the limit is 5 000 per hour. Use `GR4_MODTOOL_GITHUB_TOKEN` for automated workflows or frequent searches.

---

## docs

Write a `Doxyfile` for the project, or print a Markdown block catalog.

```bash
gr4_modtool docs [OPTIONS]
```

| Option | Description |
|---|---|
| `--catalog` | Print a Markdown block catalog to stdout instead of writing a Doxyfile |
| `--output PATH` | Write catalog output to a file (default: stdout) |
| `--project-dir PATH` | Project root |

### Doxyfile

Without `--catalog`, writes a `Doxyfile` at the project root configured for the project's include directory:

```bash
gr4_modtool docs
doxygen Doxyfile   # generates docs/html/
```

Key settings: `INPUT = include/`, `RECURSIVE = YES`, `FILE_PATTERNS = *.hpp`, `GENERATE_HTML = YES`, `EXTRACT_ALL = YES`, `JAVADOC_AUTOBRIEF = YES`.

### Block catalog

With `--catalog`, scans all groups and prints a Markdown table of every block with its ports, processing style, and parameters:

```bash
gr4_modtool docs --catalog
gr4_modtool docs --catalog --output CATALOG.md
```

Example output:

```markdown
# Block Catalog — myfilters

| Group | Block | Ports In | Ports Out | Style | Parameters |
|---|---|---|---|---|---|
| dsp | LowPassFilter | in:T | out:T | processOne | cutoff_freq:float |
| dsp | HighPassFilter | in:T | out:T | processOne | cutoff_freq:float |
```

---

## add-dep

Add a library dependency to `cmake/Dependencies.cmake`.

```bash
gr4_modtool add-dep VAR_NAME [OPTIONS]
```

| Argument / Option | Description |
|---|---|
| `VAR_NAME` | CMake variable name for the dependency (e.g. `FFTW3`) |
| `--pkg-config TEXT` | pkg-config package name (e.g. `fftw3`) |
| `--cmake-package TEXT` | CMake find_package name (e.g. `FFTW3`) |
| `--project-dir PATH` | Project root |

At least one of `--pkg-config` or `--cmake-package` is required.

**pkg-config example:**

```bash
gr4_modtool add-dep FFTW3 --pkg-config fftw3
```

Inserts into `cmake/Dependencies.cmake`:

```cmake
pkg_check_modules(FFTW3 REQUIRED IMPORTED_TARGET fftw3)
set(FFTW3_TARGET PkgConfig::FFTW3 PARENT_SCOPE)
```

**CMake find_package example:**

```bash
gr4_modtool add-dep LiquidDSP --cmake-package liquid
```

Inserts:

```cmake
find_package(liquid REQUIRED)
set(LiquidDSP_TARGET liquid::liquid PARENT_SCOPE)
```

The command raises an error if `VAR_NAME` already appears in the file.

---

## port

Parse a GNURadio 3.x Python block file and scaffold a gr4 header and test.

```bash
gr4_modtool port SOURCE_FILE [OPTIONS]
```

| Option | Description |
|---|---|
| `--group TEXT` | Target group for the new block |
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

### What gets detected

The command uses Python's `ast` module to parse the source file:

| GR3 source | GR4 output |
|---|---|
| `gr.sync_block` | `processOne`, 1 in / 1 out (filter archetype) |
| `gr.decim_block` | `processBulk`, 1 in / 1 out (decimator archetype) |
| `gr.interp_block` | `processBulk`, 1 in / 1 out (interpolator archetype) |
| `gr.basic_block` | `processOne`, 1 in / 1 out (custom) |
| `in_sig=[np.float32]` | `type_list = float` |
| `in_sig=[np.complex64]` | `type_list = std::complex<float>` |
| `__init__` parameters | `Annotated<float, "name", Doc<"...">>` fields |
| Class docstring | Block `Doc<"...">` description |

### Type mapping

| NumPy type | C++ type |
|---|---|
| `np.float32` | `float` |
| `np.float64` | `double` |
| `np.complex64` | `std::complex<float>` |
| `np.complex128` | `std::complex<double>` |
| `np.int32` | `int32_t` |
| `np.int64` | `int64_t` |
| `np.uint8` | `uint8_t` |
| `np.uint32` | `uint32_t` |

### Limitations

- Only Python block files are supported — C++ GR3 blocks (`.cc`/`.h`) must be ported manually.
- Only the **first** `gr.*_block` class in a file is detected.
- The `processOne`/`processBulk` body is always a stub — the algorithm logic must be filled in.
- GRC flow graphs (`.grc`) are not translated.

### Example

```bash
gr4_modtool port ~/old_module/python/my_fir.py --group dsp --yes
# Created:
#   blocks/dsp/include/gnuradio-4.0/dsp/MyFir.hpp
#   blocks/dsp/test/qa_MyFir.cpp
#   (update) blocks/dsp/test/CMakeLists.txt
```

Then open `MyFir.hpp` and fill in the `processOne` body with the ported algorithm.
