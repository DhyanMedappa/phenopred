# tests/unit/application/test_composition_root.py
"""Unit tests for composition_root.py's ConfigLoader wiring (Architecture
v1 Section 10/11; the step that follows infrastructure/config/
config_loader.py's own implementation).

Scope discipline: this suite verifies exactly one thing --
build_profile_file_use_case()'s new config_path/explicit-override
resolution, via ConfigLoader, for its four Section-11-scoped keyword
arguments (comment_prefix, header_keyword, delimiter_sample_size,
raw_loader_sample_size). It does not re-test ConfigLoader's own
file-reading/validation behavior (already covered by
tests/unit/infrastructure/config/test_config_loader.py), and it does
not re-test the wired pipeline's correctness end to end (already
covered by tests/unit/integration/test_profile_pipeline.py and
tests/unit/integration/test_cli_end_to_end.py, both of which continue
to call build_profile_file_use_case() with zero arguments).

Per Architecture v1 Section 15.4, no real genotype data is used here --
every fixture is a small, synthetic, in-memory-constructed file written
to pytest's own tmp_path, reproducing only the structural property
(a non-default comment prefix or header keyword) each test needs to
observe.

Where a resolved value has no easily-observable effect on a tiny
fixture's parsed output (delimiter_sample_size, raw_loader_sample_size),
this suite falls back to a direct, documented white-box check of the
constructed collaborator's own attribute, rather than manufacturing an
artificial black-box scenario.
"""

from __future__ import annotations

import io
import json
import logging
import shutil
import tempfile
from pathlib import Path

import pytest

from phenopred.application.composition_root import (
    build_profile_file_use_case,
    configure_logging,
)
from phenopred.infrastructure.config.config_loader import ConfigLoadError


def _make_temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="phenopred_composition_root_test_"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _reset_phenopred_logger() -> None:
    """Restore the "phenopred" logger to an unconfigured state, mirroring
    tests/unit/infrastructure/logging/test_logger_setup.py's own
    established discipline: the "phenopred" logger is a process-wide
    singleton owned by Python's logging module, not by this test module,
    so every test that calls configure_logging() must undo it afterward
    to avoid leaking state into other tests in this file or elsewhere in
    the suite.
    """
    logger = logging.getLogger("phenopred")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)


# ---------------------------------------------------------------------------
# 1. Zero-argument construction is unchanged (NFR-3-style regression guard)
# ---------------------------------------------------------------------------


def test_zero_argument_construction_reproduces_the_original_hardcoded_defaults() -> None:
    # These four values are exactly composition_root.py's own former
    # module-level constants (comment_prefix="#", header_keyword="rsid",
    # delimiter_sample_size=50, raw_loader_sample_size=4096). This test
    # exists specifically to prove this step introduced no behavior
    # change for every existing caller, all of which construct with zero
    # arguments (test_profile_pipeline.py, test_cli_end_to_end.py).
    use_case = build_profile_file_use_case()

    assert use_case._line_splitter._comment_prefix == "#"
    assert use_case._header_resolver._header_keyword == "rsid"
    assert use_case._delimiter_detector._sample_size == 50
    assert use_case._file_loader._sample_size == 4096


# ---------------------------------------------------------------------------
# 2. comment_prefix / header_keyword flow through to real parsing behavior
# ---------------------------------------------------------------------------


def test_config_file_comment_prefix_and_header_keyword_affect_real_parsing() -> None:
    # A synthetic fixture using a deliberately non-default convention:
    # "//" comments (not "#") and "marker" as the header keyword (not
    # "rsid"). If config_path's values were not genuinely threaded
    # through to RawLineSplitter/HeaderResolver, this file would be
    # parsed incorrectly (the "//" line would be treated as data, and
    # the header row would not be recognized as a header at all).
    tmp_dir = _make_temp_dir()
    try:
        fixture_path = tmp_dir / "sample.txt"
        fixture_path.write_text(
            "// this file uses a non-default comment convention\n"
            "marker\tchromosome\tposition\tgenotype\n"
            "rs1\t1\t100\tAA\n",
            encoding="utf-8",
        )

        config_path = tmp_dir / "config.json"
        _write_json(
            config_path,
            {"comment_prefix": "//", "header_keyword": "marker"},
        )

        # rsid_keyword is passed directly (not via the config file) only
        # to keep this synthetic fixture internally self-consistent --
        # the fixture's RSID column is itself named "marker", so
        # ColumnIdentityResolver (a separate, non-ConfigLoader-scoped
        # collaborator; see composition_root.py's own module docstring)
        # must be told to look for that same name. This is incidental to
        # what this test actually verifies: that comment_prefix and
        # header_keyword genuinely flow through from the config file.
        use_case = build_profile_file_use_case(
            config_path=config_path, rsid_keyword="marker"
        )
        result = use_case.execute(fixture_path)

        assert result["comment_block"].count == 1
        assert result["header_info"].form == "uncommented_row"
        assert result["header_info"].resolved_columns == (
            "marker",
            "chromosome",
            "position",
            "genotype",
        )
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 3. Explicit keyword argument still wins over the config file's own value
# ---------------------------------------------------------------------------


