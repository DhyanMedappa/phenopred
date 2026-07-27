# phenopred_phase2/comparison/application/comparison_use_case.py
"""Comparison Engine orchestration layer -- thin coordination only.

Per the approved Comparison Engine Final Design Specification, this
module owns exactly one responsibility: given two files' already-built
GenotypeIndex instances and already-computed TraitPrediction mappings,
call the three domain calculators (concordance_calculator,
identity_heuristic, trait_diff) and assemble the resulting
ComparisonReport.

This module contains no business/domain logic of its own -- no
classification rule, no threshold, no comparison decision is made
here. It mirrors composition.py's own "construction and wiring only"
role for the trait pipeline, applied to the comparison pipeline.
"""

from __future__ import annotations

from collections.abc import KeysView, Mapping
from typing import Protocol

from phenopred_phase2.comparison.domain.concordance_calculator import (
    calculate_concordance,
)
from phenopred_phase2.comparison.domain.entities import ComparisonReport
from phenopred_phase2.comparison.domain.identity_heuristic import (
    interpret_identity_likelihood,
)
from phenopred_phase2.comparison.domain.trait_diff import compare_trait_predictions
from phenopred_phase2.traits.domain.entities import GenotypeCall, TraitPrediction


class _ComparableGenotypeSource(Protocol):
    """The only capability this orchestrator requires from a genotype
    source for one file -- identical in shape to
    concordance_calculator's own local Protocol, restated here so this
    module's own dependency is expressed as a capability, not a
    concrete GenotypeIndex import.
    """

    def get(self, rsid: str) -> GenotypeCall | None:
        ...

    def keys(self) -> KeysView[str]:
        ...


def run_comparison(
    genotype_index_a: _ComparableGenotypeSource,
    genotype_index_b: _ComparableGenotypeSource,
    predictions_a: Mapping[str, TraitPrediction],
    predictions_b: Mapping[str, TraitPrediction],
) -> ComparisonReport:
    """Run the complete Comparison Engine for two files.

    Args:
        genotype_index_a: File A's already-built GenotypeIndex (or
            anything exposing the same .get()/.keys() interface).
        genotype_index_b: File B's already-built GenotypeIndex,
            symmetric to genotype_index_a.
        predictions_a: File A's Mapping[str, TraitPrediction] (e.g. the
            return value of composition.run_trait_pipeline()).
        predictions_b: File B's Mapping[str, TraitPrediction], symmetric
            to predictions_a.

    Returns:
        A ComparisonReport aggregating the genome-wide ConcordanceResult,
        the derived IdentityLikelihood, and every trait_id's
        TraitComparison.
    """
    concordance = calculate_concordance(genotype_index_a, genotype_index_b)
    identity_likelihood = interpret_identity_likelihood(concordance)
    trait_comparisons = compare_trait_predictions(predictions_a, predictions_b)

    return ComparisonReport(
        concordance=concordance,
        identity_likelihood=identity_likelihood,
        trait_comparisons=trait_comparisons,
    )
