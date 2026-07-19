# phenopred/domain/genomic_profiling/indel_haploid_classifier.py
"""Domain-layer genomic profiler reporting configured indel-token
occurrence counts and haploid/diploid genotype-length classification on
configured sex/mitochondrial chromosome labels, for a single file using
a single combined genotype column (FR-12).

IndelHaploidClassifier is the sole component responsible for tallying
configured indel-token occurrences in a file's designated genotype
column and for classifying rows on configured sex/mitochondrial
chromosome labels by genotype-string length, for consumption as an
IndelHaploidProfile. Per Architecture v1 (Section 4/5/6/10), ADR-1
through ADR-7, and the frozen Genomic Profiling Architecture Contract:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file. It
  contains no parsing logic and no orchestration logic.
- It consumes only a plain, already-in-memory collection of DataRow
  instances and a plain, already-resolved GenotypeChromosomeColumnIndices
  composite, delivered via the GenomicProfiler interface's context
  parameter. It never accepts, imports, or depends on HeaderInfo,
  HeaderResolver, RawFileLoader, EncodingDetector, DelimiterDetector,
  RawLineSplitter, RowParser (module or class), any QualityCheck, any
  sibling GenomicProfiler, or ReportBuilder.
- Per ADR-2, GenotypeChromosomeColumnIndices exists because the
  GenomicProfiler interface exposes a single context parameter, and this
  classifier needs two distinct pieces of column-identity context
  (designated_column_indices and chromosome_column_index) -- bundling
  them there keeps this classifier from having to accept the entire
  ColumnLayout (which would expose fields, such as rsid_column_index, it
  has no business touching). This is not a role-transposition
  safeguard -- ChrPosColumnIndices exists for that distinct reason.
- IndelHaploidClassifier performs no column-name resolution, no header
  interpretation, and no biological interpretation of any observed
  value. `haploid_count`, `diploid_count`, and `indel_token_counts` are
  required descriptive classifications named directly by FR-12, not
  biological conclusions: this classifier represents required
  descriptive observations without performing biological interpretation
  (ADR-7). It never infers biological sex, ancestry, health conditions,
  phenotype, disease, or any other medical meaning; it never maps,
  translates, or reconciles chromosome codes across files (RISK-1,
  RISK-2); and it never asserts biological meaning for any observed
  token beyond counting its presence, mirroring FR-9's own "without
  judging the cause" framing.
- No fixed indel-token vocabulary or chromosome-label vocabulary is
  assumed anywhere in this module: both are supplied exclusively by the
  caller at construction time (ADR-2, NFR-5). This module's own logic
  contains no literal occurrence of any specific token or label string
  -- every comparison is made against the constructor-injected
  `indel_tokens` and `sex_mitochondrial_labels` sequences only. The
  implementation should remain robust against unexpected structural
  variations and should not encode assumptions that are only valid for
  the two evidence datasets (ADR-6). This module never supplies a
  default value for either injected sequence, and never constructs or
  wires a default configuration itself -- that remains the exclusive,
  later responsibility of the composition root, out of scope here.
- Applicability contract: FR-12 applies only to files using a single
  combined genotype column. `applicable` is True if and only if
  `len(column_indices.designated_column_indices) == 1`; False for every
  other cardinality (0, 2, or more), in which case every other returned
  field is reported at its zero/empty value -- a legitimate, non-error
  descriptive outcome, never an exception, mirroring
  MissingValueScanner's own precedent that an unsupported input shape is
  reported as a zero-count result, not raised.
- indel_token_counts is ordered by the constructor-injected
  `indel_tokens` order -- never by frequency, alphabetical order, or
  dictionary/set insertion behavior (ADR-4).
- Bounds handling differs by observation, per the frozen implementation
  contract, mirroring two distinct existing precedents:
    - Indel-token counting requires only the single designated genotype
      column index to be in bounds for a given row (mirroring
      MissingValueScanner's per-index bounds pattern). If that index is
      out of bounds for a row, that row contributes no indel-token
      observation; no exception is raised.
    - Haploid/diploid classification requires BOTH the chromosome column
      index and the designated genotype column index to be jointly in
      bounds for a given row (mirroring DuplicateChrPosCheck's joint
      dual-index bounds pattern) -- a row missing either index
      contributes no haploid/diploid observation at all, never a partial
      classification from whichever single index happened to be in
      bounds; no exception is raised.
- The entire data_rows collection is scanned in full -- never a sample
  -- per Architecture v1 Section 17's requirement that full-file SRS
  requirements (which FR-12 is) must not be handled by a sampling
  approach.
- This component never raises: Architecture v1 Section 13.2 requires
  data-quality/descriptive-profiling conditions to always be
  represented as value-object data, never exceptions.
- It never mutates any DataRow instance or the supplied collection
  (DataRow is itself immutable -- frozen=True, slots=True -- so
  mutation is not just a convention but a language-enforced
  impossibility).
- It does not perform row-quality validation of any kind (malformed-row
  detection, duplicate detection, missing-value scanning); those remain
  the exclusive responsibility of the separate FR-5..FR-9 QualityCheck
  implementations. It does not resolve designated_column_indices or
  chromosome_column_index itself -- that remains ColumnIdentityResolver's
  and ProfileFileUseCase's responsibility; this classifier only consumes
  an already-resolved GenotypeChromosomeColumnIndices.

Determinism note (NFR-3): a single forward pass over data_rows tallies
indel-token occurrence counts (keyed by the constructor-injected token
sequence, never by a dict/set derived from row content) and
haploid/diploid counts (two plain integer accumulators). The final
indel_token_counts tuple is built by iterating `self._indel_tokens` in
its own constructor-injected order -- never by dict/set iteration or
insertion order, and never by frequency. This holds regardless of
data_rows' own traversal order and regardless of any dict iteration
order, including across different Python versions or hash-randomization
seeds.
"""