def test_explicit_keyword_argument_overrides_config_file_value() -> None:
    tmp_dir = _make_temp_dir()
    try:
        fixture_path = tmp_dir / "sample.txt"
        fixture_path.write_text(
            "! this file's real comment marker is '!', not '//'\n"
            "rsid\tchromosome\tposition\tgenotype\n"
            "rs1\t1\t100\tAA\n",
            encoding="utf-8",
        )

        config_path = tmp_dir / "config.json"
        _write_json(config_path, {"comment_prefix": "//"})

        # The config file says "//"; the explicit keyword argument to
        # build_profile_file_use_case() says "!" -- the explicit
        # argument must win, exactly mirroring ConfigLoader.load()'s own
        # documented precedence (already unit-tested in isolation by
        # test_config_loader.py; this test proves that precedence holds
        # through the real, wired composition root too).
        use_case = build_profile_file_use_case(
            config_path=config_path, comment_prefix="!"
        )
        result = use_case.execute(fixture_path)

        assert result["comment_block"].count == 1
        assert result["header_info"].form == "uncommented_row"
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 4. Sample-size fields are threaded through (white-box, documented above)
# ---------------------------------------------------------------------------


def test_config_file_sample_sizes_are_injected_into_the_real_collaborators() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        _write_json(
            config_path,
            {"delimiter_sample_size": 7, "raw_loader_sample_size": 128},
        )

        use_case = build_profile_file_use_case(config_path=config_path)

        assert use_case._delimiter_detector._sample_size == 7
        assert use_case._file_loader._sample_size == 128
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 5. The six non-ConfigLoader-scoped keyword arguments are unaffected
# ---------------------------------------------------------------------------


def test_non_configloader_scoped_keyword_arguments_still_work_unchanged() -> None:
    # rsid_keyword/chromosome_keyword/position_keyword/etc. are outside
    # ConfigLoader's scope by design (see composition_root.py's own
    # module docstring) and must keep behaving exactly as before this
    # change -- overridable directly, with no config-file involvement.
    use_case = build_profile_file_use_case(rsid_keyword="snp_id")

    assert use_case._column_identity_resolver._rsid_keyword == "snp_id"


# ---------------------------------------------------------------------------
# 6. A bad config_path propagates ConfigLoadError, uncaught
# ---------------------------------------------------------------------------


def test_nonexistent_config_path_raises_config_load_error() -> None:
    missing_path = Path(tempfile.gettempdir()) / "phenopred_no_such_config.json"

    with pytest.raises(ConfigLoadError):
        build_profile_file_use_case(config_path=missing_path)


# ---------------------------------------------------------------------------
# 7. configure_logging() -- ConfigLoader -> LoggerSetup wiring
# ---------------------------------------------------------------------------


def test_configure_logging_defaults_to_info_with_no_arguments() -> None:
    try:
        configure_logging()

        assert logging.getLogger("phenopred").level == logging.INFO
    finally:
        _reset_phenopred_logger()


def test_configure_logging_reads_level_from_a_config_file() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        _write_json(config_path, {"logging_level": "DEBUG"})

        configure_logging(config_path=config_path)

        assert logging.getLogger("phenopred").level == logging.DEBUG
    finally:
        _reset_phenopred_logger()
        shutil.rmtree(tmp_dir)


def test_configure_logging_explicit_level_overrides_config_file_value() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        _write_json(config_path, {"logging_level": "DEBUG"})

        configure_logging(config_path=config_path, level="WARNING")

        assert logging.getLogger("phenopred").level == logging.WARNING
    finally:
        _reset_phenopred_logger()
        shutil.rmtree(tmp_dir)


def test_configure_logging_lets_a_real_module_logger_reach_stderr_via_full_wiring() -> None:
    # Proves the full chain -- composition_root.configure_logging() ->
    # ConfigLoader -> LoggerSetup -- actually works end to end, the same
    # way test_config_file_comment_prefix_and_header_keyword_affect_real_parsing
    # (above) proves the ConfigLoader -> build_profile_file_use_case()
    # chain works end to end, rather than re-testing LoggerSetup's own
    # unit behavior (already covered by test_logger_setup.py).
    try:
        configure_logging()

        logger = logging.getLogger("phenopred")
        handler = logger.handlers[0]
        captured = io.StringIO()
        handler.stream = captured

        module_logger = logging.getLogger(
            "phenopred.infrastructure.io.raw_file_loader"
        )
        module_logger.info("Loaded source file: path=%s", "example.txt")

        assert "Loaded source file: path=example.txt" in captured.getvalue()
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