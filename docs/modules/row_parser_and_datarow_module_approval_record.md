# Module Approval & Handoff Record: `RowParser` and `DataRow`

**Status:** Final — frozen reference for future module integration
**Architecture:** PhenoPred Architecture v1 (Approved)
**Traceability:** SRS FR-4, NFR-2, NFR-3, NFR-5

---

## 1. Module Identification

| Field | Value |
|---|---|
| Module names | `RowParser`, `DataRow` |
| Production files | `phenopred/domain/entities.py` (defines `DataRow`); `phenopred/domain/ingestion/row_parser.py` (defines `RowParser`) |
| Test files | `tests/unit/domain/test_entities.py`; `tests/unit/domain/ingestion/test_row_parser.py` |
| Architectural layer | Domain (pure logic; no file/network/external-service I/O of any kind) |
| Related SRS functional requirement | FR-4 — split each data line into fields using the detected delimiter, without casting, coercing, trimming, or otherwise altering field values |
| Responsibility classification | `RowParser`: FR-4 implementation (behavior). `DataRow`: immutable domain data structure representing one parsed row and immutable domain value object located in domain/entities.py according to Architecture v1 naming. |
| Related Architecture clauses | Architecture v1 §4 (folder placement for both), §5 (row_parser responsibility), §6 step 6 (data-flow position), §7.2 (DataRow does not know its own correctness), §8 (DataRow entity definition), §10 (interface table — RowParser absent, confirming non-`Detector[T]` status) |

`RowParser` is the sixth pipeline module in the ingestion pipeline, following `RawFileLoader`, `EncodingDetector`, `DelimiterDetector`, `RawLineSplitter`, and `HeaderResolver`. Its two required inputs (`Sequence[str]` effective data lines, `Delimiter`) are produced by upstream pipeline stages; header exclusion is an upstream responsibility and `RowParser` receives only the resulting effective data lines.; no new upstream dependency was introduced.

---

## 2. Approved Responsibility Boundary

**`RowParser` owns, exclusively:**
- Mechanically splitting each already-in-memory, effective data line into an ordered sequence of field strings, using the delimiter character supplied by an already-detected `Delimiter` value object.
- Preserving every field value exactly as split — no casting, coercion, trimming, or other alteration.
- Assigning each resulting row a zero-based, positional `line_index`, computed over the exact sequence of lines `RowParser` receives.
- Producing an ordered `tuple[DataRow, ...]`, one entry per input line, in original order.

