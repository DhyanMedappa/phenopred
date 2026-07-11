# Module Approval & Handoff Record: `raw_file_loader`

**Status:** Final — frozen reference for future module integration
**Architecture:** PhenoPred Architecture v1 (Approved)
**Traceability:** SRS FR-14, NFR-2, NFR-3

---

## 1. Final Approved Files

### Production files

| File | Responsibility |
|---|---|
| `infrastructure/io/raw_file_loader.py` | Sole component permitted to open a source file. Reads a file's raw bytes exactly once, validates readability/non-emptiness, and produces an immutable `RawFileContent` value object. Performs no structural, encoding, delimiter, header, or row-level interpretation. |
| `phenopred/domain/errors.py` | Defines the domain-owned exception hierarchy (`PhenoPredIngestionError` and subclasses) representing file-ingestion failures, consumed by `RawFileLoader` and intended to be caught by `ProfileFileUseCase`. |

### Test files

| File | Scope of coverage |
|---|---|
| `tests/unit/infrastructure/io/test_raw_file_loader.py` | Successful loading and field correctness; file-integrity/read-only behavior (FR-14, NFR-2); the full approved exception hierarchy; determinism (NFR-3); immutability of `RawFileContent`; byte-sample slicing at under/equal/over file size; line-ending handling (LF, CRLF, mixed, no trailing newline); lossless non-ASCII decoding. 33 tests total. |

---

## 2. Final Locked Architecture Decisions

**`RawFileContent` placement — Colocated inside `raw_file_loader.py`.**
Chosen because the DTO has exactly one producer and one consumer (`RawFileLoader` → `ProfileFileUseCase`), and the Architecture's own precedent for separate model files (`domain/entities.py` / `value_objects.py`) applies to types shared across *many* components, not a single-producer DTO. Colocating avoids introducing a file not named in the Architecture's §4 folder structure and avoids premature separation. *Rejected alternative:* a dedicated `infrastructure/io/models.py` — rejected as unnecessary indirection for a single 5-field DTO at this scale; remains a safe, non-breaking future refactor if a second infrastructure DTO of similar shape ever appears.

**Exception hierarchy placement — `phenopred/domain/errors.py`.**
Chosen to mirror the Architecture's existing pattern of domain defining contracts that infrastructure implements against (as `domain/interfaces.py` does for ports). This keeps failure vocabulary owned by the domain layer, consistent with the Architecture's inward-dependency rule (§3). *Rejected alternative:* a top-level `phenopred/exceptions.py` — rejected as an ungoverned, layer-agnostic location with no precedent in the approved Architecture.

**Decoding strategy — Latin-1 (ISO-8859-1) decode, used solely to produce line boundaries and text content.**
Chosen because Latin-1 is a bijective, total mapping over all byte values 0x00–0xFF: decoding can never raise regardless of the file's true encoding, and is fully lossless/reversible (re-encoding to Latin-1 reproduces the original bytes exactly). This keeps `RawFileLoader` free of any "cannot decode" failure mode, leaving encoding *characteristics* reporting (BOM presence, decodability under ASCII/UTF-8/UTF-8-sig/Latin-1) entirely with `EncodingDetector`, operating independently on `byte_sample`. *Rejected alternatives:* `errors='replace'` (rejected — destroys information via substitution); `errors='surrogateescape'` (rejected — introduces surrogate code points that could raise on later encode/print operations in downstream domain code).

**`sample_size` ownership and configuration flow — Mandatory constructor parameter on `RawFileLoader`; no internal default.**
Chosen because the Architecture explicitly assigns default-value ownership to `ConfigLoader` (§11), which resolves and injects the value before construction. `RawFileLoader` fails fast (missing-argument error) if constructed without one, rather than silently supplying its own fallback, consistent with NFR-5 (no hard-coded structural assumptions in domain/infrastructure code) and AD-10 (config injected, never read from globals).

