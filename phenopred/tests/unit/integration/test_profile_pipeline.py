# tests/integration/test_profile_pipeline.py
"""
Application integration tests for the real, composition-root-assembled
PhenoPred pipeline.

Unlike the domain and application unit-test suites, this suite performs
no mocking, no fakes, and no synthetic collaborators of any kind. Every
test constructs its ProfileFileUseCase exclusively through
`phenopred.application.composition_root.build_profile_file_use_case`
(the single, approved place where concrete Stage 1 implementations are
bound to ProfileFileUseCase's constructor -- see composition_root.py's
own module docstring), then calls `.execute()` against a real genotype
file on disk. This proves the actual, wired dependency graph -- every
concrete RawFileLoader, RawLineSplitter, EncodingDetector,
DelimiterDetector, HeaderResolver, ColumnIdentityResolver, RowParser,
every FR-5..FR-9 QualityCheck, every FR-10..FR-12 GenomicProfiler, and,
per the frozen Reporting Architecture, the real ReportBuilder and
OpenQuestionRegistry -- exactly as the composition root assembles them
today -- works together correctly end to end. Individual collaborator
algorithms are exhaustively covered by their own unit-test suites and
are not retested here; this suite verifies only that the assembled
pipeline accepts real input and produces a well-formed, correctly
integrated result, including the final ProfilingReport.

Test data (tests/unit/integration/data/raw/):
    - anonymous_genome_v5_build37.txt: a real, byte-faithful excerpt of a
      23andMe v5 raw genotype export. 
      Every retained line is copied verbatim from the original file;
      only the number of data rows has been reduced (to keep this suite
      fast), while deliberately retaining real rows on chromosomes X, Y,
      and MT, plus real rows carrying each of the "II", "DD", and "DI"
      indel tokens, so FR-10/FR-11/FR-12 all have real, exercised
      evidence in this excerpt.
    - AncestryDNA.txt: a real, byte-faithful excerpt of an
      AncestryDNA raw genotype export, again with every
      retained line copied verbatim, reduced to a bounded number of rows
      per chromosome while retaining rows from every one of the file's
      26 distinct numeric chromosome labels.
    - malformed_no_header_keyword.txt: a small, synthetic, deliberately
      malformed fixture (not derived from either real dataset) used only
      by the failure-path test below; it contains no comment lines and
      no line -- header or data -- containing the exact "rsid" token the
      default configuration requires.

Neither real-file excerpt was re-encoded, re-ordered within its retained
rows, or content-modified in any way; only a subset of original, real
lines was selected per file, preserving each file's own original line
order.
"""

from __future__ import annotations

from pathlib import Path

from phenopred.application.composition_root import build_profile_file_use_case
from phenopred.domain.entities import ProfilingReport
from phenopred.domain.errors import PhenoPredIngestionError

DATA_DIR = Path(__file__).resolve().parent / "data" / "raw"

TWENTYTHREEANDME = DATA_DIR / "anonymous_genome_v5_build37.txt"
ANCESTRYDNA = DATA_DIR / "AncestryDNA.txt"
MALFORMED_NO_HEADER_KEYWORD = DATA_DIR / "malformed_no_header_keyword.txt"

_EXPECTED_QUALITY_CHECK_NAMES = {
    "malformed_row_check",
    "duplicate_header_check",
    "missing_value_scanner",
    "duplicate_rsid_check",
    "duplicate_chr_pos_check",
}

_EXPECTED_GENOMIC_PROFILER_NAMES = {
    "chromosome_label_profiler",
    "genotype_layout_classifier",
    "indel_haploid_classifier",
}

# The conventional human karyotype chromosome-label vocabulary (autosomes
# 1-22, plus the sex/mitochondrial labels X, Y, MT) -- the same neutral,
# fixture-independent biological fact OpenQuestionRegistry's own RISK-2
# gating is based on. Used here only to derive, from each real file's
# own already-observed ChromosomeLabelInventory, whether that specific
# run's real data should be expected to trigger the non-conventional-
# code open question -- never asserted as a fixed literal count, since
# neither fixture's own documentation guarantees the exact chromosome
# labels present.
_CONVENTIONAL_CHROMOSOME_LABELS = {str(number) for number in range(1, 23)} | {
    "X",
    "Y",
    "MT",
}


