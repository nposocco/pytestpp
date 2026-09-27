"""``pytestpp`` CLI: isolate our own flags and forward the rest to pytest.

We deliberately do *not* try to fully parse pytest's argument grammar here --
pytest does that itself. We only pull out the handful of ``pytestpp``-specific
switches (which pytest would otherwise reject), everything else is passed
through untouched so pytest reports/behaves exactly as it normally would.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field


@dataclass
class PPConfig:
    """pytestpp's own options (the rest of argv goes to pytest)."""

    impact: bool | None             # None = smart default, True/False force
    rebuild: bool | None            # None = auto, True/False override
    base: str | None                # git ref to diff against
    root: str | None                # project/repo root (else auto-detect)
    src: str | None                 # project source root for rebuilds
    extra: list[str] = field(default_factory=list)  # forwarded to pytest


SUPPORTED = {
    "--impact",
    "--no-impact",
    "--rebuild-map",
    "--no-rebuild-map",
    "--base",
    "--pp-root",
    "--pp-src",
}


def parse(argv: list[str] | None) -> tuple[PPConfig, list[str]]:
    """Split argv into a :class:`PPConfig` and the plain pytest argument list.

    Unknown flags are never consumed here; anything we don't recognise is left
    in the forwarded list so pytest can interpret (or reject) it as usual.
    """
    argv = list(argv) if argv is not None else list(os.sys.argv[1:])
    cfg = PPConfig(impact=None, rebuild=None, base=None, root=None, src=None)
    rest: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--impact":
            cfg.impact = True
        elif arg == "--no-impact":
            cfg.impact = False
        elif arg == "--rebuild-map":
            cfg.rebuild = True
        elif arg == "--no-rebuild-map":
            cfg.rebuild = False
        elif arg == "--base":
            if i + 1 >= len(argv):
                raise SystemExit("error: --base requires a value")
            cfg.base = argv[i + 1]
            i += 1
        elif arg == "--pp-root":
            if i + 1 >= len(argv):
                raise SystemExit("error: --pp-root requires a value")
            cfg.root = argv[i + 1]
            i += 1
        elif arg == "--pp-src":
            if i + 1 >= len(argv):
                raise SystemExit("error: --pp-src requires a value")
            cfg.src = argv[i + 1]
            i += 1
        elif arg in ("-h", "--help"):
            _print_help()
            raise SystemExit(0)
        else:
            rest.append(arg)
        i += 1
    return cfg, rest


def _print_help() -> None:
    parser = _build_help_parser()
    parser.print_help()


def _build_help_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pytestpp",
        add_help=False,
        description=(
            "Smart drop-in for pytest: delegates to the real pytest but runs only "
            "the tests impacted by your local git changes when it can."
        ),
    )
    parser.add_argument("--impact", action="store_true",
                        help="Force impact-filtering on.")
    parser.add_argument("--no-impact", action="store_true",
                        help="Force impact-filtering off (plain pytest behavior).")
    parser.add_argument("--rebuild-map", action="store_true",
                        help="Force rebuilding .tests/pytestpp/tests.sqlite before running.")
    parser.add_argument("--no-rebuild-map", action="store_true",
                        help="Never rebuild the mapping (use as-is).")
    parser.add_argument("--base", metavar="REF",
                        help="Git ref to diff against (default: origin/main else HEAD).")
    parser.add_argument("--pp-root", metavar="DIR",
                        help="Project / git repo root (default: auto-detected).")
    parser.add_argument("--pp-src", metavar="DIR",
                        help="Project source root used when auto-rebuilding the map "
                             "(default: auto-detected).")
    parser.epilog = (
        "All other arguments are forwarded to the underlying pytest, e.g.\n"
        "  pytestpp --impact -x -q tests/test_demoapp.py::test_add\n"
        "Run 'pytest --help' for the full list of forwarded options."
    )
    return parser