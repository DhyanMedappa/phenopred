# tests/unit/application/test_profile_file_use_case.py
"""Unit tests for ProfileFileUseCase orchestration.

ProfileFileUseCase is an application-layer orchestrator: it coordinates
ten constructor-injected collaborators, owns exactly one branching
decision (header-line exclusion based on HeaderInfo.form), translates
two collaborator-local exceptions into PhenoPredIngestionError, and
assembles a plain result dict -- including, per the frozen Reporting
Architecture, retrieving column_count_distribution from an injected
malformed_row_check collaborator (when present) and delegating final
report assembly to an injected report_builder collaborator. It contains
no domain logic of its own.

This suite verifies orchestration behavior only -- dependency wiring,
object propagation, the one application-owned branch, exception
translation, context construction, and result assembly. It uses
lightweight, hand-written fakes for every collaborator, each exposing
only the method(s) ProfileFileUseCase actually calls. It does not
duplicate the already-approved regression suites for HeaderResolver,
ColumnIdentityResolver, RowParser, any QualityCheck, any
GenomicProfiler, ReportBuilder, or OpenQuestionRegistry -- none of
those collaborators' own algorithms are exercised here.
"""

from __future__ import annotations

import ast

from phenopred.application import profile_file_use_case as profile_file_use_case_module
from phenopred.application.profile_file_use_case import ProfileFileUseCase
from phenopred.domain.detection.column_identity_resolver import (
    ColumnIdentityNotResolvedError,
)
from phenopred.domain.detection.delimiter_detector import DelimiterNotDetectedError
from phenopred.domain.errors import PhenoPredIngestionError
from phenopred.domain.value_objects import (
    ChrPosColumnIndices,
    ColumnLayout,
    GenotypeChromosomeColumnIndices,
    HeaderInfo,
)

# ---------------------------------------------------------------------------
# Lightweight fake collaborators -- each exposes only the method(s)
# ProfileFileUseCase actually calls on it.
# ---------------------------------------------------------------------------

class _FakeRawContent:
    def __init__(self, source_path, byte_sample, lines):
        self.source_path = source_path
        self.byte_sample = byte_sample
        self.lines = lines

class _FakeFileLoader:
    def __init__(self, raw_content):
        self._raw_content = raw_content

    def load(self, file_path):
        return self._raw_content

class _FakeEncodingDetector:
    def __init__(self, encoding_profile):
        self._encoding_profile = encoding_profile

    def detect(self, byte_sample):
        return self._encoding_profile

class _FakeLineSplitter:
    def __init__(self, comment_block, candidate_data_lines):
        self._comment_block = comment_block
        self._candidate_data_lines = candidate_data_lines

    def split(self, lines):
        return self._comment_block, self._candidate_data_lines

class _FakeDelimiterDetector:
    def __init__(self, delimiter=None, exception=None):
        self._delimiter = delimiter
        self._exception = exception

    def detect(self, candidate_data_lines):
        if self._exception is not None:
            raise self._exception
        return self._delimiter

class _FakeHeaderResolver:
    def __init__(self, header_info):
        self._header_info = header_info

    def detect(self, comment_block, data_lines, delimiter):
        return self._header_info

class _FakeColumnIdentityResolver:
    def __init__(self, column_layout=None, exception=None):
        self._column_layout = column_layout
        self._exception = exception
        self.received_header_info = None

    def detect(self, header_info):
        self.received_header_info = header_info
        if self._exception is not None:
            raise self._exception
        return self._column_layout

class _FakeRowParser:
    def __init__(self, data_rows):
        self._data_rows = data_rows
        self.received_lines = None
        self.received_delimiter = None

    def parse(self, lines, delimiter):
        self.received_lines = lines
        self.received_delimiter = delimiter
        return self._data_rows

class _FakeQualityCheck:
    def __init__(self, finding, column_count_distribution_result=None):
        self._finding = finding
        self._column_count_distribution_result = column_count_distribution_result
        self.received_args = None
        self.received_column_count_distribution_args = None

    def check(self, *args):
        self.received_args = args
        return self._finding

    def column_count_distribution(self, *args):
        self.received_column_count_distribution_args = args
        return self._column_count_distribution_result

