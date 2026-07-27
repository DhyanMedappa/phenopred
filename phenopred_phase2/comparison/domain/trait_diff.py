# phenopred_phase2/comparison/domain/trait_diff.py
"""Trait-level comparison between two files' already-computed
TraitPrediction mappings.

Per the approved Comparison Engine Final Design Specification, this
module owns exactly one responsibility: given two files'
Mapping[str, TraitPrediction] (the exact return type of
composition.run_trait_pipeline(), consumed here unmodified), produce
one TraitComparison per trait_id present in either mapping.

Boundaries (frozen by the approved specification):

- Never accesses raw genotype data -- consumes only already-produced
  TraitPrediction values, never a GenotypeIndex, DataRow, or
  GenotypeCall directly of its own.
- Never runs or re-runs any TraitModel -- every TraitPrediction it
  compares was already produced elsewhere (TraitEngine.run()).
- Never imports TRAIT_REGISTRY -- the set of trait_ids to compare is
  derived entirely from the two supplied mappings' own keys, keeping
  this module decoupled from the trait domain exactly the way
  TraitEngine decoupled itself from concrete models via injected
  mappings.
- Never generates report/UI prose -- the resulting TraitAgreement is a
  bare enum value; both full TraitPredictions are carried through
  unaltered specifically so a later reporting layer can explain a
  disagreement using already-existing evidence (observed_genotypes,
  supporting_snps) without this module inventing any new field.

Comparison rule, in precedence order:

    1. Either side's prediction absent (trait_id missing from that
       file's mapping) -> MISSING_TRAIT.
    2. Either present prediction has status=INSUFFICIENT_DATA ->
       INSUFFICIENT_DATA.
    3. Both PREDICTED -> AGREE if predicted_phenotype strings are
       equal, else DISAGREE. Confidence is deliberately never compared,
       per the Comparison Engine's approved responsibility boundary.
"""

from __future__ import annotations

from collections.abc import Mapping

from phenopred_phase2.comparison.domain.entities import TraitAgreement, TraitComparison
from phenopred_phase2.traits.domain.entities import PredictionStatus, TraitPrediction


def compare_trait_predictions(
    predictions_a: Mapping[str, TraitPrediction],
    predictions_b: Mapping[str, TraitPrediction],
) -> Mapping[str, TraitComparison]:
    """Compare two files' trait predictions, one TraitComparison per
    trait_id present in either mapping.

    Args:
        predictions_a: File A's Mapping[str, TraitPrediction] (e.g. the
            return value of composition.run_trait_pipeline()).
        predictions_b: File B's Mapping[str, TraitPrediction], symmetric
            to predictions_a.

    Returns:
        A trait_id-keyed mapping of TraitComparison, one entry per
        trait_id present in predictions_a and/or predictions_b, in
        ascending trait_id order (deterministic, mirroring this
        codebase's established NFR-3 discipline).
    """
    all_trait_ids = sorted(set(predictions_a.keys()) | set(predictions_b.keys()))

    comparisons: dict[str, TraitComparison] = {}
    for trait_id in all_trait_ids:
        prediction_a = predictions_a.get(trait_id)
        prediction_b = predictions_b.get(trait_id)

        agreement = _classify_agreement(prediction_a, prediction_b)

        comparisons[trait_id] = TraitComparison(
            trait_id=trait_id,
            prediction_a=prediction_a,
            prediction_b=prediction_b,
            agreement=agreement,
        )

    return comparisons


def _classify_agreement(
    prediction_a: TraitPrediction | None,
    prediction_b: TraitPrediction | None,
) -> TraitAgreement:
    """Classify one trait_id's agreement per the precedence rule
    documented in this module's own docstring.
    """
    if prediction_a is None or prediction_b is None:
        return TraitAgreement.MISSING_TRAIT

    if (
        prediction_a.status is PredictionStatus.INSUFFICIENT_DATA
        or prediction_b.status is PredictionStatus.INSUFFICIENT_DATA
    ):
        return TraitAgreement.INSUFFICIENT_DATA

    if prediction_a.predicted_phenotype == prediction_b.predicted_phenotype:
        return TraitAgreement.AGREE

    return TraitAgreement.DISAGREE
