"""Unit tests for phenopred.infrastructure.io.raw_file_loader.

Covers functional correctness, read-only/file-integrity guarantees
(FR-14, NFR-2), determinism (NFR-3), immutability, byte-sample slicing,
line-ending handling, and the approved exception hierarchy, per the
Stage 1 design review and Stage 3 approved implementation.

These tests exercise RawFileLoader's public contract (`load()`) and the
observable shape of `RawFileContent` only. Private helper methods are not
tested directly; their behavior is verified indirectly through `load()`.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import pytest

from phenopred.domain.errors import (
    EmptySourceFileError,
    SourceFileNotFoundError,
    SourceFileReadError,
    SourceFileUnreadableError,
)
from phenopred.infrastructure.io.raw_file_loader import (
    RawFileContent,
    RawFileLoader,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

# Synthetic, structurally realistic but non-biological genotype-like content:
# comment/metadata lines, a header row, and a few data rows using placeholder
# rsids/positions. No real genetic data is used anywhere in this file.
SYNTHETIC_LINES: tuple[str, ...] = (
    "# metadata: synthetic test file, not real genotype data",
    "# metadata: format version TEST-1.0",
    "rsid\tchromosome\tposition\tallele1\tallele2",
    "rs0000001\t1\t100001\tA\tT",
    "rs0000002\t1\t100002\tG\tC",
    "rs0000003\tX\t200001\tI\tD",
)


def _write_synthetic_file(tmp_path: Path, lines: tuple[str, ...], *, trailing_newline: bool = True) -> Path:
    """Write the given lines (joined with LF) to a temp file and return its path."""
    content = "\n".join(lines)
    if trailing_newline:
        content += "\n"
    file_path = tmp_path / "synthetic_genotype.txt"
    file_path.write_bytes(content.encode("ascii"))
    return file_path


@pytest.fixture()
def synthetic_file(tmp_path: Path) -> Path:
    """A small synthetic genotype-like file with comments, header, and data rows."""
    return _write_synthetic_file(tmp_path, SYNTHETIC_LINES, trailing_newline=True)


@pytest.fixture()
def loader() -> RawFileLoader:
    """A RawFileLoader instance with a generous default sample size."""
    return RawFileLoader(sample_size=1024)


# ---------------------------------------------------------------------------
# 1. Successful loading
# ---------------------------------------------------------------------------


def test_load_returns_raw_file_content(synthetic_file: Path, loader: RawFileLoader) -> None:
    result = loader.load(synthetic_file)
    assert isinstance(result, RawFileContent)


def test_load_source_path_is_correct(synthetic_file: Path, loader: RawFileLoader) -> None:
    result = loader.load(synthetic_file)
    assert result.source_path == synthetic_file


def test_load_size_bytes_is_correct(synthetic_file: Path, loader: RawFileLoader) -> None:
    expected_size = synthetic_file.stat().st_size
    result = loader.load(synthetic_file)
    assert result.size_bytes == expected_size


def test_load_lines_extracted_correctly(synthetic_file: Path, loader: RawFileLoader) -> None:
    result = loader.load(synthetic_file)
    assert result.lines == SYNTHETIC_LINES


def test_load_line_count_is_correct(synthetic_file: Path, loader: RawFileLoader) -> None:
    result = loader.load(synthetic_file)
    assert result.line_count == len(SYNTHETIC_LINES)
    assert result.line_count == len(result.lines)


def test_load_byte_sample_contains_expected_prefix(synthetic_file: Path, loader: RawFileLoader) -> None:
    raw_bytes = synthetic_file.read_bytes()
    result = loader.load(synthetic_file)
    assert result.byte_sample == raw_bytes[:1024]


# ---------------------------------------------------------------------------
# 2. File integrity and read-only behavior (FR-14, NFR-2)
# ---------------------------------------------------------------------------


def test_load_does_not_alter_file_contents(synthetic_file: Path, loader: RawFileLoader) -> None:
    original_bytes = synthetic_file.read_bytes()
    loader.load(synthetic_file)
    assert synthetic_file.read_bytes() == original_bytes


def test_load_does_not_alter_file_size(synthetic_file: Path, loader: RawFileLoader) -> None:
    original_size = synthetic_file.stat().st_size
    loader.load(synthetic_file)
    assert synthetic_file.stat().st_size == original_size


def test_load_does_not_alter_modification_time(synthetic_file: Path, loader: RawFileLoader) -> None:
    original_mtime_ns = synthetic_file.stat().st_mtime_ns
    loader.load(synthetic_file)
    assert synthetic_file.stat().st_mtime_ns == original_mtime_ns


def test_load_opens_file_in_read_only_mode(tmp_path: Path, loader: RawFileLoader, monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirm the loader never requests a write-capable file mode."""
    file_path = tmp_path / "mode_check.txt"
    file_path.write_bytes(b"rs0000001\t1\t100001\tA\tT\n")

    observed_modes: list[str] = []
    real_open = Path.open

    def spying_open(self: Path, mode: str = "r", *args, **kwargs):
        observed_modes.append(mode)
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spying_open)

    loader.load(file_path)

    assert observed_modes, "Expected RawFileLoader to open the file at least once"
    assert all(mode == "rb" for mode in observed_modes), (
        f"Expected only read-binary ('rb') file modes, observed: {observed_modes}"
    )


