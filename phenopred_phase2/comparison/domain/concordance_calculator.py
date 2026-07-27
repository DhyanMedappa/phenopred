# phenopred_phase2/comparison/domain/concordance_calculator.py
"""Genome-wide, per-RSID genotype concordance calculator.

Per the approved Comparison Engine Final Design Specification and the
subsequent scientific correctness review, this module owns exactly one
responsibility: given two files' already-built GenotypeIndex instances,
enumerate every shared RSID and classify each pairing into exactly one
of the four Blueprint Section 10.4 categories, using the final,
corrected decision table below -- never inventing a fifth category,
never guessing at an ambiguous pairing.

Boundaries (frozen by the approved specification):

- Consumes only GenotypeIndex's existing public surface (.get(),
  .keys()) -- never DataRow, ColumnLayout, or any V1 file-level object.
  It performs no file parsing and understands no file format.
- Performs no genotype-string classification of its own -- every
  GenotypeCall it reads was already classified by GenotypeIndex; this
  module only compares two already-classified GenotypeCallKind values
  and, where directly comparable, their already-normalized allele
  content. It never re-derives a GenotypeCallKind from a raw string.
- Performs no biological interpretation -- it produces only the
  structural fact "these two calls match / mismatch / are structurally
  incomparable / are not comparable due to missing data," never a
  biological conclusion about the individual(s) involved.

Final, corrected decision table (17 combinations, all resolved,
precedence order top-to-bottom):

    1. Either side NO_CALL or UNRECOGNIZED -> NO_CALL.
       (An explicit no-call and an uninterpretable call are both
       "no usable comparison information," per the scientific
       correctness review's correction of the original proposal.)
    2. Neither side NO_CALL/UNRECOGNIZED, and either side INDEL, or
       the pair is {SNP, HAPLOID} -> STRUCTURAL_MISMATCH.
       (A known-different call shape, never directly comparable as a
       simple allele pair.)
    3. Both SNP, or both HAPLOID (the only remaining, directly
       comparable cases) -> compare content: same alleles/allele ->
       SNP_MATCH; different -> SNP_MISMATCH.

See the Final Design Specification and the scientific correctness
review for the complete, authoritative rationale and the full 17-row
table this module implements.
"""

from __future__ import annotations

from collections.abc import KeysView
from typing import Protocol

from phenopred_phase2.comparison.domain.entities import (
    ConcordanceCategory,
    ConcordanceResult,
)
from phenopred_phase2.traits.domain.entities import GenotypeCall, GenotypeCallKind

_DIRECTLY_COMPARABLE_ONLY = frozenset({GenotypeCallKind.SNP, GenotypeCallKind.HAPLOID})
_NON_COMPARABLE_KINDS = frozenset(
    {GenotypeCallKind.NO_CALL, GenotypeCallKind.UNRECOGNIZED}
)


class _ComparableGenotypeSource(Protocol):
    """The only capability concordance_calculator requires from a
    genotype source for one file: RSID-keyed lookup plus key
    enumeration.

    Mirrors TraitEngine's own `_GenotypeSource` Protocol pattern
    exactly -- a narrow, local structural description of the exact two
    methods this module calls (GenotypeIndex.get() and the newly
    approved GenotypeIndex.keys()), not a new abstraction layered over
    GenotypeIndex.
    """

    def get(self, rsid: str) -> GenotypeCall | None:
        ...

    def keys(self) -> KeysView[str]:
        ...


