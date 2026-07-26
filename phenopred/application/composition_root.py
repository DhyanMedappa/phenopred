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
is named by the architecture but its Protocol shape is still explicitly
deferred -- `interfaces.py` itself documents it as "not yet designed or
approved," and this module does not add that Protocol. What Section
10/11 already do name concretely is this module's own V1 concrete
implementer: "ConfigProvider | ... | Implemented by (V1): ConfigLoader
(infrastructure)". `build_profile_file_use_case()` therefore resolves
its comment_prefix/header_keyword/delimiter_sample_size/
raw_loader_sample_size keyword arguments -- the exact configuration
surface Section 11 names -- via
`phenopred.infrastructure.config.config_loader.ConfigLoader`, given an
optional `config_path` plus this function's own explicit keyword
overrides (Section 11's "plus command-line overrides", satisfied here
at this function's own call boundary; wiring an actual `--config` CLI
flag into cli/main.py remains separate, later work, exactly mirroring
how infrastructure/io/report_writer.py was implemented before
composition_root.py was wired to inject it). ConfigLoader's own
defaults are identical to this module's former hardcoded constants, so
every existing zero-argument caller's behavior is unchanged.

This module's own "no file processing" self-description (above) needs
one narrow, explicit exception because of this: when `config_path` is
supplied, `build_profile_file_use_case()` does perform file I/O, via
the injected ConfigLoader, to read that configuration file, propagating
ConfigLoadError uncaught if it cannot be read. This is deliberately
scoped to configuration only -- Section 11's own words describe
configuration as "loaded once per run ... and passed into the
composition root," a wiring-time concern, categorically different from
the per-file genotype-file reads and report writes this module still
never performs itself; RawFileLoader remains the sole component that
reads a source genotype file, and JsonReportSerializer remains the sole
component that writes a report artifact, both still only ever invoked
later, by ProfileFileUseCase.execute(), never by this module.

The remaining six keyword arguments (rsid_keyword, chromosome_keyword,
position_keyword, designated_column_keywords, indel_tokens,
sex_mitochondrial_labels) are NOT part of ConfigLoader's scope --
Section 11 does not name any of them, and extending configurability to
them would risk exactly the "Configuration surface area creep"
Architecture v1 Section 17 warns against. They remain exactly what they
were before this change: plain module-level constants, used only inside
this module, as default keyword-argument values.

