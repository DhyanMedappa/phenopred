# tests/unit/domain/genomic_profiling/test_genotype_layout_classifier.py
"""Unit tests for GenotypeLayoutClassifier (FR-11).

Mirrors the testing approach established by
tests/unit/domain/genomic_profiling/test_chromosome_label_profiler.py and
tests/unit/domain/quality_checks/test_duplicate_rsid_check.py,
test_missing_value_scanner.py, and test_duplicate_header_check.py: small,
synthetic, in-memory fixtures only, no file I/O, exercising exactly the
structural properties named by FR-11, the GenomicProfiler Protocol
(interfaces.py), GenotypeLayoutProfile's frozen contract
(value_objects.py), and ADR-1, ADR-4, ADR-5, ADR-6, and ADR-7 as recorded
in PhenoPred_Genomic_Profiling_ADRs.md.

Scope discipline: this suite verifies GenotypeLayoutClassifier only. It
does not test, anticipate, or stub any sibling GenomicProfiler
(ChromosomeLabelProfiler, IndelHaploidClassifier) or any QualityCheck.
"""

from __future__ import annotations

import ast

from phenopred.domain.entities import DataRow
from phenopred.domain.genomic_profiling import (
    genotype_layout_classifier as genotype_layout_classifier_module,
)
from phenopred.domain.genomic_profiling.genotype_layout_classifier import (
    GenotypeLayoutClassifier,
)
from phenopred.domain.interfaces import GenomicProfiler
from phenopred.domain.value_objects import GenotypeLayoutProfile


# ---------------------------------------------------------------------------
# 1. Normal behaviour: layout_kind classification branches
# ---------------------------------------------------------------------------


def test_two_designated_columns_classified_as_two_column_allele() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "1", "100", "A", "G")),)
    profile = GenotypeLayoutClassifier().profile(rows, (3, 4))
    assert profile.layout_kind == "two_column_allele"


def test_one_designated_column_classified_as_single_column_genotype() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "1", "100", "AG")),)
    profile = GenotypeLayoutClassifier().profile(rows, (3,))
    assert profile.layout_kind == "single_column_genotype"


def test_zero_designated_columns_classified_as_undetermined() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "1", "100")),)
    profile = GenotypeLayoutClassifier().profile(rows, ())
    assert profile.layout_kind == "undetermined"


def test_three_or_more_designated_columns_classified_as_undetermined() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "1", "100", "A", "B", "C")),)
    profile_three = GenotypeLayoutClassifier().profile(rows, (3, 4, 5))
    assert profile_three.layout_kind == "undetermined"

    rows_four = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A", "B", "C", "D")),
    )
    profile_four = GenotypeLayoutClassifier().profile(rows_four, (3, 4, 5, 6))
    assert profile_four.layout_kind == "undetermined"


# ---------------------------------------------------------------------------
# 2. layout_kind independence from row content
# ---------------------------------------------------------------------------


def test_layout_kind_unaffected_by_row_content_or_row_count() -> None:
    empty_rows: tuple[DataRow, ...] = ()
    many_rows = tuple(
        DataRow(line_index=i, fields=("rs1", "1", "100", "A", "G"))
        for i in range(50)
    )
    classifier = GenotypeLayoutClassifier()
    profile_empty = classifier.profile(empty_rows, (3, 4))
    profile_many = classifier.profile(many_rows, (3, 4))
    assert profile_empty.layout_kind == "two_column_allele"
    assert profile_many.layout_kind == "two_column_allele"


# ---------------------------------------------------------------------------
# 3. column_length_distributions: measurement and ordering
# ---------------------------------------------------------------------------


def test_single_column_length_distribution_measured_correctly() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "AG")),
        DataRow(line_index=2, fields=("rs3", "1", "300", "A")),
    )
    profile = GenotypeLayoutClassifier().profile(rows, (3,))
    assert profile.column_length_distributions == ((3, ((1, 2), (2, 1))),)


