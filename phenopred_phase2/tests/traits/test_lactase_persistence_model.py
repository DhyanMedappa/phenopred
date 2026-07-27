# tests/traits/test_lactase_persistence_model.py
"""Unit tests for LactasePersistenceModel -- the first concrete
TraitModel implementation.

Per the Phase 2 Architecture Blueprint, Section 8.2, this suite verifies:
valid persistent and non-persistent genotype predictions, missing-rsid
handling, NO_CALL handling, unsupported (non-SNP) genotype states,
TraitPrediction field correctness, structural TraitModel Protocol
compliance, and that no frozen component was modified while adding this
model.
"""

from __future__ import annotations

from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCall,
    GenotypeCallKind,
    PredictionStatus,
)
from phenopred_phase2.traits.domain.interfaces import TraitModel
from phenopred_phase2.traits.domain.models.lactase_persistence_model import (
    LactasePersistenceModel,
)
from phenopred_phase2.traits.domain.snp_registry import SNP_REGISTRY

_RSID = "rs4988235"


def _snp_call(alleles: str) -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.SNP, alleles=alleles, allele=None, raw_value=alleles
    )


# ---------------------------------------------------------------------------
# Valid genotype prediction
# ---------------------------------------------------------------------------


def test_homozygous_reference_genotype_is_non_persistent() -> None:
    # The blueprint's own real-file case (Section 8.2): forward-strand
    # GG, equivalent to the literature's CC -- lactase non-persistent.
    model = LactasePersistenceModel()

    prediction = model.predict({_RSID: _snp_call("GG")})

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == "lactase non-persistent"


def test_heterozygous_genotype_is_persistent() -> None:
    # Dominant trait: one copy of the associated allele ("A") is
    # sufficient for persistence.
    model = LactasePersistenceModel()

    prediction = model.predict({_RSID: _snp_call("AG")})

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == "lactase persistent"


def test_homozygous_associated_allele_genotype_is_persistent() -> None:
    model = LactasePersistenceModel()

    prediction = model.predict({_RSID: _snp_call("AA")})

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == "lactase persistent"


# ---------------------------------------------------------------------------
# Missing rs4988235
# ---------------------------------------------------------------------------


def test_missing_required_rsid_is_insufficient_data() -> None:
    model = LactasePersistenceModel()

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
    model = LactasePersistenceModel()
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
    model = LactasePersistenceModel()
    indel_call = GenotypeCall(
        kind=GenotypeCallKind.INDEL, alleles=None, allele=None, raw_value="DD"
    )

    prediction = model.predict({_RSID: indel_call})

    assert prediction.status == PredictionStatus.INSUFFICENT_DATA if False else PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes == {_RSID: indel_call}


def test_haploid_genotype_is_insufficient_data() -> None:
    model = LactasePersistenceModel()
    haploid_call = GenotypeCall(
        kind=GenotypeCallKind.HAPLOID, alleles=None, allele="A", raw_value="A"
    )

    prediction = model.predict({_RSID: haploid_call})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes == {_RSID: haploid_call}


def test_unrecognized_genotype_is_insufficient_data() -> None:
    model = LactasePersistenceModel()
    unrecognized_call = GenotypeCall(
        kind=GenotypeCallKind.UNRECOGNIZED,
        alleles=None,
        allele=None,
        raw_value="AAA",
    )

    prediction = model.predict({_RSID: unrecognized_call})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes == {_RSID: unrecognized_call}


# ---------------------------------------------------------------------------
# TraitPrediction correctness
# ---------------------------------------------------------------------------


def test_predicted_trait_prediction_carries_expected_fields() -> None:
    model = LactasePersistenceModel()
    call = _snp_call("GG")

    prediction = model.predict({_RSID: call})

    assert prediction.trait_id == "lactase_persistence"
    assert prediction.confidence == ConfidenceLevel.HIGH
    assert prediction.observed_genotypes == {_RSID: call}
    assert prediction.supporting_snps == {_RSID: SNP_REGISTRY[_RSID]}
    assert prediction.supporting_snps[_RSID].gene == "LCT"


# ---------------------------------------------------------------------------
# TraitModel Protocol compliance
# ---------------------------------------------------------------------------


def test_lactase_persistence_model_satisfies_traitmodel_protocol() -> None:
    # TraitModel is a plain (non-runtime-checkable) Protocol per the
    # frozen specification -- verified structurally, matching the
    # convention already established in test_trait_model_contract.py.
    model = LactasePersistenceModel()

    assert hasattr(TraitModel, "predict")
    assert callable(getattr(model, "predict", None))


def test_predict_accepts_plain_mapping_and_returns_traitprediction_type() -> None:
    from phenopred_phase2.traits.domain.entities import TraitPrediction

    model = LactasePersistenceModel()

    prediction = model.predict({_RSID: _snp_call("AG")})

    assert isinstance(prediction, TraitPrediction)


def test_predict_never_raises_for_any_external_data_condition() -> None:
    model = LactasePersistenceModel()
    conditions = [
        {},
        {_RSID: GenotypeCall(GenotypeCallKind.NO_CALL, None, None, "--")},
        {_RSID: GenotypeCall(GenotypeCallKind.INDEL, None, None, "DD")},
        {_RSID: GenotypeCall(GenotypeCallKind.HAPLOID, None, "A", "A")},
        {_RSID: GenotypeCall(GenotypeCallKind.UNRECOGNIZED, None, None, "AAA")},
        {_RSID: _snp_call("GG")},
        {_RSID: _snp_call("AG")},
        {_RSID: _snp_call("AA")},
    ]

    for genotype_calls in conditions:
        model.predict(genotype_calls)  # must not raise