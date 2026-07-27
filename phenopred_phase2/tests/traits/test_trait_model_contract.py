# tests/traits/test_trait_model_contract.py
"""Unit tests for TraitPrediction and the TraitModel protocol.

These are contract-level tests only, per the frozen "Trait Contract
Layer -- Frozen Architecture Specification v1": they verify
TraitPrediction's immutability and, via a fake TraitModel
implementation, that the protocol's PREDICTED and INSUFFICIENT_DATA
paths are both usable against plain GenotypeCall data. No concrete
trait model (lactase, eye colour, ACTN3, earwax, bitter taste, ALDH2),
no TraitEngine, and no GenotypeIndex/DataRow construction is required
by this suite -- the fake model below takes only a plain dict literal,
exactly the testability property Review Point 1 of the frozen
specification is designed to guarantee.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

import pytest

from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCall,
    GenotypeCallKind,
    PredictionStatus,
    TraitPrediction,
)
from phenopred_phase2.traits.domain.interfaces import TraitModel


# ---------------------------------------------------------------------------
# TraitPrediction immutability
# ---------------------------------------------------------------------------


def _make_prediction(**overrides) -> TraitPrediction:
    fields = {
        "trait_id": "test_trait",
        "status": PredictionStatus.PREDICTED,
        "predicted_phenotype": "example phenotype",
        "confidence": ConfidenceLevel.HIGH,
        "observed_genotypes": {},
        "supporting_snps": {},
    }
    fields.update(overrides)
    return TraitPrediction(**fields)


def test_traitprediction_is_frozen() -> None:
    prediction = _make_prediction()

    with pytest.raises(dataclasses.FrozenInstanceError):
        prediction.predicted_phenotype = "other phenotype"  # type: ignore[misc]


def test_traitprediction_constructs_with_all_fields_populated() -> None:
    genotype_call = GenotypeCall(
        kind=GenotypeCallKind.SNP, alleles="AG", allele=None, raw_value="GA"
    )
    prediction = _make_prediction(observed_genotypes={"rs0000001": genotype_call})

    assert prediction.trait_id == "test_trait"
    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.observed_genotypes["rs0000001"] is genotype_call


def test_traitprediction_supports_insufficient_data_state() -> None:
    prediction = _make_prediction(
        status=PredictionStatus.INSUFFICIENT_DATA,
        predicted_phenotype=None,
        confidence=None,
        observed_genotypes={},
        supporting_snps={},
    )

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    assert prediction.confidence is None


# ---------------------------------------------------------------------------
# TraitModel protocol conformance (fake implementation)
# ---------------------------------------------------------------------------


class _FakeSingleSnpTraitModel:
    """A minimal fake TraitModel, permanently bound to one rsid, used
    only to prove the protocol's contract is satisfiable with plain
    data -- not a real trait model.
    """

    _TRAIT_ID = "fake_trait"
    _REQUIRED_RSID = "rs0000001"

    def predict(self, genotype_calls: Mapping[str, GenotypeCall]) -> TraitPrediction:
        call = genotype_calls.get(self._REQUIRED_RSID)

        if call is None or call.kind != GenotypeCallKind.SNP:
            return TraitPrediction(
                trait_id=self._TRAIT_ID,
                status=PredictionStatus.INSUFFICIENT_DATA,
                predicted_phenotype=None,
                confidence=None,
                observed_genotypes=(
                    {self._REQUIRED_RSID: call} if call is not None else {}
                ),
                supporting_snps={},
            )

        return TraitPrediction(
            trait_id=self._TRAIT_ID,
            status=PredictionStatus.PREDICTED,
            predicted_phenotype=f"example phenotype for {call.alleles}",
            confidence=ConfidenceLevel.HIGH,
            observed_genotypes={self._REQUIRED_RSID: call},
            supporting_snps={},
        )


def test_fake_trait_model_satisfies_traitmodel_protocol() -> None:
    # TraitModel is a plain (non-runtime-checkable) Protocol per the
    # frozen specification -- isinstance() checks are intentionally not
    # part of this contract, so conformance is verified structurally:
    # the fake exposes a callable predict() matching the protocol's
    # sole method name.
    model = _FakeSingleSnpTraitModel()

    assert hasattr(TraitModel, "predict")
    assert callable(getattr(model, "predict", None))


def test_fake_trait_model_predicted_path_with_plain_dict_input() -> None:
    model = _FakeSingleSnpTraitModel()
    genotype_calls = {
        "rs0000001": GenotypeCall(
            kind=GenotypeCallKind.SNP, alleles="AG", allele=None, raw_value="GA"
        )
    }

    prediction = model.predict(genotype_calls)

    assert prediction.status == PredictionStatus.PREDICTED
    assert prediction.predicted_phenotype == "example phenotype for AG"
    assert prediction.confidence == ConfidenceLevel.HIGH
    assert "rs0000001" in prediction.observed_genotypes


def test_fake_trait_model_insufficient_data_path_when_rsid_missing() -> None:
    model = _FakeSingleSnpTraitModel()

    prediction = model.predict({})

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    assert prediction.confidence is None
    assert prediction.observed_genotypes == {}


def test_fake_trait_model_insufficient_data_path_when_no_call() -> None:
    model = _FakeSingleSnpTraitModel()
    genotype_calls = {
        "rs0000001": GenotypeCall(
            kind=GenotypeCallKind.NO_CALL, alleles=None, allele=None, raw_value="--"
        )
    }

    prediction = model.predict(genotype_calls)

    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    # Partial data is still surfaced for transparency, per the frozen
    # specification's observed_genotypes contract.
    assert "rs0000001" in prediction.observed_genotypes