# MissingValueScanner Final ADRs

## ADR 1

# Architecture Decision Record: Column-Identity Input Contract for MissingValueScanner (FR-6)

**Status:** Final — frozen reference for future module integration
**Architecture version/reference:** PhenoPred Architecture v1 (Approved)
**Traceability references:** SRS FR-6, OUT-7, NFR-3, NFR-5; `interfaces.py` `QualityCheck` Protocol; `DuplicateHeaderCheck` Module Approval and Handoff Record §8 (deferred decision); `MalformedRowCheck` Module Approval Record (variable-width `DataRow` precedent)

---

### 1. Decision Context

FR-6 requires `MissingValueScanner` to scan "designated genotype/allele columns," but no frozen artifact defines how a column earns that designation. `HeaderInfo.resolved_columns` supplies only literal, file-specific column-name strings, and the two evidenced files already use different vocabularies for these columns (`allele1`/`allele2` vs `genotype`), a divergence Architecture v1 itself names via `GenotypeLayoutProfile`'s `layout_kind` distinction. Any name-based resolution logic placed inside `MissingValueScanner` would necessarily hard-code a fixed vocabulary (violating NFR-5) or require a configuration surface Architecture v1's `ConfigProvider` does not name. This gap is already recorded as a shared, cross-cutting deferred decision in `DuplicateHeaderCheck`'s Module Approval and Handoff Record §8 ("Column-name-resolution mechanism for MissingValueScanner, DuplicateRsidCheck, DuplicateChrPosCheck"), affecting three future checks, not this module alone.

This ADR resolves only `MissingValueScanner`'s own dependency boundary and input contract. It does not resolve the shared upstream column-name-resolution mechanism, so that decision remains open and independently decomposable for `DuplicateRsidCheck` and `DuplicateChrPosCheck`.

---

### 2. Decision Drivers

The final rule MUST satisfy:

1. **FR-6 compatibility** — the scanner must operate on the correct columns regardless of file layout.
2. **NFR-5 schema neutrality** — must not hard-code or otherwise fix a file-specific column-name vocabulary anywhere inside this module.
3. **Separation of concerns** — column-name semantic resolution is not a `QualityCheck`'s job; it remains outside `MissingValueScanner`'s boundary, consistent with `HeaderResolver`'s (FR-3) exclusive ownership of header/column-name interpretation.
4. **Consistency with frozen precedent** — `MalformedRowCheck` forbids a `HeaderInfo` dependency entirely to preserve schema neutrality; `DuplicateHeaderCheck` consumes `HeaderInfo` only as an already-resolved value, via exact tuple equality, never performing column-role inference.
5. **Independence from the shared, still-open deferred decision** (`DuplicateHeaderCheck` record §8) — this ADR must not presuppose or foreclose how that broader mechanism, or its use by sibling checks, is eventually resolved.
6. **Minimal abstraction** — no new value object or interface should be introduced if the existing, already-reserved `QualityCheck` `context` parameter and plain data types can serve the purpose.
7. **No uncaught exceptions from expected input shapes** — per Architecture v1 §13.2, data-quality conditions are always Finding data, never exceptions; and per `MalformedRowCheck`'s frozen record, rows of varying field-count width are an expected, ordinary member of the `DataRow` collection every `QualityCheck` consumes.
8. **Testability** — the module must remain unit-testable with plain data in/out, no file I/O, no mocking framework required.

---

### 3. Considered Alternatives

**Option A: Hardcoded column-name vocabulary inside `MissingValueScanner`**
Risks: Bakes in exactly the two evidenced vocabularies; a third vendor format with different column names silently produces zero designated columns.
NFR-5 compatibility: Violated.

**Option B: Externally configured column-name list via `ConfigProvider`**
Risks: `ConfigProvider`'s architecturally named value set (comment prefix, header keyword, output path, log level) does not include this; extends that interface beyond its documented scope; contradicts FR-6's framing that column meaning derives from the file's own header.
NFR-5 compatibility: Improved over A but still externally fixed rather than file-derived.

