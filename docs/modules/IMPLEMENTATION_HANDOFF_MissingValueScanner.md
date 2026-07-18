- Stateless: no constructor-injected configuration, no mutable instance state.
- No other public methods.

---

## Inputs

- `data_rows: Sequence[DataRow]` — already-parsed rows, as produced by `RowParser`.
- `designated_column_indices: Sequence[int]` — zero, one, or more field-position indices, already resolved by the caller. Treat as opaque positional data. MissingValueScanner does not validate semantic correctness or origin, but performs required per-row bounds checking during observation.

---

## Outputs

- Exactly one `Finding`:
    - `check_name`: `"missing_value_scanner"`.
    - `description`: short, human-readable string naming designated columns scanned and distinct values found (exact wording is an implementation choice).
    - `count`: total number of literal token **occurrences** across all designated columns (a sum), over the full, unsampled `data_rows` collection. Not distinct-value count.
    - `examples`: bounded sample, maximum 10 entries, formatted as `"value (frequency)"` strings.
    - `affected_row_refs`: bounded sample, maximum 10 entries, `line_index` of one representative row per illustrated example, in matching order with `examples`.

---

## Dependency Boundaries

**Allowed:**
- `phenopred.domain.entities.DataRow`
- `phenopred.domain.value_objects.Finding`
- Python standard library modules required for implementation

**Forbidden:**
- `HeaderInfo`, `HeaderResolver`
- `RawFileLoader`, `EncodingDetector`, `DelimiterDetector`, `RawLineSplitter`, `RowParser` (class/module)
- Any sibling `QualityCheck` (`DuplicateHeaderCheck`, `MalformedRowCheck`, `DuplicateRsidCheck`, `DuplicateChrPosCheck`)
- Any `GenomicProfiler` (`ChromosomeLabelProfiler`, `GenotypeLayoutClassifier`, `IndelHaploidClassifier`)
- `ReportBuilder`, `ColumnCountDistribution`
- `phenopred.domain.errors` / `PhenoPredIngestionError` hierarchy

---

## Invariants

- `designated_column_indices` and `data_rows` are never mutated.
- `check()` must not raise exceptions for any valid input shape covered by this contract, including empty inputs and out-of-bounds column indices.
- Given the same `data_rows` and `designated_column_indices`, `check()` always returns a field-for-field identical `Finding`.

---

## Assumptions

- `designated_column_indices` has already been resolved upstream by domain-layer logic; `MissingValueScanner` performs no resolution or validation of how it was derived.
- `data_rows` may legitimately contain rows of varying field-count width (malformed rows are an expected input, not an anomaly this module screens for).
- The input collection's traversal order is not assumed to be `line_index`-ordered.

---

## Required Behaviour

- For each row and each index in `designated_column_indices`, if `index < len(row.fields)`, treat `row.fields[index]` as one observation.
- If the same column index appears multiple times in `designated_column_indices`, each occurrence in the sequence represents one observation according to the input contract.
- Tally frequency per distinct literal value across all observations.
- `count` = sum of all observation frequencies.
- Determine each distinct value's first-observed `line_index` (smallest `line_index` among rows where it was observed at any designated column).
- Select up to 10 distinct values for `examples`/`affected_row_refs` per the Ordering Rules below.
- Handle an empty `designated_column_indices` as zero designated columns (valid, contributes no observations).
- Handle empty `data_rows` as zero observations (valid).

---

## Prohibited Behaviour

- Do not perform column-name matching, header interpretation, or any dependency on `HeaderInfo`.
- Do not import or depend on any sibling `QualityCheck`, any `GenomicProfiler`, `ReportBuilder`, or `ColumnCountDistribution`.
- Do not introduce a new value object for the output.
- Do not raise an exception for out-of-bounds indices, empty input, or any other data-quality condition.
- Do not redefine `count` as distinct-value cardinality.
- Do not cap, sample, or otherwise limit `count` — it must always reflect the full, unsampled total.

---

## Deterministic Requirements

- Repeated calls with identical `data_rows`/`designated_column_indices` must return an identical `Finding`.
- Determinism must not depend on dictionary, set, or `Counter` iteration/insertion order.
- Determinism must not depend on the traversal order of `data_rows`.

---

## Malformed-Row Behaviour

- If a designated column index is `>= len(row.fields)` for a particular row, that row contributes no observation for that designated column.
- No exception is raised for this condition.
- This is normal data-quality input, not an error condition.

---

## Finding Output Rules

- Exactly one `Finding` is returned per `check()` call.
- `count`: total occurrence count across all designated columns (sum of all frequencies), not distinct-value count.
- `examples`: ≤10 entries, each formatted as `"value (frequency)"`.
- `affected_row_refs`: ≤10 entries, each the `line_index` of one representative row for the corresponding `examples` entry.
- `examples` and `affected_row_refs` must be in matching, corresponding order.

---

## Ordering Rules

- Primary sort key for bounded-sample selection: descending frequency (highest-frequency distinct value first).
- Secondary sort key (tie-break, used only when two or more distinct values share equal frequency): ascending first-observed `DataRow.line_index`.
- This ordering applies only to which entries populate `examples`/`affected_row_refs` — it does not affect `count`.

---

## Mutation Rules

- `data_rows` must not be mutated.
- Individual `DataRow` instances must not be mutated.
- `designated_column_indices` must not be mutated.

---

## Performance Expectations

- Must process the full, unsampled `data_rows` collection (no sampling) to compute `count`, consistent with the scale already handled by upstream frozen modules (approximately 630,000–680,000 rows per file, per NFR-1 precedent).
- A linear scan over the input is expected for observation collection. Additional deterministic processing for ordering the bounded sample is permitted.

---

## Testing Obligations

1. Unique modal case with no repeated values.
2. Repeated distinct values (frequency aggregation correctness).
3. More than 10 distinct values — `examples`/`affected_row_refs` truncated at 10; `count` remains the full, unsampled total.
4. Descending-frequency ordering, including a case where a high-frequency value would be excluded under a purely positional ordering.
5. Tie-break by ascending `line_index` when two or more distinct values share equal frequency.
6. Empty `designated_column_indices` — `count == 0`, `examples == ()`, `affected_row_refs == ()`.
7. Empty `data_rows` — `count == 0`, `examples == ()`, `affected_row_refs == ()`.
8. A designated index out of bounds for some, but not all, rows.
9. A designated index out of bounds for every row.
10. Multiple designated column indices simultaneously.
11. Deterministic repeated execution (NFR-3).
12. Ordering independent of dict/set/Counter iteration order — via structurally different but logically equivalent input construction paths.
13. Non-mutation of `data_rows`, individual `DataRow` instances, and `designated_column_indices`.
14. Dependency boundary checks (structural, AST-based): no forbidden imports; only allowed domain imports present.
15. Return type is `Finding`; `check_name == "missing_value_scanner"`.

---

## Non-Goals

- Column-name resolution or semantic interpretation of header content.
- Determining which literal token(s) represent "missing" or "no-call" — this module reports frequency only, without judgment.
- Producing a complete, unbounded per-value frequency table (only a ≤10-entry bounded sample is required).
- Any interaction with `RawFileLoader`, `EncodingDetector`, `DelimiterDetector`, `RawLineSplitter`, `RowParser`, `HeaderResolver`, any sibling `QualityCheck`, any `GenomicProfiler`, or `ReportBuilder`.
- Report generation, aggregation, or pipeline orchestration.