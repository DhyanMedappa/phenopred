# tests/unit/domain/quality_checks/test_duplicate_chr_pos_check.py
"""Unit tests for DuplicateChrPosCheck (FR-9).

Mirrors the testing approach established by test_malformed_row_check.py,
test_missing_value_scanner.py, test_duplicate_header_check.py, and
test_duplicate_rsid_check.py: small, synthetic, in-memory fixtures only,
no file I/O, exercising exactly the structural properties named by the
frozen ADR 1 (Column-Identity Input Contract) and ADR 2 (Finding Output
Mapping) for DuplicateChrPosCheck.

Scope discipline: this suite verifies DuplicateChrPosCheck's interaction
with DataRow/ChrPosColumnIndices/Finding only. It does not test,
anticipate, or stub any other QualityCheck (DuplicateHeaderCheck,
MalformedRowCheck, MissingValueScanner, DuplicateRsidCheck) or any
GenomicProfiler.
"""

from __future__ import annotations

import ast
import random

from phenopred.domain.entities import DataRow
from phenopred.domain.quality_checks import (
    duplicate_chr_pos_check as duplicate_chr_pos_check_module,
)
from phenopred.domain.quality_checks.duplicate_chr_pos_check import (
    DuplicateChrPosCheck,
)
from phenopred.domain.value_objects import ChrPosColumnIndices, Finding

# Default column layout used by most fixtures below: field 0 is some
# unrelated column (e.g. rsid), field 1 is chromosome, field 2 is
# position -- matching both evidenced datasets' relative layout, but
# arbitrary from this check's own point of view (it never interprets
# column names).
_COLUMNS = ChrPosColumnIndices(
    chromosome_column_index=1, position_column_index=2
)


# ---------------------------------------------------------------------------
# 1. Finding contract
# ---------------------------------------------------------------------------


def test_return_type_is_finding() -> None:
    finding = DuplicateChrPosCheck().check(
        (DataRow(0, ("rs1", "1", "100")),), _COLUMNS
    )
    assert isinstance(finding, Finding)


def test_check_name_is_stable_label() -> None:
    finding = DuplicateChrPosCheck().check(
        (DataRow(0, ("rs1", "1", "100")),), _COLUMNS
    )
    assert finding.check_name == "duplicate_chr_pos_check"


# ---------------------------------------------------------------------------
# 2. Empty input and no duplicates
# ---------------------------------------------------------------------------


def test_no_duplicates_returns_zero_finding() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "2", "200")),
        DataRow(2, ("rs3", "3", "300")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_empty_data_rows_returns_zero_finding() -> None:
    finding = DuplicateChrPosCheck().check((), _COLUMNS)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


# ---------------------------------------------------------------------------
# 3. Single duplicated pair
# ---------------------------------------------------------------------------


def test_single_duplicated_pair_all_rows_counted() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "2", "200")),
        DataRow(2, ("rs3", "1", "100")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 2
    assert finding.affected_row_refs == (0, 2)


def test_single_duplicated_pair_three_occurrences_all_counted() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "1", "100")),
        DataRow(2, ("rs3", "1", "100")),
        DataRow(3, ("rs4", "2", "200")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    # All three occurrences of ("1", "100") are counted -- there is no
    # "first occurrence is exempt" rule.
    assert finding.count == 3
    assert finding.affected_row_refs == (0, 1, 2)


# ---------------------------------------------------------------------------
# 4. Multiple duplicated pairs
# ---------------------------------------------------------------------------


def test_multiple_duplicated_pairs_combined_into_one_finding() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "2", "200")),
        DataRow(2, ("rs3", "1", "100")),
        DataRow(3, ("rs4", "3", "300")),
        DataRow(4, ("rs5", "2", "200")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    # ("1","100") (lines 0, 2) and ("2","200") (lines 1, 4) are both
    # duplicated; ("3","300") (line 3) is not. All affected rows across
    # both groups are combined into the single Finding's count/refs --
    # matches ADR 2's worked example exactly.
    assert finding.count == 4
    assert finding.affected_row_refs == (0, 1, 2, 4)


# ---------------------------------------------------------------------------
# 5. Mixed duplicated and non-duplicated pairs
# ---------------------------------------------------------------------------


def test_mixed_duplicated_and_unique_pairs() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "9", "900")),
        DataRow(2, ("rs3", "1", "100")),
        DataRow(3, ("rs4", "8", "800")),
        DataRow(4, ("rs5", "7", "700")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 2
    assert finding.affected_row_refs == (0, 2)
    assert 1 not in finding.affected_row_refs
    assert 3 not in finding.affected_row_refs
    assert 4 not in finding.affected_row_refs


# ---------------------------------------------------------------------------
# 6. Composite key correctness
# ---------------------------------------------------------------------------


def test_same_chromosome_different_position_not_duplicate() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "1", "200")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 0
    assert finding.affected_row_refs == ()


