# Scaffolding

## newmod

Scaffold a complete GNURadio 4 OOT project.

```bash
gr4_modtool newmod [OPTIONS]
```

| Option             | Description                           |
| ------------------ | ------------------------------------- |
| `--name TEXT`      | Module name (snake_case)              |
| `--version TEXT`   | Initial version (default: `0.1.0`)    |
| `--namespace TEXT` | C++ namespace (default: `gr::<name>`) |
| `--yes / -y`       | Skip confirmation prompts             |

**What it creates:**

```
<name>/
├── .gr4modtool.toml      # tool configuration
├── CMakeLists.txt
└── blocks/
    ├── CMakeLists.txt
```

---

## newgroup

Add a block group directory to an existing project.

```bash
gr4_modtool newgroup [OPTIONS]
```

| Option               | Description                         |
| -------------------- | ----------------------------------- |
| `--name TEXT`        | Group name (snake_case)             |
| `--project-dir PATH` | Project root (default: auto-detect) |
| `--yes / -y`         | Skip confirmation                   |

**What it creates:**

```
blocks/<name>/
├── CMakeLists.txt
├── include/gnuradio-4.0/<name>/   # block headers go here
└── test/
    ├── CMakeLists.txt
```

It also updates `blocks/CMakeLists.txt` to include the new group.

---

## Flat-project mode

Flat mode is a groupless layout where all blocks live directly under a single `blocks/` directory with no group subdirectory. It is suitable for small modules that don't need the overhead of named groups.

### Enabling flat mode

When `newmod` asks for the name of the first block group, leave the prompt blank:

```
Name of first block group (leave blank to skip): <press Enter>
```

This sets `flat = true` in `.gr4modtool.toml` and generates a flat block directory structure:

```
<name>/
├── .gr4modtool.toml          # flat = true
├── CMakeLists.txt
└── blocks/
    ├── CMakeLists.txt
    ├── include/
    │   └── gnuradio-4.0/     # block headers go here
    └── test/
        ├── CMakeLists.txt
```

In a flat project, block headers are placed at `blocks/include/<gr4_prefix>/<Name>.hpp` instead of the grouped path `blocks/<group>/include/<gr4_prefix>/<group>/<Name>.hpp`.

### Command behaviour in flat mode

All block-lifecycle commands work identically in flat mode. The `--group` option is silently ignored where it is not applicable; commands that normally show a Group column (e.g. `info`, `status`) suppress it.

`newgroup` is not meaningful in a flat project and will exit with an error if called.

### Converting to grouped mode

Set `flat = false` in `.gr4modtool.toml` and add at least one group under `[groups]`, then run `gr4_modtool sync` to wire up the build entries.
