# phenopred/domain/quality_checks/malformed_row_check.py
"""Domain-layer quality check reporting rows whose column count differs
from the file's modal column count (FR-5).

MalformedRowCheck is the sole component responsible for determining a
file's modal (dominant) column count from its own parsed DataRow
collection, and for reporting every row whose field count differs from
that modal count as malformed. Per Architecture v1 (Section 4/5/6/10/14),
the Frozen Architecture Clarification Record, and the frozen Architecture
Decision Record resolving Deferred Decision B.4:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a plain, already-in-memory collection of DataRow
  instances -- the same effective, already comment-stripped,
  header-excluded data rows RowParser produces. It never accepts,
  imports, or depends on HeaderInfo, HeaderResolver, RawFileLoader,
  EncodingDetector, DelimiterDetector, RawLineSplitter, RowParser (module
  or class), ReportSerializer, ReportBuilder, or any ColumnCountDistribution
  implementation.
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
  encoding detection, no header detection/resolution, and does not
  resolve, implement, or presuppose the deferred ColumnCountDistribution
  design.
- It never modifies any DataRow instance or the supplied collection.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import Finding

_CHECK_NAME = "malformed_row_check"
_MAX_SAMPLE_SIZE = 10


class MalformedRowCheck:
    """Reports rows whose column count differs from the file's modal
    column count (FR-5).

    Stateless: holds no constructor-injected configuration and no mutable
    state of any kind, mirroring RowParser's and DuplicateHeaderCheck's
    identical pattern, since FR-5 names no configurable convention for
    this component. Given the same input, `check()` always returns a
    field-for-field identical Finding (NFR-3).
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

        modal_count = self._resolve_modal_count(data_rows)
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

        return Finding(
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

    def _resolve_modal_count(self, data_rows: Sequence[DataRow]) -> int:
        """Determine the file's modal column count, resolving ties per
        the frozen Architecture Decision Record for Deferred Decision B.4.

        The modal count is the field-count value (`len(row.fields)`)
        occurring with the highest frequency across `data_rows`. When two
        or more distinct field-count values are tied for that highest
        frequency, the tied candidate belonging to the row with the
        smallest `line_index` among all rows whose field count is one of
        the tied candidates is selected ("first observed column count
        wins"). This selection is made by direct `line_index` value
        comparison; it does not depend on dictionary, set, or Counter
        iteration/insertion order, nor on the traversal order of
        `data_rows` itself.

        Args:
            data_rows: A non-empty sequence of DataRow instances.

        Returns:
            The selected modal column count, as an int.
        """
        frequency: Counter[int] = Counter(
            len(row.fields) for row in data_rows
        )
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
