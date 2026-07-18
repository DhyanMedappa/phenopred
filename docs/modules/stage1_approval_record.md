# PhenoPred — Stage 1 Module Approval Record

**Status:** APPROVED — FROZEN ENGINEERING BASELINE
**Scope:** Stage 1 Engineering Foundation (Architecture v1)
**Reference:** PhenoPred Software Architecture Version 1 (Approved)

---

## PART 1 — Stage 1 Scope Completed

Stage 1 covers the full per-file ingestion, structural detection, column
identity resolution, row parsing, and data-quality checking path (FR-1
through FR-9, FR-13, FR-14 of the SRS), executable end-to-end from a
command-line invocation.

**What Stage 1 includes:**
- Reading a single genotype source file, read-only, exactly once.
- Reporting the file's encoding characteristics (BOM presence,
  decodability under ASCII/UTF-8/UTF-8-sig/Latin-1).
- Separating comment/metadata lines from candidate data lines.
- Empirically detecting the file's field delimiter.
- Resolving the file's header form and column names (uncommented row,
  commented-only, or absent).
- Resolving which field-position indices correspond to the RSID,
  chromosome, position, and designated genotype/allele column roles.
- Splitting each effective data line into an ordered `DataRow`.
- Running all five FR-5–FR-9 data-quality checks (malformed rows,
  duplicate header rows, missing/literal-value frequency, duplicate
  RSIDs, duplicate chromosome-position pairs) and collecting one
  `Finding` per check.
- Orchestrating the above, per file, through a single application-layer
  use case.
- Assembling the full object graph from one composition-root call.
- Invoking the pipeline from a command line and displaying a minimal,
  non-report execution summary.

**What is complete:** every item above is implemented, wired together,
and verified to execute successfully against a real file, end to end,
with no manual assembly required.

**User-to-result workflow now available:**

```
python -m phenopred.cli.main <path-to-genotype-file>
```

produces, for that file: which quality checks ran, how many `Finding`s
were produced in total, and a process exit status reflecting whether
ingestion succeeded (0), failed with a recognized structural/
infrastructure condition (1), or failed unexpectedly (2). This is the
complete, currently-available user-facing capability of the system; it
is not a report and does not persist any artifact.

---

## PART 2 — Module Inventory

### Infrastructure

**RawFileLoader**
(`phenopred/infrastructure/io/raw_file_loader.py`)
- **Layer:** Infrastructure
- **Responsibility:** The only component permitted to open a source
  file. Reads it read-only, exactly once; confirms it is readable and
  non-empty; produces an immutable `RawFileContent` (raw lines, a
  bounded byte sample, basic size metadata).
- **Key dependencies:** `phenopred.domain.errors` (raises
  `SourceFileNotFoundError`, `SourceFileUnreadableError`,
  `EmptySourceFileError`, `SourceFileReadError`).
- **Does NOT own:** any structural interpretation (encoding, delimiter,
  header, or row content); never re-reads or mutates the file.

### Domain / Processing

**EncodingDetector** (`phenopred/domain/detection/encoding_detector.py`)
- **Layer:** Domain (detection)
- **Responsibility:** Classifies BOM presence and decodability of a byte
  sample under ASCII/UTF-8/UTF-8-sig/Latin-1; produces an
  `EncodingProfile`. Purely descriptive; never raises.
- **Key dependencies:** `phenopred.domain.value_objects.EncodingProfile`
  only.
- **Does NOT own:** file I/O, line splitting, delimiter/header/row
  logic, or selection of a "correct" encoding.

**RawLineSplitter** (`phenopred/domain/ingestion/raw_line_splitter.py`)
- **Layer:** Domain (ingestion)
- **Responsibility:** Separates comment lines from candidate data lines
  by exact, position-zero prefix match (FR-1); produces a
  `CommentBlock` and a tuple of candidate data lines.
- **Key dependencies:** `phenopred.domain.value_objects.CommentBlock`
  only; injected `comment_prefix`.
- **Does NOT own:** header detection, delimiter detection, row parsing,
  or malformed-row validation.

**DelimiterDetector** (`phenopred/domain/detection/delimiter_detector.py`)
- **Layer:** Domain (detection)
- **Responsibility:** Empirically infers the field delimiter from a
  sample of candidate data lines via character-frequency analysis
  (FR-2); produces a `Delimiter`.
- **Key dependencies:** `phenopred.domain.value_objects.Delimiter`;
  injected `sample_size`; raises its own local
  `DelimiterNotDetectedError` (not part of the `PhenoPredIngestionError`
  hierarchy).
