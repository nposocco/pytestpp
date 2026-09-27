"""The impact layer: figure out which tests are touched by local changes.

Self-contained (depends only on stdlib + sqlite3 + the mapping DB), so
``pytestpp`` installs and works stand-alone.  Returns the impacted pytest
node-id list that we seed pytest with.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess


# --------------------------------------------------------------------------- #
# SQLite helpers
# --------------------------------------------------------------------------- #

_SCHEMA = """
CREATE TABLE IF NOT EXISTS coverage (
    src_file TEXT    NOT NULL,
    line_no  INTEGER NOT NULL,
    test_id  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cov_file_line ON coverage (src_file, line_no);
CREATE INDEX IF NOT EXISTS idx_cov_test      ON coverage (test_id);
"""


def connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


def known_source_files(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT DISTINCT src_file FROM coverage")}


def impacted_test_ids(conn: sqlite3.Connection, changed: dict) -> list[str]:
    """``{abs_src_file: [line_no,...]}`` -> sorted, de-duplicated test ids."""
    ids: set[str] = set()
    for f, lines in changed.items():
        lines = [ln for ln in lines if isinstance(ln, int)]
        if not lines:
            continue
        ph = ",".join("?" * len(lines))
        sql = (
            f"SELECT DISTINCT test_id FROM coverage "
            f"WHERE src_file = ? AND line_no IN ({ph})"
        )
        for (test_id,) in conn.execute(sql, [f, *lines]):
            ids.add(test_id)
    return sorted(ids)


# --------------------------------------------------------------------------- #
# git / diff
# --------------------------------------------------------------------------- #

def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True
    )


def locate_root(start: str | None = None) -> str | None:
    """Walk up from ``start`` (or cwd) to the nearest git working tree root."""
    path = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def resolve_base(root: str, requested: str | None) -> str:
    """Default base: ``origin/main`` if it exists, else ``HEAD``."""
    if requested:
        if _git(root, "rev-parse", "--verify", "--quiet", requested).returncode == 0:
            return requested
        return "HEAD"
    return "origin/main" if _git(root, "rev-parse", "--verify", "--quiet", "origin/main").returncode == 0 else "HEAD"


def parse_diff(diff_text: str, known_src: set[str], repo_root: str) -> dict:
    """``git diff -U0`` text -> ``{abs_src_file: [new_line_no, ...]}``.

    Only files already present in the mapping are kept; with ``-U0`` the +/- 
    lines are exact, and removed lines don't exist in the new file, so only
    added (+) lines become candidate changed source lines.
    """
    repo_root = os.path.abspath(repo_root)
    changed: dict[str, set[int]] = {}
    cur_file: str | None = None
    pos: int | None = None

    for raw in diff_text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("+++ b/"):
            cur_file = os.path.normpath(line[len("+++ b/"):])
            pos = None
        elif line.startswith("@@"):
            new = line.split("@@")[1].strip().split(" ")[1]  # "+45,6"
            new = new[1:]
            pos = int(new.split(",")[0])
        elif pos is None or cur_file is None:
            continue
        elif line.startswith("+"):
            changed.setdefault(cur_file, set()).add(pos)
            pos += 1
        elif line.startswith("-"):
            pass
        elif line.startswith("\\"):
            pass
        elif line.startswith(" "):
            pos += 1

    result: dict[str, list[int]] = {}
    for rel, lines in changed.items():
        if not lines or rel in ("/dev/null",):
            continue
        ap = os.path.normpath(os.path.join(repo_root, rel))
        if ap in known_src:
            result[ap] = sorted(lines)
    return result


# --------------------------------------------------------------------------- #
# public API used by main()
# --------------------------------------------------------------------------- #

def compute_impacted(db_path: str, root: str, base: str | None) -> tuple[int, list[str]]:
    """Return ``(changed_line_count, sorted_impacted_node_ids)``."""
    base = resolve_base(root, base)
    conn = connect(db_path)
    known = known_source_files(conn)
    conn.close()

    diff = _git(root, "diff", "--unified=0", base, "--", ".")
    if diff.returncode != 0:
        raise RuntimeError(f"git diff failed: {diff.stderr.strip()}")

    changed = parse_diff(diff.stdout, known, root)
    changed_lines = sum(len(v) for v in changed.values())

    conn = connect(db_path)
    try:
        impacted = impacted_test_ids(conn, changed)
    finally:
        conn.close()
    return changed_lines, impacted


def selection_header(
    impacted: list[str], base: str, changed_lines: int, n_selected: int
) -> list[str]:
    """Human-readable lines shown above pytest's own report in impact mode."""
    return [
        "=" * 62,
        f"pytestpp: impact filter   [base={base}]",
        f"  changed source lines mapped: {changed_lines}",
        f"  impacted tests selected   : {len(impacted)}",
        f"  total node-ids passed     : {n_selected}",
        "=" * 62,
    ]