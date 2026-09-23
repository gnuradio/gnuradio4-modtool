#!/usr/bin/env bash
# smoke_test.sh — end-to-end integration test for gr4_modtool
#
# Exercises: project scaffolding, block creation (filter/source/sink/decimator),
# status, info, check, show, newparam, add-test, newgroup, cp, rename, mv, rm.
#
# Usage:
#   ./smoke_test.sh           # terse pass/fail
#   ./smoke_test.sh --verbose # show command output

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GR4MT="${SCRIPT_DIR}/.venv/bin/gr4_modtool"
PY="${SCRIPT_DIR}/.venv/bin/python"

VERBOSE=0
[[ "${1:-}" == "--verbose" ]] && VERBOSE=1

if [[ ! -x "$GR4MT" ]]; then
  echo "ERROR: $GR4MT not found — run 'pip install -e .' inside the .venv first." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS=0
FAIL=0

_green() { printf '\033[32m%s\033[0m' "$*"; }
_red() { printf '\033[31m%s\033[0m' "$*"; }

pass() {
  printf "  %s  %s\n" "$(_green PASS)" "$1"
  ((PASS++)) || true
}
fail() {
  printf "  %s  %s\n" "$(_red FAIL)" "$1"
  ((FAIL++)) || true
}

run_gr4() {
  # Run gr4_modtool and capture output; show it only in verbose mode.
  local out
  out=$("$GR4MT" "$@" 2>&1) || {
    fail "gr4_modtool $*"
    return 1
  }
  [[ $VERBOSE -eq 1 ]] && echo "$out"
  echo "$out" # still returned for caller checks
}

check_exit() {
  local desc="$1"
  shift
  local out
  if out=$("$GR4MT" "$@" 2>&1); then
    pass "$desc"
    [[ $VERBOSE -eq 1 ]] && echo "$out" || true
  else
    fail "$desc"
    echo "$out"
  fi
}

check_file_exists() {
  local desc="$1" file="$2"
  [[ -f "$file" ]] && pass "$desc" || fail "$desc (missing: $file)"
}

check_no_file() {
  local desc="$1" file="$2"
  [[ ! -f "$file" ]] && pass "$desc" || fail "$desc (still exists: $file)"
}

check_file_contains() {
  local desc="$1" file="$2" pattern="$3"
  if grep -qF "$pattern" "$file" 2>/dev/null; then
    pass "$desc"
  else
    fail "$desc  [$pattern not found in $(basename "$file")]"
  fi
}

check_file_not_contains() {
  local desc="$1" file="$2" pattern="$3"
  if ! grep -qF "$pattern" "$file" 2>/dev/null; then
    pass "$desc"
  else
    fail "$desc  [$pattern still in $(basename "$file")]"
  fi
}

check_output_contains() {
  local desc="$1" pattern="$2" output="$3"
  if echo "$output" | grep -qF "$pattern"; then
    pass "$desc"
  else
    fail "$desc  ['$pattern' not in output]"
  fi
}

# ---------------------------------------------------------------------------
# Temporary project directory
# ---------------------------------------------------------------------------

PROJ=$(mktemp -d)
trap 'rm -rf "$PROJ"' EXIT

DSP_INC="$PROJ/blocks/dsp/include/gnuradio-4.0/dsp"
DSP_TEST="$PROJ/blocks/dsp/test"
SIG_INC="$PROJ/blocks/signal/include/gnuradio-4.0/signal"

echo ""
echo "=== gr4_modtool smoke test ==="
echo "Project: $PROJ"
echo ""

# ===========================================================================
# 1. Bootstrap project (Python API — newmod is interactive)
# ===========================================================================
echo "--- 1. Create project ---"

"$PY" - "$PROJ" <<'PYEOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent) if hasattr(__file__, '__file__') else '.')

proj = Path(sys.argv[1])
import importlib.util, os
# ensure the installed package is used
from gr4_modtool.project.discovery import ProjectConfig
from gr4_modtool.commands.newmod import _write_project

cfg = ProjectConfig(
    root=proj,
    name='mymod',
    version='0.1.0',
    cpp_namespace='gr::mymod',
    cmake_prefix='gr4_mymod',
    gr4_include_prefix='gnuradio-4.0',
    build_cmake=True,
    groups={'dsp': 'blocks/dsp'},
)
_write_project(cfg, 'dsp')
PYEOF

