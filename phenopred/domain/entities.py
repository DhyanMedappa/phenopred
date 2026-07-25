# phenopred/domain/entities.py
"""Core data-carrying entities for the PhenoPred domain layer.

Per Architecture v1 (Section 4), this file is the designated home for
GenotypeFile, DataRow, and ProfilingReport. DataRow and ProfilingReport
are defined here; ProfilingReport was added under the Reporting
Architecture Freeze, which resolved -- as an explicit, recorded
architecture decision -- that ProfilingReport belongs in this module
rather than in value_objects.py, because it is this system's per-file
output aggregate (one instance per file, produced exactly once and
referenced afterward), matching the same identity/lifecycle reasoning
that already places DataRow here rather than in value_objects.py.

GenotypeFile remains intentionally absent. The Reporting Architecture
Freeze considered and explicitly declined to introduce it at this
stage: every field Architecture v1 Section 8 names for GenotypeFile is
already produced and correctly threaded through
ProfileFileUseCase.execute() as plain data, and no approved component
requires a GenotypeFile instance specifically rather than that already-
existing plain data. Introducing it now would add structure with no
corresponding requirement -- adding it ahead of a demonstrated need
would exceed the scope explicitly defined for the current module
(mirroring the identical incremental-accretion precedent already
established for phenopred/domain/value_objects.py, where EncodingProfile,
Delimiter, CommentBlock, and HeaderInfo were each added only as their
own respective module required them).
"""

from __future__ import annotations

from dataclasses import dataclass

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
    OpenQuestion,
)


@dataclass(frozen=True, slots=True)
class DataRow:
    """An immutable, ordered field-value carrier for one parsed data line (FR-4).

    This is a purely descriptive record of a line's field values, once
    split by the file's detected delimiter. It carries no notion of its
    own "correctness": column-count expectations, malformed-row judgments,
    missing-value classification, and every other data-quality condition
    are computed externally -- by downstream QualityCheck implementations
    operating over a collection of DataRow instances -- and are never
    checked, inferred, or asserted by DataRow itself.

    Attributes:
        line_index: The zero-based position of this row within the
            sequence of lines RowParser was given (i.e. the effective,
            already comment-stripped and header-excluded data lines for
            this file). This identifies a row's position within this
            file's own parsed DataRow collection; it is not a
            reconstruction of the row's line number in the original
            source file. Must be non-negative.
        fields: Ordered, unmodified field-value strings, produced by
            splitting the original line on the file's detected delimiter
            character. No casting, coercion, trimming, or other
            alteration is applied to any field value.
    """

    line_index: int
    fields: tuple[str, ...]

    def __post_init__(self) -> None:
        """Enforce the sole invariant named for this entity.

        Per Architecture v1 Section 5, a DataRow cannot be constructed
        with a negative line number. No other validation is performed by
        this entity: field count, expected column count, field content,
        missing-value tokens, formatting, and every other data-quality
        condition are explicitly out of scope here (see class docstring)
        and are never checked by this method or any other part of this
        class.

        Raises:
            ValueError: If `line_index` is negative. This represents an
                invalid value-object construction argument, not an
                ingestion-pipeline failure; no PhenoPredIngestionError
                subclass or other domain-specific exception is used.
        """
        if self.line_index < 0:
            raise ValueError(
                f"line_index must be non-negative, got {self.line_index}"
            )


