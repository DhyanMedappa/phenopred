# Architecture Decision Record: Finding Output Mapping for DuplicateChrPosCheck (FR-9)

**Status:** Final — frozen reference for future module integration
**Architecture version/reference:** PhenoPred Architecture v1 (Approved)
**Traceability references:** SRS FR-9, OUT-7, NFR-3, NFR-5, NFR-6, RISK-4; Architecture v1 §7.1 (`ProfilingReport` model); Architecture v1 risk register ("Findings-as-data volume," which names chromosome-position pairs explicitly); `ADR_1_Column_Identity_Input_Contract_DuplicateChrPosCheck.md` (frozen — `ChrPosColumnIndices`); `DuplicateHeaderCheck` Module Approval and Handoff Record (exact-equality, no-normalization precedent); `MalformedRowCheck` Module Approval Record (row-population Finding precedent); `MissingValueScanner` ADR 2 (Finding Output Mapping) and `DuplicateRsidCheck` ADR 2 (Finding Output Mapping) — cited as primary precedent, extended here to a composite-key case, not altered by this ADR

---

### 1. Decision Context

FR-9 requires the system to "detect and report (chromosome, position) pairs that occur more than once within a single file, without judging the cause of any such duplication." OUT-7 lists "duplicate chromosome-position pair count" as a required per-file output element, in the same enumeration as "duplicate header row count," "malformed/ragged row count," and "duplicate RSID count." Architecture v1 §7.1 models `ProfilingReport` as containing exactly two output tracks — `findings` (tied to OUT-7) and `profiles` (tied to OUT-6/OUT-8) — with OUT-7/`Finding` as the sole designated destination for this requirement, exactly as for every other quality check already frozen.

FR-9 is structurally almost identical to FR-8, already resolved by `DuplicateRsidCheck`'s frozen ADR 2: both are duplicate-detection requirements, symmetric (no external reference row privileges one occurrence as "the original"), and both were left ambiguous by their own SRS phrasing between a distinct-value/pair cardinality and a row-population cardinality. The one respect in which FR-9 differs is that the value being compared for duplication is no longer a single field's literal value (as in FR-8) but a **composite key** formed from two same-row field values — the pair `(row.fields[chromosome_column_index], row.fields[position_column_index])`, as fixed by ADR 1. This ADR determines whether `DuplicateRsidCheck` ADR 2's resolution (Option A there: row-population `count`, symmetric, no exempt first occurrence) carries over unchanged to this composite-key case, and separately fixes what "equal" means for two such pairs, since composite-key equality is not already settled by any frozen precedent.

