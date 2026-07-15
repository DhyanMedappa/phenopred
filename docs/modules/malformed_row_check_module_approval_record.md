# MalformedRowCheck — Module Approval Record

## 1. Module Identity

- **Module name:** MalformedRowCheck
- **Requirement identifier:** FR-5
- **Production file path:** `phenopred/domain/quality_checks/malformed_row_check.py`
- **Test file path:** `phenopred/tests/unit/domain/quality_checks/test_malformed_row_check.py`
- **Layer ownership:** Domain layer (`phenopred/domain/quality_checks/`), pure logic, no file/network/external-service I/O of any kind
- **Implementation status:** Complete, tested, approved, frozen

---

## 2. Purpose and Responsibility

**Problem solved:** determining, for a single file's parsed data rows, which rows have a field count that deviates from the file's own dominant ("modal") field count, and reporting this as one `Finding`.

**MalformedRowCheck:**
- receives parsed `DataRow` objects.
- determines the file's modal column count, empirically, from those rows.
- identifies malformed rows (`len(row.fields) != modal_count`).
- produces exactly one `Finding`.

**It does NOT:**
- parse files.
- detect delimiters.
- detect encoding.
- resolve headers.
- use schemas (fixed, external, or header-derived).
- implement `ColumnCountDistribution`.
- perform reporting/aggregation.

Responsibilities not owned by this module remain, respectively, with `RawFileLoader`, `DelimiterDetector`, `EncodingDetector`, `RawLineSplitter`, `HeaderResolver`, `RowParser`, any other `QualityCheck` implementation, and the future, still-deferred `ReportBuilder`/`ColumnCountDistribution` design.

---

## 3. Frozen Architecture Decisions

### Deferred Decision B.4 Resolution

**Exact decision:** "First observed column count wins, where first observed is defined by ascending `DataRow.line_index` ordering."

- Frequency of each observed field count (`len(row.fields)`) is calculated first, across the full row collection.
- If two or more field-count values are tied for the highest observed frequency, the tie is resolved by selecting the candidate belonging to the row with the smallest `DataRow.line_index` among all rows whose field count is one of the tied candidates.
- This is a **deterministic reporting convention only** — it exists solely to guarantee a single, reproducible outcome when the data itself provides no unambiguous mode.
- It does **not** imply that earlier rows are more correct, more trustworthy, or more representative of the file's true schema, and it does **not** imply that later rows are less valid.
- **No field-count magnitude preference exists** — the rule is anchored strictly to `line_index` comparison, never to whether a candidate's field count is numerically smaller or larger than another's.

This decision is frozen and must not be reopened by any future module or refactor.

---

## 4. Input Contract

**Input:** a collection of `DataRow` objects (e.g., `Sequence[DataRow]`), matching `RowParser`'s output shape.

**Allowed `DataRow` properties:**
- `line_index`
- `fields`

**Field count calculation:** `len(row.fields)`, computed per row; no casting, coercion, or interpretation of field contents occurs.

**Ordering assumptions:** the module does not assume the input collection is presented in `line_index` order. Modal-count tie resolution is anchored to `line_index` **values** via direct comparison, never to input traversal order, dictionary/set iteration order, or `Counter` insertion order. `Finding.examples`/`affected_row_refs` ordering is likewise derived by explicitly sorting malformed rows by `line_index`, not by assuming the input arrives pre-sorted.

**Deterministic behaviour:** given the same `DataRow` collection (regardless of its presentation order), `check()` always returns a field-for-field identical `Finding`.

**Duplicate `line_index` behaviour:**
- `line_index` uniqueness is an inherited precondition from the frozen `RowParser`/`DataRow` contract (positional assignment via `enumerate()` over a single sequence cannot itself produce duplicates).
- A `DataRow` collection containing duplicate `line_index` values is invalid input, outside this module's contract.
- Behaviour under duplicate `line_index` input is intentionally undefined.
- `MalformedRowCheck` does not validate, detect, or resolve duplicate `line_index` values — this is an upstream contract-integrity concern, not this module's responsibility.

---

## 5. Algorithm Specification

**Step 1:** Calculate the frequency of each observed `len(row.fields)` value across the full `DataRow` collection.

**Step 2:** Determine the maximum frequency among all distinct observed field-count values.

**Step 3:** Identify the set of all field-count values tied for that maximum frequency ("modal candidates").

