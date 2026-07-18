from __future__ import annotations

from phenopred.domain.detection.column_identity_resolver import (
    ColumnIdentityNotResolvedError,
)
from phenopred.domain.detection.delimiter_detector import DelimiterNotDetectedError
from phenopred.domain.errors import PhenoPredIngestionError
from phenopred.domain.value_objects import ChrPosColumnIndices


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

    def execute(self, file_path):
        """
        Execute the profiling workflow for one input file, through the
        currently available pipeline stages (load, structural detection,
        column identity resolution, row parsing, and quality checks
        FR-5 through FR-9).

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
        [genomic profiling / report building: not yet wired --
         no genomic profiler or report builder implementation exists
         in the current pipeline configuration]

        Args:
            file_path: Path to the single source file to profile.

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

        return {
            "source_path": raw_content.source_path,
            "encoding_profile": encoding_profile,
            "comment_block": comment_block,
            "delimiter": delimiter,
            "header_info": header_info,
            "column_layout": column_layout,
            "data_rows": data_rows,
            "findings": findings,
            "skipped_quality_checks": skipped_quality_checks,
        }

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