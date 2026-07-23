# tests/unit/domain/genomic_profiling/test_chromosome_label_profiler.py
"""Unit tests for ChromosomeLabelProfiler (FR-10).

Mirrors the testing approach established by
tests/unit/domain/quality_checks/test_duplicate_rsid_check.py,
test_missing_value_scanner.py, and test_duplicate_header_check.py: small,
synthetic, in-memory fixtures only, no file I/O, exercising exactly the
structural properties named by FR-10, the GenomicProfiler Protocol
(interfaces.py), ChromosomeLabelInventory's frozen contract
(value_objects.py), and ADR-1, ADR-4, ADR-6, and ADR-7 as recorded in
PhenoPred_Genomic_Profiling_ADRs.md.

Scope discipline: this suite verifies ChromosomeLabelProfiler only. It
does not test, anticipate, or stub any sibling GenomicProfiler
(GenotypeLayoutClassifier, IndelHaploidClassifier) or any QualityCheck.

Ordering contract note: label_counts ordering follows each label's first
encounter during traversal of the supplied data_rows sequence (ADR-4).
Under normal, contract-respecting construction, data_rows is always
produced by RowParser in ascending DataRow.line_index order, so
traversal order and ascending-line_index order coincide; this suite's
fixtures are constructed in that same, in-contract order throughout.
Arbitrary permutation of data_rows out of ascending-line_index order is
not part of this profiler's contract and is not exercised here.
"""

from __future__ import annotations

import ast

from phenopred.domain.entities import DataRow
from phenopred.domain.genomic_profiling import (
    chromosome_label_profiler as chromosome_label_profiler_module,
)
from phenopred.domain.genomic_profiling.chromosome_label_profiler import (
    ChromosomeLabelProfiler,
)
from phenopred.domain.interfaces import GenomicProfiler
from phenopred.domain.value_objects import ChromosomeLabelInventory


# ---------------------------------------------------------------------------
# 1. Normal behaviour: single and multiple distinct labels
# ---------------------------------------------------------------------------


def test_single_label_all_rows_counted_correctly() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "G")),
        DataRow(line_index=2, fields=("rs3", "1", "300", "T")),
    )
    inventory = ChromosomeLabelProfiler().profile(rows, 1)
    assert inventory.label_counts == (("1", 3),)


def test_multiple_distinct_labels_each_counted_independently() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1")),
        DataRow(line_index=1, fields=("rs2", "X")),
        DataRow(line_index=2, fields=("rs3", "1")),
        DataRow(line_index=3, fields=("rs4", "X")),
        DataRow(line_index=4, fields=("rs5", "1")),
    )
    inventory = ChromosomeLabelProfiler().profile(rows, 1)
    counts = dict(inventory.label_counts)
    assert counts == {"1": 3, "X": 2}


# ---------------------------------------------------------------------------
# 2. Ordering (ADR-4): first observation during traversal, never frequency
# ---------------------------------------------------------------------------


def test_label_counts_ordered_by_ascending_first_observed_line_index() -> None:
    # "X" has lower frequency (2) but an earlier first-observed
    # line_index (0) than "1" (frequency 3, first observed at
    # line_index 1). Ordering by first observation during traversal
    # requires "X" to come first, despite "1" having the higher count.
    rows = (
        DataRow(line_index=0, fields=("rs1", "X")),
        DataRow(line_index=1, fields=("rs2", "1")),
        DataRow(line_index=2, fields=("rs3", "X")),
        DataRow(line_index=3, fields=("rs4", "1")),
        DataRow(line_index=4, fields=("rs5", "1")),
    )
    inventory = ChromosomeLabelProfiler().profile(rows, 1)
    assert inventory.label_counts == (("X", 2), ("1", 3))


