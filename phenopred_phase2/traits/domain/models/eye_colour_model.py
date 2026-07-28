# phenopred_phase2/traits/domain/models/eye_colour_model.py
"""Eye colour (IrisPlex) trait model -- multinomial logistic regression.

Implements the published IrisPlex model (Walsh et al. 2011) using the
coefficient table in irisplex_coefficients.py. See that module's own
docstring for the complete source attribution and verification status
-- in short: a reliable secondary reproduction with disclosed, bounded
uncertainty (notably for rs1393350), not a digit-for-digit verification
against the primary publication.

Model:
    score_blue  = ALPHA_BLUE  + sum(beta_blue[snp]  * dosage[snp])
    score_other = ALPHA_OTHER + sum(beta_other[snp] * dosage[snp])
    p_blue  = exp(score_blue)  / (1 + exp(score_blue) + exp(score_other))
    p_other = exp(score_other) / (1 + exp(score_blue) + exp(score_other))
    p_brown = 1 - p_blue - p_other

Dosage: 0/1/2 copies of each SNP's own counted_allele (from
IRISPLEX_COEFFICIENTS, not SNP_REGISTRY.phenotype_associated_allele --
IrisPlex's fitted coefficients require their own counted-allele
orientation, which is not guaranteed to match the allele
SNP_REGISTRY records for the earlier, unrelated heuristic model).
SNP_REGISTRY is still consulted, but only for its
reference_allele/alternate_allele letters (needed to build the
homozygous-other genotype shape) and for supporting_snps evidence --
neither of which is IrisPlex-specific.

Sufficiency: all six loci are required, exactly as before -- any one
locus that is missing, non-SNP, or an unrecognized allele combination
yields whole-panel INSUFFICIENT_DATA. No partial regression over a
subset is ever performed.

Confidence: derived from the margin between the highest and
second-highest predicted probability (HIGH >= 0.50, MODERATE >= 0.25,
LOW otherwise). This represents only how separated the model's own
output is -- it is not biological certainty, not clinical confidence,
and not a calibrated measure of real-world prediction accuracy.

Output: predicted_phenotype is a concise probability statement (e.g.
"Blue: 88.5%, Other: 8.1%, Brown: 3.4%. Most likely category: Blue.")
using IrisPlex's own category name "other" (not "intermediate").
Detailed provenance/limitations live in irisplex_coefficients.py's
citations, not in this string.

This class satisfies the frozen TraitModel Protocol structurally: it
accepts only a Mapping[str, GenotypeCall], performs no file I/O, never
raises for any external per-file data condition, and performs no
orchestration or reporting/presentation logic beyond the concise
disclosure already described above.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from phenopred_phase2.traits.domain.entities import (
    ConfidenceLevel,
    GenotypeCall,
    GenotypeCallKind,
    PredictionStatus,
    TraitPrediction,
)
from phenopred_phase2.traits.domain.irisplex_coefficients import (
    ALPHA_BLUE,
    ALPHA_OTHER,
    IRISPLEX_COEFFICIENTS,
)
from phenopred_phase2.traits.domain.snp_registry import SNP_REGISTRY

_TRAIT_ID = "eye_colour"

_REQUIRED_RSIDS = (
    "rs12913832",
    "rs1800407",
    "rs12896399",
    "rs16891982",
    "rs1393350",
    "rs12203592",
)

_HIGH_MARGIN_THRESHOLD = 0.50
_MODERATE_MARGIN_THRESHOLD = 0.25


def _irisplex_dosage(call: GenotypeCall | None, rsid: str) -> int | None:
    """Determine how many copies (0, 1, or 2) of this SNP's IrisPlex
    counted_allele are present in `call`'s observed genotype.

    Returns None if the call is absent, not a SNP classification, or a
    SNP genotype whose alleles match neither the homozygous-counted,
    heterozygous, nor homozygous-other shape for this locus.
    """
    if call is None or call.kind != GenotypeCallKind.SNP:
        return None

    counted_allele = IRISPLEX_COEFFICIENTS[rsid].counted_allele
    snp_record = SNP_REGISTRY[rsid]
    other_allele = (
        snp_record.alternate_allele
        if snp_record.reference_allele == counted_allele
        else snp_record.reference_allele
    )

    homozygous_counted = "".join(sorted(counted_allele + counted_allele))
    homozygous_other = "".join(sorted(other_allele + other_allele))
    heterozygous = "".join(sorted(counted_allele + other_allele))

    if call.alleles == homozygous_counted:
        return 2
    if call.alleles == heterozygous:
        return 1
    if call.alleles == homozygous_other:
        return 0
    return None


def _confidence_from_margin(probabilities: dict[str, float]) -> ConfidenceLevel:
    """Derive a ConfidenceLevel from the gap between the highest and
    second-highest predicted probability. This communicates only how
    separated the model's own output is -- not biological certainty,
    not clinical confidence, not calibrated prediction accuracy.
    """
    ranked = sorted(probabilities.values(), reverse=True)
    margin = ranked[0] - ranked[1]

    if margin >= _HIGH_MARGIN_THRESHOLD:
        return ConfidenceLevel.HIGH
    if margin >= _MODERATE_MARGIN_THRESHOLD:
        return ConfidenceLevel.MODERATE
    return ConfidenceLevel.LOW


def _softmax_probabilities(score_blue: float, score_other: float) -> dict[str, float]:
    """Convert the two IrisPlex linear scores into three category
    probabilities, using a numerically stable formulation (subtracting
    the maximum score before exponentiating) to avoid overflow for
    large score magnitudes.
    """
    max_score = max(0.0, score_blue, score_other)

    exp_zero = math.exp(0.0 - max_score)
    exp_blue = math.exp(score_blue - max_score)
    exp_other = math.exp(score_other - max_score)

    denominator = exp_zero + exp_blue + exp_other

    p_blue = exp_blue / denominator
    p_other = exp_other / denominator
    p_brown = exp_zero / denominator

    return {"blue": p_blue, "other": p_other, "brown": p_brown}


class EyeColourModel:
    """The concrete TraitModel for eye colour (IrisPlex multinomial
    logistic regression).

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
            A TraitPrediction with status=PREDICTED and a probability
            summary (blue/other/brown percentages plus most-likely
            category) when all six loci resolve to a determinable
            allele dosage; otherwise status=INSUFFICIENT_DATA.
            observed_genotypes preserves whichever of the six loci were
            actually provided; supporting_snps is populated with all
            six SNP_REGISTRY records only when a prediction is actually
            produced.
        """
        calls = {rsid: genotype_calls.get(rsid) for rsid in _REQUIRED_RSIDS}
        observed_genotypes = {
            rsid: call for rsid, call in calls.items() if call is not None
        }

        dosages: dict[str, int] = {}
        for rsid in _REQUIRED_RSIDS:
            dosage = _irisplex_dosage(calls[rsid], rsid)
            if dosage is None:
                return TraitPrediction(
                    trait_id=_TRAIT_ID,
                    status=PredictionStatus.INSUFFICIENT_DATA,
                    predicted_phenotype=None,
                    confidence=None,
                    observed_genotypes=observed_genotypes,
                    supporting_snps={},
                )
            dosages[rsid] = dosage

        score_blue = ALPHA_BLUE + sum(
            IRISPLEX_COEFFICIENTS[rsid].beta_blue * dosage
            for rsid, dosage in dosages.items()
        )
        score_other = ALPHA_OTHER + sum(
            IRISPLEX_COEFFICIENTS[rsid].beta_other * dosage
            for rsid, dosage in dosages.items()
        )

        probabilities = _softmax_probabilities(score_blue, score_other)
        most_likely_category = max(probabilities, key=probabilities.get)
        confidence = _confidence_from_margin(probabilities)

        predicted_phenotype = (
            f"Blue: {probabilities['blue'] * 100:.1f}%, "
            f"Other: {probabilities['other'] * 100:.1f}%, "
            f"Brown: {probabilities['brown'] * 100:.1f}%. "
            f"Most likely category: {most_likely_category.capitalize()}."
        )

        supporting_snps = {rsid: SNP_REGISTRY[rsid] for rsid in _REQUIRED_RSIDS}

        return TraitPrediction(
            trait_id=_TRAIT_ID,
            status=PredictionStatus.PREDICTED,
            predicted_phenotype=predicted_phenotype,
            confidence=confidence,
            observed_genotypes=observed_genotypes,
            supporting_snps=supporting_snps,
        )