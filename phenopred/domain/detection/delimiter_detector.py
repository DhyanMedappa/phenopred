# phenopred/domain/detection/delimiter_detector.py
"""Domain-layer detector reporting the empirically detected field delimiter
(FR-2).

DelimiterDetector is the sole component responsible for inferring the field
delimiter character of a file's data lines, via character-frequency
analysis over a sample of already-in-memory lines. Per Architecture v1
(Section 4/5/6/10) and the Stage 1 Engineering Review:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a plain sequence of line strings already produced
  upstream (candidate data lines); it never accepts, imports, or depends
  on RawFileContent, RawFileLoader, or any file path. This mirrors
  EncodingDetector's locked precedent of a plain-data input contract with
  no dependency on the file-loading adapter.
- Comment/data line separation (FR-1) is explicitly out of scope for this
  detector; the lines supplied to `detect()` are assumed to already be
  candidate data lines, per Architecture Section 6 step 4. Whether the
  caller supplies raw, unfiltered lines or comment-filtered lines is an
  integration-time decision made by the caller, not by this detector.
- It does not select, recommend, or imply a delimiter for the file beyond
  what the frequency analysis itself supports; its output is purely
  descriptive (mirroring EncodingProfile's descriptive-only design).
- Unlike EncodingDetector, this detector's underlying condition (no
  candidate delimiter consistently present) is a real, reachable failure
  mode explicitly named by Architecture v1 Section 13.1 ("No delimiter can
  be confidently detected"). Per the approved Stage 2 exception-ownership
  resolution, this detector raises a narrow, detector-local exception
  (DelimiterNotDetectedError, defined in this module) on that condition.
  It never raises, imports, or depends on PhenoPredIngestionError or any
  of its subclasses (phenopred/domain/errors.py) — translating this
  detector-local signal into a typed PhenoPredIngestionError, and
  attaching file-path context, is the exclusive responsibility of
  ProfileFileUseCase.
- It never performs comment/data separation, header resolution, or row
  parsing — those are separate FRs implemented by separate modules
  (raw_line_splitter, header_resolver, row_parser).
"""

from __future__ import annotations

from collections.abc import Sequence

from phenopred.domain.value_objects import Delimiter

# Fixed candidate set, in fixed preference order. The order is used solely
# as a deterministic tie-break when two or more candidates present equally
# strong, equally consistent structural evidence (NFR-3); it never
# overrides a clear, higher-scoring result. Neither the candidate set nor
# its order is configurable, since delimiter detection outcomes must never
# be overridden by configuration (Stage 1 Engineering Review Section 7).
_CANDIDATE_DELIMITERS: tuple[str, ...] = ("\t", ",", ";", "|")

_DETECTION_METHOD = "character_frequency_analysis"


class DelimiterNotDetectedError(Exception):
    """Raised when no candidate delimiter can be confidently and
    consistently detected across the sampled lines.

    This is a detector-local signal, not a member of the
    PhenoPredIngestionError hierarchy (phenopred/domain/errors.py).
    DelimiterDetector never raises, imports, or depends on that hierarchy,
    mirroring EncodingDetector's locked precedent of zero dependency on
    ingestion-error vocabulary. Translating this into a typed
    PhenoPredIngestionError (per Architecture v1 Section 13.1) — including
    attaching the file-path context this detector never has — is the
    exclusive responsibility of ProfileFileUseCase, per the approved
    Stage 2 exception-ownership resolution.
    """


class DelimiterDetector:
    """Infers the field delimiter from a sample of data lines (FR-2).

    Stateless with respect to any single `detect()` call's input: the only
    state held is the injected `sample_size`, set once at construction and
    never reassigned. Given the same input lines, `detect()` always
    returns a field-for-field identical Delimiter (NFR-3).
    """

    def __init__(self, sample_size: int) -> None:
        """Initialize the detector with an injected line-sample size.

        Args:
            sample_size: Number of leading lines (from the sequence passed
                to `detect()`) to examine. Mandatory, no internal default,
                mirroring RawFileLoader's identical constructor pattern.
                Supplied by the caller (typically via ConfigProvider
                through the composition root, per Architecture v1 Section
                11); this detector never reads configuration directly.
        """
        self._sample_size = sample_size

    def detect(self, lines: Sequence[str]) -> Delimiter:
        """Infer the delimiter character used by `lines`.

        Args:
            lines: A sequence of already-in-memory candidate data lines
                (e.g. a slice of RawFileContent.lines, or the data-line
                output of a future raw_line_splitter). No file I/O is
                performed; `lines` must already be in memory. Field
                values within each line are never altered, trimmed, or
                otherwise normalized by this method.

        Returns:
            A Delimiter describing the detected character and the
            detection method used.

        Raises:
            DelimiterNotDetectedError: If no candidate delimiter is both
                present and consistently repeated across every non-empty
                sampled line.
        """
        sample = [line for line in lines[: self._sample_size] if line]

        best_candidate: str | None = None
        best_count = 0

        for candidate in _CANDIDATE_DELIMITERS:
            if not self._is_consistent(sample, candidate):
                continue
            count = sample[0].count(candidate)
            if count > best_count:
                best_candidate = candidate
                best_count = count
            # A count equal to (not greater than) the current best leaves
            # best_candidate untouched, so the earlier, higher-preference
            # candidate in _CANDIDATE_DELIMITERS wins any tie.

        if best_candidate is None:
            raise DelimiterNotDetectedError(
                "No delimiter could be confidently and consistently "
                "detected across the sampled data lines."
            )

        return Delimiter(
            character=best_candidate,
            detection_method=_DETECTION_METHOD,
        )

    def _is_consistent(self, sample: list[str], candidate: str) -> bool:
        """Return whether `candidate` occurs the same non-zero number of
        times in every line of `sample`.

        A candidate with zero occurrences, or with a varying occurrence
        count across sampled lines, is not considered structural evidence
        of that candidate being the file's delimiter.
        """
        if not sample:
            return False
        counts = [line.count(candidate) for line in sample]
        first = counts[0]
        return first > 0 and all(count == first for count in counts)