check_file_exists "CMakeLists.txt created" "$PROJ/CMakeLists.txt"
check_file_exists ".gr4modtool.toml created" "$PROJ/.gr4modtool.toml"
check_file_exists "cmake/Dependencies.cmake" "$PROJ/cmake/Dependencies.cmake"
check_file_exists "blocks/dsp scaffold" "$PROJ/blocks/dsp/CMakeLists.txt"
check_file_exists "blocks/dsp/test scaffold" "$DSP_TEST/CMakeLists.txt"

# ===========================================================================
# 2. Create blocks (Python API — newblock is interactive)
# ===========================================================================
echo ""
echo "--- 2. Create blocks ---"

"$PY" - "$PROJ" <<'PYEOF'
import sys
from pathlib import Path
sys.path.insert(0, '.')
from gr4_modtool.project.discovery import load_config
from gr4_modtool.commands.newblock import write_block_files

cfg = load_config(Path(sys.argv[1]))

# filter — processOne, 1-in 1-out
write_block_files(cfg, {
    'group_name': 'dsp',
    'block_name': 'GainBlock',
    'description': 'Multiplies each sample by a gain scalar.',
    'template_params': ['T'],
    'in_ports': [{'name': 'in', 'type': 'T'}],
    'out_ports': [{'name': 'out', 'type': 'T'}],
    'processing_style': 'processOne',
    'type_list': 'float, double',
    'gen_test': True,
})

# source — processBulk, no inputs
write_block_files(cfg, {
    'group_name': 'dsp',
    'block_name': 'ConstSource',
    'description': 'Emits a constant value on each output sample.',
    'template_params': ['T'],
    'in_ports': [],
    'out_ports': [{'name': 'out', 'type': 'T'}],
    'processing_style': 'processBulk',
    'type_list': 'float, double',
    'gen_test': True,
})

# sink — processBulk, no outputs
write_block_files(cfg, {
    'group_name': 'dsp',
    'block_name': 'NullSink',
    'description': 'Discards all incoming samples.',
    'template_params': ['T'],
    'in_ports': [{'name': 'in', 'type': 'T'}],
    'out_ports': [],
    'processing_style': 'processBulk',
    'type_list': 'float, double',
    'gen_test': True,
})

# decimator — processBulk, multiple template params
write_block_files(cfg, {
    'group_name': 'dsp',
    'block_name': 'Decimator',
    'description': 'Down-samples by an integer factor.',
    'template_params': ['T'],
    'in_ports': [{'name': 'in', 'type': 'T'}],
    'out_ports': [{'name': 'out', 'type': 'T'}],
    'processing_style': 'processBulk',
    'type_list': 'float, double',
    'gen_test': True,
})

# block without test (to exercise add-test later)
write_block_files(cfg, {
    'group_name': 'dsp',
    'block_name': 'BareBlock',
    'description': 'Minimal block created without a test.',
    'template_params': ['T'],
    'in_ports': [{'name': 'in', 'type': 'T'}],
    'out_ports': [{'name': 'out', 'type': 'T'}],
    'processing_style': 'processOne',
    'type_list': 'float',
    'gen_test': False,
})
PYEOF

# Verify headers
check_file_exists "GainBlock.hpp" "$DSP_INC/GainBlock.hpp"
check_file_exists "ConstSource.hpp" "$DSP_INC/ConstSource.hpp"
check_file_exists "NullSink.hpp" "$DSP_INC/NullSink.hpp"
check_file_exists "Decimator.hpp" "$DSP_INC/Decimator.hpp"
check_file_exists "BareBlock.hpp" "$DSP_INC/BareBlock.hpp"