def test_label_counts_ordering_follows_first_observation_not_frequency() -> None:
    # Three distinct labels, first observed in the order B, A, C during
    # normal (ascending line_index) traversal. Frequencies are deliberately
    # arranged so that a frequency-based ordering (A:4, C:2, B:1) would
    # disagree with first-observation ordering (B, A, C) -- confirming
    # the output follows observation order, never descending or
    # ascending frequency.
    rows = (
        DataRow(line_index=0, fields=("rs1", "B")),
        DataRow(line_index=1, fields=("rs2", "A")),
        DataRow(line_index=2, fields=("rs3", "A")),
        DataRow(line_index=3, fields=("rs4", "C")),
        DataRow(line_index=4, fields=("rs5", "A")),
        DataRow(line_index=5, fields=("rs6", "C")),
        DataRow(line_index=6, fields=("rs7", "A")),
    )
    inventory = ChromosomeLabelProfiler().profile(rows, 1)
    assert inventory.label_counts == (("B", 1), ("A", 4), ("C", 2))


def test_established_first_observation_ordering_unaffected_by_relative_frequency_changes() -> None:
    # Two fixtures share the same first-observation sequence of labels
    # ("alpha" then "zeta"), both supplied in normal ascending
    # line_index traversal order, but with different relative
    # frequencies between the two runs (in fixture one "alpha" is more
    # frequent; in fixture two "zeta" is more frequent). The established
    # first-observation ordering (alpha, zeta) must be identical in both
    # cases -- frequency has no bearing on label_counts ordering.
    rows_alpha_more_frequent = (
        DataRow(line_index=0, fields=("rs1", "alpha")),
        DataRow(line_index=1, fields=("rs2", "alpha")),
        DataRow(line_index=2, fields=("rs3", "alpha")),
        DataRow(line_index=3, fields=("rs4", "zeta")),
    )
    rows_zeta_more_frequent = (
        DataRow(line_index=0, fields=("rs1", "alpha")),
        DataRow(line_index=1, fields=("rs2", "zeta")),
        DataRow(line_index=2, fields=("rs3", "zeta")),
        DataRow(line_index=3, fields=("rs4", "zeta")),
    )
    profiler = ChromosomeLabelProfiler()
    result_a = profiler.profile(rows_alpha_more_frequent, 1)
    result_b = profiler.profile(rows_zeta_more_frequent, 1)
    assert [label for label, _ in result_a.label_counts] == ["alpha", "zeta"]
    assert [label for label, _ in result_b.label_counts] == ["alpha", "zeta"]


# ---------------------------------------------------------------------------
# 3. Boundary behaviour: empty input and out-of-bounds index
# ---------------------------------------------------------------------------


def test_empty_data_rows_returns_empty_inventory() -> None:
    inventory = ChromosomeLabelProfiler().profile((), 0)
    assert inventory.label_counts == ()


def test_out_of_bounds_index_for_some_rows_contributes_no_observation() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1")),  # index 1 valid -> "1"
        DataRow(line_index=1, fields=("rs2",)),  # index 1 out of bounds -> skipped
        DataRow(line_index=2, fields=("rs3", "2")),  # index 1 valid -> "2"
    )
    inventory = ChromosomeLabelProfiler().profile(rows, 1)
    assert inventory.label_counts == (("1", 1), ("2", 1))


def test_out_of_bounds_index_for_all_rows_returns_empty_inventory() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1",)),
        DataRow(line_index=1, fields=("rs2",)),
    )
    inventory = ChromosomeLabelProfiler().profile(rows, 5)
    assert inventory.label_counts == ()


def test_no_exception_raised_for_out_of_bounds_index_on_empty_fields() -> None:
    rows = (DataRow(line_index=0, fields=()),)
    # Should not raise, despite index 0 being out of bounds for an
    # empty fields tuple.
    inventory = ChromosomeLabelProfiler().profile(rows, 0)
    assert inventory.label_counts == ()


# ---------------------------------------------------------------------------
# 4. Exact-equality / no-interpretation behaviour
# ---------------------------------------------------------------------------


def test_no_case_folding_of_labels() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "x")),
        DataRow(line_index=1, fields=("rs2", "X")),
    )
    inventory = ChromosomeLabelProfiler().profile(rows, 1)
    assert inventory.label_counts == (("x", 1), ("X", 1))


def test_no_normalization_or_trimming_of_labels() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1")),
        DataRow(line_index=1, fields=("rs2", " 1")),
    )
    inventory = ChromosomeLabelProfiler().profile(rows, 1)
    assert inventory.label_counts == (("1", 1), (" 1", 1))


