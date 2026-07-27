# phenopred_phase2/traits/reporting/trait_card_builder.py
"""Phase 2 Trait Card reporting layer -- assembly only.

Per the Phase 2 Scientific Validation Strategy (Section 11), a dedicated
validation-layer class hierarchy was explicitly considered and rejected
as unnecessary: "the flow requested (prediction -> scientific reference
-> observed genotype -> interpretation -> confidence -> limitations) is
fully satisfied by defining TraitCard as a fixed-schema, mandatory-field
value object... assembled by the existing trait_card_builder.py. This
mirrors the same pattern Architecture V1 already uses for Finding and
Profile."

This module is that assembler, and nothing else:

- It performs no prediction logic, no genotype interpretation, and no
  biological reasoning of any kind -- every fact a TraitCard carries was
  already computed by TraitEngine/TraitModel/SNP_REGISTRY before this
  module ever sees it. This module only pairs an already-computed
  TraitDefinition with its already-computed TraitPrediction and wraps
  them in one TraitCard, exactly mirroring composition.py's own
  "construction and wiring only" role for the trait pipeline, and
  report_builder.py's role in Architecture V1 for Finding/Profile.
- It never imports TraitEngine, GenotypeIndex, or SNP_REGISTRY directly
  -- a TraitPrediction's own supporting_snps mapping already carries
  every SNPRecord a model consulted (per entities.py's own
  documentation), so this module needs nothing beyond the
  TraitDefinition and TraitPrediction it is given.
- It introduces no new scientific claim, no new interpretation text, and
  no new caveat prose -- the only new concept it adds beyond what
  TraitDefinition/TraitPrediction already carry is a small, fixed set of
  stable limitation *reference keys* (never rendered sentences),
  mirroring identity_heuristic.py's identical
  METHODOLOGY_CAVEAT_KEY pattern exactly. The actual caveat sentence
  each key refers to remains a later, separate reporting-layer concern
  (the future combined JSON report / Streamlit app), never fabricated
  here.
- A trait_id mismatch between a TraitDefinition and the TraitPrediction
  it is paired with, or a trait_id present in a predictions mapping but
  absent from the supplied trait registry, is a construction-time
  caller defect -- these can only arise from mis-wiring the two inputs
  this module is given, never from any external, per-file data
  condition -- so both are raised as ValueError, never silently
  resolved or represented as data. This mirrors build_registry's and
  build_trait_registry's identical "developer-authored defect, not a
  runtime condition" precedent.

See the Phase 2 Final Architecture Blueprint, Section 11 (Scientific
Validation Strategy) for the complete, authoritative rationale this
module implements. No entities.py, interfaces.py, genotype_index.py,
snp_registry.py, trait_registry.py, trait_model_registry.py, trait
model file, or trait_engine.py is modified by this module.
"""

from __future__ import annotations

from collections.abc import Mapping

from phenopred_phase2.traits.domain.entities import (
    TraitCard,
    TraitDefinition,
    TraitPrediction,
)

# ---------------------------------------------------------------------------
# Standing limitation-key constant(s) -- stable references only, never
# rendered prose, mirroring identity_heuristic.py's own
# METHODOLOGY_CAVEAT_KEY pattern exactly. The future reporting layer
# looks this key up to render the actual required sentence; this module
# never renders it itself.
#
# This is the one standing caveat the Phase 2 blueprint requires on
# every card regardless of confidence tier ("most of these associations
# were established primarily in European-ancestry cohorts; state this
# on every card regardless of confidence tier") that is not already
# expressed as data anywhere in TraitDefinition or TraitPrediction.
# Every trait-specific caveat that already exists as data (e.g. the
# eye-colour simplified-scoring caveat, the bitter-taste unphased-
# diplotype caveat) already lives, verbatim, in
# TraitDefinition.evidence_refs and is carried through unmodified via
# trait_evidence_refs -- this module does not duplicate or re-derive it.
# ---------------------------------------------------------------------------

ANCESTRY_GENERALIZABILITY_CAVEAT_KEY = "trait_card_ancestry_generalizability"
"""Stable reference key for the standing ancestry-generalizability
caveat. Included in every TraitCard's limitation_keys, regardless of
trait or confidence tier. The rendered sentence this key refers to is a
later, separate reporting-layer concern -- never fabricated here.
"""

