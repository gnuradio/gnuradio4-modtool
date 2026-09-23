# Contributing

Contributions are welcome — bug reports, feature requests, documentation improvements, and pull requests.

---

## Development setup

```bash
git clone https://github.com/gnuradio/gnuradio4-modtool
cd gr4_modtool
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"
```

Install pre-commit hooks (optional but recommended):

```bash
pip install pre-commit
pre-commit install
```

---

## Running the tests

```bash
# All tests
python3 -m pytest tests/ -v

# Single file
python3 -m pytest tests/test_newblock.py -v

# Pattern match
python3 -m pytest -k newparam -v

# With coverage
python3 -m pytest tests/ --cov=gr4_modtool --cov-report=term-missing
```

---

## Linting

```bash
# Check
ruff check gr4_modtool/ tests/

# Auto-fix
ruff check --fix gr4_modtool/ tests/

# Type checking (optional)
mypy gr4_modtool/
```

---

## Documentation

```bash
# Serve locally
mkdocs serve

# Build static site
mkdocs build
```

---

## Project layout

```
gr4_modtool/
├── commands/        # One file per CLI command (business logic + Click command)
├── project/         # cmake.py, discovery.py — build-file utilities
├── templates/       # Jinja2 .j2 template files
├── cli.py           # Click group + command registration
├── plugins.py       # importlib.metadata entry-point loader
└── templates.py     # Jinja2 render() with user-override search
tests/
├── conftest.py      # project / project_two_groups fixtures
└── test_*.py        # One test file per command
```

---

## Adding a new command

1. Create `gr4_modtool/commands/my_cmd.py` with a business-logic function and a `@click.command("my-cmd")` named `cmd`.
2. Import and register it in `gr4_modtool/cli.py`.
3. Add tests in `tests/test_my_cmd.py` using the `project` or `project_two_groups` fixture.

---

## Adding a custom template

Users can override any built-in `.j2` template by placing a file with the same name in a directory registered via the `gr4_modtool.templates` entry-point, or by setting `MODTOOL_TEMPLATE_DIR` in the environment.

Third-party packages can register a template directory in `pyproject.toml`:

```toml
[project.entry-points."gr4_modtool.templates"]
my_package = "my_package:templates_dir"
```

---

## Submitting a pull request

1. Fork the repository and create a branch from `main`.
2. Make your changes and add tests.
3. Ensure `pytest tests/` passes and `ruff check` reports no errors.
4. Open a pull request — the CI will run tests on Python 3.11 and 3.12.
