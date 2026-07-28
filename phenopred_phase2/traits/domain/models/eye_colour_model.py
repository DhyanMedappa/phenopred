# phenopred_phase2/traits/domain/models/eye_colour_model.py
"""Eye colour (IrisPlex) trait model -- the fifth concrete TraitModel
implementation, and the first to combine six SNPs into a three-category
(brown/blue/intermediate) classification.

Per the Phase 2 Architecture Blueprint, Section 8.1 ("Eye Colour --
Final Decision"), the IrisPlex panel consists of six SNPs --
rs12913832 (HERC2), rs1800407 (OCA2), rs12896399 (SLC24A4), rs16891982
(SLC45A2), rs1393350 (TYR), rs12203592 (IRF4) -- originally published
as a fitted multinomial logistic regression (Walsh et al. 2011). That
published coefficient table has not been sourced or verified in this
project (a separate, not-yet-completed task), so this model implements
the blueprint's own pre-committed fallback instead: "the same real
6-SNP panel, scored by a transparent, documented rule (heaviest weight
on rs12913832, independently the strongest single predictor in every
source reviewed)". This is NOT the peer-reviewed IrisPlex regression --
every prediction this model produces is explicitly labeled as such in
the phenotype string itself, per the blueprint's own required wording:
"IrisPlex SNP panel, simplified scoring -- published coefficients not
used."

Scoring approach (transparent arithmetic, not a new abstraction):
for each of the six SNPs, this model determines how many copies (0, 1,
or 2) of that SNP's phenotype_associated_allele (from SNP_REGISTRY) are
present in the observed genotype -- built entirely from SNP_REGISTRY's
own reference_allele/alternate_allele/phenotype_associated_allele,
never hardcoded allele letters, matching every prior model's derivation
style. rs12913832 (HERC2)'s dosage is weighted double relative to each
of the other five SNPs (giving it roughly twice the influence of any
single other locus on the combined score), reflecting its
well-documented status as the single strongest individual predictor.
The weighted sum (range 0-14) is compared against two fixed,
documented thresholds to select brown, blue, or intermediate.

This is a bounded, explicit rule -- not a fitted statistical model, not
a machine-learning classifier, and not a new scoring framework or
probability engine. It is the same class of transparent arithmetic
already used in BitterTasteModel's per-locus zygosity derivation,
extended from pattern-matching to summation because six SNPs
contributing to a single combined score cannot be represented as a
small, enumerable truth table the way three SNPs' diplotype could.

Confidence: ConfidenceLevel.MODERATE for a decisive (brown or blue)
call -- reflecting that rs12913832 alone carries real, well-documented
predictive strength, even though this is a simplified heuristic, not
the fitted model. ConfidenceLevel.LOW for an intermediate call --
IrisPlex's own published validation studies report near-zero
sensitivity for correctly identifying intermediate eye colour even
under the real fitted model, so a simplified heuristic's intermediate
call deserves no higher confidence than that.

Evidence preservation, sufficiency, and INSUFFICIENT_DATA handling
follow BitterTasteModel's established convention exactly: all six loci
are required (no partial regression over a subset); observed_genotypes
preserves whatever of the six loci were actually provided, even on
INSUFFICIENT_DATA; supporting_snps is populated with all six
SNP_REGISTRY records only when a prediction is actually produced,
empty on INSUFFICIENT_DATA, matching TraitPrediction's documented
convention and every other TraitModel in this codebase.

This class satisfies the frozen TraitModel Protocol structurally (see
"Trait Contract Layer -- Frozen Architecture Specification v1"):

- It accepts only a Mapping[str, GenotypeCall] -- never a GenotypeIndex,
  DataRow, or any file-level object. It performs no file I/O.
- It consults SNP_REGISTRY directly, by static import, for all six
  required rsids' biological metadata -- never injected, per the frozen
  contract's Option-A decision.
- It never raises for any external, per-file data condition. Every
  unresolvable pattern is represented as
  TraitPrediction(status=PredictionStatus.INSUFFICIENT_DATA), never an
  exception.
- It performs no orchestration (no registry iteration, no knowledge of
  any other trait) and no reporting/presentation logic beyond the
  single required disclosure clause embedded in the phenotype label.

This is a plain, independent class -- not a shared base class or mixin,
and it shares no implementation with LactasePersistenceModel,
EarwaxTypeModel, ACTN3Model, or BitterTasteModel. The one small
module-private helper function below (_light_allele_dosage) is local
to this file only, used six times within this single model's own
logic -- not a new cross-model abstraction layer.

Note: this model currently has no corresponding TraitDefinition entry
in trait_registry.py -- that registration step is explicitly out of
scope for this implementation task.
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

_TRAIT_ID = "eye_colour"

_RSID_HERC2 = "rs12913832"
_RSID_OCA2 = "rs1800407"
_RSID_SLC24A4 = "rs12896399"
_RSID_SLC45A2 = "rs16891982"
_RSID_TYR = "rs1393350"
_RSID_IRF4 = "rs12203592"

_REQUIRED_RSIDS = (
    _RSID_HERC2,
    _RSID_OCA2,
    _RSID_SLC24A4,
    _RSID_SLC45A2,
    _RSID_TYR,
    _RSID_IRF4,
)

# HERC2 (rs12913832) is weighted double relative to each of the other
# five SNPs, per the blueprint's explicit "heaviest weight on
# rs12913832" instruction. Weighted score range: 0 (all dark-allele
# homozygous) to 14 (HERC2 dosage 2 * weight 2 = 4, plus the other five
# SNPs' dosage 2 each = 10; 4 + 10 = 14).
_HERC2_WEIGHT = 2
_MAX_WEIGHTED_SCORE = (2 * _HERC2_WEIGHT) + (2 * 5)
_BLUE_THRESHOLD = 10
_BROWN_THRESHOLD = 4

_DISCLOSURE = "IrisPlex SNP panel, simplified scoring -- published coefficients not used"
_PHENOTYPE_BLUE = f"blue ({_DISCLOSURE})"
_PHENOTYPE_BROWN = f"brown ({_DISCLOSURE})"
_PHENOTYPE_INTERMEDIATE = f"intermediate ({_DISCLOSURE})"


def _light_allele_dosage(call: GenotypeCall | None, record: SNPRecord) -> int | None:
    """Determine how many copies (0, 1, or 2) of `record`'s
    phenotype_associated_allele are present in `call`'s observed
    genotype.

    Returns None if the call is absent, not a SNP classification, or a
    SNP genotype whose alleles match neither the homozygous-associated,
    heterozygous, nor homozygous-other shape for this locus (a data
    anomaly, never guessed at).
    """
    if call is None or call.kind != GenotypeCallKind.SNP:
        return None

    associated_allele = record.phenotype_associated_allele
    other_allele = (
        record.alternate_allele
        if record.reference_allele == associated_allele
        else record.reference_allele
    )

    homozygous_associated = "".join(sorted(associated_allele + associated_allele))
    homozygous_other = "".join(sorted(other_allele + other_allele))
    heterozygous = "".join(sorted(associated_allele + other_allele))

    if call.alleles == homozygous_associated:
        return 2
    if call.alleles == heterozygous:
        return 1
    if call.alleles == homozygous_other:
        return 0

    print(
    "FAILED:",
    record.rsid,
    "call:",
    call.alleles,
    "associated:",
    associated_allele,
    "other:",
    other_allele
    )
    return None


class EyeColourModel:
    """The concrete TraitModel for eye colour (IrisPlex, simplified
    scoring).

    Permanently bound to the six IrisPlex rsids, per the frozen
    TraitModel contract's convention that a model does not receive its
    required rsid(s) as an argument -- they are this model's own,
    hardcoded knowledge.
    """

    def predict(self, genotype_calls: Mapping[str, GenotypeCall]) -> TraitPrediction:
        """Produce one TraitPrediction for eye colour from this file's
        observed genotype calls at all six required IrisPlex loci.

        Args:
            genotype_calls: This file's already-resolved GenotypeCall(s),
                keyed by RSID. Only the six required rsid entries (if
                present) are consulted.

        Returns:
            A TraitPrediction with status=PREDICTED and a category-based
            phenotype label (brown/blue/intermediate, always disclosing
            the simplified-scoring caveat) when all six loci resolve to
            a determinable allele dosage; otherwise
            status=INSUFFICIENT_DATA. observed_genotypes preserves
            whichever of the six loci were actually provided;
            supporting_snps is populated with all six SNP_REGISTRY
            records only when a prediction is actually produced.
        """
        calls = {rsid: genotype_calls.get(rsid) for rsid in _REQUIRED_RSIDS}
        observed_genotypes = {
            rsid: call for rsid, call in calls.items() if call is not None
        }

        dosages: dict[str, int] = {}
        for rsid in _REQUIRED_RSIDS:
            # Each rsid is a permanently-known, frozen SNP_REGISTRY
            # entry for this model -- absence would be a static-data
            # authoring defect, not a per-file runtime condition, so it
            # is deliberately not guarded with an INSUFFICIENT_DATA
            # branch; a missing entry surfaces as a KeyError, caught by
            # tests, not represented as prediction data.
            dosage = _light_allele_dosage(calls[rsid], SNP_REGISTRY[rsid])
            if dosage is None:
                # A missing/non-SNP/unrecognized-allele locus anywhere
                # in the six-SNP panel: not safely resolvable without a
                # partial-regression guess. Never forced into a
                # category.
                return TraitPrediction(
                    trait_id=_TRAIT_ID,
                    status=PredictionStatus.INSUFFICIENT_DATA,
                    predicted_phenotype=None,
                    confidence=None,
                    observed_genotypes=observed_genotypes,
                    supporting_snps={},
                )
            dosages[rsid] = dosage

        herc2_dosage = dosages[_RSID_HERC2]
        other_dosage_sum = sum(
            dosage for rsid, dosage in dosages.items() if rsid != _RSID_HERC2
        )
        weighted_score = (herc2_dosage * _HERC2_WEIGHT) + other_dosage_sum

        if weighted_score >= _BLUE_THRESHOLD:
            predicted_phenotype = _PHENOTYPE_BLUE
            confidence = ConfidenceLevel.MODERATE
        elif weighted_score <= _BROWN_THRESHOLD:
            predicted_phenotype = _PHENOTYPE_BROWN
            confidence = ConfidenceLevel.MODERATE
        else:
            predicted_phenotype = _PHENOTYPE_INTERMEDIATE
            confidence = ConfidenceLevel.LOW

        supporting_snps = {rsid: SNP_REGISTRY[rsid] for rsid in _REQUIRED_RSIDS}

        return TraitPrediction(
            trait_id=_TRAIT_ID,
            status=PredictionStatus.PREDICTED,
            predicted_phenotype=predicted_phenotype,
            confidence=confidence,
            observed_genotypes=observed_genotypes,
            supporting_snps=supporting_snps,
        )
