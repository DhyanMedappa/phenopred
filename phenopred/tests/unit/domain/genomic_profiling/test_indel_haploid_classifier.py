# tests/unit/domain/genomic_profiling/test_indel_haploid_classifier.py
"""Unit tests for IndelHaploidClassifier (FR-12).

Mirrors the testing approach established by
tests/unit/domain/genomic_profiling/test_chromosome_label_profiler.py,
test_genotype_layout_classifier.py, and
tests/unit/domain/quality_checks/test_duplicate_rsid_check.py,
test_missing_value_scanner.py, and test_duplicate_header_check.py: small,
synthetic, in-memory fixtures only, no file I/O, exercising exactly the
structural properties named by FR-12, the GenomicProfiler Protocol
(interfaces.py), IndelHaploidProfile's frozen contract (value_objects.py),
and ADR-1, ADR-2, ADR-4, ADR-6, and ADR-7 as recorded in
PhenoPred_Genomic_Profiling_ADRs.md.

Scope discipline: this suite verifies IndelHaploidClassifier only. It
does not test, anticipate, or stub any sibling GenomicProfiler
(ChromosomeLabelProfiler, GenotypeLayoutClassifier) or any QualityCheck.

Biological abstraction discipline: IndelHaploidClassifier performs pure
structural observation -- exact-match token counting and genotype-string
length classification against constructor-injected configuration -- with
no biological interpretation of any kind. Primary fixtures in this suite
use arbitrary, non-biological synthetic identifiers (e.g. "TOK_A",
"LBL_X") rather than the SRS-evidenced default vocabulary ("II", "DD",
"DI", "X", "Y", "MT"), to verify the mechanism is generic structural
observation, not indel- or chromosome-specific logic.
"""

from __future__ import annotations

import ast

from phenopred.domain.entities import DataRow
from phenopred.domain.genomic_profiling import (
    indel_haploid_classifier as indel_haploid_classifier_module,
)
from phenopred.domain.genomic_profiling.indel_haploid_classifier import (
    IndelHaploidClassifier,
)
from phenopred.domain.interfaces import GenomicProfiler
from phenopred.domain.value_objects import (
    GenotypeChromosomeColumnIndices,
    IndelHaploidProfile,
)


# ---------------------------------------------------------------------------
# 1. Applicability gate
# ---------------------------------------------------------------------------


def test_exactly_one_designated_column_is_applicable() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "LBL_X", "TOK_A")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.applicable is True


def test_zero_two_or_three_designated_columns_are_not_applicable() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "LBL_X", "TOK_A", "TOK_B")),)
    classifier = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    )

    context_zero = GenotypeChromosomeColumnIndices(
        designated_column_indices=(), chromosome_column_index=1
    )
    assert classifier.profile(rows, context_zero).applicable is False

    context_two = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2, 3), chromosome_column_index=1
    )
    assert classifier.profile(rows, context_two).applicable is False

    context_three = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2, 3, 1), chromosome_column_index=1
    )
    assert classifier.profile(rows, context_three).applicable is False


def test_non_applicable_result_has_zero_or_empty_values_for_every_other_field() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "LBL_X", "TOK_A")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.applicable is False
    assert profile.indel_token_counts == ()
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


# ---------------------------------------------------------------------------
# 2. Indel-token counting: arbitrary, non-biological vocabulary
# ---------------------------------------------------------------------------


def test_configured_indel_tokens_counted_by_exact_match() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "chrom", "TOK_A")),
        DataRow(line_index=1, fields=("rs2", "chrom", "TOK_B")),
        DataRow(line_index=2, fields=("rs3", "chrom", "TOK_A")),
    )
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A", "TOK_B"), sex_mitochondrial_labels=()
    ).profile(rows, context)
    assert profile.indel_token_counts == (("TOK_A", 2), ("TOK_B", 1))


def test_genotype_values_not_in_configured_token_set_contribute_no_count() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "chrom", "TOK_A")),
        DataRow(line_index=1, fields=("rs2", "chrom", "UNMATCHED")),
    )
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=()
    ).profile(rows, context)
    assert profile.indel_token_counts == (("TOK_A", 1),)