**Step 4:** If more than one modal candidate exists, resolve the tie by selecting the candidate belonging to the row with the smallest `DataRow.line_index` among all rows whose field count is a modal candidate.

**Step 5:** Classify every row: malformed if and only if `len(row.fields) != modal_count`.

**Step 6:** Construct and return exactly one `Finding` summarizing the result.

---

## 6. Output Contract

**`check_name`:** `"malformed_row_check"`

**`description`:** a short, human-readable statement naming the selected modal column count and what was compared.

**`count`:** the full, unsampled number of malformed rows across the entire input collection — never capped or affected by any sampling bound.

**`examples`:**
- bounded sample, maximum 10 entries.
- malformed rows only.
- ascending `line_index` order.

**`affected_row_refs`:**
- bounded sample, maximum 10 entries.
- `line_index` values only, of malformed rows.
- ascending `line_index` order.

**Confirmation:** `Finding` semantics are inherited from the existing, frozen `Finding` value object without modification — no new field was added, and no existing field's meaning was reinterpreted.

---

## 7. Dependency Boundary

**Allowed:**
- `phenopred.domain.entities.DataRow`
- `phenopred.domain.value_objects.Finding`
- Python standard library only

**Forbidden:**
- `HeaderInfo`
- `HeaderResolver`
- `RawFileLoader`
- `EncodingDetector`
- `DelimiterDetector`
- `RawLineSplitter`
- `RowParser`
- `ReportBuilder`
- `ColumnCountDistribution`

**Why these boundaries exist:** they guarantee the modal-count computation and malformed-row classification are derivable solely from the file's own observed `DataRow` population, with no direct or transitive path by which an external or header-derived expectation could influence the result. This preserves NFR-5's schema-neutrality requirement, keeps the module fully testable in isolation with plain data in and plain data out, and keeps this module fully decomposable from the still-open, deferred `ColumnCountDistribution`/`ReportBuilder` design questions.

---

## 8. Implementation Details

- **Class:** `MalformedRowCheck`
- **Public method:** `check(data_rows: Sequence[DataRow]) -> Finding`
- **Input:** `Sequence[DataRow]`
- **Output:** `Finding`
- **Internal helpers:** modal-count resolution (private tie-break logic anchored to `line_index`); example rendering (private, illustrative string formatting of a malformed row).
- **State:** Stateless — no constructor-injected configuration, no mutable instance state.
- **Configuration:** None.

---

## 9. Testing Evidence

**Total tests:** 21

**Categories covered:**
- unique modal column count.
- malformed row detection.
- two-way tie resolution.
- multi-way tie resolution.
- line_index priority verification (tie resolution independent of field-count magnitude).
- deterministic execution (repeated calls).
- input traversal independence (shuffle test).
- empty input.
- single row.
- same-width rows.
- non-sequential line_index.
- >10 malformed rows (truncation and uncapped `count`).
- Finding validation (`check_name`, return type, count accuracy).
- mutation checks (input collection and `DataRow` instances).
- dependency boundary AST checks (no forbidden imports, only allowed domain imports).

**Result:** All 21 tests passed. Consistent with every prior module's approval record, execution occurred in a stdlib-only environment with no network access to install real `pytest`; a full re-run under genuine `pytest` in CI remains a standing, open item shared across the entire project.

---

## 10. Known Non-Responsibilities and Deferred Items

**Not implemented by this module:**
- `ColumnCountDistribution`.
- Report generation/aggregation.
- Pipeline orchestration.
- Integration with a future `QualityCheckRunner`.

These are not missing features. They are intentionally outside this module's scope, per its frozen responsibility boundary, and remain the subject of separate, still-deferred architectural decisions.

---

## 11. Future Module Integration Rules

Future modules and developers must:
- treat `MalformedRowCheck`'s contract, as documented here, as frozen.
- not change or reopen the Deferred Decision B.4 tie-breaking rule.
- not introduce a `HeaderInfo` dependency into `MalformedRowCheck`.
- not assume `modal_count` equals, represents, or validates any external schema.
- not depend on `MalformedRowCheck`'s internal helper methods or implementation details.
- interact with `MalformedRowCheck` only through its public `check()` method and its `Finding` output.

---

## 12. Approval Decision

Status:
Approved

Decision:
MalformedRowCheck is complete and frozen for downstream integration.