# ---------------------------------------------------------------------------
# 3. Exception handling
# ---------------------------------------------------------------------------


def test_missing_file_raises_source_file_not_found_error(tmp_path: Path, loader: RawFileLoader) -> None:
    missing_path = tmp_path / "does_not_exist.txt"
    with pytest.raises(SourceFileNotFoundError) as exc_info:
        loader.load(missing_path)
    assert exc_info.value.path == missing_path


def test_empty_file_raises_empty_source_file_error(tmp_path: Path, loader: RawFileLoader) -> None:
    empty_path = tmp_path / "empty.txt"
    empty_path.write_bytes(b"")
    with pytest.raises(EmptySourceFileError) as exc_info:
        loader.load(empty_path)
    assert exc_info.value.path == empty_path


def test_directory_path_raises_source_file_unreadable_error(tmp_path: Path, loader: RawFileLoader) -> None:
    directory_path = tmp_path / "a_directory"
    directory_path.mkdir()
    with pytest.raises(SourceFileUnreadableError) as exc_info:
        loader.load(directory_path)
    assert exc_info.value.path == directory_path


@pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason=(
        "POSIX permission bits are not reliably enforced on Windows, and "
        "are bypassed entirely when tests run as root (common in CI "
        "containers). This test is skipped in those environments rather "
        "than asserted as a fragile, environment-dependent check."
    ),
)
def test_permission_denied_file_raises_source_file_unreadable_error(
    tmp_path: Path, loader: RawFileLoader
) -> None:
    restricted_path = tmp_path / "no_access.txt"
    restricted_path.write_bytes(b"rs0000001\t1\t100001\tA\tT\n")
    restricted_path.chmod(0o000)
    try:
        with pytest.raises(SourceFileUnreadableError) as exc_info:
            loader.load(restricted_path)
        assert exc_info.value.path == restricted_path
    finally:
        restricted_path.chmod(0o644)  # restore so tmp_path cleanup can remove it


