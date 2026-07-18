# Architecture Freeze Record: DuplicateRsidCheck (FR-8)

# Purpose

ADR 1 ("Column-Identity Input Contract for DuplicateRsidCheck") and ADR 2 ("Finding Output Mapping for DuplicateRsidCheck") are permanently frozen architecture decisions for the `DuplicateRsidCheck` module. They are authoritative, immutable, and binding on all future implementation and review activity unless explicitly superseded by a future ADR.

---

# Frozen Artifacts

## ADR 1 — Column-Identity Input Contract for DuplicateRsidCheck

- **Status:** Approved
- **Frozen:** Yes
- **Architecture Version:** PhenoPred Architecture v1
- **Decision Date:** 2026-07-15
- **Supersedes:** None
- **Superseded By:** None

## ADR 2 — Finding Output Mapping for DuplicateRsidCheck

- **Status:** Approved
- **Frozen:** Yes
- **Architecture Version:** PhenoPred Architecture v1
- **Decision Date:** 2026-07-15
- **Supersedes:** None
- **Superseded By:** None

---

# Evidence Reviewed

- PhenoPred SRS v1
- PhenoPred Architecture v1 (Approved)
- Stage 1 Engineering Review
- `phenopred/domain/interfaces.py`
- `phenopred/domain/entities.py`
- `phenopred/domain/value_objects.py`
- `phenopred/domain/errors.py`
- Frozen ADR: Architecture Decision Record — Modal Column Count Tie-Breaking Rule for MalformedRowCheck (FR-5)
- Frozen ADRs: Column-Identity Input Contract for MissingValueScanner (FR-6); Finding Output Mapping for MissingValueScanner (FR-6)
- Architecture Freeze Record — MissingValueScanner
- DuplicateHeaderCheck Module Approval and Handoff Record
- MalformedRowCheck Module Approval Record
- MissingValueScanner Module Approval Record
- Existing frozen implementations: `duplicate_header_check.py`, `malformed_row_check.py`, `missing_value_scanner.py`
- Existing frozen test suites: `test_duplicate_header_check.py`, `test_malformed_row_check.py`, `test_missing_value_scanner.py`
- ADR 1 — Column-Identity Input Contract for DuplicateRsidCheck (FR-8) (this cycle)
- ADR 2 — Finding Output Mapping for DuplicateRsidCheck (FR-8) (this cycle)

---

# 1. Module Identity

- **Module name:** DuplicateRsidCheck
- **Requirement identifier:** FR-8
- **Traceability references:** SRS FR-8, OUT-7, NFR-3, NFR-5, NFR-6
- **Production file path (planned):** `phenopred/domain/quality_checks/duplicate_rsid_check.py`
- **Responsibility boundary:** Given a file's parsed `DataRow` collection and an already-resolved RSID column field-position index, determine which rows carry an RSID value that occurs in two or more rows of the file, and report the result as exactly one `Finding`. It does not resolve which column is the RSID column, does not perform header interpretation, and does not perform file/network I/O of any kind.
- **Domain ownership:** Domain layer (`phenopred/domain/quality_checks/`), pure logic, no file/network/external-service I/O.
- **Architecture version reference:** PhenoPred Architecture v1 (Approved)

---

# 2. Frozen Input Contract

## Public Contract

```
DuplicateRsidCheck.check(
    data_rows: Sequence[DataRow],
    rsid_column_index: int,
) -> Finding
```

## Frozen Rules

1. `rsid_column_index` is a single, pre-resolved field-position index, supplied through the `QualityCheck` interface's `context` parameter, narrowed to a concrete `int` type — the same extension mechanism `DuplicateHeaderCheck` (`HeaderInfo`) and `MissingValueScanner` (`Sequence[int]`) each already use with a different concrete type.
2. `DuplicateRsidCheck` performs no resolution, name-matching, or interpretation of `rsid_column_index` beyond using it to index into `row.fields`.
3. `DuplicateRsidCheck` has no dependency on `HeaderInfo`, `HeaderResolver`, or any mechanism that maps column names to semantic roles. Resolution of `rsid_column_index` from `HeaderInfo.resolved_columns` (or any other source) is domain-layer work belonging elsewhere, not to this module.
4. `DuplicateRsidCheck` performs no parsing, no delimiter detection, no encoding detection, no file/network I/O, and has no dependency on `RawFileLoader`, `RawLineSplitter`, or `RowParser`.
5. **Malformed-row behaviour:** if `rsid_column_index >= len(row.fields)` for a given row, that row contributes no observation for duplicate-RSID detection. No exception is raised. This is normal data-quality input, not an error condition, per Architecture v1 §13.2.
6. **Full-scan requirement:** the entire, unsampled `data_rows` collection is scanned; no row is skipped for any reason other than the out-of-bounds condition in Rule 5.
7. `data_rows` and `rsid_column_index` are never mutated. Individual `DataRow` instances are never mutated.