# Verify header content
check_file_contains "GainBlock has GR_REGISTER_BLOCK" "$DSP_INC/GainBlock.hpp" "GR_REGISTER_BLOCK"
check_file_contains "GainBlock has GR_MAKE_REFLECTABLE" "$DSP_INC/GainBlock.hpp" "GR_MAKE_REFLECTABLE"
check_file_contains "GainBlock uses processOne" "$DSP_INC/GainBlock.hpp" "processOne"
check_file_contains "GainBlock has PortIn" "$DSP_INC/GainBlock.hpp" "PortIn<T>"
check_file_contains "GainBlock has PortOut" "$DSP_INC/GainBlock.hpp" "PortOut<T>"
check_file_contains "ConstSource has no PortIn" "$DSP_INC/ConstSource.hpp" "PortOut<T>"
check_file_contains "ConstSource uses processBulk" "$DSP_INC/ConstSource.hpp" "processBulk"
check_file_contains "NullSink has no PortOut" "$DSP_INC/NullSink.hpp" "PortIn<T>"
check_file_contains "NullSink uses processBulk" "$DSP_INC/NullSink.hpp" "processBulk"

# Verify tests and build files
check_file_exists "qa_GainBlock.cpp" "$DSP_TEST/qa_GainBlock.cpp"
check_file_exists "qa_ConstSource.cpp" "$DSP_TEST/qa_ConstSource.cpp"
check_file_exists "qa_NullSink.cpp" "$DSP_TEST/qa_NullSink.cpp"
check_file_exists "qa_Decimator.cpp" "$DSP_TEST/qa_Decimator.cpp"
check_no_file "BareBlock has no test yet" "$DSP_TEST/qa_BareBlock.cpp"

check_file_contains "test CMakeLists has qa_GainBlock" "$DSP_TEST/CMakeLists.txt" "qa_GainBlock"
check_file_contains "test CMakeLists has qa_ConstSource" "$DSP_TEST/CMakeLists.txt" "qa_ConstSource"
check_file_contains "test CMakeLists has qa_NullSink" "$DSP_TEST/CMakeLists.txt" "qa_NullSink"
check_file_contains "test CMakeLists has qa_Decimator" "$DSP_TEST/CMakeLists.txt" "qa_Decimator"

check_file_contains "qa_GainBlock includes header" \
  "$DSP_TEST/qa_GainBlock.cpp" "GainBlock.hpp"
check_file_contains "qa_GainBlock has boost::ut suite" \
  "$DSP_TEST/qa_GainBlock.cpp" "boost::ut::suite"

# ===========================================================================
# 3. status
# ===========================================================================
echo ""
echo "--- 3. status ---"

STATUS=$(run_gr4 status --project-dir "$PROJ")
check_output_contains "status: project name" "mymod" "$STATUS"
check_output_contains "status: group count" "1 group" "$STATUS"
check_output_contains "status: block count" "5 block" "$STATUS"
check_output_contains "status: dsp group row" "dsp" "$STATUS"
check_output_contains "status: cmake build" "cmake" "$STATUS"

# ===========================================================================
# 4. info
# ===========================================================================
echo ""
echo "--- 4. info ---"

INFO=$(run_gr4 info --project-dir "$PROJ")
check_output_contains "info: GainBlock listed" "GainBlock" "$INFO"
check_output_contains "info: ConstSource listed" "ConstSource" "$INFO"
check_output_contains "info: NullSink listed" "NullSink" "$INFO"
check_output_contains "info: Decimator listed" "Decimator" "$INFO"
check_output_contains "info: BareBlock listed" "BareBlock" "$INFO"

INFO_JSON=$(run_gr4 info --json --project-dir "$PROJ")
check_output_contains "info --json: name field" '"name"' "$INFO_JSON"
check_output_contains "info --json: groups field" '"groups"' "$INFO_JSON"

INFO_V=$(run_gr4 info -v --project-dir "$PROJ")
check_output_contains "info -v: port in listed" "in:T" "$INFO_V"
check_output_contains "info -v: port out listed" "out:T" "$INFO_V"

# ===========================================================================
# 5. check — should report BareBlock missing test
# ===========================================================================
echo ""
echo "--- 5. check ---"

CHECK=$(run_gr4 check --project-dir "$PROJ" 2>&1 || true)
check_output_contains "check: flags missing test" "BareBlock" "$CHECK"

CHECK_JSON=$(run_gr4 check --json --project-dir "$PROJ" 2>&1 || true)
check_output_contains "check --json: issues array" '"issues"' "$CHECK_JSON"

# ===========================================================================
# 6. show
# ===========================================================================
echo ""
echo "--- 6. show ---"

