# phenopred/domain/detection/encoding_detector.py
"""Domain-layer detector reporting encoding characteristics (FR-13).

EncodingDetector is the sole component responsible for classifying BOM
presence and decodability of a byte sample under the encodings named by
FR-13/OUT-3. Per Architecture v1 (Section 4/5/6/10) and the Stage 1
Engineering Review:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only a `bytes` sample already produced by RawFileLoader
  (specifically `RawFileContent.byte_sample`); it never imports
  RawFileLoader and never accepts a file path.
- It never modifies its input, and it never modifies RawFileContent.
- It does not select, recommend, or imply a "final" or "best" encoding.
  Its output is purely descriptive (OUT-3); encoding *selection* for
  line-splitting is RawFileLoader's own, independent, already-fixed
  Latin-1 strategy, unaffected by anything this module reports.
- It performs no line splitting, delimiter detection, or header
  resolution — those are separate FRs implemented by separate modules
  (raw_line_splitter, delimiter_detector, header_resolver).
- Because Latin-1 (ISO-8859-1) is a bijective, total mapping over all
  byte values 0x00-0xFF, decoding under Latin-1 can never fail. As a
  consequence, `detect()` never raises: it always returns a well-formed
  EncodingProfile for any `bytes` input, including an empty sample.
"""

from __future__ import annotations

from phenopred.domain.value_objects import EncodingProfile

_UTF8_BOM = b"\xef\xbb\xbf"


class EncodingDetector:
    """Reports BOM presence and decodability of a byte sample (FR-13).

    Stateless and side-effect-free: holds no mutable state, accepts no
    constructor configuration, and is safe for concurrent/repeated use.
    Given the same input bytes, `detect()` always returns field-for-field
    identical results (NFR-3).
    """

    def detect(self, data: bytes) -> EncodingProfile:
        """Classify BOM presence and decodability of `data`.

        Args:
            data: A byte sample to inspect (e.g. `RawFileContent.byte_sample`).
                No file I/O is performed; `data` must already be in memory.

        Returns:
            An EncodingProfile describing BOM presence and decodability
            under ASCII, UTF-8, UTF-8-sig, and Latin-1. This method never
            raises.
        """
        return EncodingProfile(
            bom_present=self._has_utf8_bom(data),
            ascii_decodable=self._is_decodable(data, "ascii"),
            utf8_decodable=self._is_decodable(data, "utf-8"),
            utf8_sig_decodable=self._is_decodable(data, "utf-8-sig"),
            latin1_decodable=self._is_decodable(data, "latin-1"),
        )

    def _has_utf8_bom(self, data: bytes) -> bool:
        """Check for a UTF-8 byte-order-mark by direct byte-prefix
        inspection, independent of any decode attempt (per the approved
        design decision: BOM presence must not be inferred from
        utf-8-sig decode success, since utf-8-sig decodes successfully
        whether or not a BOM is actually present).
        """
        return data.startswith(_UTF8_BOM)

    def _is_decodable(self, data: bytes, encoding: str) -> bool:
        """Attempt to decode `data` under `encoding`, returning whether it
        succeeded. Any UnicodeDecodeError is caught here and translated
        to False; it is never propagated out of this class.
        """
        try:
            data.decode(encoding)
            return True
        except UnicodeDecodeError:
            return False