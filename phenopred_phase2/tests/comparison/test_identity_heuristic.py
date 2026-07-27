# tests/comparison/test_identity_heuristic.py
"""Unit tests for identity_heuristic.py."""

from __future__ import annotations

from phenopred_phase2.comparison.domain.entities import (
    ConcordanceResult,
    IdentityLikelihoodCategory,
)
from phenopred_phase2.comparison.domain.identity_heuristic import (
    METHODOLOGY_CAVEAT_KEY,
    interpret_identity_likelihood,
)


def _result_with_rate(rate: float) -> ConcordanceResult:
    # Only agreement_percentage matters to identity_heuristic; the
    # count fields are given arbitrary, structurally-valid values.
    return ConcordanceResult(
        total_shared_rsids=100,
        shared_snp_count=int(rate),
        conflicting_snp_count=100 - int(rate),
        missing_or_no_call_count=0,
        structural_mismatch_count=0,
        agreement_percentage=rate,
    )


def test_rate_at_or_above_99_9_is_very_high_concordance() -> None:
    likelihood = interpret_identity_likelihood(_result_with_rate(99.99))
    assert likelihood.category == IdentityLikelihoodCategory.VERY_HIGH_CONCORDANCE


def test_rate_exactly_at_99_9_boundary_is_very_high_concordance() -> None:
    likelihood = interpret_identity_likelihood(_result_with_rate(99.9))
    assert likelihood.category == IdentityLikelihoodCategory.VERY_HIGH_CONCORDANCE


def test_rate_just_below_99_9_is_high_concordance() -> None:
    likelihood = interpret_identity_likelihood(_result_with_rate(99.89))
    assert likelihood.category == IdentityLikelihoodCategory.HIGH_CONCORDANCE


def test_rate_exactly_at_99_0_boundary_is_high_concordance() -> None:
    likelihood = interpret_identity_likelihood(_result_with_rate(99.0))
    assert likelihood.category == IdentityLikelihoodCategory.HIGH_CONCORDANCE


def test_rate_just_below_99_0_is_reduced_concordance() -> None:
    likelihood = interpret_identity_likelihood(_result_with_rate(98.99))
    assert likelihood.category == IdentityLikelihoodCategory.REDUCED_CONCORDANCE


def test_rate_exactly_at_95_0_boundary_is_reduced_concordance() -> None:
    likelihood = interpret_identity_likelihood(_result_with_rate(95.0))
    assert likelihood.category == IdentityLikelihoodCategory.REDUCED_CONCORDANCE


def test_rate_just_below_95_0_is_low_concordance() -> None:
    likelihood = interpret_identity_likelihood(_result_with_rate(94.99))
    assert likelihood.category == IdentityLikelihoodCategory.LOW_CONCORDANCE


def test_rate_of_zero_is_low_concordance() -> None:
    likelihood = interpret_identity_likelihood(_result_with_rate(0.0))
    assert likelihood.category == IdentityLikelihoodCategory.LOW_CONCORDANCE


def test_methodology_caveat_key_is_always_present_regardless_of_category() -> None:
    for rate in (100.0, 99.5, 96.0, 10.0):
        likelihood = interpret_identity_likelihood(_result_with_rate(rate))
        assert likelihood.methodology_caveat_key == METHODOLOGY_CAVEAT_KEY
        assert likelihood.methodology_caveat_key != ""


def test_concordance_percentage_is_carried_through_unaltered() -> None:
    likelihood = interpret_identity_likelihood(_result_with_rate(97.25))
    assert likelihood.concordance_percentage == 97.25
