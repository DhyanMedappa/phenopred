# tests/reporting/test_report_serializer.py
"""Tests for Phase2JsonReportSerializer
(phenopred_phase2/reporting/report_serializer.py).

These tests verify:
    - Enum handling (confirmed missing from the base JsonReportSerializer
      before this class was written -- see module docstring in
      report_serializer.py).
    - PhenoPredReport's approved top-level JSON shape ("file_a"/"file_b"/
      "comparison"), including that file_b/comparison are omitted, never
      fabricated, for a one-file report.
    - TraitCard and ComparisonReport nested conversion correctness.
    - JSON validity (the written artifact parses back with json.load).
    - Compatibility/regression: the *base* JsonReportSerializer's own
      existing behavior for a plain ProfilingReport (no Phase 2 content
      at all) is unaffected by this subclass -- i.e. this extension adds
      capability without altering inherited behavior.

Same disclosed fixture limitation as the other two reporting test
files: real ProfilingReport instances use placeholder values for their
V1 nested fields, since phenopred/domain/value_objects.py was not
uploaded to this environment.
"""

from __future__ import annotations

import json

from phenopred.domain.entities import ProfilingReport
from phenopred.infrastructure.io.report_writer import JsonReportSerializer
from phenopred_phase2.comparison.domain.entities import (
    ComparisonReport,
    ConcordanceResult,
    IdentityLikelihood,
    IdentityLikelihoodCategory,
)
from phenopred_phase2.reporting.entities import PhenoPredReport
from phenopred_phase2.reporting.report_builder import build_phenopred_report
from phenopred_phase2.reporting.report_serializer import Phase2JsonReportSerializer
from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    PredictionStatus,
    TraitCard,
    TraitPrediction,
)


def _profiling_report(source_path: str = "fake_file.txt") -> ProfilingReport:
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
# Enum handling
# ---------------------------------------------------------------------------


def test_base_serializer_raises_typeerror_on_enum_fields() -> None:
    # Regression guard proving the gap this subclass exists to close is
    # real, not assumed -- the *unmodified* base class must still fail
    # on a Phase 2 dataclass containing a plain Enum field.
    card = _trait_card()
    base_serializer = JsonReportSerializer()

    try:
        base_serializer.serialize(card, "/tmp/_should_not_be_written.json")
        raised = False
    except TypeError:
        raised = True

    assert raised, (
        "Expected the unmodified base JsonReportSerializer to raise "
        "TypeError on a plain Enum field; if this no longer raises, "
        "Phase2JsonReportSerializer's Enum-handling override may no "
        "longer be necessary and this test (and the surrounding "
        "rationale) should be revisited."
    )


def test_phase2_serializer_correctly_serializes_enum_fields(tmp_path) -> None:
    card = _trait_card()
    serializer = Phase2JsonReportSerializer()

    output_path = serializer.serialize(card, tmp_path / "card.json")
    written = json.loads(output_path.read_text())

    assert written["prediction"]["status"] == "predicted"
    assert written["prediction"]["confidence"] == "high"


# ---------------------------------------------------------------------------
# TraitCard / ComparisonReport nested conversion correctness
# ---------------------------------------------------------------------------


def test_phase2_serializer_serializes_trait_card_fields_correctly(tmp_path) -> None:
    card = _trait_card()
    serializer = Phase2JsonReportSerializer()

    output_path = serializer.serialize(card, tmp_path / "card.json")
    written = json.loads(output_path.read_text())

    assert written["trait_id"] == "lactase_persistence"
    assert written["trait_name"] == "Lactase Persistence"
    assert written["trait_evidence_refs"] == ["A citation."]
    assert written["limitation_keys"] == ["ancestry_generalizability"]
    assert written["prediction"]["predicted_phenotype"] == "lactase non-persistent"


def test_phase2_serializer_serializes_comparison_report_fields_correctly(
    tmp_path,
) -> None:
    comparison = _comparison_report()
    serializer = Phase2JsonReportSerializer()

    output_path = serializer.serialize(comparison, tmp_path / "comparison.json")
    written = json.loads(output_path.read_text())

    assert written["concordance"]["total_shared_rsids"] == 100
    assert written["concordance"]["agreement_percentage"] == 99.0
    assert written["identity_likelihood"]["category"] == "high_concordance"
    assert written["trait_comparisons"] == {}