class _FakeGenomicProfiler:
    def __init__(self, profile_result):
        self._profile_result = profile_result
        self.received_args = None

    def profile(self, *args):
        self.received_args = args
        return self._profile_result

class _FakeReportBuilder:
    def __init__(self, report_result="fake_report"):
        self._report_result = report_result
        self.received_kwargs = None

    def build(self, **kwargs):
        self.received_kwargs = kwargs
        return self._report_result

# ---------------------------------------------------------------------------
# Shared construction helper (plain function, not a pytest fixture)
# ---------------------------------------------------------------------------

def _make_use_case(
    file_loader=None,
    line_splitter=None,
    encoding_detector=None,
    delimiter_detector=None,
    header_resolver=None,
    column_identity_resolver=None,
    row_parser=None,
    quality_checks=None,
    genomic_profilers=None,
    report_builder=None,
):
    raw_content = _FakeRawContent(
        source_path="/fake/path.txt",
        byte_sample=b"fake bytes",
        lines=("header_line", "row1", "row2"),
    )
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="rsid\tchromosome\tposition\tgenotype",
    )
    column_layout = ColumnLayout(
        rsid_column_index=0,
        chromosome_column_index=1,
        position_column_index=2,
        designated_column_indices=(3,),
    )
    return ProfileFileUseCase(
        file_loader=file_loader or _FakeFileLoader(raw_content),
        line_splitter=line_splitter
        or _FakeLineSplitter(
            comment_block="fake_comment_block",
            candidate_data_lines=["header_line", "row1", "row2"],
        ),
        encoding_detector=encoding_detector
        or _FakeEncodingDetector("fake_encoding_profile"),
        delimiter_detector=delimiter_detector or _FakeDelimiterDetector("fake_delimiter"),
        header_resolver=header_resolver or _FakeHeaderResolver(header_info),
        column_identity_resolver=column_identity_resolver
        or _FakeColumnIdentityResolver(column_layout),
        row_parser=row_parser or _FakeRowParser("fake_data_rows"),
        quality_checks=quality_checks if quality_checks is not None else {},
        genomic_profilers=genomic_profilers if genomic_profilers is not None else {},
        report_builder=report_builder or _FakeReportBuilder(),
    )

# ---------------------------------------------------------------------------
# 1. Result dict output contract
# ---------------------------------------------------------------------------

def test_result_dict_contains_all_expected_keys() -> None:
    use_case = _make_use_case()
    result = use_case.execute("/fake/path.txt")
    assert set(result.keys()) == {
        "source_path",
        "encoding_profile",
        "comment_block",
        "delimiter",
        "header_info",
        "column_layout",
        "data_rows",
        "findings",
        "skipped_quality_checks",
        "profiles",
        "column_count_distribution",
        "report",
    }

# ---------------------------------------------------------------------------
# 2. Object propagation without copying or transformation
# ---------------------------------------------------------------------------

def test_returned_objects_are_the_exact_objects_collaborators_produced() -> None:
    encoding_profile = "encoding_profile_sentinel"
    comment_block = "comment_block_sentinel"
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="rsid\tchromosome\tposition\tgenotype",
    )
    column_layout = ColumnLayout(
        rsid_column_index=0,
        chromosome_column_index=1,
        position_column_index=2,
        designated_column_indices=(3,),
    )
    data_rows = "data_rows_sentinel"
    finding = "finding_sentinel"
    profile_result = "profile_sentinel"

    raw_content = _FakeRawContent(
        source_path="/fake/path.txt", byte_sample=b"x", lines=("a", "b")
    )
    quality_check = _FakeQualityCheck(finding)
    genomic_profiler = _FakeGenomicProfiler(profile_result)

    use_case = _make_use_case(
        file_loader=_FakeFileLoader(raw_content),
        line_splitter=_FakeLineSplitter(comment_block, ["a", "b"]),
        encoding_detector=_FakeEncodingDetector(encoding_profile),
        header_resolver=_FakeHeaderResolver(header_info),
        column_identity_resolver=_FakeColumnIdentityResolver(column_layout),
        row_parser=_FakeRowParser(data_rows),
        quality_checks={"malformed_row_check": quality_check},
        genomic_profilers={"chromosome_label_profiler": genomic_profiler},
    )

    result = use_case.execute("/fake/path.txt")

    assert result["encoding_profile"] is encoding_profile
    assert result["comment_block"] is comment_block
    assert result["header_info"] is header_info
    assert result["column_layout"] is column_layout
    assert result["data_rows"] is data_rows
    assert result["findings"]["malformed_row_check"] is finding
    assert result["profiles"]["chromosome_label_profiler"] is profile_result

