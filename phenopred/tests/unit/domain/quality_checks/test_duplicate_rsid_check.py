# tests/unit/domain/quality_checks/test_duplicate_rsid_check.py
"""Unit tests for DuplicateRsidCheck (FR-8).

Mirrors the testing approach established by test_malformed_row_check.py,
test_missing_value_scanner.py, and test_duplicate_header_check.py: small,
synthetic, in-memory fixtures only, no file I/O, exercising exactly the
structural properties named by the frozen ADR 1 (Column-Identity Input
Contract), ADR 2 (Finding Output Mapping), and
ARCHITECTURE_FREEZE_RECORD_DuplicateRsidCheck.md Section 7 (Testing
Obligations).

Scope discipline: this suite verifies DuplicateRsidCheck's interaction
with DataRow/Finding only. It does not test, anticipate, or stub any
other QualityCheck (DuplicateHeaderCheck, MalformedRowCheck,
MissingValueScanner, DuplicateChrPosCheck) or any GenomicProfiler.
"""

from __future__ import annotations

import ast
import random

from phenopred.domain.entities import DataRow
from phenopred.domain.quality_checks import (
    duplicate_rsid_check as duplicate_rsid_check_module,
)
from phenopred.domain.quality_checks.duplicate_rsid_check import (
    DuplicateRsidCheck,
)
from phenopred.domain.value_objects import Finding


# ---------------------------------------------------------------------------
# 1. Finding contract
# ---------------------------------------------------------------------------


def test_return_type_is_finding() -> None:
    finding = DuplicateRsidCheck().check((DataRow(0, ("rs1",)),), 0)
    assert isinstance(finding, Finding)


def test_check_name_is_stable_label() -> None:
    finding = DuplicateRsidCheck().check((DataRow(0, ("rs1",)),), 0)
    assert finding.check_name == "duplicate_rsid_check"


# ---------------------------------------------------------------------------
# 2. Empty input and no duplicates
# ---------------------------------------------------------------------------


def test_no_duplicates_returns_zero_finding() -> None:
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs2",)),
        DataRow(2, ("rs3",)),
    )
    finding = DuplicateRsidCheck().check(rows, 0)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_empty_data_rows_returns_zero_finding() -> None:
    finding = DuplicateRsidCheck().check((), 0)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


# ---------------------------------------------------------------------------
# 3. Single duplicated RSID group
# ---------------------------------------------------------------------------


def test_single_duplicated_group_all_rows_counted() -> None:
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs2",)),
        DataRow(2, ("rs1",)),
    )
    finding = DuplicateRsidCheck().check(rows, 0)
    assert finding.count == 2
    assert finding.affected_row_refs == (0, 2)


def test_single_duplicated_group_three_occurrences_all_counted() -> None:
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs1",)),
        DataRow(2, ("rs1",)),
        DataRow(3, ("rs2",)),
    )
    finding = DuplicateRsidCheck().check(rows, 0)
    # All three occurrences of "rs1" are counted -- there is no "first
    # occurrence is exempt" rule.
    assert finding.count == 3
    assert finding.affected_row_refs == (0, 1, 2)


# ---------------------------------------------------------------------------
# 4. Multiple duplicated RSID groups
# ---------------------------------------------------------------------------


def test_multiple_duplicated_groups_combined_into_one_finding() -> None:
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs2",)),
        DataRow(2, ("rs1",)),
        DataRow(3, ("rs3",)),
        DataRow(4, ("rs2",)),
    )
    finding = DuplicateRsidCheck().check(rows, 0)
    # "rs1" (lines 0, 2) and "rs2" (lines 1, 4) are both duplicated;
    # "rs3" (line 3) is not. All affected rows across both groups are
    # combined into the single Finding's count/refs.
    assert finding.count == 4
    assert finding.affected_row_refs == (0, 1, 2, 4)


# ---------------------------------------------------------------------------
# 5. Mixed duplicated and non-duplicated RSID values
# ---------------------------------------------------------------------------


def test_mixed_duplicated_and_unique_values() -> None:
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs_unique_a",)),
        DataRow(2, ("rs1",)),
        DataRow(3, ("rs_unique_b",)),
        DataRow(4, ("rs_unique_c",)),
    )
    finding = DuplicateRsidCheck().check(rows, 0)
    assert finding.count == 2
    assert finding.affected_row_refs == (0, 2)
    assert 1 not in finding.affected_row_refs
    assert 3 not in finding.affected_row_refs
    assert 4 not in finding.affected_row_refs


