# Architecture Decision Record: Column-Identity Input Contract for DuplicateRsidCheck (FR-8)

**Status:** Final — frozen reference for future module integration
**Architecture version/reference:** PhenoPred Architecture v1 (Approved)
**Traceability references:** SRS FR-8, OUT-7, NFR-3, NFR-5; `interfaces.py` `QualityCheck` Protocol; `DuplicateHeaderCheck` Module Approval and Handoff Record §8 (deferred decision); `MissingValueScanner` ADR 1 (Column-Identity Input Contract) — cited for its precedent only, not extended by it

---

### 1. Decision Context

FR-8 requires the system to "detect and report RSID values that occur more than once within a single file." As with FR-6's "designated genotype/allele columns," no frozen artifact defines how a field position earns the designation "the RSID column." `HeaderInfo.resolved_columns` supplies only literal, file-specific column-name strings (e.g. `"rsid"` in both evidenced datasets), and the mechanism that would map a header name to a semantic role is the same shared, cross-cutting deferred decision already recorded in `DuplicateHeaderCheck`'s Module Approval and Handoff Record §8 ("Column-name-resolution mechanism for MissingValueScanner, DuplicateRsidCheck, DuplicateChrPosCheck") and left explicitly open by `MissingValueScanner`'s own Architecture Freeze Record. That mechanism affects three future checks, not this module alone, and is not resolved here.

Unlike FR-6, which names "designated genotype/allele column**s**" (plural, potentially several columns per file), FR-8 concerns exactly one semantic role — a single RSID column — per file. This ADR resolves only `DuplicateRsidCheck`'s own dependency boundary and input contract, including whether its context shape should mirror `MissingValueScanner`'s `Sequence[int]` or take a narrower form appropriate to a single-column requirement.

---

### 2. Decision Drivers

The final rule MUST satisfy:

1. **FR-8 compatibility** — the check must operate on the correct column regardless of file layout, without assuming a fixed field position.
2. **NFR-5 schema neutrality** — must not hard-code or otherwise fix a file-specific column-name vocabulary anywhere inside this module.
3. **Separation of concerns** — column-name semantic resolution is not a `QualityCheck`'s job; it remains outside `DuplicateRsidCheck`'s boundary, consistent with `HeaderResolver`'s (FR-3) exclusive ownership of header/column-name interpretation.
4. **Consistency with frozen precedent** — `MalformedRowCheck` forbids any `HeaderInfo` dependency to preserve schema neutrality; `DuplicateHeaderCheck` consumes `HeaderInfo` only as an already-resolved value; `MissingValueScanner` consumes pre-resolved column indices as a plain `Sequence[int]`. `DuplicateRsidCheck` must follow the same "pre-resolved, opaque positional data" pattern, but is not obligated to copy `MissingValueScanner`'s specific shape if FR-8's own cardinality differs.
5. **Independence from the shared, still-open deferred decision** (`DuplicateHeaderCheck` record §8) — this ADR must not presuppose or foreclose how that broader mechanism, or its use by `DuplicateChrPosCheck`, is eventually resolved.
6. **Minimal abstraction, matched to actual cardinality** — the contract shape should reflect FR-8's own single-column nature rather than defaulting to a multi-column shape borrowed from a different requirement without justification.
7. **No uncaught exceptions from expected input shapes** — per Architecture v1 §13.2 and the precedent established by `MalformedRowCheck` and `MissingValueScanner`, rows of varying field-count width are an expected, ordinary member of any `DataRow` collection a `QualityCheck` consumes, and an out-of-bounds column reference must not raise.
8. **Full-scan requirement** — per Architecture v1's risk register (Section 15, "Sample-based detection missing rare structural variation"), FR-8 is a full-file requirement; the check must scan every row, not a sample.
9. **Testability** — the module must remain unit-testable with plain data in/out, no file I/O, no mocking framework required.

---

### 3. Considered Alternatives

**Option A: Hardcoded RSID column-name/position inside `DuplicateRsidCheck`**
Risks: Bakes in a fixed field position or name; both evidenced datasets happen to place `rsid` first, but nothing in the SRS or architecture guarantees this for an unseen file. Violates NFR-5 identically to the rejected equivalent option in `MissingValueScanner`'s ADR 1.
NFR-5 compatibility: Violated.

