# FR-9 DuplicateChrPosCheck Module Approval Record

## 1. Module Overview

- **Module name:** DuplicateChrPosCheck
- **Requirement ID:** FR-9
- **Architectural layer:** Domain Layer
- **Primary responsibility:** Given a file's parsed DataRow collection and an already-resolved ChrPosColumnIndices, determine which rows carry a (chromosome, position) pair that occurs in two or more rows of the file, and report the result as exactly one Finding.
- **Approved implementation files:**
  - `phenopred/domain/quality_checks/duplicate_chr_pos_check.py`
  - `phenopred/domain/value_objects.py` (additive: `ChrPosColumnIndices`)
  - `tests/unit/domain/quality_checks/test_duplicate_chr_pos_check.py`

---

## 2. Implementation Summary

DuplicateChrPosCheck exists to satisfy FR-9's requirement to detect and report (chromosome, position) pairs that occur more than once within a single file. It receives its input exclusively through the frozen `ChrPosColumnIndices` value object, which carries two already-resolved field-position indices — `chromosome_column_index` and `position_column_index` — as opaque, already-resolved positional data. The module performs no resolution of these indices from column names or header content; that responsibility remains outside this module's boundary.

The module's output is expressed exclusively through the existing Finding value object and follows the approved Finding Output Mapping ADR. DuplicateChrPosCheck produces exactly one Finding per invocation, describing the population of rows affected by chromosome-position duplication.

The module observes duplicated chromosome-position pairs only. It does not determine, classify, or report the cause of any duplication (e.g. probe redesign, multi-allelic site, or data artifact), and it performs no corrective action, transformation, or normalization of any observed value. Its function is limited strictly to detection and reporting.

---

## 3. Architecture Compliance

- **ADR 1 — Column Identity Input Contract for DuplicateChrPosCheck:** the module's `check()` method accepts only `Sequence[DataRow]` and `ChrPosColumnIndices`, consistent with the frozen input contract. No alternative shape (bare parameters, sequence, anonymous tuple) is present.
- **ADR 2 — Finding Output Mapping for DuplicateChrPosCheck:** the module's output mapping — `check_name`, `count`, `examples`, and `affected_row_refs` — conforms to the frozen Finding Output Mapping decision without deviation.
- **Domain-layer responsibility boundaries:** the module resides in `phenopred/domain/quality_checks/`, contains no infrastructure or application-layer logic, and depends only on domain-layer entities and value objects.
- **No file I/O:** the module performs no file or network access of any kind; it operates exclusively on the already-in-memory `data_rows` argument.
- **No header resolution:** the module contains no dependency on `HeaderInfo`, `HeaderResolver`, or any column-name interpretation logic.
- **No forbidden upstream/downstream dependencies:** the module's imports are limited to `phenopred.domain.entities.DataRow`, `phenopred.domain.value_objects.{ChrPosColumnIndices, Finding}`, and the Python standard library. No dependency exists on `RawFileLoader`, `EncodingDetector`, `DelimiterDetector`, `RawLineSplitter`, `RowParser`, any sibling `QualityCheck`, any `GenomicProfiler`, `ReportBuilder`, or the `phenopred.domain.errors` hierarchy.

---

## 4. Algorithm Approval

The following algorithmic behavior is approved and frozen:

- Duplicate identity is defined as the exact tuple: (chromosome, position).
- Comparison between observed pairs uses exact literal string equality.
- No trimming, normalization, case conversion, numeric coercion, or biological interpretation is applied to either component of the pair.
- The first occurrence of a duplicated pair is not excluded from the affected population; there is no "first occurrence is exempt" rule.
- Every row belonging to a duplicated pair group is counted, without exception.
- `Finding.count` represents the total affected-row population across all duplicated-pair groups, not the number of distinct duplicated pairs and not a group-size-minus-one ("extra occurrences") quantity.
- Affected rows are ordered deterministically using ascending `DataRow.line_index`.
- Rows missing either the required chromosome field or the required position field do not contribute an observation.
- No partial chromosome-position pair is created from a row where only one of the two required fields is present.
- Column indices must satisfy `0 <= index < len(row.fields)` for both the chromosome and position indices jointly; a row failing this condition for either index contributes no observation.
- Negative Python indices cannot accidentally access fields from the end of a row's field tuple; the explicit lower-bound condition prevents this class of incorrect observation.

---

## 5. Finding Output Mapping Approval

- **`check_name` behavior:** fixed to the stable label `duplicate_chr_pos_check` for every invocation.
- **`description` behavior:** a short, human-readable statement identifying the number of duplicated pairs found; exact wording is not architecturally constrained.
- **`count` semantics:** the total number of rows, across the full, unsampled data-row collection, whose observed (chromosome, position) pair occurs in two or more rows.
- **`examples` behavior:** a bounded sample of rendered rows drawn from the affected-row population, in ascending `line_index` order.
- **`affected_row_refs` behavior:** a bounded sample of `line_index` values corresponding to the same rows represented in `examples`, in the same order.
- **Maximum sample size constraint:** both `examples` and `affected_row_refs` are bounded to a maximum of 10 entries; `count` is never capped by this bound.
- **Relationship between `examples` and `affected_row_refs`:** both fields are derived from the identical sampled-row population, in identical order, ensuring index-for-index correspondence between the two fields.

---

## 6. Test Verification Record

**Test file:** `tests/unit/domain/quality_checks/test_duplicate_chr_pos_check.py`

**Verification result:** 37 passed, 0 failed, 0 skipped.

**Verified coverage:**
- Finding contract (return type, `check_name` stability)
- Duplicate detection (single duplicated pair)
- Multiple duplicate groups (combined into one Finding)
- No duplicate cases (zero-count Finding)
- Composite chromosome-position key behavior (same chromosome/different position, and reverse, correctly treated as non-duplicate)
- Literal equality behavior (leading-zero and case variants correctly treated as distinct)
- Negative index regression handling (chromosome-only, position-only, and combined negative-index cases)
- Out-of-bounds handling (positive out-of-bounds for chromosome, position, both, and mixed row populations)
- No partial pair creation (rows with only one qualifying field excluded entirely)
- Affected row count semantics (row-population count verified distinct from duplicated-pair count and from extra-occurrence count)
- More than 10 affected rows sampling (truncation to 10 entries with `count` remaining uncapped)
- Deterministic ordering (repeated execution, input traversal order, and dict/set/Counter iteration order independence)
- Input non-mutation (`data_rows`, individual `DataRow` instances, and `ChrPosColumnIndices` confirmed unchanged)
- Dependency boundary checks (structural, AST-based verification of allowed and forbidden imports)

**Regression verification:**

DuplicateRsidCheck: 27 passed, 0 failed.

**Status:** Unchanged and unaffected.

---

## 7. Final Approval Decision

**Status:**
APPROVED

**Decision:**
ACCEPTED — FR-9 implementation is complete

---

## 8. Frozen Implementation Statement

FR-9 implementation is frozen after approval. Any future behavioral change requires a new review cycle. This approval confirms conformance with the approved ADRs, architecture constraints, and verification criteria.
