# phenopred_phase2/traits/application/composition.py
"""Phase 2 orchestration layer -- the one remaining piece connecting
V1's ProfileFileUseCase output to GenotypeIndex and TraitEngine.

Per the approved architecture review, this module owns exactly one
responsibility: given the plain dict ProfileFileUseCase.execute()
already returns for one file, construct a GenotypeIndex from its
`data_rows`/`column_layout` entries, run TraitEngine against it, and
return the resulting Mapping[str, TraitPrediction].

Ownership boundaries (frozen by the approved review):

- This module lives in phenopred_phase2/, mirroring V1's own
  application/composition_root.py in spirit -- construction and
  wiring only, no domain logic, no biological interpretation, no
  file I/O of its own. It consumes only the plain dict
  ProfileFileUseCase.execute() already produces; it never imports
  ProfileFileUseCase itself, never calls .execute(), and never
  touches DataRow/ColumnLayout construction logic -- those remain
  exclusively V1's responsibility.
- Dependency direction is preserved exactly as required: this module
  imports from phenopred_phase2 (GenotypeIndex, TraitEngine,
  TRAIT_REGISTRY, TRAIT_MODEL_REGISTRY) and, only for type-checking
  purposes at the boundary, treats V1's result dict as plain data --
  it never imports any phenopred (V1) module. V1 remains completely
  unaware this module exists.
- GenotypeIndex, TraitEngine, every trait model, and both registries
  are consumed exactly as already built and tested -- none is
  modified, subclassed, wrapped, or reimplemented here.

Configuration ownership (per the approved review, Decision 2):
GenotypeIndex's three required vocabulary arguments
(missing_value_tokens, indel_tokens, sex_mitochondrial_labels) must
never live inside GenotypeIndex itself (frozen, no-default constructor
contract) and must never be invented without evidence. The defaults
below were derived by directly inspecting both real validation files
(AncestryDNA.txt, anonymous_genome_v5_build37.txt), not assumed or
copied unchanged from V1's own composition_root.py defaults (which
were confirmed, by that same inspection, to be insufficient on their
own -- see each constant's own comment below). These are supplied as
plain module-level constants and as this module's own function
default keyword arguments, mirroring V1's own
build_profile_file_use_case()'s exact style (plain constants, explicit
keyword arguments, no configuration framework, no dedicated config
package) -- consistent with the same architecture, not a new pattern.

Per the project's explicit extensibility requirement: these are
*default* values for the currently-validated file conventions, never
hardcoded assumptions baked into GenotypeIndex, TraitEngine, or this
module's own control flow. A future genotype provider using a
different no-call or indel token convention is supported simply by
passing different `missing_value_tokens`/`indel_tokens`/
`sex_mitochondrial_labels` arguments to `run_trait_pipeline()` below --
no change to this module, GenotypeIndex, or TraitEngine is required.
No file-format-specific branching of any kind exists anywhere in this
module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from phenopred_phase2.traits.application.trait_engine import TraitEngine
from phenopred_phase2.traits.domain.entities import TraitPrediction
from phenopred_phase2.traits.domain.genotype_index import GenotypeIndex
from phenopred_phase2.traits.domain.trait_model_registry import (
    TRAIT_MODEL_REGISTRY,
)
from phenopred_phase2.traits.domain.trait_registry import TRAIT_REGISTRY

# ---------------------------------------------------------------------------
# Default configuration values -- evidence-based, not invented.
#
# Verified directly against both real validation files during the
# approved architecture review:
#
# - "--" is anonymous_genome_v5_build37.txt's own documented and
#   observed (2,968 occurrences) no-call convention.
# - "0" is AncestryDNA.txt's real, observed (502 occurrences, always
#   paired "0"/"0") no-call convention -- undocumented in that file's
#   own header comments, confirmed only by direct data inspection.
#   Omitting it would silently misclassify those 502 real rows as SNP
#   calls with alleles "00", rather than NO_CALL.
# - "DD"/"II"/"DI" match anonymous_genome_v5_build37.txt's own
#   documented, two-character combined-genotype indel convention.
# - "D"/"I" match AncestryDNA.txt's real, per-column indel convention
#   (2,389 "D,D" / 6,406 "I,I" / 34 mixed real occurrences) -- absent
#   from V1's own composition_root.py default indel_tokens, which
#   would therefore be insufficient if reused unchanged for this
#   purpose.
# - "X", "Y", "MT" match V1's own composition_root.py default
#   sex_mitochondrial_labels exactly; no contradicting evidence was
#   found in either file during this review.
#
# These are defaults for the two currently-validated file layouts
# only -- never a hardcoded assumption inside GenotypeIndex, TraitEngine,
# or this module's control flow. Any future provider's differing
# convention is supported by passing different arguments to
# `run_trait_pipeline()`, not by editing these constants' meaning or
# this module's logic.
# ---------------------------------------------------------------------------

DEFAULT_MISSING_VALUE_TOKENS: tuple[str, ...] = ("--", "0")
DEFAULT_INDEL_TOKENS: tuple[str, ...] = ("D", "I", "DD", "II", "DI")
DEFAULT_SEX_MITOCHONDRIAL_LABELS: tuple[str, ...] = ("X", "Y", "MT")


def build_genotype_index(
    profile_result: Mapping[str, Any],
    *,
    missing_value_tokens: Sequence[str] = DEFAULT_MISSING_VALUE_TOKENS,
    indel_tokens: Sequence[str] = DEFAULT_INDEL_TOKENS,
    sex_mitochondrial_labels: Sequence[str] = DEFAULT_SEX_MITOCHONDRIAL_LABELS,
) -> GenotypeIndex:
    """Construct a GenotypeIndex from one file's ProfileFileUseCase
    result.

    Args:
        profile_result: The plain dict returned by
            `ProfileFileUseCase.execute()` for one file (or any
            equivalent mapping exposing the same "data_rows" and
            "column_layout" keys) -- consumed only via
            `profile_result["data_rows"]` and
            `profile_result["column_layout"]`. This function performs
            no file I/O and does not call `.execute()` itself; the
            result must already be in memory.
        missing_value_tokens: The literal value(s) treated as a
            no-call genotype. Defaults to the evidence-based value
            derived from both real validation files (see module
            docstring); explicitly overridable for any other genotype
            provider's own convention, with no change required to
            GenotypeIndex, TraitEngine, or this module's logic.
        indel_tokens: The literal value(s) treated as an indel
            genotype. Same default/override contract as
            `missing_value_tokens`.
        sex_mitochondrial_labels: The chromosome label(s) on which a
            single-character designated-column value is classified as
            haploid. Same default/override contract as
            `missing_value_tokens`.

    Returns:
        A GenotypeIndex built from `profile_result`'s already-resolved
        data_rows and column_layout, using the supplied (or default)
        vocabulary configuration. GenotypeIndex itself is consumed
        exactly as already built and tested -- unmodified.
    """
    return GenotypeIndex(
        data_rows=profile_result["data_rows"],
        column_layout=profile_result["column_layout"],
        missing_value_tokens=missing_value_tokens,
        indel_tokens=indel_tokens,
        sex_mitochondrial_labels=sex_mitochondrial_labels,
    )


def run_trait_pipeline(
    profile_result: Mapping[str, Any],
    *,
    missing_value_tokens: Sequence[str] = DEFAULT_MISSING_VALUE_TOKENS,
    indel_tokens: Sequence[str] = DEFAULT_INDEL_TOKENS,
    sex_mitochondrial_labels: Sequence[str] = DEFAULT_SEX_MITOCHONDRIAL_LABELS,
) -> Mapping[str, TraitPrediction]:
    """Run the complete trait execution pipeline for one file's
    ProfileFileUseCase result.

    This is the single, minimal orchestration boundary described by
    the approved architecture review: construct a GenotypeIndex from
    `profile_result` (via `build_genotype_index`, above), then execute
    TraitEngine -- bound to the real TRAIT_REGISTRY and
    TRAIT_MODEL_REGISTRY -- against it, and return the resulting
    predictions. It performs no biological interpretation, no file
    parsing, no reporting, and no comparison logic of any kind; every
    one of those remains the exclusive responsibility of the
    components it wires together.

    Args:
        profile_result: The plain dict returned by
            `ProfileFileUseCase.execute()` for one file (or any
            equivalent mapping exposing "data_rows"/"column_layout").
        missing_value_tokens: Forwarded to `build_genotype_index`; see
            its own docstring.
        indel_tokens: Forwarded to `build_genotype_index`; see its own
            docstring.
        sex_mitochondrial_labels: Forwarded to `build_genotype_index`;
            see its own docstring.

    Returns:
        The Mapping[str, TraitPrediction] produced by
        `TraitEngine.run()` for this file, using the real
        TRAIT_REGISTRY and TRAIT_MODEL_REGISTRY -- one entry per
        currently-bound trait, in TRAIT_REGISTRY's own iteration
        order. TraitEngine's own, already-approved behavior governs
        every edge case (an unbound trait is skipped, not raised; a
        missing genotype call yields whatever the model itself decides;
        an INSUFFICIENT_DATA prediction is returned unchanged) --
        nothing here alters or re-checks any of that.
    """
    genotype_index = build_genotype_index(
        profile_result,
        missing_value_tokens=missing_value_tokens,
        indel_tokens=indel_tokens,
        sex_mitochondrial_labels=sex_mitochondrial_labels,
    )
    engine = TraitEngine(TRAIT_REGISTRY, TRAIT_MODEL_REGISTRY)
    return engine.run(genotype_index)