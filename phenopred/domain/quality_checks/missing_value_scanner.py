# phenopred/domain/quality_checks/missing_value_scanner.py
"""Domain-layer quality check reporting the frequency of every distinct
literal value observed in a file's designated genotype/allele columns
(FR-6).

MissingValueScanner is the sole component responsible for tallying
literal-value occurrence frequency across a file's designated column(s)
and reporting the result as one Finding. Per Architecture v1 (Section
4/6/10/13.2), the frozen "Column-Identity Input Contract for
MissingValueScanner (FR-6)" ADR, and the frozen "Finding Output Mapping
for MissingValueScanner (FR-6)" ADR:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a plain, already-in-memory collection of DataRow
  instances and a plain, already-resolved Sequence[int] of designated
  column field-position indices, delivered via the QualityCheck
  interface's context parameter. It never accepts, imports, or depends
  on HeaderInfo, HeaderResolver, RawFileLoader, EncodingDetector,
  DelimiterDetector, RawLineSplitter, RowParser (module or class), any
  sibling QualityCheck, any GenomicProfiler, or ReportBuilder.
- MissingValueScanner performs no column-name resolution, no header
  interpretation, and no judgment about which literal token(s) "mean"
  missing or no-call -- it only observes and counts (frozen ADR;
  Architecture v1 Section 14: "token-level observation, not
  validation").
- Per the frozen malformed-row rule: if a designated column index is
  outside the bounds of a particular DataRow's fields tuple, that row
  contributes no observation for that designated column. No exception
  is raised -- this is normal data-quality input, not an error
  condition (Architecture v1 Section 13.2).
- Finding.count is the total number of literal-value OCCURRENCES
  observed across all designated columns (a sum), never the number of
  distinct values.
- Finding.examples/affected_row_refs are bounded to a maximum of 10
  entries, selected and ordered by descending frequency, with ascending
  DataRow.line_index (of each value's first observation) used only to
  break ties among equally-frequent distinct values -- per the frozen
  Finding Output Mapping ADR.
- This component never raises: Architecture v1 Section 13.2 requires
  data-quality conditions to always be represented as Finding data,
  never exceptions.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import Finding

_CHECK_NAME = "missing_value_scanner"
_MAX_SAMPLE_SIZE = 10


class MissingValueScanner:
    """Reports the frequency of every distinct literal value observed in
    a file's designated genotype/allele column(s) (FR-6).

    Stateless: holds no constructor-injected configuration and no
    mutable state of any kind, mirroring MalformedRowCheck's and
    DuplicateHeaderCheck's identical pattern. Given the same inputs,
    `check()` always returns a field-for-field identical Finding
    (NFR-3).
    """

    def check(
        self,
        data_rows: Sequence[DataRow],
        designated_column_indices: Sequence[int],
    ) -> Finding:
        """Tally literal-value occurrence frequency across the
        designated columns and report the result as one Finding.

        Args:
            data_rows: A sequence of already-in-memory, already-parsed
                DataRow instances (e.g. the output of RowParser.parse()).
                No file I/O is performed; `data_rows` must already be in
                memory. Rows may legitimately vary in field-count width
                (e.g. malformed rows); see the out-of-bounds handling
                below.
            designated_column_indices: A plain, already-resolved
                sequence of field-position indices identifying this
                file's designated genotype/allele columns. This method
                performs no resolution, validation, or interpretation of
                these indices beyond using each to index into
                `row.fields`.

        Returns:
            A Finding whose `count` is the total number of literal-value
            occurrences observed across all designated columns, over the
            full, unsampled `data_rows` collection; whose `examples` and
            `affected_row_refs` are bounded samples (maximum 10 entries
            each) of the most frequent distinct values observed, ordered
            by descending frequency with ascending first-observed
            `DataRow.line_index` as a tie-break; and whose
            `check_name`/`description` identify this check. If
            `data_rows` or `designated_column_indices` is empty, no
            observation exists and the returned Finding has
            `count == 0`, `examples == ()`, and `affected_row_refs == ()`.

        Raises:
            This method introduces no exception handling of its own and
            depends on no exception hierarchy. Missing-value token
            frequencies are always reported as Finding data, never
            raised as exceptions. A designated column index outside the
            bounds of a particular row's `fields` tuple contributes no
            observation for that row and never raises.
        """
        if not data_rows or not designated_column_indices:
            return self._empty_finding()

        value_frequency: Counter[str] = Counter()
        first_observed_line_index: dict[str, int] = {}

        for row in data_rows:
            row_field_count = len(row.fields)
            for index in designated_column_indices:
                if index >= row_field_count:
                    # Out-of-bounds designated index for this row:
                    # no observation contributed, no exception raised.
                    continue
                value = row.fields[index]
                value_frequency[value] += 1
                existing_first = first_observed_line_index.get(value)
                if existing_first is None or row.line_index < existing_first:
                    first_observed_line_index[value] = row.line_index

        if not value_frequency:
            return self._empty_finding()

        total_occurrences = sum(value_frequency.values())
        distinct_value_count = len(value_frequency)

        ordered_values = sorted(
            value_frequency.keys(),
            key=lambda value: (
                -value_frequency[value],
                first_observed_line_index[value],
            ),
        )
        sampled_values = ordered_values[:_MAX_SAMPLE_SIZE]

        return Finding(
            check_name=_CHECK_NAME,
            description=(
                f"Literal value frequencies observed across "
                f"{len(designated_column_indices)} designated column(s): "
                f"{distinct_value_count} distinct value(s) found."
            ),
            count=total_occurrences,
            examples=tuple(
                self._render_example(value, value_frequency[value])
                for value in sampled_values
            ),
            affected_row_refs=tuple(
                first_observed_line_index[value] for value in sampled_values
            ),
        )

    def _empty_finding(self) -> Finding:
        """Return the canonical zero-count Finding used when no
        observation exists -- because `data_rows` is empty,
        `designated_column_indices` is empty, or no designated index was
        within bounds for any row.
        """
        return Finding(
            check_name=_CHECK_NAME,
            description=(
                "No literal values were observed in the designated "
                "column(s)."
            ),
            count=0,
            examples=(),
            affected_row_refs=(),
        )

    def _render_example(self, value: str, frequency: int) -> str:
        """Render a single distinct value as an illustrative example
        string.

        The exact serialization format ("value (frequency)") is an
        implementation-level detail not prescribed by FR-6, OUT-7, or
        the frozen Finding contract beyond the frozen Finding Output
        Mapping ADR's naming of this format, mirroring the identical,
        already-accepted gap in MalformedRowCheck's and
        DuplicateHeaderCheck's own example-rendering methods.
        """
        return f"{value} ({frequency})"