A further wrinkle, specific to FR-9, is that the SRS's own illustrative evidence — "614 duplicate pairs were observed in Dataset A; 2,401 in Dataset B" — mirrors the exploratory notebook's own printed convention of counting **distinct** duplicated pairs, not row occurrences (notebook §5.6: "`{len(dup_chrpos_a):,}` distinct (chromosome, position) pairs appear more than once"). Unlike FR-8, where both evidenced files showed zero duplicates (so the SRS's number offered no support for either reading), FR-9's non-zero evidentiary figures are legible under only one of the two candidate readings. This ADR must explicitly address whether that evidentiary phrasing constrains `Finding.count`'s definition, or whether it is descriptive context only, not a schema specification.

---

### 2. Decision Drivers

The final rule MUST satisfy:

1. **FR-9/OUT-7 compatibility** — the Finding must meaningfully represent the duplicate-(chromosome, position)-pair condition FR-9 requires.
2. **"Exactly one Finding" rule** — must not require `DuplicateChrPosCheck` to emit more than one Finding.
3. **Frozen `Finding` contract** — must not alter `Finding`'s field types, and must preserve a coherent relationship between `count` and `affected_row_refs`, consistent with the concern `MissingValueScanner`'s ADR 2 raised (and resolved) and `DuplicateRsidCheck`'s ADR 2 reaffirmed, both of which rejected making `count` an unrelated cardinality from the population `affected_row_refs` samples.
4. **Frozen output-track model** — must not place this check's output on the Profile track; OUT-7 is exclusively a Finding-track output per Architecture v1 §7.1.
5. **NFR-3 determinism** — repeated execution on the same input must yield an identical Finding, independent of iteration/traversal order, and independent of dictionary/set/`Counter` insertion order.
6. **NFR-6 traceability** — the Finding must remain traceable to a specific, named check.
7. **No premature abstraction** — must not design a new value object when the frozen output model has already assigned this requirement to the Finding track; this ADR governs only the mapping of already-defined `Finding` fields, per ADR 1's already-frozen input contract.
8. **No unevidenced "originality" claim** — FR-9's duplicate relation is symmetric (no row is externally privileged as "the original," unlike `DuplicateHeaderCheck`'s fixed header reference); any rule that treats one occurrence of a repeated pair as exempt from the count would assert an unsupported claim about row precedence, the same category of concern the `MalformedRowCheck` tie-break ADR and `DuplicateRsidCheck`'s ADR 2 were both careful to avoid.
9. **Composite-key equality must not encode biological or notational judgment** — per FR-9's own text ("without judging the cause of any such duplication"), RISK-4 (which leaves duplicate chromosome-position pairs' cause explicitly unresolved), CON-3 ("No cross-file identifier or positional equivalence has been established"), and the SRS's own §7.2 caution that chromosome notations cannot yet be assumed equivalent even within describing the same file's conventions — the equality rule used to decide whether two pairs are "the same" must not normalize, coerce, or reinterpret either field's literal value (e.g. treating `"1"` and `"01"` as equal, or applying any case-folding), since doing so would itself be an unevidenced notational judgment, not a reporting operation.
10. **Findings-as-data volume** — per Architecture v1's risk register, which names chromosome-position pairs explicitly as a case where "holding full example lists could be memory-intensive," the bounded (maximum 10-entry) `examples`/`affected_row_refs` convention already established for every frozen check must be preserved unchanged, not widened.

---

### 3. Considered Alternatives

**Option A: `count` = total number of rows whose observed (chromosome, position) pair occurs more than once in the file (every row belonging to any duplicated-pair group, all counted); `examples`/`affected_row_refs` sample from that same row population, in ascending `line_index` order; pair equality is exact, literal, per-field string equality of both components, with no normalization**
Advantages: Preserves the established `count`/`affected_row_refs` relationship — both are drawn from, and describe, the identical population, exactly as in `DuplicateHeaderCheck`, `MalformedRowCheck`, and `DuplicateRsidCheck` (every affected row, counted and sampled identically). Introduces no "first occurrence is exempt" rule, avoiding an unsupported claim about row precedence (Driver 8). The exact-equality rule introduces no biological or notational judgment (Driver 9), reusing `DuplicateHeaderCheck`'s own precedent ("exact tuple equality only... no trimming, no normalization, no case conversion") applied to a two-field composite key instead of a whole-row tuple.
Risks: A `Finding.examples` entry showing only a rendered row does not by itself reveal *which other row(s)* share its pair; this is an accepted, bounded-sample limitation, no different in kind from every other check's bounded `examples`/`affected_row_refs` fields. Separately, `count` under this option will not, in general, equal the SRS's illustrative "614"/"2,401" figures, since those quote the notebook's distinct-pair convention (Option B below) rather than a row-population count — addressed directly in the Final Architecture Decision (§4).

**Option B: `count` = number of distinct (chromosome, position) pairs that occur more than once (vocabulary cardinality of duplicated pairs only) — mirrors the exploratory notebook's own printed convention and the SRS's illustrative "614"/"2,401" figures verbatim**
Advantages: Directly reproduces the notebook's own reporting convention and the specific numbers the SRS quotes as evidence for FR-9.
Risks: Breaks the established relationship between `count` and `affected_row_refs` in the same way `MissingValueScanner`'s ADR 2 identified and `DuplicateRsidCheck`'s ADR 2 reaffirmed — `affected_row_refs` would necessarily sample individual *rows*, while `count` would describe a *pair-vocabulary cardinality* unrelated to how many rows those sampled entries represent, producing an internally incoherent Finding. The SRS's "614"/"2,401" figures are cited as descriptive, evidentiary context for what the notebook observed (mirroring how FR-6's and FR-8's own illustrative numbers are cited the same way in their respective SRS entries), not as a binding specification of `Finding.count`'s definition; OUT-7's own label — "duplicate chromosome-position pair **count**" — is exactly as ambiguous between a pair-cardinality and a row-population reading as OUT-7's "duplicate RSID count" already was for FR-8, and `DuplicateRsidCheck`'s ADR 2 already resolved that identical ambiguity in favor of the row-population reading for Finding-contract coherence. Nothing in FR-9's text obligates the system's `count` field to reproduce the notebook's specific printed number; the SRS documents what was *observed*, not what the *Finding schema* must encode.
Rejected, for the same reason `MissingValueScanner`'s and `DuplicateRsidCheck`'s ADR 2s each rejected their structurally identical alternative.

