# tests/comparison/test_concordance_calculator.py
"""Unit tests for concordance_calculator.py.

Isolated unit tests only: every GenotypeIndex is a hand-built fake
exposing exactly the .get()/.keys() interface concordance_calculator
requires -- no real V1 or real GenotypeIndex construction here (that
boundary is covered separately by the end-to-end integration test).
Covers every one of the 17 rows in the final, corrected decision table
established by the scientific correctness review.
"""

from __future__ import annotations

import pytest

from phenopred_phase2.comparison.domain.concordance_calculator import (
    calculate_concordance,
)
from phenopred_phase2.comparison.domain.entities import ConcordanceResult
from phenopred_phase2.traits.domain.entities import GenotypeCall, GenotypeCallKind


class _FakeGenotypeIndex:
    """A minimal fake exposing exactly GenotypeIndex's .get()/.keys()
    interface -- no real GenotypeIndex construction needed for these
    isolated unit tests.
    """

    def __init__(self, calls_by_rsid: dict[str, GenotypeCall]) -> None:
        self._calls_by_rsid = calls_by_rsid

    def get(self, rsid: str) -> GenotypeCall | None:
        return self._calls_by_rsid.get(rsid)

    def keys(self):
        return self._calls_by_rsid.keys()


def _snp(alleles: str) -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.SNP, alleles=alleles, allele=None, raw_value=alleles
    )


def _haploid(allele: str) -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.HAPLOID, alleles=None, allele=allele, raw_value=allele
    )


def _indel() -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.INDEL, alleles=None, allele=None, raw_value="DD"
    )


def _no_call() -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.NO_CALL, alleles=None, allele=None, raw_value="--"
    )


def _unrecognized() -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.UNRECOGNIZED, alleles=None, allele=None, raw_value="???"
    )


def _single_rsid_result(call_a: GenotypeCall, call_b: GenotypeCall) -> ConcordanceResult:
    index_a = _FakeGenotypeIndex({"rs1": call_a})
    index_b = _FakeGenotypeIndex({"rs1": call_b})
    return calculate_concordance(index_a, index_b)


# ---------------------------------------------------------------------------
# Full 17-row decision table
# ---------------------------------------------------------------------------


def test_snp_vs_snp_same_alleles_is_snp_match() -> None:
    result = _single_rsid_result(_snp("AG"), _snp("AG"))
    assert result.shared_snp_count == 1
    assert result.agreement_percentage == 100.0


def test_snp_vs_snp_different_alleles_is_snp_mismatch() -> None:
    result = _single_rsid_result(_snp("AG"), _snp("CT"))
    assert result.conflicting_snp_count == 1


def test_snp_vs_indel_is_structural_mismatch() -> None:
    result = _single_rsid_result(_snp("AG"), _indel())
    assert result.structural_mismatch_count == 1


def test_snp_vs_no_call_is_no_call() -> None:
    result = _single_rsid_result(_snp("AG"), _no_call())
    assert result.missing_or_no_call_count == 1


def test_snp_vs_haploid_is_structural_mismatch() -> None:
    result = _single_rsid_result(_snp("AG"), _haploid("A"))
    assert result.structural_mismatch_count == 1


def test_snp_vs_unrecognized_is_no_call() -> None:
    result = _single_rsid_result(_snp("AG"), _unrecognized())
    assert result.missing_or_no_call_count == 1


def test_indel_vs_indel_is_structural_mismatch() -> None:
    result = _single_rsid_result(_indel(), _indel())
    assert result.structural_mismatch_count == 1


def test_indel_vs_no_call_is_no_call() -> None:
    result = _single_rsid_result(_indel(), _no_call())
    assert result.missing_or_no_call_count == 1


def test_indel_vs_haploid_is_structural_mismatch() -> None:
    result = _single_rsid_result(_indel(), _haploid("A"))
    assert result.structural_mismatch_count == 1


def test_indel_vs_unrecognized_is_no_call() -> None:
    result = _single_rsid_result(_indel(), _unrecognized())
    assert result.missing_or_no_call_count == 1


def test_no_call_vs_no_call_is_no_call() -> None:
    result = _single_rsid_result(_no_call(), _no_call())
    assert result.missing_or_no_call_count == 1


def test_no_call_vs_haploid_is_no_call() -> None:
    result = _single_rsid_result(_no_call(), _haploid("A"))
    assert result.missing_or_no_call_count == 1


def test_no_call_vs_unrecognized_is_no_call() -> None:
    result = _single_rsid_result(_no_call(), _unrecognized())
    assert result.missing_or_no_call_count == 1


def test_haploid_vs_haploid_same_allele_is_snp_match() -> None:
    result = _single_rsid_result(_haploid("A"), _haploid("A"))
    assert result.shared_snp_count == 1


def test_haploid_vs_haploid_different_allele_is_snp_mismatch() -> None:
    result = _single_rsid_result(_haploid("A"), _haploid("T"))
    assert result.conflicting_snp_count == 1


def test_haploid_vs_unrecognized_is_no_call() -> None:
    result = _single_rsid_result(_haploid("A"), _unrecognized())
    assert result.missing_or_no_call_count == 1


def test_unrecognized_vs_unrecognized_is_no_call() -> None:
    result = _single_rsid_result(_unrecognized(), _unrecognized())
    assert result.missing_or_no_call_count == 1


# ---------------------------------------------------------------------------
# RSID-set handling
# ---------------------------------------------------------------------------


def test_rsid_present_in_only_one_file_is_excluded_from_shared_count() -> None:
    index_a = _FakeGenotypeIndex({"rs1": _snp("AG"), "rs_only_a": _snp("CT")})
    index_b = _FakeGenotypeIndex({"rs1": _snp("AG")})

    result = calculate_concordance(index_a, index_b)

    assert result.total_shared_rsids == 1
    assert result.shared_snp_count == 1


def test_multiple_shared_rsids_aggregate_correctly() -> None:
    index_a = _FakeGenotypeIndex(
        {"rs1": _snp("AG"), "rs2": _snp("CT"), "rs3": _no_call()}
    )
    index_b = _FakeGenotypeIndex(
        {"rs1": _snp("AG"), "rs2": _snp("GG"), "rs3": _snp("AA")}
    )

    result = calculate_concordance(index_a, index_b)

    assert result.total_shared_rsids == 3
    assert result.shared_snp_count == 1
    assert result.conflicting_snp_count == 1
    assert result.missing_or_no_call_count == 1
    assert result.agreement_percentage == pytest.approx(100.0 / 3.0)


def test_no_shared_rsids_yields_zero_percent_agreement_not_a_crash() -> None:
    index_a = _FakeGenotypeIndex({"rs_only_a": _snp("AG")})
    index_b = _FakeGenotypeIndex({"rs_only_b": _snp("AG")})

    result = calculate_concordance(index_a, index_b)

    assert result.total_shared_rsids == 0
    assert result.agreement_percentage == 0.0