from __future__ import annotations

from collections.abc import Sequence

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import (
    GenotypeChromosomeColumnIndices,
    IndelHaploidProfile,
)

_PROFILER_NAME = "indel_haploid_classifier"


class IndelHaploidClassifier:
    """Reports configured indel-token occurrence counts and
    haploid/diploid genotype-length classification on configured
    sex/mitochondrial chromosome labels, for a file using a single
    combined genotype column (FR-12).

    Unlike ChromosomeLabelProfiler and GenotypeLayoutClassifier, this
    profiler carries constructor-injected configuration, mirroring
    ColumnIdentityResolver's established injected-keyword pattern: FR-12
    names specific tokens and labels that ADR-6/NFR-5 forbid hard-coding
    directly in domain code, so the exact token and label vocabularies
    are supplied by the caller at construction time, never assumed
    internally. Beyond that injected configuration, this class holds no
    other mutable state. Given the same inputs, `profile()` always
    returns a field-for-field identical IndelHaploidProfile (NFR-3).
    """

    def __init__(
        self,
        indel_tokens: Sequence[str],
        sex_mitochondrial_labels: Sequence[str],
    ) -> None:
        """Initialize the classifier with injected token and label
        vocabularies.

        Args:
            indel_tokens: The exact token string(s) to count occurrences
                of within the designated genotype column (e.g. the
                caller may supply values equivalent to those documented
                in FR-12). Mandatory, no internal default -- this
                classifier never supplies or falls back to a default
                vocabulary of its own. Supplied by the caller (typically
                via the composition root, per Architecture v1 Section
                11); this classifier never reads configuration directly.
            sex_mitochondrial_labels: The exact chromosome label
                string(s) on which haploid/diploid genotype-length
                classification is performed. Mandatory, no internal
                default, for the same reason as `indel_tokens`.
        """
        self._indel_tokens = tuple(indel_tokens)
        self._sex_mitochondrial_labels = tuple(sex_mitochondrial_labels)

    def profile(
        self,
        data_rows: Sequence[DataRow],
        column_indices: GenotypeChromosomeColumnIndices,
    ) -> IndelHaploidProfile:
        """Determine applicability, then tally indel-token occurrences
        and haploid/diploid genotype-length classifications, reporting
        the result as one IndelHaploidProfile.

        Args:
            data_rows: A sequence of already-in-memory, already-parsed
                DataRow instances (e.g. the output of RowParser.parse()).
                No file I/O is performed; `data_rows` must already be in
                memory. The full, unsampled collection is always
                scanned when `applicable` is True. Rows may legitimately
                vary in field-count width (e.g. malformed rows); see the
                out-of-bounds handling below.
            column_indices: A single, already-resolved
                GenotypeChromosomeColumnIndices carrying this file's
                `designated_column_indices` and `chromosome_column_index`.
                This method performs no resolution or validation of
                either field beyond using `designated_column_indices`'
                length to determine applicability and using both fields
                to index into `row.fields`.

        Returns:
            An IndelHaploidProfile. `applicable` is True if and only if
            `len(column_indices.designated_column_indices) == 1`; False
            for every other cardinality, in which case
            `indel_token_counts == ()`, `haploid_count == 0`, and
            `diploid_count == 0`. When applicable,
            `indel_token_counts` contains one (token, count) pair per
            constructor-injected indel token, in constructor-injected
            order, counting exact-match occurrences of that token in
            the single designated column across rows where that column
            index is in bounds. `haploid_count` and `diploid_count`
            count rows where both the chromosome column index and the
            designated column index are jointly in bounds, the
            chromosome value exactly matches a configured
            sex/mitochondrial label, and the genotype value's string
            length is 1 or 2, respectively; genotype values of any
            other length, and rows failing either bounds or label
            conditions, contribute to neither count.

        Raises:
            This method introduces no exception handling of its own and
            depends on no exception hierarchy. A non-applicable
            designated-column cardinality, and any out-of-bounds column
            index for a particular row, are always reported as
            IndelHaploidProfile data, never raised as exceptions.
        """
        designated_column_indices = column_indices.designated_column_indices

        if len(designated_column_indices) != 1:
            return IndelHaploidProfile(
                profiler_name=_PROFILER_NAME,
                applicable=False,
                indel_token_counts=(),
                haploid_count=0,
                diploid_count=0,
            )

        genotype_column_index = designated_column_indices[0]
        chromosome_column_index = column_indices.chromosome_column_index

        indel_token_tally: dict[str, int] = {
            token: 0 for token in self._indel_tokens
        }
        haploid_count = 0
        diploid_count = 0

        for row in data_rows:
            row_field_count = len(row.fields)
            genotype_index_in_bounds = (
                0 <= genotype_column_index < row_field_count
            )

            # Indel-token counting: requires only the genotype column
            # index to be in bounds for this row (mirroring
            # MissingValueScanner's per-index bounds pattern, extended
            # with the explicit 0 <= lower-bound guard -- Python's
            # negative-indexing semantics would otherwise let a
            # negative index silently read the wrong field from the
            # end of the tuple, per DuplicateChrPosCheck's identical,
            # already-established rationale). No exception is raised
            # when out of bounds; the row simply contributes no
            # indel-token observation.
            if genotype_index_in_bounds:
                genotype_value = row.fields[genotype_column_index]
                if genotype_value in indel_token_tally:
                    indel_token_tally[genotype_value] += 1

            # Haploid/diploid classification: requires BOTH the
            # chromosome column index and the genotype column index to
            # be jointly in bounds for this row (mirroring
            # DuplicateChrPosCheck's joint dual-index bounds pattern,
            # including its 0 <= lower-bound guard). A row missing
            # either index contributes no observation at all -- never
            # a partial classification. No exception is raised.
            chromosome_index_in_bounds = (
                0 <= chromosome_column_index < row_field_count
            )
            if genotype_index_in_bounds and chromosome_index_in_bounds:
                chromosome_value = row.fields[chromosome_column_index]
                if chromosome_value in self._sex_mitochondrial_labels:
                    genotype_value = row.fields[genotype_column_index]
                    genotype_length = len(genotype_value)
                    if genotype_length == 1:
                        haploid_count += 1
                    elif genotype_length == 2:
                        diploid_count += 1
                    # Any other length is ignored: neither haploid nor
                    # diploid, per the frozen classification contract.

        return IndelHaploidProfile(
            profiler_name=_PROFILER_NAME,
            applicable=True,
            indel_token_counts=tuple(
                (token, indel_token_tally[token])
                for token in self._indel_tokens
            ),
            haploid_count=haploid_count,
            diploid_count=diploid_count,
        )