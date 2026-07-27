# tests/traits/test_trait_registry.py
"""Unit tests for the Trait Contract Layer's TraitDefinition and trait
registry mechanism.

These are contract-level tests only, per the frozen "Trait Contract
Layer -- Frozen Architecture Specification v1": they verify
TraitDefinition's structural validation, build_trait_registry's
duplicate-detection behavior, and TRAIT_REGISTRY's immutability and
current (intentionally empty) content. They require no concrete
TraitModel, no TraitEngine, and no real trait entries -- mirroring the
same plain-function, no-test-class style already used in
test_snp_registry.py.
"""

from __future__ import annotations

import dataclasses

import pytest

from phenopred_phase2.traits.domain.entities import TraitDefinition
from phenopred_phase2.traits.domain.trait_registry import (
    TRAIT_REGISTRY,
    build_trait_registry,
)


def _make_definition(**overrides) -> TraitDefinition:
    fields = {
        "trait_id": "test_trait",
        "name": "Test Trait",
        "required_rsids": ("rs0000001",),
        "evidence_refs": ("Synthetic test citation.",),
    }
    fields.update(overrides)
    return TraitDefinition(**fields)


# ---------------------------------------------------------------------------
# TraitDefinition validation
# ---------------------------------------------------------------------------


def test_traitdefinition_constructs_with_all_fields_populated() -> None:
    definition = _make_definition()

    assert definition.trait_id == "test_trait"
    assert definition.name == "Test Trait"
    assert definition.required_rsids == ("rs0000001",)
    assert definition.evidence_refs == ("Synthetic test citation.",)


def test_traitdefinition_raises_when_trait_id_is_empty() -> None:
    with pytest.raises(ValueError):
        _make_definition(trait_id="")


def test_traitdefinition_raises_when_trait_id_is_whitespace_only() -> None:
    with pytest.raises(ValueError):
        _make_definition(trait_id="   ")


def test_traitdefinition_raises_when_name_is_empty() -> None:
    with pytest.raises(ValueError):
        _make_definition(name="")


def test_traitdefinition_raises_when_name_is_whitespace_only() -> None:
    with pytest.raises(ValueError):
        _make_definition(name="   ")


def test_traitdefinition_raises_when_required_rsids_is_empty() -> None:
    with pytest.raises(ValueError):
        _make_definition(required_rsids=())


def test_traitdefinition_does_not_raise_when_evidence_refs_is_empty() -> None:
    # evidence_refs has no non-empty requirement in the frozen
    # specification -- only trait_id, name, and required_rsids are
    # validated. This is a deliberate structural check, not an
    # oversight: a trait may be authored before its full citation trail
    # is assembled.
    definition = _make_definition(evidence_refs=())

    assert definition.evidence_refs == ()


# ---------------------------------------------------------------------------
# TraitDefinition immutability
# ---------------------------------------------------------------------------


def test_traitdefinition_is_frozen() -> None:
    definition = _make_definition()

    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.name = "Other Trait"  # type: ignore[misc]


def test_traitdefinition_has_no_model_reference() -> None:
    # Per the frozen Trait Contract Layer specification (Review Point
    # 2), TraitDefinition must never carry a model reference -- that
    # binding belongs to the composition root, not to this static
    # value object.
    definition = _make_definition()

    assert not hasattr(definition, "model")


# ---------------------------------------------------------------------------
# build_trait_registry: construction and duplicate handling
# ---------------------------------------------------------------------------


def test_build_trait_registry_indexes_definitions_by_trait_id() -> None:
    definition_a = _make_definition(trait_id="trait_a")
    definition_b = _make_definition(trait_id="trait_b")

    registry = build_trait_registry([definition_a, definition_b])

    assert registry["trait_a"] is definition_a
    assert registry["trait_b"] is definition_b
    assert len(registry) == 2


def test_build_trait_registry_raises_on_duplicate_trait_id() -> None:
    first = _make_definition(trait_id="trait_a", name="First")
    duplicate = _make_definition(trait_id="trait_a", name="Second")

    with pytest.raises(ValueError):
        build_trait_registry([first, duplicate])


def test_build_trait_registry_returns_immutable_mapping() -> None:
    registry = build_trait_registry([_make_definition(trait_id="trait_a")])

    with pytest.raises(TypeError):
        registry["trait_b"] = _make_definition(trait_id="trait_b")  # type: ignore[index]


def test_build_trait_registry_accepts_empty_sequence() -> None:
    registry = build_trait_registry([])

    assert len(registry) == 0


# ---------------------------------------------------------------------------
# TRAIT_REGISTRY: current static content
# ---------------------------------------------------------------------------


def test_trait_registry_contains_only_currently_implemented_traits() -> None:
    # Per the frozen specification, TRAIT_REGISTRY is populated
    # incrementally as each concrete TraitModel is authored. Only
    # lactase_persistence, earwax_type, actn3, bitter_taste, and
    # eye_colour exist so far; this test documents that fact so an
    # unexpected future population isn't silently unnoticed either
    # way.
    assert set(TRAIT_REGISTRY.keys()) == {
        "lactase_persistence",
        "earwax_type",
        "actn3",
        "bitter_taste",
        "eye_colour",
    }


def test_trait_registry_eye_colour_entry_has_expected_required_rsids() -> None:
    # Regression guard: confirms the six verified IrisPlex SNPs are
    # exactly the required_rsids for this trait.
    definition = TRAIT_REGISTRY.get("eye_colour")

    assert definition is not None
    assert definition.name == "Eye Colour (IrisPlex)"
    assert definition.required_rsids == (
        "rs12913832",
        "rs1800407",
        "rs12896399",
        "rs16891982",
        "rs1393350",
        "rs12203592",
    )


def test_trait_registry_lookup_of_unknown_trait_id_returns_none() -> None:
    # ALDH2 has no concrete TraitModel (and no TraitDefinition entry)
    # yet -- still a genuinely unknown trait_id.
    assert TRAIT_REGISTRY.get("aldh2") is None
    assert "aldh2" not in TRAIT_REGISTRY


def test_trait_registry_is_immutable() -> None:
    with pytest.raises(TypeError):
        TRAIT_REGISTRY["new_trait"] = _make_definition(  # type: ignore[index]
            trait_id="new_trait"
        )