**Immutability approach — `@dataclass(frozen=True, slots=True)` for `RawFileContent`; `lines` typed as `tuple[str, ...]`, not `list[str]`.**
Chosen so no field can be reassigned after construction and no arbitrary attribute can be added, closing the one gap a mutable `list` field would otherwise leave in an "immutable" object. Verified in Stage 5: reassigning an existing field correctly raises `dataclasses.FrozenInstanceError` (a subclass of `AttributeError`); assigning an undeclared attribute raises a plain `TypeError` due to a known CPython interaction between `frozen=True` and `slots=True` — both outcomes correctly block mutation, only the raised exception *type* differs by case (see §4).

**Thread-safety assumptions — `RawFileLoader` holds no mutable shared state; safe for concurrent use.**
Chosen because the loader's only attribute (`_sample_size`) is set once at construction and never reassigned, and every `load()` call operates on purely local variables. `RawFileContent` instances are fully immutable once constructed and therefore safe to share across threads without locking. No module-level mutable state exists.

**Object lifecycle decisions — `RawFileLoader` is a stateless, reusable service; `RawFileContent` is an ephemeral, single-run value.**
One `RawFileLoader` instance is constructed once (via the composition root) and reused across every file `load()`-ed in a pipeline run, with each call opening and closing its own file handle within that call — no resources held between calls. Each `RawFileContent` is produced by one `load()` call, consumed by `ProfileFileUseCase`, and is not cached or reused across files.

---

## 3. Final Public Contract

### Classes

**`RawFileContent`** — Immutable, lossless raw content read from a single source file.

**`RawFileLoader`** — Reads a source file's raw content exactly once, read-only; the only component in the pipeline permitted to open a source file.

### Public methods

```
RawFileLoader.__init__(self, sample_size: int) -> None
```
- **Parameters:** `sample_size` — number of leading bytes exposed as `byte_sample`; mandatory, no default.
- **Raises:** none (performs no I/O).

```
RawFileLoader.load(self, path: Path) -> RawFileContent
```
- **Parameters:** `path` — path to the source file to read.
- **Returns:** `RawFileContent`.
- **Raises:**
  - `SourceFileNotFoundError` — path does not exist.
  - `SourceFileUnreadableError` — path exists but is not a regular, readable file (e.g. a directory, or a permissions failure).
  - `EmptySourceFileError` — file is readable but contains zero bytes.
  - `SourceFileReadError` — unexpected I/O failure during the read.

No other public methods exist. No write, save, or mutation methods are defined.

### Data model: `RawFileContent`

| Field | Type | Notes |
|---|---|---|
| `source_path` | `Path` | Path that was read |
| `size_bytes` | `int` | Bytes actually read |
| `lines` | `tuple[str, ...]` | Ordered, lossless (Latin-1-decoded) lines, terminators stripped |
| `line_count` | `int` | Equal to `len(lines)` |
| `byte_sample` | `bytes` | Bounded prefix from the same single read, for `EncodingDetector` |

**Immutability guarantee:** `frozen=True, slots=True` — no field reassignment, no new attributes, after construction.

### Exception hierarchy (`phenopred/domain/errors.py`)

```
PhenoPredIngestionError (base)
 ├── SourceFileNotFoundError
 ├── SourceFileUnreadableError
 ├── EmptySourceFileError
 └── SourceFileReadError
```

This is the stable surface other modules (`ProfileFileUseCase`, `EncodingDetector`, and any future consumer) are permitted to depend on.

---

## 4. Final Validation Status

