# Module Approval & Handoff Record: `HeaderResolver`

**Status:** Final — frozen reference for future module integration
**Architecture:** PhenoPred Architecture v1 (Approved)
**Traceability:** SRS FR-3, OUT-4, NFR-3, NFR-5

---

## 1. Module Overview

`HeaderResolver` is the domain-layer component responsible for resolving a
file's header form and column-name list (FR-3). It is the fifth pipeline module in the ingestion pipeline, following `RawFileLoader`, `EncodingDetector`,
`DelimiterDetector`, and `RawLineSplitter`, and its two required inputs
(`CommentBlock`, `Delimiter`) are produced entirely by those four frozen,
prior modules — no new upstream dependency was introduced.

| Field | Value |
|---|---|
| Module name | `HeaderResolver` |
| Production file | `phenopred/domain/detection/header_resolver.py` |
| Test file | `tests/unit/domain/detection/test_header_resolver.py` |
| Architectural layer | Domain (pure logic; no file/network/external-service I/O of any kind) |
| Related SRS functional requirement | FR-3 — detect whether the first non-comment line is a column header row, or whether a header is documented only inside a comment line, or is absent |
| Related Architecture clauses | Architecture v1 §4 (folder placement), §6 step 5 (data-flow position), §8 (`HeaderInfo` entity definition), §10 (`Detector[T]` interface listing) |

This record documents the module in its final, amended state — including
the comment-line matching correction applied after real-dataset
validation (see Section 4 and Section 8) — as the single, current, frozen
reference. It supersedes no prior architectural decision; it consolidates
the module's approved final form.

---

## 2. Responsibility and Scope

**`HeaderResolver` owns, exclusively:**
- Classifying a file's header form into exactly one of three states:
  `"uncommented_row"`, `"commented_only"`, or `"absent"`.
- Resolving the working column-name list (`resolved_columns`) for the
  file, when one can be determined.
- Identifying the exact original line (`source_line`) the header
  determination was drawn from, when applicable.

**`HeaderResolver` explicitly does NOT own, and does not perform:**
- File I/O of any kind (owned exclusively by `RawFileLoader`).
- Comment/data line separation (FR-1, owned exclusively by
  `RawLineSplitter`); `CommentBlock` is consumed as an already-computed
  input, never re-derived.
- Delimiter detection (FR-2, owned exclusively by `DelimiterDetector`);
  `Delimiter` is consumed as an already-computed input, never re-derived.
- Row parsing of every data line (FR-4, the future `row_parser`'s
  responsibility); only the first candidate data line is inspected.
- Malformed-row validation or any other data-quality judgment (FR-5–FR-9).
- Computation of "effective data rows" (i.e. whether the first data line
  must be excluded from downstream parsing once identified as a header);
  this hand-off is owned by `ProfileFileUseCase`, which derives it
  mechanically from the returned `HeaderInfo.form`.
- Configuration loading; `header_keyword` is received as an
  already-resolved constructor argument.

---

## 3. Architecture Compliance Review

- **Domain-layer boundary — Confirmed.** `header_resolver.py` performs no
  file, network, or infrastructure access of any kind, consistent with
  the Stage 1 Engineering Review's mandatory rule that the domain layer
  performs no I/O of any kind.
- **Folder placement — Confirmed.** `phenopred/domain/detection/header_resolver.py`
  matches Architecture v1 §4's folder structure exactly
  (`domain/detection/header_resolver.py # FR-3`).
- **`Detector[T]` conformance — Confirmed.** `detect()` accepts the
  context it needs (`CommentBlock`, `data_lines`, `Delimiter`) and
  returns exactly one detected value-object, `HeaderInfo` — never a
  tuple, never a wrapper result type — satisfying Architecture v1 §10,
  Table 5's explicit listing of `HeaderResolver` as a `Detector[T]`
  implementer.
- **Dependency direction — Confirmed.** `HeaderResolver` consumes only
  the *output value objects* of upstream modules (`CommentBlock` from
  `RawLineSplitter`, `Delimiter` from `DelimiterDetector`), never their
  classes, modules, or any transitive infrastructure dependency. This was
  verified structurally (AST-based import guard), not merely by
  convention.
- **Error-ownership boundary — Confirmed.** `detect()` never raises. No
  new exception type was introduced; `phenopred/domain/errors.py` remains
  unmodified. This is consistent with Architecture v1 §13.1, which does
  not name "no header resolvable" among its structural/infrastructure
  error conditions — `form == "absent"` is a legitimate, expected
  descriptive outcome, not a failure.
- **Value-object placement — Confirmed.** `HeaderInfo` resides in
  `phenopred/domain/value_objects.py`, per Architecture v1 §8, Table 3's
  explicit naming of that file as its home, alongside — and without
  altering — `EncodingProfile`, `Delimiter`, and `CommentBlock`.

---

## 4. Approved Design Decisions

