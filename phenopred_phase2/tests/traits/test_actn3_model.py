# tests/traits/test_actn3_model.py
"""Unit tests for ACTN3Model -- the third concrete TraitModel
implementation, and the first to use a three-genotype-category
interpretation rather than a dominant single-allele-presence rule.

Per the Phase 2 Architecture Blueprint, Section 8.3, this suite verifies:
all three genotype categories (CC/RR, CT/RX, TT/XX), missing-rsid
handling, NO_CALL handling, unsupported (non-SNP) genotype states,
TraitPrediction field correctness, SNP metadata correctness, structural
TraitModel Protocol compliance, and that no frozen component (including
LactasePersistenceModel and EarwaxTypeModel) was modified while adding
this model.
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
from phenopred_phase2.traits.domain.models.actn3_model import ACTN3Model
from phenopred_phase2.traits.domain.snp_registry import SNP_REGISTRY

_RSID = "rs1815739"


def _snp_call(alleles: str) -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.SNP, alleles=alleles, allele=None, raw_value=alleles
    )


# ---------------------------------------------------------------------------
# Valid genotype prediction: three genotype categories
# ---------------------------------------------------------------------------


def test_homozygous_reference_genotype_is_rr_power_associated() -> None:
    # The blueprint's own real-file case (Section 8.3): forward-strand
    # CC -- RR genotype, power-associated, alpha-actinin-3 present.
    model = ACTN3Model()

    prediction = model.predict({_RSID: _snp_call("CC")})

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == (
        "ACTN3 RR (power-associated, alpha-actinin-3 present)"
    )


def test_heterozygous_genotype_is_rx_mixed() -> None:
    # ACTN3's biology assigns the heterozygote its own distinct
    # category -- not grouped with either homozygote.
    model = ACTN3Model()

    prediction = model.predict({_RSID: _snp_call("CT")})

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == (
        "ACTN3 RX (mixed power/endurance, one functional copy)"
    )


def test_homozygous_alternate_genotype_is_xx_endurance_associated() -> None:
    model = ACTN3Model()

    prediction = model.predict({_RSID: _snp_call("TT")})

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == (
        "ACTN3 XX (endurance-associated, alpha-actinin-3 deficient)"
    )


def test_three_genotype_categories_are_pairwise_distinct() -> None:
    # Explicit regression guard against a dominant/binary shortcut:
    # each of the three genotypes must produce a distinct label, not
    # two of them collapsing into the same "phenotype present" bucket.
    model = ACTN3Model()

    rr = model.predict({_RSID: _snp_call("CC")}).predicted_phenotype
    rx = model.predict({_RSID: _snp_call("CT")}).predicted_phenotype
    xx = model.predict({_RSID: _snp_call("TT")}).predicted_phenotype

    assert len({rr, rx, xx}) == 3


# ---------------------------------------------------------------------------
# Missing rs1815739
# ---------------------------------------------------------------------------


def test_missing_required_rsid_is_insufficient_data() -> None:
    model = ACTN3Model()

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
    model = ACTN3Model()
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
    model = ACTN3Model()
    indel_call = GenotypeCall(
        kind=GenotypeCallKind.INDEL, alleles=None, allele=None, raw_value="DD"
    )

    prediction = model.predict({_RSID: indel_call})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes == {_RSID: indel_call}


def test_haploid_genotype_is_insufficient_data() -> None:
    model = ACTN3Model()
    haploid_call = GenotypeCall(
        kind=GenotypeCallKind.HAPLOID, alleles=None, allele="C", raw_value="C"
    )

    prediction = model.predict({_RSID: haploid_call})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes == {_RSID: haploid_call}


def test_unrecognized_genotype_is_insufficient_data() -> None:
    model = ACTN3Model()
    unrecognized_call = GenotypeCall(
        kind=GenotypeCallKind.UNRECOGNIZED,
        alleles=None,
        allele=None,
        raw_value="CCC",
    )

    prediction = model.predict({_RSID: unrecognized_call})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes == {_RSID: unrecognized_call}


def test_unrecognized_allele_combination_for_this_snp_is_insufficient_data() -> (
    None
):
    # A SNP-classified call whose alleles don't match any of the three
    # genotypes this SNP's own reference/alternate alleles define (a
    # data anomaly, e.g. wrong-locus alleles) -- never guessed at,
    # never raised.
    model = ACTN3Model()

    prediction = model.predict({_RSID: _snp_call("AG")})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    assert prediction.confidence is None
    assert prediction.supporting_snps == {}


# ---------------------------------------------------------------------------
# TraitPrediction correctness
# ---------------------------------------------------------------------------


def test_predicted_trait_prediction_carries_expected_fields() -> None:
    model = ACTN3Model()
    call = _snp_call("CC")

    prediction = model.predict({_RSID: call})

    assert prediction.trait_id == "actn3"
    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == (
        "ACTN3 RR (power-associated, alpha-actinin-3 present)"
    )
    assert prediction.confidence == ConfidenceLevel.MODERATE
    assert prediction.observed_genotypes == {_RSID: call}
    assert prediction.supporting_snps == {_RSID: SNP_REGISTRY[_RSID]}


# ---------------------------------------------------------------------------
# SNP metadata
# ---------------------------------------------------------------------------


def test_supporting_snp_comes_from_snp_registry_with_correct_gene() -> None:
    model = ACTN3Model()

    prediction = model.predict({_RSID: _snp_call("CT")})

    supporting_record = prediction.supporting_snps[_RSID]
    assert supporting_record is SNP_REGISTRY[_RSID]
    assert supporting_record.gene == "ACTN3"
    assert supporting_record.reference_allele == "C"
    assert supporting_record.alternate_allele == "T"
    assert supporting_record.phenotype_associated_allele == "C"


# ---------------------------------------------------------------------------
# TraitModel Protocol compliance
# ---------------------------------------------------------------------------


def test_actn3_model_satisfies_traitmodel_protocol() -> None:
    # TraitModel is a plain (non-runtime-checkable) Protocol per the
    # frozen specification -- verified structurally, matching the
    # convention already established for LactasePersistenceModel and
    # EarwaxTypeModel.
    model = ACTN3Model()

    assert hasattr(TraitModel, "predict")
    assert callable(getattr(model, "predict", None))


def test_predict_accepts_plain_mapping_and_returns_traitprediction_type() -> None:
    model = ACTN3Model()

    prediction = model.predict({_RSID: _snp_call("CT")})

    assert isinstance(prediction, TraitPrediction)


def test_predict_never_raises_for_any_external_data_condition() -> None:
    model = ACTN3Model()
    conditions = [
        {},
        {_RSID: GenotypeCall(GenotypeCallKind.NO_CALL, None, None, "--")},
        {_RSID: GenotypeCall(GenotypeCallKind.INDEL, None, None, "DD")},
        {_RSID: GenotypeCall(GenotypeCallKind.HAPLOID, None, "C", "C")},
        {_RSID: GenotypeCall(GenotypeCallKind.UNRECOGNIZED, None, None, "CCC")},
        {_RSID: _snp_call("CC")},
        {_RSID: _snp_call("CT")},
        {_RSID: _snp_call("TT")},
        {_RSID: _snp_call("AG")},
    ]

    for genotype_calls in conditions:
        model.predict(genotype_calls)  # must not raise