**Option C: Dependency on the future `GenotypeLayoutClassifier`'s output (FR-11)**
Risks: Contradicts Architecture v1 §6's explicit design that `QualityCheck`s and `GenomicProfiler`s run independently over the same `DataRow` collection; introduces an unspecified sequencing dependency between two deliberately decoupled component families.
Architecture v1 compatibility: Violated.

**Option D: `MissingValueScanner` receives whole `HeaderInfo` and resolves columns internally**
Risks: Does not resolve the ambiguity — merely relocates the same unresolved column-naming problem inside a to-be-frozen module, reopening the exact tension `MalformedRowCheck`'s frozen boundary was built to avoid.

**Option E: `MissingValueScanner` receives pre-resolved column indices via the `QualityCheck` interface's `context` parameter**
Advantages: Uses the already-reserved extension point — `interfaces.py`'s `QualityCheck` Protocol explicitly anticipates a second implementer validating its `context` parameter against "different context needs," naming "column-identity context" as its own illustrative example. `MissingValueScanner` carries zero opinion about column names or meaning; it operates purely on already-resolved positions, mirroring how `DuplicateHeaderCheck` consumes an already-resolved `HeaderInfo` rather than resolving headers itself. No new value object is needed: a plain `Sequence[int]` carries no invariant beyond what `DataRow.line_index` already models as a bare `int`, so a wrapper type would add maintenance cost without corresponding benefit.
FR-6/NFR-5/Architecture v1 compatibility: Fully satisfied.

---

### 4. Final Architecture Decision

**The selected rule is Option E — `MissingValueScanner` receives already-resolved designated-column field indices via the `QualityCheck` interface's `context` parameter, as a plain `Sequence[int]`.**

**Concretely:**
```
MissingValueScanner.check(
    data_rows: Sequence[DataRow],
    designated_column_indices: Sequence[int],
) -> Finding
```

**Resolution ownership.** The logic that derives `designated_column_indices` from `HeaderInfo.resolved_columns` (or any other source) is **domain-layer work**, consistent with Architecture v1's module table, which confines `application/profile_file_use_case.py` to pure sequencing ("depends only on domain interfaces... contains no business logic"). This ADR does not design that resolution logic, does not name a concrete component for it, and does not expand the still-open, shared deferred decision recorded in `DuplicateHeaderCheck`'s approval record §8 — it fixes only that, wherever and however that resolution eventually happens, it must happen in the domain layer and must hand `MissingValueScanner` a plain, already-resolved `Sequence[int]`.

**Malformed-row handling.** `MalformedRowCheck`'s own frozen record confirms that a `DataRow` collection legitimately contains rows of varying field-count width — this is FR-5's entire premise, not an edge case unique to this module. Accordingly:

> If a designated column index in `designated_column_indices` is outside the bounds of a particular `DataRow`'s `fields` tuple (i.e. `index >= len(row.fields)`), that row contributes **no observation** for that designated column. No exception is raised. This is normal data-quality input, not an error condition, consistent with Architecture v1 §13.2's rule that data-quality conditions are always represented as Finding data, never as exceptions.

**Justification:**

- This narrows `QualityCheck`'s generic `context: object = None` parameter into a concrete type, exactly as `DuplicateHeaderCheck` already narrows it to `header_info: HeaderInfo` — no new interface or abstraction is introduced.
- `designated_column_indices` is a plain `Sequence[int]` — no new named value object is introduced, consistent with `DataRow`'s own precedent of using bare primitives (`line_index: int`, `fields: tuple[str, ...]`) for positional/structural data with no invariant beyond bounds.
- `MissingValueScanner` performs no column-name matching, no header interpretation, and carries no dependency on `HeaderInfo`, `HeaderResolver`, or any `GenomicProfiler` — fully preserving NFR-5 and the module's schema neutrality.
- The out-of-bounds rule closes a real gap without introducing any defensive machinery beyond a single, deterministic skip condition.

