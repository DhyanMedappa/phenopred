# tests/reporting/test_report_builder.py
"""Unit tests for build_phenopred_report()
(phenopred_phase2/reporting/report_builder.py).

These tests verify only assembly/wiring (the right already-computed
pieces end up on the right PhenoPredReport fields, unmodified) -- not
PhenoPredReport's own construction invariants, which are already
covered in isolation by test_phenopred_report.py.

Same disclosed fixture limitation as test_phenopred_report.py: real
ProfilingReport instances are constructed with placeholder values for
its V1 nested fields, since phenopred/domain/value_objects.py was not
uploaded to this environment.
"""

from __future__ import annotations

import pytest

from phenopred.domain.entities import ProfilingReport
from phenopred_phase2.comparison.domain.entities import (
    ComparisonReport,
    ConcordanceResult,
    IdentityLikelihood,
    IdentityLikelihoodCategory,
)
from phenopred_phase2.reporting.entities import PhenoPredReport
from phenopred_phase2.reporting.report_builder import build_phenopred_report
from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    PredictionStatus,
    TraitCard,
    TraitPrediction,
)


def _profiling_report(source_path: str = "fake_file.txt") -> ProfilingReport:
    return ProfilingReport(
        source_path=source_path,
        comment_block="fake-comment-block",
        encoding_profile="fake-encoding-profile",
        delimiter=",",
        header_info="fake-header-info",
        row_count=100,
        column_count_distribution=None,
        findings=(),
        profiles=(),
        open_questions=(),
    )


def _trait_card(trait_id: str = "lactase_persistence") -> TraitCard:
    prediction = TraitPrediction(
        trait_id=trait_id,
        status=PredictionStatus.PREDICTED,
        predicted_phenotype="lactase non-persistent",
        confidence=ConfidenceLevel.HIGH,
        observed_genotypes={},
        supporting_snps={},
    )
    return TraitCard(
        trait_id=trait_id,
        trait_name="Lactase Persistence",
        trait_evidence_refs=("A citation.",),
        prediction=prediction,
        limitation_keys=("ancestry_generalizability",),
    )


def _comparison_report() -> ComparisonReport:
    return ComparisonReport(
        concordance=ConcordanceResult(
            total_shared_rsids=100,
            shared_snp_count=99,
            conflicting_snp_count=1,
            missing_or_no_call_count=0,
            structural_mismatch_count=0,
            agreement_percentage=99.0,
        ),
        identity_likelihood=IdentityLikelihood(
            concordance_percentage=99.0,
            category=IdentityLikelihoodCategory.HIGH_CONCORDANCE,
            methodology_caveat_key="identity_heuristic_not_ibd_ibs",
        ),
        trait_comparisons={},
    )


# ---------------------------------------------------------------------------
# One-file flow
# ---------------------------------------------------------------------------


def test_build_phenopred_report_one_file_flow() -> None:
    profiling_report = _profiling_report("a.txt")
    trait_cards = {"lactase_persistence": _trait_card()}

    report = build_phenopred_report(profiling_report, trait_cards)

    assert isinstance(report, PhenoPredReport)
    assert report.file_a_profiling_report is profiling_report
    assert report.file_a_trait_cards is trait_cards
    assert report.file_b_profiling_report is None
    assert report.file_b_trait_cards is None
    assert report.comparison is None


# ---------------------------------------------------------------------------
# Two-file flow
# ---------------------------------------------------------------------------


def test_build_phenopred_report_two_file_flow() -> None:
    profiling_report_a = _profiling_report("a.txt")
    profiling_report_b = _profiling_report("b.txt")
    trait_cards_a = {"lactase_persistence": _trait_card()}
    trait_cards_b = {"lactase_persistence": _trait_card()}
    comparison = _comparison_report()

    report = build_phenopred_report(
        profiling_report_a,
        trait_cards_a,
        profiling_report_b,
        trait_cards_b,
        comparison,
    )

    assert report.file_a_profiling_report is profiling_report_a
    assert report.file_a_trait_cards is trait_cards_a
    assert report.file_b_profiling_report is profiling_report_b
    assert report.file_b_trait_cards is trait_cards_b
    assert report.comparison is comparison


# ---------------------------------------------------------------------------
# Correct assembly / no fabrication
# ---------------------------------------------------------------------------


def test_build_phenopred_report_does_not_fabricate_file_b_or_comparison() -> None:
    report = build_phenopred_report(
        _profiling_report("a.txt"), {"lactase_persistence": _trait_card()}
    )

    assert report.file_b_profiling_report is None
    assert report.file_b_trait_cards is None
    assert report.comparison is None


def test_build_phenopred_report_propagates_invalid_partial_state() -> None:
    # A partial file-B/comparison combination is invalid regardless of
    # whether it originates from PhenoPredReport's own constructor or
    # from the builder -- the builder must not swallow or reinterpret
    # this error.
    with pytest.raises(ValueError, match="all present or all None together"):
        build_phenopred_report(
            _profiling_report("a.txt"),
            {"lactase_persistence": _trait_card()},
            file_b_profiling_report=_profiling_report("b.txt"),
            file_b_trait_cards=None,
            comparison=_comparison_report(),
        )


# ---------------------------------------------------------------------------
# Non-mutation of inputs
# ---------------------------------------------------------------------------


def test_build_phenopred_report_does_not_mutate_its_inputs() -> None:
    profiling_report_a = _profiling_report("a.txt")
    trait_cards_a = {"lactase_persistence": _trait_card()}
    profiling_report_b = _profiling_report("b.txt")
    trait_cards_b = {"lactase_persistence": _trait_card()}
    comparison = _comparison_report()

    trait_cards_a_before = dict(trait_cards_a)
    trait_cards_b_before = dict(trait_cards_b)

    build_phenopred_report(
        profiling_report_a,
        trait_cards_a,
        profiling_report_b,
        trait_cards_b,
        comparison,
    )

    assert dict(trait_cards_a) == trait_cards_a_before
    assert dict(trait_cards_b) == trait_cards_b_before
    # Frozen dataclasses can't be mutated in place; identity is also
    # preserved (no copy-and-modify occurred anywhere in assembly).
    assert profiling_report_a.source_path == "a.txt"
    assert profiling_report_b.source_path == "b.txt"