# ---------------------------------------------------------------------------
# PhenoPredReport top-level shape (JSON validity + structure)
# ---------------------------------------------------------------------------


def test_phase2_serializer_one_file_report_shape_omits_file_b_and_comparison(
    tmp_path,
) -> None:
    report = build_phenopred_report(
        _profiling_report("a.txt"), {"lactase_persistence": _trait_card()}
    )
    serializer = Phase2JsonReportSerializer()

    output_path = serializer.serialize(report, tmp_path / "report.json")
    written = json.loads(output_path.read_text())  # must be valid JSON

    assert "file_a" in written
    assert "file_b" not in written
    assert "comparison" not in written

    assert written["file_a"]["source_path"] == "a.txt"
    assert written["file_a"]["row_count"] == 100
    assert "lactase_persistence" in written["file_a"]["traits"]


def test_phase2_serializer_two_file_report_includes_file_b_and_comparison(
    tmp_path,
) -> None:
    report = build_phenopred_report(
        _profiling_report("a.txt"),
        {"lactase_persistence": _trait_card()},
        _profiling_report("b.txt"),
        {"lactase_persistence": _trait_card()},
        _comparison_report(),
    )
    serializer = Phase2JsonReportSerializer()

    output_path = serializer.serialize(report, tmp_path / "report.json")
    written = json.loads(output_path.read_text())

    assert written["file_a"]["source_path"] == "a.txt"
    assert written["file_b"]["source_path"] == "b.txt"
    assert "lactase_persistence" in written["file_a"]["traits"]
    assert "lactase_persistence" in written["file_b"]["traits"]
    assert written["comparison"]["concordance"]["agreement_percentage"] == 99.0
    assert written["comparison"]["identity_likelihood"]["category"] == (
        "high_concordance"
    )


def test_phase2_serializer_preserves_existing_v1_profiling_report_fields(
    tmp_path,
) -> None:
    # Every field already produced by V1's ProfilingReport must survive
    # unaltered inside "file_a"/"file_b", per Blueprint Section 14's
    # "extends V1's existing ReportSerializer output shape... rather
    # than inventing a parallel format."
    report = build_phenopred_report(
        _profiling_report("a.txt"), {"lactase_persistence": _trait_card()}
    )
    serializer = Phase2JsonReportSerializer()

    output_path = serializer.serialize(report, tmp_path / "report.json")
    written = json.loads(output_path.read_text())

    file_a = written["file_a"]
    assert file_a["comment_block"] == "fake-comment-block"
    assert file_a["encoding_profile"] == "fake-encoding-profile"
    assert file_a["delimiter"] == ","
    assert file_a["header_info"] == "fake-header-info"
    assert file_a["column_count_distribution"] is None
    assert file_a["findings"] == []
    assert file_a["profiles"] == []
    assert file_a["open_questions"] == []


# ---------------------------------------------------------------------------
# Compatibility with V1 report serialization behavior (regression)
# ---------------------------------------------------------------------------


def test_phase2_serializer_behaves_identically_to_base_serializer_for_plain_v1_report(
    tmp_path,
) -> None:
    # A plain ProfilingReport with no Phase 2 content at all must
    # serialize identically whether the base JsonReportSerializer or
    # this subclass is used -- proving the extension changes nothing
    # about existing V1 behavior.
    plain_report = _profiling_report("plain.txt")

    base_output = JsonReportSerializer().serialize(
        plain_report, tmp_path / "base.json"
    )
    phase2_output = Phase2JsonReportSerializer().serialize(
        plain_report, tmp_path / "phase2.json"
    )

    assert base_output.read_text() == phase2_output.read_text()


def test_phase2_serializer_inherits_serialize_method_unmodified() -> None:
    # Phase2JsonReportSerializer must not override serialize() itself --
    # only _to_jsonable() -- per the approved "extend, do not
    # reimplement" design.
    assert (
        Phase2JsonReportSerializer.serialize is JsonReportSerializer.serialize
    )