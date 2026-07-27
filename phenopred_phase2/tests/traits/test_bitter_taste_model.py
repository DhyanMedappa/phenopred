# tests/traits/test_bitter_taste_model.py
"""Unit tests for BitterTasteModel -- the fourth concrete TraitModel
implementation, and the first to combine multiple SNPs into one joint
haplotype/diplotype interpretation rather than reading a single locus.

Per the Phase 2 Architecture Blueprint, Section 8.5, this suite verifies:
the three recognized diplotype patterns (PAV/PAV, AVI/AVI, inferred
PAV/AVI), missing-rsid handling per locus, NO_CALL/INDEL/HAPLOID/
UNRECOGNIZED handling per locus, unsupported allele combinations,
mixed-zygosity (inconsistent) and partial-heterozygosity patterns,
TraitPrediction field correctness, evidence preservation (both
observed_genotypes and supporting_snps), structural TraitModel Protocol
compliance, and that no frozen component was modified while adding this
model.
"""

from __future__ import annotations

from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCall,
    GenotypeCallKind,
    PredictionStatus,
    TraitPrediction,
)
from phenopred_phase2.traits.domain.interfaces import TraitModel
from phenopred_phase2.traits.domain.models.bitter_taste_model import BitterTasteModel
from phenopred_phase2.traits.domain.snp_registry import SNP_REGISTRY

_RSID_A = "rs713598"
_RSID_B = "rs1726866"
_RSID_C = "rs10246939"
_ALL_RSIDS = (_RSID_A, _RSID_B, _RSID_C)


def _snp_call(alleles: str) -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.SNP, alleles=alleles, allele=None, raw_value=alleles
    )


def _pav_pav_calls() -> dict[str, GenotypeCall]:
    # PAV alleles: rs713598=G, rs1726866=G, rs10246939=C
    return {
        _RSID_A: _snp_call("GG"),
        _RSID_B: _snp_call("GG"),
        _RSID_C: _snp_call("CC"),
    }


def _avi_avi_calls() -> dict[str, GenotypeCall]:
    # AVI alleles: rs713598=C, rs1726866=A, rs10246939=T
    return {
        _RSID_A: _snp_call("CC"),
        _RSID_B: _snp_call("AA"),
        _RSID_C: _snp_call("TT"),
    }


def _het_all_calls() -> dict[str, GenotypeCall]:
    return {
        _RSID_A: _snp_call("CG"),
        _RSID_B: _snp_call("AG"),
        _RSID_C: _snp_call("CT"),
    }


# ---------------------------------------------------------------------------
# Valid diplotype predictions
# ---------------------------------------------------------------------------


def test_pav_pav_all_loci_is_taster_high_confidence() -> None:
    model = BitterTasteModel()

    prediction = model.predict(_pav_pav_calls())

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == "taster (PAV/PAV)"
    assert prediction.confidence == ConfidenceLevel.HIGH


def test_avi_avi_all_loci_is_non_taster_high_confidence() -> None:
    model = BitterTasteModel()

    prediction = model.predict(_avi_avi_calls())

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == "non-taster (AVI/AVI)"
    assert prediction.confidence == ConfidenceLevel.HIGH


def test_inferred_pav_avi_heterozygous_all_loci_is_taster_moderate_with_caveat() -> (
    None
):
    model = BitterTasteModel()

    prediction = model.predict(_het_all_calls())

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.confidence == ConfidenceLevel.MODERATE
    # The approximation must be explicit in the phenotype label itself,
    # per Blueprint Section 8.5's instruction not to gloss over this --
    # and must not imply directly observed haplotype phase.
    assert prediction.predicted_phenotype == (
        "likely taster (inferred PAV/AVI from unphased genotype data; "
        "phase not directly observed)"
    )
    assert "inferred" in prediction.predicted_phenotype
    assert "unphased" in prediction.predicted_phenotype
    assert "phase not directly observed" in prediction.predicted_phenotype
    assert prediction.predicted_phenotype.startswith("likely taster")


