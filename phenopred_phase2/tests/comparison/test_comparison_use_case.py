# tests/comparison/test_comparison_use_case.py
"""Unit tests for comparison_use_case.py -- the thin orchestrator.

These tests verify only wiring/coordination (the right calculators are
called and their results correctly assembled into one ComparisonReport)
-- not the classification logic itself, which is already covered in
isolation by test_concordance_calculator.py, test_identity_heuristic.py,
and test_trait_diff.py.
"""

from __future__ import annotations

from phenopred_phase2.comparison.application.comparison_use_case import (
    run_comparison,
)
from phenopred_phase2.comparison.domain.entities import (
    ComparisonReport,
    IdentityLikelihoodCategory,
    TraitAgreement,
)
from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCall,
    GenotypeCallKind,
    PredictionStatus,
    TraitPrediction,
)


class _FakeGenotypeIndex:
    def __init__(self, calls_by_rsid: dict[str, GenotypeCall]) -> None:
        self._calls_by_rsid = calls_by_rsid

    def get(self, rsid: str):
        return self._calls_by_rsid.get(rsid)

    def keys(self):
        return self._calls_by_rsid.keys()


def _snp(alleles: str) -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.SNP, alleles=alleles, allele=None, raw_value=alleles
    )


def _predicted(trait_id: str, phenotype: str) -> TraitPrediction:
    return TraitPrediction(
        trait_id=trait_id,
        status=PredictionStatus.PREDICTED,
        predicted_phenotype=phenotype,
        confidence=ConfidenceLevel.HIGH,
        observed_genotypes={},
        supporting_snps={},
    )


def test_run_comparison_returns_a_fully_assembled_comparison_report() -> None:
    genotype_index_a = _FakeGenotypeIndex({"rs1": _snp("AG"), "rs2": _snp("CT")})
    genotype_index_b = _FakeGenotypeIndex({"rs1": _snp("AG"), "rs2": _snp("CT")})
    predictions_a = {"earwax_type": _predicted("earwax_type", "wet earwax")}
    predictions_b = {"earwax_type": _predicted("earwax_type", "wet earwax")}

    report = run_comparison(
        genotype_index_a, genotype_index_b, predictions_a, predictions_b
    )

    assert isinstance(report, ComparisonReport)
    assert report.concordance.total_shared_rsids == 2
    assert report.concordance.shared_snp_count == 2
    assert report.concordance.agreement_percentage == 100.0
    assert (
        report.identity_likelihood.category
        == IdentityLikelihoodCategory.VERY_HIGH_CONCORDANCE
    )
    assert report.trait_comparisons["earwax_type"].agreement == TraitAgreement.AGREE


def test_run_comparison_derives_identity_likelihood_from_its_own_concordance() -> (
    None
):
    genotype_index_a = _FakeGenotypeIndex({"rs1": _snp("AG")})
    genotype_index_b = _FakeGenotypeIndex({"rs1": _snp("CT")})  # mismatch

    report = run_comparison(genotype_index_a, genotype_index_b, {}, {})

    assert report.concordance.conflicting_snp_count == 1
    assert report.identity_likelihood.concordance_percentage == (
        report.concordance.agreement_percentage
    )


def test_run_comparison_handles_no_shared_genotype_data_and_no_traits() -> None:
    report = run_comparison(
        _FakeGenotypeIndex({}), _FakeGenotypeIndex({}), {}, {}
    )  # must not raise

    assert report.concordance.total_shared_rsids == 0
    assert report.trait_comparisons == {}