def test_no_biological_or_vendor_specific_interpretation_of_labels() -> None:
    # Synthetic labels matching neither AncestryDNA's nor 23andMe's
    # evidenced conventions must still be reported exactly as given,
    # with no mapping, filtering, or reconciliation applied.
    rows = (
        DataRow(line_index=0, fields=("rs1", "unknown_chr_99")),
        DataRow(line_index=1, fields=("rs2", "scaffold_42")),
        DataRow(line_index=2, fields=("rs3", "unknown_chr_99")),
    )
    inventory = ChromosomeLabelProfiler().profile(rows, 1)
    assert inventory.label_counts == (("unknown_chr_99", 2), ("scaffold_42", 1))


# ---------------------------------------------------------------------------
# 5. Determinism and non-mutation
# ---------------------------------------------------------------------------


def test_repeated_execution_produces_identical_inventory() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1")),
        DataRow(line_index=1, fields=("rs2", "X")),
        DataRow(line_index=2, fields=("rs3", "1")),
    )
    profiler = ChromosomeLabelProfiler()
    first = profiler.profile(rows, 1)
    second = profiler.profile(rows, 1)
    assert first == second


def test_input_data_rows_not_mutated() -> None:
    rows = [
        DataRow(line_index=0, fields=("rs1", "1")),
        DataRow(line_index=1, fields=("rs2", "X")),
    ]
    original_copy = list(rows)
    ChromosomeLabelProfiler().profile(rows, 1)
    assert rows == original_copy


def test_data_row_instances_not_mutated() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1"))
    ChromosomeLabelProfiler().profile((row,), 1)
    assert row.line_index == 0
    assert row.fields == ("rs1", "1")


# ---------------------------------------------------------------------------
# 6. Output contract: ChromosomeLabelInventory shape
# ---------------------------------------------------------------------------


def test_return_type_is_chromosome_label_inventory() -> None:
    inventory = ChromosomeLabelProfiler().profile((), 0)
    assert isinstance(inventory, ChromosomeLabelInventory)


def test_profiler_name_is_stable_label() -> None:
    inventory = ChromosomeLabelProfiler().profile((), 0)
    assert inventory.profiler_name == "chromosome_label_profiler"


def test_never_raises_across_varied_inputs() -> None:
    profiler = ChromosomeLabelProfiler()
    profiler.profile((), 0)
    profiler.profile((DataRow(line_index=0, fields=()),), 0)
    profiler.profile((DataRow(line_index=0, fields=("rs1", "1")),), 5)
    profiler.profile((DataRow(line_index=0, fields=("rs1", "1")),), 1)


# ---------------------------------------------------------------------------
# 7. Protocol compliance
# ---------------------------------------------------------------------------


def test_chromosome_label_profiler_satisfies_genomic_profiler_protocol() -> None:
    assert isinstance(ChromosomeLabelProfiler(), GenomicProfiler)


# ---------------------------------------------------------------------------
# 8. Dependency boundaries (structural, AST-based)
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


def test_chromosome_label_profiler_never_imports_errors_module() -> None:
    imported = _imported_module_names(chromosome_label_profiler_module)
    assert not any("errors" in name for name in imported)


def test_chromosome_label_profiler_never_imports_upstream_or_sibling_modules() -> None:
    imported = _imported_module_names(chromosome_label_profiler_module)
    forbidden_substrings = [
        "raw_file_loader",
        "encoding_detector",
        "raw_line_splitter",
        "delimiter_detector",
        "header_resolver",
        "row_parser",
        "quality_checks",
        "malformed_row_check",
        "duplicate_header_check",
        "missing_value_scanner",
        "duplicate_rsid_check",
        "duplicate_chr_pos_check",
        "genotype_layout_classifier",
        "indel_haploid_classifier",
        "report_builder",
    ]
    for name in imported:
        for forbidden in forbidden_substrings:
            assert forbidden not in name, f"forbidden import found: {name}"


def test_chromosome_label_profiler_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(chromosome_label_profiler_module)
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