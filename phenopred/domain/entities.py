# phenopred/domain/entities.py
"""Core data-carrying entities for the PhenoPred domain layer.

Per Architecture v1 (Section 4), this file is the designated home for
GenotypeFile, DataRow, and ProfilingReport. Only DataRow is defined here
at this stage; the remaining entities named by Architecture v1 belong to
modules that have not yet been designed or approved, and are intentionally
absent -- adding them ahead of that work would exceed the scope explicitly
defined for the current module (mirroring the identical incremental-
accretion precedent already established for phenopred/domain/value_objects.py,
where EncodingProfile, Delimiter, CommentBlock, and HeaderInfo were each
added only as their own respective module required them).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DataRow:
    """An immutable, ordered field-value carrier for one parsed data line (FR-4).

    This is a purely descriptive record of a line's field values, once
    split by the file's detected delimiter. It carries no notion of its
    own "correctness": column-count expectations, malformed-row judgments,
    missing-value classification, and every other data-quality condition
    are computed externally -- by downstream QualityCheck implementations
    operating over a collection of DataRow instances -- and are never
    checked, inferred, or asserted by DataRow itself.

    Attributes:
        line_index: The zero-based position of this row within the
            sequence of lines RowParser was given (i.e. the effective,
            already comment-stripped and header-excluded data lines for
            this file). This identifies a row's position within this
            file's own parsed DataRow collection; it is not a
            reconstruction of the row's line number in the original
            source file. Must be non-negative.
        fields: Ordered, unmodified field-value strings, produced by
            splitting the original line on the file's detected delimiter
            character. No casting, coercion, trimming, or other
            alteration is applied to any field value.
    """

    line_index: int
    fields: tuple[str, ...]

    def __post_init__(self) -> None:
        """Enforce the sole invariant named for this entity.

        Per Architecture v1 Section 5, a DataRow cannot be constructed
        with a negative line number. No other validation is performed by
        this entity: field count, expected column count, field content,
        missing-value tokens, formatting, and every other data-quality
        condition are explicitly out of scope here (see class docstring)
        and are never checked by this method or any other part of this
        class.

        Raises:
            ValueError: If `line_index` is negative. This represents an
                invalid value-object construction argument, not an
                ingestion-pipeline failure; no PhenoPredIngestionError
                subclass or other domain-specific exception is used.
        """
        if self.line_index < 0:
            raise ValueError(
                f"line_index must be non-negative, got {self.line_index}"
            )
