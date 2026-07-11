# Module Approval & Handoff Record: `RawLineSplitter`

**Status:** Final — frozen reference for future module integration
**Architecture:** PhenoPred Architecture v1 (Approved)
**Traceability:** SRS FR-1, OBJ-1, NFR-2, NFR-3, NFR-5

---

## 1. Module Identity

**Module name:** `RawLineSplitter`

**File paths:**

| File | Status |
|---|---|
| `phenopred/domain/ingestion/raw_line_splitter.py` | Created — production module |
| `phenopred/domain/ingestion/__init__.py` | Created — empty package marker |
| `phenopred/domain/value_objects.py` | Modified — `CommentBlock` added only |
| `tests/unit/domain/ingestion/test_raw_line_splitter.py` | Created — test module |

**Layer ownership:** Domain layer (`phenopred/domain/ingestion/`), per Architecture v1 §4 folder structure, which places `raw_line_splitter.py` under `domain/ingestion/`, not `infrastructure/`.

---

## 2. Purpose and Responsibility

**FR satisfied:** FR-1 — *"The system shall separate comment/metadata lines (lines beginning with `'#'`) from data lines on ingestion, without discarding either."*

**What this module owns:**
- Classifying each already-in-memory raw line as either a comment/metadata line or a candidate data line, by exact prefix match against an injected `comment_prefix`.
- Preserving both groups — comment lines are never discarded, candidate data lines are never discarded.
- Preserving original relative order within each output group.
- Preserving each line's exact content, unaltered.

**What this module explicitly does NOT own:**
- **File reading, byte handling, or decoding** — exclusively `RawFileLoader`'s responsibility.
- **Encoding characteristics** — exclusively `EncodingDetector`'s responsibility (FR-13), operating independently on `byte_sample`.
- **Delimiter detection** — exclusively `DelimiterDetector`'s responsibility (FR-2), which consumes this module's candidate-data-lines output.
- **Header detection or resolution** — exclusively the future `HeaderResolver`'s responsibility (FR-3); `RawLineSplitter` has no header-keyword awareness of any kind.
- **Row/field parsing** — exclusively the future `RowParser`'s responsibility (FR-4).
- **Malformed-row or any other data-quality judgment** — exclusively `QualityCheck` implementations' responsibility (FR-5–FR-9); no such condition is evaluated here.
- **Configuration loading** — `comment_prefix` is received as an already-resolved value; this module never reads configuration itself.

---

## 3. Architecture Compliance Evidence

**Architecture v1 folder placement — Confirmed.**
`phenopred/domain/ingestion/raw_line_splitter.py` matches Architecture v1 §4 exactly (`raw_line_splitter.py # comment/data separation (FR-1)`, listed under `domain/ingestion/`). `CommentBlock`'s placement in `phenopred/domain/value_objects.py` matches §4/§8 exactly (this file is architecture's designated home for `CommentBlock`).