**Option C: `count` = total row occurrences of duplicated pairs, minus one occurrence per duplicated pair ("extra" occurrences only, i.e. group size − 1 per group, summed)**
Risks: Introduces an arbitrary "first occurrence is not itself a duplicate" convention with no textual support in FR-9 (which describes "pairs that occur more than once," not "occurrences after the first") and no architectural precedent — `DuplicateHeaderCheck` counts every matching row, not every matching row after the first, and `DuplicateRsidCheck`'s ADR 2 rejected the identical alternative for FR-8. Also directly conflicts with Driver 8: designating one occurrence per group as exempt asserts an unsupported precedence claim among otherwise-symmetric rows.
Rejected.

**Option D: One Finding per distinct duplicated (chromosome, position) pair, or per duplicate group**
Risks: Violates the explicit, repeatedly-validated "exactly one Finding per check" rule (already honored by `DuplicateHeaderCheck`, `MalformedRowCheck`, `MissingValueScanner`, `DuplicateRsidCheck`); produces an unbounded, variable-length output per check, unlike every frozen check.
Rejected.

**Option E: Introduce a new value object for duplicate-pair-group reporting**
Risks: Places this check's output on the Profile track or invents a third output shape, in conflict with Architecture v1 §7.1's frozen `ProfilingReport` model, which reserves OUT-7 exclusively for `Finding`-track reporting.
Rejected.

**Option F: Normalize chromosome and/or position values before comparing pairs for equality (e.g. case-fold alphabetic chromosome labels, strip leading zeros from numeric labels or positions) so that pairs likely referring to the same locus but written differently are still treated as duplicates**
Risks: Requires a domain/biological judgment about which normalizations are semantically valid for a chromosome or position field — precisely the kind of interpretation FR-9's own text excludes ("without judging the cause of any such duplication") and RISK-4 leaves unresolved; would also violate NFR-5 schema neutrality by hard-coding an assumed-equivalence rule not evidenced uniformly by both datasets (Dataset A's numeric-only labels and Dataset B's numeric-plus-alphabetic labels are explicitly documented as not yet assumable-equivalent, SRS §7.2); no evidenced dataset in this project's scope requires or exercises such normalization for either chromosome or position values.
Rejected.

---

### 4. Final Architecture Decision

**The selected rule is Option A.**

**Definition of duplicate (chromosome, position) pair.** A (chromosome, position) pair, observed per ADR 1 as `(row.fields[chr_pos_columns.chromosome_column_index], row.fields[chr_pos_columns.position_column_index])`, is "duplicated" if it is observed in two or more rows of the full, unsampled `data_rows` collection. Two pairs are equal if and only if both of their corresponding components are equal under exact, literal string equality — no case-folding, no leading-zero stripping, no numeric coercion, and no other normalization of either the chromosome value or the position value (Driver 9; Option F rejected). **Every** row carrying a duplicated pair is counted and eligible for sampling — there is no "first occurrence is exempt" rule. This treats all rows sharing a pair symmetrically, consistent with Driver 8: FR-9's relation has no external reference point (unlike `DuplicateHeaderCheck`'s fixed header row), so no row can be privileged as more "original" than another absent evidence for such a claim.

