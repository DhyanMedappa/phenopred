# phenopred/application/composition_root.py
"""Application-layer composition root: the single place where concrete
Stage 1 implementations are bound to ProfileFileUseCase's constructor,
per Architecture v1 Section 4/5 ("application/composition_root.py --
the single place where concrete infrastructure implementations are
bound to domain interfaces; isolates wiring so no other module needs
to know concrete classes").

This module performs dependency construction and injection only. It
contains:
    - no file processing,
    - no pipeline execution,
    - no row parsing,
    - no quality-check logic,
    - no biological interpretation,
    - no domain rules of any kind.
It only imports concrete classes and calls their constructors, then
hands the fully assembled ProfileFileUseCase back to its caller (e.g.
a future cli/main.py). It never calls `.execute()` itself.

Configuration status (Architecture v1 Section 10/11): `ConfigProvider`
is named by the architecture but explicitly deferred -- `interfaces.py`
itself documents it as "not yet designed or approved." Per the approved
Stage 1 decision, this module supplies a minimal, temporary
configuration mechanism instead: plain module-level constants, used
only inside this module, as default keyword-argument values on
`build_profile_file_use_case()`. This is not a ConfigProvider
implementation and does not claim to be one -- it exists solely so the
composition root has *some* concrete value to inject into each
component's constructor today, without embedding any such value inside
a domain module (every domain/detection component here still only ever
receives its configuration via constructor injection, exactly as
before). When a real ConfigProvider is later implemented, only this
module's default-sourcing should need to change; the construction
calls themselves would not.

The `_DEFAULT_DESIGNATED_COLUMN_KEYWORDS` default below deliberately
includes both the two-column-allele keyword pair observed in Dataset A
("allele1", "allele2") and the single-combined-genotype keyword
observed in Dataset B ("genotype"). This is a composition-root-level
placeholder value only, never a schema assumption embedded in
ColumnIdentityResolver itself: ColumnIdentityResolver's own,
unmodified logic already treats any configured keyword absent from a
given file's resolved column names as simply not matched (contributing
no index), so supplying a superset of both evidenced layouts' keywords
here does not force an incorrect result for either file layout, and
introduces no fixed-schema assumption into domain code (NFR-5/AD-5).
"""

from __future__ import annotations

from collections.abc import Sequence

from phenopred.application.profile_file_use_case import ProfileFileUseCase
from phenopred.domain.detection.column_identity_resolver import (
    ColumnIdentityResolver,
)
from phenopred.domain.detection.delimiter_detector import DelimiterDetector
from phenopred.domain.detection.encoding_detector import EncodingDetector
from phenopred.domain.detection.header_resolver import HeaderResolver
from phenopred.domain.genomic_profiling.chromosome_label_profiler import (
    ChromosomeLabelProfiler,
)
from phenopred.domain.genomic_profiling.genotype_layout_classifier import (
    GenotypeLayoutClassifier,
)
from phenopred.domain.genomic_profiling.indel_haploid_classifier import (
    IndelHaploidClassifier,
)
from phenopred.domain.ingestion.raw_line_splitter import RawLineSplitter
from phenopred.domain.ingestion.row_parser import RowParser
from phenopred.domain.quality_checks.duplicate_chr_pos_check import (
    DuplicateChrPosCheck,
)
from phenopred.domain.quality_checks.duplicate_header_check import (
    DuplicateHeaderCheck,
)
from phenopred.domain.quality_checks.duplicate_rsid_check import DuplicateRsidCheck
from phenopred.domain.quality_checks.malformed_row_check import MalformedRowCheck
from phenopred.domain.quality_checks.missing_value_scanner import (
    MissingValueScanner,
)
from phenopred.infrastructure.io.raw_file_loader import RawFileLoader

# ---------------------------------------------------------------------------
# Temporary Stage 1 configuration defaults.
#
# Placeholders only, pending a real ConfigProvider (Architecture v1
# Section 10/11, explicitly deferred per interfaces.py). Used exclusively
# as this module's own default keyword-argument values below -- no domain
# or detection component reads these constants directly, or reads
# configuration from anywhere other than its own constructor arguments.
# ---------------------------------------------------------------------------

_DEFAULT_COMMENT_PREFIX = "#"
_DEFAULT_HEADER_KEYWORD = "rsid"
_DEFAULT_DELIMITER_SAMPLE_SIZE = 50
_DEFAULT_RAW_LOADER_SAMPLE_SIZE = 4096
_DEFAULT_RSID_KEYWORD = "rsid"
_DEFAULT_CHROMOSOME_KEYWORD = "chromosome"
_DEFAULT_POSITION_KEYWORD = "position"
_DEFAULT_DESIGNATED_COLUMN_KEYWORDS: tuple[str, ...] = (
    "allele1",
    "allele2",
    "genotype",
)
_DEFAULT_INDEL_TOKENS: tuple[str, ...] = ("II", "DD", "DI")
_DEFAULT_SEX_MITOCHONDRIAL_LABELS: tuple[str, ...] = ("X", "Y", "MT")


