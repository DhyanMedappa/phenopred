# Architecture Freeze Record: MissingValueScanner (FR-6)

# Purpose

ADR 1 ("Column-Identity Input Contract for MissingValueScanner") and ADR 2 ("Finding Output Mapping for MissingValueScanner") are permanently frozen architecture decisions for the `MissingValueScanner` module. They are authoritative, immutable, and binding on all future implementation and review activity unless explicitly superseded by a future ADR.

---

# Frozen Artifacts

## ADR 1 — Column-Identity Input Contract for MissingValueScanner

- **Status:** Approved
- **Frozen:** Yes
- **Architecture Version:** PhenoPred Architecture v1
- **Decision Date:** 2026-07-15
- **Supersedes:** None
- **Superseded By:** None

## ADR 2 — Finding Output Mapping for MissingValueScanner

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
- RawFileLoader Module Approval & Handoff Record
- EncodingDetector Module Approval & Handoff Record
- RawLineSplitter Module Approval & Handoff Record
- HeaderResolver Module Approval Record
- RowParser and DataRow Module Approval & Handoff Record
- DuplicateHeaderCheck Module Approval and Handoff Record
- MalformedRowCheck Module Approval Record
- Existing frozen implementations: `duplicate_header_check.py`, `malformed_row_check.py`
- Existing frozen test suites: `test_duplicate_header_check.py`, `test_malformed_row_check.py`

---

# Canonical Implementation Summary

## ADR 1 Summary

1. `MissingValueScanner.check()` takes two parameters: `data_rows: Sequence[DataRow]` and `designated_column_indices: Sequence[int]`.
2. `designated_column_indices` is delivered via the `QualityCheck` interface's `context` parameter, narrowed to a concrete type — the same pattern `DuplicateHeaderCheck` uses for `HeaderInfo`.
3. `designated_column_indices` is a plain `Sequence[int]` — no new value object is introduced.
4. `MissingValueScanner` performs no column-name resolution, no header interpretation, and has no dependency on `HeaderInfo`, `HeaderResolver`, or any `GenomicProfiler`.
5. The logic that derives `designated_column_indices` from `HeaderInfo.resolved_columns` (or any other source) belongs to the domain layer, not `ProfileFileUseCase`.
6. That resolution logic itself is not designed, named, or stubbed by this ADR.
7. For each row, for each index in `designated_column_indices`: if `index < len(row.fields)`, the value at that position is one observation.
8. If an index is `>= len(row.fields)` for a given row, that row contributes no observation for that index — this is normal input, not an error.
9. `MissingValueScanner` never raises an exception for this or any other data-quality condition.
10. `data_rows` and `designated_column_indices` are never mutated.

## ADR 2 Summary

1. `MissingValueScanner.check()` returns exactly one `Finding` — no more, no fewer.
2. No new value object is introduced; the frozen `Finding` contract is used unmodified.
3. `Finding.count` = the total number of literal token occurrences observed across all designated columns (a sum), computed over the full, unsampled `data_rows` collection.
4. `Finding.count` is **not** the number of distinct literal values.
5. `Finding.examples` is a bounded sample, maximum 10 entries, formatted as `"value (frequency)"` strings, one per distinct literal value.
6. `Finding.affected_row_refs` is a bounded sample, maximum 10 entries, each the `line_index` of one representative row for the corresponding `examples` entry, in matching order.
7. Bounded-sample selection ordering: primary key is descending frequency; secondary tie-break key is ascending first-observed `DataRow.line_index`.
8. This ordering governs only which ≤10 entries appear in `examples`/`affected_row_refs` — it has no effect on `count`.
9. `Finding.check_name` = `"missing_value_scanner"`.
10. `Finding.description` is a short, human-readable string; its exact wording is an implementation detail not prescribed by the ADR.

---

# Explicitly Deferred Decisions

- The shared column-name-to-role resolution mechanism (how `HeaderInfo.resolved_columns` maps to semantic column meaning), affecting `MissingValueScanner`, `DuplicateRsidCheck`, and `DuplicateChrPosCheck` alike, remains unresolved.
- Whether sibling checks (`DuplicateRsidCheck`, `DuplicateChrPosCheck`) will use a `context` shape compatible with `MissingValueScanner`'s `Sequence[int]` remains unresolved.
- Any future requirement for a complete, unbounded per-value frequency table (beyond the 10-entry bounded sample) is not addressed and is not anticipated by these ADRs.

---

# Future ADR Candidates

- Per-column vs aggregated missing-value frequency reporting.

---

# Implementation Authorization

Implementation of MissingValueScanner may proceed using these ADRs without further architectural review unless a future ADR explicitly supersedes them.

---

# Freeze Approval Checklist

- [x] ADR 1 frozen
- [x] ADR 2 frozen
- [x] Architecture consistency verified
- [x] SRS consistency verified
- [x] Clean Architecture consistency verified
- [x] DDD consistency verified
- [x] Implementation authorized
