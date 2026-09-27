# pytestpp usage

`pytestpp` is a drop-in replacement for `pytest` that, by default, runs only
the tests impacted by your local git changes — while delegating to the **real
pytest** under the hood so output, plugins and exit codes match pytest exactly.

---

## Installation

Like pytest:

```bash
python -m pip install .
# or, from a wheel/vcs:
python -m pip install pytestpp
```

This installs the `pytestpp` console command. You can keep the real `pytest`
installed too; they coexist (`pytestpp` calls into the installed `pytest`).

> Requirements: Python ≥ 3.9, plus `pytest>=7` and `coverage>=6.4` (installed
> automatically as dependencies).

---

## Quick start

```bash
cd my/src-layout/project          # a git repository

pytestpp                         # <= run impacted tests (or full suite if none)
```

That's it. On the first run inside a git repo, `pytestpp` builds its impact
mapping (`.tests/pytestpp/tests.sqlite`) from a coverage pass, then runs only the tests
touched by your working-tree changes.

### Typical workflow

```bash
# 1. baseline group of tests exist
pytestpp --rebuild-map           # build/refresh the line->test mapping

# 2. edit a source file
pytestpp                         # runs only tests affected by the edit

# 3. full suite when you want it
pytestpp --no-impact             # behaves exactly like plain pytest
pytestpp -q --no-impact          # ...with pytest flags forwarded
```

---

## How it behaves (smart by default)

| Situation | What `pytestpp` does |
|---|---|
| Not inside a git repo | Runs the full suite (plain pytest pass-through). |
| Git repo, clean tree (no diff) | Runs the full suite. |
| Git repo, mapping fresh, changes present | Runs **only** the impacted tests. |
| Git repo, mapping missing/stale | Auto-rebuilds the mapping, then filters. |
| `--no-impact` | Always plain full pytest run. |

In every case the **exit code is pytest's** (e.g. `1` if a test fails), so CI
semantics are unchanged.

---

## Command-line reference

`pytestpp` own flags (everything else is forwarded verbatim to pytest):

| Flag | Meaning |
|---|---|
| `--impact` | Force impact-filtering on. |
| `--no-impact` | Force impact-filtering off (plain pytest). |
| `--rebuild-map` | Force rebuilding `.tests/pytestpp/tests.sqlite` before running. |
| `--no-rebuild-map` | Never rebuild; use the map as-is. |
| `--base REF` | Git ref to diff against (default: `origin/main` else `HEAD`). |
| `--pp-root DIR` | Override the project/repo root (default: auto-detected). |
| `--pp-src DIR` | Source tree to trace when rebuilding (default: auto-detected). |
| `-h` / `--help` | Show this help. |

All other arguments — `-x`, `-q`, `-k`, `-m`, `--cov=...`, test path/`::nodeid`
selections, etc. — are forwarded unchanged to the real pytest.

### Examples

```bash
pytestpp --impact -x            # impacted tests, stop at first failure
pytestpp -k "fast" --no-impact  # plain pytest, keyword filter
pytestpp --base origin/main     # diff against origin/main explicitly
pytestpp tests/test_a.py::test_thing --rebuild-map
```

---

## The mapping: `.tests/pytestpp/tests.sqlite`

Each tool that participates in this scheme keeps its data in its **own
subfolder** of `.tests/`. `pytestpp` writes to `.tests/pytestpp/` so that other
language tools (rust, go, node, ...) can write their own mappings side by side
in the same repository without colliding:

```
.tests/
├── pytestpp/                 # <-- pytestpp's subfolder
│   ├── tests.sqlite          # the mapping DB (queried at run time)
│   └── .coverage             # raw coverage.py data (byproduct of auto-rebuild)
└── <other-lang-tool>/        # e.g. a future .tests/rust/ tool
```

The mapping DB has a single table which records which test (by pytest node id)
executed which source line:

```
coverage(src_file, line_no, test_id)
```

It is rebuilt from a per-test `coverage.py` run (`pytest -p pytestpp.covctx`).
Because it records true execution, it is exact for the code paths exercised by
the baseline suite.

### Reverse lookup (your "which tests go through this line?" question)

```sql
SELECT DISTINCT test_id FROM coverage
WHERE src_file = '/abs/path/to/module.py' AND line_no = 42;
```

### When to rebuild

Rebuild whenever you add/remove test–source relationships, rename files, or
rewrite significant chunks (`pytestpp --rebuild-map`). `pytestpp` rebuilds
automatically when the mapping is missing, and you can force it with
`--rebuild-map`.

---

## Beyond CI

Because it's just a thin wrapper over `pytest.main()`, `pytestpp` works with
`conftest.py` fixtures, third-party pytest plugins, `--pdb`, IDE debugger
integrations, and coverage plugins — anything real `pytest` supports.

---

## Troubleshooting

- **"impact analysis failed; falling back to full run"** — the impact layer
  hit an unexpected error (e.g. no coverage data). Tests still run, just
  unfiltered. Check `--pp-root` / `--pp-src` if you use a non-standard layout.
- **"no source tree detected"** — `pytestpp` couldn't find an importable
  source dir to trace. Pass `--pp-src <dir>`.
- **Impact looks stale** — run `pytestpp --rebuild-map`.