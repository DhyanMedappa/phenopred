# phenopred/domain/value_objects.py
"""Small, immutable descriptors used across the domain layer.

Per Architecture v1 (Section 4), this module is the designated home for
value objects such as Delimiter, EncodingProfile, ColumnLayout,
ChromosomeLabelCount, GenotypeLengthDistribution, and MissingValueToken.

EncodingProfile and Delimiter are defined here because they have been
approved by their respective architecture decisions. The remaining value
objects belong to modules (header_resolver, quality_checks,
genomic_profiling) that have not yet been designed or approved; adding
them ahead of that work would exceed the scope explicitly defined for the
current module (Stage 1 Engineering Review, Section 7 / Section 16).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EncodingProfile:
    """Reported encoding characteristics for a single byte sample (FR-13).

    This is a purely descriptive report of what was observed about a
    byte sample. It does not select, recommend, or imply a "correct"
    encoding for the source file — that determination is explicitly out
    of scope for the component that produces this value (EncodingDetector)
    and for this value object itself.

    Attributes:
        bom_present: Whether the byte sample begins with a UTF-8
            byte-order-mark sequence (0xEF 0xBB 0xBF), determined by
            direct byte-prefix inspection rather than inferred from any
            decode attempt.
        ascii_decodable: Whether the byte sample decodes successfully
            under strict ASCII.
        utf8_decodable: Whether the byte sample decodes successfully
            under UTF-8.
        utf8_sig_decodable: Whether the byte sample decodes successfully
            under UTF-8 with signature handling (utf-8-sig).
        latin1_decodable: Whether the byte sample decodes successfully
            under Latin-1 (ISO-8859-1). Latin-1 is a bijective, total
            mapping over all byte values 0x00-0xFF, so this is always
            True for any bytes input.
    """

    bom_present: bool
    ascii_decodable: bool
    utf8_decodable: bool
    utf8_sig_decodable: bool
    latin1_decodable: bool


@dataclass(frozen=True, slots=True)
class Delimiter:
    """Reported field delimiter for a single file's data lines (FR-2).

    This is a purely descriptive report of what was observed: it names the
    delimiter character found and the method used to find it. It does not
    carry a confidence score, alternative candidates considered, or any
    other metadata, mirroring EncodingProfile's purely descriptive design.

    Attributes:
        character: The single delimiter character detected (e.g. '\\t').
        detection_method: A short, stable label identifying how the
            delimiter was detected (e.g. "character_frequency_analysis"),
            supporting per-finding traceability (NFR-6).
    """

    character: str
    detection_method: str


@dataclass(frozen=True, slots=True)
class CommentBlock:
    """Ordered, verbatim comment/metadata lines separated from a file's
    data lines (FR-1).

    This is a purely descriptive container: it holds exactly the comment
    lines RawLineSplitter classified, in their original order, with no
    alteration. It carries no position information and does not assume
    comment lines are confined to a leading, contiguous run of the file.

    A GenotypeFile always has exactly one CommentBlock, even when a file
    has no comment lines at all; the empty case is represented as
    lines=(), count=0, never as a null/absent value.

    Attributes:
        lines: Ordered, verbatim comment lines, in original file order.
        count: Number of entries in `lines` (equal to len(lines)).
    """

    lines: tuple[str, ...]
    count: int


@dataclass(frozen=True, slots=True)
class HeaderInfo:
    """Reported header form and resolved column names for a single file
    (FR-3).

    This is a purely descriptive report of what was observed: it names
    the header's form, the resolved column-name list (when one could be
    determined), and the exact original line the header was resolved
    from. It carries no confidence score and performs no validation of
    its own fields, mirroring EncodingProfile/Delimiter/CommentBlock's
    purely descriptive, behavior-free design.

    Attributes:
        form: One of "uncommented_row", "commented_only", or "absent",
            classifying where (or whether) a header was found.
        resolved_columns: Ordered column names, split by the file's
            detected delimiter, from whichever line was identified as
            the header; None when form is "absent".
        source_line: The exact, verbatim original line (data line or
            comment line) identified as the header; None when form is
            "absent".
    """

    form: str
    resolved_columns: tuple[str, ...] | None
    source_line: str | None


@dataclass(frozen=True, slots=True)
class Finding:
    """Reported outcome of a single data-quality check over a file's parsed
    data rows (FR-5 through FR-9).

    This is a purely descriptive record of what a QualityCheck observed.
    It carries no corrective action or resolution -- only what was found --
    mirroring EncodingProfile/Delimiter/CommentBlock/HeaderInfo's
    purely descriptive, behavior-free design.

    Attributes:
        check_name: A short, stable label identifying which check produced
            this Finding (e.g. "duplicate_header_check"), supporting
            per-finding traceability (NFR-6).
        description: A short, human-readable description of what was
            checked and found.
        count: The total number of occurrences found across the full,
            unsampled data-row collection.
        examples: A bounded sample (maximum 10 entries) of illustrative
            examples of the finding, in original row order. Empty when
            count is 0.
        affected_row_refs: A bounded sample (maximum 10 entries) of the
            line_index values of affected rows, in original row order.
            Empty when count is 0.
    """

    check_name: str
    description: str
    count: int
    examples: tuple[str, ...]
    affected_row_refs: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ColumnLayout:
    """Reported column-role identity for a single file, resolved from its
    own HeaderInfo (Column Identity Resolution).

    This is a purely descriptive report of which field-position indices
    correspond to which semantic roles for this file, mirroring
    EncodingProfile/Delimiter/CommentBlock/HeaderInfo/Finding/
    ChrPosColumnIndices's identical invariant-free, purely descriptive,
    behavior-free design. It carries no biological interpretation of
    column content -- only field-position identity, resolved entirely
    from this file's own resolved column names (never a fixed,
    hard-coded schema, per NFR-5/AD-5).

    Fields are restricted to exactly what existing, already-approved
    consumers require:
        - DuplicateRsidCheck requires rsid_column_index.
        - DuplicateChrPosCheck requires chromosome_column_index and
          position_column_index (via ChrPosColumnIndices).
        - MissingValueScanner requires designated_column_indices.

    Attributes:
        rsid_column_index: Field-position index of this file's RSID
            column.
        chromosome_column_index: Field-position index of this file's
            chromosome column.
        position_column_index: Field-position index of this file's
            position column.
        designated_column_indices: Field-position indices of this
            file's designated genotype/allele column(s), in ascending
            index order. May be empty when none of the configured
            designated-column keywords were found among this file's
            resolved column names.
    """

    rsid_column_index: int
    chromosome_column_index: int
    position_column_index: int
    designated_column_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ChrPosColumnIndices:
    """Reported column identity for a file's chromosome and position
    fields, as a single, pre-resolved composite key (FR-9).

    This is a purely descriptive container of two named field-position
    indices, delivered via the QualityCheck interface's context
    parameter to DuplicateChrPosCheck. It carries no behavior and no
    construction-time invariant -- mirroring EncodingProfile/Delimiter/
    CommentBlock/HeaderInfo/Finding's identical invariant-free, purely
    descriptive design. Per ADR 1 ("Column-Identity Input Contract for
    DuplicateChrPosCheck"), this value object exists because FR-9 names
    exactly two fixed, non-interchangeable semantic roles -- chromosome
    and position -- that a bare int (wrong cardinality), a Sequence[int]
    (implies interchangeable same-role columns), or a bare tuple[int, int]
    (no protection against role transposition) could not correctly or
    safely represent.

    Attributes:
        chromosome_column_index: A single field-position index
            identifying this file's chromosome column, already resolved
            by the caller. Not validated by this value object; bounds-
            validity per row is DuplicateChrPosCheck's own runtime
            concern, never this value object's.
        position_column_index: A single field-position index
            identifying this file's position column, already resolved
            by the caller. Not validated by this value object, for the
            same reason as chromosome_column_index.
    """

    chromosome_column_index: int
    position_column_index: int
