# phenopred/domain/reporting/open_question_registry.py
"""Domain-layer reporting component holding the fixed set of open
questions the SRS identifies as requiring future validation, and
selecting the ones applicable to a given file's observed Findings and
Profiles (OUT-9, OBJ-5, AD-7).

OpenQuestionRegistry is the sole component responsible for this
selection. Per Architecture v1 (Section 5/7.2/9/10, AD-7) and the frozen
Reporting Architecture:

- This module lives in the domain layer and performs no file/network I/O
  of any kind.
- It holds a fixed registry of OpenQuestion instances, derived exactly
  from SRS Section 8.2 and RISK-1 through RISK-9, and introduces no
  additional question, risk, or decision beyond that registry.
- It never resolves, interprets, modifies, or answers any OpenQuestion
  -- resolving them is explicitly future, separate work (SRS Section
  8.2, Section 11; AD-7). Its only behavior is selecting which
  already-fixed questions are applicable to a given file.
- Per the frozen Reporting Architecture's ReportBuilder integration
  decision, this class is consulted only via
  `applicable_for(findings, profiles)` -- the same already-computed
  Finding and Profile collections ReportBuilder assembles a
  ProfilingReport from. It never accepts, imports, or depends on
  EncodingProfile, Delimiter, HeaderInfo, CommentBlock, DataRow,
  RawFileLoader, or any detection/ingestion component -- only the
  Finding/Profile value objects already produced elsewhere in the
  pipeline.
- Applicability is determined only where SRS Section 8.2/RISK-1..9's own
  text ties a question to a specific, already-produced Finding or
  Profile's observed content (chromosome-label profiling, missing-value
  scanning, duplicate chromosome-position detection, genotype-layout
  profiling). Every other open question named by the SRS (RISK-6,
  RISK-7, RISK-8, RISK-9) concerns a property this system's Findings and
  Profiles do not carry -- strand-orientation claims, encoding-content
  provenance, data-sensitivity handling, and RSID-value provenance
  respectively -- and so is always selected as a standing question,
  never gated on file content this registry has no way to inspect via
  its `applicable_for(findings, profiles)` contract. Standing questions
  are still each correctly associated with the most relevant existing
  check/profiler name for traceability where one exists (NFR-6),
  without implying that component computes or gates the question.
- No fixed chromosome-label vocabulary beyond the conventional numeric
  autosome range (1-22) plus the sex/mitochondrial labels (X, Y, MT) is
  assumed for RISK-2's applicability test; this is the standard human
  karyotype notation itself, not a vendor-specific hard-code (NFR-5).
- This component never mutates any Finding or Profile it inspects, and
  never raises for any input shape -- an absent Finding/Profile for a
  given check/profiler name simply means the corresponding
  content-gated question is not selected; every standing question is
  still selected regardless.

Determinism note (NFR-3): `findings` and `profiles` are indexed into
`dict`s keyed by `check_name`/`profiler_name` purely for O(1) named
lookup -- never iterated to decide output order. The returned tuple's
order is fixed by this method's own, single, explicit sequence of
selection steps (RISK-1 through RISK-9, in that order), never by
dict/set iteration or insertion order, and never by the input
`findings`/`profiles` collections' own order.
"""

from __future__ import annotations

from collections.abc import Sequence

from phenopred.domain.value_objects import (
    ChromosomeLabelInventory,
    Finding,
    GenotypeLayoutProfile,
    IndelHaploidProfile,
    OpenQuestion,
)

_CHROMOSOME_LABEL_PROFILER_NAME = "chromosome_label_profiler"
_GENOTYPE_LAYOUT_CLASSIFIER_NAME = "genotype_layout_classifier"
_MISSING_VALUE_SCANNER_NAME = "missing_value_scanner"
_DUPLICATE_CHR_POS_CHECK_NAME = "duplicate_chr_pos_check"
_DUPLICATE_RSID_CHECK_NAME = "duplicate_rsid_check"

# The conventional human karyotype chromosome-label vocabulary used only
# as RISK-2's applicability test (autosomes 1-22, plus the sex/
# mitochondrial labels X, Y, MT) -- a neutral, non-vendor-specific
# reference set, never used to interpret, translate, or reconcile any
# label's biological meaning (RISK-1, RISK-2; NFR-5).
_CONVENTIONAL_CHROMOSOME_LABELS: frozenset[str] = frozenset(
    {str(number) for number in range(1, 23)} | {"X", "Y", "MT"}
)