# ---------------------------------------------------------------------------
# 3. Header handling: application-owned exclusion decision
# ---------------------------------------------------------------------------

def test_uncommented_row_header_excludes_first_data_line_before_row_parser() -> None:
    candidate_data_lines = ["header_line", "row1", "row2"]
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="header_line",
    )
    row_parser = _FakeRowParser("fake_data_rows")

    use_case = _make_use_case(
        line_splitter=_FakeLineSplitter("fake_comment_block", candidate_data_lines),
        header_resolver=_FakeHeaderResolver(header_info),
        row_parser=row_parser,
    )
    use_case.execute("/fake/path.txt")

    assert row_parser.received_lines == ["row1", "row2"]

def test_commented_only_header_does_not_exclude_any_data_line() -> None:
    candidate_data_lines = ["row1", "row2"]
    header_info = HeaderInfo(
        form="commented_only",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="# rsid\tchromosome\tposition\tgenotype",
    )
    row_parser = _FakeRowParser("fake_data_rows")

    use_case = _make_use_case(
        line_splitter=_FakeLineSplitter("fake_comment_block", candidate_data_lines),
        header_resolver=_FakeHeaderResolver(header_info),
        row_parser=row_parser,
    )
    use_case.execute("/fake/path.txt")

    assert row_parser.received_lines == candidate_data_lines

def test_absent_header_does_not_exclude_any_data_line() -> None:
    candidate_data_lines = ["row1", "row2"]
    header_info = HeaderInfo(form="absent", resolved_columns=None, source_line=None)
    row_parser = _FakeRowParser("fake_data_rows")

    use_case = _make_use_case(
        line_splitter=_FakeLineSplitter("fake_comment_block", candidate_data_lines),
        header_resolver=_FakeHeaderResolver(header_info),
        row_parser=row_parser,
    )
    use_case.execute("/fake/path.txt")

    assert row_parser.received_lines == candidate_data_lines

# ---------------------------------------------------------------------------
# 4. HeaderInfo propagation
# ---------------------------------------------------------------------------

def test_header_info_passed_unmodified_to_column_identity_resolver() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="rsid\tchromosome\tposition\tgenotype",
    )
    column_identity_resolver = _FakeColumnIdentityResolver(
        ColumnLayout(
            rsid_column_index=0,
            chromosome_column_index=1,
            position_column_index=2,
            designated_column_indices=(3,),
        )
    )

    use_case = _make_use_case(
        header_resolver=_FakeHeaderResolver(header_info),
        column_identity_resolver=column_identity_resolver,
    )
    use_case.execute("/fake/path.txt")

    assert column_identity_resolver.received_header_info is header_info

def test_header_info_passed_unmodified_to_duplicate_header_check() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="rsid\tchromosome\tposition\tgenotype",
    )
    duplicate_header_check = _FakeQualityCheck("fake_finding")

    use_case = _make_use_case(
        header_resolver=_FakeHeaderResolver(header_info),
        quality_checks={"duplicate_header_check": duplicate_header_check},
    )
    use_case.execute("/fake/path.txt")

    received_data_rows, received_header_info = duplicate_header_check.received_args
    assert received_header_info is header_info

# ---------------------------------------------------------------------------
# 5. Exception translation
# ---------------------------------------------------------------------------