# ---------------------------------------------------------------------------
# 6. Count semantics
# ---------------------------------------------------------------------------


def test_count_is_total_affected_row_population_not_distinct_values() -> None:
    # Two distinct duplicated values ("rs1": 2 occurrences, "rs2": 3
    # occurrences) -> count must be 5 (total affected rows), not 2
    # (distinct duplicated value count).
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs2",)),
        DataRow(2, ("rs1",)),
        DataRow(3, ("rs2",)),
        DataRow(4, ("rs2",)),
    )
    finding = DuplicateRsidCheck().check(rows, 0)
    assert finding.count == 5
    assert finding.count != 2  # not distinct-duplicated-value cardinality


def test_count_is_not_extra_occurrences_after_first() -> None:
    # "rs1" occurs 4 times. A "group-size-minus-one" convention would
    # report 3 ("extra" occurrences); the frozen rule requires all 4 to
    # be counted.
    rows = tuple(DataRow(i, ("rs1",)) for i in range(4))
    finding = DuplicateRsidCheck().check(rows, 0)
    assert finding.count == 4
    assert finding.count != 3  # not "extra occurrences" semantics
    assert finding.affected_row_refs == (0, 1, 2, 3)


# ---------------------------------------------------------------------------
# 7. More than 10 affected rows
# ---------------------------------------------------------------------------


def test_more_than_ten_affected_rows_truncates_examples_and_refs() -> None:
    # 15 rows sharing one duplicated RSID value, plus 1 unique row.
    rows = tuple(DataRow(i, ("dup_rsid",)) for i in range(15)) + (
        DataRow(15, ("unique_rsid",)),
    )
    finding = DuplicateRsidCheck().check(rows, 0)
    assert finding.count == 15
    assert len(finding.examples) <= 10
    assert len(finding.affected_row_refs) <= 10
    assert len(finding.examples) == len(finding.affected_row_refs)
    assert finding.affected_row_refs == tuple(range(10))
    assert finding.affected_row_refs == tuple(sorted(finding.affected_row_refs))


def test_examples_and_affected_row_refs_describe_same_rows_in_same_order() -> None:
    rows = tuple(DataRow(i, ("dup_rsid",)) for i in range(12))
    finding = DuplicateRsidCheck().check(rows, 0)
    assert len(finding.examples) == len(finding.affected_row_refs) == 10
    for example, line_index in zip(finding.examples, finding.affected_row_refs):
        assert f"line_index={line_index}" in example


def test_multiple_groups_more_than_ten_affected_rows_still_ascending_order() -> None:
    rows = (
        tuple(DataRow(i, ("groupA",)) for i in range(6))
        + tuple(DataRow(6 + i, ("groupB",)) for i in range(6))
    )
    finding = DuplicateRsidCheck().check(rows, 0)
    assert finding.count == 12
    assert finding.affected_row_refs == tuple(range(10))


# ---------------------------------------------------------------------------
# 8. Some rows with out-of-bounds rsid_column_index
# ---------------------------------------------------------------------------


def test_out_of_bounds_index_for_some_rows_no_exception_and_correct_detection() -> None:
    rows = (
        DataRow(0, ("rs1", "extra")),
        DataRow(1, ("rs1",)),  # index 1 out of bounds -> excluded
        DataRow(2, ("rs2", "extra")),
    )
    # Does not raise.
    finding = DuplicateRsidCheck().check(rows, 1)
    # Only rows 0 and 2 have a value at index 1 ("extra" both times) --
    # this makes them a duplicated pair; row 1 contributes no
    # observation and is excluded.
    assert finding.count == 2
    assert finding.affected_row_refs == (0, 2)


def test_out_of_bounds_index_for_some_rows_excludes_those_rows_from_duplicates() -> None:
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs1", "x")),
        DataRow(2, ("rs1",)),
    )
    # rsid_column_index 0 is valid for all three rows; all three share
    # "rs1" -> all three counted regardless of differing widths.
    finding = DuplicateRsidCheck().check(rows, 0)
    assert finding.count == 3
    assert finding.affected_row_refs == (0, 1, 2)


# ---------------------------------------------------------------------------
# 9. All rows with out-of-bounds rsid_column_index
# ---------------------------------------------------------------------------


def test_out_of_bounds_index_for_all_rows_returns_zero_finding() -> None:
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs2",)),
    )
    finding = DuplicateRsidCheck().check(rows, 5)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_no_exception_raised_for_out_of_bounds_indices() -> None:
    rows = (DataRow(0, ()),)
    # Should not raise, despite index 0 being out of bounds for an
    # empty fields tuple.
    finding = DuplicateRsidCheck().check(rows, 0)
    assert finding.count == 0


