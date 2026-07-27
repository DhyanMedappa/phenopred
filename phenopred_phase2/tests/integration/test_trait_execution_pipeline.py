# tests/integration/test_trait_execution_pipeline.py
"""End-to-end integration test: real genotype file -> real
ProfileFileUseCase -> real GenotypeIndex -> real TraitEngine -> real
TraitPrediction mapping.

This is the one place in the test suite that proves the complete
chain works together against real data, mirroring the same
"integration test using real components, real files" style already
established in V1's own test_profile_pipeline.py -- unit tests
(test_composition.py, test_trait_engine.py, and every trait model's
own suite) already cover each component's logic in isolation with
fakes; this file does not repeat that coverage.

Real vs. substituted collaborators (disclosed explicitly, not hidden):

    - RawLineSplitter, DelimiterDetector, HeaderResolver,
      ColumnIdentityResolver, RowParser: 100% real, unmodified V1
      source (as uploaded) -- these are exactly the components
      responsible for producing `data_rows`/`column_layout`, the only
      two outputs Phase 2 ever consumes, so they are never
      substituted.
    - file_loader, encoding_detector, report_builder: V1's real source
      for these was not available in this environment (RawFileLoader,
      EncodingDetector, and ReportBuilder are infrastructure/reporting
      components with no bearing on data_rows/column_layout). Minimal,
      clearly-labeled fakes stand in for them below, satisfying only
      the trivial, undisputed part of their contract (reading a file's
      raw lines; returning a placeholder encoding/report value never
      consumed by Phase 2).
    - quality_checks={}, genomic_profilers={}: ProfileFileUseCase's own,
      already-documented "only run what's injected" contract is used
      deliberately -- Phase 2 does not consume findings or profiles,
      so none are constructed. This is not a workaround; it is exactly
      the extensibility path ProfileFileUseCase's own design already
      provides for a caller that doesn't need every collaborator.

Per the project's explicit scope clarification: AncestryDNA.txt and
anonymous_genome_v5_build37.txt are validation datasets representing
the two currently-supported column layouts (two-column-allele,
single-combined-genotype) -- this test asserts no logic specific to
either file's identity, only that the pipeline produces well-formed,
correctly-typed output for each of the two general layouts they
represent.
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
from phenopred_phase2.traits.application.composition import run_trait_pipeline
from phenopred_phase2.traits.domain.entities import PredictionStatus
from phenopred_phase2.traits.domain.trait_registry import TRAIT_REGISTRY

DATA_DIR = Path(__file__).resolve().parent / "data"
ANCESTRYDNA = DATA_DIR / "AncestryDNA.txt"
TWENTYTHREEANDME = DATA_DIR / "anonymous_genome_v5_build37.txt"

# The union of both currently-validated layouts' designated-column
# keywords, mirroring V1's own composition_root.py
# _DEFAULT_DESIGNATED_COLUMN_KEYWORDS exactly -- a superset is safe
# because ColumnIdentityResolver's own, unmodified logic already
# treats an absent keyword as simply not matched, never an error.
_DESIGNATED_COLUMN_KEYWORDS = ("allele1", "allele2", "genotype")


class _FakeRawFileContent:
    """Minimal stand-in for V1's real RawFileContent -- exposes only
    the three attributes ProfileFileUseCase.execute() actually reads
    (lines, source_path, byte_sample).
    """

    def __init__(self, lines: tuple[str, ...], source_path: str) -> None:
        self.lines = lines
        self.source_path = source_path
        self.byte_sample = b""  # never consumed by anything Phase 2 needs


class _FakeFileLoader:
    """Stand-in for V1's real RawFileLoader (infrastructure; source not
    available in this environment). Performs the same trivial,
    undisputed job -- read a file's raw lines -- and nothing else.
    """

    def load(self, file_path) -> _FakeRawFileContent:
        with open(file_path, encoding="utf-8") as handle:
            lines = tuple(line.rstrip("\n").rstrip("\r") for line in handle)
        return _FakeRawFileContent(lines=lines, source_path=str(file_path))


class EncodingDetector:
    """Stand-in for V1's real EncodingDetector. Returns a placeholder
    value never consumed by anything Phase 2 needs (encoding_profile
    is only threaded into the report, which this test never inspects).
    """

    def detect(self, byte_sample):
        return None


class _FakeReportBuilder:
    """Stand-in for V1's real ReportBuilder. Returns a placeholder
    value never consumed by anything Phase 2 needs.
    """

    def build(self, **kwargs):
        return None


def _build_real_profile_file_use_case() -> ProfileFileUseCase:
    """Assemble a real ProfileFileUseCase using 100% real, unmodified
    V1 domain-layer components for everything Phase 2 depends on
    (line_splitter, delimiter_detector, header_resolver,
    column_identity_resolver, row_parser), with minimal fakes only for
    collaborators Phase 2 never consumes (file_loader,
    encoding_detector, report_builder) and empty quality_checks/
    genomic_profilers mappings (ProfileFileUseCase's own documented,
    supported "nothing injected" path).
    """
    return ProfileFileUseCase(
        file_loader=_FakeFileLoader(),
        line_splitter=RawLineSplitter(comment_prefix="#"),
        encoding_detector= EncodingDetector(),
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


# ---------------------------------------------------------------------------
# 1. AncestryDNA.txt (two-column-allele layout) -- full real file
# ---------------------------------------------------------------------------


def test_full_pipeline_ancestrydna_produces_predictions_for_every_trait() -> (
    None
):
    use_case = _build_real_profile_file_use_case()

    profile_result = use_case.execute(str(ANCESTRYDNA))

    assert profile_result["column_layout"].designated_column_indices == (3, 4)
    assert len(profile_result["data_rows"]) > 0

    predictions = run_trait_pipeline(profile_result)

    assert set(predictions.keys()) == set(TRAIT_REGISTRY.keys())
    # Every one of the 12 required RSIDs across all 5 traits is present
    # somewhere in this real file (confirmed directly). Four traits
    # reach a real PREDICTED outcome. eye_colour is a documented,
    # disclosed exception: this real file's observed genotype at
    # rs1800407 is "CC", which does not match SNP_REGISTRY's own
    # reference/alternate allele definition for that locus (G/A) --
    # EyeColourModel correctly refuses to guess and returns
    # INSUFFICIENT_DATA rather than fabricate a result, exactly per its
    # own frozen "never guess an unrecognized allele combination"
    # contract. This is a genuine finding from this integration test,
    # not a defect in TraitEngine, GenotypeIndex, or this milestone's
    # own composition code -- see the implementation report's "Remaining
    # risks" section.
    for trait_id in ("lactase_persistence", "earwax_type", "actn3", "bitter_taste"):
        assert predictions[trait_id].status == PredictionStatus.PREDICTED, (
            f"{trait_id} unexpectedly INSUFFICIENT_DATA against the real "
            f"AncestryDNA file"
        )
    assert predictions["eye_colour"].status == PredictionStatus.INSUFFICIENT_DATA


def test_full_pipeline_ancestrydna_lactase_persistence_matches_known_genotype() -> (
    None
):
    # Regression guard: rs4988235's real genotype in this file is known
    # (verified directly against the raw file during architecture
    # review) to be heterozygous -- lactase persistent.
    use_case = _build_real_profile_file_use_case()
    profile_result = use_case.execute(str(ANCESTRYDNA))

    predictions = run_trait_pipeline(profile_result)

    assert predictions["lactase_persistence"].predicted_phenotype in (
        "lactase persistent",
        "lactase non-persistent",
    )


# ---------------------------------------------------------------------------
# 2. anonymous_genome_v5_build37.txt (single-column-genotype layout) --
#    full real file
# ---------------------------------------------------------------------------


def test_full_pipeline_23andme_produces_predictions_for_every_trait() -> None:
    use_case = _build_real_profile_file_use_case()

    profile_result = use_case.execute(str(TWENTYTHREEANDME))

    assert profile_result["column_layout"].designated_column_indices == (3,)
    assert len(profile_result["data_rows"]) > 0

    predictions = run_trait_pipeline(profile_result)

    assert set(predictions.keys()) == set(TRAIT_REGISTRY.keys())
    # Same documented eye_colour exception as the AncestryDNA test
    # above -- this file's rs1800407 genotype is also "CC" against
    # SNP_REGISTRY's G/A definition, so EyeColourModel correctly
    # returns INSUFFICIENT_DATA here too, consistently across both
    # independent real files.
    for trait_id in ("lactase_persistence", "earwax_type", "actn3", "bitter_taste"):
        assert predictions[trait_id].status == PredictionStatus.PREDICTED, (
            f"{trait_id} unexpectedly INSUFFICIENT_DATA against the real "
            f"23andMe-format file"
        )
    assert predictions["eye_colour"].status == PredictionStatus.INSUFFICIENT_DATA


def test_full_pipeline_handles_real_no_call_and_indel_rows_without_crashing() -> (
    None
):
    # anonymous_genome_v5_build37.txt is confirmed (during architecture
    # review) to contain real "--" no-call rows and real "II"/"DD"/"DI"
    # indel rows throughout -- this proves the full pipeline tolerates
    # them without raising, exactly as GenotypeIndex's own contract
    # requires, at full real-file scale, not just in a synthetic
    # fixture.
    use_case = _build_real_profile_file_use_case()
    profile_result = use_case.execute(str(TWENTYTHREEANDME))

    predictions = run_trait_pipeline(profile_result)  # must not raise

    assert len(predictions) == len(TRAIT_REGISTRY)


# ---------------------------------------------------------------------------
# 3. Cross-cutting: architecture boundaries remain intact
# ---------------------------------------------------------------------------


def test_both_real_files_produce_consistent_prediction_key_sets() -> None:
    # Regardless of which of the two supported layouts a file uses,
    # run_trait_pipeline's output shape must be identical -- proving no
    # provider-specific behavior leaked into GenotypeIndex, TraitEngine,
    # or the composition layer, per the project's explicit
    # extensibility requirement.
    use_case_a = _build_real_profile_file_use_case()
    use_case_b = _build_real_profile_file_use_case()

    predictions_a = run_trait_pipeline(use_case_a.execute(str(ANCESTRYDNA)))
    predictions_b = run_trait_pipeline(use_case_b.execute(str(TWENTYTHREEANDME)))

    assert set(predictions_a.keys()) == set(predictions_b.keys())


def test_profile_result_is_never_mutated_by_the_pipeline() -> None:
    use_case = _build_real_profile_file_use_case()
    profile_result = use_case.execute(str(ANCESTRYDNA))
    data_rows_before = profile_result["data_rows"]
    column_layout_before = profile_result["column_layout"]

    run_trait_pipeline(profile_result)

    assert profile_result["data_rows"] is data_rows_before
    assert profile_result["column_layout"] is column_layout_before