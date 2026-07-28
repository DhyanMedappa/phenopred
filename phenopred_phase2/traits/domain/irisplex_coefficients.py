# phenopred_phase2/traits/domain/irisplex_coefficients.py
"""IrisPlex multinomial regression coefficient table.

Closed, static, read-only knowledge source for the IrisPlex eye-colour
model's fitted coefficients, mirroring snp_registry.py's own frozen
design exactly:

- No dependency on GenotypeCall, GenotypeIndex, or DataRow. No
  knowledge that files, rows, or parsed genotypes exist.
- Performs no genotype interpretation, comparison, or scoring -- it
  only stores the reference data EyeColourModel needs to perform that
  interpretation itself.
- Not runtime-configurable, not an extension framework.
- Kept deliberately separate from SNP_REGISTRY: SNP_REGISTRY's
  reference_allele/alternate_allele/phenotype_associated_allele fields
  were authored for the earlier heuristic model and are not guaranteed
  to share the same counted-allele orientation IrisPlex's own fitted
  coefficients require. This table defines its own, authoritative
  counted_allele per SNP.

Source and verification status (see each SNPCoefficient.citation for
the per-SNP detail):

Model: Walsh, S., Liu, F., Ballantyne, K.N., van Oven, M., Lao, O.,
Kayser, M. (2011). "IrisPlex: A sensitive DNA tool for accurate
prediction of blue and brown eye colour in the absence of ancestry
information." Forensic Science International: Genetics, 5(3):170-180.
doi:10.1016/j.fsigen.2010.02.004.

The primary publication's own coefficient table (its Table 3) was not
directly accessible for this project (publisher access restriction; no
open-access deposit found). The values below were recovered from a
secondary, attributable academic source that explicitly cites the same
primary paper and the same six-SNP model: the CSE 185 course (UC San
Diego, Gymrek Laboratory), github.com/gymreklab/cse185-spring18-week5,
and its linked worked-example spreadsheet ("MyEyeColor").

These values were cross-validated, not accepted uncritically:
- The worked example's own arithmetic was independently reproduced by
  hand from these exact intercepts/coefficients and confirmed correct
  to full displayed precision (see
  test_irisplex_coefficients.py / test_eye_colour_model.py's
  regression-reproduction test).
- Allele-effect directions for five of six SNPs (all except rs1393350)
  were independently confirmed consistent with this project's own
  dbSNP/ClinVar-verified SNP_REGISTRY entries and, for rs12913832
  specifically, with an independent peer-reviewed source.
- rs1393350 could not be fully reconciled against this project's own
  literature-derived characterisation of that SNP (which associates
  its counted allele primarily with green/hazel eye colour, not
  specifically blue) -- see that entry's own citation for the disclosed
  detail. This is a documented, bounded limitation, not a blocker: per
  the approved implementation decision, this SNP is retained with its
  provenance caveat rather than excluded.

This is therefore a reliable secondary reproduction with disclosed,
bounded uncertainty -- not a digit-for-digit verified transcription of
the original publication. No claim of direct primary-table
verification is made anywhere in this module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

ALPHA_BLUE: float = 3.94
ALPHA_OTHER: float = 0.65


@dataclass(frozen=True, slots=True)
class IrisPlexCoefficient:
    """A single, immutable, IrisPlex-specific coefficient record for
    one registered RSID.

    This is purely descriptive -- it carries no dosage-extraction or
    regression logic of its own. The only validation it performs is
    structural (non-empty required fields); it never checks biological
    correctness.

    Attributes:
        rsid: The RSID this record describes.
        counted_allele: The allele IrisPlex's own fitted model counts
            dosage against for this SNP -- authoritative for this
            model specifically, independent of
            SNP_REGISTRY.phenotype_associated_allele.
        beta_blue: The fitted coefficient for this SNP in the
            ln(p_blue/p_brown) model.
        beta_other: The fitted coefficient for this SNP in the
            ln(p_other/p_brown) model.
        citation: The source and verification status for this specific
            SNP's coefficient values.
    """

    rsid: str
    counted_allele: str
    beta_blue: float
    beta_other: float
    citation: str

    def __post_init__(self) -> None:
        """Enforce the sole class of invariant named for this entity:
        every required string field must be non-empty after stripping
        whitespace. Mirrors SNPRecord.__post_init__'s identical,
        structural-only validation discipline.

        Raises:
            ValueError: If rsid, counted_allele, or citation is empty
                or whitespace-only.
        """
        for field_name in ("rsid", "counted_allele", "citation"):
            if not getattr(self, field_name).strip():
                raise ValueError(
                    f"IrisPlexCoefficient.{field_name} must be "
                    f"non-empty, got {getattr(self, field_name)!r}"
                )


def build_irisplex_coefficients(
    records: Sequence[IrisPlexCoefficient],
) -> Mapping[str, IrisPlexCoefficient]:
    """Build an immutable, RSID-keyed mapping from `records`.

    Exposed as a plain, public function (not folded silently into
    module-load code) specifically so its duplicate-detection behavior
    can be exercised directly in tests, mirroring
    snp_registry.build_registry()'s identical rationale.

    Args:
        records: The static IrisPlexCoefficient entries to index by
            rsid.

    Returns:
        An immutable mapping (a MappingProxyType) from rsid to
        IrisPlexCoefficient, with one entry per record in `records`.

    Raises:
        ValueError: If two records in `records` share the same rsid --
            a developer-authored static-data defect, mirroring
            build_registry()'s identical duplicate-rsid handling.
    """
    registry: dict[str, IrisPlexCoefficient] = {}
    for record in records:
        if record.rsid in registry:
            raise ValueError(
                f"Duplicate rsid {record.rsid!r} in IrisPlex coefficient "
                "static data; each rsid must be defined exactly once."
            )
        registry[record.rsid] = record

    return MappingProxyType(registry)


_RECORDS: tuple[IrisPlexCoefficient, ...] = (
    IrisPlexCoefficient(
        rsid="rs12913832",
        counted_allele="A",
        beta_blue=-4.81,
        beta_other=-1.79,
        citation=(
            "Walsh et al. 2011 IrisPlex model, as reproduced in UCSD "
            "CSE 185 (Gymrek Lab) course materials and worked example "
            "(github.com/gymreklab/cse185-spring18-week5); not "
            "independently verified against the primary publication's "
            "own table. Direction independently corroborated by this "
            "project's own dbSNP-verified SNP_REGISTRY entry and by an "
            "independent peer-reviewed source (Salvo et al., "
            "'Association between brown eye colour in HERC2 rs12913832 "
            "AA and AG Individuals'); the largest-magnitude coefficient "
            "in this table and the model's dominant predictor."
        ),
    ),
    IrisPlexCoefficient(
        rsid="rs1800407",
        counted_allele="T",
        beta_blue=1.4,
        beta_other=0.87,
        citation=(
            "Walsh et al. 2011 IrisPlex model, as reproduced in UCSD "
            "CSE 185 (Gymrek Lab) course materials and worked example; "
            "not independently verified against the primary "
            "publication's own table. Direction independently "
            "corroborated by this project's own dbSNP RefSNP-verified "
            "SNP_REGISTRY correction for this same SNP."
        ),
    ),
    IrisPlexCoefficient(
        rsid="rs12896399",
        counted_allele="G",
        beta_blue=-0.58,
        beta_other=-0.03,
        citation=(
            "Walsh et al. 2011 IrisPlex model, as reproduced in UCSD "
            "CSE 185 (Gymrek Lab) course materials and worked example; "
            "not independently verified against the primary "
            "publication's own table. Direction consistent with this "
            "project's own SNP_REGISTRY entry; the specific claim that "
            "this is the true minor allele in the original Dutch "
            "training population was not independently confirmed."
        ),
    ),
    IrisPlexCoefficient(
        rsid="rs16891982",
        counted_allele="C",
        beta_blue=-1.3,
        beta_other=-0.5,
        citation=(
            "Walsh et al. 2011 IrisPlex model, as reproduced in UCSD "
            "CSE 185 (Gymrek Lab) course materials and worked example; "
            "not independently verified against the primary "
            "publication's own table. Direction consistent with this "
            "project's own SNP_REGISTRY entry."
        ),
    ),
    IrisPlexCoefficient(
        rsid="rs1393350",
        counted_allele="A",
        beta_blue=0.47,
        beta_other=0.27,
        citation=(
            "Walsh et al. 2011 IrisPlex model, as reproduced in UCSD "
            "CSE 185 (Gymrek Lab) course materials and worked example; "
            "not independently verified against the primary "
            "publication's own table. UNRESOLVED PROVENANCE CAVEAT: "
            "this project's own SNP_REGISTRY cites a peer-reviewed "
            "comparative GWAS (Scientific Reports) associating this "
            "SNP's counted allele primarily with green/hazel eye "
            "colour, not specifically blue; this could not be cleanly "
            "reconciled with this coefficient's positive blue-axis "
            "weight without access to the primary IrisPlex table, and "
            "may reflect either a genuine secondary blue-axis effect or "
            "an unverified allele-orientation difference between "
            "sources. Retained per approved decision, not excluded; "
            "flagged here for any future re-verification."
        ),
    ),
    IrisPlexCoefficient(
        rsid="rs12203592",
        counted_allele="T",
        beta_blue=0.7,
        beta_other=0.73,
        citation=(
            "Walsh et al. 2011 IrisPlex model, as reproduced in UCSD "
            "CSE 185 (Gymrek Lab) course materials and worked example; "
            "not independently verified against the primary "
            "publication's own table. Direction consistent with this "
            "project's own SNP_REGISTRY entry."
        ),
    ),
)

IRISPLEX_COEFFICIENTS: Mapping[str, IrisPlexCoefficient] = build_irisplex_coefficients(
    _RECORDS
)