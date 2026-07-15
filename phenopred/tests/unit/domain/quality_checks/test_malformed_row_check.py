# tests/unit/domain/quality_checks/test_malformed_row_check.py
"""Unit tests for MalformedRowCheck (FR-5).

Mirrors the testing approach established by test_row_parser.py and the
DuplicateHeaderCheck test suite described in its approval record: small,
synthetic, in-memory fixtures only, no file I/O, exercising exactly the
structural properties named by the frozen Implementation Readiness
Specification and the frozen Architecture Decision Record resolving
Deferred Decision B.4 ("first observed column count wins, using ascending
DataRow.line_index ordering").

Scope discipline: this suite verifies MalformedRowCheck's interaction
with DataRow/Finding only. It does not test, anticipate, or stub
ColumnCountDistribution, ReportBuilder, or any other deferred component.
"""

from __future__ import annotations

import ast
import random

from phenopred.domain.entities import DataRow
from phenopred.domain.quality_checks import (
    malformed_row_check as malformed_row_check_module,
)
from phenopred.domain.quality_checks.malformed_row_check import (
    MalformedRowCheck,
)
from phenopred.domain.value_objects import Finding


# ---------------------------------------------------------------------------
# 1. Modal count behaviour -- unique modal column count
# ---------------------------------------------------------------------------


def test_unique_modal_column_count_no_malformed_rows() -> None:
    rows = tuple(DataRow(i, ("a", "b", "c")) for i in range(5))
    finding = MalformedRowCheck().check(rows)
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_unique_modal_column_count_flags_deviating_rows() -> None:
    rows = (
        DataRow(0, ("a", "b", "c")),
        DataRow(1, ("a", "b", "c")),
        DataRow(2, ("a", "b", "c")),
        DataRow(3, ("a", "b")),
    )
    finding = MalformedRowCheck().check(rows)
    assert finding.count == 1
    assert finding.affected_row_refs == (3,)


# ---------------------------------------------------------------------------
# 2. Modal count behaviour -- two-way and multi-way ties
# ---------------------------------------------------------------------------


def test_two_way_modal_tie_resolved_by_smallest_line_index() -> None:
    # line 1 -> 5 fields, line 2 -> 7 fields, line 3 -> 5 fields,
    # line 4 -> 7 fields (frozen ADR worked example).
    rows = (
        DataRow(0, tuple("12345")),
        DataRow(1, tuple("1234567")),
        DataRow(2, tuple("12345")),
        DataRow(3, tuple("1234567")),
    )
    finding = MalformedRowCheck().check(rows)
    # Tied candidates {5, 7}; smallest line_index (0) has 5 fields, so
    # modal_count == 5 and the 7-field rows (line_index 1, 3) are malformed.
    assert finding.count == 2
    assert finding.affected_row_refs == (1, 3)


def test_multi_way_modal_tie_resolved_by_smallest_line_index() -> None:
    # Three field-count values (3, 4, 5) each occur twice; the earliest
    # line_index (5) belongs to a 3-field row, so modal_count == 3.
    rows = (
        DataRow(5, ("a", "b", "c")),
        DataRow(6, ("a", "b", "c", "d")),
        DataRow(7, ("a", "b", "c", "d", "e")),
        DataRow(8, ("a", "b", "c")),
        DataRow(9, ("a", "b", "c", "d")),
        DataRow(10, ("a", "b", "c", "d", "e")),
    )
    finding = MalformedRowCheck().check(rows)
    assert finding.count == 4
    assert finding.affected_row_refs == (6, 7, 9, 10)


def test_tie_resolution_uses_line_index_not_field_count_magnitude() -> None:
    # Deliberately construct a tie where the smallest line_index belongs
    # to the LARGER field-count candidate, to prove the rule is anchored
    # to line_index and not to "smallest count wins" or "largest count
    # wins".
    rows = (
        DataRow(0, tuple("1234567")),  # 7 fields, smallest line_index
        DataRow(1, tuple("12345")),  # 5 fields
        DataRow(2, tuple("1234567")),  # 7 fields
        DataRow(3, tuple("12345")),  # 5 fields
    )
    finding = MalformedRowCheck().check(rows)
    # modal_count must be 7 (line_index 0's field count), so the 5-field
    # rows (line_index 1, 3) are malformed -- not the 7-field rows.
    assert finding.count == 2
    assert finding.affected_row_refs == (1, 3)


# ---------------------------------------------------------------------------
# 3. Determinism
# ---------------------------------------------------------------------------


def test_repeated_execution_produces_identical_finding() -> None:
    rows = (
        DataRow(0, ("a", "b", "c")),
        DataRow(1, ("a", "b")),
        DataRow(2, ("a", "b", "c")),
    )
    check = MalformedRowCheck()
    first = check.check(rows)
    second = check.check(rows)
    assert first == second


