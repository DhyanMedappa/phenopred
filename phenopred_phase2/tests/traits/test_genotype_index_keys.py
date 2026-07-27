# tests/traits/test_genotype_index_keys.py
"""Unit tests for GenotypeIndex's new, additive .keys() method.

Per the approved Comparison Engine Final Design Specification, this is
the sole change made to a completed component -- a purely additive
enumeration capability required by concordance_calculator.py. This
suite tests only the new method; the rest of GenotypeIndex's behavior
is already covered by its own existing test suite, untouched here.

Uses the real V1 DataRow/ColumnLayout value objects directly, mirroring
the same pattern already established for GenotypeIndex's own existing
tests.
"""

from __future__ import annotations

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import ColumnLayout
from phenopred_phase2.traits.domain.genotype_index import GenotypeIndex

_MISSING_VALUE_TOKENS = ("--",)
_INDEL_TOKENS = ("DD", "II", "DI", "D", "I")
_SEX_MITOCHONDRIAL_LABELS = ("X", "Y", "MT")


def _make_index(data_rows, column_layout=None) -> GenotypeIndex:
    if column_layout is None:
        column_layout = ColumnLayout(
            rsid_column_index=0,
            chromosome_column_index=1,
            position_column_index=2,
            designated_column_indices=(3,),
        )
    return GenotypeIndex(
        data_rows=data_rows,
        column_layout=column_layout,
        missing_value_tokens=_MISSING_VALUE_TOKENS,
        indel_tokens=_INDEL_TOKENS,
        sex_mitochondrial_labels=_SEX_MITOCHONDRIAL_LABELS,
    )


def test_keys_returns_every_rsid_the_index_holds() -> None:
    rows = [
        DataRow(line_index=0, fields=("rs1", "1", "100", "GA")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "CC")),
    ]
    index = _make_index(rows)

    assert set(index.keys()) == {"rs1", "rs2"}


def test_keys_is_empty_for_an_empty_index() -> None:
    index = _make_index([])

    assert set(index.keys()) == set()


def test_keys_length_matches_len_of_index() -> None:
    rows = [
        DataRow(line_index=0, fields=("rs1", "1", "100", "GA")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "CC")),
        DataRow(line_index=2, fields=("rs3", "1", "300", "TT")),
    ]
    index = _make_index(rows)

    assert len(index.keys()) == len(index)


def test_keys_excludes_duplicate_rsid_only_once() -> None:
    rows = [
        DataRow(line_index=0, fields=("rs1", "1", "100", "GA")),
        DataRow(line_index=1, fields=("rs1", "1", "100", "--")),
    ]
    index = _make_index(rows)

    assert list(index.keys()) == ["rs1"]


def test_keys_supports_set_intersection_for_comparison_use_case() -> None:
    # This is the exact operation concordance_calculator.py performs:
    # set(index_a.keys()) & set(index_b.keys()).
    rows_a = [
        DataRow(line_index=0, fields=("rs1", "1", "100", "GA")),
        DataRow(line_index=1, fields=("rs2", "1", "200", "CC")),
    ]
    rows_b = [
        DataRow(line_index=0, fields=("rs2", "1", "200", "CC")),
        DataRow(line_index=1, fields=("rs3", "1", "300", "TT")),
    ]
    index_a = _make_index(rows_a)
    index_b = _make_index(rows_b)

    shared = set(index_a.keys()) & set(index_b.keys())

    assert shared == {"rs2"}


def test_existing_public_members_are_unchanged_except_for_the_new_keys_method() -> (
    None
):
    # Regression guard: confirms this change is purely additive -- the
    # only new public member is `keys`; every previously-existing
    # public member remains present.
    index = _make_index([])

    public_members = {name for name in dir(index) if not name.startswith("_")}

    assert public_members == {"get", "keys"}
