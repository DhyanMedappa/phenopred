# phenopred_phase2/traits/domain/models/actn3_model.py
"""ACTN3 (alpha-actinin-3, R577X) trait model -- the third concrete
TraitModel implementation, and the first to use a three-genotype-
category interpretation rather than a dominant single-allele-presence
rule (contrast with LactasePersistenceModel and EarwaxTypeModel).

Per the Phase 2 Architecture Blueprint, Section 8.3 ("ACTN3 -- Final
Decision"): a single SNP (rs1815739), confirmed present, genotype CC in
both real files, matching the standard C/T convention directly (no
strand ambiguity). This is the well-known R577X polymorphism, in which
the three genotypes are NOT interpreted as "phenotype present vs.
absent" but as three biologically distinct categories:

- CC (RR): both copies produce functional alpha-actinin-3 --
  "power"-associated (Section 8.3: "CC = RR genotype
  ('power'-associated, alpha-actinin-3 present)").
- CT (RX): one functional copy, one null (X) copy -- an intermediate,
  mixed-association genotype.
- TT (XX): both copies are the premature-stop-codon (X) variant, no
  functional alpha-actinin-3 -- "endurance"-associated.

Explicit genotype mapping is used deliberately, matching each observed
genotype directly against reference/reference, reference/alternate, and
alternate/alternate built from SNP_REGISTRY's own reference_allele and
alternate_allele -- never a "does the associated allele appear at all"
dominant test, since ACTN3's biology assigns the heterozygote its own,
distinct category rather than grouping it with either homozygote.

Per Section 8.3's explicit instruction, this trait's card "must retain
the caveat that genotype is one minor factor among many in athletic
performance, not a determinant." That caveat is recorded in this
trait's TraitDefinition.evidence_refs (see trait_registry.py) -- it is
trait-level context, not a per-prediction fact, so it does not appear as
a TraitPrediction field, consistent with TraitPrediction's frozen scope
(facts only, no reporting prose). Confidence is set to
ConfidenceLevel.MODERATE, not HIGH: unlike lactase persistence and
earwax type (near-deterministic, monogenic phenotypes), ACTN3's own
described phenotype association is explicitly partial and contributory,
not determinative, per Section 8.3.

This class satisfies the frozen TraitModel Protocol structurally (see
"Trait Contract Layer -- Frozen Architecture Specification v1"):

- It accepts only a Mapping[str, GenotypeCall] -- never a GenotypeIndex,
  DataRow, or any file-level object. It performs no file I/O.
- It consults SNP_REGISTRY directly, by static import, for rs1815739's
  biological metadata -- never injected, per the frozen contract's
  Option-A decision.
- It never raises for any external, per-file data condition (the
  required rsid missing, a NO_CALL, any non-SNP classification, or an
  unrecognized two-allele combination for this SNP). Each such
  condition is represented as
  TraitPrediction(status=PredictionStatus.INSUFFICIENT_DATA).
- It performs no orchestration (no registry iteration, no knowledge of
  any other trait) and no reporting/presentation logic (no prose, no
  UI fields) -- it returns only the objective facts a TraitPrediction
  carries.

This is a plain, independent class -- not a shared base class or mixin,
and it shares no implementation with LactasePersistenceModel or
EarwaxTypeModel despite structural similarity in the sufficiency-check
step. Future trait models with different biology (e.g. multi-SNP
diplotype scoring for bitter taste, multi-SNP regression for eye
colour) are expected to be separate, independent classes of their own.
"""

from __future__ import annotations

from collections.abc import Mapping

from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCall,
    GenotypeCallKind,
    PredictionStatus,
    TraitPrediction,
)
from phenopred_phase2.traits.domain.snp_registry import SNP_REGISTRY

_TRAIT_ID = "actn3"
_REQUIRED_RSID = "rs1815739"

_PHENOTYPE_RR = "ACTN3 RR (power-associated, alpha-actinin-3 present)"
_PHENOTYPE_RX = "ACTN3 RX (mixed power/endurance, one functional copy)"
_PHENOTYPE_XX = "ACTN3 XX (endurance-associated, alpha-actinin-3 deficient)"


class ACTN3Model:
    """The concrete TraitModel for ACTN3 (R577X).

    Permanently bound to rs1815739, per the frozen TraitModel contract's
    convention that a model does not receive its required rsid(s) as an
    argument -- they are this model's own, hardcoded knowledge.
    """

    def predict(self, genotype_calls: Mapping[str, GenotypeCall]) -> TraitPrediction:
        """Produce one TraitPrediction for ACTN3 from this file's
        observed rs1815739 call, if any.

        Args:
            genotype_calls: This file's already-resolved GenotypeCall(s),
                keyed by RSID. Only the rs1815739 entry (if present) is
                consulted.

        Returns:
            A TraitPrediction with status=PREDICTED and one of the three
            genotype-category phenotype labels when rs1815739 was
            observed as a SNP call matching a recognized genotype for
            this SNP; otherwise status=INSUFFICIENT_DATA, with any
            partially-observed GenotypeCall still surfaced in
            observed_genotypes for transparency.
        """
        call = genotype_calls.get(_REQUIRED_RSID)

        if call is None or call.kind != GenotypeCallKind.SNP:
            return TraitPrediction(
                trait_id=_TRAIT_ID,
                status=PredictionStatus.INSUFFICIENT_DATA,
                predicted_phenotype=None,
                confidence=None,
                observed_genotypes=(
                    {_REQUIRED_RSID: call} if call is not None else {}
                ),
                supporting_snps={},
            )

        # rs1815739 is a permanently-known, frozen SNP_REGISTRY entry
        # for this model -- its absence would be a static-data authoring
        # defect (model/registry authored out of sync), not a per-file
        # runtime condition, so it is deliberately not guarded with an
        # INSUFFICIENT_DATA branch; a missing entry surfaces as a
        # KeyError, caught by tests, not represented as prediction data.
        snp_record = SNP_REGISTRY[_REQUIRED_RSID]

        reference_allele = snp_record.reference_allele
        alternate_allele = snp_record.alternate_allele

        homozygous_reference_genotype = "".join(
            sorted(reference_allele + reference_allele)
        )
        heterozygous_genotype = "".join(sorted(reference_allele + alternate_allele))
        homozygous_alternate_genotype = "".join(
            sorted(alternate_allele + alternate_allele)
        )

        if call.alleles == homozygous_reference_genotype:
            predicted_phenotype = _PHENOTYPE_RR
        elif call.alleles == heterozygous_genotype:
            predicted_phenotype = _PHENOTYPE_RX
        elif call.alleles == homozygous_alternate_genotype:
            predicted_phenotype = _PHENOTYPE_XX
        else:
            # An observed SNP genotype that matches neither of the three
            # genotypes this SNP's own reference/alternate alleles
            # define (e.g. a data anomaly reporting alleles other than
            # C/T for this locus). External, per-file condition -- never
            # raised, never guessed at.
            return TraitPrediction(
                trait_id=_TRAIT_ID,
                status=PredictionStatus.INSUFFICIENT_DATA,
                predicted_phenotype=None,
                confidence=None,
                observed_genotypes={_REQUIRED_RSID: call},
                supporting_snps={},
            )

        return TraitPrediction(
            trait_id=_TRAIT_ID,
            status=PredictionStatus.PREDICTED,
            predicted_phenotype=predicted_phenotype,
            confidence=ConfidenceLevel.MODERATE,
            observed_genotypes={_REQUIRED_RSID: call},
            supporting_snps={_REQUIRED_RSID: snp_record},
        )
