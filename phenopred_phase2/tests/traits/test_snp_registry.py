# tests/traits/test_snp_registry.py
"""Unit tests for SNP Registry.

SNP Registry is a closed, static, read-only knowledge source with no
external dependencies and no computation beyond building an immutable
RSID-keyed mapping once at module load. This suite verifies the frozen
"SNP Registry -- Final Frozen Architecture Specification (v2)" contract
directly: SNPRecord's structural validation, build_registry's
duplicate-detection behavior, SNP_REGISTRY's real static content, and
the read-only nature of both. It follows the same plain-function,
no-test-class style used in test_genotype_index.py.
"""

from __future__ import annotations

import dataclasses

import pytest

from phenopred_phase2.traits.domain.snp_registry import (
    SNP_REGISTRY,
    SNPRecord,
    build_registry,
)

_REQUIRED_FIELDS = (
    "rsid",
    "gene",
    "reference_allele",
    "alternate_allele",
    "phenotype_associated_allele",
    "citation",
)


def _make_record(**overrides) -> SNPRecord:
    fields = {
        "rsid": "rs0000001",
        "gene": "TESTGENE",
        "reference_allele": "A",
        "alternate_allele": "G",
        "phenotype_associated_allele": "A",
        "citation": "Synthetic test citation.",
    }
    fields.update(overrides)
    return SNPRecord(**fields)


# ---------------------------------------------------------------------------
# SNPRecord validation
# ---------------------------------------------------------------------------


def test_snprecord_constructs_with_all_fields_populated() -> None:
    record = _make_record()

    assert record.rsid == "rs0000001"
    assert record.gene == "TESTGENE"


@pytest.mark.parametrize("field_name", _REQUIRED_FIELDS)
def test_snprecord_raises_when_a_required_field_is_empty(field_name: str) -> None:
    with pytest.raises(ValueError):
        _make_record(**{field_name: ""})


@pytest.mark.parametrize("field_name", _REQUIRED_FIELDS)
def test_snprecord_raises_when_a_required_field_is_whitespace_only(
    field_name: str,
) -> None:
    with pytest.raises(ValueError):
        _make_record(**{field_name: "   "})


# ---------------------------------------------------------------------------
# SNPRecord immutability
# ---------------------------------------------------------------------------


def test_snprecord_is_frozen() -> None:
    record = _make_record()

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.gene = "OTHERGENE"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# build_registry: construction and duplicate handling
# ---------------------------------------------------------------------------


def test_build_registry_indexes_records_by_rsid() -> None:
    record_a = _make_record(rsid="rs0000001")
    record_b = _make_record(rsid="rs0000002")

    registry = build_registry([record_a, record_b])

    assert registry["rs0000001"] is record_a
    assert registry["rs0000002"] is record_b
    assert len(registry) == 2


def test_build_registry_raises_on_duplicate_rsid() -> None:
    first = _make_record(rsid="rs0000001", gene="GENE_A")
    duplicate = _make_record(rsid="rs0000001", gene="GENE_B")

    with pytest.raises(ValueError):
        build_registry([first, duplicate])


def test_build_registry_returns_immutable_mapping() -> None:
    registry = build_registry([_make_record(rsid="rs0000001")])

    with pytest.raises(TypeError):
        registry["rs0000002"] = _make_record(rsid="rs0000002")  # type: ignore[index]


# ---------------------------------------------------------------------------
# SNP_REGISTRY: real static content
# ---------------------------------------------------------------------------


def test_snp_registry_contains_no_duplicate_rsids() -> None:
    # SNP_REGISTRY already succeeded in building at import time (which
    # itself proves no duplicates exist, since build_registry would have
    # raised) -- this test additionally confirms every key matches its
    # own record's rsid, as a direct content-consistency check.
    for rsid, record in SNP_REGISTRY.items():
        assert record.rsid == rsid


def test_snp_registry_entries_have_all_fields_populated() -> None:
    for record in SNP_REGISTRY.values():
        for field_name in _REQUIRED_FIELDS:
            assert getattr(record, field_name) != ""


def test_snp_registry_lookup_of_known_rsid_returns_expected_record() -> None:
    record = SNP_REGISTRY.get("rs4988235")

    assert record is not None
    assert record.gene == "LCT"
    assert record.reference_allele == "G"
    assert record.alternate_allele == "A"


def test_snp_registry_earwax_entry_has_expected_values() -> None:
    # Regression guard: this entry is already-verified static data
    # (Blueprint Section 9.3); an accidental future edit corrupting it
    # should be caught immediately, not silently.
    record = SNP_REGISTRY.get("rs17822931")

    assert record is not None
    assert record.gene == "ABCC11"
    assert record.reference_allele == "C"
    assert record.alternate_allele == "T"
    assert record.phenotype_associated_allele == "C"


