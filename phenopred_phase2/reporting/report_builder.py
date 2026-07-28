# phenopred_phase2/reporting/report_builder.py
"""Phase 2 Combined Report Assembly -- assembly only.

Per the approved Combined Report Assembly milestone, this module
provides the one function responsible for pairing already-computed
Phase 1 and Phase 2 output into one PhenoPredReport, mirroring
trait_card_builder.py's own "assembly, never computation" role exactly,
and V1's report_builder.py's identical "this class needs OpenQuestionRegistry
to select applicable open questions... every value it assembles is
already computed elsewhere" discipline, applied here with no injected
collaborator needed (there is no OpenQuestionRegistry-equivalent
dependency for this step).

This module:

- Performs no computation, no recomputation, no model invocation, and
  no pipeline execution of any kind -- every argument to
  build_phenopred_report() is already fully computed by the caller
  (V1's ProfileFileUseCase/ReportBuilder, Phase 2's
  trait_card_builder.build_trait_cards(), and Phase 2's
  comparison_use_case.run_comparison()) before this function is ever
  called.
- Never imports ProfileFileUseCase, TraitEngine, TraitModel,
  GenotypeIndex, SNP_REGISTRY, TRAIT_REGISTRY, or the Comparison Engine
  domain calculators directly -- this function is trait-agnostic and
  pipeline-agnostic by construction, exactly mirroring
  build_trait_card()'s own "never imports TraitEngine, GenotypeIndex, or
  SNP_REGISTRY directly" discipline.
- Delegates all structural validation to PhenoPredReport's own
  __post_init__ -- this function performs no cross-input consistency
  check of its own beyond passing its arguments straight through,
  because (unlike build_trait_card(), which must verify a trait_id
  match between two independently-supplied inputs before it can decide
  what value to construct TraitCard with) this function derives no
  field from more than one source; each PhenoPredReport field is
  exactly one of this function's own arguments, unmodified.
- Never mutates any argument it is given.

See the Phase 2 Final Architecture Blueprint, Section 14 (Reporting
Design) for the complete, authoritative rationale this module
implements. No entities.py (Phase 2 traits or comparison), interfaces.py,
genotype_index.py, snp_registry.py, trait_registry.py,
trait_model_registry.py, trait_engine.py, trait_card_builder.py,
concordance_calculator.py, identity_heuristic.py, trait_diff.py,
comparison_use_case.py, or any V1 file is modified by this module.
"""

from __future__ import annotations

from collections.abc import Mapping

from phenopred.domain.entities import ProfilingReport
from phenopred_phase2.comparison.domain.entities import ComparisonReport
from phenopred_phase2.reporting.entities import PhenoPredReport
from phenopred_phase2.traits.domain.entities import TraitCard


def build_phenopred_report(
    file_a_profiling_report: ProfilingReport,
    file_a_trait_cards: Mapping[str, TraitCard],
    file_b_profiling_report: ProfilingReport | None = None,
    file_b_trait_cards: Mapping[str, TraitCard] | None = None,
    comparison: ComparisonReport | None = None,
) -> PhenoPredReport:
    """Assemble one PhenoPredReport from already-computed Phase 1 and
    Phase 2 output.

    Args:
        file_a_profiling_report: File A's already-built ProfilingReport
            (e.g. from V1's ProfileFileUseCase/ReportBuilder). Embedded
            whole and unaltered.
        file_a_trait_cards: File A's already-built
            Mapping[str, TraitCard] (e.g. the return value of
            trait_card_builder.build_trait_cards()). Embedded unaltered.
        file_b_profiling_report: File B's already-built ProfilingReport,
            symmetric to file_a_profiling_report, or None for a
            single-file run. Defaults to None.
        file_b_trait_cards: File B's already-built
            Mapping[str, TraitCard], symmetric to file_a_trait_cards, or
            None for a single-file run. Defaults to None.
        comparison: The already-computed ComparisonReport for this run
            (e.g. the return value of comparison_use_case.run_comparison()),
            or None for a single-file run. Defaults to None.

    Returns:
        One PhenoPredReport combining the supplied arguments exactly as
        given.

    Raises:
        ValueError: Propagated unchanged from PhenoPredReport's own
            __post_init__ if file_b_profiling_report,
            file_b_trait_cards, and comparison are not either all
            present or all None together.
    """
    return PhenoPredReport(
        file_a_profiling_report=file_a_profiling_report,
        file_a_trait_cards=file_a_trait_cards,
        file_b_profiling_report=file_b_profiling_report,
        file_b_trait_cards=file_b_trait_cards,
        comparison=comparison,
    )