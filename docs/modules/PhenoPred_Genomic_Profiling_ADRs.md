# PhenoPred — Architecture Decision Records
## Genomic Profiling (FR-10–FR-12)

**Document status:** Accepted — permanent project documentation
**Source of truth:** Genomic Profiling (FR-10–FR-12) Final Architecture Freeze
**Scope:** These records document decisions already approved during the Genomic Profiling architecture review and freeze. They introduce no new architecture and supersede no prior approval, including the Stage 1 Module Approval Record, which remains frozen and unmodified.

---

## ADR-1: GenomicProfiler Protocol Shape

**Status:** Accepted

**Context**

Architecture v1 §10 names `GenomicProfiler` as a domain-defined port ("Given DataRows (+ column layout), produce exactly one Profile") but explicitly defers its exact shape. `interfaces.py`'s own docstring states that `GenomicProfiler` "belongs to modules that have not yet been designed or approved." The existing `QualityCheck` Protocol in the same module provides a directly applicable precedent: a minimal, single-method, data-in/data-out shape, marked PROVISIONAL until validated by more than one implementer, following the same discipline already established for `Detector[T]` (treated as settled only after three independent implementers — `EncodingDetector`, `DelimiterDetector`, `HeaderResolver` — confirmed its shape).

**Decision**

Add a `GenomicProfiler` Protocol to `phenopred/domain/interfaces.py` with the single method:

```
profile(self, data_rows: object, context: object = None) -> object
```

The Protocol is marked PROVISIONAL and is treated as validated only once all three planned implementers (`ChromosomeLabelProfiler`, `GenotypeLayoutClassifier`, `IndelHaploidClassifier`) exist and confirm its shape.

**Consequences**

- All three genomic profilers implement a shared, minimal contract, enabling `ProfileFileUseCase` to invoke them uniformly without depending on their concrete types.
- The Protocol's method signature must not be treated as finally frozen until the third implementer has validated it, mirroring the `Detector[T]`/`QualityCheck` precedent.
- `interfaces.py` gains one new Protocol; `Detector[T]` and `QualityCheck` remain unchanged.

**Alternatives Considered**

- None were separately proposed. The `QualityCheck` Protocol's existing shape and PROVISIONAL-status convention were adopted directly as the applicable precedent, consistent with Architecture v1 §10's requirement that profilers expose a unified interface.

---

## ADR-2: Composite Context Object for IndelHaploidClassifier

**Status:** Accepted

**Context**

`IndelHaploidClassifier` (FR-12) requires two distinct pieces of column-identity context: `designated_column_indices` (to locate the genotype column) and `chromosome_column_index` (to classify haploid/diploid rows on sex/mitochondrial labels). The `GenomicProfiler` Protocol (ADR-1) exposes a single `context` parameter, and the established codebase convention — demonstrated by `MissingValueScanner` (receives only `designated_column_indices`) and `DuplicateRsidCheck` (receives only `rsid_column_index`) — is that a component receives only the narrow subset of `ColumnLayout` it actually needs, never the full object.

An initial proposal justified a new composite context object by direct analogy to `ChrPosColumnIndices`, whose own docstring grounds its existence in protecting against silent role-transposition between two same-typed, interchangeable `int` fields. On review, this specific rationale was found not to transfer: `IndelHaploidClassifier`'s two context values (`Sequence[int]` and `int`) are differently typed and cannot be silently transposed the way two bare ints can. The correct justification is instead: (a) the single-context-slot Protocol shape requires bundling when more than one context value is needed, exactly as it did for `DuplicateChrPosCheck`/`ChrPosColumnIndices`; and (b) the established minimal-context-injection convention rules out passing the full `ColumnLayout`.

**Decision**

Introduce a new value object, `GenotypeChromosomeColumnIndices`, with fields `designated_column_indices: tuple[int, ...]` and `chromosome_column_index: int`, added to `value_objects.py`. Its docstring states the correct justification — Protocol context-bundling and minimal-context injection — and explicitly does not cite role-transposition protection, since that risk does not apply to this type's differently-typed fields.

