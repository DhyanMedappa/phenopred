# Architecture Decision Record: Column-Identity Input Contract for DuplicateChrPosCheck (FR-9)

**Status:** Final — frozen reference for future module integration
**Architecture version/reference:** PhenoPred Architecture v1 (Approved)
**Traceability references:** SRS FR-9, OUT-7, NFR-3, NFR-5; `interfaces.py` `QualityCheck` Protocol; `DuplicateHeaderCheck` Module Approval and Handoff Record §8 (deferred decision); `MissingValueScanner` ADR 1 (Column-Identity Input Contract) and `DuplicateRsidCheck` ADR 1 (Column-Identity Input Contract) — cited for their precedent only, not extended by either

---

### 1. Decision Context

FR-9 requires the system to "detect and report (chromosome, position) pairs that occur more than once within a single file." As with FR-6's designated genotype/allele columns and FR-8's RSID column, no frozen artifact defines how a field position earns the designation "the chromosome column" or "the position column." `HeaderInfo.resolved_columns` supplies only literal, file-specific column-name strings (e.g. `"chromosome"` and `"position"` in both evidenced datasets), and the mechanism that would map a header name to a semantic role is the same shared, cross-cutting deferred decision already recorded in `DuplicateHeaderCheck`'s Module Approval and Handoff Record §8 ("Column-name-resolution mechanism for MissingValueScanner, DuplicateRsidCheck, DuplicateChrPosCheck") and left explicitly open by `MissingValueScanner`'s Architecture Freeze Record and by `DuplicateRsidCheck`'s own Architecture Freeze Record §8. That mechanism affects three checks, not this module alone, and is not resolved here.

