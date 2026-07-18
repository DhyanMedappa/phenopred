# tests/unit/domain/quality_checks/test_missing_value_scanner.py
"""Unit tests for MissingValueScanner (FR-6).

Mirrors the testing approach established by test_malformed_row_check.py
and test_duplicate_header_check.py: small, synthetic, in-memory fixtures
only, no file I/O, exercising exactly the structural properties named by
the frozen "Column-Identity Input Contract for MissingValueScanner
(FR-6)" ADR, the frozen "Finding Output Mapping for MissingValueScanner
(FR-6)" ADR, and IMPLEMENTATION_HANDOFF_MissingValueScanner.md.

Scope discipline: this suite verifies MissingValueScanner's interaction
with DataRow/Finding only. It does not test, anticipate, or stub
HeaderInfo-based column resolution, DuplicateRsidCheck, DuplicateChrPosCheck,
or any GenomicProfiler.
"""

from __future__ import annotations

import ast
import random

from phenopred.domain.entities import DataRow
from phenopred.domain.quality_checks import (
    missing_value_scanner as missing_value_scanner_module,
)
from phenopred.domain.quality_checks.missing_value_scanner import (
    MissingValueScanner,
)
from phenopred.domain.value_objects import Finding


# ---------------------------------------------------------------------------
# 1. Boundary behaviour -- empty input
# ---------------------------------------------------------------------------


def test_empty_data_rows_returns_zero_finding() -> None:
    finding = MissingValueScanner().check((), (0,))
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_empty_designated_column_indices_returns_zero_finding() -> None:
    rows = (DataRow(0, ("rs1", "1", "100", "A", "G")),)
    finding = MissingValueScanner().check(rows, ())
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_both_empty_returns_zero_finding() -> None:
    finding = MissingValueScanner().check((), ())
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


# ---------------------------------------------------------------------------
# 2. count = total occurrences, not distinct-value count
# ---------------------------------------------------------------------------


def test_count_is_total_occurrences_not_distinct_values() -> None:
    rows = (
        DataRow(0, ("A",)),
        DataRow(1, ("0",)),
        DataRow(2, ("A",)),
        DataRow(3, ("0",)),
        DataRow(4, ("0",)),
    )
    finding = MissingValueScanner().check(rows, (0,))
    # 5 total occurrences across 2 distinct values ("A": 2, "0": 3).
    assert finding.count == 5


def test_repeated_values_are_aggregated_correctly() -> None:
    rows = tuple(DataRow(i, ("X",)) for i in range(7))
    finding = MissingValueScanner().check(rows, (0,))
    assert finding.count == 7
    assert finding.examples == ("X (7)",)
    assert finding.affected_row_refs == (0,)


# ---------------------------------------------------------------------------
# 3. Descending frequency ordering + line_index tie-break
# ---------------------------------------------------------------------------


def test_examples_ordered_by_descending_frequency() -> None:
    rows = (
        DataRow(0, ("A",)),  # A: 2
        DataRow(1, ("0",)),  # 0: 3 (higher frequency, later line_index)
        DataRow(2, ("A",)),
        DataRow(3, ("0",)),
        DataRow(4, ("0",)),
    )
    finding = MissingValueScanner().check(rows, (0,))
    # "0" has higher frequency (3) than "A" (2), so it must come first
    # despite "A" being first-observed earlier (line_index 0 vs 1).
    assert finding.examples == ("0 (3)", "A (2)")
    assert finding.affected_row_refs == (1, 0)


def test_tie_resolved_by_ascending_first_observed_line_index() -> None:
    rows = (
        DataRow(0, ("B",)),  # first-observed for "B"
        DataRow(1, ("A",)),  # first-observed for "A"
        DataRow(2, ("B",)),
        DataRow(3, ("A",)),
    )
    finding = MissingValueScanner().check(rows, (0,))
    # "B" and "A" are tied at frequency 2 each; "B" first observed at
    # line_index 0, "A" at line_index 1 -> "B" must come first.
    assert finding.examples == ("B (2)", "A (2)")
    assert finding.affected_row_refs == (0, 1)


