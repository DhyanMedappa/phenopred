# phenopred/domain/errors.py
"""Domain-level exception hierarchy for PhenoPred file-ingestion failures.

These exceptions represent conditions under which a source file cannot be
safely or completely read. They are raised by infrastructure adapters
(e.g. RawFileLoader) and are intended to be caught by application-layer
orchestration (e.g. ProfileFileUseCase), per Architecture v1, Section 13.1.

Data-quality conditions (malformed rows, duplicates, missing-value tokens)
are deliberately NOT represented here — those are reported as Finding
data by domain quality checks, never raised as exceptions (AD-6).
"""

from __future__ import annotations

from pathlib import Path


class PhenoPredIngestionError(Exception):
    """Base class for all file-ingestion failures.

    Raised when a source file cannot be safely read, independent of the
    file's structural or data-quality characteristics.
    """

    def __init__(self, message: str, *, path: Path) -> None:
        super().__init__(message)
        self.path = path


class SourceFileNotFoundError(PhenoPredIngestionError):
    """Raised when the source file path does not exist."""


class SourceFileUnreadableError(PhenoPredIngestionError):
    """Raised when the source file exists but cannot be opened for reading
    (e.g. a permissions error, or the path is not a regular file)."""


class EmptySourceFileError(PhenoPredIngestionError):
    """Raised when the source file is accessible but contains zero bytes."""


class SourceFileReadError(PhenoPredIngestionError):
    """Raised when an unexpected I/O failure occurs while reading the file."""