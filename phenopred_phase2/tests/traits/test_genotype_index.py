# tests/traits/test_genotype_index.py
"""Unit tests for GenotypeIndex.

GenotypeIndex builds a per-file RSID -> GenotypeCall lookup from V1's
already-resolved DataRow/ColumnLayout outputs. This suite verifies the
frozen "GenotypeIndex -- Final Design Specification" contract directly:
layout-kind derivation, all classification rules (single-column-genotype
and two-column-allele), duplicate-RSID handling, out-of-bounds row
handling, and the read-only public API. It uses the real V1 `DataRow`
and `ColumnLayout` value objects directly (both are plain,
dependency-free data carriers with no I/O), following the same pattern
already used in `test_profile_file_use_case.py` for `HeaderInfo`/
`ColumnLayout`.
"""

from __future__ import annotations

import dataclasses

import pytest

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import ColumnLayout
from phenopred_phase2.traits.domain.entities import GenotypeCall, GenotypeCallKind
from phenopred_phase2.traits.domain.genotype_index import GenotypeIndex

_MISSING_VALUE_TOKENS = ("--",)
_INDEL_TOKENS = ("DD", "II", "DI", "D", "I")
_SEX_MITOCHONDRIAL_LABELS = ("X", "Y", "MT")


def _make_index(
    data_rows,
    column_layout,
    missing_value_tokens=_MISSING_VALUE_TOKENS,
    indel_tokens=_INDEL_TOKENS,
    sex_mitochondrial_labels=_SEX_MITOCHONDRIAL_LABELS,
) -> GenotypeIndex:
    return GenotypeIndex(
        data_rows=data_rows,
        column_layout=column_layout,
        missing_value_tokens=missing_value_tokens,
        indel_tokens=indel_tokens,
        sex_mitochondrial_labels=sex_mitochondrial_labels,
    )


def _single_column_layout(designated_index=3) -> ColumnLayout:
    return ColumnLayout(
        rsid_column_index=0,
        chromosome_column_index=1,
        position_column_index=2,
        designated_column_indices=(designated_index,),
    )


def _two_column_layout(index_a=3, index_b=4) -> ColumnLayout:
    return ColumnLayout(
        rsid_column_index=0,
        chromosome_column_index=1,
        position_column_index=2,
        designated_column_indices=(index_a, index_b),
    )


def _undetermined_layout() -> ColumnLayout:
    return ColumnLayout(
        rsid_column_index=0,
        chromosome_column_index=1,
        position_column_index=2,
        designated_column_indices=(),
    )


# ---------------------------------------------------------------------------
# Single-column-genotype layout: classification rules
# ---------------------------------------------------------------------------