def calculate_concordance(
    genotype_index_a: _ComparableGenotypeSource,
    genotype_index_b: _ComparableGenotypeSource,
) -> ConcordanceResult:
    """Compute the genome-wide concordance result between two files.

    Args:
        genotype_index_a: File A's already-built GenotypeIndex (or
            anything exposing the same .get()/.keys() interface).
        genotype_index_b: File B's already-built GenotypeIndex,
            symmetric to genotype_index_a.

    Returns:
        A ConcordanceResult aggregating every shared RSID's
        classification into exactly one of the four Section 10.4
        categories, per the final, corrected decision table above.
        An RSID present in only one file contributes to neither file's
        total_shared_rsids and is not classified at all -- this
        function only ever compares RSIDs present in both files.
    """
    shared_rsids = set(genotype_index_a.keys()) & set(genotype_index_b.keys())

    shared_snp_count = 0
    conflicting_snp_count = 0
    missing_or_no_call_count = 0
    structural_mismatch_count = 0

    for rsid in shared_rsids:
        call_a = genotype_index_a.get(rsid)
        call_b = genotype_index_b.get(rsid)
        # Both calls are guaranteed non-None here: rsid was drawn from
        # the intersection of both indexes' own .keys().
        category = _classify_pair(call_a, call_b)

        if category is ConcordanceCategory.SNP_MATCH:
            shared_snp_count += 1
        elif category is ConcordanceCategory.SNP_MISMATCH:
            conflicting_snp_count += 1
        elif category is ConcordanceCategory.STRUCTURAL_MISMATCH:
            structural_mismatch_count += 1
        else:
            missing_or_no_call_count += 1

    total_shared_rsids = len(shared_rsids)
    agreement_percentage = (
        (shared_snp_count / total_shared_rsids) * 100.0
        if total_shared_rsids > 0
        else 0.0
    )

    return ConcordanceResult(
        total_shared_rsids=total_shared_rsids,
        shared_snp_count=shared_snp_count,
        conflicting_snp_count=conflicting_snp_count,
        missing_or_no_call_count=missing_or_no_call_count,
        structural_mismatch_count=structural_mismatch_count,
        agreement_percentage=agreement_percentage,
    )


def _classify_pair(
    call_a: GenotypeCall, call_b: GenotypeCall
) -> ConcordanceCategory:
    """Classify one shared RSID's two GenotypeCalls per the final,
    corrected 17-row decision table. Every GenotypeCallKind pairing is
    resolved; no combination falls through undefined.
    """
    kind_a = call_a.kind
    kind_b = call_b.kind

    # Tier 1: either side uninformative (explicit no-call or
    # uninterpretable) -- always dominates every other classification.
    if kind_a in _NON_COMPARABLE_KINDS or kind_b in _NON_COMPARABLE_KINDS:
        return ConcordanceCategory.NO_CALL

    # Tier 2: either side a known indel/structural call, or the pair is
    # a diploid/haploid (SNP/HAPLOID) shape mismatch -- never directly
    # comparable as a simple allele pair.
    if kind_a is GenotypeCallKind.INDEL or kind_b is GenotypeCallKind.INDEL:
        return ConcordanceCategory.STRUCTURAL_MISMATCH
    if {kind_a, kind_b} == _DIRECTLY_COMPARABLE_ONLY:
        # {SNP, HAPLOID} in either order.
        return ConcordanceCategory.STRUCTURAL_MISMATCH

    # Tier 3: the only remaining, directly comparable cases -- both SNP
    # or both HAPLOID -- compared on already-normalized allele content.
    if kind_a is GenotypeCallKind.SNP and kind_b is GenotypeCallKind.SNP:
        return (
            ConcordanceCategory.SNP_MATCH
            if call_a.alleles == call_b.alleles
            else ConcordanceCategory.SNP_MISMATCH
        )
    if kind_a is GenotypeCallKind.HAPLOID and kind_b is GenotypeCallKind.HAPLOID:
        return (
            ConcordanceCategory.SNP_MATCH
            if call_a.allele == call_b.allele
            else ConcordanceCategory.SNP_MISMATCH
        )

    # Unreachable: GenotypeCallKind has exactly five members, and every
    # pairing among them is resolved by one of the three tiers above.
    raise AssertionError(
        f"Unhandled GenotypeCallKind pairing: {kind_a!r} vs {kind_b!r}"
    )
