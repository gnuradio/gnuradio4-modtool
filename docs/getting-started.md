# Getting Started

This guide walks through the most common workflows from scratch.

## 1. Create a new OOT project

```bash
gr4_modtool newmod --name myfilters
cd myfilters
```

This creates:

```
myfilters/
├── .gr4modtool.toml
├── CMakeLists.txt
└── blocks/
    └── CMakeLists.txt
```

## 2. Add a block group

Blocks are organised into groups (e.g., `dsp`, `channel`, `measure`).

```bash
gr4_modtool newgroup --name dsp
```

## 3. Add a block

```bash
gr4_modtool newblock --group dsp
```

You'll be prompted for:

- **Block name** — CamelCase, e.g. `LowPassFilter`
- **Description** — one-line docstring
- **Template parameters** — e.g. `T` or `TIN, TOUT`
- **Input ports** — name and C++ type per port
- **Output ports** — name and C++ type per port
- **Processing style** — `processOne` or `processBulk`
- **Type list** — instantiation types, e.g. `float, double`
- **Generate test?** — yes/no

This writes `blocks/dsp/include/gnuradio-4.0/dsp/LowPassFilter.hpp` and (optionally) `blocks/dsp/test/qa_LowPassFilter.cpp`, and updates both CMakeLists.txt.

## 4. Add a parameter to a block

```bash
gr4_modtool newparam LowPassFilter cutoff_freq --group dsp \
    --type float --description "Cutoff frequency in Hz" --default "1000.0f"
```

This inserts:

```cpp
Annotated<float, "cutoff_freq", Doc<"Cutoff frequency in Hz">> cutoff_freq{1000.0f};
```

into the block struct and adds `cutoff_freq` to `GR_MAKE_REFLECTABLE`.

## 5. Check project health

```bash
gr4_modtool check
```

Reports any headers missing a test, test sources missing a CMake entry, CMake entries with no source file, or blocks missing `GR_REGISTER_BLOCK`.

For scripting or CI:

```bash
gr4_modtool check --json | jq '.error_count'
```

## 6. Build and test

```bash
gr4_modtool build --test
```

Or to re-run just one block's test after it's already built:

```bash
gr4_modtool test LowPassFilter
```

## 7. Adopt an existing project

If you have an existing GNURadio 4 OOT project without a `.gr4modtool.toml`:

```bash
cd /path/to/existing/project
gr4_modtool init --yes
```

gr4_modtool will scan the directory tree, detect groups, and write the config file.
