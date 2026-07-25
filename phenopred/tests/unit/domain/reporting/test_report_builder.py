# tests/unit/domain/reporting/test_report_builder.py
"""Unit tests for ReportBuilder (SRS Section 7, Architecture v1
Section 5/7.1/9).

Mirrors the testing approach established by
tests/unit/application/test_profile_file_use_case.py: a lightweight,
hand-written fake for ReportBuilder's single constructor-injected
collaborator (OpenQuestionRegistry), each exposing only the one method
ReportBuilder actually calls on it, recording received arguments and
returning a fixed sentinel. This isolates ReportBuilder's own assembly
and ordering responsibility from OpenQuestionRegistry's own selection
logic, which is separately and exhaustively covered by
test_open_question_registry.py.

Scope discipline: this suite verifies ReportBuilder.build()'s own
assembly, field pass-through, and deterministic findings/profiles
ordering only. It does not test OpenQuestionRegistry's own selection
logic, ProfileFileUseCase, or any dependency-injection wiring performed
by the composition root.
"""

from __future__ import annotations

from phenopred.domain.entities import ProfilingReport
from phenopred.domain.reporting.report_builder import ReportBuilder
from phenopred.domain.value_objects import (
    ChromosomeLabelInventory,
    ColumnCountDistribution,
    Finding,
    GenotypeLayoutProfile,
    IndelHaploidProfile,
)

# ---------------------------------------------------------------------------
# Lightweight fake collaborator -- exposes only the one method
# ReportBuilder actually calls on it.
# ---------------------------------------------------------------------------


class _FakeOpenQuestionRegistry:
    def __init__(self, open_questions_result=()):
        self._open_questions_result = open_questions_result
        self.received_findings = None
        self.received_profiles = None

    def applicable_for(self, findings, profiles):
        self.received_findings = findings
        self.received_profiles = profiles
        return self._open_questions_result


def _make_finding(check_name: str) -> Finding:
    return Finding(
        check_name=check_name,
        description="fake_description",
        count=0,
        examples=(),
        affected_row_refs=(),
    )


def _build(
    report_builder,
    findings=None,
    profiles=None,
    column_count_distribution=None,
    row_count=0,
    source_path="genome.txt",
    comment_block="comment_block_sentinel",
    encoding_profile="encoding_profile_sentinel",
    delimiter="delimiter_sentinel",
    header_info="header_info_sentinel",
) -> ProfilingReport:
    return report_builder.build(
        source_path=source_path,
        comment_block=comment_block,
        encoding_profile=encoding_profile,
        delimiter=delimiter,
        header_info=header_info,
        row_count=row_count,
        column_count_distribution=column_count_distribution,
        findings=findings if findings is not None else {},
        profiles=profiles if profiles is not None else {},
    )


# ---------------------------------------------------------------------------
# 1. Scalar field pass-through
# ---------------------------------------------------------------------------


def test_build_carries_scalar_fields_through_unaltered() -> None:
    report_builder = ReportBuilder(open_question_registry=_FakeOpenQuestionRegistry())

    report = _build(
        report_builder,
        source_path="genome.txt",
        comment_block="comment_block_sentinel",
        encoding_profile="encoding_profile_sentinel",
        delimiter="delimiter_sentinel",
        header_info="header_info_sentinel",
        row_count=7,
    )

    assert isinstance(report, ProfilingReport)
    assert report.source_path == "genome.txt"
    assert report.comment_block == "comment_block_sentinel"
    assert report.encoding_profile == "encoding_profile_sentinel"
    assert report.delimiter == "delimiter_sentinel"
    assert report.header_info == "header_info_sentinel"
    assert report.row_count == 7


# ---------------------------------------------------------------------------
# 2. Findings ordering (NFR-3, NFR-6)
# ---------------------------------------------------------------------------


def test_build_orders_findings_ascending_by_check_name_regardless_of_input_order() -> None:
    findings = {
        "missing_value_scanner": _make_finding("missing_value_scanner"),
        "duplicate_chr_pos_check": _make_finding("duplicate_chr_pos_check"),
        "malformed_row_check": _make_finding("malformed_row_check"),
        "duplicate_header_check": _make_finding("duplicate_header_check"),
        "duplicate_rsid_check": _make_finding("duplicate_rsid_check"),
    }
    report_builder = ReportBuilder(open_question_registry=_FakeOpenQuestionRegistry())

    report = _build(report_builder, findings=findings)

    assert [finding.check_name for finding in report.findings] == sorted(
        findings.keys()
    )