_RISK_1_QUESTION = OpenQuestion(
    statement=(
        "Whether purely numeric chromosome labels (as observed in "
        "Dataset A) and numeric-plus-alphabetic chromosome labels (as "
        "observed in Dataset B) are equivalent or directly comparable "
        "across files has not been established. Any future process "
        "that joins, merges, or compares records by chromosome across "
        "files of these differing kinds risks misalignment if this is "
        "not explicitly reconciled against an authoritative reference."
    ),
    related_finding_or_profile=_CHROMOSOME_LABEL_PROFILER_NAME,
)

_RISK_2_QUESTION = OpenQuestion(
    statement=(
        "The biological meaning of non-standard numeric chromosome "
        "codes (i.e. codes beyond the conventional 1-22 autosome range) "
        "observed in a file's chromosome labels is not defined within "
        "the file itself. Interpreting these codes without an "
        "authoritative source risks silently mislabeling sex-chromosome "
        "or mitochondrial data."
    ),
    related_finding_or_profile=_CHROMOSOME_LABEL_PROFILER_NAME,
)

_RISK_3_QUESTION = OpenQuestion(
    statement=(
        "Whether missing/no-call tokens are handled equivalently across "
        "files with differing column layouts and literal token "
        "conventions has not been established. A future process that "
        "hard-codes one file's missing-value convention risks silently "
        "failing to recognize missing data expressed under a different "
        "convention."
    ),
    related_finding_or_profile=_MISSING_VALUE_SCANNER_NAME,
)

_RISK_4_QUESTION = OpenQuestion(
    statement=(
        "Whether duplicate (chromosome, position) pairs observed within "
        "a file reflect probe redesigns, multi-allelic sites, "
        "re-genotyping, or data artefacts has not been determined. "
        "Treating them as errors, or as valid multi-allelic entries, "
        "without further investigation risks either discarding valid "
        "data or retaining erroneous data."
    ),
    related_finding_or_profile=_DUPLICATE_CHR_POS_CHECK_NAME,
)

_RISK_5_QUESTION = OpenQuestion(
    statement=(
        "Whether a two-column allele-pair genotype layout and a "
        "single-column genotype-string layout (including haploid/indel "
        "variants) can be unified into a common representation without "
        "loss or misrepresentation has not been established. Any future "
        "unification of these encodings carries a risk of information "
        "loss if the haploid/diploid/indel distinctions are not "
        "preserved."
    ),
    related_finding_or_profile=_GENOTYPE_LAYOUT_CLASSIFIER_NAME,
)

_RISK_6_QUESTION = OpenQuestion(
    statement=(
        "Each file's header claims a forward/plus-strand orientation, "
        "but no independent verification of strand consistency has been "
        "performed. Any future position-based operation relying on "
        "strand consistency carries a risk of silent error if this "
        "claim does not hold in practice."
    ),
    related_finding_or_profile=None,
)

_RISK_7_QUESTION = OpenQuestion(
    statement=(
        "Whether a file's content is decodable only under certain text "
        "encodings (e.g. not as pure ASCII) has an identified source "
        "and location has not been established. This warrants further "
        "investigation before any text-processing logic assumes uniform "
        "character encoding across files."
    ),
    related_finding_or_profile=None,
)

_RISK_8_QUESTION = OpenQuestion(
    statement=(
        "Genotype data is intrinsically personal and can in principle "
        "be re-identified even with direct identifiers removed. Any "
        "handling of files of this kind inherits a data-protection risk "
        "that must be addressed by a dedicated, future security/privacy "
        "design, not assumed away here."
    ),
    related_finding_or_profile=None,
)

_RISK_9_QUESTION = OpenQuestion(
    statement=(
        "Whether every value in a file's RSID column is a standard "
        "dbSNP identifier, as opposed to a platform-internal "
        "identifier, has not been established. A future process that "
        "assumes all RSID-column values are standard dbSNP identifiers "
        "risks mishandling or misinterpreting the platform-internal "
        "subset."
    ),
    related_finding_or_profile=_DUPLICATE_RSID_CHECK_NAME,
)