**On the SRS's illustrative "614"/"2,401" figures.** These numbers, and OUT-7's own label ("duplicate chromosome-position pair count"), are descriptive evidence of what the notebook observed under its own distinct-pair-counting convention; they are not a binding specification of `Finding.count`'s definition, precisely as `DuplicateRsidCheck`'s ADR 2 already established for FR-8's structurally identical ambiguity. This ADR's `count` will not, in general, reproduce "614" or "2,401" for the two evidenced files — it will instead report the (generally larger) total number of affected rows across all duplicated-pair groups. This divergence from the notebook's specific printed number is intentional and is required for internal Finding coherence (Driver 3).

**Finding field mapping for `DuplicateChrPosCheck`:**

- `check_name`: `"duplicate_chr_pos_check"`.
- `description`: a short, human-readable statement naming the number of duplicated (chromosome, position) pairs found and the number of rows they span. Exact wording is an implementation-level detail not prescribed here, consistent with the identical, already-accepted gap in every prior check's `description` field.
- `count`: **the total number of rows, across the full, unsampled `data_rows` collection, whose observed (chromosome, position) pair occurs in two or more rows** — i.e. every row belonging to any duplicated-pair group, summed across all such groups. This is **not** the number of distinct duplicated pairs.
- `examples`: a bounded sample, maximum 10 entries, of rendered rows belonging to a duplicated-pair group, in ascending `DataRow.line_index` order — mirroring `DuplicateHeaderCheck`'s, `MalformedRowCheck`'s, and `DuplicateRsidCheck`'s row-rendering convention, not `MissingValueScanner`'s per-distinct-value convention (which suits a frequency scan, not a duplicate-row detection). Each rendered example is expected to convey both the row's chromosome value and its position value (the two components of the observed pair), consistent with `DuplicateRsidCheck`'s precedent of rendering the observed value alongside `line_index`; exact rendering format remains an implementation-level detail, not prescribed by this ADR.
- `affected_row_refs`: a bounded sample, maximum 10 entries, of the `line_index` values of those same sampled rows, in the same ascending order as `examples`.

**Ordering rule (bounded-sample selection only):**

> Rows belonging to any duplicated-pair group are sorted by ascending `DataRow.line_index`; the first 10 populate `examples`/`affected_row_refs`.

This ordering governs only which ≤10 entries populate the bounded sample; it has no bearing on `count`, which always reflects the full, unsampled total row count across all duplicated-pair groups.

**Justification:**

- Preserves the "exactly one Finding" rule without alteration.
- Keeps `count` and `affected_row_refs` describing the identical row population — the same coherence principle `MissingValueScanner`'s ADR 2 protected and `DuplicateRsidCheck`'s ADR 2 reaffirmed — by mirroring `DuplicateHeaderCheck`'s, `MalformedRowCheck`'s, and `DuplicateRsidCheck`'s row-population convention exactly, rather than the notebook's distinct-pair convention, which is suited to descriptive exploratory reporting but not to this project's frozen Finding-contract coherence rule.
- Avoids inventing an unsupported "first occurrence is not a duplicate" rule, consistent with the same caution the frozen `MalformedRowCheck` tie-break ADR and `DuplicateRsidCheck`'s ADR 2 each exercised about not implying any row is more "correct" or "representative" than another.
- Fixes composite-key equality as exact and literal, with no normalization, directly satisfying FR-9's own "without judging the cause" clause and RISK-4's explicitly-left-open interpretation question — the check observes and compares, it does not reconcile notations or infer biological equivalence.
- Keeps `DuplicateChrPosCheck`'s output entirely within the Finding track, consistent with Architecture v1 §7.1's frozen `ProfilingReport` model — no new value object, no Profile-track output.
- Ascending-`line_index` ordering reuses, rather than reinvents, the same original-row-order convention already established for `DuplicateHeaderCheck`, `MalformedRowCheck`, and `DuplicateRsidCheck`'s `examples`/`affected_row_refs` fields.
- Retains the frozen, maximum-10-entry bounded-sample convention, directly addressing the risk register's "Findings-as-data volume" entry, which names chromosome-position pairs as a case meriting this exact safeguard.