- **Test framework used:** pytest-API-compatible execution. **Environment limitation:** the execution sandbox had no network access and could not `pip install` real `pytest`; a minimal stdlib-only shim implementing exactly the subset of the pytest API this suite uses (`fixture`, `raises`, `mark.skipif`, `MonkeyPatch`, `tmp_path`) was used to run the unmodified test file against the unmodified implementation. **This requires future confirmation under real pytest in CI** before this status can be considered fully closed.
- **Tests executed:** 33
- **Tests passed:** 32
- **Tests failed (final state):** 0
- **Tests skipped:** 1 (`test_permission_denied_file_raises_source_file_unreadable_error` — skipped because execution ran as root, under which POSIX permission bits are bypassed; the suite's own `skipif` guard triggered as designed)

**The one corrected test issue:** `test_raw_file_content_has_no_dict_due_to_slots` originally asserted that assigning an undeclared attribute would raise `AttributeError`. On this Python version, a `frozen=True, slots=True` dataclass raises `dataclasses.FrozenInstanceError` (an `AttributeError` subclass) when reassigning an *existing* field, but a plain `TypeError` when assigning an *undeclared* attribute, due to a known CPython interaction between frozen `__setattr__` generation and slots-based class recreation. This was classified as a **test issue, not a production defect**: the production code correctly blocks the assignment in both cases — no `__dict__` is created, immutability holds — only the test's assumed exception *type* for the undeclared-attribute case was incorrect. The test was corrected to accept `(AttributeError, TypeError)`, with rationale documented in its docstring. No production code was changed.

**Validated behavior:** functional correctness, file-integrity/read-only guarantees (FR-14, NFR-2), determinism (NFR-3), immutability, byte-sample slicing, and line-ending handling are all confirmed under the executed suite.

**Behavior requiring future real-CI confirmation:** full suite re-execution under genuine `pytest` (not the compatibility shim); the permission-denied path (`SourceFileUnreadableError` via `chmod`) under a non-root runner.

---

## 5. Integration Notes

**Expected inputs:** a single `pathlib.Path` per `load()` call, referring to a file the calling process has permission to read. No delimiter, encoding, or schema information is accepted or required.

**Expected outputs:** one immutable `RawFileContent` per successful `load()` call, containing lossless raw lines, a bounded byte sample, and basic size metadata — with no structural interpretation applied.

**Exception handling expectations:** consumers (chiefly `ProfileFileUseCase`) must catch `PhenoPredIngestionError` and its four subclasses to handle per-file ingestion failure without aborting a multi-file batch run (per-file independence, FR-15/CON-3). `RawFileLoader` does not catch-and-continue internally — it fails fast and propagates.

**Assumptions consumers must not violate:**
- Must not treat `RawFileLoader` as a source of encoding, delimiter, or header information — those remain the responsibility of `EncodingDetector`, `DelimiterDetector`, and `HeaderResolver`, operating on the `RawFileContent` this module produces.
- Must not mutate a `RawFileContent` instance — it is frozen and slotted; any transformation must produce a new value.
- Must not assume `lines` retains original line terminators — terminators are stripped and normalized during the lossless Latin-1 line-splitting step.
- Must not open the source file independently — `RawFileLoader` is architecturally the only component permitted to do so; any component needing byte-level access (e.g. `EncodingDetector`) must consume `byte_sample` from the `RawFileContent` this module already produced, not re-read the file.

**Architectural boundaries to respect:** `RawFileLoader` sits in the Infrastructure layer and implements no domain interface beyond being the file-access adapter `ProfileFileUseCase` depends on through orchestration, per the Architecture's inward-dependency rule (§3). No domain component may import `raw_file_loader.py` directly.

---

## 6. Remaining Risks Before Full Pipeline Integration

- **Unverified integration behavior:** this module has only been unit-tested in isolation; its behavior as consumed by `ProfileFileUseCase` (argument passing, exception catching, sequencing with `raw_line_splitter`/`encoding_detector`) is not yet exercised by any integration test.
- **Test-execution environment gap:** validation in Stage 5 relied on a stdlib-only pytest-compatible shim due to no network access in the sandbox; a full re-run under genuine `pytest` in CI has not yet occurred and is required before this validation can be considered fully authoritative.
- **Permission-denied path unverified in this environment:** skipped because Stage 5 execution ran as root; this exception path (`SourceFileUnreadableError` via filesystem permissions) has not been empirically exercised and remains reliant on the non-root CI run for confirmation.
- **Scale assumption inherited from NFR-1:** full in-memory loading has only been exercised against small synthetic fixtures; behavior at the SRS-evidenced ~15–18 MB / ~630k–680k line scale (or beyond) has not been empirically measured in this environment, though it follows directly from AD-4's approved design.

---

**raw_file_loader module status: APPROVED FOR INTEGRATION**
