# tests/comparison/test_entities.py
"""Unit tests for the Comparison Engine domain entities.

Follows the same plain-function, no-test-class style already used
throughout this codebase (test_snp_registry.py, test_trait_registry.py,
test_trait_model_registry.py).
"""

from __future__ import annotations

import dataclasses

import pytest

from phenopred_phase2.comparison.domain.entities import (
    ComparisonReport,
    ConcordanceCategory,
    ConcordanceResult,
    IdentityLikelihood,
    IdentityLikelihoodCategory,
    TraitAgreement,
    TraitComparison,
)
from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    PredictionStatus,
    TraitPrediction,
)


def _make_concordance_result(**overrides) -> ConcordanceResult:
    fields = {
        "total_shared_rsids": 10,
        "shared_snp_count": 7,
        "conflicting_snp_count": 1,
        "missing_or_no_call_count": 1,
        "structural_mismatch_count": 1,
        "agreement_percentage": 70.0,
    }
    fields.update(overrides)
    return ConcordanceResult(**fields)


# ---------------------------------------------------------------------------
# ConcordanceResult
# ---------------------------------------------------------------------------


def test_concordance_result_constructs_with_all_fields_populated() -> None:
    result = _make_concordance_result()

    assert result.total_shared_rsids == 10
    assert result.shared_snp_count == 7
    assert result.agreement_percentage == 70.0


def test_concordance_result_is_frozen() -> None:
    result = _make_concordance_result()

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.shared_snp_count = 99  # type: ignore[misc]


def test_concordance_result_accepts_zero_total_shared_rsids() -> None:
    result = _make_concordance_result(
        total_shared_rsids=0,
        shared_snp_count=0,
        conflicting_snp_count=0,
        missing_or_no_call_count=0,
        structural_mismatch_count=0,
        agreement_percentage=0.0,
    )

    assert result.total_shared_rsids == 0


@pytest.mark.parametrize(
    "field_name",
    [
        "total_shared_rsids",
        "shared_snp_count",
        "conflicting_snp_count",
        "missing_or_no_call_count",
        "structural_mismatch_count",
    ],
)
def test_concordance_result_raises_on_negative_count(field_name: str) -> None:
    with pytest.raises(ValueError):
        _make_concordance_result(**{field_name: -1})


def test_concordance_result_raises_when_category_counts_do_not_sum_to_total() -> (
    None
):
    with pytest.raises(ValueError):
        _make_concordance_result(total_shared_rsids=999)


# ---------------------------------------------------------------------------
# IdentityLikelihood
# ---------------------------------------------------------------------------


def test_identity_likelihood_constructs_with_all_fields_populated() -> None:
    likelihood = IdentityLikelihood(
        concordance_percentage=99.99,
        category=IdentityLikelihoodCategory.VERY_HIGH_CONCORDANCE,
        methodology_caveat_key="identity_heuristic_not_ibd_ibs",
    )

    assert likelihood.concordance_percentage == 99.99
    assert likelihood.category == IdentityLikelihoodCategory.VERY_HIGH_CONCORDANCE


