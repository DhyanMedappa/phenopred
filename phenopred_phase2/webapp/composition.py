# phenopred_phase2/webapp/composition.py
"""Thin orchestration layer for the single-file Streamlit flow."""

from __future__ import annotations
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from phenopred.application.composition_root import build_profile_file_use_case
from phenopred_phase2.comparison.application.comparison_use_case import run_comparison
from phenopred_phase2.reporting.entities import PhenoPredReport
from phenopred_phase2.reporting.report_builder import build_phenopred_report
from phenopred_phase2.traits.application.composition import (
    build_genotype_index,
    run_trait_pipeline,
)
from phenopred_phase2.traits.domain.trait_registry import TRAIT_REGISTRY
from phenopred_phase2.traits.reporting.trait_card_builder import build_trait_cards


def profile_file(file_path: str) -> Mapping[str, Any]:
    """Run V1's profiling pipeline for one file."""
    use_case = build_profile_file_use_case()
    return use_case.execute(Path(file_path))


def build_report(profile_result: Mapping[str, Any]) -> PhenoPredReport:
    """Run the Phase 2 trait pipeline and assemble a single-file report."""
    predictions = run_trait_pipeline(profile_result)
    trait_cards = build_trait_cards(TRAIT_REGISTRY, predictions)
    return build_phenopred_report(profile_result["report"], trait_cards)


def run_single_file_pipeline(file_path: str) -> PhenoPredReport:
    """Profile one file and assemble its PhenoPredReport, end to end."""
    profile_result = profile_file(file_path)
    return build_report(profile_result)


def run_two_file_pipeline(file_path_a: str, file_path_b: str) -> PhenoPredReport:
    """Profile two files and assemble their combined PhenoPredReport."""
    profile_result_a = profile_file(file_path_a)
    profile_result_b = profile_file(file_path_b)

    genotype_index_a = build_genotype_index(profile_result_a)
    genotype_index_b = build_genotype_index(profile_result_b)

    predictions_a = run_trait_pipeline(profile_result_a)
    predictions_b = run_trait_pipeline(profile_result_b)

    trait_cards_a = build_trait_cards(TRAIT_REGISTRY, predictions_a)
    trait_cards_b = build_trait_cards(TRAIT_REGISTRY, predictions_b)

    comparison = run_comparison(
        genotype_index_a, genotype_index_b, predictions_a, predictions_b
    )

    return build_phenopred_report(
        profile_result_a["report"],
        trait_cards_a,
        profile_result_b["report"],
        trait_cards_b,
        comparison,
    )