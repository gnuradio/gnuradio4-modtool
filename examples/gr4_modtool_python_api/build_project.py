#!/usr/bin/env python3
"""End-to-end tour of the gr4_modtool Python API.

Scaffolds a complete GNURadio 4 OOT project in a temporary directory using
the :class:`Project` facade, exercises the block lifecycle, and prints an
audit — no CLI invocation, no prompts.

Run from anywhere after installing gr4_modtool:

    python3 examples/gr4_modtool_python_api/build_project.py

Pass a directory to keep the generated project instead of using a temp dir:

    python3 examples/gr4_modtool_python_api/build_project.py /tmp/gr4_demo
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from gr4_modtool.api import Project


def main(dest: Path) -> None:
    # ------------------------------------------------------------------ #
    # 1. Scaffold a project (CLI: newmod)
    # ------------------------------------------------------------------ #
    proj = Project.create(
        dest / "gr4_demo",
        "gr4_demo",
        first_group="dsp",
        gen_presets=True,  # CMakePresets.json
        gen_clang=True,  # .clang-format / .clang-tidy
    )
    print(f"Created {proj!r}")

    # ------------------------------------------------------------------ #
    # 2. Add blocks (CLI: newblock)
    # ------------------------------------------------------------------ #
    # Keyword form — ports and processing style come from the archetype.
    proj.new_block(
        block_name="Gain",
        group_name="dsp",
        description="Multiplies samples by a constant.",
    )
    proj.new_block(
        block_name="NoiseSource",
        group_name="dsp",
        archetype="source",
        gen_test=False,  # deliberately skipped; sync() fixes it below
    )

    # A spec-entry dict (the same shape YAML specs use) applies with **.
    entry = {
        "group_name": "dsp",
        "block_name": "Squelch",
        "description": "Gates samples below a power threshold.",
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
    }
    proj.new_block(**entry)

    # ------------------------------------------------------------------ #
    # 3. Evolve the project (CLI: newparam, newgroup, cp, mv, rename)
    # ------------------------------------------------------------------ #
    proj.add_param("dsp", "Gain", "gain", "float", "Gain factor", "1.0f")

    proj.new_group("filters")
    proj.copy_block("dsp", "Gain", "Attenuator", dst_group="filters", gen_test=True)
    proj.rename_block("filters", "Attenuator", "Pad")

    # ------------------------------------------------------------------ #
    # 4. Reconcile missing tests (CLI: sync)
    # ------------------------------------------------------------------ #
    actions = proj.sync_plan()
    print(f"\nsync: {len(actions)} action(s) planned")
    for a in actions:
        print(f"  {a.action}: {a.group}/{a.block}")
    proj.sync_apply(actions)

    # ------------------------------------------------------------------ #
    # 5. Inspect (CLI: ls, check, status)
    # ------------------------------------------------------------------ #
    print("\nInventory:")
    for group in proj.inventory()["groups"]:
        blocks = ", ".join(b["name"] for b in group["blocks"])
        print(f"  {group['name']}: {blocks}")

    issues = proj.audit()
    print(f"\naudit: {len(issues)} issue(s)")
    for issue in issues:
        print(f"  [{issue.severity}] {issue.group}/{issue.block}: {issue.issue}")

    status = proj.status()
    tested = sum(g.tested_count for g in status.groups)
    total = sum(g.block_count for g in status.groups)
    print(f"status: {total} block(s), {tested} tested, v{status.version}")

    print(f"\nProject written to {proj.root}")
    print("Next: cmake --preset default && cmake --build --preset default")
    # Or from Python, once GNURadio 4 is installed:
    #   proj.build(run_tests=True)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(Path(sys.argv[1]).resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="gr4_api_example_") as tmp:
            main(Path(tmp))
