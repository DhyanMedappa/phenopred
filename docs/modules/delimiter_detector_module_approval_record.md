# Module Approval & Handoff Record: `DelimiterDetector`

**Status:** Final — frozen reference for future module integration
**Architecture:** PhenoPred Architecture v1 (Approved)
**Traceability:** SRS FR-2, Architecture v1 §13.1

---

## 1. Module Identity

| Field | Value |
|---|---|
| Module name | `DelimiterDetector` |
| File | `phenopred/domain/detection/delimiter_detector.py` |
| Architectural layer | Domain (pure logic; no file/network/external-service I/O of any kind) |
| Responsibility | Infer, via character-frequency analysis over a sample of already-in-memory candidate data lines, the single field delimiter character used by a file's data rows; report the character found and the method used to find it |
| Related SRS functional requirement | FR-2 — "The system shall detect the field delimiter empirically rather than assume a fixed value... since delimiter detection in the notebook was performed via character-frequency analysis rather than hard-coded" |
| Related Architecture clause | Architecture v1 §13.1 — "No delimiter can be confidently detected" is named as one of four structural/infrastructure error conditions |

---

## 2. Public Contract

### Constructor

```
DelimiterDetector.__init__(self, sample_size: int) -> None
```
- **Parameters:** `sample_size` — number of leading lines (from the sequence passed to `detect()`) to examine. Mandatory; no internal default.
- **Raises:** none (performs no I/O; holds no other state).

### Method

```
DelimiterDetector.detect(self, lines: Sequence[str]) -> Delimiter
```
- **Parameters:** `lines` — a plain, already-in-memory sequence of candidate data lines (e.g. a slice of `RawFileContent.lines`, or the future data-line output of `raw_line_splitter`). No file I/O is performed on it.
- **Returns:** `Delimiter`.
- **Raises:** `DelimiterNotDetectedError` (module-local; see Section 4) if no candidate delimiter is confidently and consistently detected across the sampled non-empty lines.

### Input contract

- A `Sequence[str]` of lines already resident in memory.
- No dependency on `RawFileContent`, a file path, or any file-loading type. `DelimiterDetector` never receives, requests, or infers a file path — mirroring `EncodingDetector`'s locked input-contract precedent.
- Field content within each line is never altered, trimmed, stripped, or otherwise normalized before or during analysis.
- No assumption is made about whether comment lines have already been filtered from `lines`; separating comment from data lines is FR-1's responsibility (`raw_line_splitter`), not this module's.

### Output contract

- `Delimiter`, containing exactly `character: str` and `detection_method: str`.
- Deterministic: given identical input lines and identical `sample_size`, `detect()` always returns a field-for-field identical `Delimiter` (NFR-3).

### Exceptions

- **May be raised:** `DelimiterNotDetectedError` only, and only when no candidate delimiter satisfies the consistency check across the sampled lines (including the case of an empty or all-blank `lines` sequence).
- **Never raised:** `PhenoPredIngestionError` or any of its subclasses. See Section 4.

### Dependencies

See Section 5.

### Explicit non-responsibilities

