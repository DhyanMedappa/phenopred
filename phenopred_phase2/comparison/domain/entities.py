# phenopred_phase2/comparison/domain/entities.py
"""Comparison Engine domain entities.

Per the approved Comparison Engine Final Design Specification, this
module is the designated home for ConcordanceResult, IdentityLikelihood,
TraitComparison, and ComparisonReport -- named in the Phase 2 Blueprint's
own Section 6 folder structure and specified field-by-field in the
Final Design Specification and the subsequent scientific correctness
review.

Following the identical, already-established pattern used throughout
this codebase (TraitPrediction, TraitDefinition, SNPRecord, DataRow):
`@dataclass(frozen=True, slots=True)`, structural-only validation in
`__post_init__` where a genuine invariant exists, no biological
interpretation, no reporting prose, and no computation performed by
the entities themselves -- every value here is computed elsewhere
(concordance_calculator.py, identity_heuristic.py, trait_diff.py) and
carried through unaltered, mirroring TraitPrediction's identical
"carries only facts already produced" discipline.

Two typed enums (ConcordanceCategory, IdentityLikelihoodCategory,
TraitAgreement) follow this codebase's consistent preference for typed
vocabularies over free-form strings, exactly as GenotypeCallKind,
PredictionStatus, and ConfidenceLevel already establish.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from phenopred_phase2.traits.domain.entities import TraitPrediction


class ConcordanceCategory(Enum):
    """The four mutually-exclusive per-RSID genotype-pair
    classifications the Comparison Engine can produce, per the
    Blueprint's own Section 10.4 four-way classification and the
    subsequent scientific correctness review's final, corrected
    decision table.
    """

    SNP_MATCH = "snp_match"
    SNP_MISMATCH = "snp_mismatch"
    STRUCTURAL_MISMATCH = "structural_mismatch"
    NO_CALL = "no_call"


@dataclass(frozen=True, slots=True)
class ConcordanceResult:
    """The aggregate, genome-wide per-RSID concordance outcome between
    two files, per Blueprint Section 10.4.

    This is a purely descriptive record of already-computed counts --
    it performs no classification of its own (that is
    concordance_calculator.py's exclusive responsibility) and carries
    no qualitative interpretation of what the resulting percentage
    means (that is IdentityLikelihood's exclusive responsibility).

    Attributes:
        total_shared_rsids: The count of RSIDs present in both files'
            GenotypeIndex instances -- the denominator for
            agreement_percentage.
        shared_snp_count: RSIDs classified ConcordanceCategory.SNP_MATCH.
        conflicting_snp_count: RSIDs classified
            ConcordanceCategory.SNP_MISMATCH.
        missing_or_no_call_count: RSIDs classified
            ConcordanceCategory.NO_CALL (including the corrected
            treatment of UNRECOGNIZED calls as non-comparable, per the
            scientific correctness review).
        structural_mismatch_count: RSIDs classified
            ConcordanceCategory.STRUCTURAL_MISMATCH.
        agreement_percentage: shared_snp_count / total_shared_rsids,
            expressed as a percentage (0.0-100.0); 0.0 when
            total_shared_rsids is 0.
    """

    total_shared_rsids: int
    shared_snp_count: int
    conflicting_snp_count: int
    missing_or_no_call_count: int
    structural_mismatch_count: int
    agreement_percentage: float

    def __post_init__(self) -> None:
        """Enforce the two structural invariants named for this entity:
        every count must be non-negative, and the four category counts
        must sum to exactly total_shared_rsids. Mirrors DataRow's and
        SNPRecord's identical "enforce only the named, structural
        invariant" discipline -- no biological correctness check is
        ever performed here.

        Raises:
            ValueError: If any count is negative, or if the four
                category counts do not sum to total_shared_rsids.
        """
        for field_name in (
            "total_shared_rsids",
            "shared_snp_count",
            "conflicting_snp_count",
            "missing_or_no_call_count",
            "structural_mismatch_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(
                    f"ConcordanceResult.{field_name} must be "
                    f"non-negative, got {getattr(self, field_name)!r}"
                )

        computed_total = (
            self.shared_snp_count
            + self.conflicting_snp_count
            + self.missing_or_no_call_count
            + self.structural_mismatch_count
        )
        if computed_total != self.total_shared_rsids:
            raise ValueError(
                "ConcordanceResult's four category counts "
                f"(sum={computed_total}) must equal total_shared_rsids "
                f"({self.total_shared_rsids})."
            )


class IdentityLikelihoodCategory(Enum):
    """The four qualitative concordance-rate bands the Comparison
    Engine's identity heuristic can produce, per Blueprint Section 10.3
    and the approved Final Design Specification's Decision 3. Each
    label is deliberately phrased as a rate observation, never an
    identity claim -- see identity_heuristic.py for the full,
    responsible framing of each category.
    """

    VERY_HIGH_CONCORDANCE = "very_high_concordance"
    HIGH_CONCORDANCE = "high_concordance"
    REDUCED_CONCORDANCE = "reduced_concordance"
    LOW_CONCORDANCE = "low_concordance"


@dataclass(frozen=True, slots=True)
class IdentityLikelihood:
    """A structured, qualitative interpretation of a ConcordanceResult,
    per Blueprint Section 10.1/10.3.

    This entity never claims identity verification and never performs
    IBD/IBS analysis -- it carries only a qualitative category and a
    stable reference to the required methodology caveat. The actual
    caveat sentence and any rendered prose are the later, separate
    responsibility of the reporting layer, mirroring exactly how
    TraitPrediction.confidence is a bare enum value, never a rendered
    phrase.

    Attributes:
        concordance_percentage: Carried through from the source
            ConcordanceResult.agreement_percentage, for standalone
            traceability independent of any ConcordanceResult lookup.
        category: The qualitative concordance band (see
            IdentityLikelihoodCategory).
        methodology_caveat_key: A fixed, stable reference key the
            future reporting layer looks up to render the actual
            required IBD/IBS caveat sentence -- never the sentence
            text itself. Always populated; no code path produces an
            IdentityLikelihood without one.
    """

    concordance_percentage: float
    category: IdentityLikelihoodCategory
    methodology_caveat_key: str

    def __post_init__(self) -> None:
        """Enforce the sole invariant named for this entity:
        methodology_caveat_key must be non-empty after stripping
        whitespace, mirroring SNPRecord's and TraitDefinition's
        identical non-empty-field discipline. This guarantees the
        required scientific caveat reference can never be silently
        omitted.

        Raises:
            ValueError: If methodology_caveat_key is empty or
                whitespace-only.
        """
        if not self.methodology_caveat_key.strip():
            raise ValueError(
                "IdentityLikelihood.methodology_caveat_key must be "
                f"non-empty, got {self.methodology_caveat_key!r}"
            )


class TraitAgreement(Enum):
    """The four mutually-exclusive trait-level comparison outcomes
    trait_diff.py can produce for one trait_id across two files.
    """

    AGREE = "agree"
    DISAGREE = "disagree"
    INSUFFICIENT_DATA = "insufficient_data"
    MISSING_TRAIT = "missing_trait"


@dataclass(frozen=True, slots=True)
class TraitComparison:
    """A single, immutable trait-level comparison outcome for one
    trait_id across two files.

    Carries both source TraitPredictions unaltered -- this is
    deliberate, not incidental: since each TraitPrediction already
    carries observed_genotypes and supporting_snps, this entity alone
    already supplies every piece of structured evidence a future
    reporting layer needs to explain *why* two predictions differ,
    with no additional field, computation, or English explanation
    generated here or anywhere in the Comparison Engine.

    Attributes:
        trait_id: The trait this comparison is for.
        prediction_a: File A's TraitPrediction for this trait_id, or
            None if this trait_id was absent from file A's prediction
            mapping (contributes to agreement=MISSING_TRAIT).
        prediction_b: File B's TraitPrediction for this trait_id, or
            None, symmetric to prediction_a.
        agreement: The resulting TraitAgreement classification.
    """

    trait_id: str
    prediction_a: TraitPrediction | None
    prediction_b: TraitPrediction | None
    agreement: TraitAgreement


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    """The single, per-comparison-run aggregate root, produced by
    comparison_use_case.py from three already-computed pieces.

    Mirrors ProfilingReport's and TraitPrediction's identical "plain,
    immutable carrier of already-resolved values" design -- this entity
    performs no aggregation, selection, or computation of its own.

    Attributes:
        concordance: The genome-wide ConcordanceResult.
        identity_likelihood: The qualitative IdentityLikelihood derived
            from concordance.
        trait_comparisons: Every trait_id's TraitComparison, keyed by
            trait_id.
    """

    concordance: ConcordanceResult
    identity_likelihood: IdentityLikelihood
    trait_comparisons: Mapping[str, TraitComparison]