- **Does NOT own:** comment/data separation, header resolution, row
  parsing, or translation of its own exception into an ingestion error
  (owned exclusively by `ProfileFileUseCase`).

**HeaderResolver** (`phenopred/domain/detection/header_resolver.py`)
- **Layer:** Domain (detection)
- **Responsibility:** Determines header form (uncommented row,
  commented-only, absent) and resolved column names (FR-3); produces a
  `HeaderInfo`. Never raises.
- **Key dependencies:** `phenopred.domain.value_objects.{CommentBlock,
  Delimiter, HeaderInfo}`; injected `header_keyword`.
- **Does NOT own:** comment/data separation, delimiter detection, row
  parsing, quality validation, or "effective data row" exclusion
  (mechanically derived by `ProfileFileUseCase`).

**ColumnIdentityResolver**
(`phenopred/domain/detection/column_identity_resolver.py`)
- **Layer:** Domain (detection)
- **Responsibility:** Resolves which field-position indices correspond
  to the RSID, chromosome, position, and designated genotype/allele
  column roles, from `HeaderInfo.resolved_columns` only; produces a
  `ColumnLayout`.
- **Key dependencies:** `phenopred.domain.value_objects.{HeaderInfo,
  ColumnLayout}`; injected `rsid_keyword`, `chromosome_keyword`,
  `position_keyword`, `designated_column_keywords`; raises its own
  local `ColumnIdentityNotResolvedError` (not part of the
  `PhenoPredIngestionError` hierarchy).
- **Does NOT own:** row parsing, quality-check logic, biological
  interpretation of any column's content, or translation of its own
  exception into an ingestion error (owned exclusively by
  `ProfileFileUseCase`).

**RowParser** (`phenopred/domain/ingestion/row_parser.py`)
- **Layer:** Domain (ingestion)
- **Responsibility:** Mechanically splits each effective data line into
  an ordered `DataRow` using the detected delimiter (FR-4). No casting,
  coercion, or trimming.
- **Key dependencies:** `phenopred.domain.entities.DataRow`,
  `phenopred.domain.value_objects.Delimiter`.
- **Does NOT own:** comment/data separation, delimiter detection, header
  resolution/exclusion, or any judgment about row "correctness."

### Quality

**MalformedRowCheck** (FR-5), **DuplicateHeaderCheck** (FR-7),
**MissingValueScanner** (FR-6), **DuplicateRsidCheck** (FR-8),
**DuplicateChrPosCheck** (FR-9)
(`phenopred/domain/quality_checks/*.py`)
- **Layer:** Domain (quality checks)
- **Responsibility:** Each computes exactly one `Finding` from the
  parsed `DataRow` collection (plus, where required, `HeaderInfo` or a
  `ColumnLayout`-derived index/`ChrPosColumnIndices`). Stateless;
  reports, never resolves. Never raises — every data-quality condition
  is represented as `Finding` data (Section 13.2).
- **Key dependencies:** `phenopred.domain.entities.DataRow`,
  `phenopred.domain.value_objects.{Finding, HeaderInfo,
  ChrPosColumnIndices}`.
- **Does NOT own:** column-identity resolution, row parsing, header
  resolution, biological interpretation, or any other check's logic.

### Application

**ProfileFileUseCase** (`phenopred/application/profile_file_use_case.py`)
- **Layer:** Application
- **Responsibility:** Sequences exactly one file through the Stage 1
  pipeline (load → encoding → split → delimiter → header → column
  identity → row parse → quality checks) and returns a plain dict of
  results. Translates `DelimiterNotDetectedError` and
  `ColumnIdentityNotResolvedError` into `PhenoPredIngestionError` with
  file-path context, per the exception-ownership contract each detector/
  resolver documents.
- **Key dependencies:** every component listed above, received
  exclusively via constructor injection; `phenopred.domain.errors`.
- **Does NOT own:** any parsing, detection, or quality-check logic
  itself; construction of any of its own collaborators; genomic
  profiling or report building (both accepted as constructor parameters
  but never invoked).

**Composition Root** (`phenopred/application/composition_root.py`)
- **Layer:** Application
- **Responsibility:** The single place concrete implementations are
  bound to `ProfileFileUseCase`'s constructor. Supplies a temporary,
  module-local configuration mechanism (plain default constants) for
  `comment_prefix`, `header_keyword`, both `sample_size` values, and the
  four `ColumnIdentityResolver` keywords. Assembles the `quality_checks`
  name-keyed mapping. Supplies the smallest compatible placeholder
  values for `genomic_profilers` (`()`) and `report_builder` (`None`).
- **Key dependencies:** every concrete Stage 1 class; imports no
  interface/Protocol directly (it binds concrete types).