**Option B: `DuplicateRsidCheck` receives whole `HeaderInfo` and resolves the RSID column internally**
Risks: Relocates, rather than resolves, the same unresolved column-naming problem into a to-be-frozen module — the identical objection raised and rejected in `MissingValueScanner`'s ADR 1 (its Option D).
Rejected for the same reason.

**Option C: `DuplicateRsidCheck` receives a pre-resolved `Sequence[int]`, mirroring `MissingValueScanner`'s contract exactly**
Advantages: Structural consistency with an already-frozen sibling; reuses a proven shape.
Risks: FR-8 concerns exactly one semantic role (the RSID column), not "zero, one, or more" designated columns as FR-6 does. Adopting a sequence shape here would silently invite an ambiguous case FR-8 does not describe — what does it mean to scan "the RSID columns" (plural) for duplicates, when the requirement and both evidenced datasets describe a single column? Carrying that ambiguity forward without justification is not a neutral choice; it manufactures a question FR-8 never poses.

**Option D: `DuplicateRsidCheck` receives a single, pre-resolved `int` field-position index via the `QualityCheck` interface's `context` parameter**
Advantages: Matches FR-8's own single-column cardinality exactly; uses the same already-reserved extension point `interfaces.py`'s `QualityCheck` Protocol anticipates (its own docstring names "column-identity context" as an illustrative example, satisfied here by a narrower type than `MissingValueScanner`'s); `DuplicateRsidCheck` carries zero opinion about column names or meaning, mirroring `DuplicateHeaderCheck`'s and `MissingValueScanner`'s identical "operate only on already-resolved positions" stance. No new value object is needed: a bare `int` carries no invariant beyond what `DataRow.line_index` already models.
FR-8/NFR-5/Architecture v1 compatibility: Fully satisfied.

---

### 4. Final Architecture Decision

**The selected rule is Option D — `DuplicateRsidCheck` receives a single, already-resolved RSID column field-position index via the `QualityCheck` interface's `context` parameter, as a plain `int`.**

**Concretely:**
```
DuplicateRsidCheck.check(
    data_rows: Sequence[DataRow],
    rsid_column_index: int,
) -> Finding
```

**Resolution ownership.** The logic that derives `rsid_column_index` from `HeaderInfo.resolved_columns` (or any other source) is **domain-layer work**, consistent with Architecture v1's module table confining `application/profile_file_use_case.py` to pure sequencing ("depends only on domain interfaces... contains no business logic"). This ADR does not design that resolution logic, does not name a concrete component for it, and does not expand the still-open, shared deferred decision recorded in `DuplicateHeaderCheck`'s approval record §8 — it fixes only that, wherever and however that resolution eventually happens, it must happen in the domain layer and must hand `DuplicateRsidCheck` a plain, already-resolved `int`.

**Malformed-row handling.** Consistent with the same principle `MissingValueScanner`'s ADR 1 established for its own designated columns:

> If `rsid_column_index` is outside the bounds of a particular `DataRow`'s `fields` tuple (i.e. `rsid_column_index >= len(row.fields)`), that row contributes **no observation** for RSID-duplicate detection. No exception is raised. This is normal data-quality input, not an error condition, consistent with Architecture v1 §13.2's rule that data-quality conditions are always represented as Finding data, never as exceptions.

**Full-scan requirement.** Per Architecture v1's risk register, `DuplicateRsidCheck` must scan the entire `data_rows` collection; no sampling of rows is permitted, unlike the sample-based detectors (encoding/delimiter) the same risk entry distinguishes.

**Justification:**

- Narrows `QualityCheck`'s generic `context: object = None` parameter into a concrete type, exactly as `DuplicateHeaderCheck` narrows it to `HeaderInfo` and `MissingValueScanner` narrows it to `Sequence[int]` — no new interface or abstraction is introduced.
- `rsid_column_index` is a plain `int` — no new named value object, consistent with `DataRow`'s own precedent of using bare primitives for positional/structural data with no invariant beyond bounds, and correctly scoped to FR-8's single-column cardinality rather than importing an unjustified plural shape from a different requirement.
- `DuplicateRsidCheck` performs no column-name matching, no header interpretation, and carries no dependency on `HeaderInfo`, `HeaderResolver`, or any `GenomicProfiler` — fully preserving NFR-5 and the module's schema neutrality.
- The out-of-bounds rule closes a real gap without introducing any defensive machinery beyond a single, deterministic skip condition, reusing the identical pattern `MissingValueScanner`'s ADR 1 already established rather than inventing a new one.

**Rejected alternatives, briefly:** Option A was rejected for hard-coding a fixed vocabulary/position in violation of NFR-5. Option B was rejected for relocating, not resolving, the ambiguity into frozen code. Option C was rejected for importing an unjustified multi-column ambiguity FR-8's own text does not describe.

---

### 5. Formal Rule Specification

**Input**
- `data_rows: Sequence[DataRow]` — as produced by `RowParser`.
- `rsid_column_index: int` — a single field-position index, already resolved by the caller; `DuplicateRsidCheck` treats this as opaque, pre-validated positional data and performs no resolution or validation of it beyond bounds-checking per row.

**Process**
1. `DuplicateRsidCheck` performs no resolution, name-matching, or interpretation of `rsid_column_index` beyond using it to index into `row.fields`.
2. For each row: if `rsid_column_index < len(row.fields)`, the value at `row.fields[rsid_column_index]` is one observation of an RSID value at that row; otherwise, that row contributes no observation, and no exception is raised.
3. The full, unsampled `data_rows` collection is scanned; no row is skipped for reasons other than the out-of-bounds condition in step 2.

**Output**
Governed by ADR 2 ("Finding Output Mapping for DuplicateRsidCheck").

---

### 6. Architecture Impact

**Unchanged**
- `QualityCheck` Protocol (`interfaces.py`) — used exactly as designed, not modified.
- `HeaderResolver`, `HeaderInfo`, `RowParser`, `DataRow` — no changes.
- Existing module boundaries and contracts of `DuplicateHeaderCheck`, `MalformedRowCheck`, `MissingValueScanner` — untouched, not reopened.

**Resolved**
- `DuplicateRsidCheck`'s own dependency boundary, input contract (single `int` index, not a sequence), and malformed-row handling rule.

**Explicitly NOT resolved (remains open, by design)**
- The shared column-name-to-role resolution mechanism named in `DuplicateHeaderCheck`'s record §8, affecting `MissingValueScanner`, `DuplicateRsidCheck`, and `DuplicateChrPosCheck` alike, including whether `DuplicateChrPosCheck`'s own eventual context shape will be compatible with this one.

---

### 7. Testing Implications

The future `DuplicateRsidCheck` test suite must, at minimum, cover:

1. `rsid_column_index` within bounds for all rows; no duplicates present.
2. `rsid_column_index` within bounds for all rows; duplicates present.
3. `rsid_column_index` out of bounds for some, but not all, rows in the collection (mixed valid-width and short rows) — confirms no exception and correct partial-observation behavior.
4. `rsid_column_index` out of bounds for every row.
5. Repeated execution produces identical results (NFR-3).
6. No dependency on `HeaderInfo`, `HeaderResolver`, or any `GenomicProfiler` — verified via structural AST-based import checks, mirroring `MalformedRowCheck`'s, `DuplicateHeaderCheck`'s, and `MissingValueScanner`'s precedent.
7. `data_rows` and `rsid_column_index` are never mutated; individual `DataRow` instances are never mutated.
8. Full, unsampled scan confirmed (no truncation of the row population itself, as distinct from the bounded `examples`/`affected_row_refs` sample governed by ADR 2).

---

### 8. Final ADR Status

**Decision:** Accepted

**Implementation:** Approved to proceed after this ADR, together with ADR 2.

**Scope:** This ADR resolves `DuplicateRsidCheck`'s column-identity input contract and malformed-row handling only. It does not resolve the shared column-name-resolution mechanism, does not design any resolver component, and does not introduce unrelated architecture changes.