FR-9 differs in cardinality and shape from each frozen precedent. `MissingValueScanner` (FR-6) consumes a variable-length, homogeneous collection of designated columns — any number of columns, each playing the same role (a tally source). `DuplicateRsidCheck` (FR-8) consumes exactly one column — a single semantic role. FR-9 names exactly **two** semantic roles — "chromosome" and "position" — that are neither variable in count nor interchangeable with one another: a duplicate is defined over the *pair*, not over either column alone, and the two roles are not substitutable (a value observed at the chromosome position and a value observed at the position position do not mean the same thing, unlike `MissingValueScanner`'s homogeneous designated columns, which are all read for the same purpose). This ADR resolves only `DuplicateChrPosCheck`'s own dependency boundary and input contract, including whether its context shape can or should mirror either frozen sibling's shape, or must take a form appropriate to a fixed two-role composite key.

---

### 2. Decision Drivers

The final rule MUST satisfy:

1. **FR-9 compatibility** — the check must operate on the correct chromosome and position columns regardless of file layout, without assuming fixed field positions.
2. **NFR-5 schema neutrality** — must not hard-code or otherwise fix a file-specific column-name vocabulary anywhere inside this module.
3. **Separation of concerns** — column-name semantic resolution is not a `QualityCheck`'s job; it remains outside `DuplicateChrPosCheck`'s boundary, consistent with `HeaderResolver`'s (FR-3) exclusive ownership of header/column-name interpretation.
4. **Consistency with frozen precedent** — `MalformedRowCheck` forbids any `HeaderInfo` dependency to preserve schema neutrality; `DuplicateHeaderCheck` consumes `HeaderInfo` only as an already-resolved value; `MissingValueScanner` consumes pre-resolved column indices as a plain `Sequence[int]`; `DuplicateRsidCheck` consumes a single pre-resolved column index as a plain `int`. `DuplicateChrPosCheck` must follow the same "pre-resolved, opaque positional data" pattern, but is not obligated to copy either sibling's specific shape if FR-9's own cardinality and role structure differ.
5. **Independence from the shared, still-open deferred decision** (`DuplicateHeaderCheck` record §8; `DuplicateRsidCheck` Architecture Freeze Record §8) — this ADR must not presuppose or foreclose how that broader mechanism is eventually resolved, and, per `DuplicateRsidCheck`'s Freeze Record §8, is free to leave its own context shape incompatible with `DuplicateRsidCheck`'s single-`int` context if FR-9's cardinality warrants a different shape.
6. **Minimal abstraction, matched to actual cardinality and role structure** — the contract shape should reflect FR-9's own fixed, two-role, non-interchangeable composite-key nature rather than defaulting to a homogeneous multi-column shape (`MissingValueScanner`'s) or a single-column shape (`DuplicateRsidCheck`'s) borrowed from a different requirement without justification.
7. **No uncaught exceptions from expected input shapes** — per Architecture v1 §13.2 and the precedent established by `MalformedRowCheck`, `MissingValueScanner`, and `DuplicateRsidCheck`, rows of varying field-count width are an expected, ordinary member of any `DataRow` collection a `QualityCheck` consumes, and an out-of-bounds column reference (for either role) must not raise.
8. **Full-scan requirement** — per Architecture v1's risk register (Section 15, "Sample-based detection missing rare structural variation," which names FR-8/FR-9 duplicate detection explicitly), FR-9 is a full-file requirement; the check must scan every row, not a sample.
9. **Testability** — the module must remain unit-testable with plain data in/out, no file I/O, no mocking framework required.

---

### 3. Considered Alternatives

**Option A: Hardcoded chromosome/position column-name/position inside `DuplicateChrPosCheck`**
Risks: Bakes in fixed field positions or names; both evidenced datasets happen to place `chromosome` and `position` at the same relative positions, but nothing in the SRS or architecture guarantees this for an unseen file. Violates NFR-5 identically to the rejected equivalent option in `MissingValueScanner`'s and `DuplicateRsidCheck`'s own ADR 1s.
NFR-5 compatibility: Violated.

**Option B: `DuplicateChrPosCheck` receives whole `HeaderInfo` and resolves the chromosome and position columns internally**
Risks: Relocates, rather than resolves, the same unresolved column-naming problem into a to-be-frozen module — the identical objection raised and rejected in `MissingValueScanner`'s ADR 1 (its Option D) and `DuplicateRsidCheck`'s ADR 1 (its Option B).
Rejected for the same reason.

**Option C: `DuplicateChrPosCheck` receives a single, pre-resolved `Sequence[int]`, mirroring `MissingValueScanner`'s contract exactly**
Advantages: Structural consistency with an already-frozen sibling; reuses a proven shape.
Risks: `MissingValueScanner`'s `Sequence[int]` models an arbitrary number of columns that all play the *same* role (each is a tally source contributing independently to one combined frequency count). FR-9's two columns play *different*, fixed, non-interchangeable roles — a value observed at "the chromosome position" is only meaningful when paired with the value observed at "the position position" *for that same row*; the two are never tallied independently of one another. A bare `Sequence[int]` would also fail to fix the pair's cardinality at exactly two, silently admitting a caller error (a one-element or three-element sequence) that the requirement's own text never contemplates. Adopting this shape would carry forward an ambiguity FR-9 does not describe — analogous to the ambiguity `DuplicateRsidCheck`'s ADR 1 already rejected (its Option C) for the reverse reason (there, a plural shape was rejected for a singular requirement; here, a same-role shape is rejected for a dual-but-distinct-role requirement).

**Option D: `DuplicateChrPosCheck` receives a single, pre-resolved 2-element tuple `tuple[int, int]` (e.g. `(chromosome_column_index, position_column_index)`), mirroring the exploratory notebook's own tuple-keyed pairing convention**
Advantages: Fixes cardinality at exactly two, matching FR-9's own structure; no new value object is introduced; reuses a bare primitive composite, consistent with `DataRow`'s own precedent of bare primitives for positional data.
Risks: An anonymous positional tuple carries no self-documenting distinction between its two roles. Because the two roles are asymmetric and non-interchangeable (unlike `MissingValueScanner`'s homogeneous list), a caller that silently transposes the two elements — passing `(position_column_index, chromosome_column_index)` — produces no type error, no bounds error, and no visible signal at the call site or under structural inspection; the check would silently compare the wrong pair of columns. This is a materially different risk from `MissingValueScanner`'s `Sequence[int]`, where every element plays an identical role and transposition has no semantic consequence.

**Option E: `DuplicateChrPosCheck` receives two separate, plain, distinctly-named `int` parameters — `chromosome_column_index: int` and `position_column_index: int` — as two discrete arguments to `check()`, rather than bundled into a single tuple or generic `context` object**
Advantages: Matches FR-9's own cardinality and role structure exactly (exactly two fixed, distinct, non-interchangeable semantic roles forming one composite pairing key); eliminates the positional-transposition risk identified in Option D by naming each role explicitly, both at the call site and under structural/AST inspection; introduces no new value object, interface, or abstraction — both parameters remain bare primitive `int`s, consistent with `DataRow.line_index`'s own precedent that positional/structural data needs no invariant-carrying wrapper type.
Risks (identified on further review — see the interface-consistency review below): breaks the uniform, at-most-one-extra-argument shape every existing `QualityCheck` implementer follows (`MalformedRowCheck` takes none; `DuplicateHeaderCheck`, `MissingValueScanner`, and `DuplicateRsidCheck` each take exactly one), and departs from the "Given DataRows (+ context)" — singular — framing Architecture v1 §10 itself uses to describe the `QualityCheck` interface; forces any future `QualityCheckRunner` to special-case this check's call arity rather than dispatching uniformly across all registered checks; does not scale cleanly if a future check ever needs a third piece of context, since that would require another `check()` signature change rather than a field addition to an existing type.
FR-9/NFR-5 compatibility: Satisfied on cardinality and misuse-risk grounds alone, but inferior to Option F once interface uniformity and Architecture v1 §10 are weighed. Superseded by Option F below.

**Option F (selected): `DuplicateChrPosCheck` receives a single, pre-resolved, immutable, named-field value object — `ChrPosColumnIndices` — via one context-equivalent parameter, mirroring `DuplicateHeaderCheck`'s (`HeaderInfo`), `MissingValueScanner`'s (`Sequence[int]`), and `DuplicateRsidCheck`'s (`int`) identical "one context slot, narrowed by concrete type" pattern**
Advantages: Preserves, rather than breaks, the uniform arity every existing `QualityCheck` implementer shares (`data_rows` plus exactly one context argument) and the literal "Given DataRows (+ context)" framing of Architecture v1 §10; keeps any future `QualityCheckRunner` free of check-specific call-arity special-casing, since invocation remains `check(data_rows, context)` for every registered check regardless of how much internal structure that check's own context type carries; eliminates the positional-transposition risk of a bare `tuple[int, int]` (Option D) via named fields, exactly as effectively as Option E's named parameters, but without paying Option E's uniformity cost; consistent with the project's own established convention (`value_objects.py`: `EncodingProfile`, `Delimiter`, `CommentBlock`, `HeaderInfo`, `Finding`) of representing small, immutable, composite descriptive data as a frozen, slotted dataclass rather than a bare tuple or a widened method signature; matched exactly to FR-9's own cardinality (two fixed, non-interchangeable roles) — no more structure than that, no invariant-checking behavior, no methods; extends, rather than abandons, the same narrowing principle FR-6's and FR-8's frozen ADRs each already apply (`Sequence[int]` for a same-role many-columns case, `int` for a single-column case, and now a two-named-field value object for a two-different-roles case).
Risks: Introduces one new value object where FR-6's and FR-8's ADRs each introduced none — but this is a direct, justified consequence of FR-9's own cardinality (two distinct, non-interchangeable roles) rather than abstraction added without cause; the object carries no behavior and no invariant beyond what a bare primitive would also lack, so the cost is a single small, static, immutable data record, not a new subsystem.
FR-9/NFR-5/Architecture v1 compatibility: Fully satisfied, and additionally preserves interface uniformity that Option E would have broken.

**New value object — `ChrPosColumnIndices` (introduced by this ADR):**

Introduced into `phenopred/domain/value_objects.py`, alongside `EncodingProfile`, `Delimiter`, `CommentBlock`, `HeaderInfo`, and `Finding`.

```
@dataclass(frozen=True, slots=True)
class ChrPosColumnIndices:
    chromosome_column_index: int
    position_column_index: int
```
This value object carries no behavior and no `__post_init__` invariant, consistent with `HeaderInfo`, `Finding`, `Delimiter`, `CommentBlock`, and `EncodingProfile` (none of which enforce a construction-time invariant either) — bounds-validity per row remains entirely `DuplicateChrPosCheck`'s own runtime concern (§4, "Malformed-row handling" below), never this value object's. Its sole purpose is to let `QualityCheck`'s single context slot carry two named, non-interchangeable roles without ambiguity, and it introduces no dependency on `HeaderInfo`, `HeaderResolver`, or any other module. Whether a future ADR ever adds an invariant (e.g. rejecting negative indices, or the two indices being equal) is explicitly not decided here.

---

### 3.1 Interface-Consistency Review (Two Parameters vs. Single Context Object)

Before finalizing this ADR, the choice between Option E (two separate `int` parameters) and Option F (a single named-field value object) was re-examined specifically against `QualityCheck` interface consistency, independent of which option was drafted first:

- **Consistency with the `QualityCheck` pattern across the project:** every existing implementer (`MalformedRowCheck`, `DuplicateHeaderCheck`, `MissingValueScanner`, `DuplicateRsidCheck`) takes zero or one extra argument beyond `data_rows`, never two. Option F continues that pattern; Option E would be the first departure from it.
- **Consistency with Clean Architecture / interface uniformity:** the reason `QualityCheck` exists as a port is so a future `QualityCheckRunner` can invoke every registered check uniformly without knowing its concrete type (Dependency Inversion, Architecture v1 §9/§10). A single context slot per check preserves that uniform `check(data_rows, context)` invocation regardless of how much internal structure a given check's context carries; two bare parameters would require the runner to know each check's specific call arity, reintroducing the coupling the interface exists to remove.
- **Semantic clarity and risk of misuse:** both options solve the transposition risk a bare `tuple[int, int]` (Option D) would carry — Option E via named parameters, Option F via named fields on an immutable value object. Neither option has an advantage over the other on this axis alone.
- **Future maintainability:** Option F isolates any future growth in FR-9's context (should it ever occur) to a field addition on `ChrPosColumnIndices`; Option E would require a `check()` signature change, which is a wider-blast-radius change for any caller (including a future `QualityCheckRunner`).
- **Adherence to Architecture v1:** §10's own description of the interface — "Given DataRows (+ context)" — is written in the singular. Option F matches that description literally; Option E does not.
- **Consistency with the frozen FR-6 and FR-8 ADRs:** both prior ADRs narrow `QualityCheck`'s single context parameter to a concrete type matched to their own cardinality (`Sequence[int]`; `int`). Option F extends that same principle to FR-9's two-role cardinality via a new concrete type; Option E abandons the "one context slot, narrowed by type" principle rather than extending it.

**Conclusion:** Option F is architecturally superior on interface-uniformity, maintainability, and Architecture-v1-adherence grounds, while matching Option E exactly on semantic clarity and misuse-risk. Option E is not retained.

---

### 4. Final Architecture Decision

**The selected rule is Option F — `DuplicateChrPosCheck` receives a single, already-resolved `ChrPosColumnIndices` value object, carrying both the chromosome and position field-position indices as named fields, via the `QualityCheck` interface's context parameter.**

**Concretely:**
```
DuplicateChrPosCheck.check(
    data_rows: Sequence[DataRow],
    chr_pos_columns: ChrPosColumnIndices,
) -> Finding
```

**Resolution ownership.** The logic that derives `chr_pos_columns.chromosome_column_index` and `chr_pos_columns.position_column_index` from `HeaderInfo.resolved_columns` (or any other source), and that constructs the `ChrPosColumnIndices` instance itself, is **domain-layer work**, consistent with Architecture v1's module table confining `application/profile_file_use_case.py` to pure sequencing ("depends only on domain interfaces... contains no business logic"). This ADR does not design that resolution logic, does not name a concrete component for it, and does not expand the still-open, shared deferred decision recorded in `DuplicateHeaderCheck`'s approval record §8 or `DuplicateRsidCheck`'s Architecture Freeze Record §8 — it fixes only that, wherever and however that resolution eventually happens, it must happen in the domain layer and must hand `DuplicateChrPosCheck` one plain, already-resolved `ChrPosColumnIndices` instance.

**Malformed-row handling.** Consistent with the same principle `MissingValueScanner`'s ADR 1 and `DuplicateRsidCheck`'s ADR 1 each established for their own designated column(s), extended to the composite-pair case:

> A row contributes one (chromosome, position) pair observation only if **both** `chr_pos_columns.chromosome_column_index < len(row.fields)` and `chr_pos_columns.position_column_index < len(row.fields)` hold. If either index is outside the bounds of a particular `DataRow`'s `fields` tuple, that row contributes **no observation** for chromosome-position-duplicate detection — the pair is not partially formed from whichever single field happens to be in bounds. No exception is raised. This is normal data-quality input, not an error condition, consistent with Architecture v1 §13.2's rule that data-quality conditions are always represented as Finding data, never as exceptions.

**Full-scan requirement.** Per Architecture v1's risk register, `DuplicateChrPosCheck` must scan the entire `data_rows` collection; no sampling of rows is permitted, unlike the sample-based detectors (encoding/delimiter) the same risk entry distinguishes.

**Justification:**

- Narrows `QualityCheck`'s generic `context: object = None` extension point to a single concrete type — `ChrPosColumnIndices` — exactly as `DuplicateHeaderCheck` narrows it to `HeaderInfo`, `MissingValueScanner` narrows it to `Sequence[int]`, and `DuplicateRsidCheck` narrows it to a single `int`. No new interface is introduced, and the check's external call arity (`data_rows` plus exactly one context argument) stays identical to every other frozen `QualityCheck` implementer, preserving the interface uniformity a bare two-parameter signature would have broken (§3.1).
- `ChrPosColumnIndices` is a single new value object, added deliberately and only because FR-9's cardinality — two fixed, non-interchangeable roles forming one composite key — cannot be correctly or safely represented by a bare primitive: a bare `int` under-represents it (wrong cardinality), a `Sequence[int]` misrepresents it (implies interchangeable same-role columns), and a bare `tuple[int, int]` under-represents it (no protection against role transposition). The new type is scoped to exactly FR-9's own two-role cardinality, carries no behavior and no invariant, and mirrors the project's existing convention (`value_objects.py`) of representing small immutable composite descriptors as frozen, slotted dataclasses.
- `DuplicateChrPosCheck` performs no column-name matching, no header interpretation, and carries no dependency on `HeaderInfo`, `HeaderResolver`, or any `GenomicProfiler` — fully preserving NFR-5 and the module's schema neutrality.
- The both-in-bounds rule closes a real gap without introducing any defensive machinery beyond a single, deterministic joint-bounds condition, reusing the identical "no exception, no observation" pattern `MissingValueScanner`'s ADR 1 and `DuplicateRsidCheck`'s ADR 1 already established, extended (not redesigned) to cover a two-field composite key.

**Rejected alternatives, briefly:** Option A was rejected for hard-coding a fixed vocabulary/position in violation of NFR-5. Option B was rejected for relocating, not resolving, the ambiguity into frozen code. Option C was rejected for importing an unjustified same-role, unfixed-cardinality shape that does not reflect FR-9's fixed two-distinct-role structure. Option D was rejected for the silent role-transposition risk inherent in an unlabeled positional pair. Option E was rejected, on further interface-consistency review (§3.1), for breaking the uniform single-context-argument shape every other `QualityCheck` implementer follows and for departing from Architecture v1 §10's own singular "(+ context)" framing, despite otherwise satisfying FR-9's cardinality and misuse-risk concerns.

---

### 5. Formal Rule Specification

**Input**
- `data_rows: Sequence[DataRow]` — as produced by `RowParser`.
- `chr_pos_columns: ChrPosColumnIndices` — a single, already-resolved value object carrying two named field-position indices: `chromosome_column_index` (identifying this file's chromosome column) and `position_column_index` (identifying this file's position column), both already resolved by the caller.
- `DuplicateChrPosCheck` treats both of `chr_pos_columns`' fields as opaque, pre-validated positional data and performs no resolution or validation of either beyond bounds-checking per row.

**Process**
1. `DuplicateChrPosCheck` performs no resolution, name-matching, or interpretation of `chr_pos_columns.chromosome_column_index` or `chr_pos_columns.position_column_index` beyond using each to index into `row.fields`.
2. For each row: if `chr_pos_columns.chromosome_column_index < len(row.fields)` **and** `chr_pos_columns.position_column_index < len(row.fields)`, the pair `(row.fields[chr_pos_columns.chromosome_column_index], row.fields[chr_pos_columns.position_column_index])` is one observation of a (chromosome, position) pair at that row; otherwise, that row contributes no observation, and no exception is raised.
3. The full, unsampled `data_rows` collection is scanned; no row is skipped for reasons other than the joint out-of-bounds condition in step 2.

**Output**
Governed by the future ADR 2 ("Finding Output Mapping for DuplicateChrPosCheck"), not designed in this document.

---

### 6. Architecture Impact

**Unchanged**
- `QualityCheck` Protocol (`interfaces.py`) — used exactly as designed, not modified.
- `HeaderResolver`, `HeaderInfo`, `RowParser`, `DataRow` — no changes.
- Existing module boundaries and contracts of `DuplicateHeaderCheck`, `MalformedRowCheck`, `MissingValueScanner`, `DuplicateRsidCheck` — untouched, not reopened.
- `DuplicateRsidCheck`'s own single-`int` context shape — untouched; this ADR does not retrofit it to use `ChrPosColumnIndices` or any other new type.

**Resolved**
- `DuplicateChrPosCheck`'s own dependency boundary, input contract (one new value object, `ChrPosColumnIndices`, carrying two named `int` fields — not two bare parameters, not a `Sequence[int]`, and not an anonymous tuple), and malformed-row handling rule.
- The previously-open question, recorded in `DuplicateRsidCheck`'s Architecture Freeze Record §8, of "whether `DuplicateChrPosCheck`'s own eventual context shape will be compatible with [`DuplicateRsidCheck`'s single-`int` context]" — answered here: the two context *types* differ (`int` vs. `ChrPosColumnIndices`), reflecting FR-9's two-distinct-role cardinality versus FR-8's single-role cardinality, but both remain a single context *argument*, preserving the uniform `check(data_rows, context)` arity every `QualityCheck` implementer shares.
- The interface-consistency question of two parameters vs. one context object (§3.1), resolved in favor of one context object.

**Explicitly NOT resolved (remains open, by design)**
- The shared column-name-to-role resolution mechanism named in `DuplicateHeaderCheck`'s record §8, affecting `MissingValueScanner`, `DuplicateRsidCheck`, and `DuplicateChrPosCheck` alike.
- The Finding output mapping for `DuplicateChrPosCheck` (reserved for a future ADR 2).
- Whether `ChrPosColumnIndices` should ever carry a construction-time invariant (e.g. non-negativity, or disallowing equal indices) — left unaddressed, consistent with the equally invariant-free precedent of `HeaderInfo`, `Finding`, `Delimiter`, `CommentBlock`, and `EncodingProfile`.

---

### 7. Testing Implications

The future `DuplicateChrPosCheck` test suite must, at minimum, cover:

1. `chr_pos_columns.chromosome_column_index` and `chr_pos_columns.position_column_index` both within bounds for all rows; no duplicated pairs present.
2. Both indices within bounds for all rows; duplicated pairs present.
3. Either index out of bounds for some, but not all, rows in the collection (mixed valid-width and short rows) — confirms no exception and correct partial-observation behavior (the row contributes no observation, not a half-formed one).
4. Both indices out of bounds for every row.
5. `chromosome_column_index` in bounds but `position_column_index` out of bounds for a row (and the reverse) — confirms the joint-bounds rule excludes the row entirely rather than substituting a placeholder for the missing half of the pair.
6. Repeated execution produces identical results (NFR-3).
7. No dependency on `HeaderInfo`, `HeaderResolver`, or any `GenomicProfiler` — verified via structural AST-based import checks, mirroring `MalformedRowCheck`'s, `DuplicateHeaderCheck`'s, `MissingValueScanner`'s, and `DuplicateRsidCheck`'s precedent.
8. `data_rows` and `chr_pos_columns` (and its two fields) are never mutated; individual `DataRow` instances are never mutated.
9. Full, unsampled scan confirmed (no truncation of the row population itself, as distinct from any bounded sample governed by the future ADR 2).
10. `ChrPosColumnIndices` construction and field access behave as a plain, immutable, named-field record — no behavior beyond attribute access is exercised or expected.

---

### 8. Final ADR Status

**Decision:** Accepted

**Implementation:** Not authorized by this ADR alone; implementation requires this ADR together with the future ADR 2 ("Finding Output Mapping for DuplicateChrPosCheck").

**Scope:** This ADR resolves `DuplicateChrPosCheck`'s column-identity input contract and malformed-row handling only. It does not resolve the shared column-name-resolution mechanism, does not design any resolver component, does not design the Finding output mapping, and does not introduce unrelated architecture changes.
