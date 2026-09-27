"""Delegation to the real pytest.

We run pytest **in-process** via ``pytest.main()`` so that plugin
registration, ``conftest.py`` discovery, ``config``/cache handling, tracebacks
and exit codes behave like a native ``pytest`` invocation.  The only addition
is an optional human-readable header printed *before* pytest's own report,
telling the user what the impact layer selected.
"""

from __future__ import annotations

import os
import sys

import pytest


def run_pytest(args: list[str], header_lines: list[str] | None = None,
               cwd: str | None = None) -> int:
    """Run pytest with ``args``; return pytest's exit code as an int.

    ``header_lines`` (if any) are printed before pytest starts, so a short
    "impacted analysis" summary can precede the familiar pytest report without
    touching any of pytest's own output.
    """
    if header_lines:
        for line in header_lines:
            print(line)
        sys.stdout.flush()

    old_cwd: str | None = None
    try:
        if cwd:
            old_cwd = os.getcwd()
            os.chdir(cwd)
        # pytest.main() raises SystemExit carrying the process exit code.
        return int(pytest.main(args) or 0)
    except SystemExit as exc:
        return int(exc.code or 0)
    finally:
        if old_cwd is not None:
            os.chdir(old_cwd)