---

# 3. Frozen Output Contract

## Frozen Rules

1. `DuplicateRsidCheck.check()` returns exactly one `Finding` — no more, no fewer. No new value object is introduced; the frozen `Finding` contract is used unmodified.
2. `Finding.check_name` = `"duplicate_rsid_check"`.
3. **Definition of duplicate RSID detection:** an RSID value (observed at `rsid_column_index`) is "duplicated" when it occurs in two or more rows of the full, unsampled `data_rows` collection. Every row carrying a duplicated RSID value is part of the affected population — there is no "first occurrence is exempt" rule. This is a symmetric relation among rows; no row is treated as more "original" than another.
4. **`Finding.count` semantics:** `count` = the total number of rows, across the full, unsampled `data_rows` collection, belonging to any duplicated-RSID group (i.e., every row whose RSID value occurs ≥2 times, summed across all such groups).

   **Explicitly, `count` is NOT:**
   - the number of *distinct* duplicated RSID values, and
   - the number of *extra* occurrences after each value's first occurrence (i.e., not a group-size-minus-one convention).

5. **`Finding.examples`:** a bounded sample, maximum 10 entries, of rendered rows belonging to a duplicated-RSID group, in ascending `DataRow.line_index` order. Exact rendering format is an implementation-level detail, not prescribed by this record, consistent with the identical, already-accepted gap in `MalformedRowCheck`'s and `DuplicateHeaderCheck`'s own example-rendering methods.
6. **`Finding.affected_row_refs`:** a bounded sample, maximum 10 entries, of the `line_index` values of the same sampled rows as `examples`, in the same ascending order.
7. **Maximum sample size:** 10 entries for both `examples` and `affected_row_refs`, uncapped `count` (always reflects the full, unsampled total).
8. **Ordering rule:** rows belonging to any duplicated-RSID group are sorted by ascending `DataRow.line_index` for bounded-sample selection; this ordering governs only which ≤10 entries populate `examples`/`affected_row_refs` and has no effect on `count`.
9. **Empty-input behaviour:** if `data_rows` is empty, or no RSID value occurs ≥2 times, the returned `Finding` has `count == 0`, `examples == ()`, `affected_row_refs == ()`.
10. **Deterministic behaviour:** given the same `data_rows` and `rsid_column_index`, `check()` always returns a field-for-field identical `Finding` (NFR-3). Determinism does not depend on dictionary, set, or `Counter` iteration/insertion order, nor on the traversal order of `data_rows`.

---

# 4. Dependency Boundary

## Allowed

- `phenopred.domain.entities.DataRow`
- `phenopred.domain.value_objects.Finding`
- Python standard library only

## Forbidden

- `HeaderInfo`
- `HeaderResolver`
- `RawFileLoader`
- `EncodingDetector`
- `DelimiterDetector`
- `RawLineSplitter`
- `RowParser`
- Any sibling `QualityCheck` (`DuplicateHeaderCheck`, `MalformedRowCheck`, `MissingValueScanner`, `DuplicateChrPosCheck`)
- Any `GenomicProfiler` (`ChromosomeLabelProfiler`, `GenotypeLayoutClassifier`, `IndelHaploidClassifier`)
- `ReportBuilder`
- `phenopred.domain.errors` / `PhenoPredIngestionError` hierarchy

## Confirmation

`DuplicateRsidCheck` remains an isolated domain-layer component. It has no direct or transitive dependency on ingestion, detection, header resolution, sibling quality checks, genomic profiling, reporting, or the exception hierarchy. Its contract is fully expressed as plain data in (`Sequence[DataRow]`, `int`) and plain data out (`Finding`).

---

# 5. Clean Architecture and DDD Compliance