def test_indel_token_counts_ordered_by_constructor_injection_order_not_alphabetical() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "chrom", "TOK_Z")),
        DataRow(line_index=1, fields=("rs2", "chrom", "TOK_A")),
    )
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_Z", "TOK_A"), sex_mitochondrial_labels=()
    ).profile(rows, context)
    assert profile.indel_token_counts == (("TOK_Z", 1), ("TOK_A", 1))


def test_empty_configured_indel_tokens_yields_empty_indel_token_counts() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "chrom", "TOK_A")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=(), sex_mitochondrial_labels=()
    ).profile(rows, context)
    assert profile.applicable is True
    assert profile.indel_token_counts == ()


# ---------------------------------------------------------------------------
# 3. Haploid/diploid classification: arbitrary, non-biological labels
# ---------------------------------------------------------------------------


def test_matching_label_with_length_one_genotype_increments_haploid_count() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "LBL_X", "A")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=(), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.haploid_count == 1
    assert profile.diploid_count == 0


def test_matching_label_with_length_two_genotype_increments_diploid_count() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "LBL_X", "AB")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=(), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.haploid_count == 0
    assert profile.diploid_count == 1


def test_matching_label_with_other_genotype_length_contributes_to_neither_count() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "LBL_X", "")),
        DataRow(line_index=1, fields=("rs2", "LBL_X", "ABC")),
    )
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=(), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


def test_non_matching_label_never_contributes_regardless_of_genotype_length() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "OTHER_LABEL", "A")),
        DataRow(line_index=1, fields=("rs2", "OTHER_LABEL", "AB")),
    )
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=(), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


def test_empty_configured_sex_mitochondrial_labels_yields_zero_haploid_and_diploid_counts() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "LBL_X", "A")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=(), sex_mitochondrial_labels=()
    ).profile(rows, context)
    assert profile.applicable is True
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


# ---------------------------------------------------------------------------
# 4. Independence of indel counting from haploid/diploid gating
# ---------------------------------------------------------------------------


def test_indel_token_counting_unaffected_by_chromosome_label_matching() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "NON_MATCHING_LABEL", "TOK_A")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.indel_token_counts == (("TOK_A", 1),)
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


# ---------------------------------------------------------------------------
# 5. Bounds handling: asymmetric per-observation rules
# ---------------------------------------------------------------------------


def test_genotype_index_out_of_bounds_excludes_row_from_indel_counting() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "LBL_X")),)  # index 2 out of bounds
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=()
    ).profile(rows, context)
    assert profile.indel_token_counts == (("TOK_A", 0),)


def test_negative_genotype_index_excludes_row_from_both_observations() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "LBL_X", "A")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(-1,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.indel_token_counts == (("TOK_A", 0),)
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


def test_genotype_index_out_of_bounds_excludes_row_from_haploid_diploid_even_with_valid_chromosome_index() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "LBL_X")),)  # index 2 out of bounds
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=(), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


def test_chromosome_index_out_of_bounds_excludes_row_from_haploid_diploid_but_not_indel_counting() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "TOK_A")),)  # index 5 out of bounds
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(1,), chromosome_column_index=5
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.indel_token_counts == (("TOK_A", 1),)
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


def test_negative_chromosome_index_excludes_row_from_haploid_diploid_only() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "LBL_X", "TOK_A")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=-1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.indel_token_counts == (("TOK_A", 1),)
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


def test_no_exception_raised_for_out_of_bounds_indices_on_empty_fields() -> None:
    rows = (DataRow(line_index=0, fields=()),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(0,), chromosome_column_index=0
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.indel_token_counts == (("TOK_A", 0),)
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


# ---------------------------------------------------------------------------
# 6. Exact-match discipline
# ---------------------------------------------------------------------------


def test_no_case_folding_in_indel_token_matching() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "chrom", "tok_a")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=()
    ).profile(rows, context)
    assert profile.indel_token_counts == (("TOK_A", 0),)


def test_no_case_folding_in_sex_mitochondrial_label_matching() -> None:
    rows = (DataRow(line_index=0, fields=("rs1", "lbl_x", "A")),)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=(), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


# ---------------------------------------------------------------------------
# 7. Boundary: empty data_rows, applicable case
# ---------------------------------------------------------------------------


