# phenopred/domain/quality_checks/malformed_row_check.py
"""Domain-layer quality check reporting rows whose column count differs
from the file's modal column count (FR-5), and exposing the file's full
observed column-count distribution (OUT-5).

MalformedRowCheck is the sole component responsible for determining a
file's modal (dominant) column count from its own parsed DataRow
collection, and for reporting every row whose field count differs from
that modal count as malformed. Per Architecture v1 (Section 4/5/6/10/14),
the Frozen Architecture Clarification Record, the frozen Architecture
Decision Record resolving Deferred Decision B.4, and the frozen
Reporting Architecture (OUT-5 representation decision):

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a plain, already-in-memory collection of DataRow
  instances -- the same effective, already comment-stripped,
  header-excluded data rows RowParser produces. It never accepts,
  imports, or depends on HeaderInfo, HeaderResolver, RawFileLoader,
  EncodingDetector, DelimiterDetector, RawLineSplitter, RowParser (module
  or class), or ReportBuilder.
- The modal column count is computed entirely and only from the observed
  DataRow.fields lengths in the supplied collection (FR-5; Architecture
  Section 7.2/14). No external, header-derived, or hard-coded schema
  contributes to it (AD-5, NFR-5).
- Per the frozen Architecture Decision Record resolving Deferred Decision
  B.4: when two or more distinct field-count values are tied for the
  file's highest observed frequency, the tied candidate belonging to the
  row with the smallest DataRow.line_index is selected as the modal
  count ("first observed column count wins"). This is a deterministic
  reporting convention only; it carries no implication that earlier rows
  are more correct, more trustworthy, or more representative of the
  file's true shape, and no implication that a smaller or larger column
  count is preferable in general. Determinism is derived solely from
  DataRow.line_index value comparison -- never from dictionary, set, or
  Counter iteration/insertion order, and never from the input collection's
  own traversal order.
- No exception is raised for the malformed-row condition itself; it is
  always represented as Finding data (AD-6; Architecture Section 13.2).
- This component performs no parsing, no delimiter detection, no
  encoding detection, and no header detection/resolution.
- It never modifies any DataRow instance or the supplied collection.
- Per the frozen Reporting Architecture decision resolving OUT-5's
  representation gap: `check()`'s existing signature and behavior are
  unchanged. The column-count frequency tally this check already
  computed internally (and previously discarded down to a single
  `modal_count`) is now also exposed, unaltered, as a
  ColumnCountDistribution via the new `column_count_distribution()`
  method, sharing the identical tallying helper `check()` itself uses --
  the tally is never computed twice by two separate implementations.
- Per Architecture v1 Section 12: `check()` logs, at INFO, this check's
  own name and a count-only summary (modal column count and malformed-
  row count) when it completes -- never row content or field values
  (NFR-4).
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import ColumnCountDistribution, Finding

logger = logging.getLogger(__name__)

_CHECK_NAME = "malformed_row_check"
_MAX_SAMPLE_SIZE = 10


class MalformedRowCheck:
    """Reports rows whose column count differs from the file's modal
    column count (FR-5), and exposes the file's full observed
    column-count distribution (OUT-5).

    Stateless: holds no constructor-injected configuration and no mutable
    state of any kind, mirroring RowParser's and DuplicateHeaderCheck's
    identical pattern, since FR-5 names no configurable convention for
    this component. Given the same input, `check()` always returns a
    field-for-field identical Finding, and `column_count_distribution()`
    always returns a field-for-field identical ColumnCountDistribution
    (NFR-3).
    """

    def check(self, data_rows: Sequence[DataRow]) -> Finding:
        """Compute the file's modal column count and report malformed rows.

        Args:
            data_rows: A sequence of already-in-memory, already-parsed
                DataRow instances (e.g. the output of RowParser.parse()).
                No file I/O is performed; `data_rows` must already be in
                memory. This method inspects only `DataRow.fields` (via
                `len(row.fields)`) and `DataRow.line_index`; no other
                property is required or consulted.

        Returns:
            A Finding whose `count` is the total number of rows across
            the full, unsampled `data_rows` collection whose field count
            differs from the selected modal column count; whose
            `examples` and `affected_row_refs` are bounded samples
            (maximum 10 entries each) of those malformed rows, in
            original row order (ascending `line_index`); and whose
            `check_name`/`description` identify this check. If
            `data_rows` is empty, no modal count can be computed and the
            returned Finding has `count == 0`, `examples == ()`, and
            `affected_row_refs == ()`.

        Raises:
            This method introduces no exception handling of its own and
            depends on no exception hierarchy. Malformed rows are always
            reported as Finding data, never raised as exceptions.
        """
        if not data_rows:
            logger.info("%s: 0 malformed row(s) found (no data rows)", _CHECK_NAME)
            return Finding(
                check_name=_CHECK_NAME,
                description=(
                    "No data rows were available to determine a modal "
                    "column count."
                ),
                count=0,
                examples=(),
                affected_row_refs=(),
            )

        frequency = self._tally_column_counts(data_rows)
        modal_count = self._resolve_modal_count(data_rows, frequency)
        malformed_rows = sorted(
            (row for row in data_rows if len(row.fields) != modal_count),
            key=lambda row: row.line_index,
        )
        # "Original row order" (Finding's own docstring requirement) is
        # defined by ascending line_index -- the same authoritative,
        # frozen positional property used for modal-count tie resolution
        # -- rather than assumed from data_rows' own presentation order.
        # This keeps examples/affected_row_refs ordering correct and
        # deterministic even if a caller ever supplied data_rows in a
        # non-line_index-ordered sequence, without altering, reordering,
        # or mutating the input collection itself (a new list is built).

        finding = Finding(
            check_name=_CHECK_NAME,
            description=(
                f"Rows whose field count differs from the file's modal "
                f"column count ({modal_count})."
            ),
            count=len(malformed_rows),
            examples=tuple(
                self._render_example(row)
                for row in malformed_rows[:_MAX_SAMPLE_SIZE]
            ),
            affected_row_refs=tuple(
                row.line_index for row in malformed_rows[:_MAX_SAMPLE_SIZE]
            ),
        )
        logger.info(
            "%s: modal_column_count=%d malformed_row_count=%d",
            _CHECK_NAME,
            modal_count,
            finding.count,
        )
        return finding

    def column_count_distribution(
        self, data_rows: Sequence[DataRow]
    ) -> ColumnCountDistribution:
        """Compute and expose the file's full observed column-count
        frequency distribution, alongside its modal column count (OUT-5).

        This method performs no malformed-row judgment of its own --
        that remains `check()`'s own, separate Finding. It shares
        `check()`'s identical column-count tallying and modal-count
        resolution logic via the same private helpers, so the
        distribution reported here and the modal count `check()`
        compares every row against are always derived from one, single
        tally -- never computed twice by two independent
        implementations.

        Args:
            data_rows: A sequence of already-in-memory, already-parsed
                DataRow instances (e.g. the output of RowParser.parse()).
                No file I/O is performed; `data_rows` must already be in
                memory. This method inspects only `DataRow.fields` (via
                `len(row.fields)`) and, for modal-count tie resolution,
                `DataRow.line_index`.

        Returns:
            A ColumnCountDistribution whose `counts_by_column_count` is
            every distinct field-count value observed across the full,
            unsampled `data_rows` collection, together with its row
            count, as an ordered tuple of (column_count, row_count)
            pairs in ascending column_count order; and whose
            `modal_count` is the same modal column count `check()`
            itself would compute for the identical `data_rows`. If
            `data_rows` is empty, no distribution or modal count can be
            computed and the returned ColumnCountDistribution has
            `counts_by_column_count == ()` and `modal_count == 0`.

        Raises:
            This method introduces no exception handling of its own and
            depends on no exception hierarchy.
        """
        if not data_rows:
            return ColumnCountDistribution(
                check_name=_CHECK_NAME,
                counts_by_column_count=(),
                modal_count=0,
            )

        frequency = self._tally_column_counts(data_rows)
        modal_count = self._resolve_modal_count(data_rows, frequency)

        ordered_counts = tuple(
            (field_count, frequency[field_count])
            for field_count in sorted(frequency.keys())
        )
        # Ordering is derived exclusively from this explicit ascending
        # sort over the observed field-count values themselves -- never
        # from Counter/dict iteration or insertion order, mirroring this
        # codebase's established determinism discipline (NFR-3).

        return ColumnCountDistribution(
            check_name=_CHECK_NAME,
            counts_by_column_count=ordered_counts,
            modal_count=modal_count,
        )

    def _tally_column_counts(
        self, data_rows: Sequence[DataRow]
    ) -> Counter[int]:
        """Tally the observed field-count (`len(row.fields)`) frequency
        across `data_rows`.

        This is the sole tallying implementation shared by both
        `check()` (via `_resolve_modal_count`) and
        `column_count_distribution()`, so the two public methods never
        compute this frequency independently of one another.

        Args:
            data_rows: A non-empty sequence of DataRow instances.

        Returns:
            A Counter mapping each observed field-count value to its
            row-count frequency. Used only for O(1) frequency lookups
            and via explicit, ascending-key iteration in
            `column_count_distribution()`; never relied upon for output
            order via its own iteration/insertion order.
        """
        return Counter(len(row.fields) for row in data_rows)

    def _resolve_modal_count(
        self, data_rows: Sequence[DataRow], frequency: Counter[int]
    ) -> int:
        """Determine the file's modal column count from an already-
        computed frequency tally, resolving ties per the frozen
        Architecture Decision Record for Deferred Decision B.4.

        The modal count is the field-count value occurring with the
        highest frequency in `frequency`. When two or more distinct
        field-count values are tied for that highest frequency, the
        tied candidate belonging to the row with the smallest
        `line_index` among all rows whose field count is one of the
        tied candidates is selected ("first observed column count
        wins"). This selection is made by direct `line_index` value
        comparison; it does not depend on dictionary, set, or Counter
        iteration/insertion order, nor on the traversal order of
        `data_rows` itself.

        Args:
            data_rows: The same non-empty sequence of DataRow instances
                `frequency` was tallied from.
            frequency: The result of `_tally_column_counts(data_rows)`,
                supplied by the caller so the tally is computed exactly
                once per `check()`/`column_count_distribution()` call.

        Returns:
            The selected modal column count, as an int.
        """
        max_frequency = max(frequency.values())
        modal_candidates = {
            field_count
            for field_count, count in frequency.items()
            if count == max_frequency
        }

        if len(modal_candidates) == 1:
            return next(iter(modal_candidates))

        # Tie condition: select the candidate belonging to the row with
        # the smallest line_index among all rows whose field count is a
        # modal candidate. Determinism comes from comparing line_index
        # values directly (via `min`), never from iteration order.
        tied_rows = (
            row for row in data_rows if len(row.fields) in modal_candidates
        )
        earliest_row = min(tied_rows, key=lambda row: row.line_index)
        return len(earliest_row.fields)

    def _render_example(self, row: DataRow) -> str:
        """Render a single malformed row as an illustrative example string.

        The exact serialization format is an implementation-level detail
        not prescribed by FR-5, OUT-7, or the frozen Finding contract
        (mirroring the identical, already-accepted gap in
        DuplicateHeaderCheck's own approval record). This renders the
        row's original field values and its actual field count, without
        altering, casting, or interpreting any field value.
        """
        return f"line_index={row.line_index} fields={row.fields}"