class OpenQuestionRegistry:
    """Holds the SRS-derived fixed set of open questions and selects the
    ones applicable to a given file's observed Findings and Profiles
    (OUT-9, OBJ-5, AD-7).

    Stateless beyond its fixed, module-level question registry: holds no
    constructor-injected configuration and no mutable state of any kind,
    mirroring MalformedRowCheck's and the genomic profilers' identical
    pattern. Given the same inputs, `applicable_for()` always returns a
    field-for-field identical tuple of OpenQuestion instances (NFR-3).
    """

    def applicable_for(
        self,
        findings: Sequence[Finding],
        profiles: Sequence[
            ChromosomeLabelInventory | GenotypeLayoutProfile | IndelHaploidProfile
        ],
    ) -> tuple[OpenQuestion, ...]:
        """Select the subset of this system's fixed, registered open
        questions applicable to a file's already-computed Findings and
        Profiles.

        This method never resolves, alters, or interprets any selected
        question -- selection only. A Finding/Profile absent from
        `findings`/`profiles` for a given check/profiler name simply
        means the corresponding content-gated question below is not
        selected; every standing question (RISK-6, RISK-7, RISK-8,
        RISK-9) is selected regardless of `findings`/`profiles`'
        content, since none of them concerns a property those
        collections carry.

        Args:
            findings: The Finding collection already produced by this
                run's injected quality checks (e.g. the output of
                ProfileFileUseCase._run_quality_checks), consulted only
                by named `check_name` lookup -- never iterated to
                decide output order.
            profiles: The Profile collection already produced by this
                run's injected genomic profilers (e.g. the output of
                ProfileFileUseCase._run_genomic_profilers), consulted
                only by named `profiler_name` lookup -- never iterated
                to decide output order.

        Returns:
            An ordered tuple of the applicable OpenQuestion instances,
            in fixed RISK-1 through RISK-9 order (never by dict/set
            iteration or insertion order, and never by the input
            collections' own order).
        """
        findings_by_check_name = {
            finding.check_name: finding for finding in findings
        }
        profiles_by_profiler_name = {
            profile.profiler_name: profile for profile in profiles
        }

        selected: list[OpenQuestion] = []

        chromosome_label_inventory = profiles_by_profiler_name.get(
            _CHROMOSOME_LABEL_PROFILER_NAME
        )
        if isinstance(chromosome_label_inventory, ChromosomeLabelInventory):
            selected.append(_RISK_1_QUESTION)
            if self._has_non_conventional_chromosome_label(
                chromosome_label_inventory
            ):
                selected.append(_RISK_2_QUESTION)

        missing_value_finding = findings_by_check_name.get(
            _MISSING_VALUE_SCANNER_NAME
        )
        if missing_value_finding is not None and missing_value_finding.count > 0:
            selected.append(_RISK_3_QUESTION)

        duplicate_chr_pos_finding = findings_by_check_name.get(
            _DUPLICATE_CHR_POS_CHECK_NAME
        )
        if (
            duplicate_chr_pos_finding is not None
            and duplicate_chr_pos_finding.count > 0
        ):
            selected.append(_RISK_4_QUESTION)

        genotype_layout_profile = profiles_by_profiler_name.get(
            _GENOTYPE_LAYOUT_CLASSIFIER_NAME
        )
        if isinstance(genotype_layout_profile, GenotypeLayoutProfile):
            selected.append(_RISK_5_QUESTION)

        # RISK-6, RISK-7, RISK-8, RISK-9: standing questions, always
        # selected. None of them concerns a property carried by any
        # Finding or Profile this system produces (strand-orientation
        # claims, encoding-content provenance, data-sensitivity
        # handling, and RSID-value provenance respectively), so none is
        # gated on `findings`/`profiles` content.
        selected.append(_RISK_6_QUESTION)
        selected.append(_RISK_7_QUESTION)
        selected.append(_RISK_8_QUESTION)
        selected.append(_RISK_9_QUESTION)

        return tuple(selected)

    def _has_non_conventional_chromosome_label(
        self, chromosome_label_inventory: ChromosomeLabelInventory
    ) -> bool:
        """Determine whether `chromosome_label_inventory` contains at
        least one observed label outside the conventional human
        karyotype vocabulary (RISK-2's applicability test).

        Args:
            chromosome_label_inventory: An already-produced
                ChromosomeLabelInventory to inspect, read-only.

        Returns:
            True if any label in `label_counts` falls outside the
            conventional numeric autosome range (1-22) plus the
            sex/mitochondrial labels (X, Y, MT); False otherwise,
            including when `label_counts` is empty.
        """
        return any(
            label not in _CONVENTIONAL_CHROMOSOME_LABELS
            for label, _count in chromosome_label_inventory.label_counts
        )