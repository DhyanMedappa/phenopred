# phenopred_phase2/traits/domain/models/lactase_persistence_model.py
"""Lactase persistence trait model -- the first concrete TraitModel
implementation, establishing the reusable pattern for the remaining
mandatory trait models (eye colour, ACTN3, earwax, bitter taste).

Per the Phase 2 Architecture Blueprint, Section 8.2 ("Lactase
Persistence -- Final Decision"): a single SNP (rs4988235), modeled as an
unchanged, deterministic genotype table. Persistence is inherited in a
dominant fashion -- one copy of the phenotype-associated allele
(SNP_REGISTRY's forward-strand "A", corresponding to the historically-
cited gene-strand "T" in the -13910C>T literature convention) is
sufficient for lactase persistence; the homozygous-reference genotype
("GG" forward-strand, equivalent to the literature's "CC") is lactase
non-persistent. Evidence strength is stated as "very high (one of the
most replicated single-SNP trait associations in human genetics)",
which this model maps directly to ConfidenceLevel.HIGH.

This class satisfies the frozen TraitModel Protocol structurally (see
"Trait Contract Layer -- Frozen Architecture Specification v1"):

- It accepts only a Mapping[str, GenotypeCall] -- never a GenotypeIndex,
  DataRow, or any file-level object. It performs no file I/O.
- It consults SNP_REGISTRY directly, by static import, for rs4988235's
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

This is a plain, independent class -- not a shared base class or mixin.
Only this trait's own genotype-to-phenotype interpretation (a simple
dominant single-SNP rule) lives here; the reusable shape is the file
location, the class structure, and the sufficiency-check-then-interpret
sequence, not shared implementation code. Future trait models with
different biology (e.g. ACTN3's three-genotype-category interpretation)
are expected to be separate, independent classes of their own.
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

_TRAIT_ID = "lactase_persistence"
_REQUIRED_RSID = "rs4988235"

_PHENOTYPE_PERSISTENT = "lactase persistent"
_PHENOTYPE_NON_PERSISTENT = "lactase non-persistent"


class LactasePersistenceModel:
    """The concrete TraitModel for lactase persistence.

    Permanently bound to rs4988235, per the frozen TraitModel contract's
    convention that a model does not receive its required rsid(s) as an
    argument -- they are this model's own, hardcoded knowledge.
    """

    def predict(self, genotype_calls: Mapping[str, GenotypeCall]) -> TraitPrediction:
        """Produce one TraitPrediction for lactase persistence from this
        file's observed rs4988235 call, if any.

        Args:
            genotype_calls: This file's already-resolved GenotypeCall(s),
                keyed by RSID. Only the rs4988235 entry (if present) is
                consulted.

        Returns:
            A TraitPrediction with status=PREDICTED and a phenotype
            label when rs4988235 was observed as a SNP call; otherwise
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

        # rs4988235 is a permanently-known, frozen SNP_REGISTRY entry
        # for this model -- its absence would be a static-data authoring
        # defect (model/registry authored out of sync), not a per-file
        # runtime condition, so it is deliberately not guarded with an
        # INSUFFICIENT_DATA branch; a missing entry surfaces as a
        # KeyError, caught by tests, not represented as prediction data.
        snp_record = SNP_REGISTRY[_REQUIRED_RSID]

        is_persistent = snp_record.phenotype_associated_allele in call.alleles
        predicted_phenotype = (
            _PHENOTYPE_PERSISTENT if is_persistent else _PHENOTYPE_NON_PERSISTENT
        )

        return TraitPrediction(
            trait_id=_TRAIT_ID,
            status=PredictionStatus.PREDICTED,
            predicted_phenotype=predicted_phenotype,
            confidence=ConfidenceLevel.HIGH,
            observed_genotypes={_REQUIRED_RSID: call},
            supporting_snps={_REQUIRED_RSID: snp_record},
        )