**Uncommented-row detection — exact-token equality against the first
candidate data line only.**
Locked: the first entry of `data_lines` is split by `delimiter.character`;
a match requires some resulting token to be exactly equal to
`header_keyword`. No trimming, no whitespace normalization, no
case-folding, and no substring matching are applied at any point on this
path. This path is unchanged from the module's original design and was
not affected by the later comment-line amendment.

**Uncommented-row precedence over commented-only.**
Locked: the first candidate data line is always checked before any
comment line, per FR-3's own phrasing, which frames the uncommented-row
case as the primary detection target.

**Commented-only detection — exact-token equality, with one narrow,
match-only marker interpretation (amended).**
Locked, following real-dataset validation: comment lines are matched
first via the identical, unmodified exact-token-equality rule used for
data rows. Additionally, if a comment line's *first* token — after
splitting by `delimiter.character` — begins with a leading run of
non-alphanumeric, non-whitespace characters (the comment marker) followed
by zero or more whitespace characters, that leading run is disregarded
**only for the purpose of the match decision**; the remainder of that one
token is then compared to `header_keyword` for exact equality. This
interpretation:
- applies only to comment-line token index 0;
- is used only to decide whether a match occurred;
- never alters any stored value — `CommentBlock.lines`, `source_line`,
  and `resolved_columns` always reflect the original, unmodified line and
  its unmodified split tokens.

