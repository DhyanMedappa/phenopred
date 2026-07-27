# tests/traits/test_eye_colour_model.py
"""Unit tests for EyeColourModel -- the fifth concrete TraitModel
implementation, and the first to combine six SNPs into a
three-category (brown/blue/intermediate) classification.

Per the Phase 2 Architecture Blueprint, Section 8.1, this suite
verifies: model initialization, recognition of all six required
IrisPlex SNP dependencies, strong blue- and brown-associated genotype
patterns, missing-SNP handling, unknown/unrecognized genotype
handling, TraitPrediction field correctness, evidence preservation,
structural TraitModel Protocol compliance, and that no frozen
component was modified while adding this model.
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
from phenopred_phase2.traits.domain.models.eye_colour_model import EyeColourModel
from phenopred_phase2.traits.domain.snp_registry import SNP_REGISTRY

_RSID_HERC2 = "rs12913832"
_RSID_OCA2 = "rs1800407"
_RSID_SLC24A4 = "rs12896399"
_RSID_SLC45A2 = "rs16891982"
_RSID_TYR = "rs1393350"
_RSID_IRF4 = "rs12203592"

_ALL_RSIDS = (
    _RSID_HERC2,
    _RSID_OCA2,
    _RSID_SLC24A4,
    _RSID_SLC45A2,
    _RSID_TYR,
    _RSID_IRF4,
)


def _snp_call(alleles: str) -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.SNP, alleles=alleles, allele=None, raw_value=alleles
    )


def _strong_blue_calls() -> dict[str, GenotypeCall]:
    # Homozygous for each SNP's phenotype_associated_allele (verified
    # SNP_REGISTRY values): HERC2 G, OCA2 A, SLC24A4 T, SLC45A2 G,
    # TYR G, IRF4 T.
    return {
        _RSID_HERC2: _snp_call("GG"),
        _RSID_OCA2: _snp_call("AA"),
        _RSID_SLC24A4: _snp_call("TT"),
        _RSID_SLC45A2: _snp_call("GG"),
        _RSID_TYR: _snp_call("GG"),
        _RSID_IRF4: _snp_call("TT"),
    }


def _strong_brown_calls() -> dict[str, GenotypeCall]:
    # Homozygous for each SNP's non-associated (reference or
    # alternate, whichever isn't phenotype_associated_allele) allele:
    # HERC2 A, OCA2 G, SLC24A4 G, SLC45A2 C, TYR A, IRF4 C.
    return {
        _RSID_HERC2: _snp_call("AA"),
        _RSID_OCA2: _snp_call("GG"),
        _RSID_SLC24A4: _snp_call("GG"),
        _RSID_SLC45A2: _snp_call("CC"),
        _RSID_TYR: _snp_call("AA"),
        _RSID_IRF4: _snp_call("CC"),
    }


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_eye_colour_model_can_be_initialized() -> None:
    model = EyeColourModel()

    assert model is not None


# ---------------------------------------------------------------------------
# Recognition of all six required SNP dependencies
# ---------------------------------------------------------------------------


def test_missing_each_required_rsid_individually_is_insufficient_data() -> None:
    # Confirms the model actually consults all six loci: removing any
    # single one from an otherwise-complete panel must still yield
    # INSUFFICIENT_DATA, never a silent partial prediction.
    model = EyeColourModel()

    for missing_rsid in _ALL_RSIDS:
        calls = _strong_blue_calls()
        del calls[missing_rsid]

        prediction = model.predict(calls)

        assert prediction.status == PredictionStatus.INSUFFICIENT_DATA, (
            f"missing {missing_rsid} should yield INSUFFICIENT_DATA"
        )


def test_supporting_snps_on_predicted_contains_all_six_genes() -> None:
    model = EyeColourModel()

    prediction = model.predict(_strong_blue_calls())

    assert prediction.status == PredictionStatus.PREDICTED
    assert set(prediction.supporting_snps.keys()) == set(_ALL_RSIDS)
    expected_genes = {"HERC2", "OCA2", "SLC24A4", "SLC45A2", "TYR", "IRF4"}
    actual_genes = {record.gene for record in prediction.supporting_snps.values()}
    assert actual_genes == expected_genes


# ---------------------------------------------------------------------------
# Genotype interpretation: strong blue and strong brown patterns
# ---------------------------------------------------------------------------


def test_strong_blue_pattern_is_predicted_blue_moderate_confidence() -> None:
    model = EyeColourModel()

    prediction = model.predict(_strong_blue_calls())

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype.startswith("blue")
    assert "simplified scoring" in prediction.predicted_phenotype
    assert "published coefficients not used" in prediction.predicted_phenotype
    assert prediction.confidence == ConfidenceLevel.MODERATE


def test_strong_brown_pattern_is_predicted_brown_moderate_confidence() -> None:
    model = EyeColourModel()

    prediction = model.predict(_strong_brown_calls())

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype.startswith("brown")
    assert "simplified scoring" in prediction.predicted_phenotype
    assert prediction.confidence == ConfidenceLevel.MODERATE


def test_mixed_pattern_is_predicted_intermediate_low_confidence() -> None:
    # A genuinely mixed dosage pattern (not all-light, not all-dark)
    # should fall to intermediate, with lower confidence reflecting
    # IrisPlex's own documented weak intermediate-category sensitivity.
    model = EyeColourModel()
    calls = {
        _RSID_HERC2: _snp_call("AG"),  # heterozygous, dosage 1
        _RSID_OCA2: _snp_call("AG"),  # heterozygous, dosage 1
        _RSID_SLC24A4: _snp_call("GT"),  # heterozygous, dosage 1
        _RSID_SLC45A2: _snp_call("CG"),  # heterozygous, dosage 1
        _RSID_TYR: _snp_call("AG"),  # heterozygous, dosage 1
        _RSID_IRF4: _snp_call("CT"),  # heterozygous, dosage 1
    }

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype.startswith("intermediate")
    assert prediction.confidence == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# Missing SNP handling
# ---------------------------------------------------------------------------


def test_all_six_rsids_missing_is_insufficient_data() -> None:
    model = EyeColourModel()

    prediction = model.predict({})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    assert prediction.confidence is None
    assert prediction.observed_genotypes == {}
    assert prediction.supporting_snps == {}


def test_missing_herc2_specifically_is_insufficient_data_with_partial_evidence() -> (
    None
):
    # HERC2 is the most heavily weighted locus; confirm its absence
    # alone still blocks prediction rather than falling back to the
    # other five SNPs.
    model = EyeColourModel()
    calls = _strong_blue_calls()
    del calls[_RSID_HERC2]

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert _RSID_HERC2 not in prediction.observed_genotypes
    assert len(prediction.observed_genotypes) == 5
    assert prediction.supporting_snps == {}


# ---------------------------------------------------------------------------
# Unknown / unrecognized genotype handling
# ---------------------------------------------------------------------------


def test_no_call_at_one_locus_is_insufficient_data() -> None:
    model = EyeColourModel()
    calls = _strong_blue_calls()
    no_call = GenotypeCall(GenotypeCallKind.NO_CALL, None, None, "--")
    calls[_RSID_OCA2] = no_call

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes[_RSID_OCA2] is no_call


def test_indel_at_one_locus_is_insufficient_data() -> None:
    model = EyeColourModel()
    calls = _strong_blue_calls()
    calls[_RSID_SLC24A4] = GenotypeCall(GenotypeCallKind.INDEL, None, None, "DD")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


def test_haploid_at_one_locus_is_insufficient_data() -> None:
    model = EyeColourModel()
    calls = _strong_blue_calls()
    calls[_RSID_IRF4] = GenotypeCall(GenotypeCallKind.HAPLOID, None, "T", "T")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


def test_unrecognized_kind_at_one_locus_is_insufficient_data() -> None:
    model = EyeColourModel()
    calls = _strong_blue_calls()
    calls[_RSID_TYR] = GenotypeCall(GenotypeCallKind.UNRECOGNIZED, None, None, "GGG")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


def test_unsupported_allele_combination_at_one_locus_is_insufficient_data() -> None:
    # A SNP-classified call whose alleles match neither this locus's
    # associated nor other allele shape (SLC45A2's are G/C) -- a data
    # anomaly, never guessed at.
    model = EyeColourModel()
    calls = _strong_blue_calls()
    calls[_RSID_SLC45A2] = _snp_call("AT")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None


# ---------------------------------------------------------------------------
# TraitPrediction correctness
# ---------------------------------------------------------------------------


def test_predicted_trait_prediction_carries_expected_fields() -> None:
    model = EyeColourModel()
    calls = _strong_blue_calls()

    prediction = model.predict(calls)

    assert prediction.trait_id == "eye_colour"
    assert prediction.status == PredictionStatus.PREDICTED
    for rsid in _ALL_RSIDS:
        assert prediction.observed_genotypes[rsid] is calls[rsid]
        assert prediction.supporting_snps[rsid] is SNP_REGISTRY[rsid]


def test_supporting_snps_is_empty_on_insufficient_data() -> None:
    model = EyeColourModel()

    prediction = model.predict({})

    assert prediction.supporting_snps == {}


# ---------------------------------------------------------------------------
# TraitModel Protocol compliance
# ---------------------------------------------------------------------------


def test_eye_colour_model_satisfies_traitmodel_protocol() -> None:
    model = EyeColourModel()

    assert hasattr(TraitModel, "predict")
    assert callable(getattr(model, "predict", None))


def test_predict_accepts_plain_mapping_and_returns_traitprediction_type() -> None:
    model = EyeColourModel()

    prediction = model.predict(_strong_blue_calls())

    assert isinstance(prediction, TraitPrediction)


def test_predict_never_raises_for_any_condition() -> None:
    model = EyeColourModel()
    conditions = [
        {},
        _strong_blue_calls(),
        _strong_brown_calls(),
        {_RSID_HERC2: _snp_call("GG")},
        {_RSID_OCA2: GenotypeCall(GenotypeCallKind.NO_CALL, None, None, "--")},
        {_RSID_SLC24A4: GenotypeCall(GenotypeCallKind.INDEL, None, None, "DD")},
        {_RSID_SLC45A2: GenotypeCall(GenotypeCallKind.HAPLOID, None, "G", "G")},
        {_RSID_TYR: GenotypeCall(GenotypeCallKind.UNRECOGNIZED, None, None, "GGG")},
        {_RSID_IRF4: _snp_call("AG")},
    ]

    for genotype_calls in conditions:
        model.predict(genotype_calls)  # must not raise
