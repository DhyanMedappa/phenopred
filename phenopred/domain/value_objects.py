# phenopred/domain/value_objects.py
"""Small, immutable descriptors used across the domain layer.

Per Architecture v1 (Section 4), this module is the designated home for
value objects such as Delimiter, EncodingProfile, ColumnLayout,
ChromosomeLabelCount, GenotypeLengthDistribution, and MissingValueToken.

EncodingProfile and Delimiter are defined here because they have been
approved by their respective architecture decisions. ChromosomeLabelInventory,
GenotypeLayoutProfile, IndelHaploidProfile, and
GenotypeChromosomeColumnIndices are defined here because they have been
approved by the Genomic Profiling (FR-10-FR-12) Final Architecture Freeze
(ADR-1 through ADR-7). Any further value object -- including any
additional genomic-profiling value object not named above -- still
requires its own recorded architecture decision before being added to
this module; adding one ahead of that approval would exceed the scope
explicitly defined for the current module (Stage 1 Engineering Review,
Section 7 / Section 16).
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


@dataclass(frozen=True, slots=True)
class ChromosomeLabelInventory:
    """Reported chromosome-label inventory for a single file, resolved
    entirely from that file's own observed data (FR-10).

    This is a purely descriptive report of which chromosome label values
    were observed and how many rows carried each one, mirroring
    EncodingProfile/Delimiter/CommentBlock/HeaderInfo/Finding/
    ColumnLayout/ChrPosColumnIndices's identical invariant-free, purely
    descriptive, behavior-free design. It carries no biological
    interpretation of any label -- it neither maps, translates, nor
    reconciles chromosome codes across files (FR-10's own text:
    "without assuming that chromosome labels are equivalent or directly
    comparable across files"; RISK-1, RISK-2). Value objects represent
    required descriptive observations without performing biological
    interpretation.

    No fixed chromosome-label vocabulary is assumed anywhere in this
    value object or in the profiler that produces it: every label
    observed in the file is reported, whatever its form. The
    implementation should remain robust against unexpected structural
    variations and should not encode assumptions that are only valid
    for the two evidence datasets (ADR-6).

    Ordering contract (ADR-4): `label_counts` is ordered by ascending
    first-observed `DataRow.line_index` -- never by descending count or
    any other frequency-based ordering. This mirrors the neutral,
    interpretation-free ordering basis already used elsewhere in this
    codebase as a deterministic tie-break (e.g. MalformedRowCheck,
    DuplicateRsidCheck, DuplicateChrPosCheck), and specifically avoids
    ranking labels by row-count, which would imply an importance
    judgment this value object has no license to make.

    Attributes:
        profiler_name: A short, stable label identifying which profiler
            produced this inventory (e.g. "chromosome_label_profiler"),
            supporting per-profile traceability (NFR-6), mirroring
            Finding.check_name's identical purpose.
        label_counts: Every distinct chromosome label value observed in
            the file, together with its row count, as an ordered tuple
            of (label, count) pairs. Ordered by ascending first-observed
            `DataRow.line_index` per the ordering contract above. Not
            bounded or sampled -- FR-10 requires enumerating every
            distinct label observed, so this holds the full, unsampled
            inventory, unlike Finding.examples/affected_row_refs.
    """

    profiler_name: str
    label_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class GenotypeLayoutProfile:
    """Reported genotype/allele column layout classification and
    length-distribution observations for a single file (FR-11).

    This is a purely descriptive report of the file's designated
    genotype/allele column structure, mirroring EncodingProfile/
    Delimiter/CommentBlock/HeaderInfo/Finding/ColumnLayout/
    ChrPosColumnIndices/ChromosomeLabelInventory's identical
    invariant-free, purely descriptive, behavior-free design. It
    carries no biological interpretation of any observed value, and it
    does not itself perform column-layout classification or
    string-length tallying -- both are computed by the producing
    profiler and merely recorded here. Value objects represent required
    descriptive observations without performing biological
    interpretation.

    Classification contract (ADR-5): `layout_kind` is
    "two_column_allele" if and only if the file's designated-column
    count is exactly 2, "single_column_genotype" if and only if it is
    exactly 1, and "undetermined" for every other count, including 0
    and 3 or more. `column_length_distributions` is computed
    unconditionally for however many designated columns the file has,
    fully decoupled from whether `layout_kind` could be assigned -- the
    descriptive length-distribution data is never withheld on account
    of an ambiguous or absent layout classification. This value object
    therefore supports empty designated-column sets and cardinalities
    beyond the two evidenced layouts without alteration.

    The implementation should remain robust against unexpected
    structural variations and should not encode assumptions that are
    only valid for the two evidence datasets (ADR-6): no fixed
    designated-column count or vendor-specific layout is assumed
    anywhere in this value object.

    Attributes:
        profiler_name: A short, stable label identifying which profiler
            produced this profile (e.g. "genotype_layout_classifier"),
            supporting per-profile traceability (NFR-6), mirroring
            Finding.check_name's identical purpose.
        layout_kind: One of "two_column_allele",
            "single_column_genotype", or "undetermined", per the
            classification contract above.
        column_length_distributions: The observed string-length
            distribution for each designated column, as an ordered
            tuple of (designated_column_index, length_distribution)
            pairs, one entry per designated column, in ascending
            column-index order. Each length_distribution is itself an
            ordered tuple of (length, count) pairs, in ascending length
            order (ADR-4). Computed unconditionally for however many
            designated columns exist, independent of `layout_kind`.
    """

    profiler_name: str
    layout_kind: str
    column_length_distributions: tuple[
        tuple[int, tuple[tuple[int, int], ...]], ...
    ]


@dataclass(frozen=True, slots=True)
class IndelHaploidProfile:
    """Reported indel-token and haploid/diploid length-classification
    observations for a single file using a single combined genotype
    column (FR-12).

    This is a purely descriptive report of configured token occurrences
    and genotype-length classification on configured sex/mitochondrial
    chromosome labels, mirroring EncodingProfile/Delimiter/CommentBlock/
    HeaderInfo/Finding/ColumnLayout/ChrPosColumnIndices/
    ChromosomeLabelInventory/GenotypeLayoutProfile's identical
    invariant-free, purely descriptive, behavior-free design.
    `haploid_count`, `diploid_count`, and `indel_token_counts` are
    required descriptive classifications named directly by FR-12, not
    biological conclusions: this value object represents required
    descriptive observations without performing biological
    interpretation. It never maps, translates, or reconciles chromosome
    codes across files (RISK-1, RISK-2), and never asserts biological
    meaning for any observed token beyond counting its presence,
    mirroring FR-9's own "without judging the cause" framing.

    Applicability contract: FR-12 applies only to files using a single
    combined genotype column. `applicable` is False, with every count
    at zero, when the file's designated-column count is not exactly 1
    (the two-column-allele case, and any other cardinality) -- this is
    a legitimate, non-error descriptive outcome, never an exception,
    mirroring MissingValueScanner's own precedent that an unsupported
    input shape is reported as a zero-count result, not raised.

    No fixed indel-token vocabulary or chromosome-label vocabulary is
    assumed anywhere in this value object -- both are supplied by the
    caller at the producing profiler's construction time (ADR-2,
    NFR-5). The implementation should remain robust against unexpected
    structural variations and should not encode assumptions that are
    only valid for the two evidence datasets (ADR-6).

    Attributes:
        profiler_name: A short, stable label identifying which profiler
            produced this profile (e.g. "indel_haploid_classifier"),
            supporting per-profile traceability (NFR-6), mirroring
            Finding.check_name's identical purpose.
        applicable: Whether this file's designated-column count was
            exactly 1 (single combined genotype column), per the
            applicability contract above. False for every other
            cardinality, in which case every other field below is
            reported at its zero/empty value.
        indel_token_counts: The observed occurrence count for each
            configured indel token, as an ordered tuple of
            (token, count) pairs, ordered by the producing profiler's
            own constructor-injected token order (ADR-4) -- never by
            frequency.
        haploid_count: The total number of rows on a configured
            sex/mitochondrial chromosome label whose genotype string is
            single-character.
        diploid_count: The total number of rows on a configured
            sex/mitochondrial chromosome label whose genotype string is
            two-character.
    """

    profiler_name: str
    applicable: bool
    indel_token_counts: tuple[tuple[str, int], ...]
    haploid_count: int
    diploid_count: int


@dataclass(frozen=True, slots=True)
class GenotypeChromosomeColumnIndices:
    """Reported column identity for a file's designated genotype
    column(s) and chromosome field, as a single, pre-resolved composite
    context value (FR-12).

    This is a purely descriptive container of two named field-position
    values, delivered via the GenomicProfiler interface's context
    parameter to IndelHaploidClassifier. It carries no behavior and no
    construction-time invariant -- mirroring EncodingProfile/Delimiter/
    CommentBlock/HeaderInfo/Finding/ColumnLayout/ChrPosColumnIndices's
    identical invariant-free, purely descriptive design. Per ADR-2, this
    value object exists because the GenomicProfiler interface exposes a
    single context parameter, and IndelHaploidClassifier needs two
    distinct pieces of column-identity context -- bundling them here
    follows the same minimal value-object approach used elsewhere in
    the codebase, keeping the profiler from having to accept the entire
    ColumnLayout (which would expose fields, such as
    rsid_column_index, it has no business touching). This is not a
    role-transposition safeguard -- ChrPosColumnIndices exists for that
    distinct reason -- since designated_column_indices and
    chromosome_column_index are differently typed and cannot be
    silently swapped for one another.

    Attributes:
        designated_column_indices: This file's already-resolved
            designated genotype/allele column field-position indices,
            already resolved by the caller (i.e. copied from
            ColumnLayout.designated_column_indices). Not validated by
            this value object; interpreting its cardinality (e.g.
            confirming it is exactly 1) is IndelHaploidClassifier's own
            runtime concern, never this value object's.
        chromosome_column_index: A single field-position index
            identifying this file's chromosome column, already resolved
            by the caller (i.e. copied from
            ColumnLayout.chromosome_column_index). Not validated by
            this value object, for the same reason as
            designated_column_indices.
    """

    designated_column_indices: tuple[int, ...]
    chromosome_column_index: int
