# tests/integration/test_comparison_pipeline.py
"""End-to-end integration test: two real genotype files -> real
ProfileFileUseCase -> real GenotypeIndex -> real TraitEngine -> real
Comparison Engine -> real ComparisonReport.

Mirrors test_trait_execution_pipeline.py's own established real-file
integration style exactly -- same two real validation files, same
disclosed real-vs-substituted collaborator boundary (RawLineSplitter,
DelimiterDetector, HeaderResolver, ColumnIdentityResolver, RowParser
are 100% real, unmodified V1 source; file_loader/encoding_detector/
report_builder are minimal, clearly-labeled stand-ins for V1
infrastructure/reporting components with no bearing on
data_rows/column_layout). Unit tests for each Comparison Engine
component already exist in isolation (tests/comparison/); this file
proves they work together against real data end to end.
"""

from __future__ import annotations

from pathlib import Path

from phenopred.application.profile_file_use_case import ProfileFileUseCase
from phenopred.domain.detection.column_identity_resolver import (
    ColumnIdentityResolver,
)
from phenopred.domain.detection.delimiter_detector import DelimiterDetector
from phenopred.domain.detection.header_resolver import HeaderResolver
from phenopred.domain.ingestion.raw_line_splitter import RawLineSplitter
from phenopred.domain.ingestion.row_parser import RowParser
from phenopred_phase2.comparison.application.comparison_use_case import (
    run_comparison,
)
from phenopred_phase2.comparison.domain.entities import TraitAgreement
from phenopred_phase2.traits.application.composition import (
    build_genotype_index,
    run_trait_pipeline,
)
from phenopred_phase2.traits.domain.trait_registry import TRAIT_REGISTRY

DATA_DIR = Path(__file__).resolve().parent / "data"
ANCESTRYDNA = DATA_DIR / "AncestryDNA.txt"
TWENTYTHREEANDME = DATA_DIR / "anonymous_genome_v5_build37.txt"

_DESIGNATED_COLUMN_KEYWORDS = ("allele1", "allele2", "genotype")


class _FakeRawFileContent:
    def __init__(self, lines: tuple[str, ...], source_path: str) -> None:
        self.lines = lines
        self.source_path = source_path
        self.byte_sample = b""


class _FakeFileLoader:
    def load(self, file_path) -> _FakeRawFileContent:
        with open(file_path, encoding="utf-8") as handle:
            lines = tuple(line.rstrip("\n").rstrip("\r") for line in handle)
        return _FakeRawFileContent(lines=lines, source_path=str(file_path))


class _FakeEncodingDetector:
    def detect(self, byte_sample):
        return None


class _FakeReportBuilder:
    def build(self, **kwargs):
        return None


def _build_real_profile_file_use_case() -> ProfileFileUseCase:
    return ProfileFileUseCase(
        file_loader=_FakeFileLoader(),
        line_splitter=RawLineSplitter(comment_prefix="#"),
        encoding_detector=_FakeEncodingDetector(),
        delimiter_detector=DelimiterDetector(sample_size=20),
        header_resolver=HeaderResolver(header_keyword="rsid"),
        column_identity_resolver=ColumnIdentityResolver(
            rsid_keyword="rsid",
            chromosome_keyword="chromosome",
            position_keyword="position",
            designated_column_keywords=_DESIGNATED_COLUMN_KEYWORDS,
        ),
        row_parser=RowParser(),
        quality_checks={},
        genomic_profilers={},
        report_builder=_FakeReportBuilder(),
    )


def test_full_comparison_pipeline_runs_end_to_end_against_both_real_files() -> (
    None
):
    use_case_a = _build_real_profile_file_use_case()
    use_case_b = _build_real_profile_file_use_case()

    profile_result_a = use_case_a.execute(str(ANCESTRYDNA))
    profile_result_b = use_case_b.execute(str(TWENTYTHREEANDME))

    genotype_index_a = build_genotype_index(profile_result_a)
    genotype_index_b = build_genotype_index(profile_result_b)

    predictions_a = run_trait_pipeline(profile_result_a)
    predictions_b = run_trait_pipeline(profile_result_b)

    report = run_comparison(
        genotype_index_a, genotype_index_b, predictions_a, predictions_b
    )

    # Genome-wide concordance: both real files describe the same
    # underlying reference genome build (GRCh37), so a large,
    # well-formed shared-RSID set and a high agreement rate are
    # expected -- exact figures are incidental data, not a frozen
    # contract, so only well-formedness and order-of-magnitude
    # consistency are asserted here.
    assert report.concordance.total_shared_rsids > 100_000
    assert 0.0 <= report.concordance.agreement_percentage <= 100.0
    assert (
        report.concordance.shared_snp_count
        + report.concordance.conflicting_snp_count
        + report.concordance.missing_or_no_call_count
        + report.concordance.structural_mismatch_count
        == report.concordance.total_shared_rsids
    )

    # Identity likelihood: always structurally present, never omitted.
    assert report.identity_likelihood.methodology_caveat_key != ""
    assert report.identity_likelihood.concordance_percentage == (
        report.concordance.agreement_percentage
    )

    # Trait comparisons: every currently-registered trait_id appears.
    assert set(report.trait_comparisons.keys()) == set(TRAIT_REGISTRY.keys())
    for trait_id, comparison in report.trait_comparisons.items():
        assert comparison.trait_id == trait_id
        assert comparison.agreement in (
            TraitAgreement.AGREE,
            TraitAgreement.DISAGREE,
            TraitAgreement.INSUFFICIENT_DATA,
            TraitAgreement.MISSING_TRAIT,
        )
        # Both real files' predictions are present for every currently
        # -registered trait (confirmed by the existing trait pipeline
        # integration test), so MISSING_TRAIT is not expected here.
        assert comparison.agreement != TraitAgreement.MISSING_TRAIT


