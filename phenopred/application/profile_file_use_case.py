"""Application layer use case for orchestrating the full PhenoPred file profiling pipeline.

Coordinates ConfigLoader, LoggerSetup, domain services, and ReportWriter per Architecture V1 Section 5.
Enforces dependency inversion via domain interfaces. Contains no domain logic or infrastructure concerns.
"""

from __future__ import annotations

import logging

from phenopred.domain.detection.column_identity_resolver import (
    ColumnIdentityNotResolvedError,
)
from phenopred.domain.detection.delimiter_detector import DelimiterNotDetectedError
from phenopred.domain.errors import PhenoPredIngestionError
from phenopred.domain.value_objects import (
    ChrPosColumnIndices,
    GenotypeChromosomeColumnIndices,
)

logger = logging.getLogger(__name__)


class ProfileFileUseCase:
    """
    Application-layer orchestrator for profiling a single genotype file.

    This class coordinates domain services and infrastructure adapters.
    It contains no domain logic.

    `quality_checks` is expected to be a mapping of check name to an
    already-constructed check instance, using the check names introduced
    by their own modules (e.g. "malformed_row_check",
    "duplicate_header_check", "missing_value_scanner",
    "duplicate_rsid_check", "duplicate_chr_pos_check"). This orchestrator
    does not construct, name, or validate that mapping's contents beyond
    looking a given name up in it; the mapping itself is supplied by the
    composition root, per Architecture v1 Section 5.

    `report_serializer` is an optional, additive collaborator supporting
    the Report Persistence design step (Architecture v1 Section 9/10,
    AD-3): Table 2's own text already names "... build report ->
    serialize" as this orchestrator's final pipeline step, and Table 4
    already documents ReportSerializer as "invoked by ProfileFileUseCase
    via the composition root". It defaults to None so that every
    already-approved caller of this constructor -- including every
    existing unit test's hand-written fakes, none of which supply a
    ReportSerializer -- continues to construct and execute exactly as
    before; persistence is only attempted when both a `report_serializer`
    was injected at construction time and an `output_path` is supplied
    to a given `execute()` call (see `execute()`'s own docstring).

    Per Architecture v1 Section 12: `execute()` logs, at INFO, the file
    identifier (path) being profiled, exactly once, at the very start
    of each call -- this is the "file identifier" Section 12 names for
    per-file log correlation. Every individual QualityCheck/
    GenomicProfiler still logs only its own name and a count-only
    summary (never a file identifier itself, since none of their own,
    already-approved method signatures accept one); combined with this
    orchestrator's one file-identifying INFO line at the start, and per
    Architecture v1's own per-file-independence principle (FR-15/CON-3
    -- only one file is ever profiled per run), every subsequent log
    line in the same run is unambiguously attributable to this file
    without requiring any check/profiler signature change.
    """

    def __init__(
        self,
        file_loader,
        line_splitter,
        encoding_detector,
        delimiter_detector,
        header_resolver,
        column_identity_resolver,
        row_parser,
        quality_checks,
        genomic_profilers,
        report_builder,
        report_serializer=None,
    ):
        self._file_loader = file_loader
        self._line_splitter = line_splitter
        self._encoding_detector = encoding_detector
        self._delimiter_detector = delimiter_detector
        self._header_resolver = header_resolver
        self._column_identity_resolver = column_identity_resolver
        self._row_parser = row_parser
        self._quality_checks = quality_checks
        self._genomic_profilers = genomic_profilers
        self._report_builder = report_builder
        self._report_serializer = report_serializer

    def execute(self, file_path, output_path=None):
        """
        Execute the profiling workflow for one input file, through the
        full pipeline (load, structural detection, column identity
        resolution, row parsing, quality checks FR-5 through FR-9,
        genomic profiling FR-10 through FR-12, reporting, and -- only
        when both a `report_serializer` was injected at construction
        time and `output_path` is supplied here -- persistence).

        Pipeline order:

        Load
        ↓
        Detect encoding
        ↓
        Split comments/data
        ↓
        Detect delimiter
        ↓
        Resolve header
        ↓
        Resolve column identity
        ↓
        Parse rows
        ↓
        Run quality checks
        ↓
        Run genomic profilers
        ↓
        Build report (ReportBuilder)

        Args:
            file_path: Path to the single source file to profile.
            output_path: Optional destination for the serialized report
                artifact, forwarded unaltered to the injected
                `report_serializer.serialize(report, output_path)` (per
                Architecture v1 Section 11, output_location is a
                per-run configuration concern resolved by the caller --
                this orchestrator never computes or defaults a
                destination itself). Has no effect when
                `report_serializer` was not supplied at construction
                time. When `report_serializer` was supplied but
                `output_path` is None, persistence is simply not
                attempted for this call (no error) and
                `report_artifact_path` is not added to the returned
                dict, preserving this orchestrator's existing dict
                shape for every caller that does not opt into
                persistence.

        Returns:
            A plain dict of intermediate pipeline results for this file,
            for consumption by the next application stage:
                - source_path
                - encoding_profile
                - comment_block
                - delimiter
                - header_info
                - column_layout
                - data_rows
                - findings: dict of check_name -> Finding, for every
                  quality check present in the injected `quality_checks`
                  mapping.
                - skipped_quality_checks: dict of check_name -> reason,
                  reserved for any quality check this orchestrator could
                  not run for a reason other than simply not being
                  injected. Currently always empty, since
                  ColumnIdentityResolver resolves every column-identity
                  context FR-6/FR-8/FR-9 require before quality checks
                  run.
                - profiles: dict of profiler_name -> the corresponding
                  genomic-notation value object (ChromosomeLabelInventory,
                  GenotypeLayoutProfile, or IndelHaploidProfile), for
                  every genomic profiler present in the injected
                  `genomic_profilers` mapping.
                - column_count_distribution: the ColumnCountDistribution
                  (OUT-5) produced by malformed_row_check's
                  `column_count_distribution(data_rows)` method, or None
                  when malformed_row_check is not present in the
                  injected `quality_checks` mapping. Never recomputed
                  here -- this orchestrator retrieves the same
                  malformed_row_check collaborator used during quality-check 
                  execution and calls its approved column_count_distribution 
                  method.
                  
                - report: the ProfilingReport assembled by the injected
                  `report_builder` from this file's `findings`,
                  `profiles`, `column_count_distribution`, and other
                  already-computed metadata above. Assembly (ordering,
                  open-question selection) is entirely `report_builder`'s
                  own responsibility; this orchestrator only supplies
                  already-computed inputs to it.
                - report_artifact_path: the reference returned by the
                  injected `report_serializer.serialize(report,
                  output_path)`, present in this dict only when a
                  `report_serializer` was supplied at construction time
                  (absent otherwise, so this key never appears for any
                  caller that did not opt into persistence). When a
                  `report_serializer` is present but this call's
                  `output_path` argument is None, this key is still
                  present but its value is None, since persistence was
                  not attempted for this call. This orchestrator never
                  computes, converts, or interprets this value itself
                  -- it is exactly what `report_serializer` returned.

        Raises:
            PhenoPredIngestionError (or one of its subclasses): if the
            file cannot be loaded (raised directly by file_loader); if
            no delimiter can be confidently detected (this orchestrator
            catches DelimiterNotDetectedError -- a detector-local signal
            owned by DelimiterDetector -- and re-raises it as a
            PhenoPredIngestionError carrying file_path context, per the
            exception-ownership contract documented in
            delimiter_detector.py); or if column identity cannot be
            resolved (this orchestrator catches
            ColumnIdentityNotResolvedError -- a resolver-local signal
            owned by ColumnIdentityResolver -- and re-raises it as a
            PhenoPredIngestionError carrying file_path context, per the
            identical exception-ownership contract documented in
            column_identity_resolver.py).
        """
        logger.info("Profiling file: path=%s", file_path)

        raw_content = self._file_loader.load(file_path)

        encoding_profile = self._encoding_detector.detect(raw_content.byte_sample)

        comment_block, candidate_data_lines = self._line_splitter.split(
            raw_content.lines
        )

        try:
            delimiter = self._delimiter_detector.detect(candidate_data_lines)
        except DelimiterNotDetectedError as exc:
            raise PhenoPredIngestionError(str(exc), path=file_path) from exc

        header_info = self._header_resolver.detect(
            comment_block, candidate_data_lines, delimiter
        )

        try:
            column_layout = self._column_identity_resolver.detect(header_info)
        except ColumnIdentityNotResolvedError as exc:
            raise PhenoPredIngestionError(str(exc), path=file_path) from exc

        # Per Architecture v1 Section 6 step 5: the header line is
        # excluded from the effective data rows only when it was found
        # as an uncommented row -- a commented-only or absent header
        # never removes a data line.
        effective_data_lines = candidate_data_lines
        if header_info.form == "uncommented_row":
            effective_data_lines = candidate_data_lines[1:]

        data_rows = self._row_parser.parse(effective_data_lines, delimiter)

        findings, skipped_quality_checks = self._run_quality_checks(
            data_rows, header_info, column_layout
        )

        profiles = self._run_genomic_profilers(data_rows, column_layout)

        row_count = len(data_rows)

        malformed_row_check = self._quality_checks.get("malformed_row_check")
        column_count_distribution = None
        if malformed_row_check is not None:
            column_count_distribution = (
                malformed_row_check.column_count_distribution(data_rows)
            )

        report = self._report_builder.build(
            source_path=raw_content.source_path,
            comment_block=comment_block,
            encoding_profile=encoding_profile,
            delimiter=delimiter,
            header_info=header_info,
            row_count=row_count,
            column_count_distribution=column_count_distribution,
            findings=findings,
            profiles=profiles,
        )

        result = {
            "source_path": raw_content.source_path,
            "encoding_profile": encoding_profile,
            "comment_block": comment_block,
            "delimiter": delimiter,
            "header_info": header_info,
            "column_layout": column_layout,
            "data_rows": data_rows,
            "findings": findings,
            "skipped_quality_checks": skipped_quality_checks,
            "profiles": profiles,
            "column_count_distribution": column_count_distribution,
            "report": report,
        }

        # Persistence (Architecture v1 Section 9/10, AD-3) is entirely
        # optional and additive: only attempted when this instance was
        # constructed with a `report_serializer`, and only when this
        # call was given an `output_path`. `report_artifact_path` is
        # therefore only ever added to `result` when a serializer was
        # injected, preserving this method's exact prior return-dict
        # shape for every caller that does not opt in.
        if self._report_serializer is not None:
            report_artifact_path = None
            if output_path is not None:
                report_artifact_path = self._report_serializer.serialize(
                    report, output_path
                )
            result["report_artifact_path"] = report_artifact_path

        return result

    def _run_quality_checks(self, data_rows, header_info, column_layout):
        """Run every quality check present in `self._quality_checks`,
        using each check's own, already-approved calling contract.

        Args:
            data_rows: The parsed DataRow collection for this file.
            header_info: The already-resolved HeaderInfo for this file,
                used only by duplicate_header_check.
            column_layout: The already-resolved ColumnLayout for this
                file (the output of ColumnIdentityResolver), supplying
                the column-identity context missing_value_scanner,
                duplicate_rsid_check, and duplicate_chr_pos_check each
                require.

        Returns:
            A 2-tuple of (findings, skipped_quality_checks) dicts.
            `findings` maps check_name -> Finding for every check
            present in `self._quality_checks`. `skipped_quality_checks`
            is reserved for a check present in the mapping that could
            not be run for a reason other than simply not being
            injected; it is currently always empty, since
            column_layout already supplies every context value FR-6,
            FR-8, and FR-9 require.
        """
        findings = {}
        skipped_quality_checks = {}

        malformed_row_check = self._quality_checks.get("malformed_row_check")
        if malformed_row_check is not None:
            findings["malformed_row_check"] = malformed_row_check.check(data_rows)

        duplicate_header_check = self._quality_checks.get("duplicate_header_check")
        if duplicate_header_check is not None:
            findings["duplicate_header_check"] = duplicate_header_check.check(
                data_rows, header_info
            )

        missing_value_scanner = self._quality_checks.get("missing_value_scanner")
        if missing_value_scanner is not None:
            findings["missing_value_scanner"] = missing_value_scanner.check(
                data_rows, column_layout.designated_column_indices
            )

        duplicate_rsid_check = self._quality_checks.get("duplicate_rsid_check")
        if duplicate_rsid_check is not None:
            findings["duplicate_rsid_check"] = duplicate_rsid_check.check(
                data_rows, column_layout.rsid_column_index
            )

        duplicate_chr_pos_check = self._quality_checks.get("duplicate_chr_pos_check")
        if duplicate_chr_pos_check is not None:
            findings["duplicate_chr_pos_check"] = duplicate_chr_pos_check.check(
                data_rows,
                ChrPosColumnIndices(
                    chromosome_column_index=column_layout.chromosome_column_index,
                    position_column_index=column_layout.position_column_index,
                ),
            )

        return findings, skipped_quality_checks

    def _run_genomic_profilers(self, data_rows, column_layout):
        """Run every genomic profiler present in `self._genomic_profilers`,
        using each profiler's own, already-approved calling contract.

        Args:
            data_rows: The parsed DataRow collection for this file.
            column_layout: The already-resolved ColumnLayout for this
                file (the output of ColumnIdentityResolver), supplying
                the column-identity context chromosome_label_profiler,
                genotype_layout_classifier, and indel_haploid_classifier
                each require.

        Returns:
            A dict mapping profiler_name -> the corresponding
            genomic-notation value object, for every genomic profiler
            present in `self._genomic_profilers`. A profiler absent from
            `self._genomic_profilers` simply contributes no entry --
            mirroring `_run_quality_checks`'s identical "only run what's
            injected" behavior.
        """
        profiles = {}

        chromosome_label_profiler = self._genomic_profilers.get(
            "chromosome_label_profiler"
        )
        if chromosome_label_profiler is not None:
            profiles["chromosome_label_profiler"] = (
                chromosome_label_profiler.profile(
                    data_rows, column_layout.chromosome_column_index
                )
            )

        genotype_layout_classifier = self._genomic_profilers.get(
            "genotype_layout_classifier"
        )
        if genotype_layout_classifier is not None:
            profiles["genotype_layout_classifier"] = (
                genotype_layout_classifier.profile(
                    data_rows, column_layout.designated_column_indices
                )
            )

        indel_haploid_classifier = self._genomic_profilers.get(
            "indel_haploid_classifier"
        )
        if indel_haploid_classifier is not None:
            profiles["indel_haploid_classifier"] = indel_haploid_classifier.profile(
                data_rows,
                GenotypeChromosomeColumnIndices(
                    designated_column_indices=column_layout.designated_column_indices,
                    chromosome_column_index=column_layout.chromosome_column_index,
                ),
            )

        return profiles