# tests/traits/test_trait_engine.py
"""Unit tests for TraitEngine.

TraitEngine is a registry-driven orchestrator with no biological logic
of its own. This suite verifies the approved architecture directly,
using entirely fake TraitDefinition, TraitModel, and genotype-source
objects -- never the real TRAIT_REGISTRY, TRAIT_MODEL_REGISTRY, or any
real trait model -- mirroring the fake-based testing philosophy already
established in test_trait_model_contract.py. A single, separate
end-to-end smoke test at the bottom confirms the engine also works
against the real registries and real models, without making that the
primary testing strategy.
"""

from __future__ import annotations

from collections.abc import Mapping

from phenopred_phase2.traits.application.trait_engine import TraitEngine
from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCall,
    GenotypeCallKind,
    PredictionStatus,
    TraitDefinition,
    TraitPrediction,
)


# ---------------------------------------------------------------------------
# Fakes -- no real trait model or real registry is imported anywhere below
# ---------------------------------------------------------------------------


def _snp_call(alleles: str) -> GenotypeCall:
    return GenotypeCall(
        kind=GenotypeCallKind.SNP, alleles=alleles, allele=None, raw_value=alleles
    )


class _FakeGenotypeSource:
    """A minimal fake genotype source, exposing only the single .get()
    method TraitEngine is permitted to call -- no file, no DataRow, no
    ColumnLayout involved anywhere.
    """

    def __init__(self, calls_by_rsid: Mapping[str, GenotypeCall]) -> None:
        self._calls_by_rsid = dict(calls_by_rsid)

    def get(self, rsid: str) -> GenotypeCall | None:
        return self._calls_by_rsid.get(rsid)


class _FakeTraitModel:
    """A minimal fake TraitModel bound to one or more rsids, recording
    every genotype_calls mapping it was invoked with, so tests can
    assert exactly what TraitEngine passed to it.
    """

    def __init__(self, trait_id: str, required_rsids: tuple[str, ...]) -> None:
        self._trait_id = trait_id
        self._required_rsids = required_rsids
        self.calls_received: list[Mapping[str, GenotypeCall]] = []

    def predict(self, genotype_calls: Mapping[str, GenotypeCall]) -> TraitPrediction:
        self.calls_received.append(genotype_calls)

        observed = {
            rsid: genotype_calls[rsid]
            for rsid in self._required_rsids
            if rsid in genotype_calls
        }

        if len(observed) != len(self._required_rsids):
            return TraitPrediction(
                trait_id=self._trait_id,
                status=PredictionStatus.INSUFFICIENT_DATA,
                predicted_phenotype=None,
                confidence=None,
                observed_genotypes=observed,
                supporting_snps={},
            )

        return TraitPrediction(
            trait_id=self._trait_id,
            status=PredictionStatus.PREDICTED,
            predicted_phenotype=f"fake phenotype for {self._trait_id}",
            confidence=ConfidenceLevel.HIGH,
            observed_genotypes=observed,
            supporting_snps={},
        )


class _RaisingTraitModel:
    """A fake TraitModel that always raises, used only to confirm
    TraitEngine never catches an unexpected exception from predict().
    """

    def predict(self, genotype_calls: Mapping[str, GenotypeCall]) -> TraitPrediction:
        raise RuntimeError("simulated unexpected model defect")


def _make_definition(trait_id: str, *required_rsids: str) -> TraitDefinition:
    return TraitDefinition(
        trait_id=trait_id,
        name=f"Fake Trait {trait_id}",
        required_rsids=required_rsids,
        evidence_refs=(),
    )


# ---------------------------------------------------------------------------
# Multiple traits execute correctly
# ---------------------------------------------------------------------------


