# tests/unit/domain/reporting/test_open_question_registry.py
"""Unit tests for OpenQuestionRegistry (OUT-9, OBJ-5, AD-7).

Mirrors the testing approach established by test_malformed_row_check.py
and test_entities.py: small, synthetic, in-memory fixtures only, no file
I/O, exercising exactly the selection contract OpenQuestionRegistry's
own docstring and applicable_for() signature guarantee. Real Finding and
Profile value objects are constructed directly (they are plain,
behavior-free data carriers, not collaborators requiring a fake), since
this suite verifies OpenQuestionRegistry's own selection logic against
its actual, documented input contract.

Scope discipline: this suite verifies OpenQuestionRegistry's
applicable_for() selection behaviour only. It does not test
ReportBuilder, ProfileFileUseCase, or any file-ingestion component, and
it does not assert on the exact wording of any OpenQuestion.statement --
only on which questions (identified by related_finding_or_profile and
count) are selected, and in what order, since exact statement wording is
not part of the guaranteed public contract.
"""

from __future__ import annotations

from phenopred.domain.reporting.open_question_registry import (
    OpenQuestionRegistry,
)
from phenopred.domain.value_objects import (
    ChromosomeLabelInventory,
    Finding,
    GenotypeLayoutProfile,
    OpenQuestion,
)


def _make_finding(check_name: str, count: int) -> Finding:
    return Finding(
        check_name=check_name,
        description="fake_description",
        count=count,
        examples=(),
        affected_row_refs=(),
    )


# ---------------------------------------------------------------------------
# 1. Standing questions -- always selected, regardless of input
# ---------------------------------------------------------------------------


def test_empty_findings_and_profiles_selects_only_standing_questions() -> None:
    registry = OpenQuestionRegistry()
    result = registry.applicable_for((), ())
    assert len(result) == 4
    assert [question.related_finding_or_profile for question in result] == [
        None,
        None,
        None,
        "duplicate_rsid_check",
    ]


# ---------------------------------------------------------------------------
# 2. chromosome_label_profiler gating (conventional vs. non-conventional
#    chromosome labels)
# ---------------------------------------------------------------------------


def test_chromosome_label_profiler_with_conventional_labels_selects_exactly_one_related_question() -> None:
    inventory = ChromosomeLabelInventory(
        profiler_name="chromosome_label_profiler",
        label_counts=(("1", 10), ("X", 2), ("MT", 1)),
    )
    registry = OpenQuestionRegistry()
    result = registry.applicable_for((), (inventory,))
    related = [question.related_finding_or_profile for question in result]
    assert related.count("chromosome_label_profiler") == 1


def test_chromosome_label_profiler_with_non_conventional_label_selects_two_related_questions() -> None:
    inventory = ChromosomeLabelInventory(
        profiler_name="chromosome_label_profiler",
        label_counts=(("25", 3),),
    )
    registry = OpenQuestionRegistry()
    result = registry.applicable_for((), (inventory,))
    related = [question.related_finding_or_profile for question in result]
    assert related.count("chromosome_label_profiler") == 2


# ---------------------------------------------------------------------------
# 3. missing_value_scanner gating (count > 0 vs. count == 0)
# ---------------------------------------------------------------------------


def test_missing_value_scanner_finding_with_positive_count_selects_related_question() -> None:
    finding = _make_finding("missing_value_scanner", count=5)
    registry = OpenQuestionRegistry()
    result = registry.applicable_for((finding,), ())
    related = [question.related_finding_or_profile for question in result]
    assert related.count("missing_value_scanner") == 1


def test_missing_value_scanner_finding_with_zero_count_selects_no_related_question() -> None:
    finding = _make_finding("missing_value_scanner", count=0)
    registry = OpenQuestionRegistry()
    result = registry.applicable_for((finding,), ())
    assert len(result) == 4
    related = [question.related_finding_or_profile for question in result]
    assert "missing_value_scanner" not in related


# ---------------------------------------------------------------------------
# 4. duplicate_chr_pos_check gating (count > 0 vs. count == 0)
# ---------------------------------------------------------------------------