_STANDING_LIMITATION_KEYS: tuple[str, ...] = (ANCESTRY_GENERALIZABILITY_CAVEAT_KEY,)


def build_trait_card(
    trait_definition: TraitDefinition,
    trait_prediction: TraitPrediction,
) -> TraitCard:
    """Assemble one TraitCard from one already-computed TraitDefinition
    and its corresponding, already-computed TraitPrediction.

    Args:
        trait_definition: The static TraitDefinition for this trait
            (e.g. a TRAIT_REGISTRY entry). Consumed only for its
            trait_id, name, and evidence_refs -- never re-validated
            biologically here.
        trait_prediction: The already-computed TraitPrediction for the
            same trait_id (e.g. one entry of the Mapping returned by
            TraitEngine.run() / run_trait_pipeline()). Embedded whole
            and unaltered into the resulting TraitCard.

    Returns:
        One TraitCard pairing trait_definition's static identity/
        evidence with trait_prediction's already-computed result, plus
        this module's fixed, standing limitation-key(s).

    Raises:
        ValueError: If trait_definition.trait_id does not match
            trait_prediction.trait_id -- a construction-time caller
            defect (the two inputs were paired incorrectly), never a
            data condition to silently resolve.
    """
    if trait_definition.trait_id != trait_prediction.trait_id:
        raise ValueError(
            "build_trait_card: trait_definition.trait_id "
            f"({trait_definition.trait_id!r}) does not match "
            f"trait_prediction.trait_id ({trait_prediction.trait_id!r}); "
            "the caller must pair a TraitDefinition with the "
            "TraitPrediction for that same trait_id."
        )

    return TraitCard(
        trait_id=trait_definition.trait_id,
        trait_name=trait_definition.name,
        trait_evidence_refs=trait_definition.evidence_refs,
        prediction=trait_prediction,
        limitation_keys=_STANDING_LIMITATION_KEYS,
    )


def build_trait_cards(
    trait_registry: Mapping[str, TraitDefinition],
    predictions: Mapping[str, TraitPrediction],
) -> Mapping[str, TraitCard]:
    """Assemble one TraitCard per entry in `predictions`.

    Mirrors TraitEngine.run()'s own registry-driven-loop shape: this
    function never imports TRAIT_REGISTRY itself and never imports any
    concrete TraitModel -- both static configuration (trait_registry)
    and the specific, already-computed result set (predictions) are
    supplied by the caller, keeping this function trait-agnostic.

    Args:
        trait_registry: The trait_id-keyed TraitDefinition mapping to
            look up each prediction's static identity/evidence in (e.g.
            TRAIT_REGISTRY, or any equivalent Mapping).
        predictions: The trait_id-keyed TraitPrediction mapping to build
            cards for (e.g. the return value of
            composition.run_trait_pipeline() / TraitEngine.run()). This
            mapping's own keys drive iteration -- a trait_id is only
            ever given a card if a prediction for it actually exists,
            mirroring TraitEngine's own "only ever produce output for
            what was actually computed" discipline.

    Returns:
        A trait_id-keyed mapping of TraitCard, one entry per entry in
        `predictions`, in `predictions`' own iteration order.

    Raises:
        ValueError: If a trait_id present in `predictions` has no
            corresponding entry in `trait_registry`. Under a correctly
            wired system this cannot occur -- every TraitPrediction
            TraitEngine ever produces originates from iterating that
            same trait_registry (see trait_engine.py) -- so this
            indicates a genuine caller defect (mismatched registry/
            predictions pair), never an external, per-file data
            condition to represent silently.
    """
    trait_cards: dict[str, TraitCard] = {}

    for trait_id, trait_prediction in predictions.items():
        trait_definition = trait_registry.get(trait_id)
        if trait_definition is None:
            raise ValueError(
                f"build_trait_cards: trait_id {trait_id!r} is present in "
                "predictions but has no corresponding entry in "
                "trait_registry; this indicates trait_registry and "
                "predictions were not produced from the same "
                "trait_registry."
            )

        trait_cards[trait_id] = build_trait_card(trait_definition, trait_prediction)

    return trait_cards