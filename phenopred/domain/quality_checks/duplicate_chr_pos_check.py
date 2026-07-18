# phenopred/domain/quality_checks/duplicate_chr_pos_check.py
"""Domain-layer quality check reporting rows whose (chromosome, position)
pair occurs in two or more rows of a file (FR-9).

DuplicateChrPosCheck is the sole component responsible for determining,
for a file's parsed DataRow collection and an already-resolved
ChrPosColumnIndices, which rows carry a (chromosome, position) pair that
recurs elsewhere in the same file, and for reporting the result as one
Finding. Per Architecture v1 (Section 4/6/10/13.2), the frozen
"Column-Identity Input Contract for DuplicateChrPosCheck (FR-9)" ADR, and
the frozen "Finding Output Mapping for DuplicateChrPosCheck (FR-9)" ADR:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a plain, already-in-memory collection of DataRow
  instances and a plain, already-resolved ChrPosColumnIndices, delivered
  via the QualityCheck interface's context parameter. It never accepts,
  imports, or depends on HeaderInfo, HeaderResolver, RawFileLoader,
  EncodingDetector, DelimiterDetector, RawLineSplitter, RowParser (module
  or class), any sibling QualityCheck, any GenomicProfiler, or
  ReportBuilder.
- DuplicateChrPosCheck performs no column-name resolution, no header
  interpretation, and no judgment about the cause of any duplication --
  it only observes and compares literal values (frozen ADR 1/ADR 2;
  FR-9's own text: "without judging the cause of any such duplication").
- Per the frozen malformed-row rule: a row contributes an observation
  only if BOTH chromosome_column_index and position_column_index are
  within that row's fields bounds. If either index is outside the valid range 0 <= index < len(row.fields), the
  row contributes no observation -- no partial pair is ever formed from
  whichever single field happens to be in bounds. No exception is
  raised -- this is normal data-quality input, not an error condition
  (Architecture v1 Section 13.2).
- A (chromosome, position) pair is "duplicated" when it is observed in
  two or more rows. Every row carrying a duplicated pair is counted --
  there is no "first occurrence is exempt" rule (frozen ADR 2).
- Pair equality is exact, literal, per-component string equality. No
  normalization, trimming, case conversion, numeric coercion, or
  biological interpretation of either the chromosome value or the
  position value is ever applied (frozen ADR 2, Driver 9). "1" and "01"
  are distinct values; differing case in an alphabetic label is a
  distinct value.
- Finding.count is the total number of rows belonging to any duplicated
  pair group (a row-population count), never the number of distinct
  duplicated pairs, and never a count of "extra" occurrences after each
  pair's first observation.
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
from phenopred.domain.value_objects import ChrPosColumnIndices, Finding

_CHECK_NAME = "duplicate_chr_pos_check"
_MAX_SAMPLE_SIZE = 10


class DuplicateChrPosCheck:
    """Reports rows whose (chromosome, position) pair occurs in two or
    more rows of a file (FR-9).

    Stateless: holds no constructor-injected configuration and no
    mutable state of any kind, mirroring MalformedRowCheck's,
    DuplicateHeaderCheck's, MissingValueScanner's, and
    DuplicateRsidCheck's identical pattern. Given the same inputs,
    `check()` always returns a field-for-field identical Finding
    (NFR-3).
    """

    def check(
        self,
        data_rows: Sequence[DataRow],
        chr_pos_columns: ChrPosColumnIndices,
    ) -> Finding:
        """Identify duplicated (chromosome, position) pairs and report
        the affected rows as one Finding.

        Args:
            data_rows: A sequence of already-in-memory, already-parsed
                DataRow instances (e.g. the output of RowParser.parse()).
                No file I/O is performed; `data_rows` must already be in
                memory. Rows may legitimately vary in field-count width
                (e.g. malformed rows); see the out-of-bounds handling
                below.
            chr_pos_columns: A single, already-resolved value object
                carrying two named field-position indices --
                `chromosome_column_index` and `position_column_index` --
                identifying this file's chromosome and position columns.
                This method performs no resolution, validation, or
                interpretation of either index beyond using each to
                index into `row.fields`.

        Returns:
            A Finding whose `count` is the total number of rows, across
            the full, unsampled `data_rows` collection, whose
            (chromosome, position) pair occurs in two or more rows
            (every row belonging to any duplicated-pair group, summed
            across all such groups); whose `examples` and
            `affected_row_refs` are bounded samples (maximum 10 entries)
            of that same affected-row population, in ascending
            `line_index` order; and whose `check_name`/`description`
            identify this check. If `data_rows` is empty, or no
            (chromosome, position) pair occurs in two or more rows, the
            returned Finding has `count == 0`, `examples == ()`, and
            `affected_row_refs == ()`.

        Raises:
            This method introduces no exception handling of its own and
            depends on no exception hierarchy. Duplicate-pair conditions
            are always reported as Finding data, never raised as
            exceptions. A `chromosome_column_index` or
            `position_column_index` outside the bounds of a particular
            row's `fields` tuple contributes no observation for that row
            and never raises.
        """
        observations: list[tuple[DataRow, str, str]] = [
            (
                row,
                row.fields[chr_pos_columns.chromosome_column_index],
                row.fields[chr_pos_columns.position_column_index],
            )
            for row in data_rows
            if 0 <= chr_pos_columns.chromosome_column_index < len(row.fields)
            and 0 <= chr_pos_columns.position_column_index < len(row.fields)
        ]
        # A row is excluded entirely by the list-comprehension guard
        # above unless BOTH indices are in bounds: no partial pair is
        # ever formed, no observation contributed, no exception raised.
        # The explicit `0 <=` lower bound is required because Python's
        # negative-indexing semantics would otherwise let a negative
        # index (e.g. -1) pass an upper-bound-only check while silently
        # accessing a field from the end of the tuple -- that is not
        # "in bounds" under ADR 1's contract and must not contribute an
        # observation.
        # `observations` preserves data_rows' own traversal order at
        # this point, but that order is never relied upon below -- it
        # is only ever re-derived by explicit line_index sorting.

        if not observations:
            return self._empty_finding()

        # Used only to test "does this pair occur >= 2 times?" via O(1)
        # membership/count lookups. Never iterated to produce output.
        # Keyed on exact, literal (chromosome_value, position_value)
        # string tuples -- no normalization, trimming, case conversion,
        # or numeric coercion of either component.
        pair_frequency: Counter[tuple[str, str]] = Counter(
            (chr_value, pos_value) for _, chr_value, pos_value in observations
        )
        duplicated_pairs: frozenset[tuple[str, str]] = frozenset(
            pair for pair, frequency in pair_frequency.items() if frequency >= 2
        )
        # `duplicated_pairs` is consulted only via `in` (membership),
        # which does not depend on set iteration order for correctness.

        if not duplicated_pairs:
            return self._empty_finding()

        affected_rows: list[DataRow] = sorted(
            (
                row
                for row, chr_value, pos_value in observations
                if (chr_value, pos_value) in duplicated_pairs
            ),
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
                f"Rows whose (chromosome, position) pair (at field "
                f"positions {chr_pos_columns.chromosome_column_index}, "
                f"{chr_pos_columns.position_column_index}) occurs in two "
                f"or more rows: {len(duplicated_pairs)} duplicated "
                f"pair(s) found."
            ),
            count=total_affected_row_count,
            examples=tuple(
                self._render_example(row, chr_pos_columns)
                for row in sampled_rows
            ),
            affected_row_refs=tuple(row.line_index for row in sampled_rows),
        )

    def _empty_finding(self) -> Finding:
        """Return the canonical zero-count Finding used when no
        observation exists -- because `data_rows` is empty, every row
        had an out-of-bounds `chromosome_column_index` or
        `position_column_index`, or no observed (chromosome, position)
        pair occurred in two or more rows.
        """
        return Finding(
            check_name=_CHECK_NAME,
            description=(
                "No duplicated (chromosome, position) pairs were observed."
            ),
            count=0,
            examples=(),
            affected_row_refs=(),
        )

    def _render_example(
        self, row: DataRow, chr_pos_columns: ChrPosColumnIndices
    ) -> str:
        """Render a single affected row as an illustrative example
        string.

        The exact serialization format is an implementation-level detail
        not prescribed by FR-9, OUT-7, or the frozen Finding contract
        (mirroring the identical, already-accepted gap in
        MalformedRowCheck's, DuplicateHeaderCheck's, and
        DuplicateRsidCheck's own example-rendering methods). This
        renders the row's line_index and its observed chromosome and
        position values, without altering, casting, or interpreting
        either value.
        """
        chromosome_value = row.fields[chr_pos_columns.chromosome_column_index]
        position_value = row.fields[chr_pos_columns.position_column_index]
        return (
            f"line_index={row.line_index} "
            f"chromosome={chromosome_value} position={position_value}"
        )