def test_delimiter_not_detected_error_translated_to_pheno_pred_ingestion_error() -> None:
    delimiter_detector = _FakeDelimiterDetector(
        exception=DelimiterNotDetectedError("no delimiter found")
    )
    use_case = _make_use_case(delimiter_detector=delimiter_detector)

    try:
        use_case.execute("/fake/path.txt")
        raise AssertionError("expected PhenoPredIngestionError")
    except PhenoPredIngestionError as exc:
        assert exc.path == "/fake/path.txt"

def test_column_identity_not_resolved_error_translated_to_pheno_pred_ingestion_error() -> None:
    column_identity_resolver = _FakeColumnIdentityResolver(
        exception=ColumnIdentityNotResolvedError("no column identity resolved")
    )
    use_case = _make_use_case(column_identity_resolver=column_identity_resolver)

    try:
        use_case.execute("/fake/path.txt")
        raise AssertionError("expected PhenoPredIngestionError")
    except PhenoPredIngestionError as exc:
        assert exc.path == "/fake/path.txt"

# ---------------------------------------------------------------------------
# 6. QualityCheck orchestration: context construction and wiring
# ---------------------------------------------------------------------------

def test_configured_quality_checks_receive_expected_context_objects() -> None:
    data_rows = "fake_data_rows"
    column_layout = ColumnLayout(
        rsid_column_index=0,
        chromosome_column_index=1,
        position_column_index=2,
        designated_column_indices=(3,),
    )
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="rsid\tchromosome\tposition\tgenotype",
    )

    malformed_row_check = _FakeQualityCheck("finding1")
    duplicate_header_check = _FakeQualityCheck("finding2")
    missing_value_scanner = _FakeQualityCheck("finding3")
    duplicate_rsid_check = _FakeQualityCheck("finding4")
    duplicate_chr_pos_check = _FakeQualityCheck("finding5")

    use_case = _make_use_case(
        header_resolver=_FakeHeaderResolver(header_info),
        column_identity_resolver=_FakeColumnIdentityResolver(column_layout),
        row_parser=_FakeRowParser(data_rows),
        quality_checks={
            "malformed_row_check": malformed_row_check,
            "duplicate_header_check": duplicate_header_check,
            "missing_value_scanner": missing_value_scanner,
            "duplicate_rsid_check": duplicate_rsid_check,
            "duplicate_chr_pos_check": duplicate_chr_pos_check,
        },
    )
    use_case.execute("/fake/path.txt")

    assert malformed_row_check.received_args == (data_rows,)
    assert duplicate_header_check.received_args == (data_rows, header_info)
    assert missing_value_scanner.received_args == (
        data_rows,
        column_layout.designated_column_indices,
    )
    assert duplicate_rsid_check.received_args == (
        data_rows,
        column_layout.rsid_column_index,
    )

    received_data_rows, received_context = duplicate_chr_pos_check.received_args
    assert received_data_rows is data_rows
    assert isinstance(received_context, ChrPosColumnIndices)
    assert received_context.chromosome_column_index == column_layout.chromosome_column_index
    assert received_context.position_column_index == column_layout.position_column_index

def test_only_injected_quality_checks_produce_findings() -> None:
    malformed_row_check = _FakeQualityCheck("finding1")
    duplicate_rsid_check = _FakeQualityCheck("finding2")

    use_case = _make_use_case(
        quality_checks={
            "malformed_row_check": malformed_row_check,
            "duplicate_rsid_check": duplicate_rsid_check,
        }
    )
    result = use_case.execute("/fake/path.txt")

    assert set(result["findings"].keys()) == {
        "malformed_row_check",
        "duplicate_rsid_check",
    }

# ---------------------------------------------------------------------------
# 7. GenomicProfiler orchestration: context construction and wiring
# ---------------------------------------------------------------------------

