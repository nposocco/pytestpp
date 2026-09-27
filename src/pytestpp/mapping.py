"""Mapping freshness: locate / auto-rebuild ``.tests/tests.sqlite``.

The impact layer can only be trusted if the mapping reflects the current
source.  This module decides whether it's usable and, when asked (the
"smart-by-default" auto-refresh policy), rebuilds it from a fast per-test
coverage pass before filtering.
"""

from __future__ import annotations

import os
import subprocess
import sys

try:
    import coverage  # type: ignore
except Exception:  # pragma: no cover
    coverage = None  # type: ignore[assignment]


DEFAULT_DB_REL = os.path.join(".tests", "tests.sqlite")


# --------------------------------------------------------------------------- #
# locating
# --------------------------------------------------------------------------- #

def default_db_path(root: str) -> str:
    return os.path.join(root, DEFAULT_DB_REL)


def mapping_is_usable(db_path: str, root: str) -> bool:
    """A mapping is usable if the DB exists and isn't empty."""
    if not os.path.exists(db_path):
        return False
    try:
        import sqlite3

        conn = sqlite3.connect(db_path)
        try:
            n = conn.execute("SELECT COUNT(*) FROM coverage").fetchone()[0]
        finally:
            conn.close()
        return n > 0
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# auto-rebuild (per-test coverage -> mapping), mirror of build_tests_db
# --------------------------------------------------------------------------- #

def _fold_coverage(data_file: str, db_path: str, src_abs: str) -> int:
    """Fold a per-test-context ``.coverage`` file into the sqlite mapping."""
    if coverage is None:
        raise RuntimeError("coverage is not installed; cannot rebuild the mapping")
    import sqlite3

    src_abs = os.path.normpath(src_abs)
    cov = coverage.Coverage(data_file=data_file)
    cov.load()
    data = cov.get_data()

    rows: list[tuple[str, int, str]] = []
    for f in data.measured_files():
        if not os.path.normpath(f).startswith(src_abs):
            continue
        if "/tests/" in f or "/deps/" in f or "/pytestpp/" in f:
            continue
        by_line = data.contexts_by_lineno(f) or {}
        abspath = os.path.abspath(f)
        for lnr, contexts in by_line.items():
            for ctx in contexts:
                rows.append((abspath, lnr, ctx))

    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS coverage ("
        " src_file TEXT NOT NULL, line_no INTEGER NOT NULL, test_id TEXT NOT NULL);"
    )
    conn.execute("DELETE FROM coverage")
    conn.executemany(
        "INSERT INTO coverage (src_file, line_no, test_id) VALUES (?, ?, ?)", rows
    )
    conn.commit()
    n_tests = len({t for _, _, t in rows})
    conn.close()
    return n_tests


def _run_baseline(root: str, src_abs: str, data_file: str, targets: list[str]) -> int:
    """Launch the real pytest under the per-test-coverage plugin."""
    # Ensure the src/ tree (for the `pytestpp` package and its plugin) plus the
    # bundle deps dir are on the subprocess's PYTHONPATH.
    this_file = os.path.abspath(__file__)                       # .../src/pytestpp/mapping.py
    pkg_dir = os.path.dirname(this_file)                        # .../src/pytestpp
    src_root = os.path.dirname(pkg_dir)                         # .../src
    repo_root = os.path.dirname(src_root)                       # .../ (workspace root)
    extra_roots = [p for p in (repo_root, os.path.join(repo_root, "deps"), src_root)
                   if os.path.isdir(p)]

    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        extra_roots + ([existing] if existing else [])
    )
    env["DSH_COVERAGE_FILE"] = data_file
    env["DSH_COVERAGE_SRC"] = src_abs

    plugin = "pytestpp.covctx"
    cmd = [sys.executable, "-m", "pytest", "-p", plugin, *targets]
    return subprocess.run(cmd, cwd=root, env=env).returncode


def rebuild_mapping(db_path: str, root: str, src: str, targets: list[str] | None = None) -> bool:
    """Rebuild the mapping from a coverage baseline run.  Returns success."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    data_file = os.path.join(root, ".tests", ".coverage")
    src_abs = os.path.abspath(os.path.join(root, src))
    targets = targets or ["."]

    print(f"pytestpp: rebuilding impact mapping ({db_path}) ...")
    rc = _run_baseline(root, src_abs, data_file, targets)
    if not os.path.exists(data_file):
        print("pytestpp: rebuild produced no coverage data; impact filter disabled.")
        return False
    _fold_coverage(data_file, db_path, src_abs)
    print(f"pytestpp: mapping rebuilt -> {db_path}")
    return True