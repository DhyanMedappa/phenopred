# phenopred_phase2/comparison/domain/identity_heuristic.py
"""Structured interpretation of a genome-wide ConcordanceResult.

Per Blueprint Section 10.1/10.3 and the approved Final Design
Specification's Decision 3, this module owns exactly one
responsibility: map an already-computed ConcordanceResult's
agreement_percentage into one of four qualitative
IdentityLikelihoodCategory bands, always paired with a stable
methodology-caveat reference.

Boundaries (frozen by the approved specification):

- Never performs IBD/IBS calculation -- Section 10.3 explicitly
  requires this be named, never implemented.
- Never claims identity verification -- every category is a rate
  observation, phrased as "consistent with," never "proof of."
- Never generates report prose -- methodology_caveat_key is a stable
  reference string a future reporting layer looks up; the actual
  caveat sentence is rendered later, never here.

Threshold values below are a reasonable, defensible default sufficient
to produce the required qualitative bands -- they are not derived from
a validation study in the project's source materials, and the
Blueprint itself does not specify exact cutoffs. This is disclosed
here, not silently assumed.
"""

from __future__ import annotations

from phenopred_phase2.comparison.domain.entities import (
    ConcordanceResult,
    IdentityLikelihood,
    IdentityLikelihoodCategory,
)

# ---------------------------------------------------------------------------
# Threshold constants -- plain module-level constants, mirroring
# composition.py's own DEFAULT_* style and V1's composition_root.py's
# _DEFAULT_* style exactly. No dedicated configuration module is
# introduced for these, consistent with this codebase's repeated
# rejection of configuration-surface-area creep for a single
# component's own static values.
# ---------------------------------------------------------------------------

_VERY_HIGH_CONCORDANCE_THRESHOLD = 99.9
_HIGH_CONCORDANCE_THRESHOLD = 99.0
_REDUCED_CONCORDANCE_THRESHOLD = 95.0

# A stable, fixed reference key -- never rendered prose. The future
# reporting layer looks this key up to render the actual required
# sentence (Blueprint Section 10.3: IBD/IBS named in report text, not
# implemented).
METHODOLOGY_CAVEAT_KEY = "identity_heuristic_not_ibd_ibs"


def interpret_identity_likelihood(
    concordance: ConcordanceResult,
) -> IdentityLikelihood:
    """Interpret an already-computed ConcordanceResult into a
    structured, qualitative IdentityLikelihood.

    Args:
        concordance: The already-computed genome-wide ConcordanceResult
            (e.g. from concordance_calculator.calculate_concordance()).

    Returns:
        An IdentityLikelihood carrying the source concordance
        percentage, one of the four qualitative categories, and the
        fixed methodology-caveat reference key -- always populated,
        never omitted, regardless of category.
    """
    rate = concordance.agreement_percentage

    if rate >= _VERY_HIGH_CONCORDANCE_THRESHOLD:
        category = IdentityLikelihoodCategory.VERY_HIGH_CONCORDANCE
    elif rate >= _HIGH_CONCORDANCE_THRESHOLD:
        category = IdentityLikelihoodCategory.HIGH_CONCORDANCE
    elif rate >= _REDUCED_CONCORDANCE_THRESHOLD:
        category = IdentityLikelihoodCategory.REDUCED_CONCORDANCE
    else:
        category = IdentityLikelihoodCategory.LOW_CONCORDANCE

    return IdentityLikelihood(
        concordance_percentage=rate,
        category=category,
        methodology_caveat_key=METHODOLOGY_CAVEAT_KEY,
    )
