# phenopred_phase2/reporting/report_serializer.py
"""Phase 2 Combined Report Assembly -- serialization extension.

Per the approved Combined Report Assembly milestone, this module
provides Phase2JsonReportSerializer: a minimal, additive extension of
V1's existing phenopred.infrastructure.io.report_writer.JsonReportSerializer,
reusing all of its existing, already-correct, already-tested behavior
(dataclass -> dict conversion by declared field order, Path -> string,
tuple/list -> array, dict -> object) without modifying
report_writer.py and without duplicating any of that logic.

Two, and only two, capabilities are added here, because both were
empirically confirmed missing from the base class before this module
was written:

1. Enum support. Every Phase 2 dataclass introduced since TraitCard
   carries at least one plain (non-str-subclassed) Enum field
   (TraitPrediction.status: PredictionStatus,
   TraitPrediction.confidence: ConfidenceLevel,
   GenotypeCall.kind: GenotypeCallKind,
   ConcordanceResult-adjacent ConcordanceCategory,
   IdentityLikelihood.category: IdentityLikelihoodCategory,
   TraitComparison.agreement: TraitAgreement). The base class's
   _to_jsonable() has no branch for Enum instances, so passing any
   Phase 2 dataclass containing one directly to the unmodified
   JsonReportSerializer raises
   "TypeError: Object of type <EnumClass> is not JSON serializable"
   -- confirmed directly before this module was written, not assumed.
   This class adds exactly one new branch: an Enum member serializes to
   its own `.value` (e.g. PredictionStatus.PREDICTED -> "predicted"),
   the same string vocabulary already fixed by each Enum's own
   definition -- no new vocabulary or interpretation is introduced.

2. PhenoPredReport's specific top-level JSON shape. Per Phase 2
   Blueprint Section 14 ("extends V1's existing ReportSerializer output
   shape -- adds a `traits` section and, when a second file is present,
   a `comparison` section -- rather than inventing a parallel format"),
   the approved output shape merges each file's V1 ProfilingReport
   fields with a sibling "traits" key at the same nesting level (see
   the approved JSON structure), rather than nesting
   file_a_profiling_report/file_a_trait_cards as two separate,
   differently-named dataclass fields the way PhenoPredReport itself
   stores them. This specific shape cannot be produced by the base
   class's generic, one-dataclass-field-per-key conversion, so this
   class adds one additional branch recognizing PhenoPredReport
   specifically and assembling that approved shape -- delegating every
   nested value's own conversion (the ProfilingReport's own fields, each
   TraitCard's own fields, the ComparisonReport's own fields) back to
   this same class's (Enum-aware) _to_jsonable(), never re-implementing
   any of that nested conversion itself.

No other capability is added. No business logic, scientific
interpretation, or presentation/formatting decision is introduced --
this remains a structural, data-shape-only conversion, exactly like the
base class it extends.

phenopred/infrastructure/io/report_writer.py is imported, read-only, and
never modified by this module.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from phenopred.infrastructure.io.report_writer import JsonReportSerializer
from phenopred_phase2.reporting.entities import PhenoPredReport


class Phase2JsonReportSerializer(JsonReportSerializer):
    """Extends V1's JsonReportSerializer with Enum support and
    PhenoPredReport's approved top-level JSON shape.

    Inherits `serialize()` entirely unmodified from JsonReportSerializer
    -- destination handling, directory creation, and the fixed JSON
    encoding (UTF-8, fixed indentation, no locale-dependent formatting,
    per NFR-3) are all reused as-is. Only `_to_jsonable()` is overridden,
    and even that override delegates to the parent implementation
    (`super()._to_jsonable(value)`) for every value that is not either a
    PhenoPredReport or an Enum member.
    """

    def _to_jsonable(self, value: Any) -> Any:
        """Convert `value` into a JSON-compatible structure.

        Adds exactly two branches ahead of the inherited behavior:

        - A PhenoPredReport is converted into the approved combined
          top-level shape (see _phenopred_report_to_jsonable below).
        - An Enum member is converted to its own `.value`.

        Every other value (dataclasses, Path, tuple/list, dict, and
        JSON-primitive scalars) is handled by the inherited
        JsonReportSerializer._to_jsonable() implementation, unchanged.
        Because Python's attribute lookup resolves `self._to_jsonable`
        to this subclass's override even when invoked from within the
        parent class's own method body, every value nested inside a
        dataclass, tuple, list, or dict -- at any depth -- is still
        correctly given Enum/PhenoPredReport handling by the inherited
        recursive logic; this override does not need to re-implement
        that recursion itself.
        """
        if isinstance(value, PhenoPredReport):
            return self._phenopred_report_to_jsonable(value)
        if isinstance(value, Enum):
            return value.value
        return super()._to_jsonable(value)

    def _phenopred_report_to_jsonable(self, report: PhenoPredReport) -> dict[str, Any]:
        """Assemble PhenoPredReport's approved top-level JSON shape.

        Per Phase 2 Blueprint Section 14, the resulting shape merges
        each file's V1 ProfilingReport fields with a sibling "traits"
        key holding that file's Mapping[str, TraitCard], and adds a
        top-level "comparison" key only when a second file (and
        therefore a ComparisonReport) is present:

            {
                "file_a": {<ProfilingReport's own fields>, "traits": {...}},
                "file_b": {<ProfilingReport's own fields>, "traits": {...}},  # omitted for a one-file run
                "comparison": {...},  # omitted for a one-file run
            }

        This method performs no computation over any nested value's
        content -- every nested conversion (the ProfilingReport's own
        fields, each TraitCard's own fields, the ComparisonReport's own
        fields) is delegated back to `self._to_jsonable()`, reusing the
        exact same recursive, already-correct logic used everywhere
        else in this class.

        Args:
            report: The already-assembled PhenoPredReport to convert.

        Returns:
            A JSON-compatible dict in the shape shown above. "file_b"
            and "comparison" are omitted entirely (never present as
            `None` or an empty object) when `report` describes only one
            file, mirroring PhenoPredReport's own "all present or all
            None together" invariant -- a one-file report never
            fabricates a placeholder file_b/comparison section.
        """
        file_a = dict(self._to_jsonable(report.file_a_profiling_report))
        file_a["traits"] = self._to_jsonable(report.file_a_trait_cards)

        result: dict[str, Any] = {"file_a": file_a}

        if report.file_b_profiling_report is not None:
            file_b = dict(self._to_jsonable(report.file_b_profiling_report))
            file_b["traits"] = self._to_jsonable(report.file_b_trait_cards)
            result["file_b"] = file_b

        if report.comparison is not None:
            result["comparison"] = self._to_jsonable(report.comparison)

        return result