def test_same_position_different_chromosome_not_duplicate() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "2", "100")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 0
    assert finding.affected_row_refs == ()


# ---------------------------------------------------------------------------
# 7. Literal equality -- no normalization
# ---------------------------------------------------------------------------


def test_leading_zero_variant_treated_as_distinct() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "01", "100")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    # "1" and "01" are different literal strings -- no numeric
    # coercion or leading-zero stripping is applied.
    assert finding.count == 0
    assert finding.affected_row_refs == ()


def test_case_variant_alphabetic_label_treated_as_distinct() -> None:
    rows = (
        DataRow(0, ("rs1", "x", "100")),
        DataRow(1, ("rs2", "X", "100")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    # "x" and "X" are different literal strings -- no case-folding is
    # applied.
    assert finding.count == 0
    assert finding.affected_row_refs == ()


# ---------------------------------------------------------------------------
# 8. Bounds handling
# ---------------------------------------------------------------------------


def test_chromosome_index_out_of_bounds_for_some_rows_excludes_them() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2",)),  # index 1 (chromosome) out of bounds
        DataRow(2, ("rs3", "1", "100")),
    )
    # Does not raise.
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    # Only rows 0 and 2 have both fields in bounds and share ("1","100");
    # row 1 contributes no observation and is excluded.
    assert finding.count == 2
    assert finding.affected_row_refs == (0, 2)


def test_position_index_out_of_bounds_for_some_rows_excludes_them() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "1")),  # index 2 (position) out of bounds
        DataRow(2, ("rs3", "1", "100")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 2
    assert finding.affected_row_refs == (0, 2)


def test_both_indices_out_of_bounds_for_all_rows_returns_zero_finding() -> None:
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs2",)),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_mixed_valid_and_invalid_rows_partial_population() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2",)),  # both chromosome and position oob
        DataRow(2, ("rs3", "1", "100")),
        DataRow(3, ("rs4", "1")),  # position oob only
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 2
    assert finding.affected_row_refs == (0, 2)


def test_chromosome_in_bounds_but_position_out_of_bounds_excludes_row() -> None:
    # A row with a valid chromosome field but no position field must
    # contribute no observation at all -- never a half-formed pair.
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "1")),
        DataRow(2, ("rs3", "1", "100")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert 1 not in finding.affected_row_refs
    assert finding.count == 2


def test_no_exception_raised_for_out_of_bounds_indices() -> None:
    rows = (DataRow(0, ()),)
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 0


def test_negative_chromosome_index_ignored_not_wrapped() -> None:
    # A negative chromosome_column_index must not be treated as "in
    # bounds" merely because it is less than len(row.fields); Python's
    # negative-indexing semantics would otherwise silently read a field
    # from the end of the tuple instead of correctly excluding the row.
    negative_columns = ChrPosColumnIndices(
        chromosome_column_index=-1, position_column_index=2
    )
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "1", "100")),
    )
    finding = DuplicateChrPosCheck().check(rows, negative_columns)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_negative_position_index_ignored_not_wrapped() -> None:
    negative_columns = ChrPosColumnIndices(
        chromosome_column_index=1, position_column_index=-1
    )
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "1", "100")),
    )
    finding = DuplicateChrPosCheck().check(rows, negative_columns)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_negative_index_does_not_raise() -> None:
    negative_columns = ChrPosColumnIndices(
        chromosome_column_index=-1, position_column_index=-1
    )
    rows = (DataRow(0, ("rs1", "1", "100")),)
    finding = DuplicateChrPosCheck().check(rows, negative_columns)
    assert finding.count == 0