@dataclass(frozen=True, slots=True)
class ProfilingReport:
    """The single, per-file structural and genomic-notation profiling
    output aggregate (SRS Section 7, OUT-1 through OUT-9, minus OUT-2
    and OUT-6; see class-level notes below).

    Per Architecture v1 Section 7.1, ProfilingReport is the aggregate
    root of one output artifact per file, produced by ReportBuilder from
    already-computed file metadata, Findings, Profiles, and applicable
    OpenQuestions -- never computed by this entity itself. This entity
    performs no aggregation, no selection, and no detection of its own:
    it is a plain, immutable carrier of already-resolved values,
    mirroring DataRow's identical "descriptive record, no behavior
    beyond its sole named invariant" design, except that no invariant is
    named for ProfilingReport by Architecture v1 -- so, unlike DataRow,
    this entity enforces none.

    A ProfilingReport never contains a corrective action, resolution, or
    biological interpretation of any Finding or Profile it carries --
    only what was already found and already profiled elsewhere,
    consistent with the SRS's own "reporting, not resolution" framing
    (Section 4 preamble) and with Finding's and every Profile value
    object's identical discipline.

    Scope notes on two named-but-unfulfilled outputs, both explicitly
    recorded by the frozen Reporting Architecture decision rather than
    silently omitted:
        - OUT-2 (size in bytes, file extension, leading bytes) is not
          yet confirmed to be available from the current ingestion
          pipeline's output and is not represented by a field here
          pending that verification; no placeholder field is
          introduced for it.
        - OUT-6 (per-column observed value-shape counts) has no
          corresponding FR in the SRS and no producing component
          anywhere in Architecture v1 -- it is a recorded, deferred
          specification gap, not an implementation gap, and is
          deliberately not represented by a field here.
    `generated_at`, named conceptually by Architecture v1 Section 8, is
    likewise deliberately omitted: no OUT item requires it, and a
    self-generated wall-clock timestamp would conflict with Section
    15.3's byte-identical reproducibility requirement.

    Attributes:
        source_path: This file's source path, carried through unaltered
            from RawFileLoader's output (OUT-1/OUT-2 file identification).
        comment_block: This file's already-resolved CommentBlock,
            carried through unaltered (OUT-1).
        encoding_profile: This file's already-resolved EncodingProfile,
            carried through unaltered (OUT-3).
        delimiter: This file's already-resolved Delimiter, carried
            through unaltered (OUT-4).
        header_info: This file's already-resolved HeaderInfo, carried
            through unaltered (OUT-4).
        row_count: The total number of parsed DataRow instances for this
            file (OUT-5).
        column_count_distribution: This file's already-computed
            ColumnCountDistribution (OUT-5), or None when
            malformed_row_check was not among the quality checks
            injected into ProfileFileUseCase for this run -- mirroring
            the same "absent collaborator contributes no entry/value"
            convention already established by
            ProfileFileUseCase._run_quality_checks and
            _run_genomic_profilers for a check/profiler absent from
            their respective injected mappings.
        findings: Every Finding produced by this run's injected quality
            checks (FR-5 through FR-9, OUT-7), as an ordered tuple,
            ordered by ascending Finding.check_name -- never by dict
            iteration/insertion order -- mirroring this codebase's
            established determinism discipline (NFR-3).
        profiles: Every Profile produced by this run's injected genomic
            profilers (FR-10 through FR-12, OUT-8) -- each a
            ChromosomeLabelInventory, GenotypeLayoutProfile, or
            IndelHaploidProfile, never a common Profile type (mirroring
            GenomicProfiler's own documented "Profile names an
            architectural category, not a single shared Python type"
            contract) -- as an ordered tuple, ordered by ascending
            profiler_name -- never by dict iteration/insertion order,
            for the same reason as `findings`.
        open_questions: The subset of the SRS's fixed, registered open
            questions (SRS Section 8.2, RISK-1 through RISK-9) that
            OpenQuestionRegistry determined applicable to this file's
            observed findings/profiles, as an ordered tuple (OUT-9,
            OBJ-5, AD-7). Never resolved, altered, or interpreted by
            this entity or by any other component in this system.
    """

    source_path: str
    comment_block: CommentBlock
    encoding_profile: EncodingProfile
    delimiter: Delimiter
    header_info: HeaderInfo
    row_count: int
    column_count_distribution: ColumnCountDistribution | None
    findings: tuple[Finding, ...]
    profiles: tuple[
        ChromosomeLabelInventory | GenotypeLayoutProfile | IndelHaploidProfile, ...
    ]
    open_questions: tuple[OpenQuestion, ...]