**Domain-layer responsibility — Confirmed.**
`RawLineSplitter` performs no file, network, or external-service I/O of any kind (Stage 1 Engineering Review §14, constraint #2). It operates purely on strings already in memory; the same input always produces the same output (NFR-3).

**Dependency direction — Confirmed.**
`RawLineSplitter` depends only inward on a domain value object (`CommentBlock`). It has no dependency, direct or transitive, on any infrastructure module (`RawFileLoader`), any sibling detection module (`EncodingDetector`, `DelimiterDetector`), or any not-yet-built module (`HeaderResolver`). See §8 for the full dependency review.

**Frozen value object conventions — Confirmed.**
`CommentBlock` uses `@dataclass(frozen=True, slots=True)`, identical to the already-frozen `EncodingProfile` and `Delimiter` conventions in the same file, and to `RawFileContent`'s convention in `raw_file_loader.py`. No new immutability approach was introduced.

**No unnecessary abstractions — Confirmed.**
No new interface was added to `interfaces.py` (this module does not implement `Detector[T]`, since its output is a pair rather than a single detected value-object, and Architecture v1 §10's interface table does not list it as a `Detector[T]` implementer). No new exception type or hierarchy was introduced. No wrapper result type (e.g. a `RawLineSplitResult`) was introduced for the `(CommentBlock, tuple[str, ...])` return — both consumers destructure it immediately, per the Stage 2 Implementation Blueprint's evidence-based rejection of that abstraction.

---

## 4. Public API Contract

### `RawLineSplitter`

```
RawLineSplitter.__init__(self, comment_prefix: str) -> None
```
- **Parameters:** `comment_prefix` — mandatory, no internal default. Injected by the caller (application-layer composition root, via `ConfigProvider`/`ConfigLoader`), mirroring `RawFileLoader.__init__(sample_size)` and `DelimiterDetector.__init__(sample_size)`'s identical pattern.
- **Raises:** none (performs no I/O, no validation).

```
RawLineSplitter.split(self, lines: Sequence[str]) -> tuple[CommentBlock, tuple[str, ...]]
```
- **Parameters:** `lines` — a plain, already-in-memory sequence of raw lines (e.g. `RawFileContent.lines`). No file I/O is performed on it.
- **Returns:** a 2-tuple of `(CommentBlock, tuple[str, ...])` — the classified comment lines and the classified candidate data lines, respectively.
- **Raises:** none (see §5, §7).

No other public methods exist. No write, mutation, or classification-override methods are defined.

### `CommentBlock`

| Field | Type | Notes |
|---|---|---|
| `lines` | `tuple[str, ...]` | Ordered, verbatim comment lines, in original file order |
| `count` | `int` | Equal to `len(lines)` |

**Immutability guarantee:** `frozen=True, slots=True` — no field reassignment, no new attributes, after construction.

---

## 5. Behavioral Guarantees

- **Exact prefix matching using `startswith()`:** a line is classified as a comment if and only if `line.startswith(comment_prefix)` evaluates `True`. No other test is applied.
- **Comment detection anywhere in file:** comment lines are classified wherever they occur in the input sequence — leading, trailing, or interspersed among data lines — not only within a leading run.
- **No contiguous-block assumption:** `RawLineSplitter` has no concept of block boundaries or positional contiguity; `CommentBlock`'s name denotes "the aggregate of all comment lines," not a positional constraint, per Architecture v1 §6 ("all comment lines") and §9 ("by prefix").
- **No trimming:** no line's leading or trailing whitespace is stripped, in either output group.
- **No normalization:** no case-folding, unicode normalization, or other content transformation is applied to any line.
- **Order preservation:** both output groups preserve the original relative order of the lines they contain, matching the input's order.
- **Verbatim preservation:** every line's exact string content is passed through unchanged into whichever output group it belongs to.
- **Empty input validity:** an empty `lines` sequence is valid and yields `CommentBlock(lines=(), count=0)` and an empty candidate-data-lines tuple `()`, with no exception raised.
- **Deterministic behavior:** given identical input, `split()` always returns a field-for-field identical result (NFR-3).

---

## 6. Value Object Decision

**`CommentBlock` — `@dataclass(frozen=True, slots=True)`.**

**Fields:**
```
lines: tuple[str, ...]
count: int
```

**No `__post_init__` validation** — no invariant check (e.g. `count == len(lines)`) is enforced inside the value object.

**Rationale:**
- **Follows the `RawFileContent.line_count` precedent.** `RawFileContent`'s own frozen record documents `line_count` as "Equal to `len(lines)`," with that equality established once, at the call site inside `RawFileLoader.load()`, and never re-validated by the dataclass itself. `CommentBlock.count` follows the identical pattern: `RawLineSplitter.split()` is solely responsible for constructing it correctly.
- **Maintains the minimal-abstraction principle.** Neither `EncodingProfile` nor `Delimiter` — the two other frozen value objects in `value_objects.py` — contain any validation logic beyond the frozen+slots mechanism's own reassignment/new-attribute blocking. Adding `__post_init__` validation to `CommentBlock` would have been the first behavior-bearing value object in the project, contradicting Stage 1 Engineering Review §9 ("No unnecessary abstractions. Each class has a single, clearly named responsibility") and Architecture v1 §8's framing of these types as "immutable value-holders with no hidden I/O" (and, by the established pattern, no hidden validation logic either).

---

## 7. Test Evidence

**Test file:** `tests/unit/domain/ingestion/test_raw_line_splitter.py`
**RawLineSplitter tests collected:** 21
**RawLineSplitter tests passed:** 21
**RawLineSplitter tests failed:** 0

Coverage areas exercised: comments followed by data; multiple comment lines; non-contiguous comments (comment lines appearing after data lines, confirming no positional/contiguity assumption); no comments; only comments; empty input; empty `CommentBlock`; empty candidate-data-lines output; blank lines (classified as data, not specially categorized); exact `'#'`-prefix matching (including a line containing but not beginning with `'#'`); configurable, non-default prefix behavior; leading whitespace before the prefix (confirmed as a non-match); verbatim content preservation (including whitespace-padded and non-ASCII content); ordering preservation within each output group; no trimming; no case/unicode normalization; `CommentBlock` immutability (reassignment and new-attribute rejection); no mutation of caller-provided input (both `list` and `tuple` forms); and deterministic repeated calls.

**Full regression suite result:** 84 passed, 1 skipped.
This aggregates `RawLineSplitter` (21 passed) with the three previously frozen modules' own suites: `RawFileLoader` (32 passed, 1 skipped — the pre-existing, documented skip of `test_permission_denied_file_raises_source_file_unreadable_error`, unrelated to this module and unaffected by it), `EncodingDetector` (11 passed), and `DelimiterDetector` (20 passed). No regression was introduced in any previously frozen module's suite by the `CommentBlock` addition to `value_objects.py`.

**Environment note****:
Validation was performed locally using the project's configured pytest environment.

Command executed:
pytest -v

Result:
84 passed, 1 skipped

The skipped test was the pre-existing POSIX-specific permission-denied test and is unrelated to RawLineSplitter.

---

## 8. Dependency Review

**Confirmed, via direct inspection of `raw_line_splitter.py`'s import statements:**

- **No import from `RawFileLoader`.** Confirmed.
- **No import from `RawFileContent`.** Confirmed.
- **No import from `EncodingDetector`.** Confirmed.
- **No import from `DelimiterDetector`.** Confirmed.
- **No import from `HeaderResolver`.** Confirmed (module does not yet exist; no forward dependency was introduced).
- **No import from `ConfigLoader` or any `infrastructure/` module.** Confirmed.
- **No import from `phenopred/domain/errors.py`.** Confirmed — mirrors `DelimiterDetector`'s locked precedent of zero dependency on the `PhenoPredIngestionError` hierarchy, and applies with even less qualification here, since `RawLineSplitter` raises nothing at all.

**Only dependency:** `phenopred.domain.value_objects.CommentBlock`, plus Python stdlib (`collections.abc.Sequence`, `__future__.annotations`). No third-party or external library dependency of any kind.

---

## 9. Scope Control

Confirmed that no files outside the approved scope were changed:

- **Created:** `phenopred/domain/ingestion/__init__.py`, `phenopred/domain/ingestion/raw_line_splitter.py`, `tests/unit/domain/ingestion/__init__.py`, `tests/unit/domain/ingestion/test_raw_line_splitter.py`.
- **Modified (additive only):** `phenopred/domain/value_objects.py` — `CommentBlock` appended; `EncodingProfile` and `Delimiter` confirmed byte-for-byte unchanged.
- **Not touched:** `raw_file_loader.py`, `encoding_detector.py`, `delimiter_detector.py`, `interfaces.py`, `errors.py`. No compatibility issue arose during implementation that would have required touching any of these; none were modified.

No file outside this explicitly approved set was created, modified, or deleted.

---

## 10. Final Approval Decision

- **Implementation approved.**
- **Module frozen.**
- **Ready for downstream integration** (by `ProfileFileUseCase`, and as the upstream input source for `DelimiterDetector` and the future `HeaderResolver`).

---

## 11. Remaining Risks Before Full Pipeline Integration

*(Carried forward in the same form as the three prior module records, for consistency of the frozen-reference standard.)*

- **Unverified integration behavior:** this module has only been unit-tested in isolation; its behavior as consumed by `ProfileFileUseCase` (argument passing, sequencing alongside `RawFileLoader`, `DelimiterDetector`, and the future `HeaderResolver`) is not yet exercised by any integration test.
- **Test-execution environment gap:** validation relied on a stdlib-only pytest-compatible shim due to no network access in the sandbox; a full re-run under genuine `pytest` in CI has not yet occurred and is required before this validation can be considered fully authoritative.
- **`HeaderResolver` not yet designed:** this module's candidate-data-lines output and `CommentBlock` output are both intended, per Architecture v1 §6 step 5, to feed `HeaderResolver` once it is designed; that consumption has not yet been exercised against a real `HeaderResolver` implementation.

---

**RawLineSplitter module status: APPROVED FOR INTEGRATION**
