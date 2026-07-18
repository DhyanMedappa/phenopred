# Architecture Decision Record: Finding Output Mapping for DuplicateRsidCheck (FR-8)

**Status:** Final — frozen reference for future module integration
**Architecture version/reference:** PhenoPred Architecture v1 (Approved)
**Traceability references:** SRS FR-8, OUT-7, NFR-3, NFR-5, NFR-6; Architecture v1 §7.1 (`ProfilingReport` model); `DuplicateHeaderCheck` Module Approval and Handoff Record (row-level duplicate-detection precedent); `MalformedRowCheck` Module Approval Record (row-population Finding precedent); `MissingValueScanner` ADR 2 (Finding Output Mapping) — cited for its precedent and for the specific alternative it rejected, not extended by it

---

### 1. Decision Context

FR-8 requires the system to "detect and report RSID values that occur more than once within a single file." OUT-7 lists "duplicate RSID count" as a required per-file output element, in the same enumeration as "duplicate header row count" and "malformed/ragged row count." Architecture v1 §7.1 models `ProfilingReport` as containing exactly two output tracks — `findings` (tied to OUT-7) and `profiles` (tied to OUT-6/OUT-8) — with OUT-7/`Finding` as the sole designated destination for this requirement, exactly as for every other quality check already frozen.

Unlike FR-6 (a frequency scan over literal tokens with no notion of "original" versus "duplicate" instance), FR-8 is a **duplicate-detection** requirement, structurally closer to FR-7 (`DuplicateHeaderCheck`). However, FR-7's duplicate condition is defined against a fixed external reference (the header row itself), so every matching data row is unambiguously "a duplicate." FR-8's duplicate condition is defined by rows sharing a value **with each other** — a symmetric relation with no external reference point — so the population `count` should reflect, and the ordering convention that should govern the bounded sample, are not settled by any single existing precedent and must be fixed here.

FR-8's own phrasing ("RSID value**s** that occur more than once") and OUT-7's label ("duplicate RSID **count**") admit at least two materially different readings of what should be counted: the number of distinct RSID values that repeat, versus the number of row-level occurrences involved in that repetition. This ADR fixes that reading, and the corresponding `examples`/`affected_row_refs` population and ordering, without altering the frozen `Finding` contract or introducing a second output track for this check.

---

### 2. Decision Drivers

The final rule MUST satisfy:

1. **FR-8/OUT-7 compatibility** — the Finding must meaningfully represent the duplicate-RSID condition FR-8 requires.
2. **"Exactly one Finding" rule** — must not require `DuplicateRsidCheck` to emit more than one Finding.
3. **Frozen `Finding` contract** — must not alter `Finding`'s field types, and must preserve a coherent relationship between `count` and `affected_row_refs`, consistent with the concern `MissingValueScanner`'s ADR 2 raised (and resolved) when it rejected making `count` an unrelated cardinality from the population `affected_row_refs` samples.
4. **Frozen output-track model** — must not place this check's output on the Profile track; OUT-7 is exclusively a Finding-track output per Architecture v1 §7.1.
5. **NFR-3 determinism** — repeated execution on the same input must yield an identical Finding, independent of iteration/traversal order, and independent of dictionary/set/`Counter` insertion order.
6. **NFR-6 traceability** — the Finding must remain traceable to a specific, named check.
7. **No premature abstraction** — must not design a new value object when the frozen output model has already assigned this requirement to the Finding track.
8. **No unevidenced "originality" claim** — FR-8's duplicate relation is symmetric (no row is externally privileged as "the original," unlike `DuplicateHeaderCheck`'s fixed header reference); any rule that treats one occurrence of a repeated value as exempt from the count would assert an unsupported claim about row precedence, the same category of concern the `MalformedRowCheck` tie-break ADR was careful to avoid when it stressed that its own line-index-based rule "carries no implication that earlier rows are more correct... or more representative."

---

### 3. Considered Alternatives

**Option A: `count` = total number of rows whose RSID value occurs more than once in the file (every row belonging to any duplicated-value group, all counted); `examples`/`affected_row_refs` sample from that same row population, in ascending `line_index` order**
Advantages: Preserves the established `count`/`affected_row_refs` relationship — both are drawn from, and describe, the identical population, exactly as in `DuplicateHeaderCheck` (every row matching the header, counted and sampled identically) and `MalformedRowCheck` (every malformed row, counted and sampled identically). Introduces no "first occurrence is exempt" rule, avoiding an unsupported claim about row precedence (Driver 8).
Risks: A `Finding.examples` entry showing only a rendered row does not by itself reveal *which other row(s)* share its RSID value; this is an accepted, bounded-sample limitation, no different in kind from every other check's bounded `examples`/`affected_row_refs` fields.

