# phenopred_phase2/traits/domain/genotype_index.py
"""Phase 2 domain component building a per-file RSID -> GenotypeCall
lookup from V1's already-resolved DataRow/ColumnLayout outputs.

Per the frozen "GenotypeIndex -- Final Design Specification"
(Implementation-Ready), GenotypeIndex is the sole integration adapter
between Architecture V1 (frozen, unmodified) and Phase 2's Trait Engine /
Comparison Engine:

- It depends only on `phenopred.domain.entities.DataRow` and
  `phenopred.domain.value_objects.ColumnLayout`, both read-only,
  already-resolved V1 outputs. It performs no file I/O, no re-parsing,
  and no column-identity resolution of its own -- `data_rows` and
  `column_layout` are consumed exactly as `ProfileFileUseCase.execute()`
  already produces them.
- Genotype/allele column layout classification is derived independently,
  directly from `len(column_layout.designated_column_indices)`, using
  the identical rule V1's own frozen ADR-5 contract defines for
  GenotypeLayoutClassifier -- "two_column_allele" iff exactly 2,
  "single_column_genotype" iff exactly 1, "undetermined" otherwise. This
  is a local application of an already-frozen, one-line classification
  rule to data GenotypeIndex already holds; it is not a dependency on
  GenotypeLayoutProfile, since that value is only ever produced by an
  optional genomic profiler that may not have been injected for a given
  run.
- Missing-value tokens, indel tokens, and sex/mitochondrial chromosome
  labels are not available anywhere in V1 as a reusable vocabulary (V1's
  own IndelHaploidClassifier requires the identical vocabulary as
  mandatory, no-default constructor configuration, owned by V1's own
  composition root). GenotypeIndex therefore requires the same
  vocabulary as its own mandatory, no-default constructor configuration,
  supplied by Phase 2's composition root.
- Haploid classification mirrors IndelHaploidClassifier's own frozen
  joint-condition contract exactly: a single-character designated-column
  value is only ever classified HAPLOID when the same row's chromosome
  value matches a configured sex/mitochondrial label; otherwise it is
  UNRECOGNIZED.
- Every out-of-bounds field-position index is handled per V1's own,
  pervasive "skip this row's observation, never raise" convention
  (mirrored identically across ChromosomeLabelProfiler,
  GenotypeLayoutClassifier, MissingValueScanner, and
  IndelHaploidClassifier).
- Duplicate RSIDs (never prevented by V1 -- DuplicateRsidCheck reports
  them, never removes them) are resolved deterministically: first
  occurrence, by ascending DataRow.line_index, wins, since `data_rows`
  is already in original file order. No exception is raised.
- This component never raises for any data-quality or classification
  condition -- every unrecognized or malformed input state is
  represented as GenotypeCallKind.UNRECOGNIZED data, mirroring V1's
  AD-6 discipline.
- GenotypeIndex is immutable after construction: it exposes no mutation
  method, and its internal lookup is built exactly once, in a single
  forward pass over `data_rows`.

See "GenotypeIndex -- Final Design Specification" for the complete,
authoritative contract this module implements. No V1 file is read,
imported beyond its public entities/value objects, or modified by this
module.
"""

from __future__ import annotations

from collections.abc import Sequence

from phenopred.domain.entities import DataRow
from phenopred.domain.value_objects import ColumnLayout
from phenopred_phase2.traits.domain.entities import GenotypeCall, GenotypeCallKind

_LAYOUT_TWO_COLUMN_ALLELE = "two_column_allele"
_LAYOUT_SINGLE_COLUMN_GENOTYPE = "single_column_genotype"
_LAYOUT_UNDETERMINED = "undetermined"

_UNRECOGNIZED_NO_VALUE = GenotypeCall(
    kind=GenotypeCallKind.UNRECOGNIZED,
    alleles=None,
    allele=None,
    raw_value=None,
)


