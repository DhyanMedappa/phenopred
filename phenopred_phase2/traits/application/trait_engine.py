# phenopred_phase2/traits/application/trait_engine.py
"""Phase 2 Trait Engine -- orchestration only.

Per the approved TraitEngine architecture, this module provides the one
remaining piece connecting the already-complete, already-tested Trait
Contract Layer: a single, registry-driven loop that resolves each
registered trait's model and executes it against a specific file's
genotype data.

TraitEngine is a plain, dependency-injected class -- no shared base
class, no framework, no new Protocol:

- It receives its two static configuration dependencies explicitly, at
  construction time: a trait_id-keyed Mapping[str, TraitDefinition] and
  a trait_id-keyed Mapping[str, TraitModel]. It never imports
  TRAIT_REGISTRY or TRAIT_MODEL_REGISTRY itself, and it never imports
  any concrete TraitModel implementation (LactasePersistenceModel,
  EarwaxTypeModel, ACTN3Model, BitterTasteModel, EyeColourModel, or any
  future one) -- this is what keeps the engine trait-agnostic: adding a
  6th trait requires only a new TraitDefinition entry and a new
  trait_id -> TraitModel binding, never an edit to this file.
- A specific file's genotype data (a GenotypeIndex, or anything
  exposing the same public .get(rsid) -> GenotypeCall | None interface)
  is supplied separately, per run() call -- the static registries
  represent application configuration, while the genotype source
  represents one specific genome input, and the two have different
  lifetimes.
- It touches GenotypeIndex only through its existing public .get()
  method -- it never parses a file, never touches a DataRow, and never
  touches a ColumnLayout.
- It performs no biological interpretation, no confidence calculation,
  no reporting/UI formatting, and no comparison logic -- it only
  resolves, slices, executes, and collects.

Per the project's "represent data conditions, do not raise
unnecessarily" philosophy, already established identically across
GenotypeIndex and every TraitModel:

- A trait present in the trait-definition mapping but absent from the
  model-binding mapping is silently skipped -- no exception, no
  fabricated TraitPrediction. This is a legitimate, expected
  "not yet implemented" condition (mirroring the current, real state of
  any optional trait that has a TraitDefinition but no TraitModel yet),
  not a bug.
- A required RSID absent from the genotype source is never checked or
  special-cased here -- GenotypeIndex.get() already returns None for an
  absent RSID, and that absence is passed straight into the
  genotype_calls mapping exactly as interfaces.py already documents
  ("simply absent as a key"). Whether that yields
  PredictionStatus.INSUFFICIENT_DATA is entirely the model's own
  decision -- duplicating that judgment here would violate the
  boundary that keeps biological interpretation inside each TraitModel.
- A TraitPrediction with status=INSUFFICIENT_DATA is collected
  unchanged, exactly like a PREDICTED one -- INSUFFICIENT_DATA is data,
  never an error.
- An unexpected exception raised by a conforming TraitModel.predict()
  implementation is never caught here -- every model's own frozen
  contract already forbids raising for any external, per-file
  condition, so an exception surfacing from predict() indicates a
  genuine defect (a bug in that model, or a static-data authoring
  mismatch), not a data condition to represent. This mirrors the
  existing, explicit precedent already stated in every trait model's
  own source comments regarding a missing SNP_REGISTRY entry.

See the approved TraitEngine architecture review for the complete
rationale this module implements. No entities.py, interfaces.py,
genotype_index.py, snp_registry.py, trait_registry.py,
trait_model_registry.py, or trait model file is modified by this
module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from phenopred_phase2.traits.domain.entities import (
    GenotypeCall,
    TraitDefinition,
    TraitPrediction,
)
from phenopred_phase2.traits.domain.interfaces import TraitModel


class _GenotypeSource(Protocol):
    """The only capability TraitEngine requires from a genotype source
    for one file: a single, RSID-keyed lookup.

    This is intentionally the exact, already-existing public surface of
    GenotypeIndex (its .get(rsid) method) -- restated here as a narrow,
    local Protocol only so TraitEngine's own dependency is expressed as
    a capability, not as a concrete class import. This is not a new
    abstraction layered over GenotypeIndex; it is the smallest possible
    structural description of the one method TraitEngine actually
    calls, allowing tests to supply a plain fake object exposing just
    this one method, exactly as this project's existing tests already
    do for TraitModel via _FakeSingleSnpTraitModel.
    """

    def get(self, rsid: str) -> GenotypeCall | None:
        ...


class TraitEngine:
    """Registry-driven orchestrator: resolves and executes each
    registered trait's model against one file's genotype data.

    A plain, independent class -- not a shared base class, not a
    framework, not a Protocol implementation of its own. Immutable
    after construction: both static configuration mappings are stored
    exactly as given and never mutated.
    """

    def __init__(
        self,
        trait_registry: Mapping[str, TraitDefinition],
        trait_model_registry: Mapping[str, TraitModel],
    ) -> None:
        """Configure this engine with its two static dependencies.

        Args:
            trait_registry: The trait_id-keyed TraitDefinition mapping
                to iterate (e.g. TRAIT_REGISTRY, or any equivalent
                Mapping -- this engine never imports TRAIT_REGISTRY
                itself). Represents application-wide, static trait
                configuration.
            trait_model_registry: The trait_id-keyed TraitModel mapping
                used to resolve each trait's model (e.g.
                TRAIT_MODEL_REGISTRY, or any equivalent Mapping -- this
                engine never imports TRAIT_MODEL_REGISTRY itself, and
                never imports any concrete TraitModel implementation).
                Represents application-wide, static model configuration.
        """
        self._trait_registry = trait_registry
        self._trait_model_registry = trait_model_registry

    def run(self, genotype_source: _GenotypeSource) -> Mapping[str, TraitPrediction]:
        """Execute every resolvable registered trait against one
        file's genotype data.

        Args:
            genotype_source: This specific file's already-resolved
                genotype lookup (a GenotypeIndex, or anything exposing
                the same public .get(rsid) -> GenotypeCall | None
                interface). Supplied per call, since it represents one
                specific genome input, not static configuration.
                Consulted only through .get() -- no file parsing, no
                DataRow access, no ColumnLayout access occurs here or
                anywhere in this class.

        Returns:
            A trait_id-keyed mapping of TraitPrediction, one entry per
            trait in trait_registry that has a corresponding model
            in trait_model_registry, in trait_registry's own
            iteration order. A trait_id present in trait_registry but
            absent from trait_model_registry contributes no entry --
            never an exception, never a fabricated prediction. Any
            TraitPrediction returned by a model -- PREDICTED or
            INSUFFICIENT_DATA -- is collected unchanged.
        """
        predictions: dict[str, TraitPrediction] = {}

        for trait_id, trait_definition in self._trait_registry.items():
            model = self._trait_model_registry.get(trait_id)
            if model is None:
                # No TraitModel bound for this trait_id yet: a
                # legitimate, expected "not yet implemented" condition,
                # never an exception, never a fabricated prediction.
                continue

            genotype_calls: dict[str, GenotypeCall] = {}
            for rsid in trait_definition.required_rsids:
                call = genotype_source.get(rsid)
                if call is not None:
                    genotype_calls[rsid] = call
                # An absent rsid simply contributes no key -- mirroring
                # GenotypeIndex.get()'s own None-for-absent convention,
                # projected onto this mapping, exactly as interfaces.py
                # documents. Never special-cased here; the model's own
                # predict() implementation decides what an absent
                # required rsid means for its own prediction.

            predictions[trait_id] = model.predict(genotype_calls)

        return predictions