def test_snp_registry_actn3_entry_has_expected_values() -> None:
    # Regression guard, same rationale as the earwax entry above.
    record = SNP_REGISTRY.get("rs1815739")

    assert record is not None
    assert record.gene == "ACTN3"
    assert record.reference_allele == "C"
    assert record.alternate_allele == "T"
    assert record.phenotype_associated_allele == "C"


def test_snp_registry_bitter_taste_rs713598_entry_has_expected_values() -> None:
    # Regression guard: this entry resolves the one item carried into
    # Blueprint Section 20 (TAS2R38 strand-convention verification),
    # verified directly against dbSNP/ClinVar per that section.
    record = SNP_REGISTRY.get("rs713598")

    assert record is not None
    assert record.gene == "TAS2R38"
    assert record.reference_allele == "C"
    assert record.alternate_allele == "G"
    assert record.phenotype_associated_allele == "G"


def test_snp_registry_bitter_taste_rs1726866_entry_has_expected_values() -> None:
    record = SNP_REGISTRY.get("rs1726866")

    assert record is not None
    assert record.gene == "TAS2R38"
    assert record.reference_allele == "G"
    assert record.alternate_allele == "A"
    assert record.phenotype_associated_allele == "G"


def test_snp_registry_bitter_taste_rs10246939_entry_has_expected_values() -> None:
    record = SNP_REGISTRY.get("rs10246939")

    assert record is not None
    assert record.gene == "TAS2R38"
    assert record.reference_allele == "T"
    assert record.alternate_allele == "C"
    assert record.phenotype_associated_allele == "C"


def test_snp_registry_iris_plex_rs12913832_entry_has_expected_values() -> None:
    # Regression guard: HERC2 is a minus-strand gene; this entry's
    # values are the confirmed GRCh37 forward-strand representation.
    record = SNP_REGISTRY.get("rs12913832")

    assert record is not None
    assert record.gene == "HERC2"
    assert record.reference_allele == "A"
    assert record.alternate_allele == "G"
    assert record.phenotype_associated_allele == "G"


def test_snp_registry_iris_plex_rs1800407_entry_has_expected_values() -> None:
    record = SNP_REGISTRY.get("rs1800407")

    assert record is not None
    assert record.gene == "OCA2"
    assert record.reference_allele == "G"
    assert record.alternate_allele == "A"
    assert record.phenotype_associated_allele == "A"


def test_snp_registry_iris_plex_rs12896399_entry_has_expected_values() -> None:
    record = SNP_REGISTRY.get("rs12896399")

    assert record is not None
    assert record.gene == "SLC24A4"
    assert record.reference_allele == "G"
    assert record.alternate_allele == "T"
    assert record.phenotype_associated_allele == "T"


def test_snp_registry_iris_plex_rs16891982_entry_has_expected_values() -> None:
    # Regression guard: SLC45A2 is a minus-strand gene; this entry's
    # values are the confirmed GRCh37 forward-strand representation,
    # which was independently verified to coincide with (not require
    # reverse-complementing from) the widely-cited coding-strand C>G
    # notation.
    record = SNP_REGISTRY.get("rs16891982")

    assert record is not None
    assert record.gene == "SLC45A2"
    assert record.reference_allele == "C"
    assert record.alternate_allele == "G"
    assert record.phenotype_associated_allele == "G"


def test_snp_registry_iris_plex_rs1393350_entry_has_expected_values() -> None:
    record = SNP_REGISTRY.get("rs1393350")

    assert record is not None
    assert record.gene == "TYR"
    assert record.reference_allele == "G"
    assert record.alternate_allele == "A"
    assert record.phenotype_associated_allele == "G"


def test_snp_registry_iris_plex_rs12203592_entry_has_expected_values() -> None:
    record = SNP_REGISTRY.get("rs12203592")

    assert record is not None
    assert record.gene == "IRF4"
    assert record.reference_allele == "C"
    assert record.alternate_allele == "T"
    assert record.phenotype_associated_allele == "T"


def test_snp_registry_contains_all_twelve_verified_snps() -> None:
    # Documents the current, complete verified content: the 3 original
    # (Section 9.3), 3 TAS2R38, and 6 IrisPlex entries -- so an
    # unexpected future addition or omission isn't silently unnoticed.
    assert set(SNP_REGISTRY.keys()) == {
        "rs4988235",
        "rs17822931",
        "rs1815739",
        "rs713598",
        "rs1726866",
        "rs10246939",
        "rs12913832",
        "rs1800407",
        "rs12896399",
        "rs16891982",
        "rs1393350",
        "rs12203592",
    }


def test_snp_registry_lookup_of_unknown_rsid_returns_none() -> None:
    assert SNP_REGISTRY.get("rs_not_registered") is None
    assert "rs_not_registered" not in SNP_REGISTRY


def test_snp_registry_is_immutable() -> None:
    with pytest.raises(TypeError):
        SNP_REGISTRY["rs_new"] = _make_record(rsid="rs_new")  # type: ignore[index]