def test_configured_genomic_profilers_receive_expected_context_objects() -> None:
    data_rows = "fake_data_rows"
    column_layout = ColumnLayout(
        rsid_column_index=0,
        chromosome_column_index=1,
        position_column_index=2,
        designated_column_indices=(3,),
    )

    chromosome_label_profiler = _FakeGenomicProfiler("profile1")
    genotype_layout_classifier = _FakeGenomicProfiler("profile2")
    indel_haploid_classifier = _FakeGenomicProfiler("profile3")

    use_case = _make_use_case(
        column_identity_resolver=_FakeColumnIdentityResolver(column_layout),
        row_parser=_FakeRowParser(data_rows),
        genomic_profilers={
            "chromosome_label_profiler": chromosome_label_profiler,
            "genotype_layout_classifier": genotype_layout_classifier,
            "indel_haploid_classifier": indel_haploid_classifier,
        },
    )
    use_case.execute("/fake/path.txt")

    assert chromosome_label_profiler.received_args == (
        data_rows,
        column_layout.chromosome_column_index,
    )
    assert genotype_layout_classifier.received_args == (
        data_rows,
        column_layout.designated_column_indices,
    )

    received_data_rows, received_context = indel_haploid_classifier.received_args
    assert received_data_rows is data_rows
    assert isinstance(received_context, GenotypeChromosomeColumnIndices)
    assert (
        received_context.designated_column_indices
        == column_layout.designated_column_indices
    )
    assert (
        received_context.chromosome_column_index
        == column_layout.chromosome_column_index
    )

def test_only_injected_genomic_profilers_produce_profiles() -> None:
    chromosome_label_profiler = _FakeGenomicProfiler("profile1")

    use_case = _make_use_case(
        genomic_profilers={"chromosome_label_profiler": chromosome_label_profiler}
    )
    result = use_case.execute("/fake/path.txt")

    assert set(result["profiles"].keys()) == {"chromosome_label_profiler"}

# ---------------------------------------------------------------------------
# 8. ReportBuilder orchestration: context construction and wiring
# ---------------------------------------------------------------------------

def test_report_builder_receives_expected_keyword_arguments() -> None:
    encoding_profile = "encoding_profile_sentinel"
    comment_block = "comment_block_sentinel"
    delimiter = "delimiter_sentinel"
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="rsid\tchromosome\tposition\tgenotype",
    )
    data_rows = ["row1", "row2", "row3"]
    raw_content = _FakeRawContent(
        source_path="/fake/path.txt", byte_sample=b"x", lines=("a", "b")
    )
    report_builder = _FakeReportBuilder()

    use_case = _make_use_case(
        file_loader=_FakeFileLoader(raw_content),
        line_splitter=_FakeLineSplitter(comment_block, ["a", "b"]),
        encoding_detector=_FakeEncodingDetector(encoding_profile),
        delimiter_detector=_FakeDelimiterDetector(delimiter),
        header_resolver=_FakeHeaderResolver(header_info),
        row_parser=_FakeRowParser(data_rows),
        report_builder=report_builder,
    )

    result = use_case.execute("/fake/path.txt")

    received = report_builder.received_kwargs
    assert received["source_path"] == "/fake/path.txt"
    assert received["comment_block"] is comment_block
    assert received["encoding_profile"] is encoding_profile
    assert received["delimiter"] is delimiter
    assert received["header_info"] is header_info
    assert received["row_count"] == len(data_rows)
    assert received["column_count_distribution"] is None
    assert received["findings"] == {}
    assert received["profiles"] == {}
    # Object propagation: the same findings/profiles dicts must be
    # handed to ReportBuilder and returned in the result dict, never a
    # copy or a differently-constructed dict for either destination.
    assert received["findings"] is result["findings"]
    assert received["profiles"] is result["profiles"]

def test_result_report_is_the_object_report_builder_returns() -> None:
    report_result = "report_sentinel"
    report_builder = _FakeReportBuilder(report_result=report_result)

    use_case = _make_use_case(report_builder=report_builder)
    result = use_case.execute("/fake/path.txt")

    assert result["report"] is report_result

def test_row_count_passed_to_report_builder_equals_length_of_data_rows() -> None:
    data_rows = ["row1", "row2", "row3", "row4", "row5"]
    report_builder = _FakeReportBuilder()

    use_case = _make_use_case(
        row_parser=_FakeRowParser(data_rows),
        report_builder=report_builder,
    )
    use_case.execute("/fake/path.txt")

    assert report_builder.received_kwargs["row_count"] == len(data_rows)