def test_negative_index_rows_excluded_but_valid_rows_still_processed() -> None:
    # A mix of a valid ChrPosColumnIndices used across rows where some
    # rows are otherwise normal; this confirms the negative-index fix
    # does not disturb ordinary, in-bounds duplicate detection.
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "1", "100")),
        DataRow(2, ("rs3", "2", "200")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 2
    assert finding.affected_row_refs == (0, 1)


# ---------------------------------------------------------------------------
# 9. Count semantics
# ---------------------------------------------------------------------------


def test_count_is_total_affected_row_population_not_distinct_pairs() -> None:
    # Two distinct duplicated pairs (("1","100"): 2 occurrences,
    # ("2","200"): 3 occurrences) -> count must be 5 (total affected
    # rows), not 2 (distinct duplicated pair count).
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "2", "200")),
        DataRow(2, ("rs3", "1", "100")),
        DataRow(3, ("rs4", "2", "200")),
        DataRow(4, ("rs5", "2", "200")),
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 5
    assert finding.count != 2  # not distinct-duplicated-pair cardinality


def test_count_is_not_extra_occurrences_after_first() -> None:
    # ("1","100") occurs 4 times. A "group-size-minus-one" convention
    # would report 3 ("extra" occurrences); the frozen rule requires
    # all 4 to be counted.
    rows = tuple(DataRow(i, (f"rs{i}", "1", "100")) for i in range(4))
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 4
    assert finding.count != 3
    assert finding.affected_row_refs == (0, 1, 2, 3)


# ---------------------------------------------------------------------------
# 10. More than 10 affected rows
# ---------------------------------------------------------------------------


def test_more_than_ten_affected_rows_truncates_examples_and_refs() -> None:
    rows = tuple(
        DataRow(i, (f"rs{i}", "1", "100")) for i in range(15)
    ) + (DataRow(15, ("rs_unique", "9", "900")),)
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 15
    assert len(finding.examples) <= 10
    assert len(finding.affected_row_refs) <= 10
    assert len(finding.examples) == len(finding.affected_row_refs)
    assert finding.affected_row_refs == tuple(range(10))
    assert finding.affected_row_refs == tuple(sorted(finding.affected_row_refs))


def test_examples_and_affected_row_refs_describe_same_rows_in_same_order() -> None:
    rows = tuple(DataRow(i, (f"rs{i}", "1", "100")) for i in range(12))
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert len(finding.examples) == len(finding.affected_row_refs) == 10
    for example, line_index in zip(finding.examples, finding.affected_row_refs):
        assert f"line_index={line_index}" in example


def test_multiple_groups_more_than_ten_affected_rows_still_ascending_order() -> None:
    rows = tuple(
        DataRow(i, (f"rs{i}", "1", "100")) for i in range(6)
    ) + tuple(
        DataRow(6 + i, (f"rs{6+i}", "2", "200")) for i in range(6)
    )
    finding = DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert finding.count == 12
    assert finding.affected_row_refs == tuple(range(10))


# ---------------------------------------------------------------------------
# 11. Determinism
# ---------------------------------------------------------------------------


def test_repeated_execution_produces_identical_finding() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "2", "200")),
        DataRow(2, ("rs3", "1", "100")),
    )
    check = DuplicateChrPosCheck()
    first = check.check(rows, _COLUMNS)
    second = check.check(rows, _COLUMNS)
    assert first == second


def test_result_independent_of_input_traversal_order() -> None:
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "2", "200")),
        DataRow(2, ("rs3", "1", "100")),
        DataRow(3, ("rs4", "3", "300")),
        DataRow(4, ("rs5", "2", "200")),
    )
    shuffled = list(rows)
    random.Random(11).shuffle(shuffled)
    check = DuplicateChrPosCheck()
    ordered_result = check.check(rows, _COLUMNS)
    shuffled_result = check.check(shuffled, _COLUMNS)
    assert ordered_result.count == shuffled_result.count
    assert ordered_result.affected_row_refs == shuffled_result.affected_row_refs
    assert ordered_result.examples == shuffled_result.examples


