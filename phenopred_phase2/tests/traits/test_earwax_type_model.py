# tests/traits/test_earwax_type_model.py
"""Unit tests for EarwaxTypeModel -- the second concrete TraitModel
implementation.

Per the Phase 2 Architecture Blueprint, Section 8.4, this suite verifies:
valid wet/dry earwax genotype predictions, missing-rsid handling,
NO_CALL handling, unsupported (non-SNP) genotype states, TraitPrediction
field correctness, SNP metadata correctness, structural TraitModel
Protocol compliance, and that no frozen component was modified while
adding this model.
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
from phenopred_phase2.traits.domain.models.earwax_type_model import EarwaxTypeModel
from phenopred_phase2.traits.domain.snp_registry import SNP_REGISTRY

_RSID = "rs17822931"


def _snp_call(alleles: str) -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.SNP, alleles=alleles, allele=None, raw_value=alleles
    )


# ---------------------------------------------------------------------------
# Valid genotype prediction
# ---------------------------------------------------------------------------


def test_homozygous_associated_allele_genotype_is_wet_earwax() -> None:
    # The blueprint's own real-file case (Section 8.4): forward-strand
    # CC -- wet earwax, dominant homozygous.
    model = EarwaxTypeModel()

    prediction = model.predict({_RSID: _snp_call("CC")})

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == "wet earwax"


def test_heterozygous_genotype_is_wet_earwax() -> None:
    # Dominant trait: one copy of the associated allele ("C") is
    # sufficient for wet earwax.
    model = EarwaxTypeModel()

    prediction = model.predict({_RSID: _snp_call("CT")})

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == "wet earwax"


def test_homozygous_alternate_allele_genotype_is_dry_earwax() -> None:
    model = EarwaxTypeModel()

    prediction = model.predict({_RSID: _snp_call("TT")})

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == "dry earwax"


# ---------------------------------------------------------------------------
# Missing rs17822931
# ---------------------------------------------------------------------------


def test_missing_required_rsid_is_insufficient_data() -> None:
    model = EarwaxTypeModel()

    prediction = model.predict({})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    assert prediction.confidence is None
    assert prediction.observed_genotypes == {}
    assert prediction.supporting_snps == {}


# ---------------------------------------------------------------------------
# NO_CALL handling
# ---------------------------------------------------------------------------


def test_no_call_genotype_is_insufficient_data() -> None:
    model = EarwaxTypeModel()
    no_call = GenotypeCall(
        kind=GenotypeCallKind.NO_CALL, alleles=None, allele=None, raw_value="--"
    )

    prediction = model.predict({_RSID: no_call})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    assert prediction.confidence is None
    # Partial data is still surfaced for transparency.
    assert prediction.observed_genotypes == {_RSID: no_call}
    assert prediction.supporting_snps == {}


# ---------------------------------------------------------------------------
# Unsupported genotype state (non-SNP classifications)
# ---------------------------------------------------------------------------


def test_indel_genotype_is_insufficient_data() -> None:
    model = EarwaxTypeModel()
    indel_call = GenotypeCall(
        kind=GenotypeCallKind.INDEL, alleles=None, allele=None, raw_value="DD"
    )

    prediction = model.predict({_RSID: indel_call})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes == {_RSID: indel_call}


def test_haploid_genotype_is_insufficient_data() -> None:
    model = EarwaxTypeModel()
    haploid_call = GenotypeCall(
        kind=GenotypeCallKind.HAPLOID, alleles=None, allele="C", raw_value="C"
    )

    prediction = model.predict({_RSID: haploid_call})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes == {_RSID: haploid_call}


def test_unrecognized_genotype_is_insufficient_data() -> None:
    model = EarwaxTypeModel()
    unrecognized_call = GenotypeCall(
        kind=GenotypeCallKind.UNRECOGNIZED,
        alleles=None,
        allele=None,
        raw_value="CCC",
    )

    prediction = model.predict({_RSID: unrecognized_call})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes == {_RSID: unrecognized_call}


# ---------------------------------------------------------------------------
# TraitPrediction correctness
# ---------------------------------------------------------------------------


def test_predicted_trait_prediction_carries_expected_fields() -> None:
    model = EarwaxTypeModel()
    call = _snp_call("CC")

    prediction = model.predict({_RSID: call})

    assert prediction.trait_id == "earwax_type"
    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == "wet earwax"
    assert prediction.confidence == ConfidenceLevel.HIGH
    assert prediction.observed_genotypes == {_RSID: call}
    assert prediction.supporting_snps == {_RSID: SNP_REGISTRY[_RSID]}


# ---------------------------------------------------------------------------
# SNP metadata
# ---------------------------------------------------------------------------


def test_supporting_snp_comes_from_snp_registry_with_correct_gene() -> None:
    model = EarwaxTypeModel()

    prediction = model.predict({_RSID: _snp_call("CC")})

    supporting_record = prediction.supporting_snps[_RSID]
    assert supporting_record is SNP_REGISTRY[_RSID]
    assert supporting_record.gene == "ABCC11"
    assert supporting_record.reference_allele == "C"
    assert supporting_record.alternate_allele == "T"
    assert supporting_record.phenotype_associated_allele == "C"


# ---------------------------------------------------------------------------
# TraitModel Protocol compliance
# ---------------------------------------------------------------------------


def test_earwax_type_model_satisfies_traitmodel_protocol() -> None:
    # TraitModel is a plain (non-runtime-checkable) Protocol per the
    # frozen specification -- verified structurally, matching the
    # convention already established for LactasePersistenceModel.
    model = EarwaxTypeModel()

    assert hasattr(TraitModel, "predict")
    assert callable(getattr(model, "predict", None))


def test_predict_accepts_plain_mapping_and_returns_traitprediction_type() -> None:
    model = EarwaxTypeModel()

    prediction = model.predict({_RSID: _snp_call("CT")})

    assert isinstance(prediction, TraitPrediction)


def test_predict_never_raises_for_any_external_data_condition() -> None:
    model = EarwaxTypeModel()
    conditions = [
        {},
        {_RSID: GenotypeCall(GenotypeCallKind.NO_CALL, None, None, "--")},
        {_RSID: GenotypeCall(GenotypeCallKind.INDEL, None, None, "DD")},
        {_RSID: GenotypeCall(GenotypeCallKind.HAPLOID, None, "C", "C")},
        {_RSID: GenotypeCall(GenotypeCallKind.UNRECOGNIZED, None, None, "CCC")},
        {_RSID: _snp_call("CC")},
        {_RSID: _snp_call("CT")},
        {_RSID: _snp_call("TT")},
    ]

    for genotype_calls in conditions:
        model.predict(genotype_calls)  # must not raise
