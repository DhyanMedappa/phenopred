# tests/unit/domain/test_entities.py
"""Unit tests for DataRow (FR-4) and ProfilingReport, and each entity's
own enforced (or deliberately absent) invariants.

Mirrors the testing approach established by test_delimiter_detector.py,
test_raw_line_splitter.py, and test_header_resolver.py: small, synthetic,
in-memory fixtures only, no file I/O, exercising exactly the structural
properties named by each entity's own frozen design specification -- and
no more. This suite verifies DataRow and ProfilingReport only; it does
not test or anticipate GenotypeFile, which remains intentionally absent
from entities.py. It does not test ReportBuilder's or
OpenQuestionRegistry's own assembly/selection logic -- only that
ProfilingReport itself holds whatever values it is constructed with,
unaltered.
"""

from __future__ import annotations

import dataclasses

from phenopred.domain.entities import DataRow, ProfilingReport


# ---------------------------------------------------------------------------
# 1. DataRow contract -- correct fields
# ---------------------------------------------------------------------------


def test_data_row_holds_correct_fields() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "A", "G"))
    assert row.line_index == 0
    assert row.fields == ("rs1", "1", "100", "A", "G")


def test_data_row_fields_type_is_tuple() -> None:
    row = DataRow(line_index=0, fields=("a", "b"))
    assert isinstance(row.fields, tuple)


# ---------------------------------------------------------------------------
# 2. DataRow immutability (frozen=True, slots=True)
# ---------------------------------------------------------------------------


def test_data_row_reassignment_of_line_index_raises() -> None:
    row = DataRow(line_index=0, fields=("a",))
    try:
        row.line_index = 5  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def test_data_row_reassignment_of_fields_raises() -> None:
    row = DataRow(line_index=0, fields=("a",))
    try:
        row.fields = ("b",)  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def test_data_row_rejects_new_attribute() -> None:
    row = DataRow(line_index=0, fields=("a",))
    try:
        row.extra = "not allowed"  # type: ignore[attr-defined]
        raise AssertionError("expected AttributeError or TypeError")
    except (AttributeError, TypeError):
        pass


# ---------------------------------------------------------------------------
# 3. line_index invariant: negative rejected, zero accepted
# ---------------------------------------------------------------------------


def test_data_row_rejects_negative_line_index() -> None:
    try:
        DataRow(line_index=-1, fields=("a",))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_data_row_accepts_zero_line_index() -> None:
    row = DataRow(line_index=0, fields=("a",))
    assert row.line_index == 0


def test_data_row_accepts_positive_line_index() -> None:
    row = DataRow(line_index=42, fields=("a",))
    assert row.line_index == 42


# ---------------------------------------------------------------------------
# 4. No validation of fields length or contents
# ---------------------------------------------------------------------------


def test_data_row_accepts_zero_fields() -> None:
    # DataRow must not enforce any minimum field count -- that judgment
    # belongs exclusively to the future MalformedRowCheck.
    row = DataRow(line_index=0, fields=())
    assert row.fields == ()


def test_data_row_accepts_single_field() -> None:
    row = DataRow(line_index=0, fields=("only_one",))
    assert row.fields == ("only_one",)


def test_data_row_accepts_arbitrarily_many_fields() -> None:
    many_fields = tuple(f"f{i}" for i in range(50))
    row = DataRow(line_index=0, fields=many_fields)
    assert row.fields == many_fields


def test_data_row_accepts_empty_string_field_content() -> None:
    row = DataRow(line_index=0, fields=("", "", ""))
    assert row.fields == ("", "", "")


def test_data_row_accepts_non_alphanumeric_field_content() -> None:
    # DataRow performs no content-shape or missing-value judgment.
    row = DataRow(line_index=0, fields=("--", "0", "!!!", "café"))
    assert row.fields == ("--", "0", "!!!", "café")


# ---------------------------------------------------------------------------
# 5. ProfilingReport contract -- correct fields
# ---------------------------------------------------------------------------


def test_profiling_report_holds_correct_fields() -> None:
    report = ProfilingReport(
        source_path="genome.txt",
        comment_block="comment_block_sentinel",
        encoding_profile="encoding_profile_sentinel",
        delimiter="delimiter_sentinel",
        header_info="header_info_sentinel",
        row_count=10,
        column_count_distribution="column_count_distribution_sentinel",
        findings=("finding_sentinel",),
        profiles=("profile_sentinel",),
        open_questions=("open_question_sentinel",),
    )
    assert report.source_path == "genome.txt"
    assert report.comment_block == "comment_block_sentinel"
    assert report.encoding_profile == "encoding_profile_sentinel"
    assert report.delimiter == "delimiter_sentinel"
    assert report.header_info == "header_info_sentinel"
    assert report.row_count == 10
    assert report.column_count_distribution == "column_count_distribution_sentinel"
    assert report.findings == ("finding_sentinel",)
    assert report.profiles == ("profile_sentinel",)
    assert report.open_questions == ("open_question_sentinel",)


# ---------------------------------------------------------------------------
# 6. ProfilingReport immutability (frozen=True, slots=True)
# ---------------------------------------------------------------------------


def _make_profiling_report() -> ProfilingReport:
    return ProfilingReport(
        source_path="genome.txt",
        comment_block="comment_block_sentinel",
        encoding_profile="encoding_profile_sentinel",
        delimiter="delimiter_sentinel",
        header_info="header_info_sentinel",
        row_count=10,
        column_count_distribution=None,
        findings=(),
        profiles=(),
        open_questions=(),
    )


def test_profiling_report_reassignment_of_source_path_raises() -> None:
    report = _make_profiling_report()
    try:
        report.source_path = "other.txt"  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def test_profiling_report_reassignment_of_findings_raises() -> None:
    report = _make_profiling_report()
    try:
        report.findings = ("new_finding",)  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def test_profiling_report_rejects_new_attribute() -> None:
    report = _make_profiling_report()
    try:
        report.extra = "not allowed"  # type: ignore[attr-defined]
        raise AssertionError("expected AttributeError or TypeError")
    except (AttributeError, TypeError):
        pass


# ---------------------------------------------------------------------------
# 7. ProfilingReport enforces no invariant (unlike DataRow)
# ---------------------------------------------------------------------------


def test_profiling_report_accepts_none_column_count_distribution() -> None:
    # Unlike DataRow, ProfilingReport names no invariant of its own --
    # column_count_distribution=None is a legitimate, unrejected value
    # (the "malformed_row_check not injected" case).
    report = ProfilingReport(
        source_path="genome.txt",
        comment_block="comment_block_sentinel",
        encoding_profile="encoding_profile_sentinel",
        delimiter="delimiter_sentinel",
        header_info="header_info_sentinel",
        row_count=0,
        column_count_distribution=None,
        findings=(),
        profiles=(),
        open_questions=(),
    )
    assert report.column_count_distribution is None


def test_profiling_report_accepts_empty_findings_profiles_and_open_questions() -> None:
    report = ProfilingReport(
        source_path="genome.txt",
        comment_block="comment_block_sentinel",
        encoding_profile="encoding_profile_sentinel",
        delimiter="delimiter_sentinel",
        header_info="header_info_sentinel",
        row_count=0,
        column_count_distribution=None,
        findings=(),
        profiles=(),
        open_questions=(),
    )
    assert report.findings == ()
    assert report.profiles == ()
    assert report.open_questions == ()


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()