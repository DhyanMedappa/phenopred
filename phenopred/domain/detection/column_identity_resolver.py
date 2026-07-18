# phenopred/domain/detection/column_identity_resolver.py
"""Domain-layer detector resolving a file's column-role identities into a
ColumnLayout, closing the Column Identity Resolution gap named by
Architecture v1 Section 4/10 (ColumnLayout referenced but not previously
implemented) and required as context by MissingValueScanner (FR-6),
DuplicateRsidCheck (FR-8), and DuplicateChrPosCheck (FR-9).

ColumnIdentityResolver is the sole component responsible for resolving
which field-position indices correspond to the RSID, chromosome, position,
and designated genotype/allele column roles for a file. Per the approved
Column Identity Resolution contract (Domain Detection layer) and mirroring
the locked precedent already established by HeaderResolver, DelimiterDetector,
and EncodingDetector:

- This module lives in the domain layer and performs no file/network I/O
  of any kind. It never opens, reads, or re-reads a source file.
- It consumes only an already-in-memory HeaderInfo (e.g. the output of
  HeaderResolver.detect()); it never accepts, imports, or depends on
  RawFileContent, RawFileLoader, CommentBlock, RawLineSplitter,
  DelimiterDetector, RowParser, DataRow, or any QualityCheck or
  GenomicProfiler implementation. It has no awareness of parsed rows,
  delimiters, or comments -- only of a file's already-resolved column
  names.
- It performs no biological interpretation of any column's content --
  only field-position identity resolution by column name, mirroring
  HeaderResolver's and DuplicateChrPosCheck's identical "reporting, not
  interpretation" discipline.
- Per NFR-5 ("Neutrality across input layout") and AD-5 ("No fixed
  schema ... anywhere in domain code"), this resolver hard-codes no
  column-name literals of its own. Every keyword it matches against
  (the RSID keyword, the chromosome keyword, the position keyword, and
  the designated-column keywords) is supplied by the caller at
  construction time -- mirroring HeaderResolver's identical
  constructor-injected `header_keyword` pattern and DelimiterDetector's
  identical constructor-injected `sample_size` pattern. This resolver
  never reads configuration directly.
- Matching is exact-token equality only against HeaderInfo.resolved_columns
  -- no substring matching, trimming, whitespace normalization, or
  case-folding -- mirroring HeaderResolver's identical exact-token-equality
  discipline for its own base-case header-keyword matching.
- The RSID, chromosome, and position column roles are each mandatory,
  single-valued identities: FR-8 and FR-9 cannot be satisfied without
  exactly one resolved index for each. If HeaderInfo.resolved_columns is
  None (no header resolvable), or if a configured keyword is not found
  among the resolved column names, this resolver raises
  ColumnIdentityNotResolvedError rather than guessing an index -- a real,
  reachable failure mode for any file whose header does not document
  these roles under the configured keywords.
- Designated genotype/allele columns are not mandatory in the same sense:
  MissingValueScanner's own, already-approved contract already treats an
  empty `designated_column_indices` as a legitimate, non-error input
  (its own docstring: "If ... designated_column_indices is empty ... the
  returned Finding has count == 0"). Consistent with that already-locked
  downstream contract, this resolver returns an empty tuple when none of
  the configured designated-column keywords are found, rather than
  raising -- it does not invent a stricter requirement than the consumer
  it serves already defines.
- This detector's underlying "no delimiter"-style failure mode (a
  required column role absent from the resolved header) is a real,
  reachable condition, not named by any existing PhenoPredIngestionError
  subclass (phenopred/domain/errors.py), which is scoped entirely to
  whole-file ingestion failures (not found, unreadable, empty, read
  error) -- none of which describe "a required column role could not be
  identified." Per the identical, already-approved Stage 2
  exception-ownership resolution used by DelimiterDetector, this
  resolver raises a narrow, resolver-local exception
  (ColumnIdentityNotResolvedError, defined in this module) on that
  condition. It never raises, imports, or depends on
  PhenoPredIngestionError or any of its subclasses. Translating this
  resolver-local signal into a typed PhenoPredIngestionError -- and
  attaching file-path context, which this resolver never has -- remains
  the exclusive responsibility of ProfileFileUseCase, mirroring
  DelimiterDetector's identical, already-approved precedent exactly.
- It never performs comment/data separation, delimiter detection, header
  form resolution, row parsing, quality validation, or genomic profiling
  -- those are separate, already-implemented responsibilities owned by
  separate modules.
"""

from __future__ import annotations

from collections.abc import Sequence

from phenopred.domain.value_objects import ColumnLayout, HeaderInfo