**`RowParser` explicitly does NOT own, and does not perform:**
- File loading or any file/network I/O of any kind (owned exclusively by `RawFileLoader`).
- Comment/data line separation (FR-1, owned exclusively by `RawLineSplitter`).
- Delimiter detection (FR-2, owned exclusively by `DelimiterDetector`); `Delimiter` is consumed as an already-computed input, never re-derived.
- Header detection or header-exclusion (FR-3, owned exclusively by `HeaderResolver`'s detection and `ProfileFileUseCase`'s "effective data rows" hand-off, per `header_resolver_module_approval_record.md` §2). `RowParser` has no awareness of headers or comments whatsoever.
- Malformed-row detection or any column-count judgment (FR-5, the future `MalformedRowCheck`'s exclusive responsibility).
- Missing-value detection (FR-6, the future `MissingValueScanner`'s exclusive responsibility).
- Duplicate detection of any kind (FR-7/FR-8/FR-9, the future `DuplicateHeaderCheck`/`DuplicateRsidCheck`/`DuplicateChrPosCheck`'s exclusive responsibility).
- Schema validation of any kind — no fixed or expected column count is asserted anywhere in this module (NFR-5).
- Data interpretation — no genomic, biological, RSID, chromosome, or genotype-notation meaning is assigned to any field.
- Casting — field values remain `str` at all times.
- Trimming — leading/trailing whitespace in a field is preserved exactly.
- Normalization — no case-folding, unicode normalization, or other content transformation is applied to any field.

---

## 3. DataRow Contract

### Fields

| Field | Type | Notes |
|---|---|---|
| `line_index` | `int` | Zero-based, positional index over the sequence of lines `RowParser` received. Not a reconstruction of the line's position in the original source file. |
| `fields` | `tuple[str, ...]` | Ordered, unmodified field-value strings produced by the delimiter split. |

### Invariant

- **`line_index >= 0`.**

### Violation behaviour

- Constructing a `DataRow` with a negative `line_index` **raises `ValueError`**. This represents an invalid value-object construction argument, not an ingestion-pipeline failure; no `PhenoPredIngestionError` subclass or other domain-specific exception is used.

### Explicitly NOT validated by `DataRow`

`DataRow` does not check, assert, or infer any of the following — each remains the exclusive responsibility of a downstream, not-yet-built component:

| Not validated | Where it belongs instead |
|---|---|
| Field count | `MalformedRowCheck` (FR-5), relative to the file's own modal column count — never a property `DataRow` itself asserts. |
| Expected schema / column count | No component may assert a fixed schema anywhere in domain code (NFR-5); `DataRow` in particular knows nothing of what count is "expected." |
| Field contents (format, character set, etc.) | Out of scope for ingestion entirely; any content-shape classification (OUT-6) is computed elsewhere. |
| Missing values | `MissingValueScanner` (FR-6) — an observation, not a validation, and never `DataRow`'s concern. |
| Formatting | FR-4 explicitly forbids trimming/casting; `DataRow` stores exactly what was split. |
| Data quality (duplicates, ragged rows, malformed structure) | Downstream `QualityCheck` implementations, represented as `Finding` data, never as exceptions or embedded validation logic. |

`line_index >= 0` is the sole, explicitly-required invariant and the only validation logic this entity contains.

---

## 4. Public API Contract

### `RowParser`

```
RowParser.__init__(self) -> None
```
- **Parameters:** none. `RowParser` has no constructor configuration — FR-4 names no configurable convention for this module (unlike `RawFileLoader`'s `sample_size`, `DelimiterDetector`'s `sample_size`, `RawLineSplitter`'s `comment_prefix`, or `HeaderResolver`'s `header_keyword`).

```
RowParser.parse(self, lines: Sequence[str], delimiter: Delimiter) -> tuple[DataRow, ...]
```
- **Parameters:**
  - `lines` — a plain, already-in-memory sequence of effective data lines. No file I/O is performed on it.
  - `delimiter` — an already-detected `Delimiter` value object, supplied externally (never constructed or inferred by `RowParser`). Consumed via its `.character` field only.
- **Returns:** `tuple[DataRow, ...]`, one entry per line in `lines`, in the same order as `lines`.
- **`line_index` semantics:** zero-based, positional indexing assigned over the exact sequence of lines `RowParser` received — not a reconstruction of the line's position in the original source file.
- **Raises:** none, under normal, contract-respecting pipeline execution (see Section 6).

No other public methods exist. No write, mutation, validation, or interpretation methods are defined.

### Data model: `DataRow`

See Section 3.

---

## 5. Dependency Boundary

### Allowed, and used

- `phenopred.domain.entities.DataRow` — the value object `RowParser` produces.
- `phenopred.domain.value_objects.Delimiter` — consumed as an input, for its `.character` field only.
- Python standard library only (`collections.abc.Sequence`, `__future__.annotations`).

### Forbidden, and confirmed absent (via structural AST-based guard tests)

- Any file-loading module (`RawFileLoader`, `RawFileContent`).
- Any detector module (`EncodingDetector`, `DelimiterDetector` as a class, `RawLineSplitter`, `CommentBlock`).
- Any header module (`HeaderResolver`, `HeaderInfo`).
- Any quality-check module (`quality_checks/*` — none exist yet, and none were introduced ahead of need).
- The domain error hierarchy: no import of `phenopred.domain.errors` or any `PhenoPredIngestionError` subclass.
- Any configuration-loading mechanism (`ConfigProvider`, `ConfigLoader`, environment/global state).
- Any future profiling module (`genomic_profiling/*` — none exist yet, and none were introduced ahead of need).

**Confirmed:** no dependency on `phenopred.domain.errors`. No custom exception class was introduced anywhere in this module. `RowParser` holds no mutable state beyond its stateless, parameter-free construction, and is safe for concurrent/repeated use.

---

## 6. Failure Behaviour Contract

**`RowParser` performs no defensive validation of its inputs.**

It assumes, as a documented dependency assumption rather than an internally-enforced guarantee:
- The supplied `Delimiter` originates from the approved `DelimiterDetector` pipeline, whose fixed candidate set (`"\t"`, `","`, `";"`, `"|"`) guarantees a non-empty, usable `character` value under normal, contract-respecting execution.

**`RowParser` does NOT guarantee behaviour for:**
- A manually constructed, invalid `Delimiter` object (e.g., one with an empty `character` value). Such a case is explicitly outside `RowParser`'s responsibility; the specification governing this module intentionally leaves this case undefined rather than assigning it a guaranteed outcome.

**No delimiter validation was introduced** — no check on `delimiter.character`'s length, emptiness, or shape exists anywhere in `RowParser`. No new exception type was introduced to cover this or any other condition.

---

## 7. Architectural Decisions Locked

1. **`DataRow` belongs in `domain/entities.py`.**
   Locked because Architecture v1 §4 explicitly assigns it there by name (`domain/entities.py # GenotypeFile, DataRow, ProfilingReport, ...`), which controls over the placement precedent set by `CommentBlock`/`HeaderInfo` in `value_objects.py` — a precedent built on inference from a non-exhaustive listing, not a direct citation. A direct architectural assignment for a specifically-named entity is not overridden by precedent built on a different, more general basis.

2. **`DataRow` contains only the approved invariant (`line_index >= 0`).**
   Locked as the sole, explicitly-cited validation rule (Architecture v1 §5) for this entity. No other invariant, of any kind, was introduced.

3. **`RowParser` is not a `Detector[T]` implementation.**
   Locked because Architecture v1 §10's interface table does not list `RowParser` among `Detector[T]` implementers, and `RowParser`'s output — a collection of `DataRow`s — is not "a single detected value-object," the shape `Detector[T]` is designed around. This mirrors `RawLineSplitter`'s identical, already-locked exclusion from the same table.

4. **`RowParser` performs mechanical parsing only.**
   Locked: no casting, coercion, trimming, normalization, schema assumption, or data-quality judgment of any kind occurs inside `RowParser`, in strict adherence to FR-4's text and Architecture v1 §7.2's separation of "what the data is" from "what the data means."

5. **No future entities are introduced.**
   Locked: `GenotypeFile` and `ProfilingReport` — also named in Architecture v1 §4's `entities.py` listing — are not designed, stubbed, or anticipated by this module. `DataRow` is introduced as the first and only member of `entities.py` at this stage.

6. **No quality logic is introduced.**
   Locked: no `QualityCheck` implementation, `Finding` logic, or any data-quality judgment (malformed rows, missing values, duplicates) is designed, stubbed, or anticipated by this module or its tests.

---

## 8. Verification Evidence

### Implementation files

| File | Status |
|---|---|
| `phenopred/domain/entities.py` | Created — contains only `DataRow` |
| `phenopred/domain/ingestion/row_parser.py` | Created — contains only `RowParser` |

### Test files

| File | Status |
|---|---|
| `tests/unit/domain/test_entities.py` | Created |
| `tests/unit/domain/ingestion/test_row_parser.py` | Created |

### Verification result

- All `RowParser`/`DataRow` tests passed.
- All previously frozen module tests passed, confirming no regression.
- No frozen module was modified — verified unchanged against the provided frozen module contents.

### Final test summary

| Suite | Result |
|---|---|
| `test_encoding_detector.py` (frozen) | 11 passed |
| `test_delimiter_detector.py` (frozen) | 20 passed |
| `test_header_resolver.py` (frozen) | 26 passed |
| `test_raw_line_splitter.py` (frozen) | 21 passed |
| `test_entities.py` (new) | 13 passed |
| `test_row_parser.py` (new) | 31 passed |
| **Total** | **122 passed** |
| **Failures** | **0** |
| **Skipped** | **0** |

**Environment limitation:** consistent with every prior module's approval record, the execution sandbox had no network access and could not `pip install` real `pytest`; a minimal stdlib-only shim implementing exactly the pytest API surface these suites use (`pytest.raises`, and the plain-`assert`-based test style already used in `test_delimiter_detector.py`/`test_raw_line_splitter.py`/`test_header_resolver.py`) was used to run the unmodified test files against the unmodified implementation. A full re-run under genuine `pytest` in CI remains an open, standing item, exactly as noted in every prior module's record.

---

## 9. Future Developer Constraints

Future modules may consume `RowParser`/`DataRow` output but must **not**:

- Move `DataRow` out of `domain/entities.py`.
- Add validation into `DataRow` beyond the single, frozen `line_index >= 0` invariant.
- Add interpretation of any kind into `RowParser` (casting, trimming, normalization, schema assumption, or genomic/biological meaning).
- Add quality-check logic into `RowParser` (malformed-row detection, missing-value detection, duplicate detection, or any `Finding`-producing behavior).
- Modify `RowParser` to take on any upstream responsibility (file loading, comment/data separation, delimiter detection, header detection or exclusion).

**Any change to this contract requires a new architectural review.** This record, once approved, is a frozen reference; it is not to be silently reinterpreted, extended, or partially overridden by a future module's convenience.

---

## 10. Final Approval Status

**RowParser and DataRow are approved and frozen for downstream development.**
