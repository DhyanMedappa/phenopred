# phenopred/domain/genomic_profiling/chromosome_label_profiler.py
"""Domain-layer genomic profiler reporting the distinct chromosome-label
values observed in a file, together with their per-label row counts
(FR-10).

ChromosomeLabelProfiler is the sole component responsible for enumerating
every distinct chromosome-label value present in a file's parsed DataRow
collection and reporting each one's row count, for consumption as a
ChromosomeLabelInventory. Per Architecture v1 (Section 4/5/6/10), ADR-1
through ADR-7, and the frozen Genomic Profiling Architecture Contract:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a plain, already-in-memory collection of DataRow
  instances and a plain, already-resolved int field-position index,
  delivered via the GenomicProfiler interface's context parameter. It
  never accepts, imports, or depends on HeaderInfo, HeaderResolver,
  RawFileLoader, EncodingDetector, DelimiterDetector, RawLineSplitter,
  RowParser (module or class), any QualityCheck, any sibling
  GenomicProfiler, or ReportBuilder.
- ChromosomeLabelProfiler performs no column-name resolution, no header
  interpretation, and no biological interpretation of any label value --
  it neither maps, translates, nor reconciles chromosome codes across
  files (FR-10's own text: "without assuming that chromosome labels are
  equivalent or directly comparable across files"; RISK-1, RISK-2).
  Value objects represent required descriptive observations without
  performing biological interpretation (ADR-7).
- Per the frozen malformed-row rule (mirroring DuplicateRsidCheck's
  identical, already-approved precedent): if chromosome_column_index is
  outside the bounds of a particular DataRow's fields tuple, that row
  contributes no observation and is excluded from the inventory. No
  exception is raised -- this is normal data-quality input, not an
  error condition (Architecture v1 Section 13.2).
- No fixed chromosome-label vocabulary is assumed anywhere in this
  module: every label observed in the file is reported, whatever its
  form. This profiler takes no constructor configuration by design --
  it must never be given an injected label vocabulary, since doing so
  would reintroduce the cross-file comparability assumption FR-10
  forbids. The implementation should remain robust against unexpected
  structural variations and should not encode assumptions that are
  only valid for the two evidence datasets (ADR-6).
- ChromosomeLabelInventory.label_counts is ordered by ascending
  first-observed DataRow.line_index -- never by descending count,
  alphabetical order, dictionary/set insertion behavior, or any
  inferred chromosome meaning (ADR-4). Ranking labels by frequency
  would imply an importance judgment this profiler has no license to
  make.
- The entire data_rows collection is scanned in full -- never a sample
  -- per Architecture v1 Section 17's requirement that full-file SRS
  requirements (which FR-10 is) must not be handled by a sampling
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
  implementations.
- Per Architecture v1 Section 12: `profile()` logs, at INFO, this
  profiler's own name and a count-only summary (distinct chromosome-
  label count) when it completes -- never the literal label values
  themselves (NFR-4).

Determinism note (NFR-3): a single forward pass over data_rows tallies
each distinct label's occurrence count and records the line_index at
which that label was first observed. The final label_counts tuple is
built by an explicit sort on that recorded first-observed line_index --
never by dict/set iteration or insertion order, and never by frequency.
This holds regardless of data_rows' own traversal order and regardless
of any dict iteration order, including across different Python versions
or hash-randomization seeds.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import ChromosomeLabelInventory

logger = logging.getLogger(__name__)

_PROFILER_NAME = "chromosome_label_profiler"


class ChromosomeLabelProfiler:
    """Reports the distinct chromosome-label values observed in a file,
    together with their per-label row counts (FR-10).

    Stateless: holds no constructor-injected configuration and no
    mutable state of any kind, mirroring RowParser's and
    MalformedRowCheck's identical pattern. FR-10 names no configurable
    vocabulary or convention for this component -- every label observed
    is reported, whatever its form, so no constructor parameter is
    introduced or accepted. Given the same inputs, `profile()` always
    returns a field-for-field identical ChromosomeLabelInventory
    (NFR-3).
    """

    def profile(
        self,
        data_rows: Sequence[DataRow],
        chromosome_column_index: int,
    ) -> ChromosomeLabelInventory:
        """Enumerate every distinct chromosome-label value observed in
        `data_rows` and report each one's row count.

        Args:
            data_rows: A sequence of already-in-memory, already-parsed
                DataRow instances (e.g. the output of RowParser.parse()).
                No file I/O is performed; `data_rows` must already be in
                memory. The full, unsampled collection is always
                scanned. Rows may legitimately vary in field-count width
                (e.g. malformed rows); see the out-of-bounds handling
                below.
            chromosome_column_index: A single, already-resolved
                field-position index identifying this file's chromosome
                column. This method performs no resolution, validation,
                or interpretation of this index beyond using it to index
                into `row.fields`.

        Returns:
            A ChromosomeLabelInventory whose `label_counts` contains one
            (label, count) pair for every distinct chromosome-label
            value observed across the full, unsampled `data_rows`
            collection, ordered by ascending first-observed
            `DataRow.line_index`. Label values are compared by exact
            string equality only -- no normalization, trimming, case
            conversion, or biological interpretation is ever applied.
            If `data_rows` is empty, or `chromosome_column_index` is out
            of bounds for every row, the returned inventory has
            `label_counts == ()`.

        Raises:
            This method introduces no exception handling of its own and
            depends on no exception hierarchy. A `chromosome_column_index`
            outside the bounds of a particular row's `fields` tuple
            contributes no observation for that row and never raises.
        """
        label_counts: dict[str, int] = {}
        first_observed_line_index: dict[str, int] = {}

        for row in data_rows:
            if chromosome_column_index >= len(row.fields):
                # Out-of-bounds chromosome_column_index for this row:
                # no observation contributed, no exception raised.
                continue

            label = row.fields[chromosome_column_index]
            label_counts[label] = label_counts.get(label, 0) + 1
            if label not in first_observed_line_index:
                first_observed_line_index[label] = row.line_index

        # Ordering is derived exclusively from an explicit sort on each
        # label's recorded first-observed line_index -- never from
        # dict iteration/insertion order, and never from frequency,
        # alphabetical order, or any inferred chromosome meaning.
        ordered_labels = sorted(
            label_counts.keys(),
            key=lambda label: first_observed_line_index[label],
        )

        logger.info(
            "%s: %d distinct chromosome label(s) found",
            _PROFILER_NAME,
            len(ordered_labels),
        )
        return ChromosomeLabelInventory(
            profiler_name=_PROFILER_NAME,
            label_counts=tuple(
                (label, label_counts[label]) for label in ordered_labels
            ),
        )
