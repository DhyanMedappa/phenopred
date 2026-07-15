# phenopred/domain/ingestion/row_parser.py
"""Domain-layer component splitting each data line into ordered fields (FR-4).

RowParser is the sole component responsible for mechanically splitting an
already-in-memory data line into an ordered sequence of field values,
using an already-detected delimiter character, and packaging each
resulting line as a DataRow. Per Architecture v1 (Section 4/5/6/10) and
the approved RowParser design specification:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a plain sequence of line strings already produced
  upstream -- the effective data lines: comment-stripped by
  RawLineSplitter, and header-excluded by ProfileFileUseCase where
  applicable -- and an already-detected Delimiter value object (from
  DelimiterDetector). It never accepts, imports, or depends on
  RawFileContent, RawFileLoader, CommentBlock, RawLineSplitter,
  DelimiterDetector, HeaderInfo, or HeaderResolver; it consumes only the
  plain-data outputs those modules produce, never their classes or
  modules.
- Comment/data separation (FR-1), delimiter detection (FR-2), and header
  resolution/exclusion (FR-3) are explicitly out of scope for this
  component; all three are assumed already correct and already applied
  by the time RowParser receives its `lines` argument. RowParser has no
  awareness of headers, comments, or the delimiter-detection process --
  it treats every line it receives identically.
- It performs mechanical splitting only: no casting, coercion, trimming,
  or other alteration of field values (FR-4). It makes no judgment about
  a row's "correctness" -- column-count expectations, malformed-row
  detection, missing-value classification, and every other data-quality
  condition are the exclusive, later responsibility of downstream
  QualityCheck implementations (FR-5 through FR-9), operating over the
  DataRow collection this component produces. A line with zero
  delimiter occurrences, or with more delimiter occurrences than any
  other line, is parsed identically to every other line -- no branching
  or special-casing based on the resulting field count occurs here.
- It introduces no domain-specific exception and depends on nothing in
  phenopred/domain/errors.py. It performs no delimiter validation of any
  kind: it trusts that `delimiter.character` is a valid, usable
  separator, exactly as guaranteed by DelimiterDetector's fixed candidate
  set ("\t", ",", ";", "|") under normal, contract-respecting pipeline
  execution. A manually constructed Delimiter with an invalid
  `character` value (e.g. an empty string) is outside this component's
  responsibility; RowParser's mechanical split is not guaranteed to
  succeed against such a value, and no defensive check is introduced to
  guard against it -- this is a documented dependency assumption, not an
  absolute guarantee of this method.
"""

from __future__ import annotations

from collections.abc import Sequence

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import Delimiter


class RowParser:
    """Splits each data line into an ordered DataRow using the detected delimiter (FR-4).

    Stateless: holds no constructor-injected configuration and no mutable
    state of any kind, since FR-4 names no configurable convention for
    this component (unlike RawFileLoader's sample_size, DelimiterDetector's
    sample_size, RawLineSplitter's comment_prefix, or HeaderResolver's
    header_keyword). Given the same inputs, `parse()` always returns a
    field-for-field identical result (NFR-3).
    """

    def parse(
        self, lines: Sequence[str], delimiter: Delimiter
    ) -> tuple[DataRow, ...]:
        """Split every line in `lines` into an ordered DataRow.

        Args:
            lines: A sequence of already-in-memory effective data lines
                (comment-stripped and, where applicable, header-excluded
                upstream). No file I/O is performed; `lines` must already
                be in memory. Every line is parsed identically -- no
                special-casing of blank lines, lines with no delimiter
                occurrences, or lines with more delimiter occurrences
                than any other line.
            delimiter: The already-detected field delimiter (e.g. the
                output of DelimiterDetector.detect()), used to split each
                line via its `.character` field.

        Returns:
            A tuple of DataRow instances, one per entry in `lines`, in
            original order. Each DataRow's `line_index` is its zero-based
            position within `lines`; each DataRow's `fields` is the
            ordered, unmodified result of splitting that line on
            `delimiter.character`.

        Raises:
            This method introduces no exception handling of its own and
            depends on no exception hierarchy. Under valid pipeline
            execution -- a `delimiter` produced by DelimiterDetector --
            this method does not raise. It performs no defensive
            validation of `delimiter.character`; a manually constructed,
            invalid Delimiter is outside this method's responsibility and
            its behavior in that case is not guaranteed by this method.
        """
        return tuple(
            DataRow(
                line_index=index,
                fields=tuple(line.split(delimiter.character)),
            )
            for index, line in enumerate(lines)
        )
