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