"""pytest plugin that records per-test line coverage (self-contained copy).

Activated only when ``DSH_COVERAGE_FILE`` + ``DSH_COVERAGE_SRC`` are set by
``pytestpp.mapping`` when it auto-refreshes the impact mapping.  Each test runs
under a coverage *context* named by its pytest node id, giving the exact
``line -> test`` relation the impact layer needs.
"""

from __future__ import annotations

import os


def pytest_configure(config):
    data_file = os.environ.get("DSH_COVERAGE_FILE")
    src = os.environ.get("DSH_COVERAGE_SRC")
    setattr(config, "_pp_cov", None)
    if not (data_file and src):
        return
    import coverage

    cov = coverage.Coverage(
        data_file=data_file,
        source=[src],
        omit=[
            "*/tests/*",
            "*/deps/*",
            "*/pytestpp/*",
            "*/conftest.py",
        ],
        branch=False,
    )
    cov.start()
    setattr(config, "_pp_cov", cov)


def _switch(config, nodeid: str) -> None:
    cov = getattr(config, "_pp_cov", None)
    if cov is not None:
        cov.switch_context(nodeid)


def pytest_runtest_setup(item):
    _switch(item.config, item.nodeid)


def pytest_runtest_teardown(item, nextitem):
    _switch(item.config, item.nodeid)


def pytest_sessionfinish(session, exitstatus):
    cov = getattr(session.config, "_pp_cov", None)
    if cov is not None:
        cov.stop()
        cov.save()