- **Does NOT own:** pipeline execution (never calls `.execute()`),
  parsing, validation, or any domain rule.

### CLI

**cli/main.py** (`phenopred/cli/main.py`)
- **Layer:** CLI (user interaction)
- **Responsibility:** Parses one file-path argument, obtains a
  `ProfileFileUseCase` from the composition root, calls `.execute()`
  once, catches `PhenoPredIngestionError` and unexpected exceptions,
  and prints a minimal, non-report execution summary (path processed,
  Finding count, quality-check names).
- **Key dependencies:** `phenopred.application.composition_root`,
  `phenopred.domain.errors.PhenoPredIngestionError` only.
- **Does NOT own:** construction of any domain, detection, or
  infrastructure component; pipeline sequencing; parsing; validation;
  report assembly or serialization.

---

## PART 3 — Architecture Validation

- **Dependency direction preserved:** confirmed across every module —
  domain components import only other domain value objects/entities and
  (where applicable) their own local exception; infrastructure imports
  only `phenopred.domain.errors`; application imports domain and
  infrastructure concrete types; CLI imports only the application layer.
  No inward dependency (domain → application, domain → infrastructure,
  application → CLI) exists anywhere in the inventory above.
- **Domain layer contains no application logic:** every domain module
  performs a single, narrow, stateless transformation (data in, one
  value object or `Finding` out) with no sequencing of other domain
  components and no knowledge of the overall pipeline order.
- **Application layer contains no domain logic:** `ProfileFileUseCase`
  contains only sequencing, header-line exclusion (a mechanical
  derivation, not an interpretation), and exception translation;
  `composition_root.py` contains only constructor calls and a dict
  literal.
- **Composition root owns dependency construction:** verified — it is
  the only module in the repository that imports and instantiates every
  concrete Stage 1 class; no other module (including `ProfileFileUseCase`
  and `cli/main.py`) constructs a domain, detection, or infrastructure
  component.
- **CLI only invokes the application layer:** verified by direct source
  inspection — `cli/main.py` imports `composition_root` and
  `domain.errors` only; it holds no reference to any detector, resolver,
  quality check, or infrastructure class.
- **No module bypasses the intended dependency flow:** the verified
  runtime path (Part 4) exercises exactly the chain CLI →
  Composition Root → ProfileFileUseCase → domain/infrastructure
  components, with no shortcut or direct construction observed at any
  layer boundary.

---

## PART 4 — Verified Execution Flow

```
Input file
 ↓
CLI                         (phenopred/cli/main.py)
 ↓
Composition Root            (build_profile_file_use_case())
 ↓
ProfileFileUseCase          (.execute(file_path))
 ↓
Loading                     (RawFileLoader)
 ↓
Detection                   (EncodingDetector, RawLineSplitter, DelimiterDetector)
 ↓
Header Resolution           (HeaderResolver)
 ↓
Column Identity Resolution  (ColumnIdentityResolver → ColumnLayout)
 ↓
Row Parsing                 (RowParser)
 ↓
Quality Checks              (MalformedRowCheck, DuplicateHeaderCheck,
                              MissingValueScanner, DuplicateRsidCheck,
                              DuplicateChrPosCheck)
 ↓
Findings returned
```

**Verification evidence** (from the implementation and verification
tasks preceding this record):

- **Imports succeeded:** every module in the inventory above compiles
  and imports cleanly under its architecture-specified package path
  (`phenopred.infrastructure.io.*`, `phenopred.domain.detection.*`,
  `phenopred.domain.ingestion.*`, `phenopred.domain.quality_checks.*`,
  `phenopred.application.*`, `phenopred.cli.*`).
- **Composition root construction succeeded:** `build_profile_file_use_case()`
  returns a `ProfileFileUseCase` instance with every collaborator
  correctly typed and injected, and the `quality_checks` mapping
  containing all five required entries
  (`malformed_row_check`, `duplicate_header_check`,
  `missing_value_scanner`, `duplicate_rsid_check`,
  `duplicate_chr_pos_check`).
- **CLI execution succeeded:** run as a real subprocess
  (`python -m phenopred.cli.main <file>`) against a synthetic fixture
  file, producing exit code `0` and the summary:
  ```
  Processed: fixtures/sample_uncommented_header.tsv
  Findings produced: 5
  Quality checks completed: duplicate_chr_pos_check, duplicate_header_check,
  duplicate_rsid_check, malformed_row_check, missing_value_scanner
  ```