**Rejected alternatives, briefly:** Option B was rejected for breaking the `count`/`affected_row_refs` relationship, mirroring `MissingValueScanner`'s and `DuplicateRsidCheck`'s ADR 2 rejections of the structurally identical alternative, despite matching the SRS's illustrative figures more literally. Option C was rejected for introducing an unsupported row-precedence claim with no textual or architectural basis. Option D was rejected for violating the "exactly one Finding" rule. Option E was rejected for placing this check's output outside the frozen Finding-track model. Option F was rejected for requiring an unevidenced biological/notational normalization judgment FR-9 explicitly excludes.

---

### 5. Formal Rule Specification

**Input**
The output of ADR 1's process: a set of ((chromosome value, position value), row) observations, derived from `data_rows` and `chr_pos_columns`, where a row whose `chromosome_column_index` or `position_column_index` is out of bounds contributes no observation.

**Process**
1. Tally frequency per distinct `(chromosome_value, position_value)` pair across all observations, using exact, literal string equality per component (no normalization).
2. Identify the set of pairs with frequency ≥ 2 ("duplicated pairs").
3. Collect every row whose observed pair is a duplicated pair; this is the full "affected row population."
4. `count` = the size of the affected row population (i.e. the sum, across all duplicated pairs, of each pair's frequency) — computed over the full, unsampled `data_rows` collection.
5. Sort the affected row population by ascending `DataRow.line_index`. Take the first 10.
6. Render each sampled row as an `examples` entry (format not prescribed by this ADR, consistent with the identical, already-accepted gap in `MalformedRowCheck`'s, `DuplicateHeaderCheck`'s, and `DuplicateRsidCheck`'s own example-rendering methods); take each sampled row's `line_index` for the corresponding `affected_row_refs` entry, preserving matching order between the two tuples.

**Output**
A single `Finding` as specified in §4 above.

**Worked Example**

Input: `chr_pos_columns = ChrPosColumnIndices(chromosome_column_index=1, position_column_index=2)`; rows: line 0 → `fields[1]="1", fields[2]="100"`; line 1 → `fields[1]="2", fields[2]="200"`; line 2 → `fields[1]="1", fields[2]="100"`; line 3 → `fields[1]="3", fields[2]="300"`; line 4 → `fields[1]="2", fields[2]="200"`.

Frequency: `("1","100")` → 2 (lines 0, 2); `("2","200")` → 2 (lines 1, 4); `("3","300")` → 1 (line 3, not duplicated).

Duplicated pairs: `{("1","100"), ("2","200")}`. Affected row population: lines 0, 1, 2, 4 (line 3 excluded — `("3","300")` is not duplicated).

**count = 4** (total affected rows, not 2 distinct duplicated pairs, and not "614"/"2,401"-style pair cardinality).

Sorted ascending by `line_index`: 0, 1, 2, 4.

**affected_row_refs = (0, 1, 2, 4)**; **examples** = rendered forms of those four rows (each conveying both its chromosome and position values), in that same order.

---

### 6. Architecture Impact

**Unchanged**
- `Finding` value object — no field added, no field type changed.
- `ChrPosColumnIndices` (frozen by ADR 1) — no field added, no field type changed.
- `QualityCheck` boundary (remains provisional, not frozen by this ADR).
- `ProfilingReport`'s `findings`/`profiles` split (Architecture v1 §7.1) — untouched.
- `DuplicateHeaderCheck`, `MalformedRowCheck`, `MissingValueScanner`, `DuplicateRsidCheck` — untouched, not reopened.

**Resolved**
- `DuplicateChrPosCheck`'s definition of "duplicate" (row-population-based, symmetric, no exempt first occurrence).
- Composite-key equality semantics (exact, literal, per-component string equality; no normalization of either chromosome or position values).
- `Finding.count` semantics (total affected-row count, not distinct-duplicated-pair cardinality — explicitly not the SRS's illustrative "614"/"2,401" figures).
- `examples`/`affected_row_refs` population and ordering (row-level, ascending `line_index`, mirroring `DuplicateHeaderCheck`/`MalformedRowCheck`/`DuplicateRsidCheck`, not `MissingValueScanner`'s descending-frequency convention).

---

### 7. Testing Implications

The future `DuplicateChrPosCheck` test suite must, at minimum, cover:

1. No duplicated (chromosome, position) pairs present — `count == 0`, `examples == ()`, `affected_row_refs == ()`.
2. A single duplicated pair (two rows sharing it) — both rows counted and sampled.
3. Multiple distinct duplicated pairs simultaneously — all affected rows across all groups counted and sampled together.
4. A mix of duplicated and non-duplicated pairs — confirms non-duplicated rows are excluded from `count`/`examples`/`affected_row_refs`.
5. More than 10 affected rows — `examples`/`affected_row_refs` truncated at 10, ascending `line_index` order; `count` remains the full, unsampled total.
6. Rows sharing the same chromosome value but a different position value (or vice versa) are correctly treated as **not** duplicating one another — the pair, not either component alone, is the unit of comparison.
7. Values that could be considered "equivalent" under some normalization (e.g. `"1"` vs `"01"`, or differing case in an alphabetic label) are correctly treated as **distinct** — confirms no normalization is applied (Driver 9 / Option F rejection).
8. Determinism — repeated execution on identical input yields an identical Finding (NFR-3); result independent of input traversal order and independent of dict/set/`Counter` iteration order.
9. Empty `data_rows` — `count == 0`, `examples == ()`, `affected_row_refs == ()`.
10. `chromosome_column_index` or `position_column_index` out of bounds for some or all rows (per ADR 1) — those rows contribute no observation and are correctly excluded from duplicate consideration; no exception raised.
11. Non-mutation of `data_rows`, individual `DataRow` instances, and `chr_pos_columns`.
12. Dependency-boundary AST checks — no forbidden imports; only allowed domain imports present.
13. Return type is `Finding`; `check_name == "duplicate_chr_pos_check"`.

---

### 8. Additional ADR Requirement Evaluation

FR-9 raises exactly two architectural questions: (a) what shape of already-resolved input does `DuplicateChrPosCheck` consume, and (b) how does that input map to a single `Finding`'s fields — including the definition of "duplicate," the equality semantics for the composite key, and the `count`/`examples`/`affected_row_refs` population rule. Question (a) is fully and exclusively resolved by the frozen ADR 1. Question (b) is fully resolved by this ADR. No third, independent architectural question remains:

- **The shared column-name-to-role resolution mechanism** (how `HeaderInfo.resolved_columns` maps to `chr_pos_columns.chromosome_column_index`/`position_column_index`) is a cross-cutting concern already recorded as deferred in `DuplicateHeaderCheck`'s Module Approval and Handoff Record §8 and in `DuplicateRsidCheck`'s Architecture Freeze Record §8, affecting `MissingValueScanner`, `DuplicateRsidCheck`, and `DuplicateChrPosCheck` alike. It is not specific to FR-9, is not newly introduced by this ADR, and — per those already-frozen records — is explicitly reserved for its own future ADR once that mechanism is designed. Resolving it here would exceed this ADR's scope and would reopen decisions frozen elsewhere.
- **Composite-key equality/normalization** could have been mistaken for a question requiring its own ADR, given it is new relative to FR-6/FR-8. It does not: it is a direct component of the Finding output mapping (it determines what counts as "the same" pair, which determines `count`, `examples`, and `affected_row_refs` alike) and has been resolved within this ADR (§4, §3 Option F) rather than deferred.
- **No new value object, interface, infrastructure dependency, or orchestration component** is required by FR-9 beyond what ADR 1 (`ChrPosColumnIndices`) and this ADR (the `Finding` field mapping) already fix. `QualityCheckRunner` composition, `ReportBuilder` aggregation, and the shared resolution mechanism above remain the only open items touching this check, and all three are pre-existing, cross-cutting deferred decisions untouched and unexpanded by either FR-9 ADR.

**Conclusion: ADR 1 and ADR 2 together fully cover the architectural decisions required for FR-9.** No additional ADR is required for this module.

---

### 9. Final ADR Status

**Decision:** Accepted

**Implementation:** Approved to proceed after this ADR, together with ADR 1.

**Scope:** This ADR resolves `DuplicateChrPosCheck`'s Finding output mapping, its definition of "duplicate," and its composite-key equality semantics only. It does not resolve the shared column-name-resolution mechanism, does not design any resolver component, and does not introduce unrelated architecture changes.