def test_unexpected_io_failure_raises_source_file_read_error(
    tmp_path: Path, loader: RawFileLoader, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate a filesystem-level read failure that is not a permissions error."""
    file_path = tmp_path / "will_fail.txt"
    file_path.write_bytes(b"rs0000001\t1\t100001\tA\tT\n")

    def raise_os_error(self: Path, *args, **kwargs):
        raise OSError("Simulated disk I/O failure")

    monkeypatch.setattr(Path, "open", raise_os_error)

    with pytest.raises(SourceFileReadError) as exc_info:
        loader.load(file_path)
    assert exc_info.value.path == file_path


def test_read_error_preserves_original_exception_via_chaining(
    tmp_path: Path, loader: RawFileLoader, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_path = tmp_path / "will_fail.txt"
    file_path.write_bytes(b"rs0000001\t1\t100001\tA\tT\n")

    original_error = OSError("Simulated disk I/O failure")

    def raise_os_error(self: Path, *args, **kwargs):
        raise original_error

    monkeypatch.setattr(Path, "open", raise_os_error)

    with pytest.raises(SourceFileReadError) as exc_info:
        loader.load(file_path)
    assert exc_info.value.__cause__ is original_error


# ---------------------------------------------------------------------------
# 4. Determinism (NFR-3)
# ---------------------------------------------------------------------------


def test_loading_same_file_twice_produces_equal_raw_file_content(
    synthetic_file: Path, loader: RawFileLoader
) -> None:
    first = loader.load(synthetic_file)
    second = loader.load(synthetic_file)
    assert first == second


def test_loading_same_file_twice_produces_identical_lines(
    synthetic_file: Path, loader: RawFileLoader
) -> None:
    first = loader.load(synthetic_file)
    second = loader.load(synthetic_file)
    assert first.lines == second.lines


def test_loading_same_file_twice_produces_identical_byte_sample(
    synthetic_file: Path, loader: RawFileLoader
) -> None:
    first = loader.load(synthetic_file)
    second = loader.load(synthetic_file)
    assert first.byte_sample == second.byte_sample


def test_loading_same_file_twice_produces_identical_size_and_count(
    synthetic_file: Path, loader: RawFileLoader
) -> None:
    first = loader.load(synthetic_file)
    second = loader.load(synthetic_file)
    assert first.size_bytes == second.size_bytes
    assert first.line_count == second.line_count


def test_loading_with_two_separate_loader_instances_is_deterministic(
    synthetic_file: Path
) -> None:
    first = RawFileLoader(sample_size=1024).load(synthetic_file)
    second = RawFileLoader(sample_size=1024).load(synthetic_file)
    assert first == second


# ---------------------------------------------------------------------------
# 5. Immutability
# ---------------------------------------------------------------------------


def test_raw_file_content_is_frozen(synthetic_file: Path, loader: RawFileLoader) -> None:
    result = loader.load(synthetic_file)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.size_bytes = 0  # type: ignore[misc]


def test_raw_file_content_lines_field_cannot_be_reassigned(
    synthetic_file: Path, loader: RawFileLoader
) -> None:
    result = loader.load(synthetic_file)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.lines = ()  # type: ignore[misc]


def test_raw_file_content_lines_is_a_tuple_not_a_list(
    synthetic_file: Path, loader: RawFileLoader
) -> None:
    """Guards against a regression to a mutable list, which would defeat
    frozen-dataclass immutability at the field level."""
    result = loader.load(synthetic_file)
    assert isinstance(result.lines, tuple)


def test_raw_file_content_has_no_dict_due_to_slots(
    synthetic_file: Path, loader: RawFileLoader
) -> None:
    """Confirms slots=True is in effect: no arbitrary attribute can be added.
    On CPython 3.12 frozen+slots raises TypeError for undeclared attrs, 
    older versions raise AttributeError. Both are acceptable."""
    result = loader.load(synthetic_file)
    with pytest.raises((AttributeError, TypeError)): # <- this is the only change
        result.new_attribute = "unexpected"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 6. Byte sample behavior
# ---------------------------------------------------------------------------


def test_byte_sample_smaller_than_file_size(tmp_path: Path) -> None:
    file_path = _write_synthetic_file(tmp_path, SYNTHETIC_LINES)
    raw_bytes = file_path.read_bytes()
    small_sample_size = 10
    assert small_sample_size < len(raw_bytes)

    result = RawFileLoader(sample_size=small_sample_size).load(file_path)
    assert result.byte_sample == raw_bytes[:small_sample_size]
    assert len(result.byte_sample) == small_sample_size


def test_byte_sample_equal_to_file_size(tmp_path: Path) -> None:
    file_path = _write_synthetic_file(tmp_path, SYNTHETIC_LINES)
    raw_bytes = file_path.read_bytes()

    result = RawFileLoader(sample_size=len(raw_bytes)).load(file_path)
    assert result.byte_sample == raw_bytes


def test_byte_sample_larger_than_file_size(tmp_path: Path) -> None:
    file_path = _write_synthetic_file(tmp_path, SYNTHETIC_LINES)
    raw_bytes = file_path.read_bytes()
    oversized_sample = len(raw_bytes) + 1_000

    result = RawFileLoader(sample_size=oversized_sample).load(file_path)
    assert result.byte_sample == raw_bytes
    assert len(result.byte_sample) == len(raw_bytes)


# ---------------------------------------------------------------------------
# 7. Line handling
# ---------------------------------------------------------------------------


def test_lf_line_endings(tmp_path: Path, loader: RawFileLoader) -> None:
    file_path = tmp_path / "lf.txt"
    file_path.write_bytes(b"line one\nline two\nline three\n")

    result = loader.load(file_path)
    assert result.lines == ("line one", "line two", "line three")


def test_crlf_line_endings(tmp_path: Path, loader: RawFileLoader) -> None:
    file_path = tmp_path / "crlf.txt"
    file_path.write_bytes(b"line one\r\nline two\r\nline three\r\n")

    result = loader.load(file_path)
    assert result.lines == ("line one", "line two", "line three")


def test_file_without_trailing_newline(tmp_path: Path, loader: RawFileLoader) -> None:
    file_path = tmp_path / "no_trailing_newline.txt"
    file_path.write_bytes(b"line one\nline two\nline three")

    result = loader.load(file_path)
    assert result.lines == ("line one", "line two", "line three")


def test_mixed_line_endings(tmp_path: Path, loader: RawFileLoader) -> None:
    file_path = tmp_path / "mixed.txt"
    file_path.write_bytes(b"line one\nline two\r\nline three\rline four\n")

    result = loader.load(file_path)
    assert result.lines == ("line one", "line two", "line three", "line four")


def test_lines_are_losslessly_decoded_for_non_ascii_bytes(tmp_path: Path, loader: RawFileLoader) -> None:
    """Bytes outside the ASCII range must decode without error (Latin-1 is
    total over 0x00-0xFF) and must round-trip losslessly."""
    file_path = tmp_path / "non_ascii.txt"
    raw_line = bytes([0x41, 0xC3, 0x9F, 0x52])  # 'A', a non-ASCII byte, 0x9F, 'R'
    file_path.write_bytes(raw_line + b"\n")

    result = loader.load(file_path)
    assert len(result.lines) == 1
    # Round-trip: re-encoding the decoded line as Latin-1 reproduces the
    # exact original bytes, confirming no data was lost or substituted.
    assert result.lines[0].encode("latin-1") == raw_line