**Option B: `count` = number of distinct RSID values that occur more than once (vocabulary cardinality of duplicated values only)**
Risks: Breaks the established relationship between `count` and `affected_row_refs` in the same way `MissingValueScanner`'s ADR 2 identified and rejected for its own Option B — `affected_row_refs` would necessarily sample individual *rows*, while `count` would describe a *value cardinality* unrelated to how many rows those sampled entries represent, producing an internally incoherent Finding.
Rejected, for the same reason `MissingValueScanner`'s ADR 2 rejected its structurally identical alternative.

**Option C: `count` = total row occurrences of duplicated RSID values, minus one occurrence per duplicated value ("extra" occurrences only, i.e. group size − 1 per group, summed)**
Risks: Introduces an arbitrary "first occurrence is not itself a duplicate" convention with no textual support in FR-8 (which describes "values that occur more than once," not "occurrences after the first") and no architectural precedent — `DuplicateHeaderCheck` counts every matching row, not every matching row after the first. Also directly conflicts with Driver 8: designating one occurrence per group as exempt asserts an unsupported precedence claim among otherwise-symmetric rows.
Rejected.

**Option D: One Finding per distinct duplicated RSID value or per duplicate group**
Risks: Violates the explicit, repeatedly-validated "exactly one Finding per check" rule (Stage 1 Engineering Review; already honored by `DuplicateHeaderCheck`, `MalformedRowCheck`, `MissingValueScanner`); produces an unbounded, variable-length output per check, unlike every frozen check.
Rejected.

**Option E: Introduce a new value object for duplicate-group reporting**
Risks: Places this check's output on the Profile track or invents a third output shape, in conflict with Architecture v1 §7.1's frozen `ProfilingReport` model, which reserves OUT-7 exclusively for `Finding`-track reporting.
Rejected.

---

### 4. Final Architecture Decision

**The selected rule is Option A.**

**Definition of duplicate RSID detection.** An RSID value is "duplicated" if it is observed at `rsid_column_index` (per ADR 1) in two or more rows of the full, unsampled `data_rows` collection. **Every** row carrying a duplicated RSID value is counted and eligible for sampling — there is no "first occurrence is exempt" rule. This treats all rows sharing a value symmetrically, consistent with Driver 8: FR-8's relation has no external reference point (unlike `DuplicateHeaderCheck`'s fixed header row), so no row can be privileged as more "original" than another absent evidence for such a claim.

**Finding field mapping for `DuplicateRsidCheck`:**

- `check_name`: `"duplicate_rsid_check"`.
- `description`: a short, human-readable statement naming the number of duplicated RSID values found and the number of rows they span. Exact wording is an implementation-level detail not prescribed here, consistent with the identical, already-accepted gap in every prior check's `description` field.
- `count`: **the total number of rows, across the full, unsampled `data_rows` collection, whose RSID value (at `rsid_column_index`) occurs in two or more rows** — i.e. every row belonging to any duplicated-value group, summed across all such groups. This is **not** the number of distinct duplicated RSID values.
- `examples`: a bounded sample, maximum 10 entries, of rendered rows belonging to a duplicated-value group, in ascending `DataRow.line_index` order — mirroring `DuplicateHeaderCheck`'s and `MalformedRowCheck`'s row-rendering convention, not `MissingValueScanner`'s per-distinct-value convention (which suits a frequency scan, not a duplicate-row detection).
- `affected_row_refs`: a bounded sample, maximum 10 entries, of the `line_index` values of those same sampled rows, in the same ascending order as `examples`.

**Ordering rule (bounded-sample selection only):**

> Rows belonging to any duplicated-value group are sorted by ascending `DataRow.line_index`; the first 10 populate `examples`/`affected_row_refs`.

This ordering governs only which ≤10 entries populate the bounded sample; it has no bearing on `count`, which always reflects the full, unsampled total row count across all duplicated-value groups.

**Justification:**

- Preserves the "exactly one Finding" rule without alteration.
- Keeps `count` and `affected_row_refs` describing the identical row population — the same coherence principle `MissingValueScanner`'s ADR 2 protected when it rejected a distinct-value cardinality for `count` — by mirroring `DuplicateHeaderCheck`'s and `MalformedRowCheck`'s row-population convention exactly, rather than `MissingValueScanner`'s distinct-value convention, which was suited to a frequency-scan requirement with a different shape.
- Avoids inventing an unsupported "first occurrence is not a duplicate" rule, consistent with the same caution the frozen `MalformedRowCheck` tie-break ADR exercised about not implying any row is more "correct" or "representative" than another.
- Keeps `DuplicateRsidCheck`'s output entirely within the Finding track, consistent with Architecture v1 §7.1's frozen `ProfilingReport` model — no new value object, no Profile-track output.
- Ascending-`line_index` ordering reuses, rather than reinvents, the same original-row-order convention already established for `DuplicateHeaderCheck` and `MalformedRowCheck`'s `examples`/`affected_row_refs` fields.