def test_multiple_traits_execute_and_are_collected() -> None:
    trait_registry = {
        "trait_a": _make_definition("trait_a", "rs0000001"),
        "trait_b": _make_definition("trait_b", "rs0000002"),
    }
    model_a = _FakeTraitModel("trait_a", ("rs0000001",))
    model_b = _FakeTraitModel("trait_b", ("rs0000002",))
    trait_model_registry = {"trait_a": model_a, "trait_b": model_b}
    genotype_source = _FakeGenotypeSource(
        {"rs0000001": _snp_call("AG"), "rs0000002": _snp_call("CT")}
    )

    engine = TraitEngine(trait_registry, trait_model_registry)
    predictions = engine.run(genotype_source)

    assert predictions["trait_a"].status == PredictionStatus.PREDICTED
    assert predictions["trait_b"].status == PredictionStatus.PREDICTED
    assert len(predictions) == 2


# ---------------------------------------------------------------------------
# Correct model resolution
# ---------------------------------------------------------------------------


def test_each_trait_is_resolved_to_its_own_bound_model_only() -> None:
    trait_registry = {
        "trait_a": _make_definition("trait_a", "rs0000001"),
        "trait_b": _make_definition("trait_b", "rs0000002"),
    }
    model_a = _FakeTraitModel("trait_a", ("rs0000001",))
    model_b = _FakeTraitModel("trait_b", ("rs0000002",))
    trait_model_registry = {"trait_a": model_a, "trait_b": model_b}
    genotype_source = _FakeGenotypeSource(
        {"rs0000001": _snp_call("AG"), "rs0000002": _snp_call("CT")}
    )

    engine = TraitEngine(trait_registry, trait_model_registry)
    engine.run(genotype_source)

    assert len(model_a.calls_received) == 1
    assert len(model_b.calls_received) == 1


# ---------------------------------------------------------------------------
# Correct genotype calls are passed to models
# ---------------------------------------------------------------------------


def test_only_the_traits_own_required_rsids_are_passed_to_its_model() -> None:
    trait_registry = {"trait_a": _make_definition("trait_a", "rs0000001")}
    model_a = _FakeTraitModel("trait_a", ("rs0000001",))
    trait_model_registry = {"trait_a": model_a}
    call = _snp_call("AG")
    # An extra, unrelated rsid exists in the genotype source but is not
    # required by trait_a -- it must never leak into the mapping passed
    # to trait_a's model.
    genotype_source = _FakeGenotypeSource(
        {"rs0000001": call, "rs9999999": _snp_call("TT")}
    )

    engine = TraitEngine(trait_registry, trait_model_registry)
    engine.run(genotype_source)

    received = model_a.calls_received[0]
    assert dict(received) == {"rs0000001": call}


# ---------------------------------------------------------------------------
# Returned output structure is correct
# ---------------------------------------------------------------------------


def test_run_returns_a_mapping_keyed_by_trait_id() -> None:
    trait_registry = {"trait_a": _make_definition("trait_a", "rs0000001")}
    trait_model_registry = {"trait_a": _FakeTraitModel("trait_a", ("rs0000001",))}
    genotype_source = _FakeGenotypeSource({"rs0000001": _snp_call("AG")})

    engine = TraitEngine(trait_registry, trait_model_registry)
    predictions = engine.run(genotype_source)

    assert isinstance(predictions, Mapping)
    assert set(predictions.keys()) == {"trait_a"}
    assert isinstance(predictions["trait_a"], TraitPrediction)


# ---------------------------------------------------------------------------
# Deterministic ordering is preserved
# ---------------------------------------------------------------------------


def test_output_order_matches_trait_registry_iteration_order() -> None:
    trait_registry = {
        "trait_z": _make_definition("trait_z", "rs0000001"),
        "trait_a": _make_definition("trait_a", "rs0000002"),
        "trait_m": _make_definition("trait_m", "rs0000003"),
    }
    trait_model_registry = {
        "trait_z": _FakeTraitModel("trait_z", ("rs0000001",)),
        "trait_a": _FakeTraitModel("trait_a", ("rs0000002",)),
        "trait_m": _FakeTraitModel("trait_m", ("rs0000003",)),
    }
    genotype_source = _FakeGenotypeSource(
        {
            "rs0000001": _snp_call("AG"),
            "rs0000002": _snp_call("CT"),
            "rs0000003": _snp_call("GG"),
        }
    )

    engine = TraitEngine(trait_registry, trait_model_registry)
    predictions = engine.run(genotype_source)

    assert list(predictions.keys()) == ["trait_z", "trait_a", "trait_m"]


