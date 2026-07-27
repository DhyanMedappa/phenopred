# phenopred_phase2/traits/domain/trait_model_registry.py
"""Phase 2 static trait model registry -- resolution only.

Per the Trait Model Resolution Architecture review, this module
provides the one missing binding the Trait Contract Layer deliberately
left out of TraitDefinition/TRAIT_REGISTRY: a closed, static, trait_id-
keyed lookup of the concrete TraitModel instance that executes each
trait. It follows the identical design philosophy already frozen for
SNP Registry (build_registry/SNP_REGISTRY) and Trait Registry
(build_trait_registry/TRAIT_REGISTRY):

- build_trait_model_registry() is a pure function, exposed (not
  private) specifically so its duplicate-detection behavior can be
  exercised directly in tests, without needing to corrupt the real
  TRAIT_MODEL_REGISTRY constant -- mirroring build_registry's and
  build_trait_registry's identical exposure rationale.
- A duplicate trait_id across bindings raises ValueError at build time
  -- a developer-authored static-data defect, never a runtime condition
  to silently resolve, mirroring build_registry's and
  build_trait_registry's identical duplicate-key handling.
- TRAIT_MODEL_REGISTRY is an immutable MappingProxyType; runtime lookup
  of an unknown trait_id returns None and never raises, mirroring
  SNP_REGISTRY.get()'s and TRAIT_REGISTRY.get()'s identical convention.

Scope boundary (frozen by the Trait Model Resolution Architecture
review): this module answers exactly one question -- "given a trait_id,
which TraitModel instance executes it?" -- and nothing else:

- It stores no TraitDefinition data and duplicates no TRAIT_REGISTRY
  metadata (no name, no required_rsids, no evidence_refs). That
  metadata remains solely owned by trait_registry.py.
- It has no knowledge that GenotypeIndex, DataRow, or any file-level
  object exists.
- It never calls predict() and never executes a model -- it only
  constructs and stores instances for later resolution. Execution is a
  separate, later concern owned by the future TraitEngine.
- It contains no biological interpretation, no confidence logic, and no
  reporting/presentation content of any kind.
- It stores no reference to itself inside TraitDefinition or
  TRAIT_REGISTRY -- per the Trait Contract Layer's explicit, frozen
  prohibition on TraitDefinition carrying a model reference, this is a
  separate, sibling static table, not a merge into an existing one.

Currently holds the lactase persistence, earwax type, ACTN3, bitter
taste, and eye colour bindings, matching the five trait_ids already
populated in TRAIT_REGISTRY. Any optional trait (e.g. ALDH2) remains
unbound until its own concrete model is authored and registered here.

See the Trait Model Resolution Architecture review for the complete
rationale this module implements. No entities.py, interfaces.py,
snp_registry.py, trait_registry.py, or GenotypeIndex file is modified
by this module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from phenopred_phase2.traits.domain.interfaces import TraitModel
from phenopred_phase2.traits.domain.models.actn3_model import ACTN3Model
from phenopred_phase2.traits.domain.models.bitter_taste_model import (
    BitterTasteModel,
)
from phenopred_phase2.traits.domain.models.earwax_type_model import (
    EarwaxTypeModel,
)
from phenopred_phase2.traits.domain.models.eye_colour_model import EyeColourModel
from phenopred_phase2.traits.domain.models.lactase_persistence_model import (
    LactasePersistenceModel,
)


def build_trait_model_registry(
    bindings: Sequence[tuple[str, TraitModel]],
) -> Mapping[str, TraitModel]:
    """Build an immutable, trait_id-keyed mapping from `bindings`.

    Exposed as a plain, public function (not folded silently into
    module-load code) specifically so its duplicate-detection behavior
    can be exercised directly in tests, without needing to corrupt the
    real TRAIT_MODEL_REGISTRY constant -- mirroring build_registry's and
    build_trait_registry's identical rationale in the SNP Registry and
    Trait Registry modules.

    Args:
        bindings: The static (trait_id, TraitModel instance) pairs to
            index by trait_id.

    Returns:
        An immutable mapping (a MappingProxyType) from trait_id to
        TraitModel instance, with one entry per pair in `bindings`.

    Raises:
        ValueError: If two pairs in `bindings` share the same trait_id.
            A duplicate trait_id in developer-authored static data is
            unambiguously a defect in that data -- never a legitimate
            runtime condition to silently resolve, mirroring
            build_registry's and build_trait_registry's identical
            duplicate-key handling.
    """
    registry: dict[str, TraitModel] = {}
    for trait_id, model in bindings:
        if trait_id in registry:
            raise ValueError(
                f"Duplicate trait_id {trait_id!r} in trait model registry "
                "static data; each trait_id must be bound exactly once."
            )
        registry[trait_id] = model

    return MappingProxyType(registry)


_BINDINGS: tuple[tuple[str, TraitModel], ...] = (
    ("lactase_persistence", LactasePersistenceModel()),
    ("earwax_type", EarwaxTypeModel()),
    ("actn3", ACTN3Model()),
    ("bitter_taste", BitterTasteModel()),
    ("eye_colour", EyeColourModel()),
)
"""Populated incrementally as each concrete TraitModel is authored and
registered, mirroring TRAIT_REGISTRY's own incremental-population
convention. Currently holds the five trait_ids already present in
TRAIT_REGISTRY. Any optional trait remains unbound until its own
concrete model is authored.
"""

TRAIT_MODEL_REGISTRY: Mapping[str, TraitModel] = build_trait_model_registry(
    _BINDINGS
)