def test_multiple_columns_measured_independently() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A", "GG")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "AA", "G")),
    )
    profile = GenotypeLayoutClassifier().profile(rows, (3, 4))
    distributions = dict(profile.column_length_distributions)
    assert distributions[3] == ((1, 1), (2, 1))
    assert distributions[4] == ((1, 1), (2, 1))


def test_column_length_distributions_ordered_by_ascending_column_index_regardless_of_input_order() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "1", "100", "A", "GG")),)
    profile = GenotypeLayoutClassifier().profile(rows, (4, 3))
    column_indices_in_output = [
        column_index for column_index, _ in profile.column_length_distributions
    ]
    assert column_indices_in_output == [3, 4]


def test_length_distribution_ordered_by_ascending_length_not_frequency() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "AAA")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "AAA")),
        DataRow(line_index=2, fields=("rs3", "1", "300", "AAA")),
        DataRow(line_index=3, fields=("rs4", "1", "400", "A")),
    )
    profile = GenotypeLayoutClassifier().profile(rows, (3,))
    # Length 3 has higher frequency (3) than length 1 (1), but ascending
    # length order requires length 1 to come first.
    assert profile.column_length_distributions == ((3, ((1, 1), (3, 3))),)


def test_column_length_distributions_ordering_independent_of_data_rows_traversal_order() -> None:
    # Two data_rows collections carrying identical (row content) ->
    # (length observations) mappings, supplied in different traversal
    # orders. Length distributions are aggregated independently of
    # traversal order and the final ordering is produced through
    # explicit ascending sorts, so both collections must yield an
    # identical result regardless of which row is encountered first.
    rows_in_order = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "AG")),
        DataRow(line_index=2, fields=("rs3", "1", "300", "A")),
    )
    rows_reversed = (
        DataRow(line_index=2, fields=("rs3", "1", "300", "A")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "AG")),
        DataRow(line_index=0, fields=("rs1", "1", "100", "A")),
    )
    classifier = GenotypeLayoutClassifier()
    result_in_order = classifier.profile(rows_in_order, (3,))
    result_reversed = classifier.profile(rows_reversed, (3,))
    assert result_in_order.column_length_distributions == (
        result_reversed.column_length_distributions
    )
    assert result_in_order.column_length_distributions == ((3, ((1, 2), (2, 1))),)


# ---------------------------------------------------------------------------
# 4. Decoupling of column_length_distributions from layout_kind (ADR-5)
# ---------------------------------------------------------------------------


def test_column_length_distributions_computed_for_undetermined_layout_with_three_columns() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A", "GG", "T")),
    )
    profile = GenotypeLayoutClassifier().profile(rows, (3, 4, 5))
    assert profile.layout_kind == "undetermined"
    assert len(profile.column_length_distributions) == 3
    distributions = dict(profile.column_length_distributions)
    assert distributions[3] == ((1, 1),)
    assert distributions[4] == ((2, 1),)
    assert distributions[5] == ((1, 1),)


def test_column_length_distributions_empty_when_zero_designated_columns() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "1", "100")),)
    profile = GenotypeLayoutClassifier().profile(rows, ())
    assert profile.column_length_distributions == ()


# ---------------------------------------------------------------------------
# 5. Boundary cases: empty input and out-of-bounds index
# ---------------------------------------------------------------------------


def test_empty_data_rows_with_designated_columns_yields_present_but_empty_distributions() -> None:
    profile = GenotypeLayoutClassifier().profile((), (3, 4))
    assert profile.column_length_distributions == ((3, ()), (4, ()))


def test_out_of_bounds_index_for_some_rows_in_one_column_does_not_affect_other_columns() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A", "GG")),
        DataRow(line_index=1, fields=("rs2", "1", "200")),  # index 3, 4 out of bounds
        DataRow(line_index=2, fields=("rs3", "1", "300", "AA", "G")),
    )
    profile = GenotypeLayoutClassifier().profile(rows, (3, 4))
    distributions = dict(profile.column_length_distributions)
    assert distributions[3] == ((1, 1), (2, 1))
    assert distributions[4] == ((1, 1), (2, 1))


