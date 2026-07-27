# tests/traits/test_trait_model_registry.py
"""Unit tests for the Trait Model Registry.

The Trait Model Registry is a closed, static, read-only binding of
trait_id -> TraitModel instance -- the one missing resolution step
identified by the Trait Model Resolution Architecture review. This
suite verifies that contract directly: build_trait_model_registry's
duplicate-detection behavior, TRAIT_MODEL_REGISTRY's real static
content, correct model-class resolution per trait_id, safe unknown-key
lookup, immutability, and the architecture constraints this component
must never violate (no TraitDefinition data, no execution, no
biological interpretation). It follows the same plain-function,
no-test-class style already used in test_snp_registry.py and
test_trait_registry.py.
"""

from __future__ import annotations

import pytest

from phenopred_phase2.traits.domain.interfaces import TraitModel
from phenopred_phase2.traits.domain.models.actn3_model import ACTN3Model
from phenopred_phase2.traits.domain.models.bitter_taste_model import (
    BitterTasteModel,
)
from phenopred_phase2.traits.domain.models.earwax_type_model import (
    EarwaxTypeModel,
)
from phenopred_phase2.traits.domain.models.eye_colour_model import EyeColourModel
from phenopred_phase2.traits.domain.models.lactase_persistence_model import (
    LactasePersistenceModel,
)
from phenopred_phase2.traits.domain.trait_model_registry import (
    TRAIT_MODEL_REGISTRY,
    build_trait_model_registry,
)


class _FakeTraitModel:
    """A minimal fake TraitModel, used only to exercise
    build_trait_model_registry's own mechanics in isolation, without
    depending on any real trait model's biology.
    """

    def predict(self, genotype_calls):  # pragma: no cover - not exercised
        raise NotImplementedError


# ---------------------------------------------------------------------------
# build_trait_model_registry: construction and duplicate handling
# ---------------------------------------------------------------------------


def test_build_trait_model_registry_indexes_bindings_by_trait_id() -> None:
    model_a = _FakeTraitModel()
    model_b = _FakeTraitModel()

    registry = build_trait_model_registry(
        [("trait_a", model_a), ("trait_b", model_b)]
    )

    assert registry["trait_a"] is model_a
    assert registry["trait_b"] is model_b
    assert len(registry) == 2


def test_build_trait_model_registry_raises_on_duplicate_trait_id() -> None:
    first = _FakeTraitModel()
    duplicate = _FakeTraitModel()

    with pytest.raises(ValueError):
        build_trait_model_registry(
            [("trait_a", first), ("trait_a", duplicate)]
        )


def test_build_trait_model_registry_returns_immutable_mapping() -> None:
    registry = build_trait_model_registry([("trait_a", _FakeTraitModel())])

    with pytest.raises(TypeError):
        registry["trait_b"] = _FakeTraitModel()  # type: ignore[index]


def test_build_trait_model_registry_accepts_empty_sequence() -> None:
    registry = build_trait_model_registry([])

    assert len(registry) == 0


# ---------------------------------------------------------------------------
# TRAIT_MODEL_REGISTRY: all expected trait_ids exist
# ---------------------------------------------------------------------------


def test_trait_model_registry_contains_exactly_the_five_implemented_traits() -> (
    None
):
    # Mirrors TRAIT_REGISTRY's own five-trait content exactly -- an
    # unexpected future addition or omission should not be silently
    # unnoticed either way.
    assert set(TRAIT_MODEL_REGISTRY.keys()) == {
        "lactase_persistence",
        "earwax_type",
        "actn3",
        "bitter_taste",
        "eye_colour",
    }


# ---------------------------------------------------------------------------
# Each trait_id resolves to the correct model class
# ---------------------------------------------------------------------------


def test_lactase_persistence_resolves_to_lactase_persistence_model() -> None:
    model = TRAIT_MODEL_REGISTRY.get("lactase_persistence")

    assert model is not None
    assert isinstance(model, LactasePersistenceModel)


def test_earwax_type_resolves_to_earwax_type_model() -> None:
    model = TRAIT_MODEL_REGISTRY.get("earwax_type")

    assert model is not None
    assert isinstance(model, EarwaxTypeModel)


def test_actn3_resolves_to_actn3_model() -> None:
    model = TRAIT_MODEL_REGISTRY.get("actn3")

    assert model is not None
    assert isinstance(model, ACTN3Model)


