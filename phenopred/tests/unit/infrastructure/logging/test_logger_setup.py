# tests/unit/infrastructure/logging/test_logger_setup.py
"""Unit tests for LoggerSetup (Architecture v1 Section 5/12).

Mirrors the testing approach already established by
tests/unit/infrastructure/config/test_config_loader.py: plain,
hand-written assertion functions, no framework-specific fixtures
required.

Scope discipline: this suite verifies LoggerSetup's own handler/
formatter/level configuration behavior only. It does not test any
domain, application, or other infrastructure module's own logging
calls, since none of them are changed by this step (see
logger_setup.py's own module docstring), and it does not test
composition_root.py or cli/main.py, since neither consumes LoggerSetup
yet -- that wiring is explicitly separate, later work.

Because the "phenopred" logger LoggerSetup configures is a process-wide
singleton owned by Python's logging module (not by LoggerSetup itself),
every test here restores it to a clean, pre-test state in a `finally`
block, so no test's configuration leaks into another test or into the
rest of this repository's test suite.
"""

from __future__ import annotations

import io
import logging

from phenopred.infrastructure.logging.logger_setup import LoggerSetup

_LOGGER_NAME = "phenopred"


def _reset_phenopred_logger() -> None:
    """Restore the "phenopred" logger to an unconfigured state: no
    handlers, level reset to NOTSET (the logging module's own default
    for a freshly created logger).
    """
    logger = logging.getLogger(_LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)


# ---------------------------------------------------------------------------
# 1. Level configuration
# ---------------------------------------------------------------------------


def test_configure_sets_the_phenopred_logger_level() -> None:
    try:
        LoggerSetup().configure(level="DEBUG", stream=io.StringIO())

        assert logging.getLogger(_LOGGER_NAME).level == logging.DEBUG
    finally:
        _reset_phenopred_logger()


def test_configure_defaults_to_info_level() -> None:
    try:
        LoggerSetup().configure(stream=io.StringIO())

        assert logging.getLogger(_LOGGER_NAME).level == logging.INFO
    finally:
        _reset_phenopred_logger()


def test_configure_accepts_lowercase_level_names() -> None:
    try:
        LoggerSetup().configure(level="warning", stream=io.StringIO())

        assert logging.getLogger(_LOGGER_NAME).level == logging.WARNING
    finally:
        _reset_phenopred_logger()


def test_configure_raises_value_error_for_an_unrecognized_level() -> None:
    try:
        try:
            LoggerSetup().configure(level="NOT_A_REAL_LEVEL", stream=io.StringIO())
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "NOT_A_REAL_LEVEL" in str(exc)
    finally:
        _reset_phenopred_logger()


# ---------------------------------------------------------------------------
# 2. Handler/formatter attachment and idempotency
# ---------------------------------------------------------------------------


def test_configure_attaches_exactly_one_stream_handler_with_a_formatter() -> None:
    try:
        LoggerSetup().configure(stream=io.StringIO())

        handlers = logging.getLogger(_LOGGER_NAME).handlers
        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.StreamHandler)
        assert handlers[0].formatter is not None
    finally:
        _reset_phenopred_logger()


def test_configure_is_idempotent_and_does_not_duplicate_handlers() -> None:
    try:
        LoggerSetup().configure(stream=io.StringIO())
        LoggerSetup().configure(stream=io.StringIO())
        LoggerSetup().configure(stream=io.StringIO())

        assert len(logging.getLogger(_LOGGER_NAME).handlers) == 1
    finally:
        _reset_phenopred_logger()


def test_configure_returns_the_phenopred_logger() -> None:
    try:
        returned_logger = LoggerSetup().configure(stream=io.StringIO())

        assert returned_logger is logging.getLogger(_LOGGER_NAME)
    finally:
        _reset_phenopred_logger()


# ---------------------------------------------------------------------------
# 3. Behavioral check: a real module logger's records reach the configured
#    stream, exactly as domain/infrastructure code already logs today
# ---------------------------------------------------------------------------


def test_configure_lets_a_module_logger_reach_the_configured_stream() -> None:
    try:
        captured = io.StringIO()
        LoggerSetup().configure(level="INFO", stream=captured)

        # Mirrors exactly how infrastructure/io/raw_file_loader.py and
        # infrastructure/io/report_writer.py already obtain their own
        # logger today: logging.getLogger(__name__), never anything
        # LoggerSetup-specific.
        module_logger = logging.getLogger("phenopred.infrastructure.io.raw_file_loader")
        module_logger.info("Loaded source file: path=%s", "example.txt")

        output = captured.getvalue()
        assert "Loaded source file: path=example.txt" in output
        assert "INFO" in output
        assert "phenopred.infrastructure.io.raw_file_loader" in output
    finally:
        _reset_phenopred_logger()


def test_configure_below_info_level_suppresses_debug_records() -> None:
    try:
        captured = io.StringIO()
        LoggerSetup().configure(level="INFO", stream=captured)

        module_logger = logging.getLogger("phenopred.some.module")
        module_logger.debug("this should not appear")

        assert captured.getvalue() == ""
    finally:
        _reset_phenopred_logger()


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()