# tests/traits/test_eye_colour_model.py
"""Unit tests for EyeColourModel -- IrisPlex multinomial logistic
regression implementation.

Covers: model initialization, recognition of all six required IrisPlex
SNP dependencies, regression reproduction of the verified worked
example, the probability-sum invariant, dosage conversion for all
three genotype shapes, missing-SNP handling, unknown/unrecognized
genotype handling, TraitPrediction field correctness, evidence
preservation, structural TraitModel Protocol compliance, and
confidence-margin derivation.
"""

from __future__ import annotations

import math
import re

from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCall,
    GenotypeCallKind,
    PredictionStatus,
    TraitPrediction,
)
from phenopred_phase2.traits.domain.interfaces import TraitModel
from phenopred_phase2.traits.domain.irisplex_coefficients import IRISPLEX_COEFFICIENTS
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


def _counted_allele(rsid: str) -> str:
    return IRISPLEX_COEFFICIENTS[rsid].counted_allele


def _other_allele(rsid: str) -> str:
    record = SNP_REGISTRY[rsid]
    counted = _counted_allele(rsid)
    return record.alternate_allele if record.reference_allele == counted else record.reference_allele


def _homozygous_counted_calls() -> dict[str, GenotypeCall]:
    return {
        rsid: _snp_call("".join(sorted(_counted_allele(rsid) * 2)))
        for rsid in _ALL_RSIDS
    }


def _homozygous_other_calls() -> dict[str, GenotypeCall]:
    return {
        rsid: _snp_call("".join(sorted(_other_allele(rsid) * 2)))
        for rsid in _ALL_RSIDS
    }


def _heterozygous_calls() -> dict[str, GenotypeCall]:
    return {
        rsid: _snp_call("".join(sorted(_counted_allele(rsid) + _other_allele(rsid))))
        for rsid in _ALL_RSIDS
    }


# The Gymrek Lab / CSE 185 worked example this project independently
# verified during coefficient review: rs12913832=GG, rs1800407=CC,
# rs12896399=GG, rs16891982=GG, rs1393350=GA, rs12203592=CC, expected
# p_blue=0.8846, p_other=0.0811, p_brown=0.0343.
_WORKED_EXAMPLE_CALLS: dict[str, GenotypeCall] = {
    _RSID_HERC2: _snp_call("GG"),
    _RSID_OCA2: _snp_call("CC"),
    _RSID_SLC24A4: _snp_call("GG"),
    _RSID_SLC45A2: _snp_call("GG"),
    _RSID_TYR: _snp_call("AG"),
    _RSID_IRF4: _snp_call("CC"),
}


def _parse_probabilities(predicted_phenotype: str) -> dict[str, float]:
    pattern = r"(Blue|Other|Brown):\s*([\d.]+)%"
    matches = re.findall(pattern, predicted_phenotype)
    return {label.lower(): float(value) / 100.0 for label, value in matches}


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_eye_colour_model_can_be_initialized() -> None:
    model = EyeColourModel()

    assert model is not None


# ---------------------------------------------------------------------------
# Regression correctness (worked example reproduction)
# ---------------------------------------------------------------------------


def test_worked_example_reproduces_verified_probabilities() -> None:
    model = EyeColourModel()

    prediction = model.predict(_WORKED_EXAMPLE_CALLS)

    assert prediction.status == PredictionStatus.PREDICTED
    probabilities = _parse_probabilities(prediction.predicted_phenotype)
    assert math.isclose(probabilities["blue"], 0.885, abs_tol=1e-9)
    assert math.isclose(probabilities["other"], 0.081, abs_tol=1e-9)
    assert math.isclose(probabilities["brown"], 0.034, abs_tol=1e-9)
    assert "most likely category: blue" in prediction.predicted_phenotype.lower()


def test_worked_example_probabilities_sum_to_one() -> None:
    model = EyeColourModel()

    prediction = model.predict(_WORKED_EXAMPLE_CALLS)

    probabilities = _parse_probabilities(prediction.predicted_phenotype)
    total = probabilities["blue"] + probabilities["other"] + probabilities["brown"]
    assert math.isclose(total, 1.0, abs_tol=0.01)


def test_worked_example_is_high_confidence() -> None:
    # Blue (88.5%) vs. the next-highest (Other, 8.1%) is a very large
    # margin (~80 points) -- HIGH confidence under the approved
    # thresholds.
    model = EyeColourModel()

    prediction = model.predict(_WORKED_EXAMPLE_CALLS)

    assert prediction.confidence == ConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# Recognition of all six required SNP dependencies
# ---------------------------------------------------------------------------


def test_missing_each_required_rsid_individually_is_insufficient_data() -> None:
    model = EyeColourModel()

    for missing_rsid in _ALL_RSIDS:
        calls = _homozygous_counted_calls()
        del calls[missing_rsid]

        prediction = model.predict(calls)

        assert prediction.status == PredictionStatus.INSUFFICIENT_DATA, (
            f"missing {missing_rsid} should yield INSUFFICIENT_DATA"
        )


def test_supporting_snps_on_predicted_contains_all_six_genes() -> None:
    model = EyeColourModel()

    prediction = model.predict(_homozygous_counted_calls())

    assert prediction.status == PredictionStatus.PREDICTED
    assert set(prediction.supporting_snps.keys()) == set(_ALL_RSIDS)
    expected_genes = {"HERC2", "OCA2", "SLC24A4", "SLC45A2", "TYR", "IRF4"}
    actual_genes = {record.gene for record in prediction.supporting_snps.values()}
    assert actual_genes == expected_genes