# ---------------------------------------------------------------------------
# 10. Determinism
# ---------------------------------------------------------------------------


def test_repeated_execution_produces_identical_finding() -> None:
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs2",)),
        DataRow(2, ("rs1",)),
    )
    check = DuplicateRsidCheck()
    first = check.check(rows, 0)
    second = check.check(rows, 0)
    assert first == second


def test_result_independent_of_input_traversal_order() -> None:
    rows = (
        DataRow(0, ("rs1",)),
        DataRow(1, ("rs2",)),
        DataRow(2, ("rs1",)),
        DataRow(3, ("rs3",)),
        DataRow(4, ("rs2",)),
    )
    shuffled = list(rows)
    random.Random(11).shuffle(shuffled)
    check = DuplicateRsidCheck()
    ordered_result = check.check(rows, 0)
    shuffled_result = check.check(shuffled, 0)
    assert ordered_result.count == shuffled_result.count
    assert ordered_result.affected_row_refs == shuffled_result.affected_row_refs
    assert ordered_result.examples == shuffled_result.examples


def test_ordering_independent_of_dict_and_set_iteration_order() -> None:
    # Two structurally different, but logically equivalent, input
    # orderings/paths, to confirm no reliance on dict/set/Counter
    # insertion order.
    rows_a = (
        DataRow(0, ("zeta",)),
        DataRow(1, ("alpha",)),
        DataRow(2, ("alpha",)),
        DataRow(3, ("zeta",)),
        DataRow(4, ("zeta",)),
    )
    rows_b = (
        DataRow(3, ("zeta",)),
        DataRow(4, ("zeta",)),
        DataRow(0, ("zeta",)),
        DataRow(2, ("alpha",)),
        DataRow(1, ("alpha",)),
    )
    check = DuplicateRsidCheck()
    result_a = check.check(rows_a, 0)
    result_b = check.check(rows_b, 0)
    assert result_a.count == result_b.count
    assert result_a.affected_row_refs == result_b.affected_row_refs
    assert result_a.examples == result_b.examples


# ---------------------------------------------------------------------------
# 11. Non-mutation
# ---------------------------------------------------------------------------


def test_input_data_rows_not_mutated() -> None:
    rows = [DataRow(0, ("rs1",)), DataRow(1, ("rs1",))]
    original_copy = list(rows)
    DuplicateRsidCheck().check(rows, 0)
    assert rows == original_copy


def test_data_row_instances_not_mutated() -> None:
    row = DataRow(0, ("rs1", "chr1"))
    DuplicateRsidCheck().check((row,), 0)
    assert row.line_index == 0
    assert row.fields == ("rs1", "chr1")


def test_rsid_column_index_argument_not_mutated() -> None:
    # rsid_column_index is a plain int (immutable by nature), but this
    # test confirms the value passed in is not reassigned or altered as
    # observed by the caller across repeated calls.
    rsid_column_index = 0
    rows = (DataRow(0, ("rs1",)), DataRow(1, ("rs1",)))
    check = DuplicateRsidCheck()
    check.check(rows, rsid_column_index)
    assert rsid_column_index == 0


# ---------------------------------------------------------------------------
# 12. Dependency boundaries (structural, AST-based)
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


def test_duplicate_rsid_check_never_imports_errors_module() -> None:
    imported = _imported_module_names(duplicate_rsid_check_module)
    assert not any("errors" in name for name in imported)


def test_duplicate_rsid_check_never_imports_upstream_or_sibling_modules() -> None:
    imported = _imported_module_names(duplicate_rsid_check_module)
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
        "duplicate_chr_pos_check",
        "chromosome_label_profiler",
        "genotype_layout_classifier",
        "indel_haploid_classifier",
        "interfaces",
    ]
    for name in imported:
        for forbidden in forbidden_substrings:
            assert forbidden not in name, f"forbidden import found: {name}"


def test_duplicate_rsid_check_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(duplicate_rsid_check_module)
    domain_imports = [name for name in imported if name.startswith("phenopred.")]
    assert set(domain_imports) == {
        "phenopred.domain.entities",
        "phenopred.domain.value_objects",
    }


def test_never_raises_across_varied_inputs() -> None:
    check = DuplicateRsidCheck()
    check.check((), 0)
    check.check((DataRow(0, ()),), 0)
    check.check((DataRow(0, ("A",)),), 5)
    check.check((DataRow(0, ("A", "B")),), 1)


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()