def _expected_chromosome_related_open_question_count(chromosome_label_inventory) -> int:
    observed_labels = {label for label, _ in chromosome_label_inventory.label_counts}
    has_non_conventional_label = bool(
        observed_labels - _CONVENTIONAL_CHROMOSOME_LABELS
    )
    return 2 if has_non_conventional_label else 1


# ---------------------------------------------------------------------------
# 1. 23andMe dataset: full pipeline, real file, composition-root wiring
# ---------------------------------------------------------------------------


def test_23andme_pipeline_executes_successfully_end_to_end() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(TWENTYTHREEANDME)

    assert result is not None
    assert result["source_path"] == TWENTYTHREEANDME
    assert result["encoding_profile"] is not None
    assert result["comment_block"] is not None
    assert result["delimiter"] is not None
    assert result["header_info"] is not None
    assert result["column_layout"] is not None
    assert result["data_rows"] is not None
    assert len(result["data_rows"]) > 0

    assert isinstance(result["findings"], dict)
    assert set(result["findings"].keys()) == _EXPECTED_QUALITY_CHECK_NAMES
    assert result["skipped_quality_checks"] == {}

    assert isinstance(result["profiles"], dict)
    assert set(result["profiles"].keys()) == _EXPECTED_GENOMIC_PROFILER_NAMES


def test_23andme_header_and_column_layout_resolved_correctly() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(TWENTYTHREEANDME)

    # The real 23andMe file's header lives inside its comment block
    # ("# rsid\tchromosome\tposition\tgenotype"), never as an
    # uncommented data row.
    header_info = result["header_info"]
    assert header_info.form == "commented_only"
    assert header_info.resolved_columns == (
        "rsid",
        "chromosome",
        "position",
        "genotype",
    )

    column_layout = result["column_layout"]
    assert column_layout.rsid_column_index == 0
    assert column_layout.chromosome_column_index == 1
    assert column_layout.position_column_index == 2
    assert column_layout.designated_column_indices == (3,)


def test_23andme_chromosome_profiling_executes() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(TWENTYTHREEANDME)

    inventory = result["profiles"]["chromosome_label_profiler"]
    observed_labels = {label for label, _ in inventory.label_counts}
    # Real rows on chromosomes 1, X, Y, and MT are present in this excerpt.
    assert {"1", "X", "Y", "MT"}.issubset(observed_labels)


def test_23andme_genotype_layout_profiling_executes() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(TWENTYTHREEANDME)

    layout_profile = result["profiles"]["genotype_layout_classifier"]
    # Exactly one designated (combined genotype) column -> single_column_genotype.
    assert layout_profile.layout_kind == "single_column_genotype"
    assert len(layout_profile.column_length_distributions) == 1


def test_23andme_indel_haploid_profiling_executes() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(TWENTYTHREEANDME)

    indel_profile = result["profiles"]["indel_haploid_classifier"]
    # Single combined genotype column -> FR-12 is applicable for this file.
    assert indel_profile.applicable is True

    token_counts = dict(indel_profile.indel_token_counts)
    assert token_counts.get("II", 0) > 0
    assert token_counts.get("DD", 0) > 0
    assert token_counts.get("DI", 0) > 0

    # Real haploid (X/Y/MT, single-character) and diploid (two-character)
    # calls are both present in this excerpt.
    assert indel_profile.haploid_count > 0
    assert indel_profile.diploid_count > 0


