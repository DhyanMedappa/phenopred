# phenopred_phase2/traits/domain/entities.py
"""Phase 2 trait-domain data-carrying entities.

Per the Phase 2 Software Architecture (Section 6), this module is the
designated home for TraitDefinition, GenotypeCall, TraitPrediction,
TraitCard, and ConfidenceLevel.

Two independent groups of entities are currently defined here, per two
separate frozen specifications:

- GenotypeCall / GenotypeCallKind -- required by the frozen GenotypeIndex
  component (see "GenotypeIndex -- Final Design Specification").
- PredictionStatus / ConfidenceLevel / TraitDefinition / TraitPrediction
  -- required by the frozen "Trait Contract Layer -- Frozen Architecture
  Specification v1". These are the shared contract every future
  TraitModel implementation and the future Trait Engine are built
  against; they carry no biological interpretation, no orchestration
  logic, and no reporting/presentation content of their own.

TraitCard is now defined here. It was explicitly out of scope for the
Trait Contract Layer (a later, separate reporting concern), and remains
so in spirit: TraitCard is a plain, immutable value object that carries
already-computed facts (a TraitDefinition's static metadata plus a
TraitPrediction's already-computed result) through to the reporting
layer. It performs no prediction logic, no genotype interpretation, and
introduces no new scientific claim of its own -- assembly is the sole
responsibility of trait_card_builder.py (traits/reporting/), mirroring
exactly how Architecture V1's report_builder.py assembles Finding/Profile
data without computing any of it itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from phenopred_phase2.traits.domain.snp_registry import SNPRecord


class GenotypeCallKind(Enum):
    """The five mutually-exclusive genotype-call classifications
    GenotypeIndex can produce for a single RSID in a single file, per
    the frozen GenotypeIndex Final Design Specification (Sections 5, 8).
    """

    SNP = "snp"
    NO_CALL = "no_call"
    INDEL = "indel"
    HAPLOID = "haploid"
    UNRECOGNIZED = "unrecognized"


@dataclass(frozen=True, slots=True)
class GenotypeCall:
    """A single, immutable, normalized genotype-call result for one RSID
    in one file, produced exclusively by GenotypeIndex.

    This is a purely descriptive record of what GenotypeIndex classified
    -- it carries no biological interpretation beyond the shape-level
    normalization the frozen GenotypeIndex Final Design Specification
    defines (allele-order canonicalization, missing/indel/haploid
    classification). Strand convention, phenotype association, and every
    other biological interpretation are explicitly out of scope here,
    and remain the SNP registry's and Trait Engine's responsibility.

    Attributes:
        kind: Which of the five GenotypeCallKind classifications this
            call represents.
        alleles: The canonical, sorted two-character allele pair (e.g.
            "AG", never "GA" for the same underlying genotype).
            Populated only when kind is SNP; None otherwise.
        allele: The single observed allele character. Populated only
            when kind is HAPLOID; None otherwise.
        raw_value: The original literal value(s) as observed in the
            source row, preserved unaltered for traceability (e.g.
            "A/G" for a two-column-allele row, or the single designated-
            column string for a single-column-genotype row). None only
            when no value could be read at all (an out-of-bounds row or
            an undetermined layout).
    """

    kind: GenotypeCallKind
    alleles: str | None
    allele: str | None
    raw_value: str | None


class PredictionStatus(Enum):
    """Whether a TraitModel was able to produce a phenotype prediction
    for one file, per the frozen Trait Contract Layer specification
    (Section 12, "Error handling philosophy").

    A missing required RSID, a NO_CALL genotype, or an INDEL/
    UNRECOGNIZED call where a SNP genotype was expected are all
    external, per-file data conditions -- never exceptions -- and are
    represented uniformly as INSUFFICIENT_DATA, mirroring GenotypeIndex's
    own "represent as data, never raise" discipline.
    """

    PREDICTED = "predicted"
    INSUFFICIENT_DATA = "insufficient_data"


class ConfidenceLevel(Enum):
    """The shared confidence taxonomy every TraitModel assigns to its
    own prediction. The value is always computed by the TraitModel that
    made the underlying scientific judgment; this type only fixes the
    shared vocabulary, per the frozen Trait Contract Layer specification.
    """

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class TraitDefinition:
    """A single, immutable, static registry entry describing one trait's
    identity and data requirements, per the frozen Trait Contract Layer
    specification.

    This is purely declarative metadata -- it carries no model
    reference, no interpretation logic, and no biological reasoning of
    any kind. The trait_id -> TraitModel instance binding is a separate,
    later concern owned by Phase 2's own composition root (mirroring
    Architecture V1's AD-10: composition root owns wiring, domain data
    does not).

    Attributes:
        trait_id: The unique identifier for this trait, used as the
            TRAIT_REGISTRY lookup key.
        name: The human-readable trait name.
        required_rsids: The RSID(s) this trait's model requires to
            produce a prediction.
        evidence_refs: This trait's own trait-level literature
            citations -- distinct from any SNPRecord.citation, which
            verifies a single SNP's allele-convention resolution, not a
            trait association.
    """

    trait_id: str
    name: str
    required_rsids: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        """Enforce structural validity only: trait_id and name must be
        non-empty after stripping whitespace, and required_rsids must be
        a non-empty tuple. Mirrors SNPRecord.__post_init__'s identical,
        structural-only validation discipline -- no biological
        correctness check, no cross-referencing against any external
        source, is ever performed here.

        Raises:
            ValueError: If trait_id or name is empty/whitespace-only,
                or if required_rsids is empty.
        """
        if not self.trait_id.strip():
            raise ValueError(
                f"TraitDefinition.trait_id must be non-empty, got "
                f"{self.trait_id!r}"
            )
        if not self.name.strip():
            raise ValueError(
                f"TraitDefinition.name must be non-empty, got {self.name!r}"
            )
        if not self.required_rsids:
            raise ValueError(
                "TraitDefinition.required_rsids must be a non-empty tuple, "
                f"got {self.required_rsids!r}"
            )


@dataclass(frozen=True, slots=True)
class TraitPrediction:
    """A single, immutable output of one TraitModel for one file, per
    the frozen Trait Contract Layer specification.

    This carries only facts a model produced or the evidence it
    consulted to reach them -- never reporting prose, explanatory text,
    UI fields, or any other presentation formatting. TraitCard (a later,
    separate reporting concern) is built from this value plus
    TraitDefinition.evidence_refs; it displays these facts, it never
    recomputes them.

    Attributes:
        trait_id: The trait this prediction is for, matching a
            TraitDefinition.trait_id -- present for standalone
            traceability, independent of any registry lookup.
        status: Whether a prediction was actually produced
            (PredictionStatus).
        predicted_phenotype: The predicted phenotype label. Populated
            only when status is PREDICTED; None otherwise.
        confidence: The model-assigned confidence tier. Populated only
            when status is PREDICTED; None otherwise.
        observed_genotypes: The GenotypeCall(s) this model actually had
            available, keyed by RSID -- may be non-empty even when
            status is INSUFFICIENT_DATA, for transparency about what
            partial data was observed.
        supporting_snps: The SNPRecord(s) this model actually consulted,
            keyed by RSID -- empty when status is INSUFFICIENT_DATA.
    """

    trait_id: str
    status: PredictionStatus
    predicted_phenotype: str | None
    confidence: ConfidenceLevel | None
    observed_genotypes: Mapping[str, GenotypeCall]
    supporting_snps: Mapping[str, SNPRecord]

@dataclass(frozen=True, slots=True)
class TraitCard:
    """A single, immutable, reporting-facing record pairing one trait's
    static identity/evidence with its already-computed TraitPrediction,
    per the frozen Trait Contract Layer's own deferred scope and the
    Phase 2 Scientific Validation Strategy (Section 11): "the flow
    requested (prediction -> scientific reference -> observed genotype
    -> interpretation -> confidence -> limitations) is fully satisfied
    by defining TraitCard as a fixed-schema, mandatory-field value
    object... assembled by the existing trait_card_builder.py."

    TraitCard computes nothing. Every fact it carries was already
    computed elsewhere:

    - trait_id/trait_name/trait_evidence_refs come unmodified from a
      TraitDefinition (TRAIT_REGISTRY).
    - The prediction itself -- status, predicted phenotype ("the
      interpretation"), confidence, observed genotypes, and supporting
      SNP evidence ("the scientific reference") -- is the already-
      computed TraitPrediction, embedded whole and unaltered, mirroring
      TraitComparison's identical "carry the source TraitPrediction(s)
      through unaltered" discipline in the Comparison Engine.
    - limitation_keys are stable reference keys only (never rendered
      caveat prose), mirroring IdentityLikelihood.methodology_caveat_key
      exactly: the actual sentence is a later, separate reporting-layer
      concern, never fabricated here.

    TraitCard introduces no new scientific claim, no new interpretation,
    and no biological judgment of any kind -- it is a thin, additive
    pairing of two already-validated value objects, plus a fixed set of
    caveat-reference keys.

    Attributes:
        trait_id: This trait's identifier, matching both
            TraitDefinition.trait_id and prediction.trait_id (enforced
            in __post_init__ as a consistency check between the two
            already-independent inputs this card pairs together).
        trait_name: The human-readable trait name, carried unmodified
            from TraitDefinition.name.
        trait_evidence_refs: This trait's own trait-level literature
            citations, carried unmodified from
            TraitDefinition.evidence_refs -- distinct from any
            SNPRecord.citation already embedded inside
            prediction.supporting_snps.
        prediction: The already-computed TraitPrediction this card
            reports on, embedded whole and unaltered.
        limitation_keys: Stable, non-empty reference key(s) for
            standing scientific caveats that must appear on every card
            regardless of confidence tier (e.g. the ancestry-
            generalizability caveat) -- never rendered prose. Always
            non-empty; no code path produces a TraitCard without at
            least one.
    """

    trait_id: str
    trait_name: str
    trait_evidence_refs: tuple[str, ...]
    prediction: TraitPrediction
    limitation_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        """Enforce only the structural invariants named for this
        entity, mirroring this codebase's consistent "structural-only,
        no biological judgment" validation discipline
        (TraitDefinition, SNPRecord, ConcordanceResult,
        IdentityLikelihood):

        - trait_id and trait_name must be non-empty after stripping
          whitespace.
        - trait_id must match prediction.trait_id -- a defensive
          consistency check between the two independently-supplied
          inputs this card pairs together; a mismatch here is a
          construction-time caller defect (mirroring
          concordance_calculator's own "unreachable configuration is a
          bug, not a data condition" precedent), never a data
          condition to silently resolve.
        - limitation_keys must be a non-empty tuple, structurally
          guaranteeing the Phase 2 requirement that every card carry at
          least its standing scientific caveat reference(s) -- this is
          the "construction-time error, a cheap, existing enforcement
          mechanism" the Scientific Validation Strategy (Section 11)
          explicitly calls for, applied here exactly as it already is
          for IdentityLikelihood.methodology_caveat_key.

        Raises:
            ValueError: If trait_id or trait_name is empty/whitespace-
                only, if trait_id does not match prediction.trait_id,
                or if limitation_keys is empty.
        """
        if not self.trait_id.strip():
            raise ValueError(
                f"TraitCard.trait_id must be non-empty, got {self.trait_id!r}"
            )
        if not self.trait_name.strip():
            raise ValueError(
                f"TraitCard.trait_name must be non-empty, got "
                f"{self.trait_name!r}"
            )
        if self.trait_id != self.prediction.trait_id:
            raise ValueError(
                f"TraitCard.trait_id ({self.trait_id!r}) must match "
                f"TraitCard.prediction.trait_id "
                f"({self.prediction.trait_id!r}); a mismatch indicates "
                "the card was assembled from a TraitDefinition and a "
                "TraitPrediction for two different traits."
            )
        if not self.limitation_keys:
            raise ValueError(
                "TraitCard.limitation_keys must be a non-empty tuple: "
                "every card must carry at least its standing scientific "
                "caveat reference key(s)."
            )