`configure_logging()` (below, separate from `build_profile_file_use_case()`)
similarly binds infrastructure/logging/logger_setup.py's LoggerSetup --
Section 5's other named V1 component -- into this module, mirroring
ConfigLoader's own binding. It is intentionally a separate function
rather than a side effect folded into `build_profile_file_use_case()`:
configuring the "phenopred" logger is a process-wide, ambient side
effect (Section 2's "Cross-cutting (used by all layers): Configuration
* Logging * Error Handling"), not an object constructed and injected
into ProfileFileUseCase, so it does not belong inside a function whose
own contract is "construction and injection only." cli/main.py calls
this function once, explicitly, before calling
`build_profile_file_use_case()`. `main.py` still never imports an
infrastructure module directly (ConfigLoader and LoggerSetup remain
known only to this module), preserving Section 3's layer table
("Presentation (CLI) | ... | Depends on: Application layer") --
including for the `--config` flag added alongside
`resolve_output_location()` below, which threads a user-supplied
config path into all three of this module's functions without
`main.py` ever needing to construct or reference ConfigLoader or
LoggerSetup by name.

`resolve_output_location()` (below) closes Section 5's cli/main.py
responsibility ("Parses command-line arguments (input file path(s),
optional config path)") together with a new `--config` flag now added
to cli/main.py: it resolves `RunConfig.output_location` (Section 11)
via the same ConfigLoader precedence as every other value here, so
cli/main.py's own default-output-path computation can honor it without
importing ConfigLoader itself. Calling `configure_logging()`,
`build_profile_file_use_case()`, and `resolve_output_location()`
separately means a supplied config file is read up to three times per
CLI invocation -- an accepted, deliberate trade-off (a config file is
small; this is a single CLI run, not a hot loop) rather than merging
three genuinely distinct responsibilities (logging setup, pipeline
construction, output-path resolution) into one function or introducing
a new bootstrap abstraction this architecture does not name.

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

import logging
from collections.abc import Sequence
from pathlib import Path

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
from phenopred.domain.reporting.open_question_registry import (
    OpenQuestionRegistry,
)
from phenopred.domain.reporting.report_builder import ReportBuilder
from phenopred.infrastructure.config.config_loader import (
    ConfigLoader,
    ConfigLoadError,  # re-exported: see resolve_output_location()'s and
                      # this module's own docstring -- cli/main.py catches
                      # this via `from ...composition_root import
                      # ConfigLoadError`, never importing infrastructure
                      # directly, per Section 3's layer table.
)
from phenopred.infrastructure.io.raw_file_loader import RawFileLoader
from phenopred.infrastructure.io.report_writer import JsonReportSerializer
from phenopred.infrastructure.logging.logger_setup import LoggerSetup

# ---------------------------------------------------------------------------
# Temporary Stage 1 configuration defaults -- narrowed scope.
#
# comment_prefix, header_keyword, delimiter_sample_size, and
# raw_loader_sample_size are no longer defaulted here: they are exactly
# Section 11's named configuration surface, now resolved via
# ConfigLoader (see the module docstring above). The six constants below
# remain, unchanged, exactly as before -- Section 11 does not name any
# of them, so they stay outside ConfigLoader's scope (see module
# docstring); no domain or detection component reads these constants
# directly, or reads configuration from anywhere other than its own
# constructor arguments.
# ---------------------------------------------------------------------------

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
    config_path: Path | str | None = None,
    comment_prefix: str | None = None,
    header_keyword: str | None = None,
    delimiter_sample_size: int | None = None,
    raw_loader_sample_size: int | None = None,
    rsid_keyword: str = _DEFAULT_RSID_KEYWORD,
    chromosome_keyword: str = _DEFAULT_CHROMOSOME_KEYWORD,
    position_keyword: str = _DEFAULT_POSITION_KEYWORD,
    designated_column_keywords: Sequence[str] = _DEFAULT_DESIGNATED_COLUMN_KEYWORDS,
    indel_tokens: Sequence[str] = _DEFAULT_INDEL_TOKENS,
    sex_mitochondrial_labels: Sequence[str] = _DEFAULT_SEX_MITOCHONDRIAL_LABELS,
) -> ProfileFileUseCase:
    """Construct and wire the Stage 1 application object graph.

    This function performs construction and injection only -- it never
    calls `.execute()` and never runs any pipeline stage. It does now
    perform one narrow category of file I/O of its own: when
    `config_path` is supplied, it is passed to ConfigLoader, which reads
    that configuration file (see this module's own docstring for why
    this is a deliberate, narrowly-scoped exception, confined to
    configuration only -- RawFileLoader remains the sole component that
    ever reads a source *genotype* file).

    comment_prefix, header_keyword, delimiter_sample_size, and
    raw_loader_sample_size are resolved via
    `ConfigLoader.load(config_path, comment_prefix=comment_prefix, ...)`
    with that method's own documented precedence: an explicit,
    non-None argument to this function always wins; otherwise the
    configuration file's own value (if `config_path` was given and the
    key is present) is used; otherwise ConfigLoader's own default is
    used -- identical to this module's former hardcoded constants, so
    every existing zero-argument caller's behavior is unchanged. The
    remaining six keyword arguments are unaffected by this change and
    keep their own prior, directly-defaulted behavior exactly as
    before.

    Args:
        config_path: An optional path to a JSON configuration file
            (Section 11's "simple, human-readable configuration file"
            assumption), passed through to ConfigLoader. When None (the
            default), no file is read and every ConfigLoader-scoped
            argument below falls back to its own explicit value (if
            given) or ConfigLoader's own default.
        comment_prefix: Injected into RawLineSplitter (FR-1). An
            explicit override for this run; see precedence above.
        header_keyword: Injected into HeaderResolver (FR-3). An
            explicit override for this run; see precedence above.
        delimiter_sample_size: Injected into DelimiterDetector (FR-2).
            An explicit override for this run; see precedence above.
        raw_loader_sample_size: Injected into RawFileLoader (FR-14). An
            explicit override for this run; see precedence above.
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
            - report_builder: a ReportBuilder instance, constructed with
              an OpenQuestionRegistry instance injected, per the frozen
              Reporting Architecture. ReportBuilder assembles the
              ProfilingReport for each file from that file's already-
              computed Findings, Profiles, ColumnCountDistribution, and
              other metadata; OpenQuestionRegistry selects the subset of
              the SRS's fixed, registered open questions (SRS Section
              8.2, RISK-1 through RISK-9) applicable to that same
              Finding/Profile data. Neither collaborator takes any
              per-run configuration value, so neither is exposed as a
              parameter of this function.
            - report_serializer: a JsonReportSerializer instance (Version
              1's sole ReportSerializer implementation, per AD-3 /
              Section 9/10), constructor-injected into
              ProfileFileUseCase per the frozen Report Persistence
              design step. Stateless -- it takes no per-run
              configuration value of its own, since `output_path` is
              supplied per `ProfileFileUseCase.execute()` call by that
              call's own caller (e.g. cli/main.py), not by this
              function -- so it is likewise not exposed as a parameter
              here, mirroring `open_question_registry`/`report_builder`
              immediately above.

    Raises:
        ConfigLoadError: If `config_path` is supplied but does not
            exist, is not a regular file, cannot be read, is not valid
            JSON, is not a JSON object at its top level, or contains a
            key outside ConfigLoader's own known configuration surface
            (phenopred.infrastructure.config.config_loader). Propagates
            uncaught -- this function performs no error translation of
            its own, mirroring its own "no domain rules" scope.
    """
    run_config = ConfigLoader().load(
        config_path,
        comment_prefix=comment_prefix,
        header_keyword=header_keyword,
        delimiter_sample_size=delimiter_sample_size,
        raw_loader_sample_size=raw_loader_sample_size,
    )

    file_loader = RawFileLoader(sample_size=run_config.raw_loader_sample_size)
    line_splitter = RawLineSplitter(comment_prefix=run_config.comment_prefix)
    encoding_detector = EncodingDetector()
    delimiter_detector = DelimiterDetector(
        sample_size=run_config.delimiter_sample_size
    )
    header_resolver = HeaderResolver(header_keyword=run_config.header_keyword)
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

    open_question_registry = OpenQuestionRegistry()
    report_builder = ReportBuilder(open_question_registry=open_question_registry)

    report_serializer = JsonReportSerializer()

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
        report_builder=report_builder,
        report_serializer=report_serializer,
    )