def test_findings_ordering_is_independent_of_dict_insertion_order() -> None:
    findings_forward = {
        "malformed_row_check": _make_finding("malformed_row_check"),
        "duplicate_rsid_check": _make_finding("duplicate_rsid_check"),
    }
    findings_reversed = {
        key: findings_forward[key] for key in reversed(list(findings_forward.keys()))
    }

    report_builder_a = ReportBuilder(open_question_registry=_FakeOpenQuestionRegistry())
    report_builder_b = ReportBuilder(open_question_registry=_FakeOpenQuestionRegistry())

    report_a = _build(report_builder_a, findings=findings_forward)
    report_b = _build(report_builder_b, findings=findings_reversed)

    assert report_a.findings == report_b.findings


# ---------------------------------------------------------------------------
# 3. Profiles ordering (NFR-3, NFR-6)
# ---------------------------------------------------------------------------


def test_build_orders_profiles_ascending_by_profiler_name_regardless_of_input_order() -> None:
    profiles = {
        "genotype_layout_classifier": GenotypeLayoutProfile(
            profiler_name="genotype_layout_classifier",
            layout_kind="two_column_allele",
            column_length_distributions=(),
        ),
        "chromosome_label_profiler": ChromosomeLabelInventory(
            profiler_name="chromosome_label_profiler",
            label_counts=(),
        ),
        "indel_haploid_classifier": IndelHaploidProfile(
            profiler_name="indel_haploid_classifier",
            applicable=False,
            indel_token_counts=(),
            haploid_count=0,
            diploid_count=0,
        ),
    }
    report_builder = ReportBuilder(open_question_registry=_FakeOpenQuestionRegistry())

    report = _build(report_builder, profiles=profiles)

    assert [profile.profiler_name for profile in report.profiles] == sorted(
        profiles.keys()
    )


# ---------------------------------------------------------------------------
# 4. OpenQuestionRegistry delegation
# ---------------------------------------------------------------------------


def test_open_question_registry_receives_the_same_ordered_findings_and_profiles_as_the_report() -> None:
    findings = {
        "malformed_row_check": _make_finding("malformed_row_check"),
        "duplicate_rsid_check": _make_finding("duplicate_rsid_check"),
    }
    profiles = {
        "genotype_layout_classifier": GenotypeLayoutProfile(
            profiler_name="genotype_layout_classifier",
            layout_kind="two_column_allele",
            column_length_distributions=(),
        ),
    }
    open_question_registry = _FakeOpenQuestionRegistry()
    report_builder = ReportBuilder(open_question_registry=open_question_registry)

    report = _build(report_builder, findings=findings, profiles=profiles)

    assert open_question_registry.received_findings == report.findings
    assert open_question_registry.received_profiles == report.profiles


def test_report_open_questions_is_exactly_what_registry_returns() -> None:
    open_questions_result = ("open_question_sentinel_1", "open_question_sentinel_2")
    report_builder = ReportBuilder(
        open_question_registry=_FakeOpenQuestionRegistry(
            open_questions_result=open_questions_result
        )
    )

    report = _build(report_builder)

    assert report.open_questions is open_questions_result


# ---------------------------------------------------------------------------
# 5. column_count_distribution pass-through
# ---------------------------------------------------------------------------


def test_build_accepts_none_column_count_distribution() -> None:
    report_builder = ReportBuilder(open_question_registry=_FakeOpenQuestionRegistry())

    report = _build(report_builder, column_count_distribution=None)

    assert report.column_count_distribution is None


def test_build_carries_real_column_count_distribution_through_unaltered() -> None:
    distribution = ColumnCountDistribution(
        check_name="malformed_row_check",
        counts_by_column_count=((5, 10),),
        modal_count=5,
    )
    report_builder = ReportBuilder(open_question_registry=_FakeOpenQuestionRegistry())

    report = _build(report_builder, column_count_distribution=distribution)

    assert report.column_count_distribution is distribution


# ---------------------------------------------------------------------------
# 6. Empty input handling
# ---------------------------------------------------------------------------


def test_build_handles_empty_findings_and_profiles() -> None:
    report_builder = ReportBuilder(open_question_registry=_FakeOpenQuestionRegistry())

    report = _build(report_builder, findings={}, profiles={})

    assert report.findings == ()
    assert report.profiles == ()


# ---------------------------------------------------------------------------
# 7. Determinism
# ---------------------------------------------------------------------------


def test_repeated_build_calls_produce_identical_result() -> None:
    findings = {"malformed_row_check": _make_finding("malformed_row_check")}
    report_builder = ReportBuilder(open_question_registry=_FakeOpenQuestionRegistry())

    first = _build(report_builder, findings=findings, row_count=3)
    second = _build(report_builder, findings=findings, row_count=3)

    assert first == second


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()