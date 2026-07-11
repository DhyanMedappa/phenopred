# Module Approval & Handoff Record: `EncodingDetector`

**Status:** Final — frozen reference for future module integration
**Architecture:** PhenoPred Architecture v1 (Approved)
**Traceability:** SRS FR-13, OUT-3, NFR-3

---

## 1. Final Approved Files

### Production files

| File | Responsibility |
|---|---|
| `phenopred/domain/detection/encoding_detector.py` | Domain-layer component that classifies BOM presence and decodability of an already-in-memory byte sample under ASCII, UTF-8, UTF-8-sig, and Latin-1. Performs no file I/O, no encoding selection, and no line/delimiter/header interpretation. |
| `phenopred/domain/value_objects.py` | Defines `EncodingProfile`, the immutable value object `EncodingDetector` returns. (Contains only `EncodingProfile` at this stage; other value objects named by Architecture v1 §4 for this file — `Delimiter`, `ColumnLayout`, etc. — belong to modules not yet designed and are intentionally absent.) |
| `phenopred/domain/interfaces.py` | Defines the `Detector[T]` protocol that `EncodingDetector` structurally satisfies. (Contains only `Detector[T]` at this stage; `QualityCheck`, `GenomicProfiler`, `ReportSerializer`, `ConfigProvider` belong to modules not yet designed and are intentionally absent.) |
| `phenopred/domain/detection/__init__.py` | Package marker for the `domain/detection/` package, per Architecture v1 §4 folder structure. |

### Test files

| File | Validation scope |
|---|---|
| `tests/unit/domain/detection/test_encoding_detector.py` | ASCII input decodability and no-BOM reporting; non-ASCII UTF-8 detection; UTF-8 BOM-prefixed input; UTF-8 input without BOM (proving BOM presence and UTF-8-sig decodability are reported independently); invalid-UTF-8-but-valid-Latin-1 input; full 256-byte-value range (Latin-1 totality, no raise); empty-bytes input; determinism (identical input → equivalent `EncodingProfile`); `EncodingProfile` immutability (reassignment and new-attribute rejection); confirmation that `detect()` never raises across varied inputs. 11 tests total. |

---

## 2. Final Locked Architecture Decisions

**Module location and domain-layer placement — `phenopred/domain/detection/encoding_detector.py`.**
Locked per Architecture v1 §4 (folder structure), §5 (module responsibility table), and §10 (interfaces table), all of which place `encoding_detector.py` under `domain/detection/`, not `infrastructure/`. This is consistent with the Stage 1 Engineering Review's mandatory rule that the domain layer performs no file/network I/O of any kind — `EncodingDetector` performs none, since it operates only on an already-produced `bytes` sample.

**`EncodingProfile` placement — `domain/value_objects.py`.**
Locked because Architecture v1 §4/§5 explicitly names `EncodingProfile` as residing in this file (`value_objects.py # Delimiter, EncodingProfile, ColumnLayout, ...`). Unlike `RawFileContent` (colocated with `RawFileLoader` because no separate model file was named for it), `EncodingProfile` has an explicitly named home in the approved Architecture, so colocating it in `encoding_detector.py` would have contradicted the Architecture rather than followed a documented precedent.

**Detector interface compatibility — `Detector[T]`, single type parameter.**
Locked per Architecture v1 §10 ("`Detector[T] | Given raw input (bytes or lines), produce a detected value-object`") and Stage 1 Engineering Review §4. `EncodingDetector` structurally satisfies `Detector[EncodingProfile]` via a single `detect(data: bytes) -> EncodingProfile` method. A two-parameter `Detector[TIn, TOut]` form was considered during design review and explicitly rejected as an implementation preference that was not what the frozen Architecture specifies.

**`EncodingDetector` input contract — plain `bytes`, never `RawFileContent` or a file path.**
Locked so that `EncodingDetector` has no dependency, direct or transitive, on `infrastructure/io/raw_file_loader.py`. Callers are responsible for extracting `RawFileContent.byte_sample` before calling `detect()`.