def configure_logging(
    *,
    config_path: Path | str | None = None,
    level: str | None = None,
) -> logging.Logger:
    """Resolve `logging_level` via ConfigLoader and configure the
    "phenopred" logger via LoggerSetup (Architecture v1 Section 5/12).

    This function performs no pipeline construction and returns no
    ProfileFileUseCase -- it is entirely separate from
    `build_profile_file_use_case()` above, and touches no domain or
    application collaborator. Its only effect is the same kind of
    narrow, deliberate file-I/O exception `build_profile_file_use_case()`
    already documents for `config_path` (see this module's own
    docstring): when `config_path` is supplied, ConfigLoader reads that
    file to resolve `logging_level`, propagating ConfigLoadError
    uncaught if it cannot be read.

    Callers (in practice, cli/main.py, exactly once, before calling
    `build_profile_file_use_case()`) pass through cli/main.py's own
    `--config` flag value as `config_path`; `level` still has no CLI
    flag of its own and exists only for symmetry with
    `build_profile_file_use_case()`'s own explicit-override parameters
    and for direct testability.

    Args:
        config_path: An optional path to a JSON configuration file,
            passed through to ConfigLoader exactly as
            `build_profile_file_use_case()`'s own `config_path` is.
            When None (the default), no file is read.
        level: An explicit logging-level override for this run, taking
            precedence over both the configuration file's own value (if
            any) and ConfigLoader's own default ("INFO"), mirroring
            ConfigLoader.load()'s own documented precedence exactly.

    Returns:
        The configured "phenopred" `logging.Logger`, as returned by
        LoggerSetup.configure() -- a convenience for callers/tests;
        every other module in this codebase still obtains its own
        logger independently via `logging.getLogger(__name__)`.

    Raises:
        ConfigLoadError: If `config_path` is supplied but cannot be
            read/parsed/validated (see ConfigLoader.load()'s own
            documented conditions). Propagates uncaught.
        ValueError: If the resolved logging level is not one of
            LoggerSetup's recognized standard level names. Unreachable
            when called with no arguments, since ConfigLoader's own
            default ("INFO") is always valid.
    """
    run_config = ConfigLoader().load(config_path, logging_level=level)
    return LoggerSetup().configure(level=run_config.logging_level)


def resolve_output_location(
    *,
    config_path: Path | str | None = None,
    output_location: str | None = None,
) -> str | None:
    """Resolve `output_location` via ConfigLoader (Architecture v1
    Section 5/11).

    This function performs no pipeline construction, no logging
    configuration, and touches no domain or application collaborator --
    it is entirely separate from `build_profile_file_use_case()` and
    `configure_logging()` above, mirroring their identical shape.
    Resolving *where* to write a report when cli/main.py's own
    `--output` flag is omitted is still that module's own "argument
    parsing" responsibility (per its own docstring); this function only
    supplies the one additional, config-file-sourced input
    (`output_location`) that computation may now optionally consult,
    without cli/main.py needing to import ConfigLoader itself.

    Args:
        config_path: An optional path to a JSON configuration file,
            passed through to ConfigLoader exactly as
            `build_profile_file_use_case()`'s own `config_path` is.
            When None (the default), no file is read.
        output_location: An explicit override for this run, taking
            precedence over both the configuration file's own value (if
            any) and ConfigLoader's own default (None), mirroring
            ConfigLoader.load()'s own documented precedence exactly.
            Exists for symmetry/testability; cli/main.py does not expose
            a separate CLI flag for this specific override today (its
            own `--output` flag already supersedes any computed default
            path entirely, at a different point in cli/main.py's own
            logic).

    Returns:
        The resolved `output_location` string, or None when no config
        file was supplied, the supplied config file does not set this
        key, and no explicit override was given -- ConfigLoader's own
        documented default for this field.

    Raises:
        ConfigLoadError: If `config_path` is supplied but cannot be
            read/parsed/validated (see ConfigLoader.load()'s own
            documented conditions). Propagates uncaught.
    """
    run_config = ConfigLoader().load(config_path, output_location=output_location)
    return run_config.output_location