**Rejected alternatives, briefly:** Option A was rejected for hard-coding a fixed vocabulary in violation of NFR-5. Option B was rejected for extending `ConfigProvider` beyond its named scope. Option C was rejected for violating the architecture's explicit `QualityCheck`/`GenomicProfiler` independence. Option D was rejected for relocating, not resolving, the ambiguity into frozen code.

---

### 5. Formal Rule Specification

**Input**
- `data_rows: Sequence[DataRow]` — as produced by `RowParser`.
- `designated_column_indices: Sequence[int]` — zero, one, or more field-position indices, already resolved by the caller; `MissingValueScanner` treats this as opaque, pre-validated positional data and performs no resolution or validation of it beyond bounds-checking per row.

**Process**
1. `MissingValueScanner` performs no resolution, name-matching, or interpretation of `designated_column_indices` beyond using each value to index into `row.fields`.
2. An empty `designated_column_indices` is valid: zero designated columns, contributing no observations.
3. For each row, for each index in `designated_column_indices`: if `index < len(row.fields)`, the value at `row.fields[index]` is one observation; otherwise, that row contributes no observation for that index, and no exception is raised.

**Output**
Governed by ADR 2 ("Finding Output Mapping for MissingValueScanner").

---

### 6. Architecture Impact

**Unchanged**
- `QualityCheck` Protocol (`interfaces.py`) — used exactly as designed, not modified.
- `HeaderResolver`, `HeaderInfo`, `RowParser`, `DataRow` — no changes.
- Existing module boundaries of `MalformedRowCheck`, `DuplicateHeaderCheck`.

**Resolved**
- `MissingValueScanner`'s own dependency boundary, input contract, and malformed-row handling rule.

**Explicitly NOT resolved (remains open, by design)**
- The shared column-name-to-role resolution mechanism named in `DuplicateHeaderCheck`'s record §8, affecting `MissingValueScanner`, `DuplicateRsidCheck`, and `DuplicateChrPosCheck` alike, including whether those sibling checks will use a compatible `context` shape.

---

### 7. Testing Implications

The future `MissingValueScanner` test suite must, at minimum, cover:

1. Empty `designated_column_indices` — zero designated columns, valid, no exception.
2. Single designated column index; multiple designated column indices simultaneously.
3. A designated index that is out of bounds for some, but not all, rows in the collection (mixed valid-width and short rows) — confirms no exception and correct partial-observation behavior.
4. A designated index that is out of bounds for every row.
5. Repeated execution produces identical results (NFR-3).
6. No dependency on `HeaderInfo`, `HeaderResolver`, or any `GenomicProfiler` — verified via structural AST-based import checks, mirroring `MalformedRowCheck`'s and `DuplicateHeaderCheck`'s precedent.
7. `designated_column_indices` and `data_rows` are never mutated.

---

### 8. Final ADR Status

**Decision:** Accepted

**Implementation:** Approved to proceed after this ADR, together with ADR 2.

**Scope:** This ADR resolves `MissingValueScanner`'s column-identity input contract and malformed-row handling only. It does not resolve the shared column-name-resolution mechanism, does not design any resolver component, and does not introduce unrelated architecture changes.

---

## ADR 2

# Architecture Decision Record: Finding Output Mapping for MissingValueScanner (FR-6)

**Status:** Final — frozen reference for future module integration
**Architecture version/reference:** PhenoPred Architecture v1 (Approved)
**Traceability references:** SRS FR-6, OUT-7, NFR-3, NFR-5, NFR-6; Architecture v1 §7.1 (`ProfilingReport` model); frozen ADR resolving Deferred Decision B.4 (`MalformedRowCheck` tie-break, cited for its ordering mechanism only); `MalformedRowCheck` Module Approval Record §10 (`ColumnCountDistribution` deferral precedent)

---

### 1. Decision Context

