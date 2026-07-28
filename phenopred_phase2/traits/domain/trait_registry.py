from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from phenopred_phase2.traits.domain.entities import TraitDefinition


def build_trait_registry(
    definitions: Sequence[TraitDefinition],
) -> Mapping[str, TraitDefinition]:
    """Build an immutable, trait_id-keyed mapping from definitions."""

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
            "LCT/MCM6 lactase persistence variant (Enattah et al., 2002).",
        ),
    ),

    TraitDefinition(
        trait_id="earwax_type",
        name="Earwax Type",
        required_rsids=("rs17822931",),
        evidence_refs=(
            "ABCC11 earwax association (Yoshiura et al., 2006).",
        ),
    ),

    TraitDefinition(
        trait_id="actn3",
        name="ACTN3 (Alpha-Actinin-3)",
        required_rsids=("rs1815739",),
        evidence_refs=(
            "ACTN3 R577X variant and athletic performance association "
            "(Yang et al., 2003).",
        ),
    ),

    TraitDefinition(
        trait_id="bitter_taste",
        name="Bitter Taste (TAS2R38)",
        required_rsids=(
            "rs713598",
            "rs1726866",
            "rs10246939",
        ),
        evidence_refs=(
            "TAS2R38 PAV/AVI bitter taste haplotypes "
            "(Kim et al., 2003).",
            "Consumer genotype data lacks phase information; diplotype "
            "interpretation uses common haplotype assumptions.",
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
            "IrisPlex 6-SNP panel and eye colour prediction model "
            "(Walsh et al., 2011).",
        ),
    ),
)


TRAIT_REGISTRY: Mapping[str, TraitDefinition] = build_trait_registry(_DEFINITIONS)