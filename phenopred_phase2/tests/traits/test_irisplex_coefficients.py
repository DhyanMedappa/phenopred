# tests/traits/test_irisplex_coefficients.py
"""Unit tests for the IrisPlex coefficient registry.

Mirrors test_snp_registry.py's own style: structural validation,
duplicate-detection behavior, and real static-content checks.
"""

from __future__ import annotations

import dataclasses

import pytest

from phenopred_phase2.traits.domain.irisplex_coefficients import (
    ALPHA_BLUE,
    ALPHA_OTHER,
    IRISPLEX_COEFFICIENTS,
    IrisPlexCoefficient,
    build_irisplex_coefficients,
)

_REQUIRED_FIELDS = ("rsid", "counted_allele", "citation")


def _make_record(**overrides) -> IrisPlexCoefficient:
    fields = {
        "rsid": "rs0000001",
        "counted_allele": "A",
        "beta_blue": 0.0,
        "beta_other": 0.0,
        "citation": "Synthetic test citation.",
    }
    fields.update(overrides)
    return IrisPlexCoefficient(**fields)


# ---------------------------------------------------------------------------
# IrisPlexCoefficient validation
# ---------------------------------------------------------------------------


def test_irisplex_coefficient_constructs_with_all_fields_populated() -> None:
    record = _make_record()

    assert record.rsid == "rs0000001"
    assert record.counted_allele == "A"


@pytest.mark.parametrize("field_name", _REQUIRED_FIELDS)
def test_irisplex_coefficient_raises_when_a_required_field_is_empty(
    field_name: str,
) -> None:
    with pytest.raises(ValueError):
        _make_record(**{field_name: ""})


@pytest.mark.parametrize("field_name", _REQUIRED_FIELDS)
def test_irisplex_coefficient_raises_when_a_required_field_is_whitespace_only(
    field_name: str,
) -> None:
    with pytest.raises(ValueError):
        _make_record(**{field_name: "   "})


def test_irisplex_coefficient_is_frozen() -> None:
    record = _make_record()

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.counted_allele = "G"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# build_irisplex_coefficients: construction and duplicate handling
# ---------------------------------------------------------------------------


def test_build_irisplex_coefficients_indexes_records_by_rsid() -> None:
    record_a = _make_record(rsid="rs0000001")
    record_b = _make_record(rsid="rs0000002")

    registry = build_irisplex_coefficients([record_a, record_b])

    assert registry["rs0000001"] is record_a
    assert registry["rs0000002"] is record_b
    assert len(registry) == 2


def test_build_irisplex_coefficients_raises_on_duplicate_rsid() -> None:
    first = _make_record(rsid="rs0000001", counted_allele="A")
    duplicate = _make_record(rsid="rs0000001", counted_allele="G")

    with pytest.raises(ValueError):
        build_irisplex_coefficients([first, duplicate])


def test_build_irisplex_coefficients_returns_immutable_mapping() -> None:
    registry = build_irisplex_coefficients([_make_record(rsid="rs0000001")])

    with pytest.raises(TypeError):
        registry["rs0000002"] = _make_record(rsid="rs0000002")  # type: ignore[index]


# ---------------------------------------------------------------------------
# IRISPLEX_COEFFICIENTS: real static content
# ---------------------------------------------------------------------------


def test_irisplex_coefficients_contains_no_duplicate_rsids() -> None:
    for rsid, record in IRISPLEX_COEFFICIENTS.items():
        assert record.rsid == rsid


def test_irisplex_coefficients_entries_have_all_fields_populated() -> None:
    for record in IRISPLEX_COEFFICIENTS.values():
        for field_name in _REQUIRED_FIELDS:
            assert getattr(record, field_name) != ""
        assert isinstance(record.beta_blue, float)
        assert isinstance(record.beta_other, float)


def test_irisplex_coefficients_contains_exactly_the_six_required_snps() -> None:
    assert set(IRISPLEX_COEFFICIENTS.keys()) == {
        "rs12913832",
        "rs1800407",
        "rs12896399",
        "rs16891982",
        "rs1393350",
        "rs12203592",
    }


def test_irisplex_coefficients_rs12913832_entry_has_expected_values() -> None:
    record = IRISPLEX_COEFFICIENTS.get("rs12913832")

    assert record is not None
    assert record.counted_allele == "A"
    assert record.beta_blue == -4.81
    assert record.beta_other == -1.79


def test_irisplex_coefficients_rs1800407_entry_has_expected_values() -> None:
    record = IRISPLEX_COEFFICIENTS.get("rs1800407")

    assert record is not None
    assert record.counted_allele == "T"
    assert record.beta_blue == 1.4
    assert record.beta_other == 0.87


def test_irisplex_coefficients_rs12896399_entry_has_expected_values() -> None:
    record = IRISPLEX_COEFFICIENTS.get("rs12896399")

    assert record is not None
    assert record.counted_allele == "G"
    assert record.beta_blue == -0.58
    assert record.beta_other == -0.03


def test_irisplex_coefficients_rs16891982_entry_has_expected_values() -> None:
    record = IRISPLEX_COEFFICIENTS.get("rs16891982")

    assert record is not None
    assert record.counted_allele == "C"
    assert record.beta_blue == -1.3
    assert record.beta_other == -0.5


def test_irisplex_coefficients_rs1393350_entry_has_expected_values_and_caveat() -> (
    None
):
    record = IRISPLEX_COEFFICIENTS.get("rs1393350")

    assert record is not None
    assert record.counted_allele == "A"
    assert record.beta_blue == 0.47
    assert record.beta_other == 0.27
    # This is the one SNP with a disclosed, unresolved provenance
    # caveat -- confirm it is actually documented, not silently omitted.
    assert "UNRESOLVED" in record.citation


def test_irisplex_coefficients_rs12203592_entry_has_expected_values() -> None:
    record = IRISPLEX_COEFFICIENTS.get("rs12203592")

    assert record is not None
    assert record.counted_allele == "T"
    assert record.beta_blue == 0.7
    assert record.beta_other == 0.73


def test_irisplex_coefficients_lookup_of_unknown_rsid_returns_none() -> None:
    assert IRISPLEX_COEFFICIENTS.get("rs_not_registered") is None
    assert "rs_not_registered" not in IRISPLEX_COEFFICIENTS


def test_irisplex_coefficients_is_immutable() -> None:
    with pytest.raises(TypeError):
        IRISPLEX_COEFFICIENTS["rs_new"] = _make_record(rsid="rs_new")  # type: ignore[index]


# ---------------------------------------------------------------------------
# Intercepts
# ---------------------------------------------------------------------------


def test_alpha_blue_and_alpha_other_have_expected_values() -> None:
    assert ALPHA_BLUE == 3.94
    assert ALPHA_OTHER == 0.65