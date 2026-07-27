# tests/traits/test_composition.py
"""Unit tests for the Phase 2 orchestration/composition layer
(build_genotype_index, run_trait_pipeline).

These are isolated unit tests only: every input is a hand-built fake
-- a plain dict standing in for ProfileFileUseCase's result, and
fake DataRow/ColumnLayout-shaped values built directly from
GenotypeIndex's own real domain types (GenotypeCall's building blocks
live in phenopred_phase2, so real DataRow/ColumnLayout are not
required here; only the two keys this module actually reads --
"data_rows" and "column_layout" -- need to be present and of the
correct shape). No real V1 module is imported anywhere in this file;
that boundary is covered separately by the end-to-end integration
test. This mirrors the fake-based testing style already established
throughout this project (test_trait_model_contract.py,
test_trait_engine.py).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from phenopred_phase2.traits.application.composition import (
    DEFAULT_INDEL_TOKENS,
    DEFAULT_MISSING_VALUE_TOKENS,
    DEFAULT_SEX_MITOCHONDRIAL_LABELS,
    build_genotype_index,
    run_trait_pipeline,
)
from phenopred_phase2.traits.domain.entities import PredictionStatus
from phenopred_phase2.traits.domain.genotype_index import GenotypeIndex
from phenopred_phase2.traits.domain.trait_registry import TRAIT_REGISTRY


class _FakeDataRow:
    """A minimal stand-in for V1's real DataRow -- exposes only the
    two attributes GenotypeIndex actually reads (line_index, fields),
    so this test suite never needs to import any real V1 module.
    """

    def __init__(self, line_index: int, fields: tuple[str, ...]) -> None:
        self.line_index = line_index
        self.fields = fields


class _FakeColumnLayout:
    """A minimal stand-in for V1's real ColumnLayout -- exposes only
    the four attributes GenotypeIndex actually reads.
    """

    def __init__(
        self,
        rsid_column_index: int,
        chromosome_column_index: int,
        position_column_index: int,
        designated_column_indices: tuple[int, ...],
    ) -> None:
        self.rsid_column_index = rsid_column_index
        self.chromosome_column_index = chromosome_column_index
        self.position_column_index = position_column_index
        self.designated_column_indices = designated_column_indices


def _fake_profile_result(
    rows: Sequence[tuple[str, ...]],
    designated_column_indices: tuple[int, ...] = (3,),
) -> dict:
    """Build a minimal fake dict shaped like
    ProfileFileUseCase.execute()'s real return value -- only the two
    keys this module actually reads are populated; every other real
    key (findings, profiles, report, ...) is deliberately omitted to
    prove this module never touches them.
    """
    data_rows = tuple(
        _FakeDataRow(line_index=i, fields=fields) for i, fields in enumerate(rows)
    )
    column_layout = _FakeColumnLayout(
        rsid_column_index=0,
        chromosome_column_index=1,
        position_column_index=2,
        designated_column_indices=designated_column_indices,
    )
    return {"data_rows": data_rows, "column_layout": column_layout}


# ---------------------------------------------------------------------------
# build_genotype_index: correct construction
# ---------------------------------------------------------------------------


def test_build_genotype_index_constructs_from_fake_profile_result() -> None:
    profile_result = _fake_profile_result([("rs1", "1", "100", "AG")])

    index = build_genotype_index(profile_result)

    assert isinstance(index, GenotypeIndex)
    assert len(index) == 1
    call = index.get("rs1")
    assert call is not None
    assert call.alleles == "AG"


def test_build_genotype_index_only_reads_data_rows_and_column_layout_keys() -> (
    None
):
    # Every other real ProfileFileUseCase key (findings, profiles,
    # report, skipped_quality_checks, ...) is absent from this fake
    # result -- construction must still succeed, proving this module
    # never touches them.
    profile_result = _fake_profile_result([("rs1", "1", "100", "AG")])
    assert set(profile_result.keys()) == {"data_rows", "column_layout"}

    index = build_genotype_index(profile_result)

    assert index.get("rs1") is not None


# ---------------------------------------------------------------------------
# Configuration injection and overrides
# ---------------------------------------------------------------------------


def test_default_missing_value_tokens_classifies_both_real_no_call_conventions() -> (
    None
):
    # "--" (anonymous_genome_v5_build37.txt's convention) and "0"
    # (AncestryDNA.txt's real, undocumented convention) must both be
    # recognized by the default configuration.
    profile_result = _fake_profile_result(
        [("rs1", "1", "100", "--"), ("rs2", "1", "200", "0")]
    )

    index = build_genotype_index(profile_result)

    assert index.get("rs1").kind.value == "no_call"
    assert index.get("rs2").kind.value == "no_call"


def test_default_indel_tokens_classifies_both_real_indel_conventions() -> None:
    # "DD" (anonymous_genome_v5_build37.txt's convention) and "D"
    # (AncestryDNA.txt's real per-column convention) must both be
    # recognized by the default configuration.
    profile_result = _fake_profile_result(
        [("rs1", "1", "100", "DD"), ("rs2", "1", "200", "D")]
    )

    index = build_genotype_index(profile_result)

    assert index.get("rs1").kind.value == "indel"
    assert index.get("rs2").kind.value == "indel"


def test_configuration_can_be_overridden_for_a_future_provider_convention() -> (
    None
):
    # A hypothetical future provider using "NULL" as its own no-call
    # token, unsupported by the current defaults, must be fully
    # configurable without any change to GenotypeIndex or this module.
    profile_result = _fake_profile_result([("rs1", "1", "100", "NULL")])

    index_with_default_config = build_genotype_index(profile_result)
    assert index_with_default_config.get("rs1").kind.value != "no_call"

    index_with_override = build_genotype_index(
        profile_result, missing_value_tokens=("NULL",)
    )
    assert index_with_override.get("rs1").kind.value == "no_call"


def test_default_constants_are_the_documented_evidence_based_values() -> None:
    assert DEFAULT_MISSING_VALUE_TOKENS == ("--", "0")
    assert DEFAULT_INDEL_TOKENS == ("D", "I", "DD", "II", "DI")
    assert DEFAULT_SEX_MITOCHONDRIAL_LABELS == ("X", "Y", "MT")


def test_sex_mitochondrial_labels_override_affects_haploid_classification() -> (
    None
):
    profile_result = _fake_profile_result(
        [("rs1", "CUSTOM_MT", "100", "A")]
    )

    index_default = build_genotype_index(profile_result)
    assert index_default.get("rs1").kind.value != "haploid"

    index_override = build_genotype_index(
        profile_result, sex_mitochondrial_labels=("CUSTOM_MT",)
    )
    assert index_override.get("rs1").kind.value == "haploid"


# ---------------------------------------------------------------------------
# run_trait_pipeline: TraitEngine execution and returned mapping
# ---------------------------------------------------------------------------


def test_run_trait_pipeline_returns_prediction_for_every_registered_trait() -> (
    None
):
    # An essentially-empty fake file: no real trait's required rsids
    # are present, so every trait legitimately resolves to
    # INSUFFICIENT_DATA -- still proving every registered trait_id is
    # processed, none silently dropped.
    profile_result = _fake_profile_result([("rs_unrelated", "1", "100", "AG")])

    predictions = run_trait_pipeline(profile_result)

    assert isinstance(predictions, Mapping)
    assert set(predictions.keys()) == set(TRAIT_REGISTRY.keys())
    for prediction in predictions.values():
        assert prediction.status == PredictionStatus.INSUFFICIENT_DATA


def test_run_trait_pipeline_produces_a_real_prediction_when_data_present() -> (
    None
):
    # rs4988235 is lactase_persistence's single required rsid; "AG"
    # (heterozygous, associated allele present) is a real, documented
    # PREDICTED case for that model.
    profile_result = _fake_profile_result(
        [("rs4988235", "2", "136608646", "AG")]
    )

    predictions = run_trait_pipeline(profile_result)

    lactase_prediction = predictions["lactase_persistence"]
    assert lactase_prediction.status == PredictionStatus.PREDICTED
    assert lactase_prediction.predicted_phenotype == "lactase persistent"


def test_run_trait_pipeline_missing_calls_do_not_crash_execution() -> None:
    profile_result = _fake_profile_result([])

    predictions = run_trait_pipeline(profile_result)  # must not raise

    assert set(predictions.keys()) == set(TRAIT_REGISTRY.keys())
    assert all(
        prediction.status == PredictionStatus.INSUFFICIENT_DATA
        for prediction in predictions.values()
    )


def test_run_trait_pipeline_forwards_configuration_overrides() -> None:
    # A no-call token override must actually reach GenotypeIndex
    # through the full run_trait_pipeline call, not just
    # build_genotype_index in isolation. "ZZ" is a 2-character token,
    # so by default (not a recognized missing-value/indel token) it
    # classifies as a SNP-shaped call (GenotypeIndex performs no
    # biological validation of allele letters) -- the override below
    # must change that to INSUFFICIENT_DATA.
    profile_result = _fake_profile_result([("rs4988235", "2", "136608646", "ZZ")])

    default_predictions = run_trait_pipeline(profile_result)
    assert (
        default_predictions["lactase_persistence"].status
        == PredictionStatus.PREDICTED
    )

    overridden_predictions = run_trait_pipeline(
        profile_result, missing_value_tokens=("ZZ",)
    )
    assert (
        overridden_predictions["lactase_persistence"].status
        == PredictionStatus.INSUFFICIENT_DATA
    )