**Supported encoding checks — exactly ASCII, UTF-8, UTF-8-sig, Latin-1.**
Locked per FR-13/OUT-3, which name these four and no others. Each is checked independently (an ordered/short-circuiting pipeline was considered and rejected, since FR-13/OUT-3 ask for a full decodability matrix, not a single "winning" encoding, mirroring the notebook's own per-encoding reporting).

**BOM detection strategy — direct byte-prefix inspection (`b"\xef\xbb\xbf"`), independent of any decode attempt.**
Locked because inferring BOM presence from `utf-8-sig` decode success was rejected: `utf-8-sig` decodes successfully whether or not a BOM is actually present, which would make the reported BOM flag unreliable. Only the UTF-8 BOM form is checked, matching the SRS's evidenced scope (no UTF-16/32 BOM handling was evidenced or is checked).

**Exception behavior — `detect()` never raises.**
Locked because Latin-1 (ISO-8859-1) is a bijective, total mapping over all byte values 0x00–0xFF (the same rationale `RawFileLoader` relies on for its own lossless decode), so "not decodable under any candidate encoding" is unreachable once Latin-1 is among the checked candidates. Any `UnicodeDecodeError` from the ASCII/UTF-8/UTF-8-sig attempts is caught internally and reported as `False`, never propagated. This intentionally leaves the Architecture v1 §13.1 exception-condition wording ("file cannot be decoded under any candidate encoding") effectively unreachable in practice for this module — noted here as a known documentation tension, not resolved or altered by this record.

**Fallback behavior — none.**
Locked: no "assume Latin-1 if nothing else decodes" logic or any other fallback exists, because no downstream consumer needs a "final" encoding decision from this component. `RawFileLoader`'s own Latin-1 line-splitting strategy is independent and unaffected by anything `EncodingDetector` reports.

**Confidence/encoding-selection decisions — none; purely descriptive output.**
Locked: `EncodingProfile` carries only boolean decodability flags plus `bom_present`. No confidence score, no "detected encoding" field, and no recommended/selected encoding are computed or exposed, since FR-13/OUT-3 ask for reported characteristics, not a judgment.

**Immutability approach — `@dataclass(frozen=True, slots=True)` for `EncodingProfile`.**
Locked, mirroring the `RawFileContent` precedent: no field can be reassigned after construction and no undeclared attribute can be added. As with `RawFileContent`, reassigning an existing field raises `dataclasses.FrozenInstanceError`; assigning an undeclared attribute may raise a plain `TypeError` on this Python version due to the same known CPython interaction between `frozen=True` and `slots=True` documented in the `raw_file_loader` handoff record — both outcomes correctly block mutation.

---

## 3. Final Public Contract

### Classes

**`EncodingProfile`** — Immutable, descriptive report of encoding characteristics observed in a single byte sample.

**`EncodingDetector`** — Stateless domain-layer component that classifies BOM presence and decodability of a byte sample; the sole component responsible for this classification.

### Methods

```
EncodingDetector.detect(self, data: bytes) -> EncodingProfile
```
- **Parameters:** `data` — a byte sample already in memory (e.g. `RawFileContent.byte_sample`). No file I/O is performed on it.
- **Returns:** `EncodingProfile`.
- **Raises:** none (see Exceptions, below).

No constructor parameters. No other public methods. No write, mutation, or encoding-selection methods are defined.

### Data model: `EncodingProfile`

| Field | Type | Notes |
|---|---|---|
| `bom_present` | `bool` | Whether the sample begins with a UTF-8 BOM, via direct byte-prefix check |
| `ascii_decodable` | `bool` | Whether the sample decodes under strict ASCII |
| `utf8_decodable` | `bool` | Whether the sample decodes under UTF-8 |
| `utf8_sig_decodable` | `bool` | Whether the sample decodes under UTF-8-sig |
| `latin1_decodable` | `bool` | Whether the sample decodes under Latin-1; always `True` for any `bytes` input |

**Immutability guarantee:** `frozen=True, slots=True` — no field reassignment, no new attributes, after construction.

### Behavior guarantees

- **Deterministic:** given identical input bytes, `detect()` always returns a field-for-field identical `EncodingProfile` (NFR-3).
- **No filesystem access:** `EncodingDetector` performs no I/O of any kind; it operates only on the `bytes` object passed to it.
- **No source-file rereading:** `EncodingDetector` never opens, reads, or re-reads the original source file; it consumes only the byte sample already produced by `RawFileLoader`.
- **No mutation of input data:** the input `bytes` object is never modified; `bytes` is itself immutable, and no other mutable state is touched.

### Exceptions

- **May be raised:** none, under any `bytes` input, including empty bytes and the full 256-value byte range.
- **Intentionally never raised:** any `UnicodeDecodeError` arising from the ASCII/UTF-8/UTF-8-sig decode attempts is caught internally and converted to `False`; it never escapes `detect()`. No `PhenoPredIngestionError` or any subclass is raised by this module — ingestion-failure exceptions remain the exclusive concern of `RawFileLoader` and `phenopred/domain/errors.py`.

### Dependencies

**Allowed:**
- `phenopred/domain/value_objects.py` (for `EncodingProfile`)
- `phenopred/domain/interfaces.py` (for structural compatibility with `Detector[T]`)
- Python stdlib only (`bytes.decode`)

**Forbidden:**
- Any `infrastructure/` module, including `infrastructure/io/raw_file_loader.py`
- Any filesystem access (`pathlib.Path`, `open()`, or equivalent)
- Any import of `RawFileLoader` or `RawFileContent`
- Any external/third-party encoding- or charset-detection library

---

## 4. Test Validation Status

- **Test file executed:** `tests/unit/domain/detection/test_encoding_detector.py`
- **Tests collected:** 11
- **Tests passed:** 11
- **Tests failed:** 0
- **Tests skipped:** 0

**Environment limitation:** the execution sandbox had no network access and could not `pip install` real `pytest`; a minimal stdlib-only shim implementing exactly the one pytest API surface this suite uses (`pytest.raises`) was used to run the unmodified test file against the unmodified `EncodingDetector`/`EncodingProfile` implementation — the same environment constraint documented in the `raw_file_loader` module approval record. **Real pytest execution in CI is still recommended** before this validation can be considered fully authoritative.

---

## 5. Integration Notes

**How consumers should call `EncodingDetector`:** a consumer (chiefly the future `ProfileFileUseCase`) constructs `EncodingDetector()` with no arguments, then calls `detect(raw_file_content.byte_sample)`, where `raw_file_content` is a `RawFileContent` instance already produced by `RawFileLoader.load(path)`. `EncodingDetector` never receives, requests, or infers a file path.

**Expected inputs:** consumers must supply `RawFileContent.byte_sample` (or any other in-memory `bytes` value); `EncodingDetector` never opens, receives, or reasons about `Path` objects.

**Division of responsibility with `RawFileLoader`:**
- `RawFileLoader` remains the only component permitted to open and read the source file.
- `RawFileLoader` remains solely responsible for lossless Latin-1 raw-text extraction used to produce `RawFileContent.lines`; this is fixed and independent of anything `EncodingDetector` reports.
- `EncodingDetector` only reports encoding *characteristics* (BOM presence, per-encoding decodability) for informational/reporting purposes (OUT-3); it does not feed back into or alter how `RawFileLoader` decodes anything.

**Responsibilities `EncodingDetector` must never take on:**
- Opening files or performing any file I/O.
- Selecting, recommending, or asserting a "final" or "correct" encoding for the source file.
- Modifying `RawFileContent` or any of its fields.
- Delimiter detection (remains `delimiter_detector`'s responsibility, FR-2).
- Header detection (remains `header_resolver`'s responsibility, FR-3).
- Schema, structural, or row-level interpretation of any kind.

---

## 6. Remaining Risks Before Full Pipeline Integration

- **Unverified integration behavior:** this module has only been unit-tested in isolation; its behavior as consumed by `ProfileFileUseCase` (argument passing, sequencing alongside `raw_line_splitter`/`delimiter_detector`/`header_resolver`) is not yet exercised by any integration test.
- **Test-execution environment gap:** validation relied on a stdlib-only pytest-compatible shim due to no network access in the sandbox; a full re-run under genuine `pytest` in CI has not yet occurred and is required before this validation can be considered fully authoritative.
- **Architecture §13.1 wording tension:** Architecture v1 §13.1 lists "file cannot be decoded under any candidate encoding examined by the encoding detector" as an infrastructure-error condition, but given Latin-1's inclusion and totality, this condition can never actually occur under the locked design. This is noted as a documentation discrepancy for future architecture-doc maintenance, not something this record resolves or changes.
- **Scope-limited supporting files:** `domain/value_objects.py` and `domain/interfaces.py` currently contain only the members this module needs (`EncodingProfile`, `Detector[T]`); other members Architecture v1 names for these files belong to modules not yet designed and will need to be added when those modules are approved, without disturbing the members frozen here.

---

**EncodingDetector module status: APPROVED FOR INTEGRATION**