def build_profile_file_use_case(
    *,
    comment_prefix: str = _DEFAULT_COMMENT_PREFIX,
    header_keyword: str = _DEFAULT_HEADER_KEYWORD,
    delimiter_sample_size: int = _DEFAULT_DELIMITER_SAMPLE_SIZE,
    raw_loader_sample_size: int = _DEFAULT_RAW_LOADER_SAMPLE_SIZE,
    rsid_keyword: str = _DEFAULT_RSID_KEYWORD,
    chromosome_keyword: str = _DEFAULT_CHROMOSOME_KEYWORD,
    position_keyword: str = _DEFAULT_POSITION_KEYWORD,
    designated_column_keywords: Sequence[str] = _DEFAULT_DESIGNATED_COLUMN_KEYWORDS,
    indel_tokens: Sequence[str] = _DEFAULT_INDEL_TOKENS,
    sex_mitochondrial_labels: Sequence[str] = _DEFAULT_SEX_MITOCHONDRIAL_LABELS,
) -> ProfileFileUseCase:
    """Construct and wire the Stage 1 application object graph.

    This function performs construction and injection only -- it never
    reads a file, never calls `.execute()`, and never runs any pipeline
    stage. Every argument it accepts is a plain configuration value,
    already defaulted from this module's own temporary constants;
    callers (e.g. a future cli/main.py, or a real ConfigProvider-backed
    caller once implemented) may override any of them without this
    function's body changing.

    Args:
        comment_prefix: Injected into RawLineSplitter (FR-1).
        header_keyword: Injected into HeaderResolver (FR-3).
        delimiter_sample_size: Injected into DelimiterDetector (FR-2).
        raw_loader_sample_size: Injected into RawFileLoader (FR-14).
        rsid_keyword: Injected into ColumnIdentityResolver.
        chromosome_keyword: Injected into ColumnIdentityResolver.
        position_keyword: Injected into ColumnIdentityResolver.
        designated_column_keywords: Injected into ColumnIdentityResolver.
        indel_tokens: Injected into IndelHaploidClassifier (FR-12).
        sex_mitochondrial_labels: Injected into IndelHaploidClassifier
            (FR-12).

    Returns:
        A fully constructed ProfileFileUseCase, with every Stage 1
        collaborator injected:
            - file_loader: RawFileLoader
            - line_splitter: RawLineSplitter
            - encoding_detector: EncodingDetector
            - delimiter_detector: DelimiterDetector
            - header_resolver: HeaderResolver
            - column_identity_resolver: ColumnIdentityResolver
            - row_parser: RowParser
            - quality_checks: a name-keyed mapping containing all five
              FR-5..FR-9 checks (malformed_row_check,
              duplicate_header_check, missing_value_scanner,
              duplicate_rsid_check, duplicate_chr_pos_check), matching
              the check names ProfileFileUseCase's own docstring
              already documents it expects.
            - genomic_profilers: a name-keyed mapping containing all
              three FR-10..FR-12 genomic profilers
              (chromosome_label_profiler, genotype_layout_classifier,
              indel_haploid_classifier), matching the profiler names
              ProfileFileUseCase's `_run_genomic_profilers` method
              already looks up.
            - report_builder: None. Reporting is out of Stage 1 scope;
              no ReportBuilder implementation exists in this
              repository to construct. None is the smallest value
              compatible with ProfileFileUseCase's existing,
              unmodified constructor -- it is never called by the
              current, frozen ProfileFileUseCase.execute()
              implementation.
    """
    file_loader = RawFileLoader(sample_size=raw_loader_sample_size)
    line_splitter = RawLineSplitter(comment_prefix=comment_prefix)
    encoding_detector = EncodingDetector()
    delimiter_detector = DelimiterDetector(sample_size=delimiter_sample_size)
    header_resolver = HeaderResolver(header_keyword=header_keyword)
    column_identity_resolver = ColumnIdentityResolver(
        rsid_keyword=rsid_keyword,
        chromosome_keyword=chromosome_keyword,
        position_keyword=position_keyword,
        designated_column_keywords=designated_column_keywords,
    )
    row_parser = RowParser()

    chromosome_label_profiler = ChromosomeLabelProfiler()
    genotype_layout_classifier = GenotypeLayoutClassifier()
    indel_haploid_classifier = IndelHaploidClassifier(
        indel_tokens=indel_tokens,
        sex_mitochondrial_labels=sex_mitochondrial_labels,
    )

    quality_checks = {
        "malformed_row_check": MalformedRowCheck(),
        "duplicate_header_check": DuplicateHeaderCheck(),
        "missing_value_scanner": MissingValueScanner(),
        "duplicate_rsid_check": DuplicateRsidCheck(),
        "duplicate_chr_pos_check": DuplicateChrPosCheck(),
    }

    genomic_profilers = {
        "chromosome_label_profiler": chromosome_label_profiler,
        "genotype_layout_classifier": genotype_layout_classifier,
        "indel_haploid_classifier": indel_haploid_classifier,
    }

    return ProfileFileUseCase(
        file_loader=file_loader,
        line_splitter=line_splitter,
        encoding_detector=encoding_detector,
        delimiter_detector=delimiter_detector,
        header_resolver=header_resolver,
        column_identity_resolver=column_identity_resolver,
        row_parser=row_parser,
        quality_checks=quality_checks,
        genomic_profilers=genomic_profilers,
        report_builder=None,
    )