def test_duplicate_chr_pos_check_finding_with_positive_count_selects_related_question() -> None:
    finding = _make_finding("duplicate_chr_pos_check", count=2)
    registry = OpenQuestionRegistry()
    result = registry.applicable_for((finding,), ())
    related = [question.related_finding_or_profile for question in result]
    assert related.count("duplicate_chr_pos_check") == 1


def test_duplicate_chr_pos_check_finding_with_zero_count_selects_no_related_question() -> None:
    finding = _make_finding("duplicate_chr_pos_check", count=0)
    registry = OpenQuestionRegistry()
    result = registry.applicable_for((finding,), ())
    related = [question.related_finding_or_profile for question in result]
    assert "duplicate_chr_pos_check" not in related


# ---------------------------------------------------------------------------
# 5. genotype_layout_classifier gating (presence only)
# ---------------------------------------------------------------------------


def test_genotype_layout_classifier_present_selects_related_question() -> None:
    profile = GenotypeLayoutProfile(
        profiler_name="genotype_layout_classifier",
        layout_kind="two_column_allele",
        column_length_distributions=(),
    )
    registry = OpenQuestionRegistry()
    result = registry.applicable_for((), (profile,))
    related = [question.related_finding_or_profile for question in result]
    assert related.count("genotype_layout_classifier") == 1


# ---------------------------------------------------------------------------
# 6. Combined conditions -- full fixed RISK-1..9 ordering contract
# ---------------------------------------------------------------------------


def test_all_conditions_combined_selects_all_nine_questions_in_fixed_order() -> None:
    chromosome_inventory = ChromosomeLabelInventory(
        profiler_name="chromosome_label_profiler",
        label_counts=(("25", 1),),
    )
    genotype_layout_profile = GenotypeLayoutProfile(
        profiler_name="genotype_layout_classifier",
        layout_kind="single_column_genotype",
        column_length_distributions=(),
    )
    missing_value_finding = _make_finding("missing_value_scanner", count=3)
    duplicate_chr_pos_finding = _make_finding("duplicate_chr_pos_check", count=1)

    registry = OpenQuestionRegistry()
    result = registry.applicable_for(
        (missing_value_finding, duplicate_chr_pos_finding),
        (chromosome_inventory, genotype_layout_profile),
    )

    assert len(result) == 9
    assert [question.related_finding_or_profile for question in result] == [
        "chromosome_label_profiler",
        "chromosome_label_profiler",
        "missing_value_scanner",
        "duplicate_chr_pos_check",
        "genotype_layout_classifier",
        None,
        None,
        None,
        "duplicate_rsid_check",
    ]


# ---------------------------------------------------------------------------
# 7. Determinism
# ---------------------------------------------------------------------------


def test_result_order_independent_of_input_collection_order() -> None:
    missing_value_finding = _make_finding("missing_value_scanner", count=3)
    duplicate_chr_pos_finding = _make_finding("duplicate_chr_pos_check", count=1)
    chromosome_inventory = ChromosomeLabelInventory(
        profiler_name="chromosome_label_profiler",
        label_counts=(("1", 1),),
    )
    genotype_layout_profile = GenotypeLayoutProfile(
        profiler_name="genotype_layout_classifier",
        layout_kind="two_column_allele",
        column_length_distributions=(),
    )

    registry = OpenQuestionRegistry()
    result_a = registry.applicable_for(
        (missing_value_finding, duplicate_chr_pos_finding),
        (chromosome_inventory, genotype_layout_profile),
    )
    result_b = registry.applicable_for(
        (duplicate_chr_pos_finding, missing_value_finding),
        (genotype_layout_profile, chromosome_inventory),
    )
    assert result_a == result_b


def test_repeated_calls_produce_identical_result() -> None:
    finding = _make_finding("missing_value_scanner", count=1)
    registry = OpenQuestionRegistry()
    first = registry.applicable_for((finding,), ())
    second = registry.applicable_for((finding,), ())
    assert first == second


# ---------------------------------------------------------------------------
# 8. Return contract validation
# ---------------------------------------------------------------------------


def test_every_selected_question_is_an_open_question_with_non_empty_statement() -> None:
    registry = OpenQuestionRegistry()
    result = registry.applicable_for((), ())
    assert len(result) > 0
    for question in result:
        assert isinstance(question, OpenQuestion)
        assert isinstance(question.statement, str)
        assert len(question.statement) > 0


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()