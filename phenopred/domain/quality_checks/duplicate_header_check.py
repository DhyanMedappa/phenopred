# phenopred/domain/quality_checks/duplicate_header_check.py
"""Domain-layer quality check reporting data rows that verbatim-duplicate
the file's column header row (FR-7).

DuplicateHeaderCheck is the sole component responsible for detecting and
counting DataRow entries whose fields exactly duplicate a file's resolved
header content. Per Architecture v1 (Section 4/6/9/10) and the frozen
DuplicateHeaderCheck design/approval decisions:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only already-in-memory value objects produced upstream:
  a sequence of DataRow (from RowParser) and a HeaderInfo (from
  HeaderResolver). It never accepts, imports, or depends on
  RawFileContent, RawFileLoader, CommentBlock, RawLineSplitter,
  DelimiterDetector, EncodingDetector, or the HeaderResolver/RowParser
  classes/modules themselves -- only the plain-data outputs those
  modules produce.
- Header detection/resolution (FR-3), row parsing (FR-4), delimiter
  detection (FR-2), encoding detection (FR-13), and file loading (FR-14)
  are explicitly out of scope for this check; all are assumed already
  correct and already applied by the time this check receives its
  inputs.
- Comparison is exact tuple equality only: `row.fields ==
  header_info.resolved_columns`. No trimming, whitespace normalization,
  case conversion, or other interpretation is applied to either side of
  the comparison.
- The entire `data_rows` collection is scanned in full -- never a
  sample -- per Architecture v1 Section 17's requirement that full-file
  SRS requirements (which FR-7 is) must not be handled by a sampling
  approach.
- No column-name resolution, schema inference, genotype interpretation,
  RSID inspection, or chromosome/position inspection is performed here
  -- those remain other, separate quality checks' and profilers'
  exclusive responsibilities (FR-6, FR-8, FR-9, FR-10, FR-11, FR-12).
- It never raises: Architecture v1 Section 13.2 requires data-quality
  conditions to always be represented as Finding data, never exceptions.
  This includes the case where `header_info.resolved_columns is None`
  (no header resolvable) -- treated identically to "zero duplicates
  found", not as an error, mirroring HeaderResolver's own precedent that
  `form == "absent"` is a legitimate, expected descriptive outcome.
- `Finding.examples` and `Finding.affected_row_refs` are each bounded to
  a maximum of 10 entries (the one concrete number Architecture v1
  Section 17 itself names, drawn from the EDA notebook's own "first 10
  examples" reporting convention), in original row order.
- Per Architecture v1 Section 12: `check()` logs, at INFO, this check's
  own name and a count-only summary (duplicate-row count) when it
  completes -- never row content or field values (NFR-4).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import Finding, HeaderInfo

logger = logging.getLogger(__name__)

_CHECK_NAME = "duplicate_header_check"
_MAX_EXAMPLES = 10


class DuplicateHeaderCheck:
    """Detects and reports DataRows that verbatim-duplicate the file's
    resolved header content (FR-7).

    Stateless: holds no constructor-injected configuration and no
    mutable state of any kind, since FR-7 names no configurable
    convention for this component. Given the same inputs, `check()`
    always returns a field-for-field identical Finding (NFR-3).
    """

    def check(
        self, data_rows: Sequence[DataRow], header_info: HeaderInfo
    ) -> Finding:
        """Scan `data_rows` for rows that verbatim-duplicate the header.

        Args:
            data_rows: A sequence of already-in-memory, already-parsed
                DataRow instances (e.g. the output of RowParser.parse()).
                No file I/O is performed; `data_rows` must already be in
                memory. Every row is scanned; the full collection is
                always examined, never a sample.
            header_info: The already-resolved HeaderInfo for the file
                (e.g. the output of HeaderResolver.detect()), consumed
                only via its `.resolved_columns` field.

        Returns:
            A Finding describing the total count of duplicate rows found
            and a bounded (maximum 10) sample of illustrative examples
            and affected row references, in original row order. `count`
            is 0, and both bounded collections are empty tuples, when no
            duplicate is found, when `data_rows` is empty, or when
            `header_info.resolved_columns` is None. This method never
            raises, and never mutates `data_rows` or `header_info`.
        """
        resolved_columns = header_info.resolved_columns

        if resolved_columns is None:
            return self._empty_finding()

        matched_examples: list[str] = []
        matched_refs: list[int] = []
        count = 0

        for row in data_rows:
            if row.fields == resolved_columns:
                count += 1
                if len(matched_examples) < _MAX_EXAMPLES:
                    matched_examples.append(str(row.fields))
                    matched_refs.append(row.line_index)

        logger.info("%s: %d duplicate row(s) found", _CHECK_NAME, count)
        return Finding(
            check_name=_CHECK_NAME,
            description=(
                "Data rows that verbatim-duplicate the resolved column "
                "header row."
            ),
            count=count,
            examples=tuple(matched_examples),
            affected_row_refs=tuple(matched_refs),
        )

    def _empty_finding(self) -> Finding:
        """Return the canonical zero-count Finding used both when no
        duplicate is found and when no header content is available to
        duplicate (header_info.resolved_columns is None).
        """
        logger.info("%s: 0 duplicate row(s) found", _CHECK_NAME)
        return Finding(
            check_name=_CHECK_NAME,
            description=(
                "Data rows that verbatim-duplicate the resolved column "
                "header row."
            ),
            count=0,
            examples=(),
            affected_row_refs=(),
        )