**Rejected alternatives, briefly:** Option B was rejected for breaking the `count`/`affected_row_refs` relationship, mirroring `MissingValueScanner` ADR 2's rejection of its structurally identical alternative. Option C was rejected for introducing an unsupported row-precedence claim with no textual or architectural basis. Option D was rejected for violating the "exactly one Finding" rule. Option E was rejected for placing this check's output outside the frozen Finding-track model.

---

### 5. Formal Rule Specification

**Input**
The output of ADR 1's process: a set of (RSID value, row) observations, derived from `data_rows` and `rsid_column_index`, where out-of-bounds rows contribute no observation.

**Process**
1. Tally frequency per distinct RSID value across all observations.
2. Identify the set of RSID values with frequency ≥ 2 ("duplicated values").
3. Collect every row whose observed RSID value is a duplicated value; this is the full "affected row population."
4. `count` = the size of the affected row population (i.e. the sum, across all duplicated values, of each value's frequency) — computed over the full, unsampled `data_rows` collection.
5. Sort the affected row population by ascending `DataRow.line_index`. Take the first 10.
6. Render each sampled row as an `examples` entry (format not prescribed by this ADR, consistent with the identical, already-accepted gap in `MalformedRowCheck`'s and `DuplicateHeaderCheck`'s own example-rendering methods); take each sampled row's `line_index` for the corresponding `affected_row_refs` entry, preserving matching order between the two tuples.

**Output**
A single `Finding` as specified in §4 above.

**Worked Example**

Input: `rsid_column_index = 0`; rows: line 0 → `fields[0]="rs1"`; line 1 → `fields[0]="rs2"`; line 2 → `fields[0]="rs1"`; line 3 → `fields[0]="rs3"`; line 4 → `fields[0]="rs2"`.

Frequency: `"rs1"` → 2 (lines 0, 2); `"rs2"` → 2 (lines 1, 4); `"rs3"` → 1 (line 3, not duplicated).

Duplicated values: `{"rs1", "rs2"}`. Affected row population: lines 0, 1, 2, 4 (line 3 excluded — `"rs3"` is not duplicated).

**count = 4** (total affected rows, not 2 distinct duplicated values).

Sorted ascending by `line_index`: 0, 1, 2, 4.

**affected_row_refs = (0, 1, 2, 4)**; **examples** = rendered forms of those four rows, in that same order.

---

### 6. Architecture Impact

**Unchanged**
- `Finding` value object — no field added, no field type changed.
- `QualityCheck` boundary (remains provisional, not frozen by this ADR).
- `ProfilingReport`'s `findings`/`profiles` split (Architecture v1 §7.1) — untouched.
- `DuplicateHeaderCheck`, `MalformedRowCheck`, `MissingValueScanner` — untouched, not reopened.

**Resolved**
- `DuplicateRsidCheck`'s definition of "duplicate" (row-population-based, symmetric, no exempt first occurrence).
- `Finding.count` semantics (total affected-row count, not distinct-duplicated-value cardinality).
- `examples`/`affected_row_refs` population and ordering (row-level, ascending `line_index`, mirroring `DuplicateHeaderCheck`/`MalformedRowCheck`, not `MissingValueScanner`'s descending-frequency convention).

---

### 7. Testing Implications

The future `DuplicateRsidCheck` test suite must, at minimum, cover:

1. No duplicated RSID values present — `count == 0`, `examples == ()`, `affected_row_refs == ()`.
2. A single duplicated RSID value (two rows sharing it) — both rows counted and sampled.
3. Multiple distinct duplicated RSID values simultaneously — all affected rows across all groups counted and sampled together.
4. A mix of duplicated and non-duplicated RSID values — confirms non-duplicated rows are excluded from `count`/`examples`/`affected_row_refs`.
5. More than 10 affected rows — `examples`/`affected_row_refs` truncated at 10, ascending `line_index` order; `count` remains the full, unsampled total.
6. Determinism — repeated execution on identical input yields an identical Finding (NFR-3); result independent of input traversal order and independent of dict/set/`Counter` iteration order.
7. Empty `data_rows` — `count == 0`, `examples == ()`, `affected_row_refs == ()`.
8. `rsid_column_index` out of bounds for some or all rows (per ADR 1) — those rows contribute no observation and are correctly excluded from duplicate consideration; no exception raised.
9. Non-mutation of `data_rows`, individual `DataRow` instances, and `rsid_column_index`.
10. Dependency-boundary AST checks — no forbidden imports; only allowed domain imports present.
11. Return type is `Finding`; `check_name == "duplicate_rsid_check"`.

---

### 8. Final ADR Status

**Decision:** Accepted

**Implementation:** Approved to proceed after this ADR, together with ADR 1.

**Scope:** This ADR resolves `DuplicateRsidCheck`'s Finding output mapping only. It does not resolve the shared column-name-resolution mechanism, does not design any resolver component, and does not introduce unrelated architecture changes.