FR-6 requires reporting "the frequency of every distinct literal value observed" in designated columns. OUT-7 lists "literal missing/no-call token frequencies" as a required per-file output element, in the same enumeration as "duplicate header row count" and "malformed/ragged row count." Architecture v1 §7.1 models `ProfilingReport` as containing exactly two output tracks: `findings` (one per quality check, explicitly tied to OUT-7) and `profiles` (tied explicitly to OUT-6/OUT-8, produced by `GenomicProfiler` implementations). There is no metadata-style output slot analogous to OUT-5 available for missing-value token data — OUT-7/`Finding` is its sole designated destination in the frozen architecture. This ADR fixes how FR-6's distribution-shaped requirement maps onto the frozen, single-Finding-per-check contract, without altering that contract or introducing a second output track for this check.

---

### 2. Decision Drivers

The final rule MUST satisfy:

1. **FR-6/OUT-7 compatibility** — the Finding must meaningfully represent the token-frequency observation FR-6 requires.
2. **"Exactly one Finding" rule** — must not require `MissingValueScanner` to emit more than one Finding.
3. **Frozen `Finding` contract** — must not alter `Finding`'s field types, and must preserve the established relationship between `count` and `affected_row_refs` (both anchored to the same underlying occurrence population, as in `DuplicateHeaderCheck` and `MalformedRowCheck`).
4. **Frozen output-track model** — must not place this check's output on the Profile track; OUT-7 is exclusively a Finding-track output per Architecture v1 §7.1.
5. **NFR-3 determinism** — repeated execution on the same input must yield an identical Finding, independent of iteration/traversal order.
6. **NFR-6 traceability** — the Finding must remain traceable to a specific, named check.
7. **No premature abstraction** — must not design a new value object for a distribution requirement when the frozen output model has already assigned this requirement to the Finding track.

---

### 3. Considered Alternatives

**Option A: `count` = total literal-value occurrences across designated columns; exactly one Finding; bounded `examples`/`affected_row_refs`**
Advantages: Preserves the established `count`/`affected_row_refs` occurrence-based relationship used by every existing check; introduces no new type; stays fully within the frozen Finding-track output model.
Risks: The full per-value frequency table beyond the bounded sample size is not literally reproducible from this Finding alone — an accepted, bounded-sample limitation shared with every other check's `examples`/`affected_row_refs` fields.

**Option B: `count` = number of distinct literal values (vocabulary cardinality)**
Risks: Breaks the established relationship between `count` and `affected_row_refs` — every existing check ties both to the same occurrence population; this option would make `count` an unrelated cardinality while `affected_row_refs` continues to sample rows, an internally incoherent Finding.
Rejected.

**Option C: One Finding per distinct literal value or per designated column**
Risks: Violates the explicit, twice-validated "exactly one Finding per check" rule (Stage 1 Engineering Review); produces an unbounded, variable-length output per check, unlike every frozen check.
Rejected.

**Option D: Introduce a new `MissingValueTokenDistribution` value object now, alongside or instead of a Finding**
Risks: Places this check's output on the Profile track, which Architecture v1 §7.1 reserves exclusively for `GenomicProfiler`-produced OUT-6/OUT-8 outputs — a direct conflict with the frozen `ProfilingReport` model, not merely a premature-abstraction concern.
Rejected.

---

### 4. Final Architecture Decision

**The selected rule is Option A.**

**Finding field mapping for `MissingValueScanner`:**

- `check_name`: `"missing_value_scanner"`.
- `description`: a short, human-readable statement naming the number of designated columns scanned and the number of distinct literal values found. The exact wording is an implementation-level detail not prescribed here, consistent with the identical, already-accepted gap in `MalformedRowCheck`'s own `description` field.
- `count`: **the total number of literal missing/no-call token occurrences observed across all designated columns** — i.e. the sum of every observation counted per ADR 1 §5, computed over the full, unsampled `DataRow` collection. This is **not** the number of distinct tokens.
- `examples`: a bounded sample, maximum 10 entries, of rendered `"value (frequency)"` strings, one per distinct literal value, selected and ordered per §5 below.
- `affected_row_refs`: a bounded sample, maximum 10 entries, of the `line_index` of one representative row exhibiting each illustrated (≤10) distinct value, in the same order as `examples`.

