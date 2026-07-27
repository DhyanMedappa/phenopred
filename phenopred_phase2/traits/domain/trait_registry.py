# phenopred_phase2/traits/domain/trait_registry.py
"""Phase 2 static trait registry -- structure only.

Per the frozen "Trait Contract Layer -- Frozen Architecture Specification
v1" (Review Point 2), this module provides a metadata-only, trait_id-
keyed lookup of TraitDefinition entries, following the identical design
philosophy already frozen for SNP Registry's build_registry/SNP_REGISTRY:

- build_trait_registry() is a pure function, exposed (not private)
  specifically so its duplicate-detection behavior can be exercised
  directly in tests, mirroring build_registry's own exposure rationale
  exactly.
- A duplicate trait_id across TraitDefinition entries raises ValueError
  at build time -- a developer-authored static-data defect, never a
  runtime condition to silently resolve, mirroring build_registry's
  identical duplicate-rsid handling.
- TRAIT_REGISTRY is an immutable MappingProxyType; runtime lookup of an
  unknown trait_id returns None and never raises, mirroring
  SNP_REGISTRY.get()'s identical convention.

Scope boundary (frozen, Review Point 2): TRAIT_REGISTRY is metadata
only. It stores no model reference and performs no trait_id ->
TraitModel instance binding -- that wiring is a separate, later concern
owned by Phase 2's own composition root, mirroring Architecture V1's
AD-10 (composition root owns wiring; domain data does not).

Per the frozen specification, this module is populated incrementally as
each concrete TraitModel is authored. Currently holds the lactase
persistence, earwax type, ACTN3, bitter taste, and eye colour entries,
matching LactasePersistenceModel, EarwaxTypeModel, ACTN3Model,
BitterTasteModel, and EyeColourModel
(traits/domain/models/lactase_persistence_model.py,
traits/domain/models/earwax_type_model.py,
traits/domain/models/actn3_model.py,
traits/domain/models/bitter_taste_model.py,
traits/domain/models/eye_colour_model.py). Any optional traits remain
unpopulated until their own concrete models are authored.

See "Trait Contract Layer -- Frozen Architecture Specification v1" for
the complete, authoritative contract this module implements. No V1
file, GenotypeIndex file, or SNP Registry file is read, imported beyond
its public entities, or modified by this module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from phenopred_phase2.traits.domain.entities import TraitDefinition


def build_trait_registry(
    definitions: Sequence[TraitDefinition],
) -> Mapping[str, TraitDefinition]:
    """Build an immutable, trait_id-keyed mapping from `definitions`.

    Exposed as a plain, public function (not folded silently into
    module-load code) specifically so its duplicate-detection behavior
    can be exercised directly in tests, without needing to corrupt the
    real TRAIT_REGISTRY constant -- mirroring build_registry's identical
    rationale in the SNP Registry module.

    Args:
        definitions: The static TraitDefinition entries to index by
            trait_id.

    Returns:
        An immutable mapping (a MappingProxyType) from trait_id to
        TraitDefinition, with one entry per definition in `definitions`.

    Raises:
        ValueError: If two definitions in `definitions` share the same
            trait_id. A duplicate trait_id in developer-authored static
            data is unambiguously a defect in that data -- never a
            legitimate runtime condition to silently resolve, mirroring
            build_registry's identical duplicate-rsid handling.
    """
    registry: dict[str, TraitDefinition] = {}
    for definition in definitions:
        if definition.trait_id in registry:
            raise ValueError(
                f"Duplicate trait_id {definition.trait_id!r} in trait "
                "registry static data; each trait_id must be defined "
                "exactly once."
            )
        registry[definition.trait_id] = definition

    return MappingProxyType(registry)


_DEFINITIONS: tuple[TraitDefinition, ...] = (
    TraitDefinition(
        trait_id="lactase_persistence",
        name="Lactase Persistence",
        required_rsids=("rs4988235",),
        evidence_refs=(
            "One of the most replicated single-SNP trait associations "
            "in human genetics (Phase 2 Architecture Blueprint, "
            "Section 8.2).",
        ),
    ),
    TraitDefinition(
        trait_id="earwax_type",
        name="Earwax Type",
        required_rsids=("rs17822931",),
        evidence_refs=(
            "Sourced, confirmed interpretation (Yoshiura et al. 2006 "
            "gene-strand convention, cross-referenced against a "
            "position-matched ClinVar record) (Phase 2 Architecture "
            "Blueprint, Section 8.4).",
        ),
    ),
    TraitDefinition(
        trait_id="actn3",
        name="ACTN3 (Alpha-Actinin-3)",
        required_rsids=("rs1815739",),
        evidence_refs=(
            "Genotype is one minor factor among many in athletic "
            "performance, not a determinant (Phase 2 Architecture "
            "Blueprint, Section 8.3).",
        ),
    ),
    TraitDefinition(
        trait_id="bitter_taste",
        name="Bitter Taste (TAS2R38)",
        required_rsids=("rs713598", "rs1726866", "rs10246939"),
        evidence_refs=(
            "PAV (taster) and AVI (non-taster) are the two common "
            "TAS2R38 haplotypes; PAV is dominant (Phase 2 Architecture "
            "Blueprint, Section 8.5).",
            "Consumer genotype data carries no phase information; a "
            "heterozygous-at-all-three-loci pattern is interpreted as "
            "an inferred PAV/AVI diplotype under the common-haplotype "
            "assumption, not directly observed phase -- an explicit, "
            "labeled approximation, not a hypothesis presented as fact "
            "(Phase 2 Architecture Blueprint, Section 8.5).",
        ),
    ),
    TraitDefinition(
        trait_id="eye_colour",
        name="Eye Colour (IrisPlex)",
        required_rsids=(
            "rs12913832",
            "rs1800407",
            "rs12896399",
            "rs16891982",
            "rs1393350",
            "rs12203592",
        ),
        evidence_refs=(
            "IrisPlex 6-SNP panel (Walsh et al. 2011); published "
            "multinomial regression coefficients have not been sourced "
            "or verified for this project, so the current model uses a "
            "transparent, documented simplified-scoring fallback, "
            "explicitly labeled as such in every prediction (Phase 2 "
            "Architecture Blueprint, Section 8.1).",
            "IrisPlex's own published validation studies report "
            "near-zero sensitivity for correctly identifying "
            "intermediate eye colour even under the fitted model; "
            "this is reflected in the current model's confidence "
            "assignment, not overstated as a determinate result "
            "(Phase 2 Architecture Blueprint, Section 8.1).",
        ),
    ),
)
"""Populated incrementally as each concrete TraitModel is authored, per
the Trait Contract Layer freeze's explicit deferral decision. Currently
holds the lactase persistence, earwax type, ACTN3, bitter taste, and
eye colour entries, matching LactasePersistenceModel, EarwaxTypeModel,
ACTN3Model, BitterTasteModel, and EyeColourModel
(traits/domain/models/lactase_persistence_model.py,
traits/domain/models/earwax_type_model.py,
traits/domain/models/actn3_model.py,
traits/domain/models/bitter_taste_model.py,
traits/domain/models/eye_colour_model.py). Any optional traits remain
unpopulated until their own concrete models are authored.
"""

TRAIT_REGISTRY: Mapping[str, TraitDefinition] = build_trait_registry(_DEFINITIONS)