# phenopred/domain/quality_checks/duplicate_rsid_check.py
"""Domain-layer quality check reporting rows whose RSID value occurs in
two or more rows of a file (FR-8).

DuplicateRsidCheck is the sole component responsible for determining, for
a file's parsed DataRow collection and an already-resolved RSID column
field-position index, which rows carry an RSID value that recurs
elsewhere in the same file, and for reporting the result as one Finding.
Per Architecture v1 (Section 4/6/10/13.2), the frozen "Column-Identity
Input Contract for DuplicateRsidCheck (FR-8)" ADR, and the frozen
"Finding Output Mapping for DuplicateRsidCheck (FR-8)" ADR:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a plain, already-in-memory collection of DataRow
  instances and a plain, already-resolved int field-position index,
  delivered via the QualityCheck interface's context parameter. It never
  accepts, imports, or depends on HeaderInfo, HeaderResolver,
  RawFileLoader, EncodingDetector, DelimiterDetector, RawLineSplitter,
  RowParser (module or class), any sibling QualityCheck, any
  GenomicProfiler, or ReportBuilder.
- DuplicateRsidCheck performs no column-name resolution, no header
  interpretation, and no judgment about RSID value format or biological
  validity -- it only observes and compares literal values (frozen ADR;
  Architecture v1 Section 14: "reporting, not resolution").
- Per the frozen malformed-row rule: if rsid_column_index is outside the
  bounds of a particular DataRow's fields tuple, that row contributes no
  observation and is excluded from duplicate consideration. No exception
  is raised -- this is normal data-quality input, not an error condition
  (Architecture v1 Section 13.2).
- An RSID value is "duplicated" when it is observed in two or more rows.
  Every row carrying a duplicated value is counted -- there is no "first
  occurrence is exempt" rule (frozen Finding Output Mapping ADR).
- Finding.count is the total number of rows belonging to any duplicated
  RSID group (a row-population count), never the number of distinct
  duplicated RSID values, and never a count of "extra" occurrences after
  each value's first observation.
- Finding.examples/affected_row_refs are bounded to a maximum of 10
  entries, drawn from the same affected-row population that count
  describes, ordered by ascending DataRow.line_index -- per the frozen
  Finding Output Mapping ADR.
- This component never raises: Architecture v1 Section 13.2 requires
  data-quality conditions to always be represented as Finding data,
  never exceptions.

Determinism note (NFR-3): a Counter and a frozenset are used internally
purely as O(1) frequency-tally and membership-test aids. Neither is ever
iterated to decide an output value or an output order. Every
order-sensitive or count-sensitive result in this module -- the
population size used for `count`, and the selection/ordering of
`examples`/`affected_row_refs` -- is derived exclusively from an
explicit `sorted(..., key=lambda row: row.line_index)` call and `len()`
over a plain `list`. This holds regardless of `data_rows`' own traversal
order and regardless of any dict/set/Counter iteration/insertion order,
including across different Python versions or hash-randomization seeds.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import Finding

_CHECK_NAME = "duplicate_rsid_check"
_MAX_SAMPLE_SIZE = 10


class DuplicateRsidCheck:
    """Reports rows whose RSID value occurs in two or more rows of a
    file (FR-8).

    Stateless: holds no constructor-injected configuration and no
    mutable state of any kind, mirroring MalformedRowCheck's,
    DuplicateHeaderCheck's, and MissingValueScanner's identical pattern.
    Given the same inputs, `check()` always returns a field-for-field
    identical Finding (NFR-3).
    """

    def check(
        self,
        data_rows: Sequence[DataRow],
        rsid_column_index: int,
    ) -> Finding:
        """Identify duplicated RSID values and report the affected rows
        as one Finding.

        Args:
            data_rows: A sequence of already-in-memory, already-parsed
                DataRow instances (e.g. the output of RowParser.parse()).
                No file I/O is performed; `data_rows` must already be in
                memory. Rows may legitimately vary in field-count width
                (e.g. malformed rows); see the out-of-bounds handling
                below.
            rsid_column_index: A single, already-resolved field-position
                index identifying this file's RSID column. This method
                performs no resolution, validation, or interpretation of
                this index beyond using it to index into `row.fields`.

        Returns:
            A Finding whose `count` is the total number of rows, across
            the full, unsampled `data_rows` collection, whose RSID value
            occurs in two or more rows (every row belonging to any
            duplicated-value group, summed across all such groups);
            whose `examples` and `affected_row_refs` are bounded samples
            (maximum 10 entries) of that same affected-row population, in
            ascending `line_index` order; and whose `check_name`/
            `description` identify this check. If `data_rows` is empty,
            or no RSID value occurs in two or more rows, the returned
            Finding has `count == 0`, `examples == ()`, and
            `affected_row_refs == ()`.

        Raises:
            This method introduces no exception handling of its own and
            depends on no exception hierarchy. Duplicate-RSID conditions
            are always reported as Finding data, never raised as
            exceptions. An `rsid_column_index` outside the bounds of a
            particular row's `fields` tuple contributes no observation
            for that row and never raises.
        """
        observations: list[tuple[DataRow, str]] = [
            (row, row.fields[rsid_column_index])
            for row in data_rows
            if rsid_column_index < len(row.fields)
        ]
        # Out-of-bounds rows are excluded by the list-comprehension
        # guard above: no observation contributed, no exception raised.
        # `observations` preserves data_rows' own traversal order at
        # this point, but that order is never relied upon below -- it
        # is only ever re-derived by explicit line_index sorting.

        if not observations:
            return self._empty_finding()

        # Used only to test "does this value occur >= 2 times?" via O(1)
        # membership/count lookups. Never iterated to produce output.
        value_frequency: Counter[str] = Counter(
            value for _, value in observations
        )
        duplicated_values: frozenset[str] = frozenset(
            value for value, frequency in value_frequency.items() if frequency >= 2
        )
        # `duplicated_values` is consulted only via `in` (membership),
        # which does not depend on set iteration order for correctness.

        if not duplicated_values:
            return self._empty_finding()

        affected_rows: list[DataRow] = sorted(
            (row for row, value in observations if value in duplicated_values),
            key=lambda row: row.line_index,
        )
        # The sole ordering basis for the affected-row population is
        # this explicit ascending DataRow.line_index sort -- never
        # dict/set/Counter iteration order, and never `observations`' or
        # `data_rows`' own traversal order. A new list is built;
        # `data_rows` and its DataRow instances are never mutated.

        total_affected_row_count = len(affected_rows)
        # `count` is the length of this fully-materialized, explicitly
        # ordered list -- a plain, deterministic integer, unaffected by
        # how `affected_rows` came to be ordered.

        sampled_rows = affected_rows[:_MAX_SAMPLE_SIZE]

        return Finding(
            check_name=_CHECK_NAME,
            description=(
                f"Rows whose RSID value (at field position "
                f"{rsid_column_index}) occurs in two or more rows: "
                f"{len(duplicated_values)} duplicated RSID value(s) found."
            ),
            count=total_affected_row_count,
            examples=tuple(
                self._render_example(row, rsid_column_index)
                for row in sampled_rows
            ),
            affected_row_refs=tuple(row.line_index for row in sampled_rows),
        )

    def _empty_finding(self) -> Finding:
        """Return the canonical zero-count Finding used when no
        observation exists -- because `data_rows` is empty, every row
        had an out-of-bounds `rsid_column_index`, or no observed RSID
        value occurred in two or more rows.
        """
        return Finding(
            check_name=_CHECK_NAME,
            description="No duplicated RSID values were observed.",
            count=0,
            examples=(),
            affected_row_refs=(),
        )

    def _render_example(self, row: DataRow, rsid_column_index: int) -> str:
        """Render a single affected row as an illustrative example
        string.

        The exact serialization format is an implementation-level detail
        not prescribed by FR-8, OUT-7, or the frozen Finding contract
        (mirroring the identical, already-accepted gap in
        MalformedRowCheck's and DuplicateHeaderCheck's own
        example-rendering methods). This renders the row's line_index
        and its observed RSID value, without altering, casting, or
        interpreting the value.
        """
        return f"line_index={row.line_index} rsid={row.fields[rsid_column_index]}"