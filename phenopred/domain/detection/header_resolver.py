# phenopred/domain/detection/header_resolver.py
"""Domain-layer detector reporting the resolved header form and column
names for a file (FR-3).

HeaderResolver is the sole component responsible for determining whether
the first non-comment line of a file is a column header row, whether a
header is instead documented only inside a comment line, or whether no
header can be resolved at all. Per Architecture v1 (Section 4/5/6/10) and
the Stage 1 Engineering Review:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only plain, already-in-memory value objects produced
  upstream: CommentBlock (from raw_line_splitter) and Delimiter (from
  delimiter_detector), plus a plain sequence of candidate data lines. It
  never accepts, imports, or depends on RawFileContent, RawFileLoader, or
  any file path, mirroring EncodingDetector's and DelimiterDetector's
  locked precedent of a plain-data input contract with no dependency on
  the file-loading adapter.
- Comment/data line separation (FR-1) and delimiter detection (FR-2) are
  explicitly out of scope for this detector; both are assumed already
  correct, as produced by raw_line_splitter and delimiter_detector
  respectively. This detector never re-classifies comment lines and
  never re-derives a delimiter.
- It does not select, recommend, or resolve "effective data rows" (i.e.
  whether the first data line must be excluded once identified as a
  header). That hand-off is owned by ProfileFileUseCase, which derives it
  mechanically from the returned HeaderInfo.form, per the finalized
  architecture decision on this module's interface contract.
- It implements Detector[T] literally: `detect()` accepts the context it
  needs (CommentBlock, candidate data lines, Delimiter) and returns
  exactly one detected value-object, HeaderInfo — never a tuple, never a
  wrapper result type.
- Matching against the first candidate data line (the uncommented-row
  path) is exact-token-equality only, after splitting the line by the
  detected delimiter character. No substring matching, trimming,
  whitespace normalization, case-folding, or other cleanup is applied to
  either the injected header_keyword or any of that line's tokens,
  mirroring RawLineSplitter's exact `startswith()` matching discipline
  for `comment_prefix`. This path is unchanged from the original design.
- Matching against comment lines (the commented-only path) uses the same
  exact-token-equality rule as its base case, but additionally allows one
  narrow, match-only interpretation: if a comment line's first token,
  after splitting by the delimiter, begins with a leading run of
  non-alphanumeric, non-whitespace characters (the comment marker),
  this interpretation assumes comment markers are represented by
  non-alphanumeric marker characters, consistent with the supported file
  formats and current architecture configuration. If a future configuration
  introduces an alphanumeric comment prefix, this fallback intentionally
  becomes inactive rather than changing matching semantics. That leading
  run is disregarded for the purpose of comparing the remainder of that
  one token to header_keyword. This exists because a comment line's marker
  character is written by convention as "marker + space + content" in
  real vendor files (e.g. "# rsid\t..."), not "marker + delimiter +
  content" — so the marker is otherwise inseparable from the header
  keyword by delimiter-splitting alone. This interpretation applies only
  to comment-line token index 0. Per ADR-8, the marker-stripped form of
  that token is also used to construct HeaderInfo.resolved_columns for
  the commented_only form, so that resolved_columns holds semantic
  column names (as HeaderInfo's own field contract, and Architecture v1
  Section 6 step 5, both already specify) rather than a verbatim,
  marker-prefixed artifact; CommentBlock.lines and source_line are
  unaffected and always reflect the original, unmodified line. No
  substring matching, case-folding, or general token cleanup is
  introduced by this interpretation; a token whose content after the
  stripped leading run does not exactly equal header_keyword is not a
  match, and stripping a token with no leading marker run is a no-op
  (the token is returned unchanged).
- It never performs row parsing, quality validation, or genomic
  profiling — those are separate FRs implemented by separate modules
  (row_parser, quality_checks, genomic_profiling).
- `detect()` never raises. A file with no resolvable header is a
  legitimate, expected outcome (form == "absent"), not a failure
  condition — unlike DelimiterDetector's "no delimiter detected" case,
  "no header resolvable" is not named by Architecture v1 Section 13.1 as
  a structural/infrastructure error. This detector never raises, imports,
  or depends on PhenoPredIngestionError or any of its subclasses
  (phenopred/domain/errors.py).
"""

from __future__ import annotations

from collections.abc import Sequence

from phenopred.domain.value_objects import CommentBlock, Delimiter, HeaderInfo


