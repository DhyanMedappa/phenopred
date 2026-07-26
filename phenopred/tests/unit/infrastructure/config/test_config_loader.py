# tests/unit/infrastructure/config/test_config_loader.py
"""Unit tests for ConfigLoader (Architecture v1 Section 5/10/11).

Mirrors the testing approach already established by
tests/unit/integration/test_report_writer.py: plain, hand-written
assertion functions, no framework-specific fixtures required.

Scope discipline: this suite verifies ConfigLoader's own file-reading,
precedence-resolution, and validation behavior only. It does not test
composition_root.py or cli/main.py, since neither consumes ConfigLoader
yet -- that wiring is explicitly separate, later work (see
config_loader.py's own module docstring).
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import tempfile
from pathlib import Path

from phenopred.infrastructure.config.config_loader import (
    ConfigLoader,
    ConfigLoadError,
    RunConfig,
)


def _make_temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="phenopred_config_loader_test_"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Defaults, with no config file and no overrides
# ---------------------------------------------------------------------------


def test_load_returns_documented_defaults_when_nothing_supplied() -> None:
    loader = ConfigLoader()

    config = loader.load()

    assert config == RunConfig(
        comment_prefix="#",
        header_keyword="rsid",
        output_location=None,
        logging_level="INFO",
        delimiter_sample_size=50,
        raw_loader_sample_size=4096,
    )


# ---------------------------------------------------------------------------
# 2. Reading values from a JSON configuration file
# ---------------------------------------------------------------------------


def test_load_reads_every_known_value_from_a_json_config_file() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        _write_json(
            config_path,
            {
                "comment_prefix": ";",
                "header_keyword": "marker",
                "output_location": "/reports",
                "logging_level": "DEBUG",
                "delimiter_sample_size": 25,
                "raw_loader_sample_size": 2048,
            },
        )
        loader = ConfigLoader()

        config = loader.load(config_path)

        assert config.comment_prefix == ";"
        assert config.header_keyword == "marker"
        assert config.output_location == "/reports"
        assert config.logging_level == "DEBUG"
        assert config.delimiter_sample_size == 25
        assert config.raw_loader_sample_size == 2048
    finally:
        shutil.rmtree(tmp_dir)


def test_load_accepts_a_string_config_path_as_well_as_a_path_object() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        _write_json(config_path, {"comment_prefix": "%"})
        loader = ConfigLoader()

        config = loader.load(str(config_path))

        assert config.comment_prefix == "%"
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 3. Partial config files fall back to defaults for every omitted key
# ---------------------------------------------------------------------------


def test_load_falls_back_to_defaults_for_keys_absent_from_the_config_file() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        _write_json(config_path, {"comment_prefix": ";"})
        loader = ConfigLoader()

        config = loader.load(config_path)

        assert config.comment_prefix == ";"
        assert config.header_keyword == "rsid"
        assert config.output_location is None
        assert config.logging_level == "INFO"
        assert config.delimiter_sample_size == 50
        assert config.raw_loader_sample_size == 4096
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 4. Precedence: explicit override > config file > default
# ---------------------------------------------------------------------------


def test_explicit_override_takes_precedence_over_config_file_value() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        _write_json(config_path, {"comment_prefix": ";"})
        loader = ConfigLoader()

        config = loader.load(config_path, comment_prefix="!")

        assert config.comment_prefix == "!"
    finally:
        shutil.rmtree(tmp_dir)


def test_explicit_override_takes_precedence_over_default_with_no_config_file() -> None:
    loader = ConfigLoader()

    config = loader.load(header_keyword="marker_name")

    assert config.header_keyword == "marker_name"
    # Every other field is untouched by this single override.
    assert config.comment_prefix == "#"
    assert config.delimiter_sample_size == 50


# ---------------------------------------------------------------------------
# 5. Failure modes -> ConfigLoadError
# ---------------------------------------------------------------------------


def test_load_raises_config_load_error_for_a_nonexistent_config_path() -> None:
    loader = ConfigLoader()
    missing_path = Path(tempfile.gettempdir()) / "phenopred_does_not_exist.json"

    try:
        loader.load(missing_path)
        raise AssertionError("expected ConfigLoadError")
    except ConfigLoadError as exc:
        assert str(missing_path) in str(exc)


def test_load_raises_config_load_error_for_invalid_json() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        config_path.write_text("{not valid json", encoding="utf-8")
        loader = ConfigLoader()

        try:
            loader.load(config_path)
            raise AssertionError("expected ConfigLoadError")
        except ConfigLoadError:
            pass
    finally:
        shutil.rmtree(tmp_dir)


def test_load_raises_config_load_error_when_top_level_json_is_not_an_object() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        config_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
        loader = ConfigLoader()

        try:
            loader.load(config_path)
            raise AssertionError("expected ConfigLoadError")
        except ConfigLoadError:
            pass
    finally:
        shutil.rmtree(tmp_dir)


def test_load_raises_config_load_error_for_an_unknown_config_key() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        _write_json(config_path, {"comment_prefix": ";", "not_a_real_key": True})
        loader = ConfigLoader()

        try:
            loader.load(config_path)
            raise AssertionError("expected ConfigLoadError")
        except ConfigLoadError as exc:
            assert "not_a_real_key" in str(exc)
    finally:
        shutil.rmtree(tmp_dir)


def test_load_raises_config_load_error_when_config_path_is_a_directory() -> None:
    tmp_dir = _make_temp_dir()
    try:
        loader = ConfigLoader()

        try:
            loader.load(tmp_dir)
            raise AssertionError("expected ConfigLoadError")
        except ConfigLoadError:
            pass
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 6. Determinism (NFR-3) and immutability
# ---------------------------------------------------------------------------


def test_load_is_deterministic_given_the_same_inputs() -> None:
    tmp_dir = _make_temp_dir()
    try:
        config_path = tmp_dir / "config.json"
        _write_json(config_path, {"comment_prefix": ";", "delimiter_sample_size": 10})
        loader = ConfigLoader()

        first = loader.load(config_path, header_keyword="marker")
        second = loader.load(config_path, header_keyword="marker")

        assert first == second
    finally:
        shutil.rmtree(tmp_dir)


def test_run_config_is_immutable() -> None:
    config = ConfigLoader().load()

    try:
        config.comment_prefix = "!"  # type: ignore[misc]
        raise AssertionError("expected a dataclasses.FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()