def test_full_comparison_pipeline_lactase_persistence_agrees_across_both_files() -> (
    None
):
    # Regression guard: both real files' rs4988235 genotype is known
    # (verified during architecture review) to be heterozygous, so the
    # two files' lactase_persistence predictions should agree.
    use_case_a = _build_real_profile_file_use_case()
    use_case_b = _build_real_profile_file_use_case()

    profile_result_a = use_case_a.execute(str(ANCESTRYDNA))
    profile_result_b = use_case_b.execute(str(TWENTYTHREEANDME))

    genotype_index_a = build_genotype_index(profile_result_a)
    genotype_index_b = build_genotype_index(profile_result_b)
    predictions_a = run_trait_pipeline(profile_result_a)
    predictions_b = run_trait_pipeline(profile_result_b)

    report = run_comparison(
        genotype_index_a, genotype_index_b, predictions_a, predictions_b
    )

    assert (
        report.trait_comparisons["lactase_persistence"].agreement
        == TraitAgreement.AGREE
    )


def test_full_comparison_pipeline_eye_colour_reaches_a_real_agreement_classification() -> (
    None
):
    # Previously, this test expected INSUFFICIENT_DATA on both sides,
    # based on the earlier SNP_REGISTRY entry for rs1800407 (G/A),
    # under which both real files' "CC" genotype was unrecognized. That
    # entry has since been corrected (OCA2 is a minus-strand gene; the
    # verified GRCh37 forward-strand pair is C/T), and EyeColourModel
    # was separately replaced with the IrisPlex multinomial regression.
    # Per test_trait_execution_pipeline.py, both real files' eye_colour
    # prediction now individually reaches PREDICTED -- and
    # trait_diff._classify_agreement() only returns INSUFFICIENT_DATA
    # when at least one side's own prediction status is
    # INSUFFICIENT_DATA, so that outcome is no longer reachable here.
    # The actual classification (AGREE vs. DISAGREE) depends on whether
    # both files' six IrisPlex loci happen to produce byte-identical
    # probability strings, which is real data this test does not
    # otherwise assert on -- so only that a genuine, non-exceptional
    # classification is reached is verified here.
    use_case_a = _build_real_profile_file_use_case()
    use_case_b = _build_real_profile_file_use_case()

    profile_result_a = use_case_a.execute(str(ANCESTRYDNA))
    profile_result_b = use_case_b.execute(str(TWENTYTHREEANDME))

    genotype_index_a = build_genotype_index(profile_result_a)
    genotype_index_b = build_genotype_index(profile_result_b)
    predictions_a = run_trait_pipeline(profile_result_a)
    predictions_b = run_trait_pipeline(profile_result_b)

    report = run_comparison(
        genotype_index_a, genotype_index_b, predictions_a, predictions_b
    )

    assert report.trait_comparisons["eye_colour"].agreement in (
        TraitAgreement.AGREE,
        TraitAgreement.DISAGREE,
    )


def test_comparison_report_is_produced_without_mutating_source_inputs() -> None:
    use_case_a = _build_real_profile_file_use_case()
    use_case_b = _build_real_profile_file_use_case()

    profile_result_a = use_case_a.execute(str(ANCESTRYDNA))
    profile_result_b = use_case_b.execute(str(TWENTYTHREEANDME))

    genotype_index_a = build_genotype_index(profile_result_a)
    genotype_index_b = build_genotype_index(profile_result_b)
    predictions_a = run_trait_pipeline(profile_result_a)
    predictions_b = run_trait_pipeline(profile_result_b)

    predictions_a_before = dict(predictions_a)
    predictions_b_before = dict(predictions_b)

    run_comparison(genotype_index_a, genotype_index_b, predictions_a, predictions_b)

    assert dict(predictions_a) == predictions_a_before
    assert dict(predictions_b) == predictions_b_before