class ColumnIdentityNotResolvedError(Exception):
    """Raised when a mandatory column role (RSID, chromosome, or
    position) cannot be resolved from a file's HeaderInfo.

    This is a resolver-local signal, not a member of the
    PhenoPredIngestionError hierarchy (phenopred/domain/errors.py).
    ColumnIdentityResolver never raises, imports, or depends on that
    hierarchy, mirroring DelimiterDetector's locked precedent of zero
    dependency on ingestion-error vocabulary. Translating this into a
    typed PhenoPredIngestionError -- including attaching the file-path
    context this resolver never has -- is the exclusive responsibility
    of ProfileFileUseCase, per the approved exception-ownership
    resolution already established for DelimiterNotDetectedError.
    """


class ColumnIdentityResolver:
    """Resolves a file's column-role identities into a ColumnLayout.

    Stateless with respect to any single `detect()` call's input: the
    only state held is the injected keyword configuration, set once at
    construction and never reassigned. Given the same HeaderInfo,
    `detect()` always returns a field-for-field identical ColumnLayout
    (NFR-3), or always raises the same exception.
    """

    def __init__(
        self,
        rsid_keyword: str,
        chromosome_keyword: str,
        position_keyword: str,
        designated_column_keywords: Sequence[str],
    ) -> None:
        """Initialize the resolver with injected column-role keywords.

        Args:
            rsid_keyword: The exact column name identifying the RSID
                column (e.g. "rsid"). Mandatory, no internal default,
                mirroring HeaderResolver's identical constructor
                pattern. Supplied by the caller (typically via
                ConfigProvider through the composition root, per
                Architecture v1 Section 11); this resolver never reads
                configuration directly.
            chromosome_keyword: The exact column name identifying the
                chromosome column (e.g. "chromosome").
            position_keyword: The exact column name identifying the
                position column (e.g. "position").
            designated_column_keywords: The exact column name(s)
                identifying this file's designated genotype/allele
                column(s) (e.g. ("allele1", "allele2") for a
                two-column-allele layout, or ("genotype",) for a
                single-combined-genotype layout). Not assumed to be a
                fixed set across files, consistent with NFR-5 -- the
                caller supplies whichever keywords apply to the file
                layout(s) it is configured for.
        """
        self._rsid_keyword = rsid_keyword
        self._chromosome_keyword = chromosome_keyword
        self._position_keyword = position_keyword
        self._designated_column_keywords = tuple(designated_column_keywords)

    def detect(self, header_info: HeaderInfo) -> ColumnLayout:
        """Resolve column-role identities from `header_info`.

        Args:
            header_info: The already-resolved HeaderInfo for the file
                (e.g. the output of HeaderResolver.detect()), consumed
                only via its `.resolved_columns` field. No file I/O is
                performed; `header_info` must already be in memory.

        Returns:
            A ColumnLayout whose `rsid_column_index`,
            `chromosome_column_index`, and `position_column_index` are
            each the exact field-position index of the corresponding
            configured keyword within `header_info.resolved_columns`;
            and whose `designated_column_indices` is the ascending-order
            tuple of field-position indices of every configured
            designated-column keyword found within
            `header_info.resolved_columns` (empty if none are found).

        Raises:
            ColumnIdentityNotResolvedError: If
                `header_info.resolved_columns` is None, or if the
                configured `rsid_keyword`, `chromosome_keyword`, or
                `position_keyword` is not found among the resolved
                column names. This method never guesses a role's index;
                an unresolvable mandatory role is always reported as
                this exception, never as a partially-populated
                ColumnLayout.
        """
        resolved_columns = header_info.resolved_columns

        if resolved_columns is None:
            raise ColumnIdentityNotResolvedError(
                "Cannot resolve column identities: no header column "
                "names were resolved for this file."
            )

        return ColumnLayout(
            rsid_column_index=self._require_index(
                resolved_columns, self._rsid_keyword
            ),
            chromosome_column_index=self._require_index(
                resolved_columns, self._chromosome_keyword
            ),
            position_column_index=self._require_index(
                resolved_columns, self._position_keyword
            ),
            designated_column_indices=self._resolve_designated_indices(
                resolved_columns
            ),
        )

    def _require_index(
        self, resolved_columns: tuple[str, ...], keyword: str
    ) -> int:
        """Return the exact field-position index of `keyword` within
        `resolved_columns`, by exact-token equality only.

        Raises:
            ColumnIdentityNotResolvedError: If `keyword` is not present
                in `resolved_columns`.
        """
        if keyword not in resolved_columns:
            raise ColumnIdentityNotResolvedError(
                f"Required column '{keyword}' was not found among this "
                f"file's resolved column names: {resolved_columns}."
            )
        return resolved_columns.index(keyword)

    def _resolve_designated_indices(
        self, resolved_columns: tuple[str, ...]
    ) -> tuple[int, ...]:
        """Return the ascending-order field-position indices of every
        configured designated-column keyword found in `resolved_columns`.

        Consistent with MissingValueScanner's own already-approved
        contract, an empty result is a legitimate, non-error outcome --
        this method never raises for a designated-column keyword that is
        absent.
        """
        return tuple(
            index
            for index, name in enumerate(resolved_columns)
            if name in self._designated_column_keywords
        )