class GenotypeIndex:
    """Per-file RSID -> GenotypeCall lookup, built once from V1's
    already-resolved `data_rows` and `column_layout`.

    Immutable after construction: exposes no mutation method. Given the
    same inputs, the resulting index is always field-for-field
    identical (mirroring V1's own NFR-3 determinism discipline).
    """

    def __init__(
        self,
        data_rows: Sequence[DataRow],
        column_layout: ColumnLayout,
        missing_value_tokens: Sequence[str],
        indel_tokens: Sequence[str],
        sex_mitochondrial_labels: Sequence[str],
    ) -> None:
        """Build the full RSID -> GenotypeCall index in a single forward
        pass over `data_rows`.

        Args:
            data_rows: This file's already-in-memory, already-parsed
                DataRow collection (e.g. `result["data_rows"]` from
                `ProfileFileUseCase.execute()`). No file I/O is
                performed here; `data_rows` must already be in memory.
            column_layout: This file's already-resolved ColumnLayout
                (e.g. `result["column_layout"]`). Consumed only as
                opaque field-position indices -- this class performs no
                column-name resolution or vendor-specific interpretation
                of its own.
            missing_value_tokens: The literal value(s) treated as a
                no-call/missing genotype for this run. Mandatory, no
                internal default -- supplied by Phase 2's own
                composition root, mirroring IndelHaploidClassifier's
                identical, no-default vocabulary-injection pattern in
                V1.
            indel_tokens: The literal value(s) treated as an indel
                genotype for this run. Mandatory, no internal default,
                for the same reason as `missing_value_tokens`.
            sex_mitochondrial_labels: The exact chromosome label
                string(s) on which a single-character designated-column
                value is classified as a haploid call. Mandatory, no
                internal default, for the same reason as
                `missing_value_tokens`.
        """
        self._missing_value_tokens = tuple(missing_value_tokens)
        self._indel_tokens = tuple(indel_tokens)
        self._sex_mitochondrial_labels = tuple(sex_mitochondrial_labels)

        self._layout_kind = self._classify_layout_kind(
            column_layout.designated_column_indices
        )
        self._calls_by_rsid = self._build_index(data_rows, column_layout)

    def get(self, rsid: str) -> GenotypeCall | None:
        """Return this file's GenotypeCall for `rsid`.

        Returns:
            The GenotypeCall observed for `rsid` in this file, or None
            if `rsid` was not observed in any row of this file.
        """
        return self._calls_by_rsid.get(rsid)

    def __contains__(self, rsid: str) -> bool:
        return rsid in self._calls_by_rsid

    def __len__(self) -> int:
        return len(self._calls_by_rsid)

    # -----------------------------------------------------------------
    # Construction
    # -----------------------------------------------------------------

    def _build_index(
        self,
        data_rows: Sequence[DataRow],
        column_layout: ColumnLayout,
    ) -> dict[str, GenotypeCall]:
        """Build the RSID -> GenotypeCall mapping in a single forward
        pass over `data_rows`, in original row order.

        A row whose rsid_column_index is out of bounds contributes no
        entry. A row whose RSID was already observed by an earlier row
        (lower line_index) is skipped -- first occurrence wins,
        deterministically, since `data_rows` is already in original
        file order. No exception is ever raised.
        """
        calls_by_rsid: dict[str, GenotypeCall] = {}
        rsid_column_index = column_layout.rsid_column_index

        for row in data_rows:
            row_field_count = len(row.fields)
            if not (0 <= rsid_column_index < row_field_count):
                # Out-of-bounds rsid_column_index for this row: no
                # entry contributed, no exception raised.
                continue

            rsid = row.fields[rsid_column_index]
            if rsid in calls_by_rsid:
                # Duplicate RSID: first occurrence (lower line_index)
                # already won; this later row is skipped.
                continue

            calls_by_rsid[rsid] = self._classify_row(row, column_layout)

        return calls_by_rsid

    # -----------------------------------------------------------------
    # Layout classification
    # -----------------------------------------------------------------

    def _classify_layout_kind(
        self, designated_column_indices: Sequence[int]
    ) -> str:
        """Classify this file's genotype/allele layout kind solely from
        the count of designated columns, mirroring V1's frozen ADR-5
        classification contract (GenotypeLayoutClassifier) exactly. Row
        values are never inspected here.
        """
        designated_column_count = len(designated_column_indices)
        if designated_column_count == 2:
            return _LAYOUT_TWO_COLUMN_ALLELE
        if designated_column_count == 1:
            return _LAYOUT_SINGLE_COLUMN_GENOTYPE
        return _LAYOUT_UNDETERMINED

    # -----------------------------------------------------------------
    # Row classification
    # -----------------------------------------------------------------

    def _classify_row(
        self, row: DataRow, column_layout: ColumnLayout
    ) -> GenotypeCall:
        """Classify a single row's designated-column value(s) into one
        GenotypeCall, per the layout kind resolved at construction time.
        """
        if self._layout_kind == _LAYOUT_SINGLE_COLUMN_GENOTYPE:
            return self._classify_single_column(row, column_layout)
        if self._layout_kind == _LAYOUT_TWO_COLUMN_ALLELE:
            return self._classify_two_column(row, column_layout)
        return _UNRECOGNIZED_NO_VALUE

    def _classify_single_column(
        self, row: DataRow, column_layout: ColumnLayout
    ) -> GenotypeCall:
        """Classify one row under a single-column-genotype layout,
        per the frozen Final Design Specification, Section 8.
        """
        row_field_count = len(row.fields)
        designated_index = column_layout.designated_column_indices[0]

        if not (0 <= designated_index < row_field_count):
            return _UNRECOGNIZED_NO_VALUE

        raw = row.fields[designated_index]

        if raw in self._missing_value_tokens:
            return GenotypeCall(
                kind=GenotypeCallKind.NO_CALL,
                alleles=None,
                allele=None,
                raw_value=raw,
            )
        if raw in self._indel_tokens:
            return GenotypeCall(
                kind=GenotypeCallKind.INDEL,
                alleles=None,
                allele=None,
                raw_value=raw,
            )

        if len(raw) == 1:
            chromosome_index = column_layout.chromosome_column_index
            if (
                0 <= chromosome_index < row_field_count
                and row.fields[chromosome_index]
                in self._sex_mitochondrial_labels
            ):
                return GenotypeCall(
                    kind=GenotypeCallKind.HAPLOID,
                    alleles=None,
                    allele=raw,
                    raw_value=raw,
                )
            return GenotypeCall(
                kind=GenotypeCallKind.UNRECOGNIZED,
                alleles=None,
                allele=None,
                raw_value=raw,
            )

        if len(raw) == 2:
            return GenotypeCall(
                kind=GenotypeCallKind.SNP,
                alleles="".join(sorted(raw)),
                allele=None,
                raw_value=raw,
            )

        return GenotypeCall(
            kind=GenotypeCallKind.UNRECOGNIZED,
            alleles=None,
            allele=None,
            raw_value=raw,
        )

    def _classify_two_column(
        self, row: DataRow, column_layout: ColumnLayout
    ) -> GenotypeCall:
        """Classify one row under a two-column-allele layout, per the
        frozen Final Design Specification, Section 8.
        """
        row_field_count = len(row.fields)
        index_a, index_b = column_layout.designated_column_indices

        if not (
            0 <= index_a < row_field_count and 0 <= index_b < row_field_count
        ):
            return _UNRECOGNIZED_NO_VALUE

        value_a = row.fields[index_a]
        value_b = row.fields[index_b]
        raw_value = f"{value_a}/{value_b}"

        if (
            value_a in self._missing_value_tokens
            or value_b in self._missing_value_tokens
        ):
            return GenotypeCall(
                kind=GenotypeCallKind.NO_CALL,
                alleles=None,
                allele=None,
                raw_value=raw_value,
            )
        if value_a in self._indel_tokens or value_b in self._indel_tokens:
            return GenotypeCall(
                kind=GenotypeCallKind.INDEL,
                alleles=None,
                allele=None,
                raw_value=raw_value,
            )
        if len(value_a) == 1 and len(value_b) == 1:
            return GenotypeCall(
                kind=GenotypeCallKind.SNP,
                alleles="".join(sorted(value_a + value_b)),
                allele=None,
                raw_value=raw_value,
            )

        return GenotypeCall(
            kind=GenotypeCallKind.UNRECOGNIZED,
            alleles=None,
            allele=None,
            raw_value=raw_value,
        )