def test_high_frequency_value_not_excluded_by_positional_ordering() -> None:
    # A rare, early value must not push out a common, later value from
    # the bounded 10-entry sample under descending-frequency ordering.
    rows = (DataRow(0, ("rare",)),) + tuple(
        DataRow(i, ("common",)) for i in range(1, 21)
    )
    finding = MissingValueScanner().check(rows, (0,))
    assert finding.examples[0] == "common (20)"
    assert finding.affected_row_refs[0] == 1


# ---------------------------------------------------------------------------
# 4. More than 10 distinct values (truncation, count uncapped)
# ---------------------------------------------------------------------------


def test_more_than_ten_distinct_values_truncates_examples_and_refs() -> None:
    # 15 distinct values, each with a distinct descending frequency so
    # ordering is unambiguous: value i has frequency (15 - i).
    rows: list[DataRow] = []
    line_index = 0
    for i in range(15):
        frequency = 15 - i
        for _ in range(frequency):
            rows.append(DataRow(line_index, (f"v{i}",)))
            line_index += 1
    finding = MissingValueScanner().check(tuple(rows), (0,))
    assert len(finding.examples) == 10
    assert len(finding.affected_row_refs) == 10
    # count must reflect the full, unsampled total occurrence count.
    assert finding.count == sum(15 - i for i in range(15))
    # Highest-frequency value ("v0", frequency 15) must be first.
    assert finding.examples[0] == "v0 (15)"


# ---------------------------------------------------------------------------
# 5. Out-of-bounds designated indices (malformed-row handling)
# ---------------------------------------------------------------------------


def test_out_of_bounds_index_for_some_rows_contributes_no_observation() -> None:
    rows = (
        DataRow(0, ("A", "B")),  # index 1 valid -> "B"
        DataRow(1, ("A",)),  # index 1 out of bounds -> skipped
        DataRow(2, ("A", "C")),  # index 1 valid -> "C"
    )
    finding = MissingValueScanner().check(rows, (1,))
    assert finding.count == 2
    assert set(finding.examples) == {"B (1)", "C (1)"}


def test_out_of_bounds_index_for_all_rows_returns_zero_finding() -> None:
    rows = (
        DataRow(0, ("A",)),
        DataRow(1, ("A",)),
    )
    finding = MissingValueScanner().check(rows, (5,))
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_no_exception_raised_for_out_of_bounds_indices() -> None:
    rows = (DataRow(0, ()),)
    # Should not raise, despite index 0 being out of bounds for an
    # empty fields tuple.
    finding = MissingValueScanner().check(rows, (0,))
    assert finding.count == 0


# ---------------------------------------------------------------------------
# 6. Multiple designated columns
# ---------------------------------------------------------------------------


def test_multiple_designated_columns_combined() -> None:
    rows = (
        DataRow(0, ("A", "G")),
        DataRow(1, ("A", "A")),
        DataRow(2, ("0", "0")),
    )
    finding = MissingValueScanner().check(rows, (0, 1))
    # Observations: A(row0 col0), G(row0 col1), A(row1 col0),
    # A(row1 col1), 0(row2 col0), 0(row2 col1)
    # -> A: 3, G: 1, 0: 2 => total = 6
    assert finding.count == 6
    assert finding.examples[0] == "A (3)"


# ---------------------------------------------------------------------------
# 7. Duplicate designated column indices
# ---------------------------------------------------------------------------


def test_duplicate_designated_column_indices_double_counts_per_contract() -> None:
    # The frozen contract places no uniqueness requirement on
    # designated_column_indices; each index is processed independently,
    # so a duplicated index observes the same field twice per row.
    rows = (DataRow(0, ("A",)),)
    finding = MissingValueScanner().check(rows, (0, 0))
    assert finding.count == 2
    assert finding.examples == ("A (2)",)


# ---------------------------------------------------------------------------
# 8. Determinism
# ---------------------------------------------------------------------------


def test_repeated_execution_produces_identical_finding() -> None:
    rows = (
        DataRow(0, ("A", "B")),
        DataRow(1, ("0", "B")),
        DataRow(2, ("A", "0")),
    )
    scanner = MissingValueScanner()
    first = scanner.check(rows, (0, 1))
    second = scanner.check(rows, (0, 1))
    assert first == second


