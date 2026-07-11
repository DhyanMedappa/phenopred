# infrastructure/io/raw_file_loader.py
"""Infrastructure adapter responsible for reading raw genotype source files.

RawFileLoader is the sole component in the PhenoPred pipeline permitted to
open a source file. It reads a file's raw bytes exactly once, performs no
content interpretation beyond confirming the file is readable and
non-empty, and produces an immutable RawFileContent value object consumed
by ProfileFileUseCase.

Per Architecture v1 (Section 13.1) and the approved Stage 1/2 design review:
- No delimiter, encoding, header, or row-level interpretation is performed
  here.
- Encoding *characteristics* (BOM presence, decodability under candidate
  encodings) remain the sole responsibility of EncodingDetector; this
  module's internal Latin-1 decode exists only to produce a lossless
  textual line representation and carries no reporting semantics of its
  own.
- FR-14 / NFR-2: the source file is never modified, moved, renamed,
  rewritten, deduplicated, or reordered.
- NFR-3: given the same input file, load() is deterministic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from phenopred.domain.errors import (
    EmptySourceFileError,
    SourceFileNotFoundError,
    SourceFileReadError,
    SourceFileUnreadableError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RawFileContent:
    """Immutable, lossless raw content read from a single source file.

    Attributes:
        source_path: The path that was read.
        size_bytes: Number of bytes actually read from the file.
        lines: Ordered sequence of raw lines, decoded losslessly (Latin-1),
            one entry per physical line, in original file order. Line
            terminators are not retained.
        line_count: Number of entries in `lines` (equal to len(lines)).
        byte_sample: A bounded prefix of the raw bytes, taken from the
            same single read, for use by EncodingDetector. Never re-read
            from disk.
    """

    source_path: Path
    size_bytes: int
    lines: tuple[str, ...]
    line_count: int
    byte_sample: bytes


class RawFileLoader:
    """Reads a source genotype file's raw content exactly once, read-only.

    This is the only component in the pipeline permitted to open a source
    file. It performs no interpretation of the file's structure or content
    beyond confirming it is readable and non-empty (FR-14, NFR-2).
    """

    def __init__(self, sample_size: int) -> None:
        """Initialize the loader with an injected byte-sample size.

        Args:
            sample_size: Number of leading bytes to expose as
                `byte_sample` for downstream encoding detection. Must be
                supplied by the caller (typically via ConfigLoader); no
                internal default is provided, consistent with NFR-5's
                prohibition on hard-coded structural assumptions.
        """
        self._sample_size = sample_size

    def load(self, path: Path) -> RawFileContent:
        """Read a source file's full raw content exactly once.

        Args:
            path: Path to the source file to read.

        Returns:
            A RawFileContent instance describing the file's raw lines, a
            bounded byte sample, and basic size metadata.

        Raises:
            SourceFileNotFoundError: If `path` does not exist.
            SourceFileUnreadableError: If `path` exists but is not a
                regular, readable file.
            EmptySourceFileError: If the file is readable but contains
                zero bytes.
            SourceFileReadError: If an unexpected I/O failure occurs
                during the read.
        """
        self._validate_path(path)
        raw_bytes = self._read_raw_bytes(path)

        if not raw_bytes:
            logger.error("Source file is empty: path=%s", path)
            raise EmptySourceFileError(
                f"Source file is empty: {path}", path=path
            )

        byte_sample = self._extract_byte_sample(raw_bytes)
        lines = self._decode_to_lines(raw_bytes)
        size_bytes = len(raw_bytes)
        line_count = len(lines)

        logger.info(
            "Loaded source file: path=%s size_bytes=%d line_count=%d",
            path,
            size_bytes,
            line_count,
        )

        return RawFileContent(
            source_path=path,
            size_bytes=size_bytes,
            lines=lines,
            line_count=line_count,
            byte_sample=byte_sample,
        )

    def _validate_path(self, path: Path) -> None:
        """Confirm the path exists and is a regular, accessible file.

        Raises:
            SourceFileNotFoundError: If the path does not exist.
            SourceFileUnreadableError: If the path exists but is not a
                regular file (e.g. a directory), or cannot be inspected.
        """
        try:
            exists = path.exists()
        except OSError as err:
            logger.error(
                "Failed to check source path: path=%s error=%s", path, err
            )
            raise SourceFileUnreadableError(
                f"Could not access source path: {path}", path=path
            ) from err

        if not exists:
            logger.error("Source file not found: path=%s", path)
            raise SourceFileNotFoundError(
                f"Source file not found: {path}", path=path
            )

        try:
            is_file = path.is_file()
        except OSError as err:
            logger.error(
                "Failed to inspect source path: path=%s error=%s", path, err
            )
            raise SourceFileUnreadableError(
                f"Could not inspect source path: {path}", path=path
            ) from err

        if not is_file:
            logger.error("Source path is not a regular file: path=%s", path)
            raise SourceFileUnreadableError(
                f"Source path is not a regular file: {path}", path=path
            )

    def _read_raw_bytes(self, path: Path) -> bytes:
        """Perform the single physical read of the source file.

        This is the only method in the pipeline that opens the source
        file. The file is opened read-only and read exactly once.

        Raises:
            SourceFileUnreadableError: If the file cannot be opened
                (e.g. a permissions error).
            SourceFileReadError: If an unexpected I/O failure occurs
                while reading.
        """
        try:
            with path.open("rb") as handle:
                return handle.read()
        except PermissionError as err:
            logger.error(
                "Permission denied reading source file: path=%s", path
            )
            raise SourceFileUnreadableError(
                f"Permission denied reading source file: {path}", path=path
            ) from err
        except OSError as err:
            logger.error(
                "Unexpected I/O error reading source file: path=%s error=%s",
                path,
                err,
            )
            raise SourceFileReadError(
                f"Unexpected I/O error reading source file: {path}", path=path
            ) from err

    def _extract_byte_sample(self, raw_bytes: bytes) -> bytes:
        """Return a bounded prefix of already-read bytes for encoding detection.

        No additional file I/O is performed; the sample is sliced from the
        buffer already produced by `_read_raw_bytes`.
        """
        return raw_bytes[: self._sample_size]

    def _decode_to_lines(self, raw_bytes: bytes) -> tuple[str, ...]:
        """Decode raw bytes into an ordered, lossless sequence of lines.

        Decoding uses Latin-1 (ISO-8859-1), a bijective byte-to-codepoint
        mapping under which every byte value 0x00-0xFF decodes
        unambiguously and decoding can never raise, regardless of the
        file's true encoding. This produces line boundaries and textual
        content without pre-judging or asserting the file's real encoding;
        determining actual encoding characteristics (BOM presence,
        decodability under ASCII/UTF-8/UTF-8-sig/Latin-1) remains the sole
        responsibility of EncodingDetector, operating on `byte_sample`.

        Line splitting is deliberately restricted to the three
        conventional terminators (\\n, \\r\\n, \\r) rather than Python's
        broader `str.splitlines()` semantics, which also splits on control
        characters (e.g. NEL, form feed, file/group/record separators)
        that could legitimately occur as literal byte content within a
        genotype file (see SRS RISK-7: unidentified non-ASCII content).
        Line terminators are not retained in the returned lines.
        """
        text = raw_bytes.decode("latin-1")
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if normalized.endswith("\n"):
            normalized = normalized[:-1]
        return tuple(normalized.split("\n"))