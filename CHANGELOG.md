# Changelog

All notable changes to `pytestpp` are documented here. We follow
[semantic versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
Pre-`1.0.0` releases use `0.MINOR.PATCH` where `MINOR` may introduce breaking
changes.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Initial public release: a drop-in `pytestpp` command that runs only the tests
  impacted by your local git changes.
- Smart-by-default behavior: inside a git repository it shrinks the selection to
  impacted tests; otherwise it degrades to a plain full `pytest` run.
- Auto-refresh of the `.tests/tests.sqlite` line-to-test mapping from a
  per-test coverage pass.
- Reverse traceability: query which tests executed a given source line.
- CLI flags: `--impact`, `--no-impact`, `--rebuild-map`, `--no-rebuild-map`,
  `--base REF`, `--pp-root DIR`, `--pp-src DIR`; all other arguments are
  forwarded verbatim to the underlying `pytest`.
- MIT-licensed, packaged with `setuptools-scm` (version derived from git tags).

### Changed

- Renamed from an earlier prototype (`pytest-pp` / `pytest_pp`) to `pytestpp` to
  reduce misspelling risk.
- Removed the legacy `dsh_test_impact` package and `bin/` launchers from the
  distribution.