def test_result_independent_of_input_traversal_order() -> None:
    rows = (
        DataRow(0, ("A",)),
        DataRow(1, ("0",)),
        DataRow(2, ("A",)),
        DataRow(3, ("0",)),
        DataRow(4, ("0",)),
    )
    shuffled = list(rows)
    random.Random(7).shuffle(shuffled)
    scanner = MissingValueScanner()
    ordered_result = scanner.check(rows, (0,))
    shuffled_result = scanner.check(shuffled, (0,))
    assert ordered_result.count == shuffled_result.count
    assert ordered_result.examples == shuffled_result.examples
    assert ordered_result.affected_row_refs == shuffled_result.affected_row_refs


def test_ordering_independent_of_dict_and_set_iteration_order() -> None:
    # Constructed via two structurally different, but logically
    # equivalent, input orderings/paths to confirm no reliance on
    # dict/set/Counter insertion order.
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
    scanner = MissingValueScanner()
    result_a = scanner.check(rows_a, (0,))
    result_b = scanner.check(rows_b, (0,))
    assert result_a.count == result_b.count
    assert result_a.examples == result_b.examples
    assert result_a.affected_row_refs == result_b.affected_row_refs


# ---------------------------------------------------------------------------
# 9. Non-mutation
# ---------------------------------------------------------------------------


def test_input_data_rows_not_mutated() -> None:
    rows = [DataRow(0, ("A",)), DataRow(1, ("0",))]
    original_copy = list(rows)
    MissingValueScanner().check(rows, (0,))
    assert rows == original_copy


def test_designated_column_indices_not_mutated() -> None:
    indices = [0, 1]
    original_copy = list(indices)
    rows = (DataRow(0, ("A", "B")),)
    MissingValueScanner().check(rows, indices)
    assert indices == original_copy


def test_data_row_instances_not_mutated() -> None:
    row = DataRow(0, ("A", "B"))
    MissingValueScanner().check((row,), (0, 1))
    assert row.line_index == 0
    assert row.fields == ("A", "B")


# ---------------------------------------------------------------------------
# 10. Finding contract validation
# ---------------------------------------------------------------------------


def test_return_type_is_finding() -> None:
    finding = MissingValueScanner().check((DataRow(0, ("A",)),), (0,))
    assert isinstance(finding, Finding)


def test_check_name_is_stable_label() -> None:
    finding = MissingValueScanner().check((DataRow(0, ("A",)),), (0,))
    assert finding.check_name == "missing_value_scanner"


def test_never_raises_across_varied_inputs() -> None:
    scanner = MissingValueScanner()
    scanner.check((), ())
    scanner.check((), (0,))
    scanner.check((DataRow(0, ()),), (0,))
    scanner.check((DataRow(0, ("A",)),), (5,))
    scanner.check((DataRow(0, ("A", "B")),), (0, 1, 2))


# ---------------------------------------------------------------------------
# 11. Dependency boundaries (structural, AST-based)
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


def test_missing_value_scanner_never_imports_errors_module() -> None:
    imported = _imported_module_names(missing_value_scanner_module)
    assert not any("errors" in name for name in imported)


def test_missing_value_scanner_never_imports_upstream_or_sibling_modules() -> None:
    imported = _imported_module_names(missing_value_scanner_module)
    forbidden_substrings = [
        "raw_file_loader",
        "encoding_detector",
        "raw_line_splitter",
        "delimiter_detector",
        "header_resolver",
        "row_parser",
        "report_builder",
        "duplicate_header_check",
        "malformed_row_check",
        "duplicate_rsid_check",
        "duplicate_chr_pos_check",
        "chromosome_label_profiler",
        "genotype_layout_classifier",
        "indel_haploid_classifier",
        "interfaces",
    ]
    for name in imported:
        for forbidden in forbidden_substrings:
            assert forbidden not in name, f"forbidden import found: {name}"


def test_missing_value_scanner_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(missing_value_scanner_module)
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
