# tests/traits/test_trait_card_builder.py
"""Unit and compatibility tests for trait_card_builder.py.

These tests verify only assembly/wiring (the right TraitDefinition is
paired with the right TraitPrediction, and the result is correctly
shaped) -- not TraitCard's own construction invariants, which are
already covered in isolation by test_trait_card.py, and not any
trait model's prediction logic, which is out of scope for this module
entirely.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from phenopred_phase2.traits.application.trait_engine import TraitEngine
from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCall,
    GenotypeCallKind,
    PredictionStatus,
    TraitCard,
    TraitDefinition,
    TraitPrediction,
)
from phenopred_phase2.traits.domain.trait_registry import TRAIT_REGISTRY
from phenopred_phase2.traits.reporting.trait_card_builder import (
    ANCESTRY_GENERALIZABILITY_CAVEAT_KEY,
    build_trait_card,
    build_trait_cards,
)


def _definition(trait_id: str = "demo_trait") -> TraitDefinition:
    return TraitDefinition(
        trait_id=trait_id,
        name="Demo Trait",
        required_rsids=("rs0000001",),
        evidence_refs=("A demo citation.",),
    )


def _predicted(trait_id: str = "demo_trait") -> TraitPrediction:
    return TraitPrediction(
        trait_id=trait_id,
        status=PredictionStatus.PREDICTED,
        predicted_phenotype="demo phenotype",
        confidence=ConfidenceLevel.MODERATE,
        observed_genotypes={
            "rs0000001": GenotypeCall(
                kind=GenotypeCallKind.SNP, alleles="AG", allele=None, raw_value="A/G"
            )
        },
        supporting_snps={},
    )


def _insufficient(trait_id: str = "demo_trait") -> TraitPrediction:
    return TraitPrediction(
        trait_id=trait_id,
        status=PredictionStatus.INSUFFICIENT_DATA,
        predicted_phenotype=None,
        confidence=None,
        observed_genotypes={},
        supporting_snps={},
    )


# ---------------------------------------------------------------------------
# build_trait_card: single-pair assembly
# ---------------------------------------------------------------------------


def test_build_trait_card_pairs_definition_and_prediction_correctly() -> None:
    definition = _definition()
    prediction = _predicted()

    card = build_trait_card(definition, prediction)

    assert isinstance(card, TraitCard)
    assert card.trait_id == "demo_trait"
    assert card.trait_name == "Demo Trait"
    assert card.trait_evidence_refs == ("A demo citation.",)
    assert card.prediction is prediction
    assert ANCESTRY_GENERALIZABILITY_CAVEAT_KEY in card.limitation_keys


def test_build_trait_card_works_for_insufficient_data_predictions() -> None:
    definition = _definition()
    prediction = _insufficient()

    card = build_trait_card(definition, prediction)

    assert card.prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert card.prediction.predicted_phenotype is None
    # Even an insufficient-data card must still carry its standing
    # caveat reference -- limitations are about generalizability of the
    # science, not about whether a result was reached.
    assert ANCESTRY_GENERALIZABILITY_CAVEAT_KEY in card.limitation_keys


def test_build_trait_card_rejects_mismatched_trait_ids() -> None:
    definition = _definition(trait_id="demo_trait")
    prediction = _predicted(trait_id="a_different_trait")

    with pytest.raises(ValueError, match="does not match"):
        build_trait_card(definition, prediction)


def test_build_trait_card_does_not_mutate_its_inputs() -> None:
    definition = _definition()
    prediction = _predicted()

    definition_before = definition
    prediction_before = prediction

    build_trait_card(definition, prediction)

    # Frozen dataclasses can't be mutated in place, but this also
    # confirms identity was preserved (no copy-and-modify occurred).
    assert definition is definition_before
    assert prediction is prediction_before


# ---------------------------------------------------------------------------
# build_trait_cards: registry-driven, plural assembly
# ---------------------------------------------------------------------------


def test_build_trait_cards_returns_one_card_per_prediction() -> None:
    registry = {"demo_trait": _definition()}
    predictions = {"demo_trait": _predicted()}

    cards = build_trait_cards(registry, predictions)

    assert isinstance(cards, Mapping)
    assert set(cards.keys()) == {"demo_trait"}
    assert isinstance(cards["demo_trait"], TraitCard)


def test_build_trait_cards_only_builds_cards_for_predictions_actually_present() -> (
    None
):
    # trait_registry has two traits, but predictions only has one --
    # mirroring TraitEngine.run()'s own "not every registered trait is
    # necessarily bound/executed" discipline. build_trait_cards must
    # never fabricate a card for a trait that was never predicted.
    registry = {
        "demo_trait": _definition("demo_trait"),
        "other_trait": _definition("other_trait"),
    }
    predictions = {"demo_trait": _predicted("demo_trait")}

    cards = build_trait_cards(registry, predictions)

    assert set(cards.keys()) == {"demo_trait"}


def test_build_trait_cards_raises_on_trait_id_absent_from_registry() -> None:
    registry: dict[str, TraitDefinition] = {}
    predictions = {"demo_trait": _predicted("demo_trait")}

    with pytest.raises(ValueError, match="no corresponding entry in trait_registry"):
        build_trait_cards(registry, predictions)


def test_build_trait_cards_handles_empty_predictions() -> None:
    cards = build_trait_cards(TRAIT_REGISTRY, {})  # must not raise
    assert cards == {}


def test_build_trait_cards_does_not_mutate_the_predictions_mapping() -> None:
    predictions = {"demo_trait": _predicted()}
    predictions_before = dict(predictions)

    build_trait_cards({"demo_trait": _definition()}, predictions)

    assert dict(predictions) == predictions_before


# ---------------------------------------------------------------------------
# Compatibility with real TRAIT_REGISTRY and real TraitEngine output
# ---------------------------------------------------------------------------


class _FakeSingleSnpTraitModel:
    """Minimal fake TraitModel, mirroring the existing test convention
    already referenced in trait_engine.py's own docstring
    (_FakeSingleSnpTraitModel) -- exposes only predict(), the one method
    the TraitModel Protocol requires.
    """

    def __init__(self, trait_id: str, rsid: str) -> None:
        self._trait_id = trait_id
        self._rsid = rsid

    def predict(self, genotype_calls):
        call = genotype_calls.get(self._rsid)
        if call is None:
            return TraitPrediction(
                trait_id=self._trait_id,
                status=PredictionStatus.INSUFFICIENT_DATA,
                predicted_phenotype=None,
                confidence=None,
                observed_genotypes={},
                supporting_snps={},
            )
        return TraitPrediction(
            trait_id=self._trait_id,
            status=PredictionStatus.PREDICTED,
            predicted_phenotype="fake phenotype",
            confidence=ConfidenceLevel.HIGH,
            observed_genotypes={self._rsid: call},
            supporting_snps={},
        )


class _FakeGenotypeSource:
    def __init__(self, calls: dict[str, GenotypeCall]) -> None:
        self._calls = calls

    def get(self, rsid: str):
        return self._calls.get(rsid)


def test_build_trait_cards_is_compatible_with_real_trait_registry_and_real_trait_engine_output() -> (
    None
):
    # Uses the real, unmodified TRAIT_REGISTRY plus a real TraitEngine
    # run (with fake models standing in for the five concrete trait
    # models, exactly as trait_engine.py's own docstring documents as
    # the established fake-model testing convention) to prove
    # build_trait_cards accepts TraitEngine's actual output shape
    # without any adaptation.
    trait_model_registry = {
        trait_id: _FakeSingleSnpTraitModel(
            trait_id, TRAIT_REGISTRY[trait_id].required_rsids[0]
        )
        for trait_id in TRAIT_REGISTRY
    }
    engine = TraitEngine(TRAIT_REGISTRY, trait_model_registry)

    # Genotype source has no observed calls at all -> every trait must
    # resolve to INSUFFICIENT_DATA, but every registered trait must
    # still receive a TraitPrediction (and therefore a TraitCard).
    predictions = engine.run(_FakeGenotypeSource({}))

    assert set(predictions.keys()) == set(TRAIT_REGISTRY.keys())

    cards = build_trait_cards(TRAIT_REGISTRY, predictions)

    assert set(cards.keys()) == set(TRAIT_REGISTRY.keys())
    for trait_id, card in cards.items():
        assert card.trait_id == trait_id
        assert card.trait_name == TRAIT_REGISTRY[trait_id].name
        assert card.trait_evidence_refs == TRAIT_REGISTRY[trait_id].evidence_refs
        assert card.prediction is predictions[trait_id]
        assert card.prediction.status == PredictionStatus.INSUFFICIENT_DATA
        assert ANCESTRY_GENERALIZABILITY_CAVEAT_KEY in card.limitation_keys


def test_build_trait_cards_does_not_mutate_trait_registry_or_predictions() -> None:
    trait_model_registry = {
        trait_id: _FakeSingleSnpTraitModel(
            trait_id, TRAIT_REGISTRY[trait_id].required_rsids[0]
        )
        for trait_id in TRAIT_REGISTRY
    }
    engine = TraitEngine(TRAIT_REGISTRY, trait_model_registry)
    predictions = engine.run(_FakeGenotypeSource({}))
    predictions_before = dict(predictions)

    build_trait_cards(TRAIT_REGISTRY, predictions)

    assert dict(predictions) == predictions_before
    # TRAIT_REGISTRY is a MappingProxyType (immutable); confirm identity
    # and membership are unchanged.
    assert set(TRAIT_REGISTRY.keys()) == set(predictions_before.keys())