SHOW=$(run_gr4 show GainBlock --group dsp --project-dir "$PROJ")
check_output_contains "show: struct name" "GainBlock" "$SHOW"
check_output_contains "show: GR_REGISTER_BLOCK" "GR_REGISTER_BLOCK" "$SHOW"
check_output_contains "show: PortIn" "PortIn" "$SHOW"

SHOW_TEST=$(run_gr4 show GainBlock --group dsp --test --project-dir "$PROJ")
check_output_contains "show --test: boost::ut" "boost::ut" "$SHOW_TEST"
check_output_contains "show --test: suite name" "GainBlock" "$SHOW_TEST"

# ===========================================================================
# 7. newparam
# ===========================================================================
echo ""
echo "--- 7. newparam ---"

check_exit "newparam: add gain_factor to GainBlock" \
  newparam GainBlock gain_factor \
  --group dsp \
  --type float \
  --description "Multiplicative gain applied to each sample" \
  --default "1.0f" \
  --yes \
  --project-dir "$PROJ"

check_file_contains "gain_factor appears in header" \
  "$DSP_INC/GainBlock.hpp" "gain_factor"
check_file_contains "Doc<> contains description" \
  "$DSP_INC/GainBlock.hpp" "Multiplicative gain applied to each sample"
check_file_contains "Annotated<float, ...> present" \
  "$DSP_INC/GainBlock.hpp" "Annotated<float"
check_file_contains "GR_MAKE_REFLECTABLE updated" \
  "$DSP_INC/GainBlock.hpp" "gain_factor"

check_exit "newparam: add factor to Decimator" \
  newparam Decimator decimation_factor \
  --group dsp \
  --type "uint32_t" \
  --description "Integer decimation factor" \
  --default "2U" \
  --yes \
  --project-dir "$PROJ"

check_file_contains "decimation_factor in Decimator" \
  "$DSP_INC/Decimator.hpp" "decimation_factor"

# ===========================================================================
# 8. add-test (BareBlock has no test yet)
# ===========================================================================
echo ""
echo "--- 8. add-test ---"

check_exit "add-test: generate test for BareBlock" \
  add-test BareBlock --group dsp --yes --project-dir "$PROJ"

check_file_exists "qa_BareBlock.cpp created" "$DSP_TEST/qa_BareBlock.cpp"
check_file_contains "CMakeLists updated with qa_BareBlock" \
  "$DSP_TEST/CMakeLists.txt" "qa_BareBlock"

CHECK2=$(run_gr4 check --project-dir "$PROJ" 2>&1 || true)
check_output_contains "check clean after add-test" "No issues found" "$CHECK2"

# ===========================================================================
# 9. newgroup
# ===========================================================================
echo ""
echo "--- 9. newgroup ---"

check_exit "newgroup: add 'signal' group" \
  newgroup --name signal --project-dir "$PROJ"

check_file_exists "signal/CMakeLists.txt" "$PROJ/blocks/signal/CMakeLists.txt"
check_file_exists "signal/test/CMakeLists.txt" "$PROJ/blocks/signal/test/CMakeLists.txt"
check_file_contains "blocks CMakeLists references signal" \
  "$PROJ/blocks/CMakeLists.txt" "signal"
check_file_contains ".gr4modtool.toml updated with signal" \
  "$PROJ/.gr4modtool.toml" "signal"

INFO2=$(run_gr4 info --project-dir "$PROJ")
check_output_contains "info: signal group appears" "signal" "$INFO2"

# ===========================================================================
# 10. cp
# ===========================================================================
echo ""
echo "--- 10. cp ---"

# Copy within the same group, generating a fresh test
check_exit "cp: GainBlock → GainBlock2 (same group)" \
  cp GainBlock GainBlock2 \
  --from-group dsp \
  --to-group dsp \
  --gen-test \
  --yes \
  --project-dir "$PROJ"

check_file_exists "GainBlock2.hpp created" "$DSP_INC/GainBlock2.hpp"
check_file_exists "qa_GainBlock2.cpp created" "$DSP_TEST/qa_GainBlock2.cpp"
check_file_contains "GainBlock2 struct renamed" "$DSP_INC/GainBlock2.hpp" "struct GainBlock2"
check_file_contains "GainBlock still exists" "$DSP_INC/GainBlock.hpp" "struct GainBlock"
check_file_contains "CMakeLists has qa_GainBlock2" "$DSP_TEST/CMakeLists.txt" "qa_GainBlock2"