def test_run_is_repeatable_and_deterministic_across_calls() -> None:
    trait_registry = {"trait_a": _make_definition("trait_a", "rs0000001")}
    trait_model_registry = {"trait_a": _FakeTraitModel("trait_a", ("rs0000001",))}
    genotype_source = _FakeGenotypeSource({"rs0000001": _snp_call("AG")})

    engine = TraitEngine(trait_registry, trait_model_registry)
    first_run = engine.run(genotype_source)
    second_run = engine.run(genotype_source)

    assert list(first_run.keys()) == list(second_run.keys())
    assert first_run["trait_a"].status == second_run["trait_a"].status


# ---------------------------------------------------------------------------
# Missing model bindings are skipped
# ---------------------------------------------------------------------------


def test_trait_with_no_bound_model_is_skipped_not_raised() -> None:
    trait_registry = {
        "trait_a": _make_definition("trait_a", "rs0000001"),
        "trait_unbound": _make_definition("trait_unbound", "rs0000002"),
    }
    # Deliberately no entry for "trait_unbound".
    trait_model_registry = {"trait_a": _FakeTraitModel("trait_a", ("rs0000001",))}
    genotype_source = _FakeGenotypeSource({"rs0000001": _snp_call("AG")})

    engine = TraitEngine(trait_registry, trait_model_registry)
    predictions = engine.run(genotype_source)  # must not raise

    assert "trait_unbound" not in predictions
    assert "trait_a" in predictions


def test_all_traits_unbound_returns_empty_mapping() -> None:
    trait_registry = {"trait_a": _make_definition("trait_a", "rs0000001")}
    trait_model_registry: dict = {}
    genotype_source = _FakeGenotypeSource({})

    engine = TraitEngine(trait_registry, trait_model_registry)
    predictions = engine.run(genotype_source)

    assert predictions == {}


# ---------------------------------------------------------------------------
# Missing genotype information is delegated to model behavior
# ---------------------------------------------------------------------------


def test_missing_required_rsid_is_passed_through_as_absence_not_checked_by_engine() -> (
    None
):
    trait_registry = {"trait_a": _make_definition("trait_a", "rs0000001")}
    model_a = _FakeTraitModel("trait_a", ("rs0000001",))
    trait_model_registry = {"trait_a": model_a}
    # The genotype source has no entry at all for rs0000001.
    genotype_source = _FakeGenotypeSource({})

    engine = TraitEngine(trait_registry, trait_model_registry)
    predictions = engine.run(genotype_source)

    # The engine passed an empty mapping through; the fake model itself
    # decided this yields INSUFFICIENT_DATA -- the engine never checked
    # for the rsid's presence or absence itself.
    assert dict(model_a.calls_received[0]) == {}
    assert predictions["trait_a"].status == PredictionStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# INSUFFICIENT_DATA predictions are preserved
# ---------------------------------------------------------------------------


def test_insufficient_data_prediction_is_collected_unchanged() -> None:
    trait_registry = {"trait_a": _make_definition("trait_a", "rs0000001")}
    trait_model_registry = {"trait_a": _FakeTraitModel("trait_a", ("rs0000001",))}
    genotype_source = _FakeGenotypeSource({})  # forces INSUFFICIENT_DATA

    engine = TraitEngine(trait_registry, trait_model_registry)
    predictions = engine.run(genotype_source)

    prediction = predictions["trait_a"]
    assert prediction.status == PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_phenotype is None
    assert prediction.confidence is None


# ---------------------------------------------------------------------------
# Unexpected TraitModel exception is never caught
# ---------------------------------------------------------------------------