def test_result_independent_of_input_traversal_order() -> None:
    rows = (
        DataRow(5, ("a", "b", "c")),
        DataRow(6, ("a", "b", "c", "d")),
        DataRow(7, ("a", "b", "c", "d", "e")),
        DataRow(8, ("a", "b", "c")),
        DataRow(9, ("a", "b", "c", "d")),
        DataRow(10, ("a", "b", "c", "d", "e")),
    )
    shuffled = list(rows)
    random.Random(42).shuffle(shuffled)
    check = MalformedRowCheck()
    ordered_result = check.check(rows)
    shuffled_result = check.check(shuffled)
    assert ordered_result.count == shuffled_result.count
    assert ordered_result.affected_row_refs == shuffled_result.affected_row_refs
    assert ordered_result.examples == shuffled_result.examples


def test_examples_and_affected_row_refs_in_ascending_line_index_order() -> None:
    rows = (
        DataRow(3, ("a", "b")),
        DataRow(1, ("a", "b", "c")),
        DataRow(2, ("a", "b")),
        DataRow(0, ("a", "b", "c")),
    )
    finding = MalformedRowCheck().check(rows)
    # modal is 3 fields (tie between line_index 0 and 1 at freq 2 vs
    # 2-field rows also freq 2 -- tie among {2, 3}; smallest line_index
    # overall is 0, which has 3 fields, so modal_count == 3).
    assert finding.affected_row_refs == tuple(
        sorted(finding.affected_row_refs)
    )


# ---------------------------------------------------------------------------
# 4. Edge cases
# ---------------------------------------------------------------------------


def test_empty_data_rows_returns_zero_count_finding() -> None:
    finding = MalformedRowCheck().check(())
    assert finding.count == 0
    assert finding.examples == ()
    assert finding.affected_row_refs == ()


def test_single_row_is_never_malformed() -> None:
    finding = MalformedRowCheck().check((DataRow(0, ("a", "b")),))
    assert finding.count == 0


def test_all_rows_same_width_yields_zero_malformed() -> None:
    rows = tuple(DataRow(i, ("a", "b", "c", "d")) for i in range(10))
    finding = MalformedRowCheck().check(rows)
    assert finding.count == 0


def test_non_sequential_line_index_values_still_resolve_correctly() -> None:
    rows = (
        DataRow(100, ("a", "b")),
        DataRow(50, ("a", "b", "c")),
        DataRow(75, ("a", "b")),
    )
    finding = MalformedRowCheck().check(rows)
    assert finding.count == 1
    assert finding.affected_row_refs == (50,)


def test_more_than_ten_malformed_rows_truncates_examples_and_refs() -> None:
    rows = tuple(DataRow(i, ("a", "b")) for i in range(20)) + tuple(
        DataRow(20 + i, ("a", "b", "c")) for i in range(15)
    )
    finding = MalformedRowCheck().check(rows)
    assert finding.count == 15
    assert len(finding.examples) == 10
    assert len(finding.affected_row_refs) == 10
    assert finding.affected_row_refs == tuple(range(20, 30))


# ---------------------------------------------------------------------------
# 5. Finding contract validation
# ---------------------------------------------------------------------------


def test_return_type_is_finding() -> None:
    finding = MalformedRowCheck().check((DataRow(0, ("a",)),))
    assert isinstance(finding, Finding)


def test_check_name_is_stable_label() -> None:
    finding = MalformedRowCheck().check((DataRow(0, ("a",)),))
    assert finding.check_name == "malformed_row_check"


def test_count_reflects_full_unsampled_collection() -> None:
    rows = tuple(DataRow(i, ("a", "b")) for i in range(20)) + tuple(
        DataRow(20 + i, ("a", "b", "c")) for i in range(15)
    )
    finding = MalformedRowCheck().check(rows)
    # count must reflect the true total (15), never capped by the
    # examples/affected_row_refs 10-entry bound.
    assert finding.count == 15


# ---------------------------------------------------------------------------
# 6. Non-mutation
# ---------------------------------------------------------------------------


def test_input_collection_is_not_mutated() -> None:
    rows = [DataRow(0, ("a", "b")), DataRow(1, ("a", "b", "c"))]
    original_copy = list(rows)
    MalformedRowCheck().check(rows)
    assert rows == original_copy


def test_data_row_instances_are_not_mutated() -> None:
    row = DataRow(0, ("a", "b", "c"))
    MalformedRowCheck().check((row,))
    assert row.line_index == 0
    assert row.fields == ("a", "b", "c")


# ---------------------------------------------------------------------------
# 7. Dependency boundaries (structural, AST-based)
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


def test_malformed_row_check_never_imports_errors_module() -> None:
    imported = _imported_module_names(malformed_row_check_module)
    assert not any("errors" in name for name in imported)


def test_malformed_row_check_never_imports_upstream_or_sibling_modules() -> None:
    imported = _imported_module_names(malformed_row_check_module)
    forbidden_substrings = [
        "raw_file_loader",
        "encoding_detector",
        "raw_line_splitter",
        "delimiter_detector",
        "header_resolver",
        "row_parser",
        "report_builder",
        "duplicate_header_check",
        "interfaces",
    ]
    for name in imported:
        for forbidden in forbidden_substrings:
            assert forbidden not in name, f"forbidden import found: {name}"


def test_malformed_row_check_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(malformed_row_check_module)
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
