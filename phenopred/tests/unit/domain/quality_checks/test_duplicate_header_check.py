# tests/unit/domain/quality_checks/test_duplicate_header_check.py
"""Unit tests for DuplicateHeaderCheck (FR-7).

Mirrors the testing approach established by test_row_parser.py,
test_header_resolver.py, and test_raw_line_splitter.py: small, synthetic,
in-memory fixtures only, no file I/O, exercising exactly the structural
properties named by the frozen DuplicateHeaderCheck design specification.

Scope discipline: this suite verifies DuplicateHeaderCheck only. It does
not test, anticipate, or stub any other QualityCheck (MalformedRowCheck,
MissingValueScanner, DuplicateRsidCheck, DuplicateChrPosCheck) or any
GenomicProfiler.
"""

from __future__ import annotations

import ast

from phenopred.domain.entities import DataRow
from phenopred.domain.quality_checks import (
    duplicate_header_check as duplicate_header_check_module,
)
from phenopred.domain.quality_checks.duplicate_header_check import (
    DuplicateHeaderCheck,
)
from phenopred.domain.value_objects import Finding, HeaderInfo


# ---------------------------------------------------------------------------
# 1. Normal behaviour: duplicate header detected
# ---------------------------------------------------------------------------


def test_single_duplicate_header_row_detected() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "allele1", "allele2"),
        source_line="rsid\tchromosome\tposition\tallele1\tallele2",
    )
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A", "G")),
        DataRow(
            line_index=1,
            fields=("rsid", "chromosome", "position", "allele1", "allele2"),
        ),
        DataRow(line_index=2, fields=("rs2", "1", "200", "C", "T")),
    )
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 1
    assert finding.affected_row_refs == (1,)


def test_duplicate_header_matches_commented_only_form() -> None:
    header_info = HeaderInfo(
        form="commented_only",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="# rsid\tchromosome\tposition\tgenotype",
    )
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "AG")),
        DataRow(
            line_index=1,
            fields=("rsid", "chromosome", "position", "genotype"),
        ),
    )
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 1
    assert finding.affected_row_refs == (1,)


# ---------------------------------------------------------------------------
# 2. Normal behaviour: zero duplicates
# ---------------------------------------------------------------------------


def test_zero_duplicates_returns_empty_finding() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "allele1", "allele2"),
        source_line="rsid\tchromosome\tposition\tallele1\tallele2",
    )
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A", "G")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "C", "T")),
    )
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


# ---------------------------------------------------------------------------
# 3. Normal behaviour: multiple duplicates
# ---------------------------------------------------------------------------


def test_multiple_duplicate_header_rows_all_counted() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "allele1", "allele2"),
        source_line="rsid\tchromosome\tposition\tallele1\tallele2",
    )
    duplicate_fields = ("rsid", "chromosome", "position", "allele1", "allele2")
    rows = (
        DataRow(line_index=0, fields=duplicate_fields),
        DataRow(line_index=1, fields=("rs1", "1", "100", "A", "G")),
        DataRow(line_index=2, fields=duplicate_fields),
        DataRow(line_index=3, fields=duplicate_fields),
    )
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 3
    assert finding.affected_row_refs == (0, 2, 3)


def test_examples_and_refs_bounded_at_ten() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid",),
        source_line="rsid",
    )
    # 15 duplicate rows; only the first 10 should appear as examples/refs,
    # but count must reflect all 15.
    rows = tuple(DataRow(line_index=i, fields=("rsid",)) for i in range(15))
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 15
    assert len(finding.examples) == 10
    assert len(finding.affected_row_refs) == 10
    assert finding.affected_row_refs == tuple(range(10))


# ---------------------------------------------------------------------------
# 4. Boundary behaviour: empty input
# ---------------------------------------------------------------------------


def test_empty_data_rows_returns_zero_finding() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "allele1", "allele2"),
        source_line="rsid\tchromosome\tposition\tallele1\tallele2",
    )
    finding = DuplicateHeaderCheck().check((), header_info)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


# ---------------------------------------------------------------------------
# 5. Boundary behaviour: missing header (resolved_columns is None)
# ---------------------------------------------------------------------------


def test_absent_header_returns_zero_finding() -> None:
    header_info = HeaderInfo(form="absent", resolved_columns=None, source_line=None)
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A", "G")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "C", "T")),
    )
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_absent_header_with_empty_rows_returns_zero_finding() -> None:
    header_info = HeaderInfo(form="absent", resolved_columns=None, source_line=None)
    finding = DuplicateHeaderCheck().check((), header_info)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


# ---------------------------------------------------------------------------
# 6. Exact comparison behaviour: no trimming, no case conversion,
#    no interpretation
# ---------------------------------------------------------------------------


def test_partial_field_match_is_not_a_duplicate() -> None:
    # Same field count, but content differs -> not a match.
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "allele1", "allele2"),
        source_line="rsid\tchromosome\tposition\tallele1\tallele2",
    )
    rows = (DataRow(line_index=0, fields=("rsid", "chromosome", "position", "allele1", "X")),)
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 0


