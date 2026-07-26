# phenopred/domain/genomic_profiling/genotype_layout_classifier.py
"""Domain-layer genomic profiler reporting a file's genotype/allele
column layout classification and per-designated-column string-length
distributions (FR-11).

GenotypeLayoutClassifier is the sole component responsible for
classifying whether a file's designated genotype/allele columns follow
a two-column-allele layout, a single-column-genotype layout, or an
undetermined layout, and for reporting the observed string-length
distribution of each designated column, for consumption as a
GenotypeLayoutProfile. Per Architecture v1 (Section 4/5/6/10), ADR-1
through ADR-7, and the frozen Genomic Profiling Architecture Contract:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a plain, already-in-memory collection of DataRow
  instances and a plain, already-resolved Sequence[int] of designated
  column field-position indices, delivered via the GenomicProfiler
  interface's context parameter. It never accepts, imports, or depends
  on HeaderInfo, HeaderResolver, RawFileLoader, EncodingDetector,
  DelimiterDetector, RawLineSplitter, RowParser (module or class), any
  QualityCheck, any sibling GenomicProfiler, or ReportBuilder.
- GenotypeLayoutClassifier performs no column-name resolution, no header
  interpretation, and no biological interpretation of any observed
  value -- it measures only the structural shape of the designated
  column(s): how many there are, and what string lengths their values
  take. It never inspects a value's characters or content beyond
  measuring len(value); indel-token detection, haploid-call detection,
  allele-content classification, and every other content-level
  observation are FR-12's exclusive domain (IndelHaploidClassifier),
  never this module's. Value objects represent required descriptive
  observations without performing biological interpretation (ADR-7).
- Classification contract (ADR-5): layout_kind is derived exclusively
  from len(designated_column_indices) -- "two_column_allele" if and
  only if that count is exactly 2, "single_column_genotype" if and
  only if it is exactly 1, and "undetermined" for every other count,
  including 0 and 3 or more. Row values are never inspected to
  determine layout_kind, and layout_kind is never inferred from
  observed genotype strings.
- column_length_distributions is computed unconditionally for however
  many designated columns exist, fully decoupled from layout_kind
  (ADR-5). The descriptive length-distribution data is never withheld
  on account of an ambiguous or absent layout classification.
- Per the frozen malformed-row rule (mirroring MissingValueScanner's
  identical, already-approved precedent): if a designated column index
  is outside the bounds of a particular DataRow's fields tuple, that
  row contributes no observation for that designated column only --
  processing of remaining rows and remaining columns continues, and no
  exception is raised (Architecture v1 Section 13.2). This handling is
  applied independently for every designated column.
- No fixed designated-column count or vendor-specific layout is assumed
  anywhere in this module: the same unconfigured classification and
  measurement logic applies uniformly regardless of how many designated
  columns a file has. This profiler takes no constructor configuration
  by design. The implementation should remain robust against unexpected
  structural variations and should not encode assumptions that are only
  valid for the two evidence datasets (ADR-6).
- column_length_distributions is ordered, at the outer level, by
  ascending designated-column index, and at the inner level, by
  ascending numeric length -- never by descending count, frequency,
  alphabetical order, dictionary/set insertion behavior, or any
  inferred biological meaning (ADR-4).
- The entire data_rows collection is scanned in full -- never a sample
  -- per Architecture v1 Section 17's requirement that full-file SRS
  requirements (which FR-11 is) must not be handled by a sampling
  approach.
- This component never raises: Architecture v1 Section 13.2 requires
  data-quality/descriptive-profiling conditions to always be
  represented as value-object data, never exceptions.
- It never mutates any DataRow instance or the supplied collection
  (DataRow is itself immutable -- frozen=True, slots=True -- so
  mutation is not just a convention but a language-enforced
  impossibility).
- It does not perform row-quality validation of any kind (malformed-row
  detection, duplicate detection, missing-value scanning); those remain
  the exclusive responsibility of the separate FR-5..FR-9 QualityCheck
  implementations. It does not resolve designated_column_indices itself
  -- that remains ColumnIdentityResolver's and ProfileFileUseCase's
  responsibility; this profiler only consumes an already-resolved
  sequence.
- Per Architecture v1 Section 12: `profile()` logs, at INFO, this
  profiler's own name and a count-only summary (the classified
  `layout_kind`, plus the designated-column count it was derived from)
  when it completes -- never any observed genotype/allele string
  itself (NFR-4).

Determinism note (NFR-3): for each designated column, a single forward
pass over data_rows tallies each distinct observed string length's
occurrence count for that column. The final column_length_distributions
tuple is built by explicit ascending sorts -- first over the designated
column indices themselves, then, within each column, over the observed
length values -- never by dict/set iteration or insertion order, and
never by frequency. This holds regardless of data_rows' own traversal
order and regardless of any dict iteration order, including across
different Python versions or hash-randomization seeds.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import GenotypeLayoutProfile

logger = logging.getLogger(__name__)

_PROFILER_NAME = "genotype_layout_classifier"


class GenotypeLayoutClassifier:
    """Reports a file's genotype/allele column layout classification and
    per-designated-column string-length distributions (FR-11).

    Stateless: holds no constructor-injected configuration and no
    mutable state of any kind, mirroring ChromosomeLabelProfiler's and
    RowParser's identical pattern. FR-11 names no configurable
    vocabulary or convention for this component -- the classification
    and measurement logic applies uniformly regardless of how many
    designated columns a file has, so no constructor parameter is
    introduced or accepted. Given the same inputs, `profile()` always
    returns a field-for-field identical GenotypeLayoutProfile (NFR-3).
    """

    def profile(
        self,
        data_rows: Sequence[DataRow],
        designated_column_indices: Sequence[int],
    ) -> GenotypeLayoutProfile:
        """Classify the file's designated genotype/allele column layout
        and report each designated column's observed string-length
        distribution.

        Args:
            data_rows: A sequence of already-in-memory, already-parsed
                DataRow instances (e.g. the output of RowParser.parse()).
                No file I/O is performed; `data_rows` must already be in
                memory. The full, unsampled collection is always
                scanned, independently, once per designated column.
                Rows may legitimately vary in field-count width (e.g.
                malformed rows); see the out-of-bounds handling below.
            designated_column_indices: A plain, already-resolved
                sequence of field-position indices identifying this
                file's designated genotype/allele columns. This method
                performs no resolution, validation, or interpretation
                of these indices beyond using each to index into
                `row.fields` and using their count to derive
                `layout_kind`.

        Returns:
            A GenotypeLayoutProfile whose `layout_kind` is
            "two_column_allele" if `len(designated_column_indices) ==
            2`, "single_column_genotype" if it is 1, or "undetermined"
            for every other count -- determined solely from that count,
            never from row content. `column_length_distributions`
            contains one entry per index in `designated_column_indices`,
            in ascending column-index order, computed unconditionally
            regardless of `layout_kind`; each entry's inner distribution
            is a tuple of (length, count) pairs, in ascending length
            order, tallying the string length of every in-bounds value
            observed at that column across the full, unsampled
            `data_rows` collection. If `designated_column_indices` is
            empty, `column_length_distributions == ()`.

        Raises:
            This method introduces no exception handling of its own and
            depends on no exception hierarchy. A designated column
            index outside the bounds of a particular row's `fields`
            tuple contributes no observation for that row and that
            column only, and never raises.
        """
        layout_kind = self._classify_layout_kind(designated_column_indices)
        column_length_distributions = self._measure_length_distributions(
            data_rows, designated_column_indices
        )

        logger.info(
            "%s: layout_kind=%s designated_column_count=%d",
            _PROFILER_NAME,
            layout_kind,
            len(designated_column_indices),
        )
        return GenotypeLayoutProfile(
            profiler_name=_PROFILER_NAME,
            layout_kind=layout_kind,
            column_length_distributions=column_length_distributions,
        )

    def _classify_layout_kind(
        self, designated_column_indices: Sequence[int]
    ) -> str:
        """Classify `layout_kind` solely from the count of designated
        columns, per the frozen ADR-5 classification contract.

        Row values are never inspected here -- this classification is
        derived exclusively from `len(designated_column_indices)`.
        """
        designated_column_count = len(designated_column_indices)
        if designated_column_count == 2:
            return "two_column_allele"
        if designated_column_count == 1:
            return "single_column_genotype"
        return "undetermined"

    def _measure_length_distributions(
        self,
        data_rows: Sequence[DataRow],
        designated_column_indices: Sequence[int],
    ) -> tuple[tuple[int, tuple[tuple[int, int], ...]], ...]:
        """Measure each designated column's observed string-length
        distribution, unconditionally and independently of
        `layout_kind`.

        Returns an ordered tuple of (designated_column_index,
        length_distribution) pairs, in ascending column-index order.
        Each length_distribution is itself an ordered tuple of
        (length, count) pairs, in ascending length order (ADR-4).
        """
        distributions: list[tuple[int, tuple[tuple[int, int], ...]]] = []

        for column_index in sorted(designated_column_indices):
            length_counts: dict[int, int] = {}

            for row in data_rows:
                if column_index >= len(row.fields):
                    # Out-of-bounds designated column index for this
                    # row: no observation contributed for this column,
                    # no exception raised, remaining rows/columns
                    # continue processing.
                    continue

                value_length = len(row.fields[column_index])
                length_counts[value_length] = (
                    length_counts.get(value_length, 0) + 1
                )

            ordered_length_distribution = tuple(
                (length, length_counts[length])
                for length in sorted(length_counts.keys())
            )
            distributions.append((column_index, ordered_length_distribution))

        return tuple(distributions)
