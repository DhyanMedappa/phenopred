# tests/traits/test_trait_card.py
"""Unit tests for the TraitCard entity (phenopred_phase2/traits/domain/
entities.py).

These are pure entity-construction tests, mirroring this codebase's
existing style for TraitDefinition/TraitPrediction/ConcordanceResult/
IdentityLikelihood: no file I/O, no engine, no registry lookup --
every input is hand-built directly. Builder-level tests (pairing a
TraitDefinition with a TraitPrediction, iterating a registry) live
separately in test_trait_card_builder.py.
"""

from __future__ import annotations

import pytest

from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCall,
    GenotypeCallKind,
    PredictionStatus,
    TraitCard,
    TraitPrediction,
)


def _predicted(trait_id: str = "lactase_persistence") -> TraitPrediction:
    return TraitPrediction(
        trait_id=trait_id,
        status=PredictionStatus.PREDICTED,
        predicted_phenotype="lactase non-persistent",
        confidence=ConfidenceLevel.HIGH,
        observed_genotypes={
            "rs4988235": GenotypeCall(
                kind=GenotypeCallKind.SNP, alleles="GG", allele=None, raw_value="G/G"
            )
        },
        supporting_snps={},
    )


def _insufficient(trait_id: str = "eye_colour") -> TraitPrediction:
    return TraitPrediction(
        trait_id=trait_id,
        status=PredictionStatus.INSUFFICIENT_DATA,
        predicted_phenotype=None,
        confidence=None,
        observed_genotypes={},
        supporting_snps={},
    )


# ---------------------------------------------------------------------------
# Correct construction
# ---------------------------------------------------------------------------


def test_trait_card_constructs_with_valid_predicted_data() -> None:
    prediction = _predicted()

    card = TraitCard(
        trait_id="lactase_persistence",
        trait_name="Lactase Persistence",
        trait_evidence_refs=("Some literature citation.",),
        prediction=prediction,
        limitation_keys=("ancestry_generalizability",),
    )

    assert card.trait_id == "lactase_persistence"
    assert card.trait_name == "Lactase Persistence"
    assert card.trait_evidence_refs == ("Some literature citation.",)
    assert card.prediction is prediction
    assert card.limitation_keys == ("ancestry_generalizability",)


def test_trait_card_constructs_with_valid_insufficient_data_prediction() -> None:
    prediction = _insufficient()

    card = TraitCard(
        trait_id="eye_colour",
        trait_name="Eye Colour (IrisPlex)",
        trait_evidence_refs=(),
        prediction=prediction,
        limitation_keys=("ancestry_generalizability",),
    )

    assert card.prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert card.prediction.predicted_phenotype is None
    assert card.prediction.confidence is None


def test_trait_card_trait_evidence_refs_may_be_empty_tuple() -> None:
    # TraitDefinition.evidence_refs carries no non-empty invariant of its
    # own (only required_rsids does); TraitCard must not impose a
    # stricter rule on this field than the entity it is sourced from.
    card = TraitCard(
        trait_id="actn3",
        trait_name="ACTN3 (Alpha-Actinin-3)",
        trait_evidence_refs=(),
        prediction=_predicted(trait_id="actn3"),
        limitation_keys=("ancestry_generalizability",),
    )
    assert card.trait_evidence_refs == ()


# ---------------------------------------------------------------------------
# Required-field / invalid-state enforcement
# ---------------------------------------------------------------------------


def test_trait_card_rejects_empty_trait_id() -> None:
    with pytest.raises(ValueError, match="trait_id must be non-empty"):
        TraitCard(
            trait_id="",
            trait_name="Lactase Persistence",
            trait_evidence_refs=(),
            prediction=_predicted(trait_id=""),
            limitation_keys=("ancestry_generalizability",),
        )


def test_trait_card_rejects_whitespace_only_trait_id() -> None:
    with pytest.raises(ValueError, match="trait_id must be non-empty"):
        TraitCard(
            trait_id="   ",
            trait_name="Lactase Persistence",
            trait_evidence_refs=(),
            prediction=_predicted(trait_id="   "),
            limitation_keys=("ancestry_generalizability",),
        )


def test_trait_card_rejects_empty_trait_name() -> None:
    with pytest.raises(ValueError, match="trait_name must be non-empty"):
        TraitCard(
            trait_id="lactase_persistence",
            trait_name="",
            trait_evidence_refs=(),
            prediction=_predicted(),
            limitation_keys=("ancestry_generalizability",),
        )


def test_trait_card_rejects_mismatched_trait_id_and_prediction_trait_id() -> None:
    # card claims "actn3" but embeds a prediction for "lactase_persistence"
    with pytest.raises(ValueError, match="must match"):
        TraitCard(
            trait_id="actn3",
            trait_name="ACTN3 (Alpha-Actinin-3)",
            trait_evidence_refs=(),
            prediction=_predicted(trait_id="lactase_persistence"),
            limitation_keys=("ancestry_generalizability",),
        )


def test_trait_card_rejects_empty_limitation_keys() -> None:
    # Every card must carry at least its standing scientific caveat
    # reference key -- this must be structurally impossible to omit.
    with pytest.raises(ValueError, match="limitation_keys must be a non-empty tuple"):
        TraitCard(
            trait_id="lactase_persistence",
            trait_name="Lactase Persistence",
            trait_evidence_refs=(),
            prediction=_predicted(),
            limitation_keys=(),
        )


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


def test_trait_card_is_frozen() -> None:
    card = TraitCard(
        trait_id="lactase_persistence",
        trait_name="Lactase Persistence",
        trait_evidence_refs=(),
        prediction=_predicted(),
        limitation_keys=("ancestry_generalizability",),
    )
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
        card.trait_name = "Something else"  # type: ignore[misc]