def test_identity_likelihood_is_frozen() -> None:
    likelihood = IdentityLikelihood(
        concordance_percentage=99.99,
        category=IdentityLikelihoodCategory.VERY_HIGH_CONCORDANCE,
        methodology_caveat_key="identity_heuristic_not_ibd_ibs",
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        likelihood.category = IdentityLikelihoodCategory.LOW_CONCORDANCE  # type: ignore[misc]


def test_identity_likelihood_raises_when_caveat_key_empty() -> None:
    with pytest.raises(ValueError):
        IdentityLikelihood(
            concordance_percentage=99.99,
            category=IdentityLikelihoodCategory.VERY_HIGH_CONCORDANCE,
            methodology_caveat_key="",
        )


def test_identity_likelihood_raises_when_caveat_key_whitespace_only() -> None:
    with pytest.raises(ValueError):
        IdentityLikelihood(
            concordance_percentage=99.99,
            category=IdentityLikelihoodCategory.VERY_HIGH_CONCORDANCE,
            methodology_caveat_key="   ",
        )


# ---------------------------------------------------------------------------
# TraitComparison
# ---------------------------------------------------------------------------


def _make_prediction(status: PredictionStatus, phenotype: str | None) -> TraitPrediction:
    return TraitPrediction(
        trait_id="fake_trait",
        status=status,
        predicted_phenotype=phenotype,
        confidence=ConfidenceLevel.HIGH if status == PredictionStatus.PREDICTED else None,
        observed_genotypes={},
        supporting_snps={},
    )


def test_trait_comparison_constructs_with_both_predictions_present() -> None:
    prediction_a = _make_prediction(PredictionStatus.PREDICTED, "wet earwax")
    prediction_b = _make_prediction(PredictionStatus.PREDICTED, "wet earwax")

    comparison = TraitComparison(
        trait_id="earwax_type",
        prediction_a=prediction_a,
        prediction_b=prediction_b,
        agreement=TraitAgreement.AGREE,
    )

    assert comparison.prediction_a is prediction_a
    assert comparison.prediction_b is prediction_b
    assert comparison.agreement == TraitAgreement.AGREE


def test_trait_comparison_supports_missing_prediction_on_either_side() -> None:
    comparison = TraitComparison(
        trait_id="earwax_type",
        prediction_a=None,
        prediction_b=_make_prediction(PredictionStatus.PREDICTED, "wet earwax"),
        agreement=TraitAgreement.MISSING_TRAIT,
    )

    assert comparison.prediction_a is None
    assert comparison.agreement == TraitAgreement.MISSING_TRAIT


def test_trait_comparison_is_frozen() -> None:
    comparison = TraitComparison(
        trait_id="earwax_type",
        prediction_a=None,
        prediction_b=None,
        agreement=TraitAgreement.MISSING_TRAIT,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        comparison.agreement = TraitAgreement.AGREE  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ComparisonReport
# ---------------------------------------------------------------------------


def test_comparison_report_constructs_with_all_fields_populated() -> None:
    concordance = _make_concordance_result()
    identity_likelihood = IdentityLikelihood(
        concordance_percentage=70.0,
        category=IdentityLikelihoodCategory.LOW_CONCORDANCE,
        methodology_caveat_key="identity_heuristic_not_ibd_ibs",
    )
    trait_comparisons = {
        "earwax_type": TraitComparison(
            trait_id="earwax_type",
            prediction_a=None,
            prediction_b=None,
            agreement=TraitAgreement.MISSING_TRAIT,
        )
    }

    report = ComparisonReport(
        concordance=concordance,
        identity_likelihood=identity_likelihood,
        trait_comparisons=trait_comparisons,
    )

    assert report.concordance is concordance
    assert report.identity_likelihood is identity_likelihood
    assert report.trait_comparisons is trait_comparisons


def test_comparison_report_is_frozen() -> None:
    report = ComparisonReport(
        concordance=_make_concordance_result(),
        identity_likelihood=IdentityLikelihood(
            concordance_percentage=70.0,
            category=IdentityLikelihoodCategory.LOW_CONCORDANCE,
            methodology_caveat_key="identity_heuristic_not_ibd_ibs",
        ),
        trait_comparisons={},
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        report.trait_comparisons = {}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Enum sanity
# ---------------------------------------------------------------------------


def test_concordance_category_has_exactly_four_members() -> None:
    assert {member.value for member in ConcordanceCategory} == {
        "snp_match",
        "snp_mismatch",
        "structural_mismatch",
        "no_call",
    }


def test_identity_likelihood_category_has_exactly_four_members() -> None:
    assert {member.value for member in IdentityLikelihoodCategory} == {
        "very_high_concordance",
        "high_concordance",
        "reduced_concordance",
        "low_concordance",
    }


def test_trait_agreement_has_exactly_four_members() -> None:
    assert {member.value for member in TraitAgreement} == {
        "agree",
        "disagree",
        "insufficient_data",
        "missing_trait",
    }
