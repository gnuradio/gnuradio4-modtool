# gr4_modtool Python API example

A single runnable script showing the `gr4_modtool.api` library surface —
everything the CLI does, driven from Python with no prompts.

[`build_project.py`](build_project.py) walks through:

1. **Scaffold** a project with `Project.create` (`newmod`), including
   CMake presets and clang config
2. **Add blocks** with `Project.new_block` — keyword form, archetype
   defaults, and applying a spec-entry dict via `**entry` (`newblock`)
3. **Evolve** it: `add_param`, `new_group`, `copy_block`, `rename_block`
4. **Reconcile** a deliberately missing test with `sync_plan`/`sync_apply`
5. **Inspect** the result: `inventory`, `audit`, `status`

## Run

```bash
# Generates into a temp dir and cleans up
python3 build_project.py

# Keep the generated project for a look around
python3 build_project.py /tmp/gr4_demo
```

Expected output ends with a clean audit:

```
audit: 0 issue(s)
status: 4 block(s), 4 tested, v0.1.0
```

Full reference: [docs/python-api.md](../../docs/python-api.md), including the
complete CLI-command → API mapping table.