- **Domain-layer ownership:** `DuplicateRsidCheck` lives in `phenopred/domain/quality_checks/`, alongside its already-frozen siblings, with no infrastructure or application-layer code.
- **Dependency direction:** dependencies point inward only — `DuplicateRsidCheck` depends on `DataRow` and `Finding` (both domain entities/value objects) and nothing outward-facing (no infrastructure adapters, no application-layer orchestration).
- **No orchestration responsibility:** `DuplicateRsidCheck` does not sequence pipeline steps; that responsibility belongs exclusively to `application/profile_file_use_case.py`, per Architecture v1's module table.
- **No integration responsibility:** registration into any `QualityCheckRunner` or composition root is out of scope for this module and this freeze record.
- **No premature abstraction:** no new interface, base class, or value object is introduced. `DuplicateRsidCheck` structurally satisfies the existing, still-provisional `QualityCheck` Protocol via its `check()` method, with no import or inheritance relationship to it, mirroring `DuplicateHeaderCheck`'s, `MalformedRowCheck`'s, and `MissingValueScanner`'s identical pattern.
- **Findings-as-data principle:** the duplicate-RSID condition is reported exclusively as `Finding` data. No exception is raised for this or any other data-quality condition (Architecture v1 §13.2).

---

# 6. Deterministic Behaviour

- **Full scan of `data_rows`:** the entire, unsampled collection is scanned to compute `count`; no sampling is performed during detection (distinct from the sample-based encoding/delimiter detectors named in Architecture v1's risk register).
- **Bounded sampling only for `examples`/`affected_row_refs`:** the 10-entry cap applies solely to the reported sample, never to `count`.
- **Identical input produces an identical `Finding`:** repeated calls with the same `data_rows` and `rsid_column_index` always yield a field-for-field identical `Finding` (NFR-3).
- **No dependency on dictionary/set iteration ordering:** determinism is derived solely from `DataRow.line_index` value comparisons during bounded-sample ordering, never from `dict`, `set`, or `Counter` iteration/insertion order, and never from the input collection's own traversal order.

---

# 7. Testing Obligations

The future `DuplicateRsidCheck` test suite must, at minimum, cover:

1. No duplicated RSID values present — `count == 0`, `examples == ()`, `affected_row_refs == ()`.
2. A single duplicated RSID value (two or more rows sharing it).
3. Multiple distinct duplicated RSID groups simultaneously.
4. A mix of duplicated and non-duplicated RSID values — non-duplicated rows correctly excluded from `count`/`examples`/`affected_row_refs`.
5. More than 10 affected rows — `examples`/`affected_row_refs` truncated at 10 in ascending `line_index` order; `count` remains the full, unsampled total.
6. Empty `data_rows` — zero-count `Finding`, no exception.
7. Malformed/out-of-bounds rows — `rsid_column_index` outside a row's `fields` bounds contributes no observation and is correctly excluded; no exception raised, for some-rows-affected and all-rows-affected cases alike.
8. Deterministic repeated execution (NFR-3); result independent of input traversal order and independent of dict/set/`Counter` iteration order.
9. Non-mutation of `data_rows`, individual `DataRow` instances, and `rsid_column_index`.
10. Dependency-boundary checks (structural, AST-based): no forbidden imports; only allowed domain imports (`phenopred.domain.entities`, `phenopred.domain.value_objects`) present.
11. `Finding` contract validation: return type is `Finding`; `check_name == "duplicate_rsid_check"`.

---

# 8. Explicitly Deferred Decisions

- The shared column-name-to-role resolution mechanism (how `HeaderInfo.resolved_columns` maps to `rsid_column_index`), affecting `MissingValueScanner`, `DuplicateRsidCheck`, and the future `DuplicateChrPosCheck` alike, remains unresolved.
- `DuplicateChrPosCheck`'s (FR-9) own future context shape, and whether it will be compatible with `DuplicateRsidCheck`'s single-`int` context, remains unresolved and is not anticipated here.
- Any future requirement beyond the 10-entry bounded sample (e.g. a complete, unbounded duplicate-group listing) is not addressed and is not anticipated by these ADRs.
- Orchestration/integration design (registration into a future `QualityCheckRunner`, composition-root wiring) is out of scope for this record.
- Evolution of the still-provisional `QualityCheck` Protocol signature is not undertaken here; it remains validated, as before, by its existing three implementers plus this fourth.

---

# Future ADR Candidates

- The shared column-name-to-role resolution mechanism, once designed, may itself require a dedicated ADR.

---

# Implementation Authorization

Implementation of `DuplicateRsidCheck` may proceed using these ADRs without further architectural review unless a future ADR explicitly supersedes them.

---

# Freeze Approval Checklist

- [x] ADR 1 frozen
- [x] ADR 2 frozen
- [x] Architecture consistency verified
- [x] SRS consistency verified
- [x] Clean Architecture consistency verified
- [x] DDD consistency verified
- [x] Implementation authorized