# ---------------------------------------------------------------------------
# Missing required SNPs
# ---------------------------------------------------------------------------


def test_missing_rs713598_is_insufficient_data() -> None:
    model = BitterTasteModel()
    calls = _pav_pav_calls()
    del calls[_RSID_A]

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    assert prediction.confidence is None
    assert _RSID_A not in prediction.observed_genotypes
    assert _RSID_B in prediction.observed_genotypes
    assert _RSID_C in prediction.observed_genotypes


def test_missing_rs1726866_is_insufficient_data() -> None:
    model = BitterTasteModel()
    calls = _pav_pav_calls()
    del calls[_RSID_B]

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert _RSID_B not in prediction.observed_genotypes


def test_missing_rs10246939_is_insufficient_data() -> None:
    model = BitterTasteModel()
    calls = _pav_pav_calls()
    del calls[_RSID_C]

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert _RSID_C not in prediction.observed_genotypes


def test_missing_all_three_rsids_is_insufficient_data() -> None:
    model = BitterTasteModel()

    prediction = model.predict({})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    assert prediction.confidence is None
    assert prediction.observed_genotypes == {}


# ---------------------------------------------------------------------------
# Invalid genotype states at a single locus
# ---------------------------------------------------------------------------


def test_no_call_at_one_locus_is_insufficient_data() -> None:
    model = BitterTasteModel()
    calls = _pav_pav_calls()
    no_call = GenotypeCall(GenotypeCallKind.NO_CALL, None, None, "--")
    calls[_RSID_A] = no_call

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    # Partial data is still surfaced for transparency.
    assert prediction.observed_genotypes[_RSID_A] is no_call


def test_haploid_at_one_locus_is_insufficient_data() -> None:
    model = BitterTasteModel()
    calls = _pav_pav_calls()
    calls[_RSID_B] = GenotypeCall(GenotypeCallKind.HAPLOID, None, "G", "G")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


def test_indel_at_one_locus_is_insufficient_data() -> None:
    model = BitterTasteModel()
    calls = _pav_pav_calls()
    calls[_RSID_C] = GenotypeCall(GenotypeCallKind.INDEL, None, None, "DD")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


def test_unrecognized_kind_at_one_locus_is_insufficient_data() -> None:
    model = BitterTasteModel()
    calls = _pav_pav_calls()
    calls[_RSID_A] = GenotypeCall(GenotypeCallKind.UNRECOGNIZED, None, None, "GGG")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


def test_unsupported_allele_combination_at_one_locus_is_insufficient_data() -> None:
    # A SNP-classified call whose alleles match neither this locus's PAV
    # nor AVI shape (rs713598's PAV/AVI are G/C) -- a data anomaly,
    # never guessed at.
    model = BitterTasteModel()
    calls = _pav_pav_calls()
    calls[_RSID_A] = _snp_call("AT")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None


# ---------------------------------------------------------------------------
# Ambiguous / inconsistent multi-locus patterns
# ---------------------------------------------------------------------------


def test_inconsistent_multi_locus_pattern_is_insufficient_data() -> None:
    # Mixed zygosities: PAV, HET, AVI -- not explainable by a pure
    # PAV/PAV, AVI/AVI, or all-heterozygous pattern.
    model = BitterTasteModel()
    calls = {
        _RSID_A: _snp_call("GG"),  # PAV
        _RSID_B: _snp_call("AG"),  # HET
        _RSID_C: _snp_call("TT"),  # AVI
    }

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    assert prediction.confidence is None


def test_partial_heterozygosity_pattern_is_insufficient_data() -> None:
    # HET, HET, PAV -- heterozygous at two loci but homozygous-PAV at
    # the third; not safely resolvable to any of the three recognized
    # patterns.
    model = BitterTasteModel()
    calls = {
        _RSID_A: _snp_call("CG"),  # HET
        _RSID_B: _snp_call("AG"),  # HET
        _RSID_C: _snp_call("CC"),  # PAV
    }

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# TraitPrediction correctness and evidence preservation
# ---------------------------------------------------------------------------