def test_23andme_report_is_assembled_with_correct_pipeline_data() -> None:
    # Proves the real ReportBuilder/OpenQuestionRegistry/
    # MalformedRowCheck.column_count_distribution() wiring, which no
    # unit test (all of which fake at least one of these collaborators)
    # can prove. This would fail if that wiring were broken even while
    # every individual collaborator's own unit tests kept passing.
    use_case = build_profile_file_use_case()
    result = use_case.execute(TWENTYTHREEANDME)

    report = result["report"]
    assert isinstance(report, ProfilingReport)

    # Scalar fields must be the exact same objects already verified
    # present in the result dict -- not merely equal-by-coincidence
    # values -- proving the report was assembled from this same run's
    # real pipeline output, not recomputed or substituted.
    assert report.source_path == result["source_path"]
    assert report.comment_block is result["comment_block"]
    assert report.encoding_profile is result["encoding_profile"]
    assert report.delimiter is result["delimiter"]
    assert report.header_info is result["header_info"]
    assert report.row_count == len(result["data_rows"])

    # The full real check/profiler set must be present, correctly
    # ordered, on the report -- not a subset, and not silently dropped.
    assert {finding.check_name for finding in report.findings} == (
        _EXPECTED_QUALITY_CHECK_NAMES
    )
    assert [finding.check_name for finding in report.findings] == sorted(
        finding.check_name for finding in result["findings"].values()
    )
    assert {profile.profiler_name for profile in report.profiles} == (
        _EXPECTED_GENOMIC_PROFILER_NAMES
    )
    assert [profile.profiler_name for profile in report.profiles] == sorted(
        profile.profiler_name for profile in result["profiles"].values()
    )

    # column_count_distribution must be the exact same object threaded
    # through to the report, and its modal_count must match this real
    # file's own already-verified header column count (rsid,
    # chromosome, position, genotype).
    assert report.column_count_distribution is result["column_count_distribution"]
    assert report.column_count_distribution.modal_count == len(
        result["header_info"].resolved_columns
    )


def test_23andme_open_questions_reflect_real_chromosome_and_genotype_layout_profiling() -> None:
    # 23andMe's real chromosome-label output (already produced by this
    # same run) determines whether the real OpenQuestionRegistry should
    # select one or two chromosome-related questions -- derived here
    # from the actual observed labels rather than assumed from the
    # fixture's documentation, since neither fixture's own docstring
    # guarantees the exact set of labels present.
    use_case = build_profile_file_use_case()
    result = use_case.execute(TWENTYTHREEANDME)

    report = result["report"]
    chromosome_label_inventory = result["profiles"]["chromosome_label_profiler"]
    expected_chromosome_related_count = _expected_chromosome_related_open_question_count(
        chromosome_label_inventory
    )

    related = [question.related_finding_or_profile for question in report.open_questions]

    assert related.count("chromosome_label_profiler") == expected_chromosome_related_count
    assert related.count("genotype_layout_classifier") == 1
    # The four standing questions (RISK-6/7/8/9) are always present,
    # regardless of file content.
    assert related.count(None) == 3
    assert related.count("duplicate_rsid_check") == 1


# ---------------------------------------------------------------------------
# 2. AncestryDNA dataset: full pipeline, real file, composition-root wiring
# ---------------------------------------------------------------------------


def test_ancestrydna_pipeline_executes_successfully_end_to_end() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(ANCESTRYDNA)

    assert result is not None
    assert result["source_path"] == ANCESTRYDNA
    assert result["encoding_profile"] is not None
    assert result["comment_block"] is not None
    assert result["delimiter"] is not None
    assert result["header_info"] is not None
    assert result["column_layout"] is not None
    assert result["data_rows"] is not None
    assert len(result["data_rows"]) > 0

    assert isinstance(result["findings"], dict)
    assert set(result["findings"].keys()) == _EXPECTED_QUALITY_CHECK_NAMES
    assert result["skipped_quality_checks"] == {}

    assert isinstance(result["profiles"], dict)
    assert set(result["profiles"].keys()) == _EXPECTED_GENOMIC_PROFILER_NAMES