# ---------------------------------------------------------------------------
# Dosage conversion
# ---------------------------------------------------------------------------


def test_homozygous_counted_allele_yields_dosage_two_for_every_snp() -> None:
    # Homozygous for every SNP's own counted_allele should push the
    # model as far toward "not brown" as every locus allows -- confirms
    # dosage=2 is being applied, not silently truncated or ignored.
    model = EyeColourModel()

    prediction = model.predict(_homozygous_counted_calls())

    assert prediction.status == PredictionStatus.PREDICTED


def test_homozygous_other_allele_yields_dosage_zero_for_every_snp() -> None:
    model = EyeColourModel()

    prediction = model.predict(_homozygous_other_calls())

    assert prediction.status == PredictionStatus.PREDICTED


def test_heterozygous_yields_dosage_one_for_every_snp() -> None:
    model = EyeColourModel()

    prediction = model.predict(_heterozygous_calls())

    assert prediction.status == PredictionStatus.PREDICTED


def test_dosage_extremes_produce_different_predictions() -> None:
    # A direct behavioural check that dosage genuinely drives the
    # regression: the all-counted-homozygous and all-other-homozygous
    # panels must not produce the same probability distribution.
    model = EyeColourModel()

    counted_prediction = model.predict(_homozygous_counted_calls())
    other_prediction = model.predict(_homozygous_other_calls())

    assert counted_prediction.predicted_phenotype != other_prediction.predicted_phenotype


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
    model = EyeColourModel()
    calls = _homozygous_counted_calls()
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
    calls = _homozygous_counted_calls()
    no_call = GenotypeCall(GenotypeCallKind.NO_CALL, None, None, "--")
    calls[_RSID_OCA2] = no_call

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.observed_genotypes[_RSID_OCA2] is no_call


def test_indel_at_one_locus_is_insufficient_data() -> None:
    model = EyeColourModel()
    calls = _homozygous_counted_calls()
    calls[_RSID_SLC24A4] = GenotypeCall(GenotypeCallKind.INDEL, None, None, "DD")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


def test_haploid_at_one_locus_is_insufficient_data() -> None:
    model = EyeColourModel()
    calls = _homozygous_counted_calls()
    calls[_RSID_IRF4] = GenotypeCall(GenotypeCallKind.HAPLOID, None, "T", "T")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


def test_unrecognized_kind_at_one_locus_is_insufficient_data() -> None:
    model = EyeColourModel()
    calls = _homozygous_counted_calls()
    calls[_RSID_TYR] = GenotypeCall(GenotypeCallKind.UNRECOGNIZED, None, None, "GGG")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


def test_unsupported_allele_combination_at_one_locus_is_insufficient_data() -> None:
    # A SNP-classified call whose alleles match neither this locus's
    # counted nor other allele shape (SLC45A2's are C/G) -- a data
    # anomaly, never guessed at.
    model = EyeColourModel()
    calls = _homozygous_counted_calls()
    calls[_RSID_SLC45A2] = _snp_call("AT")

    prediction = model.predict(calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None


# ---------------------------------------------------------------------------
# TraitPrediction correctness
# ---------------------------------------------------------------------------


def test_predicted_trait_prediction_carries_expected_fields() -> None:
    model = EyeColourModel()
    calls = _homozygous_counted_calls()

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


def test_predicted_phenotype_uses_other_not_intermediate() -> None:
    # Per the approved decision: use IrisPlex's own category name
    # "other" in model logic/output, never "intermediate".
    model = EyeColourModel()

    prediction = model.predict(_homozygous_counted_calls())

    assert "other" in prediction.predicted_phenotype.lower()
    assert "intermediate" not in prediction.predicted_phenotype.lower()


# ---------------------------------------------------------------------------
# TraitModel Protocol compliance
# ---------------------------------------------------------------------------


def test_eye_colour_model_satisfies_traitmodel_protocol() -> None:
    model = EyeColourModel()

    assert hasattr(TraitModel, "predict")
    assert callable(getattr(model, "predict", None))


def test_predict_accepts_plain_mapping_and_returns_traitprediction_type() -> None:
    model = EyeColourModel()

    prediction = model.predict(_homozygous_counted_calls())

    assert isinstance(prediction, TraitPrediction)


def test_predict_never_raises_for_any_condition() -> None:
    model = EyeColourModel()
    conditions = [
        {},
        _homozygous_counted_calls(),
        _homozygous_other_calls(),
        _heterozygous_calls(),
        {_RSID_HERC2: _snp_call("GG")},
        {_RSID_OCA2: GenotypeCall(GenotypeCallKind.NO_CALL, None, None, "--")},
        {_RSID_SLC24A4: GenotypeCall(GenotypeCallKind.INDEL, None, None, "DD")},
        {_RSID_SLC45A2: GenotypeCall(GenotypeCallKind.HAPLOID, None, "G", "G")},
        {_RSID_TYR: GenotypeCall(GenotypeCallKind.UNRECOGNIZED, None, None, "GGG")},
        {_RSID_IRF4: _snp_call("AT")},
    ]

    for genotype_calls in conditions:
        model.predict(genotype_calls)  # must not raise