class HeaderResolver:
    """Resolves header form and column names for a file (FR-3).

    Stateless with respect to any single `detect()` call's input: the only
    state held is the injected `header_keyword`, set once at construction
    and never reassigned. Given the same inputs, `detect()` always returns
    a field-for-field identical HeaderInfo (NFR-3).
    """

    def __init__(self, header_keyword: str) -> None:
        """Initialize the resolver with an injected header keyword.

        Args:
            header_keyword: The token used to recognize a header line
                (e.g. "rsid"). Mandatory, no internal default, mirroring
                RawLineSplitter's and DelimiterDetector's identical
                constructor pattern. Supplied by the caller (typically
                via ConfigProvider through the composition root, per
                Architecture v1 Section 11); this resolver never reads
                configuration directly.
        """
        self._header_keyword = header_keyword

    def detect(
        self,
        comment_block: CommentBlock,
        data_lines: Sequence[str],
        delimiter: Delimiter,
    ) -> HeaderInfo:
        """Resolve the header form and column names for a file.

        Args:
            comment_block: The already-classified comment lines for the
                file (e.g. the first element of RawLineSplitter.split()'s
                return tuple). Consulted only if no uncommented header is
                found among `data_lines`.
            data_lines: A sequence of already-in-memory candidate data
                lines (e.g. the second element of RawLineSplitter.split()'s
                return tuple). Only the first entry is inspected. No file
                I/O is performed; `data_lines` must already be in memory.
            delimiter: The already-detected field delimiter (e.g. the
                output of DelimiterDetector.detect()), used to split a
                candidate header line into tokens.

        Returns:
            A HeaderInfo describing the resolved header form, the
            resolved column names (or None), and the exact source line
            the header was resolved from (or None). This method never
            raises.
        """
        if data_lines:
            first_line = data_lines[0]
            tokens = first_line.split(delimiter.character)
            if self._header_keyword in tokens:
                return HeaderInfo(
                    form="uncommented_row",
                    resolved_columns=tuple(tokens),
                    source_line=first_line,
                )

        for comment_line in comment_block.lines:
            tokens = comment_line.split(delimiter.character)
            if self._header_keyword in tokens or (
                tokens and self._marker_stripped_token_matches(tokens[0])
            ):
                # Per ADR-8: resolved_columns must contain semantic
                # column names, not verbatim tokens, for the
                # commented_only form -- source_line (below) remains
                # the exact, unmodified original comment line
                # regardless. Only token index 0 is ever affected,
                # mirroring the marker interpretation's own documented
                # scope; token 0's marker-stripped form is a no-op
                # (returns the token unchanged) when no leading marker
                # run is present, so this applies uniformly and safely
                # to both matching paths above. Tokens at every other
                # index are passed through unmodified.
                semantic_columns = (
                    (self._strip_marker(tokens[0]), *tokens[1:])
                    if tokens
                    else tuple(tokens)
                )
                return HeaderInfo(
                    form="commented_only",
                    resolved_columns=tuple(semantic_columns),
                    source_line=comment_line,
                )

        return HeaderInfo(
            form="absent",
            resolved_columns=None,
            source_line=None,
        )

    def _marker_stripped_token_matches(self, token: str) -> bool:
        """Return whether `token`, with a leading comment-marker run and
        one following run of whitespace disregarded, exactly equals
        `header_keyword`.

        This is a match-only interpretation: it is never used to alter
        any stored value. A "marker run" is a leading, contiguous run of
        characters that are neither alphanumeric nor whitespace (e.g.
        '#', ';;'); stripping stops at the first alphanumeric or
        whitespace character. Any whitespace immediately following that
        run is also disregarded, then the remainder is compared to
        header_keyword for exact equality only — no substring matching,
        no case-folding, and no further cleanup of the remainder.
        """
        return self._strip_marker(token) == self._header_keyword

    def _strip_marker(self, token: str) -> str:
        """Return `token` with a leading comment-marker run and one
        following run of whitespace disregarded.

        A "marker run" is a leading, contiguous run of characters that
        are neither alphanumeric nor whitespace (e.g. '#', ';;');
        stripping stops at the first alphanumeric or whitespace
        character. Any whitespace immediately following that run is
        also disregarded. No substring matching, case-folding, or
        further cleanup of the remainder is performed. A token with no
        such leading marker run is returned unchanged (stripping is a
        no-op in that case).

        This method holds the single, shared implementation of the
        marker-stripping rule: `_marker_stripped_token_matches` uses it
        to decide whether a comment-line header match occurred, and
        `detect()` uses it to construct the semantic column name stored
        in `HeaderInfo.resolved_columns` for the commented_only header
        form (ADR-8) -- the same stripped value in both cases, computed
        once, here.
        """
        index = 0
        length = len(token)
        while index < length and not token[index].isalnum() and not token[index].isspace():
            index += 1
        while index < length and token[index].isspace():
            index += 1
        return token[index:]