# Copy to a different group
check_exit "cp: NullSink → SignalSink (dsp → signal)" \
  cp NullSink SignalSink \
  --from-group dsp \
  --to-group signal \
  --yes \
  --project-dir "$PROJ"

check_file_exists "SignalSink.hpp in signal" "$SIG_INC/SignalSink.hpp"
check_file_contains "SignalSink struct renamed" "$SIG_INC/SignalSink.hpp" "struct SignalSink"
check_file_contains "NullSink still in dsp" "$DSP_INC/NullSink.hpp" "struct NullSink"

# ===========================================================================
# 11. rename
# ===========================================================================
echo ""
echo "--- 11. rename ---"

check_exit "rename: GainBlock2 → AmplifierBlock" \
  rename GainBlock2 AmplifierBlock \
  --group dsp \
  --yes \
  --project-dir "$PROJ"

check_file_exists "AmplifierBlock.hpp created" "$DSP_INC/AmplifierBlock.hpp"
check_no_file "GainBlock2.hpp removed" "$DSP_INC/GainBlock2.hpp"
check_file_contains "struct name updated" "$DSP_INC/AmplifierBlock.hpp" "struct AmplifierBlock"
check_file_contains "CMakeLists has qa_Amplifier" "$DSP_TEST/CMakeLists.txt" "qa_AmplifierBlock"
check_file_not_contains "CMakeLists no GainBlock2" "$DSP_TEST/CMakeLists.txt" "qa_GainBlock2"

# ===========================================================================
# 12. mv
# ===========================================================================
echo ""
echo "--- 12. mv ---"

check_exit "mv: ConstSource dsp → signal" \
  mv ConstSource \
  --from dsp \
  --to signal \
  --yes \
  --project-dir "$PROJ"

check_file_exists "ConstSource.hpp in signal" "$SIG_INC/ConstSource.hpp"
check_no_file "ConstSource.hpp gone from dsp" "$DSP_INC/ConstSource.hpp"
check_file_contains "signal test CMakeLists updated" \
  "$PROJ/blocks/signal/test/CMakeLists.txt" "qa_ConstSource"
check_file_not_contains "dsp test CMakeLists no ConstSource" \
  "$DSP_TEST/CMakeLists.txt" "qa_ConstSource"

# ===========================================================================
# 13. rm
# ===========================================================================
echo ""
echo "--- 13. rm ---"

check_exit "rm: AmplifierBlock from dsp" \
  rm AmplifierBlock \
  --group dsp \
  --yes \
  --project-dir "$PROJ"

check_no_file "AmplifierBlock.hpp removed" "$DSP_INC/AmplifierBlock.hpp"
check_file_not_contains "CMakeLists no qa_AmplifierBlock" \
  "$DSP_TEST/CMakeLists.txt" "qa_AmplifierBlock"

check_exit "rm: SignalSink from signal" \
  rm SignalSink \
  --group signal \
  --yes \
  --project-dir "$PROJ"

check_no_file "SignalSink.hpp removed" "$SIG_INC/SignalSink.hpp"

# ===========================================================================
# 14. Final state check
# ===========================================================================
echo ""
echo "--- 14. Final state ---"

FINAL=$(run_gr4 info --project-dir "$PROJ")
check_output_contains "dsp: GainBlock remains" "GainBlock" "$FINAL"
check_output_contains "dsp: NullSink remains" "NullSink" "$FINAL"
check_output_contains "dsp: Decimator remains" "Decimator" "$FINAL"
check_output_contains "dsp: BareBlock remains" "BareBlock" "$FINAL"
check_output_contains "signal: ConstSource moved" "ConstSource" "$FINAL"

FINAL_CHECK=$(run_gr4 check --project-dir "$PROJ" 2>&1 || true)
check_output_contains "final check: no issues" "No issues found" "$FINAL_CHECK"

# ===========================================================================
# Results
# ===========================================================================
echo ""
echo "========================================"
printf "  Results: %s passed, %s failed\n" \
  "$(_green "$PASS")" "$(_red "$FAIL")"
echo "========================================"
echo ""

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
