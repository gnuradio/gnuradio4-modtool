# Installation

## Requirements

- Python 3.11 or later
- pip

Optional (for specific commands):

- `clang-format` — required by `gr4_modtool format`
- `cmake` — required by `gr4_modtool build` and `gr4_modtool test`

## From PyPI

```bash
pip install gr4_modtool
```

## From source

```bash
git clone https://github.com/gnuradio/gnuradio4-modtool
cd gr4_modtool
pip install -e ".[dev]"
```

The `-e` flag installs in editable mode, so changes to the source take effect immediately.

## Verify the installation

```bash
gr4_modtool --version
gr4_modtool --help
```

## Shell completion

gr4_modtool uses Click, which supports tab completion for bash, zsh, and fish.

```bash
# bash
eval "$(_GR4_MODTOOL_COMPLETE=bash_source gr4_modtool)"

# zsh
eval "$(_GR4_MODTOOL_COMPLETE=zsh_source gr4_modtool)"

# fish
_GR4_MODTOOL_COMPLETE=fish_source gr4_modtool | source
```

Add the appropriate line to your shell's startup file (`.bashrc`, `.zshrc`, `~/.config/fish/completions/gr4_modtool.fish`) to make completion persistent.
