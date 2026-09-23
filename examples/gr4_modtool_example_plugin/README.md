# gr4-modtool-example-plugin

A minimal example demonstrating both gr4_modtool extension points:

- **CLI command** — adds `gr4_modtool report` which prints a block-count summary
- **Template override** — replaces `qa_block.cpp.j2` with an annotated version

## Install

```bash
pip install -e .
```

## Try it

```bash
# New command from the plugin
gr4_modtool report
gr4_modtool report --json

# See that the template override is active
gr4_modtool templates list
```

## Structure

```
gr4_modtool_example_plugin/
├── commands/
│   └── report.py          ← @click.command("report")
└── templates/
    ├── __init__.py        ← get_templates_dir() callable
    └── qa_block.cpp.j2    ← overrides the built-in test template
```

## How it works

`pyproject.toml` registers two entry points:

```toml
[project.entry-points."gr4_modtool.commands"]
report = "gr4_modtool_example_plugin.commands.report:cmd"

[project.entry-points."gr4_modtool.templates"]
example_plugin = "gr4_modtool_example_plugin.templates:get_templates_dir"
```

At startup, gr4_modtool discovers both and:
1. Adds `cmd` to the CLI as `gr4_modtool report`
2. Inserts the `templates/` directory into the Jinja2 search path before the built-ins

See [docs/plugins.md](../../docs/plugins.md) for the full plugin development guide.