def test_column_count_distribution_propagated_when_malformed_row_check_present() -> None:
    data_rows = "fake_data_rows"
    column_count_distribution_result = "column_count_distribution_sentinel"
    malformed_row_check = _FakeQualityCheck(
        "finding1", column_count_distribution_result=column_count_distribution_result
    )
    report_builder = _FakeReportBuilder()

    use_case = _make_use_case(
        row_parser=_FakeRowParser(data_rows),
        quality_checks={"malformed_row_check": malformed_row_check},
        report_builder=report_builder,
    )
    result = use_case.execute("/fake/path.txt")

    assert malformed_row_check.received_column_count_distribution_args == (data_rows,)
    assert result["column_count_distribution"] is column_count_distribution_result
    assert (
        report_builder.received_kwargs["column_count_distribution"]
        is column_count_distribution_result
    )

def test_column_count_distribution_is_none_when_malformed_row_check_absent() -> None:
    report_builder = _FakeReportBuilder()

    use_case = _make_use_case(report_builder=report_builder)
    result = use_case.execute("/fake/path.txt")

    assert result["column_count_distribution"] is None
    assert report_builder.received_kwargs["column_count_distribution"] is None

# ---------------------------------------------------------------------------
# 9. Dependency injection boundary (structural, AST-based)
# ---------------------------------------------------------------------------

def _get_forbidden_imported_class_names(module) -> set[str]:
    """Return the set of local names bound by imports whose source
    module path falls under a forbidden concrete-implementation package
    (domain.quality_checks, domain.genomic_profiling, or
    domain.reporting), regardless of which specific class or file is
    involved. This checks the architectural package boundary itself,
    not any current filename.
    """
    with open(module.__file__, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    forbidden_roots = (
        "domain.quality_checks",
        "domain.genomic_profiling",
        "domain.reporting",
    )
    forbidden_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(root in node.module for root in forbidden_roots):
                for alias in node.names:
                    forbidden_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if any(root in alias.name for root in forbidden_roots):
                    forbidden_names.add(alias.asname or alias.name)
    return forbidden_names

def _get_called_bare_names(module) -> set[str]:
    """Return the set of bare (unqualified) names invoked via ast.Call
    nodes where the callee is a simple ast.Name -- i.e. calls of the
    form `SomeName(...)`. Method calls such as `obj.method(...)`
    (ast.Attribute callees) are intentionally excluded, since those are
    collaborator invocations, not local class instantiation.
    """
    with open(module.__file__, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
    return called_names

def test_profile_file_use_case_never_imports_concrete_quality_check_profiler_or_reporting_implementations() -> None:
    # Rule 1: no import may originate from the architecturally forbidden
    # concrete-implementation package roots -- checked by package path,
    # never by filename substring matching.
    forbidden_class_names = _get_forbidden_imported_class_names(
        profile_file_use_case_module
    )
    assert not forbidden_class_names, (
        f"forbidden concrete implementation import(s) found: "
        f"{forbidden_class_names}"
    )

    # Rule 2: no bare-name call may target a class imported from a
    # forbidden module. Since Rule 1 already guarantees no such import
    # exists, forbidden_class_names is empty here by construction; this
    # intersection remains the correct, general check that would catch
    # a forbidden instantiation even if Rule 1's import guard were ever
    # weakened, without flagging any legitimate method/function call
    # (load, parse, detect, check, profile, build,
    # _run_quality_checks, _run_genomic_profilers, str, dict, list,
    # etc.), since those are either ast.Attribute callees or bare names
    # never imported from a forbidden module.
    called_bare_names = _get_called_bare_names(profile_file_use_case_module)
    disallowed_instantiations = called_bare_names & forbidden_class_names
    assert not disallowed_instantiations, (
        f"forbidden concrete implementation instantiation(s) found: "
        f"{disallowed_instantiations}"
    )

def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")

if __name__ == "__main__":
    _run_all()