def test_ordering_independent_of_dict_and_set_iteration_order() -> None:
    # Two structurally different, but logically equivalent, input
    # orderings, to confirm no reliance on dict/set/Counter insertion
    # order.
    rows_a = (
        DataRow(0, ("rs0", "9", "900")),
        DataRow(1, ("rs1", "1", "100")),
        DataRow(2, ("rs2", "1", "100")),
        DataRow(3, ("rs3", "9", "900")),
        DataRow(4, ("rs4", "9", "900")),
    )
    rows_b = (
        DataRow(3, ("rs3", "9", "900")),
        DataRow(4, ("rs4", "9", "900")),
        DataRow(0, ("rs0", "9", "900")),
        DataRow(2, ("rs2", "1", "100")),
        DataRow(1, ("rs1", "1", "100")),
    )
    check = DuplicateChrPosCheck()
    result_a = check.check(rows_a, _COLUMNS)
    result_b = check.check(rows_b, _COLUMNS)
    assert result_a.count == result_b.count
    assert result_a.affected_row_refs == result_b.affected_row_refs
    assert result_a.examples == result_b.examples


# ---------------------------------------------------------------------------
# 12. Non-mutation
# ---------------------------------------------------------------------------


def test_input_data_rows_not_mutated() -> None:
    rows = [
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "1", "100")),
    ]
    original_copy = list(rows)
    DuplicateChrPosCheck().check(rows, _COLUMNS)
    assert rows == original_copy


def test_data_row_instances_not_mutated() -> None:
    row = DataRow(0, ("rs1", "1", "100"))
    DuplicateChrPosCheck().check((row,), _COLUMNS)
    assert row.line_index == 0
    assert row.fields == ("rs1", "1", "100")


def test_chr_pos_columns_argument_not_mutated() -> None:
    columns = ChrPosColumnIndices(
        chromosome_column_index=1, position_column_index=2
    )
    rows = (
        DataRow(0, ("rs1", "1", "100")),
        DataRow(1, ("rs2", "1", "100")),
    )
    check = DuplicateChrPosCheck()
    check.check(rows, columns)
    assert columns.chromosome_column_index == 1
    assert columns.position_column_index == 2


# ---------------------------------------------------------------------------
# 13. Dependency boundaries (structural, AST-based)
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


def test_duplicate_chr_pos_check_never_imports_errors_module() -> None:
    imported = _imported_module_names(duplicate_chr_pos_check_module)
    assert not any("errors" in name for name in imported)


def test_duplicate_chr_pos_check_never_imports_upstream_or_sibling_modules() -> None:
    imported = _imported_module_names(duplicate_chr_pos_check_module)
    forbidden_substrings = [
        "raw_file_loader",
        "encoding_detector",
        "raw_line_splitter",
        "delimiter_detector",
        "header_resolver",
        "column_identity_resolver",
        "row_parser",
        "report_builder",
        "duplicate_header_check",
        "malformed_row_check",
        "missing_value_scanner",
        "duplicate_rsid_check",
        "chromosome_label_profiler",
        "genotype_layout_classifier",
        "indel_haploid_classifier",
        "interfaces",
    ]
    for name in imported:
        for forbidden in forbidden_substrings:
            assert forbidden not in name, f"forbidden import found: {name}"


def test_duplicate_chr_pos_check_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(duplicate_chr_pos_check_module)
    domain_imports = [name for name in imported if name.startswith("phenopred.")]
    assert set(domain_imports) == {
        "phenopred.domain.entities",
        "phenopred.domain.value_objects",
    }


def test_never_raises_across_varied_inputs() -> None:
    check = DuplicateChrPosCheck()
    check.check((), _COLUMNS)
    check.check((DataRow(0, ()),), _COLUMNS)
    check.check((DataRow(0, ("A",)),), _COLUMNS)
    check.check((DataRow(0, ("A", "B")),), _COLUMNS)
    check.check(
        (DataRow(0, ("A", "B", "C")),),
        ChrPosColumnIndices(chromosome_column_index=5, position_column_index=6),
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