**Ordering rule (bounded-sample selection only):**

> Primary: descending frequency (most-observed distinct value first).
> Secondary, used only to break ties among distinct values of equal frequency: ascending `DataRow.line_index` of that value's first observation.

This ordering governs only which ≤10 entries populate `examples`/`affected_row_refs`; it has no bearing on `count`, which always reflects the full, unsampled total.

**Justification:**

- Preserves the "exactly one Finding" rule without alteration.
- Restores the established `count`/`affected_row_refs` occurrence-based relationship shared by every frozen check, rather than introducing a third, incompatible meaning for `count`.
- Keeps `MissingValueScanner`'s output entirely within the Finding track, consistent with Architecture v1 §7.1's frozen `ProfilingReport` model — no new value object, no Profile-track output.
- Descending-frequency ordering ensures the bounded 10-entry sample surfaces the most meaningful values (matching the SRS's own illustrative example of a high-frequency no-call token), rather than risking their omission under a purely positional ordering. The `line_index` tie-break is reused, not reinvented, applying the frozen FR-5 ADR's mechanism strictly to the narrow case it was designed for — equal-magnitude candidates with no other principled ordering available.

**Rejected alternatives, briefly:** Option B was rejected for breaking the `count`/`affected_row_refs` relationship every frozen check shares. Option C was rejected for violating the "exactly one Finding" rule. Option D was rejected for placing this check's output on the Profile track in conflict with the frozen `ProfilingReport` model.

---

### 5. Formal Rule Specification

**Input**
The output of ADR 1's process: a set of observations, each an (observed literal value, row) pair, derived from `data_rows` and `designated_column_indices`.

**Process**
1. Tally frequency per distinct literal value across all observations (per ADR 1 §5 — out-of-bounds indices contribute no observation).
2. `count` = the sum of all observation frequencies (total occurrences), across all distinct values.
3. For each distinct value, determine its first-observed `line_index` (the smallest `line_index` among rows where that value was observed at any designated column) and its total frequency.
4. Sort distinct values by descending frequency; break ties by ascending first-observed `line_index`. Take the first 10.
5. Render each as a `"value (frequency)"` string for `examples`; take its first-observed `line_index` for the corresponding `affected_row_refs` entry, preserving matching order between the two tuples.

**Output**
A single `Finding` as specified in §4 above.

**Worked Example**

Input: `designated_column_indices = (3,)`; rows: line 0 → `fields[3]="A"`; line 1 → `fields[3]="0"`; line 2 → `fields[3]="A"`; line 3 → `fields[3]="0"`; line 4 → `fields[3]="0"`.

Distinct values: `"A"` → frequency 2, first observed line 0; `"0"` → frequency 3, first observed line 1.

**count = 5** (total occurrences, not 2 distinct values).

Ordered by descending frequency: `"0"` (3), `"A"` (2).

**examples = ("0 (3)", "A (2)")**; **affected_row_refs = (1, 0)**.

---

### 6. Architecture Impact

**Unchanged**
- `Finding` value object — no field added, no field type changed.
- `QualityCheck` boundary (remains provisional, not frozen by this ADR).
- `ProfilingReport`'s `findings`/`profiles` split (Architecture v1 §7.1) — untouched.
- `ColumnCountDistribution`'s own, separately deferred status — untouched.

**Resolved**
- `MissingValueScanner`'s Finding output mapping and bounded-sample ordering convention.

**Explicitly NOT resolved (remains open, by design)**
- No distribution-shaped value object is introduced or anticipated for this check; if a future requirement calls for a complete, unbounded frequency table, that is separate, future work requiring its own architecture decision.

---

### 7. Testing Implications

The future `MissingValueScanner` test suite must, at minimum, cover:

1. `count` reflects total occurrences, not distinct-value cardinality (explicit regression test).
2. Descending-frequency ordering of `examples`/`affected_row_refs`, including a case where a high-frequency value would be excluded under a purely positional ordering.
3. Tie-break by ascending `line_index` when two or more distinct values share equal frequency.
4. More than 10 distinct values — `examples`/`affected_row_refs` truncated at 10; `count` remains the full, unsampled total.
5. Empty `designated_column_indices` or empty `data_rows` — `count == 0`, `examples == ()`, `affected_row_refs == ()`.
6. Ordering independent of dict/set/Counter iteration order — verified via structurally different but logically equivalent input construction paths.
7. Deterministic repeated execution (NFR-3).

---

### 8. Final ADR Status

**Decision:** Accepted

**Implementation:** Approved to proceed after this ADR, together with ADR 1.

**Scope:** This ADR resolves `MissingValueScanner`'s Finding output mapping and bounded-sample ordering only. It does not introduce any new value object, does not alter the `Finding` contract, and does not introduce unrelated architecture changes.

---

## Freeze Checklist

**Consistency verification performed against:** SRS (FR-6, OUT-7, NFR-3, NFR-5, NFR-6), Architecture v1 (§6, §7.1, §13.2, §16), Clean Architecture / DDD layering, `interfaces.py`, `entities.py`, `value_objects.py`, the frozen FR-5 ADR, `MalformedRowCheck`/`DuplicateHeaderCheck` approval records, and the Stage 1 Engineering Review. No violation found in the final ADR text above.

**One new observation surfaced during final verification, outside the scope of these two ADRs:**

- **Issue:** Neither ADR specifies whether frequency tallying should be reported per individual designated column (e.g. `allele1` vs `allele2` separately) or aggregated across all designated columns into one combined tally (as both worked examples assume).
- **Why it is out of scope here:** Resolving this would require deciding how multi-column genotype layouts (FR-11's two-column vs single-column distinction) interact with FR-6's reporting granularity — a question that touches the still-open, shared column-resolution deferred decision (ADR 1 §1) and was not part of the authorized revisions for this freeze. Deciding it now would expand these ADRs beyond their approved scope.
- **Disposition:** Recorded as a **Future ADR Candidate** — *"Per-column vs. aggregated frequency-reporting granularity for MissingValueScanner."*

**Checklist:**

- [x] ADR 1 — domain-layer ownership statement for `HeaderInfo → designated_column_indices` resolution added, without designing the resolver or expanding the shared deferred decision.
- [x] ADR 1 — malformed-row / out-of-bounds index rule added exactly as specified: no observation contributed, no exception raised.
- [x] ADR 1 — no wrapper value object introduced; `Sequence[int]` retained.
- [x] ADR 2 — `Finding.count` redefined as total occurrence count, not distinct-value cardinality.
- [x] ADR 2 — exactly one `Finding` retained; no `MissingValueTokenDistribution` or other new value object introduced; `Finding` contract unchanged.
- [x] ADR 2 — ordering rule set to descending frequency, ascending `line_index` tie-break, applied only to bounded-sample selection.
- [x] Rejected review recommendations excluded: cross-implementer `context`-type consistency requirement, wrapper value object for column indices, and any distribution-shaped value object on the Profile track.
- [x] Architecture consistency verified against SRS, Architecture v1, Clean Architecture/DDD boundaries, `interfaces.py`, `entities.py`, `value_objects.py`, frozen ADRs, and frozen module approval records.
- [x] No frozen contract changed: `Finding`, `QualityCheck`, `DataRow`, `HeaderInfo`, `ProfilingReport`, and all previously frozen modules remain untouched.
- [x] One new, out-of-scope observation identified and recorded as a Future ADR Candidate rather than resolved inline.
- [x] Ready for permanent freeze.