- **Sample file completed the Stage 1 pipeline:** the same fixture,
  driven directly through `ProfileFileUseCase.execute()`, produced a
  correctly resolved `Delimiter`, `HeaderInfo`, and `ColumnLayout`
  (verified field-for-field), with the header line correctly excluded
  from the four returned `DataRow`s.
- **Quality checks executed:** all five `Finding`s were produced and
  numerically verified against the fixture's known structure (e.g.
  `duplicate_rsid_check.count == 2`, `duplicate_chr_pos_check.count == 2`).
- **Error paths verified:** a nonexistent file and a file with no
  detectable delimiter each correctly propagated as a
  `PhenoPredIngestionError` (or a recognized subclass), surfaced by the
  CLI as exit code `1` with a clear `stderr` message; column-identity
  failure was verified identically at the `ProfileFileUseCase` level.

---

## PART 5 — Deferred Components and Known Limitations

The following are **intentionally not implemented** in Stage 1, per
Architecture v1's own Section 16 ("Future Extension Points... none
should be inferred as implicitly authorized") and this task series'
explicit scope boundaries:

- **ConfigProvider** — named by Architecture v1 Section 10 as an
  interface but explicitly deferred (`interfaces.py`'s own docstring).
  Not implemented, and not even defined as a Protocol.
- **Reporting** — no `ProfilingReport` assembly of any kind exists.
- **ReportBuilder** — not implemented; `ProfileFileUseCase` accepts a
  `report_builder` constructor argument but never calls it.
- **ReportSerializer** — not implemented; no persisted output artifact
  is produced anywhere in Stage 1.
- **Genomic Profiling** (FR-10–FR-12: chromosome label inventory,
  genotype/allele layout classification, indel/haploid classification)
  — not implemented; `ProfileFileUseCase` accepts a `genomic_profilers`
  constructor argument but never calls it.
- **Trait Prediction** — no concept, module, or interface anticipating
  this exists anywhere in the codebase, consistent with Architecture v1
  Section 16's explicit exclusion.
- **Streamlit interface** (or any UI) — not implemented; the only
  user-facing surface is the CLI described above.

**Additional documented limitations:**

- **Temporary configuration mechanism:** `composition_root.py` sources
  `comment_prefix`, `header_keyword`, both `sample_size` values, and the
  four `ColumnIdentityResolver` keywords from plain module-local default
  constants, not from a real `ConfigProvider`. This was an explicitly
  approved interim decision, not a permanent architectural position. The
  `designated_column_keywords` default (`"allele1"`, `"allele2"`,
  `"genotype"`) is a composition-root-level placeholder only, covering
  both evidenced dataset layouts; it is not embedded in any domain
  component.
- **Absence of a production reporting layer:** the CLI's execution
  summary is a minimal, non-persisted, non-formatted diagnostic display
  only — it is not, and must not be mistaken for, a `ProfilingReport`
  or any reporting-layer output.
- **Absence of later genomic analysis stages:** no genomic-notation
  interpretation (chromosome label inventory, allele/genotype layout,
  indel/haploid classification) occurs anywhere in the current
  execution path; `Finding`s returned by Stage 1 cover only FR-5–FR-9
  data-quality observations.

---

## PART 6 — Approval Decision

**Stage 1 is approved as the frozen engineering baseline for future development.**

**Approved capabilities:**
- End-to-end, per-file ingestion, structural detection, column identity
  resolution, row parsing, and FR-5–FR-9 data-quality checking,
  executable from a single CLI command.
- A fully working, tested dependency-injection object graph, assembled
  by one composition-root call.
- A verified, typed error-handling path from any detector/resolver-local
  exception through to a CLI exit code.

**Frozen architectural decisions:**
- Layer boundaries and dependency direction as validated in Part 3
  (Infrastructure → Domain ← Application ← CLI, composition root as the
  sole binder of concrete types).
- The exception-ownership pattern: detector/resolver-local exceptions,
  translated exclusively by `ProfileFileUseCase` into
  `PhenoPredIngestionError`.
- The `Detector[T]` pattern for all detection-layer components,
  including `ColumnIdentityResolver`.
- The `ColumnLayout` contract (`rsid_column_index`,
  `chromosome_column_index`, `position_column_index`,
  `designated_column_indices`) as the fixed interface between column
  identity resolution and the three column-identity-dependent quality
  checks.
- The `quality_checks` name-keyed mapping contract consumed by
  `ProfileFileUseCase`.

**Next development should build on this baseline without modifying any
completed Stage 1 component listed in Part 2, unless a new architecture
decision is recorded.** This applies in particular to any future work on
genomic profiling, reporting, `ConfigProvider`, or a user interface: such
work must integrate against the interfaces and contracts frozen here,
not alter them.
