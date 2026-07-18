# Implementation Handoff: DuplicateRsidCheck (FR-8)

Target file: `phenopred/domain/quality_checks/duplicate_rsid_check.py`
Corresponding test file (future): `tests/unit/domain/quality_checks/test_duplicate_rsid_check.py`

This document translates the frozen `ARCHITECTURE_FREEZE_RECORD_DuplicateRsidCheck.md` (and the ADRs it consolidates) into implementation-ready instructions. It does not reopen, reinterpret, or extend any frozen decision. Where this document and the Freeze Record appear to differ, the Freeze Record governs.

---

## 1. Module Overview

- **Module name:** DuplicateRsidCheck
- **Requirement ID:** FR-8 — "The system shall detect and report RSID values that occur more than once within a single file."
- **Responsibility:** Given a file's parsed `DataRow` collection and an already-resolved RSID column field-position index, determine which rows carry an RSID value occurring in two or more rows of the file, and report the result as exactly one `Finding`.
- **Domain layer location:** `phenopred/domain/quality_checks/`, alongside `duplicate_header_check.py`, `malformed_row_check.py`, and `missing_value_scanner.py`.
- **Relationship to existing QualityCheck modules:** `DuplicateRsidCheck` is an **independent** `QualityCheck` module. It structurally satisfies the provisional `QualityCheck` Protocol (`interfaces.py`) via its own `check()` method, with no import, inheritance, or runtime dependency on that Protocol — the same relationship `DuplicateHeaderCheck`, `MalformedRowCheck`, and `MissingValueScanner` each already have to it.

**Explicit statement:** DuplicateRsidCheck must not reuse, inherit from, or depend on `DuplicateHeaderCheck`, `MalformedRowCheck`, `MissingValueScanner`, or any other `QualityCheck` implementation, in any form — no shared base class, no imported helper function, no composed instance of a sibling check.

---

## 2. Implementation Contract

```
DuplicateRsidCheck.check(
    data_rows: Sequence[DataRow],
    rsid_column_index: int,
) -> Finding
```

**Implementation MUST:**
- Accept `rsid_column_index` as a pre-resolved, opaque `int` — perform no validation of its provenance or correctness beyond using it to index into `row.fields`.
- Scan the complete, unsampled `data_rows` collection — no row sampling of any kind.
- Identify RSID values (observed at `rsid_column_index`) that occur in two or more rows.
- Return exactly one `Finding` per call.

**Implementation MUST NOT:**
- Resolve column names or interpret header content.
- Inspect, import, or depend on `HeaderInfo` or `HeaderResolver`.
- Access files, perform network I/O, or depend on `RawFileLoader`.
- Parse raw data or depend on `RawLineSplitter` or `RowParser`.
- Perform schema detection of any kind, or presuppose a fixed file layout.
- Raise an exception for any data-quality condition (out-of-bounds index, empty input, absence of duplicates) — these are always represented as `Finding` data.

---

## 3. Algorithm Responsibility

The implementation must achieve the following behavior. The specific internal data structures used to achieve it (e.g. `collections.Counter`, plain `dict`, list comprehensions) are implementation details, not prescribed here — mirroring the identical latitude given to `MalformedRowCheck` and `MissingValueScanner`'s own internal helper methods. Do not introduce unnecessary internal structures, new classes, or additional public methods beyond what is needed to satisfy this contract.

Required behavior, at a minimum:

1. **Extract RSID observations from valid rows.** For each row in `data_rows`, if `rsid_column_index < len(row.fields)`, treat `row.fields[rsid_column_index]` as one RSID observation for that row.
2. **Ignore rows where `rsid_column_index` is outside row bounds.** Such a row contributes no observation. No exception is raised for this condition.
3. **Determine which RSID values occur two or more times** across the full, unsampled observation set.
4. **Determine all rows belonging to duplicated RSID groups** — i.e., every row whose observed RSID value is one of the values identified in step 3. There is no "first occurrence is exempt" concept: every row carrying a duplicated value belongs to the affected population, including the row where that value was first observed.
5. **Calculate `Finding.count`** as the size of the full affected-row population from step 4, computed over the complete, unsampled `data_rows` collection.
6. **Select bounded `examples` and `affected_row_refs`** from the affected-row population, ordered by ascending `DataRow.line_index`, capped at 10 entries each, per Section 4 below.

