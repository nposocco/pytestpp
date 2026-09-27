# pytestpp — smart drop-in for pytest

[![PyPI - Version](https://img.shields.io/pypi/v/pytestpp.svg)](https://pypi.org/project/pytestpp)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/pytestpp.svg)](https://pypi.org/project/pytestpp)
[![PyPI - License](https://img.shields.io/pypi/l/pytestpp.svg)](https://pypi.org/project/pytestpp)
[![tests](https://img.shields.io/github/actions/workflow/status/nposocco/pytestpp/ci.yml?branch=main&label=tests)](https://github.com/nposocco/pytestpp/actions)
[![codecov](https://codecov.io/gh/nposocco/pytestpp/branch/main/graph/badge.svg)](https://codecov.io/gh/nposocco/pytestpp)

Run **only the tests impacted by your local git changes**, with the exact look
and feel of pytest. `pytestpp` wraps the real `pytest` (in-process) and, by
default, auto-selects the impacted subset — while still rewarding you with the
native pytest report, plugins, and exit codes in every other case.

```
pytestpp                 # impacted tests only (or full suite if none)
pytestpp --no-impact     # exactly like plain pytest
pytestpp -x -k "fast"    # forwarded verbatim to the underlying pytest
```

## Highlights

- **Drop-in install** — `pip install .` gives a `pytestpp` console command that
  coexists with the real `pytest` and calls into it.
- **Smart by default** — inside a git repo it shrinks the selection to impacted
  tests; otherwise it degrades gracefully to a plain full run.
- **Auto-refresh** — rebuilds the `.tests/pytestpp/tests.sqlite` line→test mapping when
  missing/stale, from a per-test coverage pass.
- **Reverse traceability** — the same SQLite mapping answers *"which tests go
  through this line?"* (see `docs/usage.md`).

## Layout

```
pyproject.toml            # console_script: pytestpp = "pytestpp:main"
src/pytestpp/            # the package
  cli.py, main.py         # own flags + smart orchestration
  impact.py               # git diff -> impacted node ids (sqlite reverse-lookup)
  mapping.py, covctx.py   # auto-build .tests/pytestpp/tests.sqlite via per-test coverage
  delegator.py            # thin wrapper over pytest.main()
demo/                     # sample git repo used for verification
docs/
  usage.md                # the usage manual
  design.md               # architecture & rationale
```

## Try it in this repo

```bash
# Build/install the console command (a normal venv works too):
PYTHONPATH=./deps python3 -m pip install --target ./runtime .

cd demo                       # a tiny git repo with 7 tests
../runtime/bin/pytestpp      # clean tree -> full suite
# edit src/demoapp/__init__.py, e.g. change `add`, then:
../runtime/bin/pytestpp      # runs ONLY the implicated tests
```

See **[`docs/usage.md`](docs/usage.md)** for the full manual and CLI reference,
and **[`docs/design.md`](docs/design.md)** for how the delegation + impact
layers are put together.

## Install

```bash
pip install pytestpp            # from PyPI (once published)
pytestpp --help
```

## Versioning

This project uses **semantic versioning** (`MAJOR.MINOR.PATCH`). Versions are
derived from git tags via [`setuptools-scm`](https://github.com/pypa/setuptools-scm);
tag the repo (`git tag v1.2.3`) rather than editing a version string by hand.

## License

[MIT](LICENSE) — see `LICENSE` for details.
