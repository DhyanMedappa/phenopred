# phenopred_phase2/traits/domain/models/bitter_taste_model.py
"""Bitter taste (TAS2R38) trait model -- the fourth concrete TraitModel
implementation, and the first to combine multiple SNPs into one joint
interpretation rather than reading a single locus (contrast with
LactasePersistenceModel, EarwaxTypeModel, and ACTN3Model).

Per the Phase 2 Architecture Blueprint, Section 8.5 ("Bitter Taste
(TAS2R38) -- Final Decision"): three SNPs (rs713598, rs1726866,
rs10246939) jointly determine PTC/PROP bitter-taste sensitivity via the
two common TAS2R38 haplotypes -- PAV (taster) and AVI (non-taster).
PAV is dominant: one PAV haplotype is sufficient for taster status.

This is a BOUNDED haplotype/diplotype interpretation, not SNP voting,
2-of-3 allele scoring, or independent-per-SNP averaging -- combining
per-locus zygosity into exactly three recognized diplotype patterns,
built entirely from SNP_REGISTRY's own reference_allele/alternate_allele
/phenotype_associated_allele (never hardcoded allele letters, matching
ACTN3Model's derivation style):

- All three loci homozygous for the phenotype_associated (PAV) allele
  -> PAV/PAV, taster, ConfidenceLevel.HIGH (unambiguous; the real demo
  files' actual case per Section 8.5).
- All three loci homozygous for the other (AVI) allele -> AVI/AVI,
  non-taster, ConfidenceLevel.HIGH (unambiguous).
- All three loci heterozygous, consistently -> an INFERRED PAV/AVI
  diplotype, taster, ConfidenceLevel.MODERATE. Consumer genotype data
  carries no phase information (GenotypeCall has no phase field), so
  this is an explicit, labeled approximation under the common-haplotype
  assumption (PAV and AVI account for the overwhelming majority of
  chromosomes; rarer recombinant haplotypes -- AAI, AAV, AVV, PVI --
  exist but are not modeled here), stated plainly in the phenotype
  label itself per Section 8.5's explicit instruction not to gloss over
  this approximation.
- Any other per-locus pattern (mixed zygosities across loci, any locus
  missing/NO_CALL/INDEL/HAPLOID/UNRECOGNIZED, or a SNP-classified call
  whose alleles match neither this SNP's PAV nor AVI shape) ->
  PredictionStatus.INSUFFICIENT_DATA. Such a pattern is not safely
  resolvable to one of the three patterns above without guessing --
  it may reflect a genuine rare recombinant haplotype or a data
  anomaly, and is never forced into a taster/non-taster label.

Evidence preservation: observed_genotypes includes every one of the
three required loci's GenotypeCall that was actually provided (even
when overall interpretation is INSUFFICIENT_DATA, for transparency
about partial data, mirroring every prior model). supporting_snps
includes all three SNP_REGISTRY records only when a prediction is
actually produced (status=PREDICTED); it is empty on
INSUFFICIENT_DATA, matching TraitPrediction's documented convention
("supporting_snps: ... empty when status is INSUFFICIENT_DATA") and
every other TraitModel in this codebase -- supporting_snps represents
the evidence a produced prediction actually rests on, not a standing
dump of this trait's static reference data independent of whether
interpretation succeeded.

This class satisfies the frozen TraitModel Protocol structurally (see
"Trait Contract Layer -- Frozen Architecture Specification v1"):

- It accepts only a Mapping[str, GenotypeCall] -- never a GenotypeIndex,
  DataRow, or any file-level object. It performs no file I/O.
- It consults SNP_REGISTRY directly, by static import, for all three
  required rsids' biological metadata -- never injected, per the frozen
  contract's Option-A decision.
- It never raises for any external, per-file data condition. Every
  unresolvable pattern is represented as
  TraitPrediction(status=PredictionStatus.INSUFFICIENT_DATA), never an
  exception.
- It performs no orchestration (no registry iteration, no knowledge of
  any other trait) and no reporting/presentation logic (no prose beyond
  the single required approximation caveat embedded in one phenotype
  label, no UI fields).

This is a plain, independent class -- not a shared base class or mixin,
and it shares no implementation with LactasePersistenceModel,
EarwaxTypeModel, or ACTN3Model despite reusing the same sufficiency-
check-then-interpret shape. The one small module-private helper
function below (_classify_locus) is local to this file only, used
three times within this single model's own logic -- not a new
cross-model abstraction layer.
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
from phenopred_phase2.traits.domain.snp_registry import SNP_REGISTRY, SNPRecord

_TRAIT_ID = "bitter_taste"

_RSID_A = "rs713598"
_RSID_B = "rs1726866"
_RSID_C = "rs10246939"
_REQUIRED_RSIDS = (_RSID_A, _RSID_B, _RSID_C)

_ZYGOSITY_PAV = "PAV"
_ZYGOSITY_AVI = "AVI"
_ZYGOSITY_HET = "HET"

_PHENOTYPE_TASTER_PAV_PAV = "taster (PAV/PAV)"
_PHENOTYPE_NON_TASTER_AVI_AVI = "non-taster (AVI/AVI)"
_PHENOTYPE_TASTER_INFERRED_PAV_AVI = (
    "likely taster (inferred PAV/AVI from unphased genotype data; "
    "phase not directly observed)"
)


def _classify_locus(call: GenotypeCall | None, record: SNPRecord) -> str | None:
    """Classify one TAS2R38 locus's zygosity relative to its PAV
    (phenotype_associated_allele) and AVI (the other registry allele).

    Returns "PAV", "AVI", "HET", or None if the call is absent, not a
    SNP classification, or a SNP genotype whose alleles match neither
    this locus's PAV nor AVI shape (a data anomaly, never guessed at).
    """
    if call is None or call.kind != GenotypeCallKind.SNP:
        return None

    pav_allele = record.phenotype_associated_allele
    avi_allele = (
        record.alternate_allele
        if record.reference_allele == pav_allele
        else record.reference_allele
    )

    homozygous_pav_genotype = "".join(sorted(pav_allele + pav_allele))
    homozygous_avi_genotype = "".join(sorted(avi_allele + avi_allele))
    heterozygous_genotype = "".join(sorted(pav_allele + avi_allele))

    if call.alleles == homozygous_pav_genotype:
        return _ZYGOSITY_PAV
    if call.alleles == homozygous_avi_genotype:
        return _ZYGOSITY_AVI
    if call.alleles == heterozygous_genotype:
        return _ZYGOSITY_HET
    return None


class BitterTasteModel:
    """The concrete TraitModel for bitter taste (TAS2R38).

    Permanently bound to rs713598, rs1726866, and rs10246939, per the
    frozen TraitModel contract's convention that a model does not
    receive its required rsid(s) as an argument -- they are this
    model's own, hardcoded knowledge.
    """

    def predict(self, genotype_calls: Mapping[str, GenotypeCall]) -> TraitPrediction:
        """Produce one TraitPrediction for bitter taste from this
        file's observed genotype calls at all three required loci.

        Args:
            genotype_calls: This file's already-resolved GenotypeCall(s),
                keyed by RSID. Only the three required rsid entries (if
                present) are consulted.

        Returns:
            A TraitPrediction with status=PREDICTED and a diplotype-based
            phenotype label when all three loci resolve consistently to
            PAV/PAV, AVI/AVI, or an inferred PAV/AVI pattern; otherwise
            status=INSUFFICIENT_DATA. observed_genotypes preserves
            whichever of the three loci were actually provided;
            supporting_snps always includes all three SNP_REGISTRY
            records for this trait's required rsids.
        """
        calls = {rsid: genotype_calls.get(rsid) for rsid in _REQUIRED_RSIDS}
        observed_genotypes = {
            rsid: call for rsid, call in calls.items() if call is not None
        }

        zygosities = tuple(
            _classify_locus(calls[rsid], SNP_REGISTRY[rsid])
            for rsid in _REQUIRED_RSIDS
        )

        if all(zygosity == _ZYGOSITY_PAV for zygosity in zygosities):
            predicted_phenotype = _PHENOTYPE_TASTER_PAV_PAV
            confidence = ConfidenceLevel.HIGH
        elif all(zygosity == _ZYGOSITY_AVI for zygosity in zygosities):
            predicted_phenotype = _PHENOTYPE_NON_TASTER_AVI_AVI
            confidence = ConfidenceLevel.HIGH
        elif all(zygosity == _ZYGOSITY_HET for zygosity in zygosities):
            predicted_phenotype = _PHENOTYPE_TASTER_INFERRED_PAV_AVI
            confidence = ConfidenceLevel.MODERATE
        else:
            # A mixed-zygosity pattern, a missing/non-SNP locus, or an
            # unrecognized allele combination at any locus: not safely
            # resolvable to one of the three patterns above. Never
            # forced into a taster/non-taster label. supporting_snps is
            # empty here, matching TraitPrediction's documented
            # convention and every other TraitModel in this codebase --
            # observed_genotypes alone carries whatever partial data
            # was actually available, for transparency.
            return TraitPrediction(
                trait_id=_TRAIT_ID,
                status=PredictionStatus.INSUFFICIENT_DATA,
                predicted_phenotype=None,
                confidence=None,
                observed_genotypes=observed_genotypes,
                supporting_snps={},
            )

        # All three rsids are permanently-known, frozen SNP_REGISTRY
        # entries for this model -- absence would be a static-data
        # authoring defect (model/registry authored out of sync), not a
        # per-file runtime condition, so it is deliberately not guarded
        # with an INSUFFICIENT_DATA branch; a missing entry surfaces as
        # a KeyError, caught by tests, not represented as prediction
        # data.
        supporting_snps = {rsid: SNP_REGISTRY[rsid] for rsid in _REQUIRED_RSIDS}

        return TraitPrediction(
            trait_id=_TRAIT_ID,
            status=PredictionStatus.PREDICTED,
            predicted_phenotype=predicted_phenotype,
            confidence=confidence,
            observed_genotypes=observed_genotypes,
            supporting_snps=supporting_snps,
        )