def test_empty_data_rows_with_applicable_layout_yields_zero_counts_for_every_configured_token() -> None:
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    profile = IndelHaploidClassifier(
        indel_tokens=("TOK_A", "TOK_B"), sex_mitochondrial_labels=("LBL_X",)
    ).profile((), context)
    assert profile.applicable is True
    assert profile.indel_token_counts == (("TOK_A", 0), ("TOK_B", 0))
    assert profile.haploid_count == 0
    assert profile.diploid_count == 0


# ---------------------------------------------------------------------------
# 8. Determinism and non-mutation
# ---------------------------------------------------------------------------


def test_repeated_execution_produces_identical_profile() -> None:
    rows = (
        DataRow(line_index=0, fields=("rs1", "LBL_X", "TOK_A")),
        DataRow(line_index=1, fields=("rs2", "LBL_X", "AB")),
    )
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    classifier = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    )
    first = classifier.profile(rows, context)
    second = classifier.profile(rows, context)
    assert first == second


def test_input_data_rows_not_mutated() -> None:
    rows = [
        DataRow(line_index=0, fields=("rs1", "LBL_X", "TOK_A")),
        DataRow(line_index=1, fields=("rs2", "LBL_X", "AB")),
    ]
    original_copy = list(rows)
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    ).profile(rows, context)
    assert rows == original_copy


def test_data_row_instances_not_mutated() -> None:
    row = DataRow(line_index=0, fields=("rs1", "LBL_X", "TOK_A"))
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(2,), chromosome_column_index=1
    )
    IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    ).profile((row,), context)
    assert row.line_index == 0
    assert row.fields == ("rs1", "LBL_X", "TOK_A")


# ---------------------------------------------------------------------------
# 9. Output contract: IndelHaploidProfile shape
# ---------------------------------------------------------------------------


def test_return_type_is_indel_haploid_profile() -> None:
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(), chromosome_column_index=0
    )
    profile = IndelHaploidClassifier(
        indel_tokens=(), sex_mitochondrial_labels=()
    ).profile((), context)
    assert isinstance(profile, IndelHaploidProfile)


def test_profiler_name_is_stable_label() -> None:
    context = GenotypeChromosomeColumnIndices(
        designated_column_indices=(), chromosome_column_index=0
    )
    profile = IndelHaploidClassifier(
        indel_tokens=(), sex_mitochondrial_labels=()
    ).profile((), context)
    assert profile.profiler_name == "indel_haploid_classifier"


def test_never_raises_across_varied_inputs() -> None:
    classifier = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    )
    classifier.profile(
        (),
        GenotypeChromosomeColumnIndices(
            designated_column_indices=(), chromosome_column_index=0
        ),
    )
    classifier.profile(
        (DataRow(line_index=0, fields=()),),
        GenotypeChromosomeColumnIndices(
            designated_column_indices=(0,), chromosome_column_index=0
        ),
    )
    classifier.profile(
        (DataRow(line_index=0, fields=("A", "B")),),
        GenotypeChromosomeColumnIndices(
            designated_column_indices=(5,), chromosome_column_index=5
        ),
    )
    classifier.profile(
        (DataRow(line_index=0, fields=("A", "B", "C")),),
        GenotypeChromosomeColumnIndices(
            designated_column_indices=(-1,), chromosome_column_index=-1
        ),
    )


# ---------------------------------------------------------------------------
# 10. Protocol compliance
# ---------------------------------------------------------------------------


def test_indel_haploid_classifier_satisfies_genomic_profiler_protocol() -> None:
    classifier = IndelHaploidClassifier(
        indel_tokens=("TOK_A",), sex_mitochondrial_labels=("LBL_X",)
    )
    assert isinstance(classifier, GenomicProfiler)


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


def test_indel_haploid_classifier_never_imports_errors_module() -> None:
    imported = _imported_module_names(indel_haploid_classifier_module)
    assert not any("errors" in name for name in imported)


def test_indel_haploid_classifier_never_imports_upstream_or_sibling_modules() -> None:
    imported = _imported_module_names(indel_haploid_classifier_module)
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
        "genotype_layout_classifier",
        "report_builder",
    ]
    for name in imported:
        for forbidden in forbidden_substrings:
            assert forbidden not in name, f"forbidden import found: {name}"


def test_indel_haploid_classifier_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(indel_haploid_classifier_module)
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