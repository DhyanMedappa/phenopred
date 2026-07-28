# tests/reporting/test_phenopred_report.py
"""Unit tests for the PhenoPredReport entity
(phenopred_phase2/reporting/entities.py).

DISCLOSED FIXTURE LIMITATION: phenopred/domain/value_objects.py (which
defines CommentBlock, EncodingProfile, Delimiter, HeaderInfo, Finding,
the Profile family, and OpenQuestion) was not available in this
environment. phenopred.domain.entities.ProfilingReport performs no
field-type validation of its own (confirmed directly in its source:
"no invariant is named for ProfilingReport... this entity enforces
none"), so these tests construct real ProfilingReport instances using
simple, explicitly-labeled placeholder strings/None/empty-tuples in
place of those nested V1 value objects, rather than fabricating stand-in
classes that impersonate real V1 types. This mirrors the same disclosed
fake-substitution convention already used elsewhere in this test suite
(e.g. test_composition.py's _FakeDataRow/_FakeColumnLayout) for V1
construction inputs not authored in this environment.
"""

from __future__ import annotations

import pytest

from phenopred.domain.entities import ProfilingReport
from phenopred_phase2.comparison.domain.entities import (
    ComparisonReport,
    ConcordanceResult,
    IdentityLikelihood,
    IdentityLikelihoodCategory,
)
from phenopred_phase2.reporting.entities import PhenoPredReport
from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    PredictionStatus,
    TraitCard,
    TraitPrediction,
)


def _profiling_report(source_path: str = "fake_file.txt") -> ProfilingReport:
    # Placeholder V1 nested values -- see module docstring.
    return ProfilingReport(
        source_path=source_path,
        comment_block="fake-comment-block",
        encoding_profile="fake-encoding-profile",
        delimiter=",",
        header_info="fake-header-info",
        row_count=100,
        column_count_distribution=None,
        findings=(),
        profiles=(),
        open_questions=(),
    )


def _trait_card(trait_id: str = "lactase_persistence") -> TraitCard:
    prediction = TraitPrediction(
        trait_id=trait_id,
        status=PredictionStatus.PREDICTED,
        predicted_phenotype="lactase non-persistent",
        confidence=ConfidenceLevel.HIGH,
        observed_genotypes={},
        supporting_snps={},
    )
    return TraitCard(
        trait_id=trait_id,
        trait_name="Lactase Persistence",
        trait_evidence_refs=("A citation.",),
        prediction=prediction,
        limitation_keys=("ancestry_generalizability",),
    )


def _comparison_report() -> ComparisonReport:
    return ComparisonReport(
        concordance=ConcordanceResult(
            total_shared_rsids=100,
            shared_snp_count=99,
            conflicting_snp_count=1,
            missing_or_no_call_count=0,
            structural_mismatch_count=0,
            agreement_percentage=99.0,
        ),
        identity_likelihood=IdentityLikelihood(
            concordance_percentage=99.0,
            category=IdentityLikelihoodCategory.HIGH_CONCORDANCE,
            methodology_caveat_key="identity_heuristic_not_ibd_ibs",
        ),
        trait_comparisons={},
    )


# ---------------------------------------------------------------------------
# Valid construction
# ---------------------------------------------------------------------------


def test_phenopred_report_valid_single_file_report() -> None:
    report = PhenoPredReport(
        file_a_profiling_report=_profiling_report("a.txt"),
        file_a_trait_cards={"lactase_persistence": _trait_card()},
        file_b_profiling_report=None,
        file_b_trait_cards=None,
        comparison=None,
    )

    assert report.file_a_profiling_report.source_path == "a.txt"
    assert "lactase_persistence" in report.file_a_trait_cards
    assert report.file_b_profiling_report is None
    assert report.file_b_trait_cards is None
    assert report.comparison is None


def test_phenopred_report_valid_two_file_report() -> None:
    report = PhenoPredReport(
        file_a_profiling_report=_profiling_report("a.txt"),
        file_a_trait_cards={"lactase_persistence": _trait_card()},
        file_b_profiling_report=_profiling_report("b.txt"),
        file_b_trait_cards={"lactase_persistence": _trait_card()},
        comparison=_comparison_report(),
    )

    assert report.file_a_profiling_report.source_path == "a.txt"
    assert report.file_b_profiling_report.source_path == "b.txt"
    assert report.comparison is not None
    assert report.comparison.concordance.agreement_percentage == 99.0


# ---------------------------------------------------------------------------
# Invalid partial file-B/comparison state
# ---------------------------------------------------------------------------


def test_phenopred_report_rejects_file_b_profiling_report_without_trait_cards() -> (
    None
):
    with pytest.raises(ValueError, match="all present or all None together"):
        PhenoPredReport(
            file_a_profiling_report=_profiling_report("a.txt"),
            file_a_trait_cards={"lactase_persistence": _trait_card()},
            file_b_profiling_report=_profiling_report("b.txt"),
            file_b_trait_cards=None,
            comparison=_comparison_report(),
        )


def test_phenopred_report_rejects_comparison_without_file_b() -> None:
    with pytest.raises(ValueError, match="all present or all None together"):
        PhenoPredReport(
            file_a_profiling_report=_profiling_report("a.txt"),
            file_a_trait_cards={"lactase_persistence": _trait_card()},
            file_b_profiling_report=None,
            file_b_trait_cards=None,
            comparison=_comparison_report(),
        )


def test_phenopred_report_rejects_file_b_trait_cards_without_profiling_report() -> (
    None
):
    with pytest.raises(ValueError, match="all present or all None together"):
        PhenoPredReport(
            file_a_profiling_report=_profiling_report("a.txt"),
            file_a_trait_cards={"lactase_persistence": _trait_card()},
            file_b_profiling_report=None,
            file_b_trait_cards={"lactase_persistence": _trait_card()},
            comparison=None,
        )


def test_phenopred_report_rejects_file_b_present_without_comparison() -> None:
    with pytest.raises(ValueError, match="all present or all None together"):
        PhenoPredReport(
            file_a_profiling_report=_profiling_report("a.txt"),
            file_a_trait_cards={"lactase_persistence": _trait_card()},
            file_b_profiling_report=_profiling_report("b.txt"),
            file_b_trait_cards={"lactase_persistence": _trait_card()},
            comparison=None,
        )


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


def test_phenopred_report_is_frozen() -> None:
    report = PhenoPredReport(
        file_a_profiling_report=_profiling_report("a.txt"),
        file_a_trait_cards={"lactase_persistence": _trait_card()},
        file_b_profiling_report=None,
        file_b_trait_cards=None,
        comparison=None,
    )
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
        report.comparison = _comparison_report()  # type: ignore[misc]