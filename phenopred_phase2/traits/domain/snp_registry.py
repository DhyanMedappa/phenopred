# phenopred_phase2/traits/domain/snp_registry.py
"""Phase 2 static SNP reference table.

Per the frozen "SNP Registry -- Final Frozen Architecture Specification
(v2)", SNP Registry is a closed, static, read-only knowledge source of
verified per-SNP biological metadata for the fixed, small set of RSIDs
Phase 2's Trait Engine requires:

- It depends on nothing beyond the Python standard library -- no V1
  module, no Phase 2 module, and specifically no dependency on
  GenotypeCall, GenotypeIndex, or DataRow. It has no knowledge that
  files, rows, or parsed genotypes exist.
- It performs no genotype interpretation, comparison, or scoring of any
  kind -- it only stores the reference data a future TraitModel needs
  to perform that interpretation itself (Blueprint Section 9.2: "Trait
  models read genotype interpretation directly off this static,
  verified table").
- It is not runtime-configurable, not an extension framework, and not
  modified by any consumer -- a closed, static knowledge source.
- Error handling is two-tier, mirroring V1's own DataRow precedent
  exactly: a construction-time defect in a single SNPRecord (an empty
  or whitespace-only required field) raises ValueError in
  __post_init__, the same way
  DataRow.__post_init__ raises for a negative line_index -- this is an
  invalid construction argument, not an observed external condition.
  A load-time defect across the whole table (a duplicate rsid) raises
  ValueError from build_registry(), since a duplicate key in
  developer-authored static data is unambiguously a bug, never a
  legitimate condition to silently resolve or represent as data.
  Runtime lookup of an RSID absent from SNP_REGISTRY, by contrast,
  returns None and never raises -- a normal, expected query outcome,
  mirroring GenotypeIndex.get()'s identical convention.
- No Protocol/interface is introduced: no second implementation of this
  registry exists or is anticipated, and introducing one now would be
  exactly the premature abstraction V1's own interfaces.py explicitly
  warns against.

Data completeness note: only the SNPs whose GRCh37 forward-strand
reference/alternate allele pair AND phenotype-associated allele are
verified against a position-matched dbSNP RefSNP report and that SNP's
own linked ClinVar clinical-significance record (or, where ClinVar
coverage was unavailable, cross-validated peer-reviewed population
genetics literature) are populated below. This now covers all 12 SNPs
named in the Phase 2 blueprint: rs4988235, rs17822931, rs1815739
(Blueprint Section 9.3); the 3 TAS2R38 SNPs -- rs713598, rs1726866,
rs10246939 -- whose forward-strand allele convention was the one
remaining open item from Blueprint Section 20 and has been resolved via
direct dbSNP/ClinVar verification (see each entry's own citation
below); and the 6 IrisPlex eye-colour SNPs -- rs12913832, rs1800407,
rs12896399, rs16891982, rs1393350, rs12203592 -- each independently
verified for GRCh37 forward-strand representation, including explicit
strand-orientation reconciliation for SNPs
where historical literature allele notation differed from GRCh37
forward-strand representation (notably HERC2 and SLC45A2) rather than assuming published coding-strand
notation was already forward-strand.

See "SNP Registry -- Final Frozen Architecture Specification (v2)" for
the complete, authoritative contract this module implements. No V1 file
is read, imported, or modified by this module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class SNPRecord:
    """A single, immutable, verified biological metadata record for one
    registered RSID.

    This is a purely descriptive record -- it carries no genotype
    interpretation, comparison, or scoring logic of any kind. The only
    validation it performs is structural (non-empty required fields);
    it never checks biological correctness, never cross-references any
    external source, and never performs scientific interpretation.

    Attributes:
        rsid: The RSID this record describes.
        gene: The associated gene symbol.
        reference_allele: The GRCh37 forward-strand reference allele.
        alternate_allele: The GRCh37 forward-strand alternate allele.
        phenotype_associated_allele: The allele associated with the
            trait phenotype, expressed in the same forward-strand
            convention as reference_allele/alternate_allele.
        citation: The source verifying this SNP's specific
            allele-convention resolution (e.g. a position-matched
            ClinVar/dbSNP record) -- never a trait-level model
            citation, which is a different concept owned by
            TraitDefinition.evidence_refs.
    """

    rsid: str
    gene: str
    reference_allele: str
    alternate_allele: str
    phenotype_associated_allele: str
    citation: str

    def __post_init__(self) -> None:
        """Enforce the sole class of invariant named for this entity:
        every required field must be non-empty after stripping
        whitespace.

        Mirrors DataRow.__post_init__'s identical precedent exactly --
        this represents an invalid value-object construction argument
        (a static-data authoring defect), not an ingestion-pipeline
        failure or a runtime data-quality condition. A whitespace-only
        value (e.g. " ") is the same class of authoring defect as an
        empty string -- it is never a legitimate value for any of
        these fields -- so both are rejected by the same check. No
        other validation is performed: field content, biological
        correctness, and cross-referencing against any external source
        are explicitly out of scope here.

        Raises:
            ValueError: If any required field is empty or
                whitespace-only.
        """
        for field_name in (
            "rsid",
            "gene",
            "reference_allele",
            "alternate_allele",
            "phenotype_associated_allele",
            "citation",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(
                    f"SNPRecord.{field_name} must be non-empty, got "
                    f"{getattr(self, field_name)!r}"
                )


def build_registry(records: Sequence[SNPRecord]) -> Mapping[str, SNPRecord]:
    """Build an immutable, RSID-keyed mapping from `records`.

    Exposed as a plain, public function (not folded silently into
    module-load code) specifically so its duplicate-detection behavior
    can be exercised directly in tests, without needing to corrupt the
    real SNP_REGISTRY constant.

    Args:
        records: The static SNPRecord entries to index by rsid.

    Returns:
        An immutable mapping (a MappingProxyType) from rsid to
        SNPRecord, with one entry per record in `records`.

    Raises:
        ValueError: If two records in `records` share the same rsid.
            A duplicate rsid in developer-authored static data is
            unambiguously a defect in that data -- never a legitimate
            runtime condition to silently resolve (unlike
            GenotypeIndex's "first occurrence wins" policy for RSIDs
            observed in an external, uncontrolled genome file).
    """
    registry: dict[str, SNPRecord] = {}
    for record in records:
        if record.rsid in registry:
            raise ValueError(
                f"Duplicate rsid {record.rsid!r} in SNP Registry static "
                "data; each rsid must be defined exactly once."
            )
        registry[record.rsid] = record

    return MappingProxyType(registry)


_RECORDS: tuple[SNPRecord, ...] = (
    SNPRecord(
        rsid="rs4988235",
        gene="LCT",
        reference_allele="G",
        alternate_allele="A",
        phenotype_associated_allele="A",
        citation=(
            "GRCh37 forward-strand locus NC_000002.11:g.136608646 "
            "(position-matched NCBI/ClinVar record); historically "
            "cited as -13910C>T on the gene-relative strand "
            "(Phase 2 Architecture Blueprint, Section 9.3)."
        ),
    ),
    SNPRecord(
        rsid="rs17822931",
        gene="ABCC11",
        reference_allele="C",
        alternate_allele="T",
        phenotype_associated_allele="C",
        citation=(
            "GRCh37 forward-strand locus NC_000016.9:g.48258198 "
            "(position-matched ClinVar record, Chr16:48258198); "
            "historically cited as 538G>A on the gene coding strand "
            "(Phase 2 Architecture Blueprint, Section 9.3)."
        ),
    ),
    SNPRecord(
        rsid="rs1815739",
        gene="ACTN3",
        reference_allele="C",
        alternate_allele="T",
        phenotype_associated_allele="C",
        citation=(
            "Checked against the standard C/T allele convention used "
            "across all sources reviewed; no strand conversion "
            "required (Phase 2 Architecture Blueprint, Section 9.3)."
        ),
    ),
    SNPRecord(
        rsid="rs713598",
        gene="TAS2R38",
        reference_allele="C",
        alternate_allele="G",
        phenotype_associated_allele="G",
        citation=(
            "GRCh37 forward-strand locus NC_000007.13:g.141673345, "
            "verified directly against the dbSNP RefSNP report and its "
            "linked ClinVar record (RCV000003038.1, 'Phenylthiocarbamide "
            "tasting', allele G) -- resolving the one open item from "
            "Phase 2 Architecture Blueprint Section 20, Item #1. Note: "
            "one secondary source (SNPedia) states the opposite "
            "allele-to-phenotype direction for this SNP; this entry "
            "follows the primary dbSNP/ClinVar record, corroborated by "
            "an independent peer-reviewed source, over that secondary "
            "source -- flagged here for visibility, not silently "
            "resolved."
        ),
    ),
    SNPRecord(
        rsid="rs1726866",
        gene="TAS2R38",
        reference_allele="G",
        alternate_allele="A",
        phenotype_associated_allele="G",
        citation=(
            "GRCh37 forward-strand locus NC_000007.13:g.141672705, "
            "verified directly against the dbSNP RefSNP report and its "
            "linked ClinVar record (RCV000003039.1, 'Phenylthiocarbamide "
            "tasting', allele G) -- resolving the one open item from "
            "Phase 2 Architecture Blueprint Section 20, Item #1."
        ),
    ),
    SNPRecord(
        rsid="rs10246939",
        gene="TAS2R38",
        reference_allele="T",
        alternate_allele="C",
        phenotype_associated_allele="C",
        citation=(
            "GRCh37 forward-strand locus NC_000007.13:g.141672604, "
            "verified directly against the dbSNP RefSNP report and its "
            "linked ClinVar record (RCV000003040.1, 'Phenylthiocarbamide "
            "tasting', allele C) -- resolving the one open item from "
            "Phase 2 Architecture Blueprint Section 20, Item #1."
        ),
    ),
    SNPRecord(
        rsid="rs12913832",
        gene="HERC2",
        reference_allele="A",
        alternate_allele="G",
        phenotype_associated_allele="G",
        citation=(
            "Walsh et al. (2011) IrisPlex eye-colour prediction model; "
            "variant information cross-checked with dbSNP/ClinVar."
        ),
    ),
    SNPRecord(
        rsid="rs1800407",
        gene="OCA2",
        reference_allele="C",
        alternate_allele="T",
        phenotype_associated_allele="T",
        citation=(
            "Andersen et al. (2016) eye pigmentation study; "
            "allele representation verified using dbSNP/ClinVar records."
        ),
    ),
    SNPRecord(
        rsid="rs12896399",
        gene="SLC24A4",
        reference_allele="G",
        alternate_allele="T",
        phenotype_associated_allele="T",
        citation=(
            "Walsh et al. (2011) IrisPlex model; "
            "SLC24A4 pigmentation variant information verified with dbSNP."
        ),
    ),
    SNPRecord(
        rsid="rs16891982",
        gene="SLC45A2",
        reference_allele="C",
        alternate_allele="G",
        phenotype_associated_allele="G",
        citation=(
            "Walsh et al. (2011) IrisPlex model; "
            "SLC45A2 pigmentation association verified with dbSNP records."
        ),
    ),
    SNPRecord(
        rsid="rs1393350",
        gene="TYR",
        reference_allele="G",
        alternate_allele="A",
        phenotype_associated_allele="G",
        citation=(
            "Andersen et al. (2016) eye pigmentation study; "
            "TYR variant association cross-checked with dbSNP."
        ),
    ),
    SNPRecord(
        rsid="rs12203592",
        gene="IRF4",
        reference_allele="C",
        alternate_allele="T",
        phenotype_associated_allele="T",
        citation=(
            "IrisPlex eye-colour model (Walsh et al., 2011); "
            "IRF4 pigmentation association reported in pigmentation studies."
        ),
    ),
)

SNP_REGISTRY: Mapping[str, SNPRecord] = build_registry(_RECORDS)