`ProfileFileUseCase` constructs this object from the relevant `ColumnLayout` fields and passes it to `IndelHaploidClassifier.profile()` as the `context` argument.

**Consequences**

- `IndelHaploidClassifier` never receives the full `ColumnLayout`, preserving the minimal-context-injection convention.
- A new invariant-free, purely descriptive value object is added, following the same minimal value-object approach used elsewhere in the codebase (no construction-time validation; bounds-checking remains the consuming profiler's own runtime concern) without duplicating `ChrPosColumnIndices`'s specific rationale.
- Naming (`GenotypeChromosomeColumnIndices`) preserves parallelism with `ChrPosColumnIndices` and preserves the field name `designated_column_indices` for direct traceability back to `ColumnLayout`.

**Alternatives Considered**

- **Pass the full `ColumnLayout` to `IndelHaploidClassifier`.** Rejected: this would let the profiler reach into `rsid_column_index`, which it has no business touching, and would break the minimal-context discipline every existing quality check follows.
- **Justify the new composite object by analogy to `ChrPosColumnIndices`'s role-transposition rationale.** Rejected: that rationale does not apply, since the two fields are differently typed and cannot be silently swapped; citing it would misrepresent why the type exists.

---

## ADR-3: ProfileFileUseCase / Composition Root Contract Extension

**Status:** Accepted

**Context**

Architecture v1 §5/§6 defines `ProfileFileUseCase`'s pipeline order as ending in "...→ run quality checks → run genomic profiling → build report → serialize." The current frozen Stage 1 implementation's own docstring documents `genomic_profilers` as an accepted-but-never-invoked constructor parameter (currently supplied as an empty tuple `()` by `composition_root.py`), explicitly deferring this exact wiring. The Stage 1 Module Approval Record requires that any change to a frozen Stage 1 component be recorded as a new architecture decision before it is made.

Wiring genomic profiling into the pipeline changes `genomic_profilers` from an unused placeholder constructor argument into an active, mapping-based dependency contract. This is a controlled contract extension, not a purely additive change, since the expected shape of an existing constructor parameter changes.

**Decision**

- `ProfileFileUseCase` gains a new private method, `_run_genomic_profilers(data_rows, column_layout)`, mirroring the structure of the existing `_run_quality_checks()` method: each profiler is looked up by name in `self._genomic_profilers` and invoked with only the minimal context it requires.
- A single new call site is inserted in `execute()`, immediately after the existing `_run_quality_checks()` call.
- The dict returned by `execute()` gains one new key, `"profiles"`.
- The `genomic_profilers` constructor parameter's expected shape changes from an empty tuple to a name-keyed mapping (`"chromosome_label_profiler"`, `"genotype_layout_classifier"`, `"indel_haploid_classifier"`), mirroring the existing `quality_checks` mapping contract.
- `composition_root.py` is extended to construct the three concrete profiler instances and supply this mapping, following its existing `_DEFAULT_*` constant and dict-literal pattern.

**Consequences**

- Stage 1 stability is preserved — existing Stage 1 behavior and frozen components remain unchanged. `ProfileFileUseCase` and `composition_root` receive controlled contract extensions required for FR-10–FR-12 under this ADR.
- Existing steps 1 through 7 of `execute()` (load → encoding → split → delimiter → header → column identity → row parse → quality checks), the exception-translation logic, `_run_quality_checks()` itself, and every existing return-dict key remain unchanged.
- Every existing `_DEFAULT_*` constant, the existing `quality_checks` dict construction, all five existing `QualityCheck` instantiations, and `report_builder=None` remain unchanged in `composition_root.py`.

**Alternatives Considered**

- **Describe the change as "strictly additive."** Rejected as imprecise: although existing Stage 1 behavior is preserved, `genomic_profilers` changes from an unused placeholder into an active mapping-based dependency contract, which is more accurately described as a controlled contract extension.

---

## ADR-4: Deterministic Ordering Discipline for Unbounded Profiler Outputs

**Status:** Accepted

**Context**

Unlike `Finding.examples`/`affected_row_refs`, which are capped at 10 entries and therefore use descending-frequency ordering (in `MissingValueScanner`) to select which entries make the cut, the three genomic-profiling value objects are uncapped — FR-10 requires enumerating every distinct chromosome label, and the length/token distributions are naturally bounded by small key spaces rather than by an arbitrary sample size. An initial proposal carried the descending-frequency ordering convention over to `ChromosomeLabelInventory` by direct analogy to `MissingValueScanner`. On review, this was found not to transfer: frequency-ordering exists specifically to decide sample-cap membership, which does not apply to an uncapped output, and ranking labels by row-count would introduce an interpretive framing (implying importance by frequency) inconsistent with the descriptive-only principle.

NFR-3 requires that identical input always produce identical output on repeated execution, and that no component introduce nondeterminism via unordered collections or iteration order.

**Decision**

- `ChromosomeLabelInventory.label_counts` is ordered by ascending first-observed `DataRow.line_index` — the same neutral ordering basis already used elsewhere in the codebase as a tie-break mechanism (`MalformedRowCheck`, `DuplicateRsidCheck`, `DuplicateChrPosCheck`).
- `GenotypeLayoutProfile`'s length distributions are ordered by ascending numeric length.
- `IndelHaploidProfile.indel_token_counts` is ordered by the constructor-injected token order.
- No frequency-based ordering is used anywhere in genomic profiling.

**Consequences**

- All three profiler outputs are fully deterministic and reproducible under NFR-3, with the ordering basis for each explicitly frozen rather than left to implementation-time discretion.
- No profiler output ordering carries interpretive weight (e.g., no implied ranking of chromosome labels by importance or frequency).
- Ordering rules must be stated explicitly in each affected value object's docstring in `value_objects.py` and reflected in each profiler module's implementation.

**Alternatives Considered**

- **Descending-frequency ordering for `ChromosomeLabelInventory.label_counts`, mirroring `MissingValueScanner`.** Rejected: that convention exists solely to select entries within a 10-item cap, which does not apply to an uncapped enumeration, and would introduce an unwarranted interpretive framing.

---

## ADR-5: layout_kind Classification Boundary and Distribution Coupling

**Status:** Accepted

**Context**

`ColumnLayout.designated_column_indices` cardinality is fully data-driven, derived from whatever configured keywords a file's header happens to match — nothing in `ColumnIdentityResolver` restricts it to `{0, 1, 2}`. An initial proposal for `GenotypeLayoutProfile.layout_kind` defined three states (`two_column_allele`, `single_column_genotype`, `undetermined`) but left the `undetermined` case explicitly triggered only by the zero-designated-columns scenario, leaving cardinalities of three or more unaddressed. This is the kind of unhandled input Architecture v1 §17 identifies as a premature-abstraction risk from only two observed layouts, and the kind of case the mandated neutrality test (§15.2) is intended to catch. It was also left ambiguous whether the length distribution should be computed at all in the undetermined case.

**Decision**

- `layout_kind` is `"two_column_allele"` if and only if `len(designated_column_indices) == 2`.
- `layout_kind` is `"single_column_genotype"` if and only if `len(designated_column_indices) == 1`.
- `layout_kind` is `"undetermined"` for every other count, including 0 and 3 or more.
- `column_length_distributions` is computed unconditionally for however many designated columns exist, fully decoupled from whether a `layout_kind` label could be assigned.

**Consequences**

- Every possible cardinality of `designated_column_indices` is handled without an unhandled-input gap.
- The descriptive length-distribution data is never withheld on account of an ambiguous or absent layout classification, keeping the two concerns independent.
- The mandated neutrality test (Architecture v1 §15.2) must include a synthetic fixture exercising a cardinality other than 0, 1, or 2 to confirm this boundary.

**Alternatives Considered**

- **Trigger `undetermined` only for the zero-designated-columns case, leaving cardinalities of three or more unaddressed.** Rejected: this left a gap that a differently-shaped file could fall through without a defined classification.
- **Withhold `column_length_distributions` when `layout_kind` is `undetermined`.** Rejected: the distribution is purely structural/descriptive and does not depend on a `layout_kind` label to be meaningful or computable.

---

## ADR-6: Dataset Neutrality Language

**Status:** Accepted

**Context**

PhenoPred is an application whose scope is to implement Genomic Profiling FR-10–FR-12 and validate correctness using two evidence datasets: the AncestryDNA raw export and the 23andMe raw export (Build 37). Earlier drafts of the architecture documentation used wording such as "future AncestryDNA/23andMe versions," "support future vendors," or "support all consumer genotype providers." This wording overstates the project's obligations: the two datasets define validation evidence, not the architecture, and the application is not required to support every possible future export format. At the same time, the implementation must remain descriptive-only and must not break when encountering unexpected structural variations, consistent with NFR-5's neutrality requirement.

**Decision**

All docstrings, ADRs, and the eventual Genomic Profiling Module Approval Record use the fixed phrase: *"The implementation should remain robust against unexpected structural variations and should not encode assumptions that are only valid for the two evidence datasets."*

No wording anywhere in genomic-profiling code or documentation references "future AncestryDNA/23andMe versions," "future vendors," "support future vendors," or "all consumer genotype providers." AncestryDNA and 23andMe define validation evidence only; they do not define the architecture.

**Consequences**

- The scope boundary between "validated against these two datasets" and "must support unbounded future formats" is unambiguous in all project documentation.
- Robustness against unexpected structural variation means the implementation must not crash or misbehave on a differently-shaped file — it does not mean the implementation must correctly interpret every possible vendor's semantics.
- This language must be applied consistently across all three profiler module docstrings, `value_objects.py` docstrings, and the eventual Genomic Profiling Module Approval Record.

**Alternatives Considered**

- **Wording implying support for future AncestryDNA/23andMe versions or all consumer genotype providers.** Rejected: this would expand the project's stated obligations beyond what the SRS and Architecture v1 require, framing a general-purpose genomics platform rather than the scoped application PhenoPred is.

---

## ADR-7: Biological Interpretation Language

**Status:** Accepted

**Context**

FR-12 explicitly requires descriptive classifications — haploid count, diploid count, and configured indel-token counts — that are named using biologically-derived terminology. An earlier framing stated "no biological assumptions enter value objects," which is inaccurate: these FR-12-mandated fields are required descriptive observations, not an absence of biologically-named data. At the same time, the descriptive-only principle (Architecture v1 §1: "Descriptive-only genomic profiling... reports facts... without asserting cross-file equivalence or biological meaning") must be preserved and precisely bounded.

**Decision**

Replace any "no biological assumptions enter value objects" framing with: *"Value objects represent required descriptive observations without performing biological interpretation."*

The implementation may report: chromosome labels; genotype lengths; configured token occurrences; haploid/diploid-style length observations. The implementation must not: map chromosome labels biologically; infer ancestry; explain biological causes; reconcile vendor-specific meanings.

**Consequences**

- The distinction between "reporting a named, FR-12-mandated observation" and "performing biological interpretation" is stated precisely, avoiding both overclaiming (no biologically-named fields at all) and scope creep (inferring meaning beyond what is observed).
- This language must be applied consistently across all three profiler module docstrings, `value_objects.py` docstrings (especially `IndelHaploidProfile`), and the eventual Genomic Profiling Module Approval Record.
- No profiler may map, translate, or reconcile chromosome codes across files (consistent with RISK-1/RISK-2), and no profiler may assert biological meaning for any observed token beyond counting its presence (consistent with FR-9's established "without judging the cause" framing, extended here to FR-12's tokens).

**Alternatives Considered**

- **"No biological assumptions enter value objects."** Rejected as inaccurate: FR-12 itself mandates descriptive classifications (haploid/diploid/indel counts) that use biologically-derived terminology; an absolute claim of "no biological assumptions" misrepresents what these required fields are.

---

*This document consolidates ADR-1 through ADR-7 as approved during the Genomic Profiling (FR-10–FR-12) architecture review and Final Architecture Freeze. It introduces no new decisions and supersedes no prior approval, including the Stage 1 Module Approval Record, which remains the frozen engineering baseline. Implementation may proceed once this document is filed as permanent project documentation.*