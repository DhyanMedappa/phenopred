# phenopred_phase2/traits/domain/models/earwax_type_model.py
"""Earwax type trait model -- the second concrete TraitModel
implementation, following the pattern established by
LactasePersistenceModel.

Per the Phase 2 Architecture Blueprint, Section 8.4 ("Earwax Type --
Final Decision"): a single SNP (rs17822931), modeled as an unchanged,
deterministic genotype table. Forward-strand genotype CC (both real
files) resolves, per Section 9.3's dbSNP/ClinVar-sourced strand
resolution, to GG under the Yoshiura et al. 2006 gene-strand convention
-- wet earwax, dominant homozygous. Earwax type is inherited in a
dominant fashion: one copy of the phenotype-associated allele
(SNP_REGISTRY's forward-strand "C") is sufficient for wet earwax; the
homozygous-alternate-allele genotype ("TT" forward-strand) is dry
earwax. This is "now a sourced, confirmed interpretation, not a
hypothesis" (Section 8.4), the same class of well-replicated, near-
single-gene trait association as lactase persistence, which this model
maps to ConfidenceLevel.HIGH.

This class satisfies the frozen TraitModel Protocol structurally (see
"Trait Contract Layer -- Frozen Architecture Specification v1"):

- It accepts only a Mapping[str, GenotypeCall] -- never a GenotypeIndex,
  DataRow, or any file-level object. It performs no file I/O.
- It consults SNP_REGISTRY directly, by static import, for rs17822931's
  biological metadata -- never injected, per the frozen contract's
  Option-A decision.
- It never raises for any external, per-file data condition (the
  required rsid missing, a NO_CALL, or any non-SNP classification). Each
  such condition is represented as
  TraitPrediction(status=PredictionStatus.INSUFFICIENT_DATA).
- It performs no orchestration (no registry iteration, no knowledge of
  any other trait) and no reporting/presentation logic (no prose, no
  UI fields) -- it returns only the objective facts a TraitPrediction
  carries.

This is a plain, independent class -- not a shared base class or mixin,
and not sharing any implementation with LactasePersistenceModel despite
the identical dominant-single-SNP interpretation shape. Future trait
models with different biology (e.g. ACTN3's three-genotype-category
interpretation) are expected to be separate, independent classes of
their own.
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

_TRAIT_ID = "earwax_type"
_REQUIRED_RSID = "rs17822931"

_PHENOTYPE_WET = "wet earwax"
_PHENOTYPE_DRY = "dry earwax"


class EarwaxTypeModel:
    """The concrete TraitModel for earwax type.

    Permanently bound to rs17822931, per the frozen TraitModel
    contract's convention that a model does not receive its required
    rsid(s) as an argument -- they are this model's own, hardcoded
    knowledge.
    """

    def predict(self, genotype_calls: Mapping[str, GenotypeCall]) -> TraitPrediction:
        """Produce one TraitPrediction for earwax type from this file's
        observed rs17822931 call, if any.

        Args:
            genotype_calls: This file's already-resolved GenotypeCall(s),
                keyed by RSID. Only the rs17822931 entry (if present) is
                consulted.

        Returns:
            A TraitPrediction with status=PREDICTED and a phenotype
            label when rs17822931 was observed as a SNP call; otherwise
            status=INSUFFICIENT_DATA, with any partially-observed
            GenotypeCall still surfaced in observed_genotypes for
            transparency.
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

        # rs17822931 is a permanently-known, frozen SNP_REGISTRY entry
        # for this model -- its absence would be a static-data authoring
        # defect (model/registry authored out of sync), not a per-file
        # runtime condition, so it is deliberately not guarded with an
        # INSUFFICIENT_DATA branch; a missing entry surfaces as a
        # KeyError, caught by tests, not represented as prediction data.
        snp_record = SNP_REGISTRY[_REQUIRED_RSID]

        is_wet = snp_record.phenotype_associated_allele in call.alleles
        predicted_phenotype = _PHENOTYPE_WET if is_wet else _PHENOTYPE_DRY

        return TraitPrediction(
            trait_id=_TRAIT_ID,
            status=PredictionStatus.PREDICTED,
            predicted_phenotype=predicted_phenotype,
            confidence=ConfidenceLevel.HIGH,
            observed_genotypes={_REQUIRED_RSID: call},
            supporting_snps={_REQUIRED_RSID: snp_record},
        )
