# phenopred_phase2/reporting/entities.py
"""Phase 2 Combined Report Assembly -- reporting-layer aggregate entity.

Per the approved Combined Report Assembly milestone (following the Phase
2 Final Architecture Blueprint, Section 14, "Reporting Design"), this
module defines PhenoPredReport: the single, per-run aggregate that
combines already-computed output from three independently-built
pipelines --

    - Architecture V1's per-file profiling pipeline (ProfilingReport),
    - Phase 2's trait pipeline (Mapping[str, TraitCard]), and
    - Phase 2's optional Comparison Engine (ComparisonReport) --

into one object, ready to be serialized and downloaded. This mirrors
ComparisonReport's own established design exactly: "these entities
carry only facts already produced by [other components] and carried
through unaltered" -- PhenoPredReport performs no aggregation logic,
selection, or computation of its own; it is a plain, immutable carrier.

Placement: this is a Phase 2 *reporting-layer* concern, not a new
domain layer -- per the approved package structure, this file lives at
phenopred_phase2/reporting/entities.py (a sibling to traits/ and
comparison/), not under a new phenopred_phase2/reporting/domain/
package. This mirrors how ComparisonReport (comparison/domain/
entities.py) already composes ConcordanceResult + IdentityLikelihood +
TraitComparison without modifying any of them -- PhenoPredReport applies
the identical composition-over-modification pattern one level higher,
across all of Phase 1 and Phase 2's already-computed outputs.

Composition, never modification: PhenoPredReport embeds V1's
ProfilingReport whole and unaltered (per Architecture V1 Section 5's
"no file inside phenopred/... is modified" and the identically-frozen
Phase 2 Blueprint Section 5 dependency rule). No field, method, or
behavior of ProfilingReport is changed, subclassed, or reimplemented
anywhere in this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from phenopred.domain.entities import ProfilingReport
from phenopred_phase2.comparison.domain.entities import ComparisonReport
from phenopred_phase2.traits.domain.entities import TraitCard


@dataclass(frozen=True, slots=True)
class PhenoPredReport:
    """The single, immutable, per-run combined report aggregate.

    PhenoPredReport computes nothing. Every value it carries was already
    computed elsewhere before this entity is constructed:

    - file_a_profiling_report / file_b_profiling_report are V1's own
      ProfilingReport instances, produced by V1's already-existing,
      unmodified pipeline (ProfileFileUseCase / ReportBuilder), embedded
      whole and unaltered.
    - file_a_trait_cards / file_b_trait_cards are the
      Mapping[str, TraitCard] already produced by
      trait_card_builder.build_trait_cards(), embedded unaltered.
    - comparison is the ComparisonReport already produced by
      comparison_use_case.run_comparison(), embedded whole and
      unaltered, present only when a second file was supplied.

    This is the same "carry already-computed facts through unaltered"
    discipline already established for TraitCard (which embeds a whole
    TraitPrediction) and ComparisonReport (which embeds a whole
    ConcordanceResult, IdentityLikelihood, and Mapping[str,
    TraitComparison]) -- applied here one aggregation level higher, to
    combine Phase 1 and Phase 2 output into the one object that will
    later be serialized and downloaded.

    PhenoPredReport does not calculate trait predictions, does not run
    TraitEngine or the Comparison Engine, does not interpret genotype
    data, and introduces no new scientific claim, UI formatting, or
    presentation logic of any kind -- it is a thin, additive combination
    of three already-validated aggregates.

    Attributes:
        file_a_profiling_report: File A's already-built ProfilingReport
            (V1's own aggregate), embedded whole and unaltered. Always
            present -- a PhenoPredReport always describes at least one
            file.
        file_a_trait_cards: File A's already-built
            Mapping[str, TraitCard], embedded unaltered. Always
            present, for the same reason as file_a_profiling_report.
        file_b_profiling_report: File B's already-built ProfilingReport,
            embedded whole and unaltered, or None when only one file was
            supplied for this run.
        file_b_trait_cards: File B's already-built
            Mapping[str, TraitCard], embedded unaltered, or None when
            only one file was supplied -- symmetric to
            file_b_profiling_report.
        comparison: The already-computed ComparisonReport for this run,
            embedded whole and unaltered, or None when only one file was
            supplied. The Comparison Engine only ever runs with two
            files (Phase 2 Blueprint Section 4: "only runs with 2
            files"), so comparison's presence is tied to file_b's
            presence, not an independent condition -- enforced in
            __post_init__ below.
    """

    file_a_profiling_report: ProfilingReport
    file_a_trait_cards: Mapping[str, TraitCard]
    file_b_profiling_report: ProfilingReport | None
    file_b_trait_cards: Mapping[str, TraitCard] | None
    comparison: ComparisonReport | None

    def __post_init__(self) -> None:
        """Enforce the sole structural invariant named for this entity:
        file_b_profiling_report, file_b_trait_cards, and comparison must
        either all be present together or all be absent (None) together
        -- mirroring this codebase's consistent "structural-only, no
        biological judgment" validation discipline (TraitDefinition,
        SNPRecord, ConcordanceResult, IdentityLikelihood, TraitCard).

        A PhenoPredReport describing only one file must not carry a
        partial, inconsistent file-B/comparison state (e.g. a file_b
        profiling report present with no corresponding trait cards, or
        a comparison present with no file_b data at all) -- any such
        state is a construction-time caller defect, not a legitimate
        one-file or two-file run, and is rejected here rather than
        silently accepted.

        Raises:
            ValueError: If exactly one or two (but not all three or
                none) of file_b_profiling_report, file_b_trait_cards,
                and comparison are None.
        """
        file_b_fields_present = (
            self.file_b_profiling_report is not None,
            self.file_b_trait_cards is not None,
            self.comparison is not None,
        )
        if len(set(file_b_fields_present)) != 1:
            raise ValueError(
                "PhenoPredReport requires file_b_profiling_report, "
                "file_b_trait_cards, and comparison to be either all "
                "present or all None together (got "
                f"file_b_profiling_report={self.file_b_profiling_report is not None}, "
                f"file_b_trait_cards={self.file_b_trait_cards is not None}, "
                f"comparison={self.comparison is not None}); a partial "
                "file-B/comparison state is not a valid one-file or "
                "two-file run."
            )