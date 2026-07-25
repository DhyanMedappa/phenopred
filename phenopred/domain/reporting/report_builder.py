# phenopred/domain/reporting/report_builder.py
"""Domain-layer reporting component assembling one ProfilingReport per
file from already-computed file metadata, Findings, Profiles, a
ColumnCountDistribution, and applicable OpenQuestions (SRS Section 7,
OUT-1 through OUT-9 minus OUT-2/OUT-6; Architecture v1 Section 5/7.1/9).

ReportBuilder is the sole component responsible for this assembly. Per
Architecture v1 (Section 5/7.1/9/10) and the frozen Reporting
Architecture:

- This module lives in the domain layer and performs no file/network I/O
  of any kind.
- It performs no aggregation source logic of its own -- no detection, no
  quality-check evaluation, no genomic profiling, no column-count
  tallying, and no open-question selection. Every value it assembles is
  already computed elsewhere in the pipeline and supplied to `build()`
  as plain data; this class only orders and packages that data into one
  ProfilingReport.
- It never recomputes or duplicates MalformedRowCheck's column-count
  tallying logic: the ColumnCountDistribution it stores on
  ProfilingReport is accepted exactly as already produced by
  MalformedRowCheck.column_count_distribution(), or as None when that
  check was not among the quality checks injected for this run --
  mirroring the same "absent collaborator contributes no value"
  convention already established by
  ProfileFileUseCase._run_quality_checks and _run_genomic_profilers for
  a check/profiler absent from their respective injected mappings.
- It never resolves, interprets, filters, or modifies any OpenQuestion:
  selection is delegated entirely to the constructor-injected
  OpenQuestionRegistry, which is given the same ordered Finding and
  Profile tuples this method places on ProfilingReport, mirroring the
  frozen Reporting Architecture's ReportBuilder/OpenQuestionRegistry
  dependency relationship (OpenQuestionRegistry constructor-injected,
  never self-constructed here).
- ProfilingReport remains a passive, immutable aggregate with no
  behavior of its own; this class is the only place aggregation logic
  lives (Architecture v1 Section 5's "report_builder.py aggregates ...
  into a single ProfilingReport" responsibility).
- `findings` and `profiles` are accepted as the same name-keyed mappings
  ProfileFileUseCase._run_quality_checks/_run_genomic_profilers already
  produce (mirroring that existing pipeline design exactly), but the
  ordered tuples placed on ProfilingReport are derived exclusively from
  an explicit `sorted(..., key=...)` over each object's own
  `check_name`/`profiler_name` attribute -- never from the input
  mapping's iteration or insertion order, and never from any other
  collection's own traversal order (NFR-6, NFR-3).
- No common Profile base type or return hierarchy is introduced or
  assumed anywhere in this module: each profile value is stored and
  ordered as whatever concrete type it already is (ChromosomeLabelInventory,
  GenotypeLayoutProfile, or IndelHaploidProfile), mirroring
  GenomicProfiler's own documented "Profile names an architectural
  category, not a single shared Python type" contract.
"""

from __future__ import annotations

from collections.abc import Mapping

from phenopred.domain.entities import ProfilingReport
from phenopred.domain.reporting.open_question_registry import (
    OpenQuestionRegistry,
)
from phenopred.domain.value_objects import (
    ChromosomeLabelInventory,
    ColumnCountDistribution,
    CommentBlock,
    Delimiter,
    EncodingProfile,
    Finding,
    GenotypeLayoutProfile,
    HeaderInfo,
    IndelHaploidProfile,
)


