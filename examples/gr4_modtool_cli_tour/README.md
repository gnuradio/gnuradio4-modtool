# gr4_modtool CLI tour

A guided, fully non-interactive tour of the gr4_modtool command line —
[`tour.sh`](tour.sh) creates a real OOT module in a scratch directory and
walks it through most of the top-level commands, echoing each invocation
before running it so the output reads as a working session transcript.

What it exercises, in order:

1. **Scaffold** — `newmod` with a first group
2. **Blocks from a spec** — `newblock --spec` with three archetypes
   (`sync`, `source`, `decimator`)
3. **Evolve** — `newparam`, `add-test`, `newbench --wire-build`
4. **Lifecycle** — `newgroup`, `cp` (across and within groups), `rename`,
   `mv`, `rm`
5. **Inspect** — `info`, `ls --format json`, `status`, `show`
6. **Health** — `check`, `validate`, `lint-headers`, `sync`, `doctor`
7. **Docs & release** — `docs --catalog`, `export-spec`, `version-bump`

## Run

```bash
# Work in a temp dir, clean up afterwards
./tour.sh

# Keep the generated project for a look around
./tour.sh /tmp/gr4_demo
```

This is a demo, not a test — the assertion-based integration test lives at
`smoke_test.sh` in the repository root, and the same walkthrough driven from
Python lives in `examples/gr4_modtool_python_api/`.
