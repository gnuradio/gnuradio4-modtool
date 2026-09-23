#!/usr/bin/env bash
# tour.sh — a guided tour of the gr4_modtool CLI.
#
# Creates a new OOT module in a scratch directory, adds blocks from a spec
# file, then exercises the block-lifecycle and project-health commands.
# Every gr4_modtool invocation is echoed before it runs, so the script reads
# as a transcript of a working session. Non-interactive throughout.
#
# This is a demo, not a test — for the assertion-based integration test see
# smoke_test.sh at the repository root.
#
# Usage:
#   ./tour.sh                 # work in a temp dir, clean up afterwards
#   ./tour.sh /tmp/gr4_demo   # work (and leave the project) there

set -euo pipefail

command -v gr4_modtool >/dev/null || {
  echo "gr4_modtool not found on PATH — install it first: pip install -e ." >&2
  exit 1
}

if [[ $# -ge 1 ]]; then
  WORKDIR="$1"
  mkdir -p "$WORKDIR"
  CLEANUP=0
else
  WORKDIR="$(mktemp -d -t gr4_cli_tour_XXXXXX)"
  CLEANUP=1
  trap 'rm -rf "$WORKDIR"' EXIT
fi

say() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
run() { printf '\033[36m$ %s\033[0m\n' "$*"; "$@"; }

cd "$WORKDIR"

# ---------------------------------------------------------------------------
say "Scaffold a new module with one group (newmod)"
# ---------------------------------------------------------------------------
run gr4_modtool newmod --name gr4_demo --first-group dsp --yes
cd gr4_demo

# ---------------------------------------------------------------------------
say "Add blocks from a YAML spec (newblock --spec)"
# ---------------------------------------------------------------------------
cat > /tmp/tour_blocks.yaml <<'EOF'
- block_name: Gain
  group: dsp
  description: Multiplies samples by a constant.
  archetype: sync
- block_name: NoiseSource
  group: dsp
  description: Emits uniform noise.
  archetype: source
  gen_test: false
- block_name: Decimator
  group: dsp
  description: Keeps every Nth sample.
  archetype: decimator
EOF
run gr4_modtool newblock --spec /tmp/tour_blocks.yaml
rm -f /tmp/tour_blocks.yaml

# ---------------------------------------------------------------------------
say "Evolve the blocks (newparam, add-test, newbench)"
# ---------------------------------------------------------------------------
run gr4_modtool newparam Gain gain --group dsp --type float \
  --description "Gain factor" --default "1.0f" --yes
run gr4_modtool add-test NoiseSource --group dsp --yes
run gr4_modtool newbench Gain --group dsp --wire-build --yes

# ---------------------------------------------------------------------------
say "Block lifecycle (newgroup, cp, mv, rename, rm)"
# ---------------------------------------------------------------------------
run gr4_modtool newgroup --name filters
run gr4_modtool cp Gain Attenuator --from-group dsp --to-group filters --gen-test --yes
run gr4_modtool rename Attenuator Pad --group filters --yes
run gr4_modtool cp Gain Gain2 --from-group dsp --to-group dsp --yes
run gr4_modtool mv Gain2 --from dsp --to filters --yes
run gr4_modtool rm Gain2 --group filters --yes

# ---------------------------------------------------------------------------
say "Inspect the project (info, ls, status, show)"
# ---------------------------------------------------------------------------
run gr4_modtool info
run gr4_modtool ls --format json
run gr4_modtool status
run gr4_modtool show Gain --group dsp

# ---------------------------------------------------------------------------
say "Health checks (check, validate, lint-headers, sync, doctor)"
# ---------------------------------------------------------------------------
run gr4_modtool check
run gr4_modtool validate
run gr4_modtool lint-headers
run gr4_modtool sync --yes
run gr4_modtool doctor || true # informational; exit code reflects the host env

# ---------------------------------------------------------------------------
say "Docs, specs, and versioning (docs, export-spec, version-bump)"
# ---------------------------------------------------------------------------
run gr4_modtool docs --catalog
run gr4_modtool export-spec --output project --out-dir specs
run gr4_modtool version-bump --minor --yes

# ---------------------------------------------------------------------------
say "Compile and run the generated tests (build --test)"
# ---------------------------------------------------------------------------
# Only possible where GNURadio 4 is installed (e.g. inside the repository's
# devcontainer) and a C++23 compiler is available. Elsewhere the tour ends
# here with everything generated.
cxx23_compiler() {
  # First compiler (newest first) whose stdlib has C++23 <print>.
  for c in c++ g++-16 g++-15 g++-14 clang++-19 clang++-18; do
    command -v "$c" > /dev/null || continue
    if printf '#include <print>\nint main(){}\n' |
      "$c" -std=c++23 -fsyntax-only -x c++ - 2>/dev/null; then
      echo "$c"
      return 0
    fi
  done
  return 1
}

if ! pkg-config --exists gnuradio4 2>/dev/null; then
  echo "gnuradio4 not found via pkg-config — skipping the compile step."
elif ! CXX23="$(cxx23_compiler)"; then
  echo "no C++23-capable compiler found — skipping the compile step."
elif [[ "$CXX23" == "c++" ]]; then
  run gr4_modtool build --test
else
  echo "(default c++ lacks C++23 <print>; using $CXX23)"
  run gr4_modtool build --test --cmake-args "-DCMAKE_CXX_COMPILER=$(command -v "$CXX23")"
fi

say "Done"
echo "Project root: $WORKDIR/gr4_demo"
if [[ $CLEANUP -eq 1 ]]; then
  echo "(temp dir — will be removed on exit; pass a directory to keep it)"
else
  echo "Build it with: cd $WORKDIR/gr4_demo && cmake -B build && cmake --build build"
fi