def test_different_field_count_is_not_a_duplicate() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "allele1", "allele2"),
        source_line="rsid\tchromosome\tposition\tallele1\tallele2",
    )
    rows = (DataRow(line_index=0, fields=("rsid", "chromosome", "position")),)
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 0


def test_no_trimming_of_whitespace_in_comparison() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome"),
        source_line="rsid\tchromosome",
    )
    rows = (DataRow(line_index=0, fields=(" rsid", "chromosome ")),)
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 0


def test_no_case_folding_in_comparison() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome"),
        source_line="rsid\tchromosome",
    )
    rows = (DataRow(line_index=0, fields=("RSID", "Chromosome")),)
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 0


def test_exact_match_required_full_equality() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome"),
        source_line="rsid\tchromosome",
    )
    rows = (DataRow(line_index=0, fields=("rsid", "chromosome")),)
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.count == 1


# ---------------------------------------------------------------------------
# 7. Order preservation
# ---------------------------------------------------------------------------


def test_affected_row_refs_preserve_original_order() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid",),
        source_line="rsid",
    )
    rows = (
        DataRow(line_index=0, fields=("rsid",)),
        DataRow(line_index=1, fields=("other",)),
        DataRow(line_index=2, fields=("rsid",)),
    )
    finding = DuplicateHeaderCheck().check(rows, header_info)
    assert finding.affected_row_refs == (0, 2)


# ---------------------------------------------------------------------------
# 8. Determinism and non-mutation
# ---------------------------------------------------------------------------


def test_deterministic_repeated_calls() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome"),
        source_line="rsid\tchromosome",
    )
    rows = (
        DataRow(line_index=0, fields=("rsid", "chromosome")),
        DataRow(line_index=1, fields=("rs1", "1")),
    )
    check = DuplicateHeaderCheck()
    first = check.check(rows, header_info)
    second = check.check(rows, header_info)
    assert first == second


def test_input_data_rows_not_mutated() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome"),
        source_line="rsid\tchromosome",
    )
    rows = (
        DataRow(line_index=0, fields=("rsid", "chromosome")),
        DataRow(line_index=1, fields=("rs1", "1")),
    )
    original_copy = tuple(rows)
    DuplicateHeaderCheck().check(rows, header_info)
    assert rows == original_copy


def test_input_header_info_not_mutated() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome"),
        source_line="rsid\tchromosome",
    )
    original = HeaderInfo(
        form=header_info.form,
        resolved_columns=header_info.resolved_columns,
        source_line=header_info.source_line,
    )
    rows = (DataRow(line_index=0, fields=("rsid", "chromosome")),)
    DuplicateHeaderCheck().check(rows, header_info)
    assert header_info == original


# ---------------------------------------------------------------------------
# 9. Output contract: Finding shape
# ---------------------------------------------------------------------------


def test_result_is_finding_instance() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid",),
        source_line="rsid",
    )
    finding = DuplicateHeaderCheck().check((), header_info)
    assert isinstance(finding, Finding)
    assert finding.check_name == "duplicate_header_check"


def test_never_raises_across_varied_inputs() -> None:
    header_info_absent = HeaderInfo(form="absent", resolved_columns=None, source_line=None)
    header_info_present = HeaderInfo(
        form="uncommented_row", resolved_columns=("rsid",), source_line="rsid"
    )
    # None of these should raise.
    DuplicateHeaderCheck().check((), header_info_absent)
    DuplicateHeaderCheck().check((), header_info_present)
    DuplicateHeaderCheck().check(
        (DataRow(line_index=0, fields=("rsid",)),), header_info_absent
    )
    DuplicateHeaderCheck().check(
        (DataRow(line_index=0, fields=("rsid",)),), header_info_present
    )


# ---------------------------------------------------------------------------
# 10. Dependency boundaries (structural, AST-based)
# ---------------------------------------------------------------------------


def _imported_module_names(module) -> list[str]:
    with open(module.__file__, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_duplicate_header_check_never_imports_ingestion_errors() -> None:
    imported = _imported_module_names(duplicate_header_check_module)
    assert not any("errors" in name for name in imported)


def test_duplicate_header_check_never_imports_upstream_modules() -> None:
    imported = _imported_module_names(duplicate_header_check_module)
    forbidden_substrings = [
        "raw_file_loader",
        "encoding_detector",
        "raw_line_splitter",
        "delimiter_detector",
        "header_resolver",
        "column_identity_resolver",
        "row_parser",
    ]
    for name in imported:
        for forbidden in forbidden_substrings:
            assert forbidden not in name, f"forbidden import found: {name}"


def test_duplicate_header_check_never_imports_sibling_quality_checks() -> None:
    imported = _imported_module_names(duplicate_header_check_module)
    forbidden_substrings = [
        "malformed_row_check",
        "missing_value_scanner",
        "duplicate_rsid_check",
        "duplicate_chr_pos_check",
    ]
    for name in imported:
        for forbidden in forbidden_substrings:
            assert forbidden not in name, f"forbidden import found: {name}"


def test_duplicate_header_check_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(duplicate_header_check_module)
    domain_imports = [name for name in imported if name.startswith("phenopred.")]
    assert set(domain_imports) == {
        "phenopred.domain.entities",
        "phenopred.domain.value_objects",
    }


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()