def test_unexpected_model_exception_propagates_uncaught() -> None:
    trait_registry = {"trait_a": _make_definition("trait_a", "rs0000001")}
    trait_model_registry = {"trait_a": _RaisingTraitModel()}
    genotype_source = _FakeGenotypeSource({"rs0000001": _snp_call("AG")})

    engine = TraitEngine(trait_registry, trait_model_registry)

    try:
        engine.run(genotype_source)
        raised = False
    except RuntimeError:
        raised = True

    assert raised, "TraitEngine must not silently catch an unexpected model exception"


# ---------------------------------------------------------------------------
# TraitEngine does not import any concrete trait model
# ---------------------------------------------------------------------------


def test_trait_engine_module_imports_no_concrete_trait_model() -> None:
    import phenopred_phase2.traits.application.trait_engine as module

    with open(module.__file__, encoding="utf-8") as handle:
        import_lines = [
            line
            for line in handle
            if line.strip().startswith(("from ", "import "))
        ]

    joined_imports = "".join(import_lines)
    for forbidden in (
        "LactasePersistenceModel",
        "EarwaxTypeModel",
        "ACTN3Model",
        "BitterTasteModel",
        "EyeColourModel",
        "models.actn3_model",
        "models.bitter_taste_model",
        "models.earwax_type_model",
        "models.eye_colour_model",
        "models.lactase_persistence_model",
    ):
        assert forbidden not in joined_imports


def test_trait_engine_module_does_not_import_trait_registry_or_trait_model_registry() -> (
    None
):
    # TraitEngine must receive its configuration via constructor
    # injection only -- never by importing TRAIT_REGISTRY or
    # TRAIT_MODEL_REGISTRY itself.
    import phenopred_phase2.traits.application.trait_engine as module

    with open(module.__file__, encoding="utf-8") as handle:
        import_lines = [
            line
            for line in handle
            if line.strip().startswith(("from ", "import "))
        ]

    joined_imports = "".join(import_lines)
    assert "trait_registry import" not in joined_imports
    assert "trait_model_registry import" not in joined_imports


def test_trait_engine_module_does_not_import_genotype_index_internals() -> None:
    # No DataRow / ColumnLayout import anywhere -- confirms the engine
    # only ever touches a genotype source through its public .get().
    # (The module's own docstring legitimately mentions these names in
    # prose while explaining what it does NOT depend on -- exactly as
    # trait_model_registry.py's docstring already does for
    # GenotypeIndex -- so only import lines are checked, not the whole
    # file's text.)
    import phenopred_phase2.traits.application.trait_engine as module

    with open(module.__file__, encoding="utf-8") as handle:
        import_lines = [
            line
            for line in handle
            if line.strip().startswith(("from ", "import "))
        ]

    joined_imports = "".join(import_lines)
    assert "DataRow" not in joined_imports
    assert "ColumnLayout" not in joined_imports


# ---------------------------------------------------------------------------
# End-to-end smoke test against the real registries and real models
# (a single, separate confirmation -- never the primary testing strategy)
# ---------------------------------------------------------------------------


def test_engine_runs_end_to_end_against_real_registries_and_real_models() -> None:
    from phenopred_phase2.traits.domain.trait_model_registry import (
        TRAIT_MODEL_REGISTRY,
    )
    from phenopred_phase2.traits.domain.trait_registry import TRAIT_REGISTRY

    # A real genotype source exposing exactly GenotypeIndex's own
    # public .get() surface, populated only with lactase persistence's
    # single required rsid -- every other real trait will therefore
    # legitimately resolve to INSUFFICIENT_DATA, which is expected and
    # asserted below, not treated as a failure.
    genotype_source = _FakeGenotypeSource({"rs4988235": _snp_call("AG")})

    engine = TraitEngine(TRAIT_REGISTRY, TRAIT_MODEL_REGISTRY)
    predictions = engine.run(genotype_source)

    assert set(predictions.keys()) == set(TRAIT_REGISTRY.keys())
    assert (
        predictions["lactase_persistence"].status == PredictionStatus.PREDICTED
    )
    assert (
        predictions["lactase_persistence"].predicted_phenotype
        == "lactase persistent"
    )
    assert predictions["eye_colour"].status == PredictionStatus.INSUFFICIENT_DATA