class ReportBuilder:
    """Assembles one ProfilingReport from already-computed file metadata,
    Findings, Profiles, a ColumnCountDistribution, and applicable
    OpenQuestions.

    Carries constructor-injected dependency in the form of a single
    collaborator, mirroring IndelHaploidClassifier's established
    constructor-injection pattern for a domain class that genuinely
    needs one: this class needs OpenQuestionRegistry to select
    applicable open questions, and that collaborator is supplied by the
    caller (the composition root) rather than self-constructed here, per
    AD-10's dependency-injection discipline. Beyond that injected
    collaborator, this class holds no other mutable state. Given the
    same inputs, `build()` always returns a field-for-field identical
    ProfilingReport (NFR-3).
    """

    def __init__(self, open_question_registry: OpenQuestionRegistry) -> None:
        """Initialize the builder with its injected OpenQuestionRegistry
        collaborator.

        Args:
            open_question_registry: The already-constructed
                OpenQuestionRegistry used to select the subset of the
                SRS's fixed, registered open questions applicable to a
                given file's Findings and Profiles. Supplied by the
                caller (typically the composition root, per Architecture
                v1 Section 11); this class never constructs its own
                OpenQuestionRegistry.
        """
        self._open_question_registry = open_question_registry

    def build(
        self,
        source_path: str,
        comment_block: CommentBlock,
        encoding_profile: EncodingProfile,
        delimiter: Delimiter,
        header_info: HeaderInfo,
        row_count: int,
        column_count_distribution: ColumnCountDistribution | None,
        findings: Mapping[str, Finding],
        profiles: Mapping[
            str,
            ChromosomeLabelInventory | GenotypeLayoutProfile | IndelHaploidProfile,
        ],
    ) -> ProfilingReport:
        """Assemble one ProfilingReport from this file's already-computed
        pipeline outputs.

        This method performs no computation of its own beyond ordering:
        every argument is accepted exactly as already produced upstream
        in the pipeline (e.g. by ProfileFileUseCase, MalformedRowCheck,
        the other injected quality checks, and the injected genomic
        profilers).

        Args:
            source_path: This file's source path, carried through
                unaltered (OUT-1/OUT-2).
            comment_block: This file's already-resolved CommentBlock,
                carried through unaltered (OUT-1).
            encoding_profile: This file's already-resolved
                EncodingProfile, carried through unaltered (OUT-3).
            delimiter: This file's already-resolved Delimiter, carried
                through unaltered (OUT-4).
            header_info: This file's already-resolved HeaderInfo,
                carried through unaltered (OUT-4).
            row_count: The total number of parsed DataRow instances for
                this file (OUT-5), already computed by the caller.
            column_count_distribution: This file's already-computed
                ColumnCountDistribution (OUT-5), e.g. the output of
                MalformedRowCheck.column_count_distribution(), or None
                when malformed_row_check was not among the quality
                checks injected for this run. This method never
                computes or recomputes this value itself.
            findings: The name-keyed mapping of Finding results already
                produced by this run's injected quality checks (FR-5
                through FR-9, OUT-7) -- e.g. the same mapping
                ProfileFileUseCase._run_quality_checks already returns.
                Consulted only via `.values()`; never relied upon for
                its own iteration or insertion order.
            profiles: The name-keyed mapping of Profile results already
                produced by this run's injected genomic profilers
                (FR-10 through FR-12, OUT-8) -- e.g. the same mapping
                ProfileFileUseCase._run_genomic_profilers already
                returns. Consulted only via `.values()`; never relied
                upon for its own iteration or insertion order.

        Returns:
            A ProfilingReport whose `findings` is an ordered tuple of
            every value in `findings`, sorted by ascending
            `Finding.check_name`; whose `profiles` is an ordered tuple
            of every value in `profiles`, sorted by ascending
            `profiler_name`; whose `open_questions` is the tuple
            returned by this builder's injected OpenQuestionRegistry,
            given those same two ordered tuples; and whose every other
            field is the corresponding argument above, carried through
            unaltered.
        """
        ordered_findings = tuple(
            sorted(findings.values(), key=lambda finding: finding.check_name)
        )
        ordered_profiles = tuple(
            sorted(profiles.values(), key=lambda profile: profile.profiler_name)
        )
        # Ordering is derived exclusively from these two explicit sorts
        # over each object's own check_name/profiler_name attribute --
        # never from `findings`/`profiles`' own mapping iteration or
        # insertion order, mirroring this codebase's established
        # determinism discipline (NFR-3).

        open_questions = self._open_question_registry.applicable_for(
            ordered_findings, ordered_profiles
        )

        return ProfilingReport(
            source_path=source_path,
            comment_block=comment_block,
            encoding_profile=encoding_profile,
            delimiter=delimiter,
            header_info=header_info,
            row_count=row_count,
            column_count_distribution=column_count_distribution,
            findings=ordered_findings,
            profiles=ordered_profiles,
            open_questions=open_questions,
        )