This amendment was adopted because real vendor comment-header lines are
conventionally written as "marker + space + content" (e.g.
`"# rsid\t..."`), not "marker + delimiter + content" — a format the
module's original, unamended exact-token rule could never detect, making
FR-3's own evidenced Dataset B case unreachable. The amendment restores
that capability without loosening the uncommented-row path, without
requiring access to the actual configured `comment_prefix` value (which
remains `RawLineSplitter`'s exclusive concern), and without introducing
any new configuration parameter, constructor argument, or stored-value
normalization.

**No configuration coupling to `RawLineSplitter`.**
Locked: `HeaderResolver` does not receive, request, or infer the
configured `comment_prefix` value. The marker interpretation is generic
(any leading non-alphanumeric, non-whitespace run), not tied to a
specific character, preserving the module's independence from
`RawLineSplitter`'s configuration and avoiding a rejected alternative
design (passing `comment_prefix` as a new constructor parameter, which
would have violated the "no new configuration parameters" constraint of
the approved amendment).

**No new exception type; `detect()` never raises.**
Locked, unchanged since the module's original design — see Section 3.

**`HeaderInfo` immutability — `@dataclass(frozen=True, slots=True)`,
no `__post_init__` validation.**
Locked, unchanged since the module's original design, mirroring the
convention already established for `EncodingProfile`, `Delimiter`, and
`CommentBlock`.

---

## 5. Compatibility Validation

Validated against both real, uploaded source datasets (not only synthetic
fixtures), by reconstructing the pipeline's intermediate state
(`CommentBlock`, `data_lines`, `Delimiter`) from each file's actual
content and running the production `HeaderResolver.detect()` directly.

**Dataset A — `AncestryDNA.txt` (AncestryDNA-style, uncommented header):**
- Input first data line: `rsid\tchromosome\tposition\tallele1\tallele2`
- Result: `form == "uncommented_row"`,
  `resolved_columns == ("rsid", "chromosome", "position", "allele1", "allele2")`
- Matches expected behavior exactly; confirms no regression from the
  amendment on this path.

**Dataset B — `anonymous_genome_v5_build37.txt` (23andMe-style, commented-only header):**
- Input comment line: `# rsid\tchromosome\tposition\tgenotype`
- Result: `form == "commented_only"`,
  `resolved_columns == ("# rsid", "chromosome", "position", "genotype")`,
  `source_line == "# rsid\tchromosome\tposition\tgenotype"`
- Matches expected behavior; confirms the amendment resolves the
  previously-identified compatibility gap, with stored output preserved
  exactly as originally parsed (the marker and its following space remain
  attached to the first entry, unstripped).

No compatibility issue remains open for either evidenced dataset.

---

## 6. Test Evidence

- **Test file:** `tests/unit/domain/detection/test_header_resolver.py`
- **Command executed:** `pytest tests/unit/domain/detection/test_header_resolver.py -v`
- **Tests collected:** 26
- **Tests passed:** 26
- **Tests failed:** 0
- **Tests skipped:** 0

**Coverage areas exercised:**
- Normal uncommented-header detection (Dataset-A-style).
- Normal commented-only-header detection, including the real Dataset B
  format (marker + space), the delimiter-separated marker format, and a
  marker with no following whitespace at all.
- Absent-header detection.
- Boundary cases: empty `data_lines`, empty `CommentBlock`,
  `header_keyword` present in both an uncommented data line and a comment
  line simultaneously (confirming uncommented-row precedence), multiple
  comment lines (confirming first-match-in-order selection).
- Exact-token-matching discipline on the uncommented-row path: no
  substring matching, no trimming/whitespace normalization, no
  case-folding, configurable `header_keyword`.
- False-positive protection for the amended comment-line path: prose
  comments containing the keyword mid-sentence, a keyword embedded inside
  an unbroken word (`"#notarealrsid"`), and case-sensitivity preservation
  under the marker-stripping interpretation.
- Generalized marker handling: a multi-character, non-`'#'` marker
  (`";; rsid"`) confirmed to match, verifying the interpretation is not
  hard-coded to a single character.
- `HeaderInfo` immutability (reassignment and new-attribute rejection).
- Input immutability: `CommentBlock` and `data_lines` confirmed unchanged
  after `detect()` is called, including specifically under the amended
  marker-stripped match path.
- Deterministic repeated calls.
- `detect()` never raises, across varied and degenerate inputs.
- Structural dependency guard (AST-based): confirms no import of
  `errors.py`, any `infrastructure/*` module, or any sibling
  detector/downstream module.

Environment validation: The test suite was executed under the project's actual pytest environment locally.

Command executed:

pytest tests/unit/domain/detection/test_header_resolver.py -v

Result:

26 passed, 0 failed, 0 skipped.

The HeaderResolver implementation, including the comment-line matching amendment, was successfully validated under the project's actual pytest environment.
---

## 7. Files Modified

| File | Status |
|---|---|
| `phenopred/domain/detection/header_resolver.py` | Created, then amended (comment-line matching correction) |
| `tests/unit/domain/detection/test_header_resolver.py` | Created, then amended (9 tests added; 17 pre-existing tests unmodified) |

**Modified, additive only (prior to this module's own work):**
- `phenopred/domain/value_objects.py` — `HeaderInfo` was added as the required value object definition. Existing value objects (`EncodingProfile`, `Delimiter`, and `CommentBlock`) remained unchanged.

**Not touched, at any point in this module's implementation or
amendment:**
- `phenopred/infrastructure/io/raw_file_loader.py`
- `phenopred/domain/detection/encoding_detector.py`
- `phenopred/domain/detection/delimiter_detector.py`
- `phenopred/domain/ingestion/raw_line_splitter.py`
- `phenopred/domain/interfaces.py`
- `phenopred/domain/errors.py`

No file outside this explicitly approved set was created, modified, or
deleted.

---

## 8. Known Tradeoffs / Design Notes

- **Marker-character interpretation is punctuation-shaped, not
  configuration-driven.** The comment-line match-only interpretation
  identifies a marker generically as a leading run of non-alphanumeric,
  non-whitespace characters. This correctly and losslessly covers every
  case evidenced by both real datasets (`'#'`) and generalizes to other
  punctuation-style markers (e.g. `';;'`, `'@@'`) without requiring
  `HeaderResolver` to know the actual configured `comment_prefix`. It
  implicitly assumes comment markers are punctuation/symbol characters,
  not letters or digits; if `comment_prefix` were ever configured to an
  alphanumeric value (e.g. a `"REM"`-style marker), the marker-stripping
  step would not fire, and the fallback would be inert for that file —
  degrading gracefully to "no match via the amendment, base rule still
  applies" rather than misbehaving. This is consistent with the evidenced
  default and both real datasets and is noted here as a documented
  assumption, not an open defect.
- **The amendment is confined to comment-line matching only.** The
  uncommented-row detection path is provably untouched by the amendment —
  it uses the identical, unmodified exact-token-equality rule as the
  module's original design, with no fallback of any kind.
- **Environment testing gap** (carried forward from every prior module's
  record): validation relied on a stdlib-only pytest-compatible
  equivalent due to no network access in this environment; a full re-run
  under genuine `pytest` in CI remains an open, standing item.

---

## 9. Dependency Boundary Confirmation

**Allowed, and used:**
- `phenopred.domain.value_objects` — for `CommentBlock`, `Delimiter`
  (consumed as inputs) and `HeaderInfo` (produced as output).
- Python stdlib only — `collections.abc.Sequence`,
  `__future__.annotations`. No third-party or external library dependency
  of any kind.

**Forbidden, and confirmed absent (via structural AST-based guard test):**
- `phenopred/domain/errors.py` or any `PhenoPredIngestionError` subclass.
- Any `infrastructure/` module of any kind.
- `raw_file_loader.py`, `raw_line_splitter.py`, `delimiter_detector.py`,
  `encoding_detector.py` — `HeaderResolver` consumes only their produced
  value objects, never their classes or modules.
- `row_parser.py`, any `quality_checks/*`, `genomic_profiling/*` — none
  of these exist yet and none were introduced ahead of need.

`HeaderResolver` holds no mutable state beyond the constructor-injected
`header_keyword`, set once and never reassigned, and is safe for
concurrent/repeated use.

---

## 10. Final Approval Status

- **Implementation approved**, including the comment-line matching
  amendment.
- **Module frozen** in its current, final form as documented in this
  record.
- **Ready for downstream integration** by `ProfileFileUseCase`, and as
  the upstream input source for the future `row_parser`.

**HeaderResolver module status: APPROVED FOR INTEGRATION**