---

## 4. Finding Construction Rules

- **`check_name`:** `"duplicate_rsid_check"` — exact string, frozen.
- **`description`:** a short, human-readable string naming the number of duplicated RSID values and/or affected rows found. Exact wording is an implementation-level detail, not prescribed by this handoff, consistent with the same accepted gap in every prior check.
- **`count` semantics:** the total number of rows, across the full, unsampled `data_rows` collection, belonging to any duplicated-RSID group (every row whose RSID value occurs ≥2 times, summed across all such groups).

  **Frozen exclusions — `count` is explicitly NOT:**
  - the number of distinct duplicated RSID values, and
  - the number of "extra" occurrences after each value's first occurrence (no group-size-minus-one convention).

- **`examples` requirements:** a bounded sample, maximum 10 entries, of rendered rows drawn from the affected-row population, in ascending `DataRow.line_index` order. Rendering format is an implementation detail (mirror the style already used by `MalformedRowCheck._render_example` / `DuplicateHeaderCheck`'s equivalent, if convenient, but this is not mandated).
- **`affected_row_refs` requirements:** a bounded sample, maximum 10 entries, of the `line_index` values of the *same* sampled rows as `examples`, in the same order — `examples` and `affected_row_refs` must always describe the identical rows, index-for-index.
- **Maximum sample size:** 10, for both `examples` and `affected_row_refs`. `count` is never capped by this bound.
- **Ordering rule:** ascending `DataRow.line_index` across the full affected-row population; take the first 10 for the bounded sample. This ordering affects only which entries appear in `examples`/`affected_row_refs` — it has no effect on `count`.
- **Empty-result behaviour:** if `data_rows` is empty, or no RSID value occurs ≥2 times (including the case where `rsid_column_index` is out of bounds for every row, leaving zero observations), return a `Finding` with `count == 0`, `examples == ()`, `affected_row_refs == ()`.
- **Determinism:** `examples` and `affected_row_refs` must be derived from the affected-row population by direct `line_index` comparison — never from `dict`, `set`, or `Counter` iteration/insertion order, and never from `data_rows`' own traversal order.

---

## 5. Dependency Rules

**Allowed imports:**
- `phenopred.domain.entities.DataRow`
- `phenopred.domain.value_objects.Finding`
- Python standard library modules required for implementation

**Forbidden imports:**
- `HeaderInfo`
- `HeaderResolver`
- `RowParser`
- `RawFileLoader`
- `EncodingDetector`
- `DelimiterDetector`
- `RawLineSplitter`
- Any sibling `QualityCheck` (`DuplicateHeaderCheck`, `MalformedRowCheck`, `MissingValueScanner`, `DuplicateChrPosCheck`)
- Any `GenomicProfiler` module (`ChromosomeLabelProfiler`, `GenotypeLayoutClassifier`, `IndelHaploidClassifier`)
- `ReportBuilder`
- `phenopred.domain.errors` / `PhenoPredIngestionError` hierarchy

The implementation should pass AST-based dependency boundary checks — i.e. a structural scan of the module's import statements must show only the allowed domain imports plus standard library, with none of the forbidden substrings present, mirroring the AST check pattern already established in `test_malformed_row_check.py` and `test_missing_value_scanner.py`.

---

## 6. Edge Case Requirements

- **Empty input:** `data_rows == ()` → `Finding` with `count == 0`, `examples == ()`, `affected_row_refs == ()`. No exception.
- **No duplicates:** every observed RSID value occurs exactly once → `count == 0`, `examples == ()`, `affected_row_refs == ()`.
- **One duplicated RSID group:** exactly one RSID value occurs ≥2 times → all rows carrying that value are counted and (up to 10) sampled.
- **Multiple duplicated RSID groups:** two or more distinct RSID values each occur ≥2 times → rows from all groups are combined into a single affected-row population, counted together, and sampled together in ascending `line_index` order (not grouped or segmented by value).
- **More than 10 affected rows:** `examples`/`affected_row_refs` truncated to the first 10 in ascending `line_index` order; `count` reflects the full, uncapped total.
- **Malformed rows (some out of bounds):** rows where `rsid_column_index >= len(row.fields)` contribute no observation and are excluded from all duplicate consideration; no exception raised.
- **All rows malformed:** if `rsid_column_index` is out of bounds for every row, there are zero observations, and the result is the same as "empty input" — `count == 0`, `examples == ()`, `affected_row_refs == ()`. No exception.
- **Repeated execution with identical input:** calling `check()` twice with the same `data_rows` and `rsid_column_index` must produce a field-for-field identical `Finding` (NFR-3), regardless of the input collection's traversal order.

---

## 7. Non-Goals

DuplicateRsidCheck does **NOT**:

- Identify or resolve the RSID column — `rsid_column_index` is supplied, already resolved, by the caller.
- Validate whether a column is biologically or semantically correct as an RSID column.
- Perform genomic interpretation of any kind (e.g., judging whether duplication indicates a probe redesign, multi-allelic site, or artifact — per FR-8/RISK-4, that interpretation is explicitly out of scope for this SRS).
- Detect invalid or malformed RSID value *formats* (e.g., non-standard identifier patterns) — it observes and compares literal values only.
- Modify any `DataRow` instance or the supplied `data_rows` collection.
- Modify, extend, or reinterpret the `Finding` value object's structure.
- Integrate with any `QualityCheckRunner`, composition root, or orchestration component.
- Solve, design, or presuppose an answer to the shared column-name-to-role resolution architecture question (explicitly deferred in the Architecture Freeze Record).

---

## 8. Testing Expectations

The implementation must satisfy tests covering, at minimum:

- **Finding contract tests:** return type is `Finding`; `check_name == "duplicate_rsid_check"`.
- **Duplicate detection tests:** no duplicates; single duplicated RSID group; multiple duplicated RSID groups; mix of duplicated and non-duplicated values.
- **Count semantics tests:** `count` reflects total affected-row population, not distinct-duplicated-value cardinality, and not a group-size-minus-one ("extra occurrences") count.
- **Ordering tests:** `examples`/`affected_row_refs` in ascending `line_index` order; correct truncation to 10 entries when the affected population exceeds 10, with `count` remaining uncapped.
- **Malformed-row tests:** `rsid_column_index` out of bounds for some rows; out of bounds for all rows; confirms no exception and correct exclusion from observation.
- **Determinism tests:** repeated execution yields identical `Finding`; result independent of `data_rows` traversal order and independent of dict/set/`Counter` iteration order.
- **Mutation tests:** `data_rows`, individual `DataRow` instances, and `rsid_column_index` are never mutated.
- **Dependency-boundary tests:** AST-based import checks confirming only allowed domain imports and no forbidden imports.

---

## 9. Implementation Approval Criteria

Implementation is acceptable only if:

- All decisions frozen in ADR 1 (Column-Identity Input Contract) and ADR 2 (Finding Output Mapping) for DuplicateRsidCheck are respected without deviation.
- All rules recorded in `ARCHITECTURE_FREEZE_RECORD_DuplicateRsidCheck.md` are respected without deviation.
- The full test suite described in Section 8 above passes.
- No architecture or dependency boundary is violated, as confirmed by AST-based structural import checks.
- No new abstraction, value object, interface, or public method is introduced beyond what this handoff specifies.

---

## Final Handoff Status

**Scope:** This document translates already-frozen architecture into implementation instructions for `DuplicateRsidCheck` only. It introduces no new architectural decisions, reopens no ADR, and authorizes no scope beyond FR-8 as specified in ADR 1, ADR 2, and the Architecture Freeze Record.

**Status:** Ready for implementation.