def test_single_column_snp_genotype_is_canonicalized() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "GA"))
    index = _make_index([row], _single_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.SNP
    assert call.alleles == "AG"
    assert call.allele is None
    assert call.raw_value == "GA"


def test_single_column_no_call() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "--"))
    index = _make_index([row], _single_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.NO_CALL
    assert call.alleles is None
    assert call.raw_value == "--"


def test_single_column_indel() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "DD"))
    index = _make_index([row], _single_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.INDEL
    assert call.raw_value == "DD"


def test_single_column_haploid_on_configured_sex_mitochondrial_label() -> None:
    row = DataRow(line_index=0, fields=("rs1", "X", "100", "A"))
    index = _make_index([row], _single_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.HAPLOID
    assert call.allele == "A"
    assert call.alleles is None
    assert call.raw_value == "A"


def test_single_column_length_one_on_non_sex_mitochondrial_label_is_unrecognized() -> (
    None
):
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "A"))
    index = _make_index([row], _single_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.UNRECOGNIZED
    assert call.raw_value == "A"


def test_single_column_unrecognized_length_is_unrecognized() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "AAA"))
    index = _make_index([row], _single_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.UNRECOGNIZED
    assert call.raw_value == "AAA"


def test_single_column_empty_string_is_unrecognized_when_not_a_missing_token() -> (
    None
):
    row = DataRow(line_index=0, fields=("rs1", "1", "100", ""))
    index = _make_index(
        [row], _single_column_layout(), missing_value_tokens=("--",)
    )

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.UNRECOGNIZED
    assert call.raw_value == ""


# ---------------------------------------------------------------------------
# Two-column-allele layout: classification rules
# ---------------------------------------------------------------------------


def test_two_column_snp_genotype_is_canonicalized() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "G", "A"))
    index = _make_index([row], _two_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.SNP
    assert call.alleles == "AG"
    assert call.raw_value == "G/A"


def test_two_column_allele_order_normalizes_symmetrically() -> None:
    row_ga = DataRow(line_index=0, fields=("rs1", "1", "100", "G", "A"))
    row_ag = DataRow(line_index=0, fields=("rs1", "1", "100", "A", "G"))

    call_ga = _make_index([row_ga], _two_column_layout()).get("rs1")
    call_ag = _make_index([row_ag], _two_column_layout()).get("rs1")

    assert call_ga.alleles == call_ag.alleles == "AG"


def test_two_column_no_call_when_either_field_is_a_missing_token() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "--", "A"))
    index = _make_index([row], _two_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.NO_CALL
    assert call.raw_value == "--/A"


def test_two_column_indel_when_either_field_is_an_indel_token() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "D", "A"))
    index = _make_index([row], _two_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.INDEL
    assert call.raw_value == "D/A"


def test_two_column_unrecognized_when_a_field_is_not_length_one() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "AG", "A"))
    index = _make_index([row], _two_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.UNRECOGNIZED
    assert call.raw_value == "AG/A"


# ---------------------------------------------------------------------------
# Undetermined layout
# ---------------------------------------------------------------------------


def test_undetermined_layout_yields_unrecognized_for_every_row_and_never_raises() -> (
    None
):
    rows = [
        DataRow(line_index=0, fields=("rs1", "1", "100")),
        DataRow(line_index=1, fields=("rs2", "2", "200")),
    ]
    index = _make_index(rows, _undetermined_layout())

    call_1 = index.get("rs1")
    call_2 = index.get("rs2")

    assert call_1.kind == GenotypeCallKind.UNRECOGNIZED
    assert call_1.raw_value is None
    assert call_2.kind == GenotypeCallKind.UNRECOGNIZED
    assert call_2.raw_value is None


# ---------------------------------------------------------------------------
# Duplicate RSID handling
# ---------------------------------------------------------------------------


def test_duplicate_rsid_first_occurrence_wins() -> None:
    first_row = DataRow(line_index=0, fields=("rs1", "1", "100", "GA"))
    second_row = DataRow(line_index=1, fields=("rs1", "1", "100", "--"))
    index = _make_index([first_row, second_row], _single_column_layout())

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.SNP
    assert call.alleles == "AG"
    assert len(index) == 1


# ---------------------------------------------------------------------------
# RSID lookup
# ---------------------------------------------------------------------------


def test_get_returns_none_for_rsid_not_present_in_file() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "GA"))
    index = _make_index([row], _single_column_layout())

    assert index.get("rs_not_present") is None
    assert "rs_not_present" not in index


def test_contains_and_len_reflect_indexed_rsids() -> None:
    rows = [
        DataRow(line_index=0, fields=("rs1", "1", "100", "GA")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "CC")),
    ]
    index = _make_index(rows, _single_column_layout())

    assert "rs1" in index
    assert "rs2" in index
    assert len(index) == 2


# ---------------------------------------------------------------------------
# Out-of-bounds handling
# ---------------------------------------------------------------------------


def test_out_of_bounds_rsid_column_index_row_contributes_no_entry() -> None:
    empty_row = DataRow(line_index=0, fields=())
    normal_row = DataRow(line_index=1, fields=("rs1", "1", "100", "GA"))
    index = _make_index([empty_row, normal_row], _single_column_layout())

    assert len(index) == 1
    assert index.get("rs1").kind == GenotypeCallKind.SNP


def test_out_of_bounds_designated_column_index_is_unrecognized_with_no_value() -> (
    None
):
    row = DataRow(line_index=0, fields=("rs1", "1", "100"))
    index = _make_index([row], _single_column_layout(designated_index=3))

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.UNRECOGNIZED
    assert call.raw_value is None


def test_out_of_bounds_chromosome_column_index_is_unrecognized_not_haploid() -> (
    None
):
    row = DataRow(line_index=0, fields=("rs1", "100", "A"))
    layout = ColumnLayout(
        rsid_column_index=0,
        chromosome_column_index=5,
        position_column_index=1,
        designated_column_indices=(2,),
    )
    index = _make_index([row], layout)

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.UNRECOGNIZED
    assert call.raw_value == "A"


def test_out_of_bounds_two_column_index_is_unrecognized_with_no_value() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "A"))
    index = _make_index([row], _two_column_layout(index_a=3, index_b=4))

    call = index.get("rs1")

    assert call.kind == GenotypeCallKind.UNRECOGNIZED
    assert call.raw_value is None


# ---------------------------------------------------------------------------
# Immutability / no mutation surface
# ---------------------------------------------------------------------------


def test_genotype_call_is_frozen() -> None:
    call = GenotypeCall(kind=GenotypeCallKind.SNP, alleles="AG", allele=None, raw_value="AG")

    with pytest.raises(dataclasses.FrozenInstanceError):
        call.alleles = "GA"  # type: ignore[misc]


def test_genotype_index_exposes_no_mutation_method() -> None:
    row = DataRow(line_index=0, fields=("rs1", "1", "100", "GA"))
    index = _make_index([row], _single_column_layout())

    public_members = {
        name for name in dir(index) if not name.startswith("_")
    }

    assert public_members == {"get", "keys"}