def test_bitter_taste_resolves_to_bitter_taste_model() -> None:
    model = TRAIT_MODEL_REGISTRY.get("bitter_taste")

    assert model is not None
    assert isinstance(model, BitterTasteModel)


def test_eye_colour_resolves_to_eye_colour_model() -> None:
    model = TRAIT_MODEL_REGISTRY.get("eye_colour")

    assert model is not None
    assert isinstance(model, EyeColourModel)


def test_each_registered_model_satisfies_traitmodel_protocol() -> None:
    # TraitModel is a plain (non-runtime-checkable) Protocol per the
    # frozen Trait Contract Layer specification -- verified
    # structurally, matching the convention already established in
    # test_trait_model_contract.py and each model's own test file.
    assert hasattr(TraitModel, "predict")
    for model in TRAIT_MODEL_REGISTRY.values():
        assert callable(getattr(model, "predict", None))


# ---------------------------------------------------------------------------
# Unknown trait lookup behavior
# ---------------------------------------------------------------------------


def test_lookup_of_unknown_trait_id_returns_none() -> None:
    # ALDH2 has no concrete TraitModel yet -- a genuinely unbound
    # trait_id, mirroring TRAIT_REGISTRY.get()'s identical convention
    # for the same trait_id.
    assert TRAIT_MODEL_REGISTRY.get("aldh2") is None
    assert "aldh2" not in TRAIT_MODEL_REGISTRY


def test_lookup_of_empty_string_trait_id_returns_none() -> None:
    assert TRAIT_MODEL_REGISTRY.get("") is None


# ---------------------------------------------------------------------------
# Registry immutability
# ---------------------------------------------------------------------------


def test_trait_model_registry_is_immutable() -> None:
    with pytest.raises(TypeError):
        TRAIT_MODEL_REGISTRY["new_trait"] = _FakeTraitModel()  # type: ignore[index]


def test_trait_model_registry_entries_cannot_be_deleted() -> None:
    with pytest.raises(TypeError):
        del TRAIT_MODEL_REGISTRY["actn3"]  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Architecture constraints that must remain protected
# ---------------------------------------------------------------------------


def test_registry_values_are_traitmodel_instances_not_definitions() -> None:
    # This registry must never store TraitDefinition data (name,
    # required_rsids, evidence_refs) -- only TraitModel instances. A
    # TraitDefinition has no `predict` attribute, so this also guards
    # against an accidental future mix-up of the two registries.
    for model in TRAIT_MODEL_REGISTRY.values():
        assert not hasattr(model, "required_rsids")
        assert not hasattr(model, "evidence_refs")
        assert callable(getattr(model, "predict", None))


def test_registry_module_does_not_import_genotype_index_dependency() -> None:
    # This registry must have no knowledge of GenotypeIndex, DataRow,
    # or any file-level object -- verified by checking the module's
    # actual import statements only. (Explanatory prose in the module's
    # own docstring may legitimately mention these names when
    # describing what this component intentionally does NOT depend on
    # -- exactly as trait_registry.py's own docstring already does --
    # so only import lines are checked, not the whole file's text.)
    import phenopred_phase2.traits.domain.trait_model_registry as module

    module_source = module.__file__
    with open(module_source, encoding="utf-8") as handle:
        import_lines = [
            line
            for line in handle
            if line.strip().startswith(("from ", "import "))
        ]

    joined_imports = "".join(import_lines)
    assert "GenotypeIndex" not in joined_imports
    assert "DataRow" not in joined_imports
    assert "genotype_index" not in joined_imports


def test_registry_module_never_calls_predict() -> None:
    # This registry only constructs and stores TraitModel instances --
    # it must never itself invoke predict(), which is strictly an
    # execution responsibility owned by the future TraitEngine.
    import phenopred_phase2.traits.domain.trait_model_registry as module

    module_source = module.__file__
    with open(module_source, encoding="utf-8") as handle:
        contents = handle.read()

    assert ".predict(" not in contents


def test_registry_repeated_lookup_returns_the_same_instance() -> None:
    # The registry stores instances, not factories -- repeated lookups
    # must return the identical object, never a freshly-constructed one.
    first = TRAIT_MODEL_REGISTRY.get("actn3")
    second = TRAIT_MODEL_REGISTRY.get("actn3")

    assert first is second