def test_out_of_bounds_index_for_all_rows_in_one_column_yields_empty_distribution_for_that_column_only() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "AG")),
    )
    profile = GenotypeLayoutClassifier().profile(rows, (3, 10))
    distributions = dict(profile.column_length_distributions)
    assert distributions[3] == ((1, 1), (2, 1))
    assert distributions[10] == ()


def test_no_exception_raised_for_out_of_bounds_index_on_empty_fields() -> None:
    rows = (DataRow(line_index=0, fields=()),)
    profile = GenotypeLayoutClassifier().profile(rows, (0,))
    assert profile.column_length_distributions == ((0, ()),)


# ---------------------------------------------------------------------------
# 6. Determinism and non-mutation
# ---------------------------------------------------------------------------


def test_repeated_execution_produces_identical_profile() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "1", "100", "A", "GG")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "AA", "G")),
    )
    classifier = GenotypeLayoutClassifier()
    first = classifier.profile(rows, (3, 4))
    second = classifier.profile(rows, (3, 4))
    assert first == second


def test_input_data_rows_not_mutated() -> None:
    rows = [
        DataRow(line_index=0, fields=("rs1", "1", "100", "A")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "AG")),
    ]
    original_copy = list(rows)
    GenotypeLayoutClassifier().profile(rows, (3,))
    assert rows == original_copy


def test_data_row_instances_not_mutated() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "A"))
    GenotypeLayoutClassifier().profile((row,), (3,))
    assert row.line_index == 0
    assert row.fields == ("rs1", "1", "100", "A")


def test_designated_column_indices_not_mutated() -> None:
    indices = [3, 4]
    original_copy = list(indices)
    rows = (DataRow(line_index=0, fields=("rs1", "1", "100", "A", "GG")),)
    GenotypeLayoutClassifier().profile(rows, indices)
    assert indices == original_copy


# ---------------------------------------------------------------------------
# 7. Output contract: GenotypeLayoutProfile shape
# ---------------------------------------------------------------------------


def test_return_type_is_genotype_layout_profile() -> None:
    profile = GenotypeLayoutClassifier().profile((), ())
    assert isinstance(profile, GenotypeLayoutProfile)


def test_profiler_name_is_stable_label() -> None:
    profile = GenotypeLayoutClassifier().profile((), ())
    assert profile.profiler_name == "genotype_layout_classifier"


def test_never_raises_across_varied_inputs() -> None:
    classifier = GenotypeLayoutClassifier()
    classifier.profile((), ())
    classifier.profile((), (0,))
    classifier.profile((DataRow(line_index=0, fields=()),), (0,))
    classifier.profile((DataRow(line_index=0, fields=("A", "B")),), (5,))
    classifier.profile((DataRow(line_index=0, fields=("A", "B", "C")),), (1, 2))


# ---------------------------------------------------------------------------
# 8. Protocol compliance
# ---------------------------------------------------------------------------


def test_genotype_layout_classifier_satisfies_genomic_profiler_protocol() -> None:
    assert isinstance(GenotypeLayoutClassifier(), GenomicProfiler)


# ---------------------------------------------------------------------------
# 9. Dependency boundaries (structural, AST-based)
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


def test_genotype_layout_classifier_never_imports_errors_module() -> None:
    imported = _imported_module_names(genotype_layout_classifier_module)
    assert not any("errors" in name for name in imported)


def test_genotype_layout_classifier_never_imports_upstream_or_sibling_modules() -> None:
    imported = _imported_module_names(genotype_layout_classifier_module)
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
        "chromosome_label_profiler",
        "indel_haploid_classifier",
        "report_builder",
    ]
    for name in imported:
        for forbidden in forbidden_substrings:
            assert forbidden not in name, f"forbidden import found: {name}"


def test_genotype_layout_classifier_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(genotype_layout_classifier_module)
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