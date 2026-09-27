"""``pytestpp`` entry point: orchestrate the smart drop-in behavior.

Decision flow (smart by default):

  * Not inside a git repo .................  ->   plain pytest run
  * ``--no-impact`` ........................  ->   plain pytest run
  * mapping usable + changes detected ......  ->   run only impacted node-ids
  * mapping missing/stale + auto-refresh on  ->   rebuild map, then filter
  * no impacted tests ......................  ->   full pytest run (nothing to shrink)

Pytest's exit code is always preserved (CI semantics unchanged).
"""

from __future__ import annotations

import os
import sys

from .cli import parse
from .delegator import run_pytest
from . import impact, mapping


def _detect_root(cfg_root: str | None) -> str | None:
    if cfg_root:
        return os.path.abspath(cfg_root)
    return impact.locate_root()


def _has_python(abspath: str) -> bool:
    for dp, _dn, files in os.walk(abspath):
        if "tests" in dp.replace(os.sep, "/").split("/"):
            continue
        if any(f.endswith(".py") for f in files):
            return True
    return False


def _detect_src(root: str, hinted: str | None) -> str | None:
    """Find the importable source tree to trace for the auto-rebuild."""
    if hinted:
        p = os.path.join(root, hinted)
        return p if os.path.isdir(p) else None
    for c in (os.path.join(root, "src"), root):
        if os.path.isdir(c) and _has_python(c):
            return c
    return None


def _decide_impact(cfg_impact: bool | None, inside_git: bool) -> bool:
    if cfg_impact is not None:
        return cfg_impact
    return inside_git  # smart default: only when a git repo is present


def run(argv=None) -> int:
    cfg, args = parse(argv)

    root = _detect_root(cfg.root)
    inside_git = root is not None

    if not _decide_impact(cfg.impact, inside_git):
        return run_pytest(args, cwd=root)

    # ---- we are inside a git repo and impact is enabled (or default) ----
    assert root is not None  # guaranteed by the gate above
    db_path = mapping.default_db_path(root)
    usable = mapping.mapping_is_usable(db_path, root)
    want_rebuild = (cfg.rebuild is True) or (cfg.rebuild is None and not usable)

    if want_rebuild:
        src = _detect_src(root, cfg.src)
        if src is None:
            print("pytestpp: no source tree detected to trace; running full suite.")
            return run_pytest(args, cwd=root)
        ok = mapping.rebuild_mapping(db_path, root, os.path.relpath(src, root))
        if not ok:
            return run_pytest(args, cwd=root)

    try:
        base = cfg.base
        changed_lines, impacted = impact.compute_impacted(db_path, root, base)
    except Exception as exc:  # never let the impact layer break a test run
        print(f"pytestpp: impact analysis failed ({exc}); falling back to full run.",
              file=sys.stderr)
        return run_pytest(args, cwd=root)

    if not impacted:
        print("pytestpp: no impacted tests found for the current diff; running full suite.")
        return run_pytest(args, cwd=root)

    base_used = cfg.base or "origin/main"
    header = impact.selection_header(
        impacted, base_used, changed_lines, len(impacted)
    )
    return run_pytest(impacted + args, header_lines=header, cwd=root)


if __name__ == "__main__":
    raise SystemExit(run())