def test_ancestrydna_header_and_allele_column_layout_recognized() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(ANCESTRYDNA)

    # The real AncestryDNA file's header is an uncommented data row,
    # a different structural layout from 23andMe's commented-only header.
    header_info = result["header_info"]
    assert header_info.form == "uncommented_row"
    assert header_info.resolved_columns == (
        "rsid",
        "chromosome",
        "position",
        "allele1",
        "allele2",
    )

    column_layout = result["column_layout"]
    assert column_layout.rsid_column_index == 0
    assert column_layout.chromosome_column_index == 1
    assert column_layout.position_column_index == 2
    # Two separate allele columns, correctly recognized -- distinct from
    # 23andMe's single combined genotype column.
    assert column_layout.designated_column_indices == (3, 4)


def test_ancestrydna_chromosome_profiling_executes() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(ANCESTRYDNA)

    inventory = result["profiles"]["chromosome_label_profiler"]
    observed_labels = {label for label, _ in inventory.label_counts}
    # AncestryDNA reports purely numeric chromosome labels (1-26 in this
    # excerpt), never the X/Y/MT convention 23andMe uses.
    assert {"1", "2", "22"}.issubset(observed_labels)
    assert not observed_labels & {"X", "Y", "MT"}


def test_ancestrydna_genotype_layout_classified_as_two_column_allele() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(ANCESTRYDNA)

    layout_profile = result["profiles"]["genotype_layout_classifier"]
    assert layout_profile.layout_kind == "two_column_allele"
    assert len(layout_profile.column_length_distributions) == 2


def test_ancestrydna_indel_haploid_profiler_reports_not_applicable() -> None:
    # AncestryDNA uses two designated (allele) columns, so FR-12's
    # single-combined-genotype-column applicability gate must report
    # not-applicable for this real file, mirroring
    # test_indel_haploid_classifier.py's own applicability contract.
    use_case = build_profile_file_use_case()
    result = use_case.execute(ANCESTRYDNA)

    indel_profile = result["profiles"]["indel_haploid_classifier"]
    assert indel_profile.applicable is False
    assert indel_profile.indel_token_counts == ()
    assert indel_profile.haploid_count == 0
    assert indel_profile.diploid_count == 0


def test_ancestrydna_report_is_assembled_with_correct_pipeline_data() -> None:
    # Mirrors test_23andme_report_is_assembled_with_correct_pipeline_data
    # for AncestryDNA's structurally distinct vendor layout (uncommented
    # header, two designated columns), proving the real Reporting wiring
    # holds for both real, structurally different vendor formats -- not
    # just one.
    use_case = build_profile_file_use_case()
    result = use_case.execute(ANCESTRYDNA)

    report = result["report"]
    assert isinstance(report, ProfilingReport)

    assert report.source_path == result["source_path"]
    assert report.comment_block is result["comment_block"]
    assert report.encoding_profile is result["encoding_profile"]
    assert report.delimiter is result["delimiter"]
    assert report.header_info is result["header_info"]
    assert report.row_count == len(result["data_rows"])

    assert {finding.check_name for finding in report.findings} == (
        _EXPECTED_QUALITY_CHECK_NAMES
    )
    assert [finding.check_name for finding in report.findings] == sorted(
        finding.check_name for finding in result["findings"].values()
    )
    assert {profile.profiler_name for profile in report.profiles} == (
        _EXPECTED_GENOMIC_PROFILER_NAMES
    )
    assert [profile.profiler_name for profile in report.profiles] == sorted(
        profile.profiler_name for profile in result["profiles"].values()
    )

    # AncestryDNA's header has five resolved columns (rsid, chromosome,
    # position, allele1, allele2) -- distinct from 23andMe's four --
    # proving column_count_distribution reflects this file's own real
    # structure, not a hard-coded or copied value.
    assert report.column_count_distribution is result["column_count_distribution"]
    assert report.column_count_distribution.modal_count == len(
        result["header_info"].resolved_columns
    )