`DelimiterDetector` never performs, and must never be assumed to perform:
- Comment/data line separation (FR-1 — `raw_line_splitter`'s responsibility).
- Header detection or column-name resolution (FR-3 — `header_resolver`'s responsibility).
- Row/field splitting of actual data content (FR-4 — `row_parser`'s responsibility; `row_parser` is this module's consumer, not the reverse).
- Encoding characteristic reporting (FR-13 — `EncodingDetector`'s exclusive responsibility).
- Any file I/O, path resolution, or filesystem access.
- Construction, raising, or handling of any `PhenoPredIngestionError`-family exception.
- Reading configuration directly (all tunable values are constructor-injected).

---

## 3. Architectural Decisions Frozen

**Candidate delimiters — exactly tab (`\t`), comma (`,`), semicolon (`;`), pipe (`|`).**
Locked per the approved Stage 2 resolution: FR-2 mandates the detection *method* (character-frequency analysis) but does not enumerate specific candidates the way FR-13 does for encodings; this fixed four-member set was adopted as the minimal, evidence-consistent candidate list (tab being the only value actually evidenced, per SRS §6.1), with the other three included to satisfy NFR-5's prohibition on assuming only the evidenced value generalizes to future files.

**Candidate ordering — tab > comma > semicolon > pipe, used only for deterministic tie-breaking.**
Locked: this ordering never overrides a clear, higher-scoring detection result. It is invoked only when two or more candidates are equally consistent and present the same non-zero per-line count, to satisfy NFR-3's determinism requirement without introducing dependence on incidental collection-iteration order.

**Detection algorithm — character-frequency analysis with per-line consistency checking; highest consistent occurrence count wins.**
Locked: for each candidate, in fixed preference order, the sampled non-empty lines are checked for an identical non-zero occurrence count of that candidate across every line. Among candidates satisfying this consistency check, the one with the highest per-line count is selected (stronger structural evidence of being the true delimiter). `csv.Sniffer` and any other external dialect-inference approach were explicitly rejected as not matching FR-2's described method and as introducing an opaque, non-traceable heuristic (NFR-6).

**Sample size — mandatory constructor injection, no internal default.**
Locked: `sample_size: int` is a required constructor argument, mirroring `RawFileLoader.__init__(self, sample_size: int)` exactly, per Architecture v1 §11's explicit naming of detector sample sizes as a per-run-configurable value supplied via `ConfigProvider`/composition root. `DelimiterDetector` never reads configuration directly.

**No quote handling.** Locked: quote characters are treated as ordinary literal characters; no quoted-field parsing or dialect inference of any kind, since no notebook evidence supports quoting in either evidenced file.

**No escaped-delimiter handling.** Locked: no escape-sequence interpretation; every occurrence of a candidate character is counted literally, consistent with FR-4's "without... otherwise altering field values" principle extended to the detection step.

**No whitespace normalization.** Locked: a literal space character is excluded from the candidate set; no stripping, trimming, or normalization of leading/trailing/repeated whitespace is performed on lines before or during counting.

**No fallback delimiter.** Locked: if no candidate satisfies the consistency check, `DelimiterDetector` raises rather than defaulting to any delimiter (including tab). This is directly required by Stage 1 Engineering Review §7/§16 ("delimiter is always detected, never configurable as a fixed override") and by Architecture v1 §13.1, which treats non-detection as a genuine, exception-worthy failure condition.

**`Delimiter` value object — `character: str`, `detection_method: str`, `@dataclass(frozen=True, slots=True)`.**
Locked: added to the existing `phenopred/domain/value_objects.py`, per Architecture v1 §4/§8's explicit naming of `Delimiter` as belonging in that file, alongside — and without altering — `EncodingProfile`. No confidence score, candidate ranking, or additional metadata field is present, mirroring `EncodingProfile`'s purely descriptive design.

---

## 4. Exception Ownership Boundary

- **`DelimiterDetector` does NOT raise `PhenoPredIngestionError` or any of its subclasses.**
- **`DelimiterDetector` raises only `DelimiterNotDetectedError`** — a module-local exception class defined inside `phenopred/domain/detection/delimiter_detector.py` itself.
- **`DelimiterNotDetectedError` is not a member of the `PhenoPredIngestionError` hierarchy** and has no import relationship with `phenopred/domain/errors.py`.
- **`ProfileFileUseCase` owns the translation** of a caught `DelimiterNotDetectedError` into the existing, unmodified `PhenoPredIngestionError` base class (attaching `path` and an appropriate `message`, via `raise ... from err` exception chaining), at the point it invokes delimiter detection as part of sequencing one file's pipeline.
- **`phenopred/domain/errors.py` remains unchanged** — no new subclass was added, no existing subclass was altered.

**Why this preserves the `EncodingDetector` precedent:** `EncodingDetector`'s own approval record states plainly that "no `PhenoPredIngestionError` or any subclass is raised by this module — ingestion-failure exceptions remain the exclusive concern of `RawFileLoader` and `phenopred/domain/errors.py`." `DelimiterDetector` extends this same zero-dependency posture: it neither imports nor constructs anything from that hierarchy, keeping every `domain/detection/` component uniformly decoupled from ingestion-error vocabulary, regardless of whether the detector in question can fail (as `DelimiterDetector` can) or cannot (as `EncodingDetector` cannot, given Latin-1's totality).

**Why this preserves Stage 1 Engineering Review exception rules:** §10.4 requires that "only specific, anticipated exception types are caught and translated" and prohibits broad `except Exception` handling. `DelimiterNotDetectedError` is a single, narrowly-scoped, purpose-built type raised at exactly one anticipated condition, making it safe for `ProfileFileUseCase` to catch specifically without risk of masking an unrelated defect — a risk a generic builtin exception would have carried.

**Why this preserves Architecture §13.1's typed exception hierarchy:** §13.1 requires that "No delimiter can be confidently detected" ultimately surface as part of "a small, typed exception hierarchy... rooted at a shared base `PhenoPredIngestionError`." This is satisfied at the point of translation: `ProfileFileUseCase` raises the existing, frozen `PhenoPredIngestionError` base class itself for this condition (as precedented by the "cannot decode under any candidate encoding" condition from the same §13.1 list, which also has no dedicated subclass). The typed-hierarchy guarantee is honored at the application-orchestration boundary, while the domain-layer detector itself remains free of any dependency on that hierarchy's vocabulary.

---

## 5. Dependencies and Forbidden Dependencies

**Allowed:**
- `phenopred/domain/value_objects.py` (for `Delimiter`)
- Python stdlib only (`collections.abc.Sequence`; no third-party or external library)

**Forbidden:**
- `phenopred/infrastructure/io/raw_file_loader.py` or any import of `RawFileLoader`/`RawFileContent`
- Any filesystem access (`pathlib.Path`, `open()`, or equivalent)
- Any `infrastructure/` module of any kind
- `phenopred/domain/errors.py` or any `PhenoPredIngestionError` subclass
- Any `ConfigProvider`/configuration-loading mechanism — `sample_size` is received only as an already-resolved constructor argument
- Any external/third-party CSV-dialect or delimiter-sniffing library (e.g. `csv.Sniffer`)

---

## 6. Testing Evidence

- **Test file:** `tests/unit/domain/detection/test_delimiter_detector.py`
- **Tests executed:** 20
- **Tests passed:** 20
- **Tests failed:** 0
- **Tests skipped:** 0

**Categories covered:**
- Candidate delimiter detection — one test per candidate (tab, comma, semicolon, pipe) confirming each is correctly identified from consistent, structurally distinct fixtures.
- Deterministic tie-break — confirms that when two candidates present equal consistent evidence, the fixed preference order (tab > comma > semicolon > pipe) resolves the tie, and that a candidate with objectively stronger (higher-count) consistent evidence wins over the preference order.
- Inconsistent-detection failure — confirms `DelimiterNotDetectedError` is raised when candidate counts vary across sampled lines, when no candidate is present at all, and when the input line sequence is empty.
- Sample-size behavior — confirms only the first `sample_size` lines are examined, and that content beyond the sample boundary does not influence the result.
- Immutability — confirms `Delimiter` rejects reassignment of an existing field (`dataclasses.FrozenInstanceError`) and rejects assignment of an undeclared attribute (`AttributeError`/`TypeError`), mirroring the `EncodingProfile`/`RawFileContent` precedent.
- No quote handling — confirms quote characters are treated as literal content with no special parsing.
- No escape handling — confirms a backslash-escaped delimiter is counted literally, with no escape-sequence interpretation.
- No whitespace normalization — confirms space is never treated as a detected delimiter, and that leading/trailing whitespace around fields does not affect detection of the true delimiter.
- No ingestion-error dependency — a structural (AST-based) guard confirming `delimiter_detector.py` contains no `import` of any module whose name includes `errors`, verifying the exception-ownership boundary in Section 4 at the source level, not merely by convention.
- Determinism — confirms repeated calls with identical input produce field-for-field identical `Delimiter` results.

**Environment note:** tests were executed as plain functions (no `pytest` dependency invoked), consistent with the environment-constraint precedent already documented in both the `raw_file_loader` and `encoding_detector` approval records; a full re-run under genuine `pytest` in CI remains recommended before this validation is considered fully authoritative, matching the same open item already logged for both prior modules.

---

## 7. Handoff Information for Future Modules

**What `DelimiterDetector` guarantees to `ProfileFileUseCase` (or any future caller):**
- Given the same input lines and `sample_size`, `detect()` always returns a field-for-field identical `Delimiter` (NFR-3).
- The input `lines` sequence and its contents are never altered, trimmed, or mutated.
- `detect()` raises only `DelimiterNotDetectedError`, and only when no candidate delimiter is confidently and consistently present in the sample — never a generic or unanticipated exception type.
- The returned `Delimiter.character` reflects one of exactly four possible values (`\t`, `,`, `;`, `|`); `Delimiter.detection_method` is always the fixed label `"character_frequency_analysis"`.

**What `DelimiterDetector` does NOT guarantee:**
- It does not guarantee the detected delimiter is "correct" for the file as a whole beyond what the sampled lines evidence — it is descriptive of the sample, not an assertion about the entire file's structure.
- It does not guarantee comment lines have been excluded from consideration — if raw, unfiltered lines (including comment lines) are passed to `detect()`, the detector will analyze exactly what it is given, with no awareness that some lines may be non-data comment lines. **Whether the caller must supply comment-filtered data lines, or may pass `RawFileContent.lines` directly, is an integration-time decision that remains open until `raw_line_splitter` (FR-1) is designed and approved** — this is an unresolved integration risk carried forward, not resolved by this module.
- It does not guarantee successful detection for every possible file — non-detection is a real, expected outcome for files with no consistent delimiter evidence in the sampled lines.

**What exception must be translated by `ProfileFileUseCase`:**
- `DelimiterNotDetectedError`, caught specifically (never via broad `except Exception`), and re-raised as the existing, unmodified `PhenoPredIngestionError` base class, with `path` and an appropriate `message` attached, using exception chaining (`raise ... from err`) to preserve the original cause.

**What context `DelimiterDetector` intentionally does not know:**
- The source file's path, name, or any filesystem identifier.
- Whether the lines it receives are comment-filtered or raw.
- The file's byte-level encoding characteristics (that remains `EncodingDetector`'s exclusive concern).
- The file's header form or column names (that remains `header_resolver`'s exclusive concern, not yet built).
- Any configuration source — it receives only the already-resolved `sample_size` value passed to its constructor.

---

## 8. Final Approval Status

**DelimiterDetector is approved and frozen for downstream integration.**
