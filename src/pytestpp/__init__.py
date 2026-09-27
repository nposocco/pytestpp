"""pytestpp: a smart drop-in for pytest.

Runs the real pytest under the hood, but automatically limits the selection to
the tests impacted by your local git changes whenever it can, and auto-refreshes
its coverage-derived mapping (``.tests/pytestpp/tests.sqlite``) when needed.
"""

from __future__ import annotations

__all__ = ["__version__", "main"]

try:
    # setuptools-scm writes this at build/install time; fall back to a
    # placeholder when running from a source checkout without it.
    from ._version import __version__  # type: ignore[no-redef]
except ImportError:  # pragma: no cover
    __version__ = "0+unknown"


def main(argv=None) -> int:
    """Console entry point (project.scripts ``pytestpp``)."""
    from .main import run

    return run(argv or None)