def test_ancestrydna_open_questions_reflect_real_chromosome_and_genotype_layout_profiling() -> None:
    # Same derivation as the 23andMe version above: AncestryDNA's real
    # chromosome-label output for this run determines the expected
    # count, rather than assuming the fixture contains non-conventional
    # codes based on its docstring alone. This still proves the real
    # profiler-to-registry gating wiring: if that wiring were broken,
    # the registry's actual selected count would diverge from this
    # independently-derived expectation even though every unit test
    # (using synthetic, always-matching profiler names) would stay
    # green.
    use_case = build_profile_file_use_case()
    result = use_case.execute(ANCESTRYDNA)

    report = result["report"]
    chromosome_label_inventory = result["profiles"]["chromosome_label_profiler"]
    expected_chromosome_related_count = _expected_chromosome_related_open_question_count(
        chromosome_label_inventory
    )

    related = [question.related_finding_or_profile for question in report.open_questions]

    assert related.count("chromosome_label_profiler") == expected_chromosome_related_count
    assert related.count("genotype_layout_classifier") == 1
    assert related.count(None) == 3
    assert related.count("duplicate_rsid_check") == 1


# ---------------------------------------------------------------------------
# 3. Both real datasets through one composition-root-built use case
# ---------------------------------------------------------------------------


def test_same_composition_root_use_case_processes_both_real_vendor_formats() -> None:
    # A single ProfileFileUseCase instance, built once through the
    # composition root with its default configuration, must correctly
    # accept both real, structurally distinct vendor file layouts --
    # proving the wiring itself (not per-file configuration) is what
    # makes both formats work.
    use_case = build_profile_file_use_case()

    twentythreeandme_result = use_case.execute(TWENTYTHREEANDME)
    ancestrydna_result = use_case.execute(ANCESTRYDNA)

    assert twentythreeandme_result["column_layout"].designated_column_indices == (3,)
    assert ancestrydna_result["column_layout"].designated_column_indices == (3, 4)

    assert (
        twentythreeandme_result["profiles"]["genotype_layout_classifier"].layout_kind
        == "single_column_genotype"
    )
    assert (
        ancestrydna_result["profiles"]["genotype_layout_classifier"].layout_kind
        == "two_column_allele"
    )


# ---------------------------------------------------------------------------
# 4. Failure path: malformed genotype input -> PhenoPredIngestionError
# ---------------------------------------------------------------------------


def test_pipeline_raises_pheno_pred_ingestion_error_for_missing_header_keyword() -> None:
    # This fixture has no comment lines and no line -- header or data --
    # containing the exact "rsid" token the default configuration
    # requires, so HeaderResolver must report form="absent"
    # (resolved_columns=None). ColumnIdentityResolver then rejects that
    # as ColumnIdentityNotResolvedError, and ProfileFileUseCase
    # translates it into a PhenoPredIngestionError carrying file_path
    # context, exactly as documented in profile_file_use_case.py's own
    # docstring and exercised (with a fake collaborator) by
    # test_column_identity_not_resolved_error_translated_to_pheno_pred_ingestion_error
    # in test_profile_file_use_case.py -- this test proves the same
    # translation holds through the real, wired pipeline.
    use_case = build_profile_file_use_case()

    try:
        use_case.execute(MALFORMED_NO_HEADER_KEYWORD)
        raise AssertionError("expected PhenoPredIngestionError")
    except PhenoPredIngestionError as exc:
        assert exc.path == MALFORMED_NO_HEADER_KEYWORD


def test_pipeline_raises_pheno_pred_ingestion_error_for_nonexistent_file() -> None:
    # RawFileLoader raises directly (SourceFileNotFoundError, a
    # PhenoPredIngestionError subclass) before any other pipeline stage
    # runs, when asked to load a file that does not exist on disk.
    use_case = build_profile_file_use_case()
    missing_path = DATA_DIR / "does_not_exist.txt"

    try:
        use_case.execute(missing_path)
        raise AssertionError("expected PhenoPredIngestionError")
    except PhenoPredIngestionError as exc:
        assert exc.path == missing_path


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()