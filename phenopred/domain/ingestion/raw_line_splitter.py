# phenopred/domain/ingestion/raw_line_splitter.py
"""Domain-layer component separating comment lines from data lines (FR-1).

RawLineSplitter is the sole component responsible for classifying each raw
line of a file as either a comment/metadata line or a candidate data line,
by exact prefix match, without discarding either group. Per Architecture
v1 (Section 4/5/6/9) and the Stage 1 Engineering Review:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a plain sequence of line strings already produced
  upstream (RawFileContent.lines); it never accepts, imports, or depends
  on RawFileContent, RawFileLoader, or any file path. This mirrors the
  input-contract precedent already locked for EncodingDetector and
  DelimiterDetector.
- Comment detection is a per-line, position-zero prefix test only
  (line.startswith(comment_prefix)); it has no awareness of position or
  contiguity, consistent with Architecture v1 Section 6's description of
  CommentBlock as holding "all comment lines" and Section 9's description
  of the splitter as separating lines "by prefix." A comment line found
  anywhere in the file -- not only in a leading run -- is classified as a
  comment.
- No line's content is trimmed, stripped, cased, or otherwise altered.
  Leading whitespace before the prefix does not create a match (e.g.
  " #comment" is a data line, not a comment line).
- It never performs header detection, delimiter detection, row parsing,
  or malformed-row validation -- those are separate FRs implemented by
  separate modules (header_resolver, delimiter_detector, row_parser,
  malformed_row_check).
- It raises no exceptions: no failure mode for comment/data classification
  is named anywhere in Architecture v1 Section 13.1's structural/
  infrastructure-error list, unlike DelimiterDetector's "no delimiter
  detected" condition. A prefix check against a string either matches or
  it doesn't; there is no unreachable or error state to guard against.
"""

from __future__ import annotations

from collections.abc import Sequence

from phenopred.domain.value_objects import CommentBlock


class RawLineSplitter:
    """Separates comment lines from candidate data lines (FR-1).

    Stateless with respect to any single `split()` call's input: the only
    state held is the injected `comment_prefix`, set once at construction
    and never reassigned. Given the same input lines, `split()` always
    returns a field-for-field identical result (NFR-3).
    """

    def __init__(self, comment_prefix: str) -> None:
        """Initialize the splitter with an injected comment prefix.

        Args:
            comment_prefix: The literal prefix identifying a comment line
                (e.g. '#'). Mandatory, no internal default, mirroring
                RawFileLoader's and DelimiterDetector's identical
                constructor pattern. Supplied by the caller (typically
                via ConfigProvider through the composition root, per
                Architecture v1 Section 11); this splitter never reads
                configuration directly.
        """
        self._comment_prefix = comment_prefix

    def split(
        self, lines: Sequence[str]
    ) -> tuple[CommentBlock, tuple[str, ...]]:
        """Partition `lines` into comment lines and candidate data lines.

        Args:
            lines: A sequence of already-in-memory raw lines (e.g.
                RawFileContent.lines). No file I/O is performed; `lines`
                must already be in memory. Line values are never altered,
                trimmed, or otherwise normalized by this method, and the
                input sequence itself is never mutated.

        Returns:
            A 2-tuple of (CommentBlock, candidate_data_lines):
            - CommentBlock: every line starting with `comment_prefix`,
              in original order, preserved verbatim.
            - candidate_data_lines: every remaining line, in original
              order, preserved verbatim, as a plain tuple[str, ...].

            Both may be empty (an all-data file yields an empty
            CommentBlock; an all-comment file yields an empty candidate
            data-lines tuple; an empty `lines` input yields both empty).
            This method never raises.
        """
        comment_lines: list[str] = []
        data_lines: list[str] = []

        for line in lines:
            if line.startswith(self._comment_prefix):
                comment_lines.append(line)
            else:
                data_lines.append(line)

        comment_block = CommentBlock(
            lines=tuple(comment_lines),
            count=len(comment_lines),
        )
        return comment_block, tuple(data_lines)
