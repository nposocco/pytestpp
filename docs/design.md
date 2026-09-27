# pytestpp: design notes

`pytestpp` is a thin, **smart** wrapper around the real pytest. It deliberately
*does not re-implement* test execution, plugin handling or reporting. It adds one
thing: a pre-pass that computes which tests are affected by your uncommitted
changes, and seeds pytest with exactly that subset of node ids.

## Core principle: delegate, don't reimplement

The entire test run is performed in-process by `pytest.main()`:

```
pytestpp/delegator.py::run_pytest(args, header_lines, cwd)
    print(header_lines)      # optional impact summary, before pytest's report
    code = int(pytest.main(args) or 0)
    return code
```

Because pytest runs **in-process**:
- plugins register normally,
- `conftest.py` discovery behaves identically,
- tracebacks, `-k/-m` filters, `--pdb` and debugger hooks all keep their native
  semantics,
- the returned exit code is pytest's own (CI-safe).

The wrapper only prints an optional header *before* calling pytest; it never
mutates pytest's output.

## Module map

```
pytestpp/
  __init__.py    version + console entry (delegates to main.run)
  cli.py         split `pytestpp`'s own CLI flags from forwarded pytest args
  main.py        orchestration / decision flow (smart by default)
  impact.py      git diff -> changed lines -> impacted node ids (sqlite reverse look-up)
  mapping.py     locate / auto-rebuild .tests/tests.sqlite
  covctx.py      pytest plugin that records per-test coverage contexts
  delegator.py   thin wrapper around pytest.main()
```

### decision flow (`main.run`)

```
parse flags
root = locate git root          (None => not a git repo)
impact_enabled = --impact/--no-impact overrides, else (root is not None)

if not impact_enabled:
    run_pytest(args)                       # plain pytest
else:
    db = <root>/.tests/tests.sqlite
    if map missing and --no-rebuild-map -> fall back to full run
    if map missing/stale and auto-refresh -> rebuild_mapping(...)   # coverage pass
    impacted = compute_impacted(db, root, base)
    if not impacted -> run_pytest(args)                            # full suite
    else -> run_pytest(impacted + args, header_lines=...)
```

`--impact` forces the layer on even outside a repo; `--no-impact` forces it off.

## The impact computation (`impact.py`)

1. **Diff** — `git diff --unified=0 <base> -- .`; base defaults to
   `origin/main` if the ref exists, else `HEAD`. Parsed hunks yield the
   *changed new-file line numbers*; removed lines don't exist in the new file,
   so only added `+` lines are candidates.
2. **Reverse look-up** — for each `(src_file, line_no)` in the mapping DB:

   ```sql
   SELECT DISTINCT test_id FROM coverage
   WHERE src_file = ? AND line_no IN (...);
   ```

   The union over all changed lines is the impacted set (dedup + sort).

Files are resolved against the **repo root** (git emits repo-root-relative
paths, while the DB stores absolute paths); only files that already exist in
the mapping are considered.

## The mapping (`mapping.py`, `covctx.py`)

`.tests/tests.sqlite` is built by a coverage run where each test runs in its
own coverage **context** named after its pytest node id. The `covctx` plugin:

```
pytest_configure:      start coverage (source=<src>, contexts enabled)
pytest_runtest_setup:  coverage.switch_context(nodeid)
pytest_sessionfinish:  stop + save
```

The `.coverage` file is then folded via the stable
`coverage.CoverageData.contexts_by_lineno()` API into
`coverage(src_file, line_no, test_id)` rows.

**Auto-refresh trade-off**: rebuilding requires a *full* suite pass (coverage
needs every line mapped). This is why `pytestpp` only rebuilds when the map is
missing or `--rebuild-map` is passed, and never silently for every invocation.

## Naming / coexistence

Console script is `pytestpp`; the real `pytest` remains on PATH and is called
into. A true `pytest`-named binary is *not* shadowed — coexist by design.

## Known limitations

- **Mapping freshness** — reflects the last build; rebuild after editing
  test-source relationships or renaming files.
- **Coverage-based** — exact for lines actually executed at build time;
  indirect dispatch (`getattr`, meta-classes) resolves to executed lines.
- **Auto-refresh cost** — first run (or `--rebuild-map`) pays a full coverage
  pass; subsequent runs are cheap reverse look-ups.
- **Repo-root relative paths** — the mapping records absolute paths; moving the
  repo path (e.g. CI checkout dir) requires a rebuild (handled automatically
  when the map is found empty/missing).