def test_predicted_trait_prediction_carries_expected_fields() -> None:
    model = BitterTasteModel()
    calls = _pav_pav_calls()

    prediction = model.predict(calls)

    assert prediction.trait_id == "bitter_taste"
    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.confidence == ConfidenceLevel.HIGH
    for rsid in _ALL_RSIDS:
        assert prediction.observed_genotypes[rsid] is calls[rsid]
        assert prediction.supporting_snps[rsid] is SNP_REGISTRY[rsid]


def test_supporting_snps_is_empty_on_insufficient_data() -> None:
    # supporting_snps is prediction-support evidence, not standalone
    # static metadata -- empty when status is INSUFFICIENT_DATA,
    # matching TraitPrediction's documented convention and every other
    # TraitModel in this codebase (LactasePersistenceModel,
    # EarwaxTypeModel, ACTN3Model).
    model = BitterTasteModel()

    prediction = model.predict({})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.supporting_snps == {}


def test_supporting_snps_is_empty_on_insufficient_data_with_partial_calls() -> None:
    # Even when some loci did have usable data, an overall
    # INSUFFICIENT_DATA result still carries no supporting_snps --
    # only observed_genotypes preserves the partial evidence.
    model = BitterTasteModel()
    calls = _pav_pav_calls()
    del calls[_RSID_A]

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.supporting_snps == {}
    assert prediction.observed_genotypes != {}


def test_supporting_snps_contains_all_three_records_on_predicted() -> None:
    model = BitterTasteModel()

    prediction = model.predict(_pav_pav_calls())

    assert prediction.status == PredictionStatus.PREDICTED
    assert set(prediction.supporting_snps.keys()) == set(_ALL_RSIDS)
    for rsid in _ALL_RSIDS:
        assert prediction.supporting_snps[rsid] is SNP_REGISTRY[rsid]
        assert prediction.supporting_snps[rsid].gene == "TAS2R38"


def test_observed_genotypes_preserves_only_provided_calls() -> None:
    model = BitterTasteModel()
    calls = {_RSID_A: _snp_call("GG"), _RSID_B: _snp_call("GG")}

    prediction = model.predict(calls)

    assert set(prediction.observed_genotypes.keys()) == {_RSID_A, _RSID_B}


# ---------------------------------------------------------------------------
# TraitModel Protocol compliance
# ---------------------------------------------------------------------------


def test_bitter_taste_model_satisfies_traitmodel_protocol() -> None:
    model = BitterTasteModel()

    assert hasattr(TraitModel, "predict")
    assert callable(getattr(model, "predict", None))


def test_predict_accepts_plain_mapping_and_returns_traitprediction_type() -> None:
    model = BitterTasteModel()

    prediction = model.predict(_pav_pav_calls())

    assert isinstance(prediction, TraitPrediction)


def test_predict_never_raises_for_any_condition() -> None:
    model = BitterTasteModel()
    conditions = [
        {},
        _pav_pav_calls(),
        _avi_avi_calls(),
        _het_all_calls(),
        {_RSID_A: _snp_call("GG")},
        {_RSID_A: GenotypeCall(GenotypeCallKind.NO_CALL, None, None, "--")},
        {_RSID_B: GenotypeCall(GenotypeCallKind.INDEL, None, None, "DD")},
        {_RSID_C: GenotypeCall(GenotypeCallKind.HAPLOID, None, "C", "C")},
        {_RSID_A: GenotypeCall(GenotypeCallKind.UNRECOGNIZED, None, None, "GGG")},
        {_RSID_A: _snp_call("AT")},
    ]

    for genotype_calls in conditions:
        model.predict(genotype_calls)  # must not raise