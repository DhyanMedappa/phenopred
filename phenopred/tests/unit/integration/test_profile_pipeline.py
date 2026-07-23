# tests/integration/test_profile_pipeline.py
"""Application integration tests for the real, composition-root-assembled
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
every FR-5..FR-9 QualityCheck, and every FR-10..FR-12 GenomicProfiler,
exactly as the composition root assembles them today -- works together
correctly end to end. Individual collaborator algorithms are exhaustively
covered by their own unit-test suites and are not retested here; this
suite verifies only that the assembled pipeline accepts real input and
produces a well-formed result.

Test data (tests/integration/data/):
    - twentythreeandme_v5_sample.txt: a real, byte-faithful excerpt of a
      23andMe v5 raw genotype export (anonymous_genome_v5_build37.txt).
      Every retained line is copied verbatim from the original file;
      only the number of data rows has been reduced (to keep this suite
      fast), while deliberately retaining real rows on chromosomes X, Y,
      and MT, plus real rows carrying each of the "II", "DD", and "DI"
      indel tokens, so FR-10/FR-11/FR-12 all have real, exercised
      evidence in this excerpt.
    - ancestrydna_sample.txt: a real, byte-faithful excerpt of an
      AncestryDNA raw genotype export (AncestryDNA.txt), again with every
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
from phenopred.domain.errors import PhenoPredIngestionError

DATA_DIR = Path(__file__).resolve().parent / "data"

TWENTYTHREEANDME_SAMPLE = DATA_DIR / "twentythreeandme_v5_sample.txt"
ANCESTRYDNA_SAMPLE = DATA_DIR / "ancestrydna_sample.txt"
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


# ---------------------------------------------------------------------------
# 1. 23andMe dataset: full pipeline, real file, composition-root wiring
# ---------------------------------------------------------------------------


def test_23andme_pipeline_executes_successfully_end_to_end() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(TWENTYTHREEANDME_SAMPLE)

    assert result is not None
    assert result["source_path"] == TWENTYTHREEANDME_SAMPLE
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
    result = use_case.execute(TWENTYTHREEANDME_SAMPLE)

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
    result = use_case.execute(TWENTYTHREEANDME_SAMPLE)

    inventory = result["profiles"]["chromosome_label_profiler"]
    observed_labels = {label for label, _ in inventory.label_counts}
    # Real rows on chromosomes 1, X, Y, and MT are present in this excerpt.
    assert {"1", "X", "Y", "MT"}.issubset(observed_labels)


def test_23andme_genotype_layout_profiling_executes() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(TWENTYTHREEANDME_SAMPLE)

    layout_profile = result["profiles"]["genotype_layout_classifier"]
    # Exactly one designated (combined genotype) column -> single_column_genotype.
    assert layout_profile.layout_kind == "single_column_genotype"
    assert len(layout_profile.column_length_distributions) == 1


def test_23andme_indel_haploid_profiling_executes() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(TWENTYTHREEANDME_SAMPLE)

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


# ---------------------------------------------------------------------------
# 2. AncestryDNA dataset: full pipeline, real file, composition-root wiring
# ---------------------------------------------------------------------------


def test_ancestrydna_pipeline_executes_successfully_end_to_end() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(ANCESTRYDNA_SAMPLE)

    assert result is not None
    assert result["source_path"] == ANCESTRYDNA_SAMPLE
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
    result = use_case.execute(ANCESTRYDNA_SAMPLE)

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
    result = use_case.execute(ANCESTRYDNA_SAMPLE)

    inventory = result["profiles"]["chromosome_label_profiler"]
    observed_labels = {label for label, _ in inventory.label_counts}
    # AncestryDNA reports purely numeric chromosome labels (1-26 in this
    # excerpt), never the X/Y/MT convention 23andMe uses.
    assert {"1", "2", "22"}.issubset(observed_labels)
    assert not observed_labels & {"X", "Y", "MT"}


def test_ancestrydna_genotype_layout_classified_as_two_column_allele() -> None:
    use_case = build_profile_file_use_case()
    result = use_case.execute(ANCESTRYDNA_SAMPLE)

    layout_profile = result["profiles"]["genotype_layout_classifier"]
    assert layout_profile.layout_kind == "two_column_allele"
    assert len(layout_profile.column_length_distributions) == 2


def test_ancestrydna_indel_haploid_profiler_reports_not_applicable() -> None:
    # AncestryDNA uses two designated (allele) columns, so FR-12's
    # single-combined-genotype-column applicability gate must report
    # not-applicable for this real file, mirroring
    # test_indel_haploid_classifier.py's own applicability contract.
    use_case = build_profile_file_use_case()
    result = use_case.execute(ANCESTRYDNA_SAMPLE)

    indel_profile = result["profiles"]["indel_haploid_classifier"]
    assert indel_profile.applicable is False
    assert indel_profile.indel_token_counts == ()
    assert indel_profile.haploid_count == 0
    assert indel_profile.diploid_count == 0


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

    twentythreeandme_result = use_case.execute(TWENTYTHREEANDME_SAMPLE)
    ancestrydna_result = use_case.execute(ANCESTRYDNA_SAMPLE)

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
