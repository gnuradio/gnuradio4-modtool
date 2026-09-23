# Developer Environment

## vscode

Write `.vscode/settings.json` and `.vscode/launch.json` for the project.

```bash
gr4_modtool vscode [OPTIONS]
```

| Option | Description |
|---|---|
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

**`settings.json`** configures:

- `cmake.buildDirectory` pointing at `${workspaceFolder}/build`
- `clangd.arguments` with `--compile-commands-dir=build` for accurate symbol resolution
- `editor.formatOnSave` with `clangd` as the C++ formatter

**`launch.json`** adds a `C++ (GDB)` debug configuration with a `promptString` input so you can pick the test binary to debug without editing the file.

Running the command again is safe: files are merged rather than overwritten, so any manual edits are preserved.

---

## devcontainer

Write a `.devcontainer/` directory with a Dockerfile and `devcontainer.json`.

```bash
gr4_modtool devcontainer [OPTIONS]
```

| Option | Description |
|---|---|
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

Creates:

```
.devcontainer/
├── devcontainer.json    # VS Code / GitHub Codespaces config
└── Dockerfile           # Ubuntu-based image with GNURadio 4 dependencies
```

The Dockerfile installs: `cmake`, `ninja-build`, `clang`, `clang-tidy`, `clang-format`, `libfmt-dev`, `python3-pip`, and `gr4_modtool` itself.

---

## completion

Print the shell completion setup line for bash, zsh, or fish.

```bash
gr4_modtool completion --shell SHELL
```

| Option | Description |
|---|---|
| `--shell TEXT` | One of `bash`, `zsh`, `fish` (required) |
| `--print-script` | Emit the full completion script (pipe to a file) |

**Setup (one-time):**

```bash
# bash — add to ~/.bashrc
eval "$(_GR4_MODTOOL_COMPLETE=bash_source gr4_modtool)"

# zsh — add to ~/.zshrc
eval "$(_GR4_MODTOOL_COMPLETE=zsh_source gr4_modtool)"

# fish — add to ~/.config/fish/config.fish
_GR4_MODTOOL_COMPLETE=fish_source gr4_modtool | source
```

Run `gr4_modtool completion --shell bash` to print the correct line for your shell without having to remember the syntax.

To install the script to a file (e.g. for system-wide completions):

```bash
gr4_modtool completion --shell bash --print-script > /etc/bash_completion.d/gr4_modtool
```

---

## templates

Manage project-local Jinja2 template overrides.

```bash
gr4_modtool templates SUBCOMMAND
```

Override any built-in template by copying it into `.gr4modtool/templates/` and editing it. Commands that generate files (e.g. `newblock`, `add-test`) will use your override automatically.

### templates list

```bash
gr4_modtool templates list [--project-dir PATH]
```

List all built-in templates and show which ones have project-local overrides.

```
Template                         Status
block.hpp.j2                     built-in
qa_block.cpp.j2                  overridden
test_cmake.build.j2              built-in
```

### templates init

```bash
gr4_modtool templates init TEMPLATE_NAME [--force] [--project-dir PATH]
```

Copy a built-in template into `.gr4modtool/templates/` for editing. Prints the Jinja2 context variables available in that template after copying.

```bash
gr4_modtool templates init block.hpp.j2
# Copied block.hpp.j2 → .gr4modtool/templates/block.hpp.j2
#
# Context variables:
#   block_name        str    Block class name (CamelCase)
#   description       str    Doc<"..."> string
#   ...
```

Use `--force` to overwrite an existing override.

### templates check

```bash
gr4_modtool templates check [--project-dir PATH]
```

Render all override templates with dummy context to catch Jinja2 syntax errors before they surface during block generation.

```
Checking 2 override template(s)...
  block.hpp.j2                             OK
  qa_block.cpp.j2                          ERROR: 'block_name' is undefined
```

Exit code 1 if any template fails to render.
