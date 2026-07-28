# phenopred_phase2/webapp/app.py
"""Streamlit entrypoint for the PhenoPred flow (single-file and two-file)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from phenopred.domain.errors import PhenoPredIngestionError
from phenopred_phase2.comparison.domain.entities import TraitAgreement
from phenopred_phase2.reporting.report_serializer import Phase2JsonReportSerializer
from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCallKind,
    PredictionStatus,
)
from phenopred_phase2.webapp.composition import (
    run_single_file_pipeline,
    run_two_file_pipeline,
)

st.set_page_config(page_title="PhenoPred", page_icon="🧬", layout="wide")

_ANCESTRY_CAVEAT = (
    "Most trait associations were established primarily in European-ancestry "
    "cohorts and may not generalize equally across populations."
)
_ANCESTRY_CAVEAT_POINTER = (
    "Population-generalizability caveat applies to this trait -- "
    "see Methodology & Limitations below."
)

_METHODOLOGY_CAVEAT_DISPLAY = {
    "identity_heuristic_not_ibd_ibs": (
        "Rigorous identity or relatedness determination uses identity-by-descent/"
        "identity-by-state estimation across many more markers than this "
        "concordance check performs."
    ),
}

# Categorical confidence indicator only -- these block counts are a fixed
# UI convention, not a probability. HIGH/MODERATE/LOW is all the backend
# ever provides; no numeric confidence value is invented here.
_CONFIDENCE_BAR = {
    ConfidenceLevel.HIGH: "██████████",
    ConfidenceLevel.MODERATE: "███████░░░",
    ConfidenceLevel.LOW: "███░░░░░░░",
}

_CONFIDENCE_COLOR = {
    ConfidenceLevel.HIGH: "green",
    ConfidenceLevel.MODERATE: "orange",
    ConfidenceLevel.LOW: "red",
}

_GENOTYPE_DISPLAY = {
    GenotypeCallKind.SNP: lambda call: call.alleles,
    GenotypeCallKind.HAPLOID: lambda call: call.allele,
    GenotypeCallKind.NO_CALL: lambda call: "no call",
    GenotypeCallKind.INDEL: lambda call: "indel",
    GenotypeCallKind.UNRECOGNIZED: lambda call: "unrecognized",
}

_AGREEMENT_DISPLAY = {
    TraitAgreement.AGREE: "✓ Agree",
    TraitAgreement.DISAGREE: "✗ Disagree",
    TraitAgreement.INSUFFICIENT_DATA: "Insufficient data",
    TraitAgreement.MISSING_TRAIT: "Missing",
}

_LAYOUT_KIND_DISPLAY = {
    "two_column_allele": "Two-column allele layout",
    "single_column_genotype": "Single-column genotype layout",
    "undetermined": "Undetermined",
}


# ---------------------------------------------------------------------------
# Small, pure display helpers (no Streamlit calls, no biological logic)
# ---------------------------------------------------------------------------


def genotype_display(call) -> str:
    return _GENOTYPE_DISPLAY[call.kind](call)


def encoding_label(encoding_profile) -> str:
    if encoding_profile.utf8_decodable:
        label = "UTF-8"
    elif encoding_profile.ascii_decodable:
        label = "ASCII"
    else:
        label = "Latin-1"
    if encoding_profile.bom_present:
        label += " (BOM present)"
    return label


def genotype_layout_label(profiling_report) -> str:
    for profile in profiling_report.profiles:
        layout_kind = getattr(profile, "layout_kind", None)
        if layout_kind is not None:
            return _LAYOUT_KIND_DISPLAY.get(layout_kind, layout_kind)
    return "Not detected"


def detected_finding_count(profiling_report) -> int:
    # "Detected" = checks that actually flagged something, not the total
    # number of checks that ran.
    return sum(1 for finding in profiling_report.findings if finding.count > 0)


def _prediction_display(prediction) -> str:
    if prediction is None:
        return "—"
    if prediction.status == PredictionStatus.PREDICTED:
        return prediction.predicted_phenotype
    return "insufficient data"


def _confidence_label(prediction) -> str:
    if prediction.status != PredictionStatus.PREDICTED:
        return "—"
    return prediction.confidence.value.upper()


def _supporting_snps_label(prediction) -> str:
    snps = prediction.supporting_snps
    if not snps:
        return "—"
    if len(snps) == 1:
        return next(iter(snps))
    return f"{len(snps)} SNPs"


def comparable_genotype_agreement_percentage(concordance) -> float | None:
    # Display-only ratio derived from two already-computed backend
    # integers (shared_snp_count, conflicting_snp_count) -- no new
    # genotype comparison or biological judgment is performed here.
    comparable = concordance.shared_snp_count + concordance.conflicting_snp_count
    if comparable == 0:
        return None
    return (concordance.shared_snp_count / comparable) * 100.0


def predicted_trait_count(trait_cards) -> tuple[int, int]:
    predicted = sum(
        1
        for card in trait_cards.values()
        if card.prediction.status == PredictionStatus.PREDICTED
    )
    return predicted, len(trait_cards)


# ---------------------------------------------------------------------------
# Shared visual components
# ---------------------------------------------------------------------------


def render_confidence_indicator(confidence: ConfidenceLevel) -> None:
    color = _CONFIDENCE_COLOR[confidence]
    label = confidence.value.upper()
    st.markdown(f":{color}[**{label}**]")
    st.markdown(f"`{_CONFIDENCE_BAR[confidence]}`")
    st.caption("Category-based confidence -- not a numeric probability.")


def render_metric_card(label: str, value) -> None:
    with st.container(border=True):
        st.metric(label, value)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def render_quality_dashboard(profiling_report) -> None:
    col1, col2, col3 = st.columns(3)
    with col1:
        render_metric_card("Rows processed", f"{profiling_report.row_count:,}")
    with col2:
        render_metric_card("Encoding", encoding_label(profiling_report.encoding_profile))
    with col3:
        render_metric_card("Genotype layout", genotype_layout_label(profiling_report))

    col4, col5 = st.columns(2)
    with col4:
        render_metric_card("Detected findings", detected_finding_count(profiling_report))
    with col5:
        render_metric_card("Methodology caveats", len(profiling_report.open_questions))

    if any(finding.count > 0 for finding in profiling_report.findings):
        st.divider()
        st.markdown("**Findings detail**")
        for finding in profiling_report.findings:
            if finding.count > 0:
                st.write(f"- {finding.check_name}: {finding.description} ({finding.count})")

    if profiling_report.open_questions:
        st.divider()
        st.markdown("**Open questions**")
        for question in profiling_report.open_questions:
            st.write(f"- {question.statement}")


def render_trait_card(card) -> None:
    with st.expander(f"🧬 {card.trait_name}"):
        prediction = card.prediction

        if prediction.status == PredictionStatus.PREDICTED:
            st.markdown(f"#### {prediction.predicted_phenotype}")
            render_confidence_indicator(prediction.confidence)
        else:
            st.info("Insufficient data to predict this trait.")

        st.divider()
        st.markdown("**🔬 Evidence**")
        st.write(f"Supporting SNPs: {_supporting_snps_label(prediction)}")
        if prediction.observed_genotypes:
            for rsid, call in prediction.observed_genotypes.items():
                st.write(f"- {rsid} = {genotype_display(call)}")

        references = list(card.trait_evidence_refs) + [
            snp.citation for snp in prediction.supporting_snps.values()
        ]
        if references:
            st.divider()
            st.markdown("**📚 References**")
            for reference in references:
                st.caption(reference)

        st.divider()
        st.markdown("**⚠️ Limitations**")
        st.caption(_ANCESTRY_CAVEAT_POINTER)


def render_trait_summary_table(trait_cards) -> None:
    rows = [
        {
            "Trait": card.trait_name,
            "Prediction": _prediction_display(card.prediction),
            "Confidence": _confidence_label(card.prediction),
            "Supporting SNPs": _supporting_snps_label(card.prediction),
        }
        for card in trait_cards.values()
    ]
    st.table(rows)


def render_concordance_dashboard(comparison) -> None:
    concordance = comparison.concordance

    st.markdown("#### Comparable genotype agreement")
    comparable_pct = comparable_genotype_agreement_percentage(concordance)
    if comparable_pct is not None:
        st.progress(min(comparable_pct / 100.0, 1.0))
        st.markdown(f"**{comparable_pct:.2f}%**")
    else:
        st.write("n/a -- no comparable SNPs")
    col1, col2 = st.columns(2)
    with col1:
        render_metric_card("Matching SNPs", f"{concordance.shared_snp_count:,}")
    with col2:
        render_metric_card("Conflicting SNPs", f"{concordance.conflicting_snp_count:,}")

    st.divider()
    st.markdown("#### Platform coverage differences")
    st.caption("Platform coverage differences are not biological disagreement.")
    col3, col4 = st.columns(2)
    with col3:
        render_metric_card("Structural mismatches", f"{concordance.structural_mismatch_count:,}")
    with col4:
        render_metric_card("Missing / no-call", f"{concordance.missing_or_no_call_count:,}")

    st.divider()
    st.markdown("#### Overall shared-marker agreement")
    st.caption("Across all shared SNPs, including no-call and structural differences.")
    st.progress(min(concordance.agreement_percentage / 100.0, 1.0))
    st.markdown(f"**{concordance.agreement_percentage:.2f}%**")

    st.divider()
    identity = comparison.identity_likelihood
    st.write(
        f"**Identity likelihood:** {identity.category.value.replace('_', ' ')}"
    )
    caveat = _METHODOLOGY_CAVEAT_DISPLAY.get(identity.methodology_caveat_key)
    if caveat:
        st.caption(caveat)


def render_trait_comparison_table(comparison, trait_cards_a, trait_cards_b) -> None:
    rows = []
    for trait_id, trait_comparison in comparison.trait_comparisons.items():
        card = trait_cards_a.get(trait_id) or trait_cards_b.get(trait_id)
        trait_name = card.trait_name if card is not None else trait_id
        rows.append(
            {
                "Trait": trait_name,
                "Dataset A": _prediction_display(trait_comparison.prediction_a),
                "Dataset B": _prediction_display(trait_comparison.prediction_b),
                "Agreement": _AGREEMENT_DISPLAY[trait_comparison.agreement],
            }
        )
    st.table(rows)


def render_dataset_quality_section(report) -> None:
    with st.expander("📊 Dataset Quality", expanded=False):
        if report.comparison is not None:
            tab_a, tab_b = st.tabs(["Dataset A", "Dataset B"])
            with tab_a:
                render_quality_dashboard(report.file_a_profiling_report)
            with tab_b:
                render_quality_dashboard(report.file_b_profiling_report)
        else:
            render_quality_dashboard(report.file_a_profiling_report)


def render_trait_predictions_section(report) -> None:
    st.subheader("🎯 Trait Predictions")
    if report.comparison is not None:
        tab_a, tab_b = st.tabs(["Dataset A", "Dataset B"])
        with tab_a:
            for card in report.file_a_trait_cards.values():
                render_trait_card(card)
        with tab_b:
            for card in report.file_b_trait_cards.values():
                render_trait_card(card)
    else:
        for card in report.file_a_trait_cards.values():
            render_trait_card(card)


def render_trait_summary_section(report) -> None:
    with st.expander("📋 Trait Summary", expanded=True):
        if report.comparison is not None:
            tab_a, tab_b = st.tabs(["Dataset A", "Dataset B"])
            with tab_a:
                render_trait_summary_table(report.file_a_trait_cards)
            with tab_b:
                render_trait_summary_table(report.file_b_trait_cards)
        else:
            render_trait_summary_table(report.file_a_trait_cards)


def render_comparison_section(report) -> None:
    if report.comparison is None:
        return
    with st.expander("🔗 Dataset Comparison", expanded=True):
        render_concordance_dashboard(report.comparison)
        st.divider()
        st.markdown("#### Per-trait comparison")
        render_trait_comparison_table(
            report.comparison, report.file_a_trait_cards, report.file_b_trait_cards
        )


def render_methodology_section(report) -> None:
    with st.expander("⚠️ Methodology and Limitations", expanded=False):
        st.markdown("**Ancestry generalizability**")
        st.caption(
            "Applies to every trait prediction above: "
            + _ANCESTRY_CAVEAT
        )
        if report.comparison is not None:
            st.divider()
            st.markdown("**Identity/relatedness methodology**")
            st.write("See the Dataset Comparison section above.")


def render_progress_indicators(report) -> None:
    st.success("✓ Processing completed")

    predicted_a, total_a = predicted_trait_count(report.file_a_trait_cards)
    if report.comparison is not None:
        predicted_b, total_b = predicted_trait_count(report.file_b_trait_cards)
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.write("**Dataset A**")
                st.write(f"✓ Profiled -- {predicted_a}/{total_a} traits evaluated")
        with col2:
            with st.container(border=True):
                st.write("**Dataset B**")
                st.write(f"✓ Profiled -- {predicted_b}/{total_b} traits evaluated")
    else:
        st.write(f"✓ Profiled -- {predicted_a}/{total_a} traits evaluated")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("🧬 PhenoPred")
st.caption("AI-powered genomic trait prediction and dataset comparison")
st.divider()

uploaded_file_a = st.file_uploader("Upload Dataset A (required)")
uploaded_file_b = st.file_uploader("Upload Dataset B (optional)")

if uploaded_file_a is not None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        upload_path_a = Path(tmp_dir) / uploaded_file_a.name
        upload_path_a.write_bytes(uploaded_file_a.getvalue())

        upload_path_b = None
        if uploaded_file_b is not None:
            upload_path_b = Path(tmp_dir) / uploaded_file_b.name
            upload_path_b.write_bytes(uploaded_file_b.getvalue())

        try:
            with st.spinner("Profiling file(s)..."):
                if upload_path_b is not None:
                    report = run_two_file_pipeline(
                        str(upload_path_a), str(upload_path_b)
                    )
                else:
                    report = run_single_file_pipeline(str(upload_path_a))
        except PhenoPredIngestionError as exc:
            st.error(f"Could not profile this file: {exc}")
        else:
            render_progress_indicators(report)
            st.divider()

            render_dataset_quality_section(report)
            st.divider()
            render_trait_predictions_section(report)
            st.divider()
            render_trait_summary_section(report)
            render_comparison_section(report)
            render_methodology_section(report)

            report_path = Path(tmp_dir) / "phenopred_report.json"
            Phase2JsonReportSerializer().serialize(report, report_path)
            st.divider()
            st.download_button(
                "⬇️ Download report (JSON)",
                data=report_path.read_bytes(),
                file_name="phenopred_report.json",
                mime="application/json",
            )