# tests/comparison/test_trait_diff.py
"""Unit tests for trait_diff.py."""

from __future__ import annotations

from phenopred_phase2.comparison.domain.entities import TraitAgreement
from phenopred_phase2.comparison.domain.trait_diff import compare_trait_predictions
from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    PredictionStatus,
    TraitPrediction,
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


def _insufficient(trait_id: str) -> TraitPrediction:
    return TraitPrediction(
        trait_id=trait_id,
        status=PredictionStatus.INSUFFICIENT_DATA,
        predicted_phenotype=None,
        confidence=None,
        observed_genotypes={},
        supporting_snps={},
    )


def test_both_predicted_same_phenotype_is_agree() -> None:
    predictions_a = {"earwax_type": _predicted("earwax_type", "wet earwax")}
    predictions_b = {"earwax_type": _predicted("earwax_type", "wet earwax")}

    result = compare_trait_predictions(predictions_a, predictions_b)

    assert result["earwax_type"].agreement == TraitAgreement.AGREE


def test_both_predicted_different_phenotype_is_disagree() -> None:
    predictions_a = {"earwax_type": _predicted("earwax_type", "wet earwax")}
    predictions_b = {"earwax_type": _predicted("earwax_type", "dry earwax")}

    result = compare_trait_predictions(predictions_a, predictions_b)

    assert result["earwax_type"].agreement == TraitAgreement.DISAGREE


def test_either_side_insufficient_data_is_insufficient_data() -> None:
    predictions_a = {"earwax_type": _predicted("earwax_type", "wet earwax")}
    predictions_b = {"earwax_type": _insufficient("earwax_type")}

    result = compare_trait_predictions(predictions_a, predictions_b)

    assert result["earwax_type"].agreement == TraitAgreement.INSUFFICIENT_DATA


def test_both_sides_insufficient_data_is_insufficient_data() -> None:
    predictions_a = {"earwax_type": _insufficient("earwax_type")}
    predictions_b = {"earwax_type": _insufficient("earwax_type")}

    result = compare_trait_predictions(predictions_a, predictions_b)

    assert result["earwax_type"].agreement == TraitAgreement.INSUFFICIENT_DATA


def test_trait_missing_from_one_mapping_is_missing_trait() -> None:
    predictions_a = {"earwax_type": _predicted("earwax_type", "wet earwax")}
    predictions_b: dict = {}

    result = compare_trait_predictions(predictions_a, predictions_b)

    assert result["earwax_type"].agreement == TraitAgreement.MISSING_TRAIT
    assert result["earwax_type"].prediction_a is not None
    assert result["earwax_type"].prediction_b is None


def test_trait_missing_from_both_mappings_never_appears_in_result() -> None:
    result = compare_trait_predictions({}, {})

    assert result == {}


def test_result_includes_every_trait_id_present_in_either_mapping() -> None:
    predictions_a = {
        "earwax_type": _predicted("earwax_type", "wet earwax"),
        "actn3": _predicted("actn3", "ACTN3 RR"),
    }
    predictions_b = {
        "earwax_type": _predicted("earwax_type", "wet earwax"),
        "bitter_taste": _predicted("bitter_taste", "taster"),
    }

    result = compare_trait_predictions(predictions_a, predictions_b)

    assert set(result.keys()) == {"earwax_type", "actn3", "bitter_taste"}
    assert result["actn3"].agreement == TraitAgreement.MISSING_TRAIT
    assert result["bitter_taste"].agreement == TraitAgreement.MISSING_TRAIT


def test_full_predictions_are_preserved_for_future_discrepancy_explanation() -> (
    None
):
    prediction_a = _predicted("earwax_type", "wet earwax")
    prediction_b = _predicted("earwax_type", "dry earwax")
    predictions_a = {"earwax_type": prediction_a}
    predictions_b = {"earwax_type": prediction_b}

    result = compare_trait_predictions(predictions_a, predictions_b)

    # Both full TraitPredictions -- including observed_genotypes and
    # supporting_snps -- must be preserved unaltered, since this is the
    # structured evidence a future reporting layer needs to explain the
    # discrepancy without this module generating any prose itself.
    assert result["earwax_type"].prediction_a is prediction_a
    assert result["earwax_type"].prediction_b is prediction_b


def test_confidence_is_never_used_to_determine_agreement() -> None:
    # Two predictions with the same phenotype but (hypothetically)
    # different confidence must still agree -- confidence comparison is
    # explicitly out of scope for this module.
    prediction_a = _predicted("earwax_type", "wet earwax")
    prediction_b = TraitPrediction(
        trait_id="earwax_type",
        status=PredictionStatus.PREDICTED,
        predicted_phenotype="wet earwax",
        confidence=ConfidenceLevel.LOW,
        observed_genotypes={},
        supporting_snps={},
    )

    result = compare_trait_predictions(
        {"earwax_type": prediction_a}, {"earwax_type": prediction_b}
    )

    assert result["earwax_type"].agreement == TraitAgreement.AGREE
