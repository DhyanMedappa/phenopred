# PhenoPred Stage 1 Engineering Review

**Purpose:** Immutable engineering reference consolidating the principles, constraints, and decisions established during Stage 1 engineering review, derived from the approved SRS, Architecture v1, and the `raw_file_loader` Stage 1 design review. This document introduces no new decisions — it consolidates what was already established, for use when designing future modules (e.g. `EncodingDetector`).

**Source basis:** PhenoPred SRS v1.0, PhenoPred Architecture v1 (Approved), and the Stage 1 engineering design review conducted for `raw_file_loader`.

---

## 1. Engineering Goals

These translate directly from Architecture v1 §1 (Architectural Goals), each traceable to specific SRS clauses:

| Goal | Property |
|---|---|
| Structural fidelity | The system must never alter, reorder, deduplicate, or lose source data at any layer; all transformations are read/derive-only (OBJ-1, FR-14, NFR-2). |
| Empirical detection over assumption | Encoding, delimiter, and header-form must be detected at runtime per file, never hard-coded as a fixed schema (OBJ-2, FR-2, FR-3, NFR-5). |
| Reproducible, auditable findings | Every check must be deterministic and individually traceable to a named component (OBJ-3, NFR-3, NFR-6). |
| Descriptive-only genomic profiling | Genomic notation profiling must report facts without asserting cross-file equivalence or biological meaning (OBJ-4, FR-10–FR-12). |
| Explicit unresolved questions | Every open question identified by the SRS/EDA must be surfaced as first-class output, never silently dropped (OBJ-5, OUT-9). |
| Per-file independence | No architectural component may read or reference more than one input file's data during a single profiling run (FR-15, CON-3). |
| Sensitivity-aware handling | Architecture must avoid incidental exposure of raw genotype values in logs, errors, or intermediate artifacts beyond what reporting requires (NFR-4, RISK-8). |
| Extensibility without redesign | New vendor file layouts must be supportable by adding components, not by modifying existing ones (NFR-5, CON-1, CON-5). |
| Testability | Domain logic must be independently testable without file I/O, network, or external services. |

---

## 2. Architectural Principles

- The system is a **single-process, per-file profiling pipeline**. Each input file is processed independently end-to-end; there is no shared mutable state between files and no merge step (FR-15).
- The system follows a **Clean/Hexagonal Architecture style**: the domain layer defines ports (interfaces such as `Detector`, `QualityCheck`, `ReportSerializer`); infrastructure supplies adapters.
- The domain model expresses exactly the concepts the SRS names, and nothing more. It has no concept of "individual," "phenotype," "trait," or "comparison" — such concepts are out of scope and are not modeled even as placeholders.
- Data flows strictly forward through the pipeline for one input file; no step mutates a previous step's output in place — each stage produces a new, immutable value passed to the next stage.

---

## 3. Clean Architecture Rules

The system is organized into **four layers**, with dependencies pointing strictly inward:

| Layer | Contains | Depends on | I/O? |
|---|---|---|---|
| Presentation (CLI) | Entrypoint, argument parsing, exit-code handling | Application layer | No (delegates) |
| Application (Orchestration) | Use-case coordinators sequencing domain operations for one file | Domain layer (via interfaces), Infrastructure (via injected implementations) | No (delegates) |
| Domain | Entities, value objects, detectors, checks, profilers, report model — pure logic | Nothing outside itself | None |
| Infrastructure | File readers, report serializers/writers, config loading, logging setup | Domain interfaces it implements | Yes |

**Mandatory rule:** outer layers depend inward on abstractions defined by the domain layer, never the reverse.

---

## 4. Dependency Direction Rules

- **Dependency Inversion Principle applies throughout:** the domain layer defines ports (`Detector[T]`, `QualityCheck`, `GenomicProfiler`, `ReportSerializer`, `ConfigProvider`); infrastructure and application code depend on these abstractions, never the reverse.
- Cross-module contracts are expressed as **plain data in, plain data out** — no interface passes a mutable file handle or shared state across module boundaries.
- **Only one component may touch the filesystem for reading a source file** — the file-loading adapter (`RawFileLoader`) is architecturally the sole point of file access; other components requiring byte-level or line-level data must consume it from that adapter's output, never by independently reopening the source file.
- Configuration and logging are cross-cutting infrastructure concerns **injected into** domain/application code via interfaces (`ConfigProvider`) or the standard logging facility — never read directly from global state inside domain classes.

---

## 5. Separation of Responsibilities

- **One class per SRS functional requirement** for quality checks and genomic profilers, unified behind shared interfaces (strategy-pattern style). This maps 1:1 to SRS requirements, satisfies traceability (NFR-6), and supports the Open/Closed Principle — a new check can be added without modifying existing ones or the orchestrator.
- Each `QualityCheck`/`GenomicProfiler` implementation computes **exactly one** Finding or Profile.
- The application-layer orchestrator (`ProfileFileUseCase`) sequences domain operations for exactly one file, end to end, depending only on domain interfaces, with concrete implementations received via constructor injection.
- A single composition root is the **only place** concrete infrastructure implementations are bound to domain interfaces — no other module needs to know concrete classes.

---

## 6. Rules About Infrastructure vs. Application vs. Domain Responsibilities

- **Domain:** entities, value objects, detectors, checks, profilers, report model. Pure logic; no file/network access of any kind. Must be independently unit-testable with plain data in, plain data out.
- **Application:** sequences domain operations for one file (load → split → detect → resolve → parse → check → profile → build → serialize). Contains no business logic itself — it delegates.
- **Infrastructure:** file readers, report serializers/writers, config loading, logging setup. The only layer permitted actual I/O. Implements domain-defined interfaces; never the reverse.
- **CLI/Presentation:** parses arguments, invokes the composition root, translates domain/infrastructure exceptions into process exit codes and user-facing messages. Contains no business logic.

---

## 7. Rules About Avoiding Premature Abstraction

- Interfaces (`Detector`, `QualityCheck`, `GenomicProfiler`) are generalized from **exactly two observed file layouts**; this is an acknowledged risk (a third real-world layout could reveal the abstraction is a poor fit). Interfaces are kept **minimal and single-method** (data-in/data-out) specifically to limit the cost of being wrong.
- **Composition over inheritance:** all checks/profilers/detectors implement small protocols/interfaces; no deep class hierarchies or shared base classes carrying behavior. Each check/profiler is independent with no natural "is-a" relationship that would justify a shared behavioral superclass.
- **No cross-file comparison module, chromosome-reconciliation module, or missing-value policy module is built or stubbed with concrete logic in Version 1** — only interfaces that could later support them are noted as extension points. Designing these now, even as empty stubs with logic, would exceed the instruction to reflect only current project scope.
- **Configuration surface area is deliberately bounded:** configurable values are limited to genuine conventions (e.g. default comment marker), never to overriding detection outcomes themselves (e.g. delimiter is always detected, never configurable as a fixed override) — this guards against blurring the empirical-detection goal.

---

## 8. Testing Philosophy

- **Unit testing:** each `Detector`, `QualityCheck`, and `GenomicProfiler` is tested in isolation against small, synthetic in-memory fixtures — never the real source files. Because components take plain data in and return plain data out, no mocking framework is needed for most domain tests beyond simple fixture construction.
- **Integration testing:** the orchestrator is tested end-to-end against small synthetic files exercising all observed layouts, verifying the assembled report contains expected Findings, Profiles, and OpenQuestions.
- **Neutrality testing:** a dedicated test constructs a third, synthetic file layout differing from both evidenced datasets (different column count, different missing-value token) and asserts the pipeline still produces a correct report without code changes — the regression test for "no hard-coded schema" (NFR-5).
- **Determinism testing:** running the pipeline twice on the same fixture file must produce byte-identical serialized output (NFR-3).
- **Test data policy:** automated tests must use synthetic fixture files reproducing structural properties without containing real or realistic personal genotype data; real source files are never committed to a test suite or version control.
- **Traceability:** test module names mirror requirement IDs where practical, so SRS-to-test coverage can be reviewed directly.
- Mocking is used only where a real fault condition cannot be reliably reproduced across platforms (e.g. simulating an unexpected I/O failure) — never as a default testing strategy.

---

## 9. Code Quality Expectations

- Production code favors **plain, unsurprising structure** over cleverness — a normal Python package layout, no exotic patterns beyond what SOLID and separation-of-concerns require.
- **No unnecessary abstractions.** Each class has a single, clearly named responsibility.
- **Strong type safety** and **full type hints** are expected throughout.
- Data-carrying objects are **immutable value objects/dataclasses** with no behavior beyond simple invariants.
- **No premature optimization** — e.g. full in-memory loading is accepted for Version 1 at the evidenced scale, with parallelization noted only as a possible future optimization, not built now.

---

## 10. Error Handling Philosophy

The architecture draws a **strict, mandatory distinction** between two categories of "problem":

### 10.1 Structural/Infrastructure Errors → Exceptions
- File not found, unreadable, or empty.
- File cannot be decoded under any candidate encoding examined by the encoding detector.
- No delimiter can be confidently detected.
- Any unexpected filesystem or I/O failure during read.

These are raised via a **small, typed exception hierarchy** rooted at a shared base, and propagate up to the application-layer orchestrator, which logs the error and reports a clean failure for that file **without crashing a batch run over multiple files** — one file's ingestion failure must not prevent independent processing of another file (per-file independence, FR-15).

### 10.2 Data-Quality Observations → Never Exceptions
- Malformed/ragged rows, duplicate headers, duplicate RSIDs, duplicate chromosome-position pairs, missing-value tokens are **always represented as Finding data, never raised as exceptions**.
- A file containing many such findings is not itself an error condition for the system.
- This split keeps "is something wrong with the file as a whole" (infrastructure) cleanly separate from "what does the data look like" (domain findings) — avoiding the anti-pattern of using exceptions for expected, countable conditions.

### 10.3 Exception Hierarchy Placement
- The exception hierarchy is owned by the **domain layer**, mirroring the pattern already established by `domain/interfaces.py`: domain defines the contract/vocabulary; infrastructure raises against it; application catches it. This preserves the inward-dependency rule.

### 10.4 General Rules
- **Never use broad `except Exception`.** Only specific, anticipated exception types are caught and translated.
- **Always preserve original exceptions via chaining** (`raise ... from err`) — never suppress the underlying cause.
- **Never silently ignore errors.**

---

## 11. Determinism / Reproducibility Requirements (NFR-3)

- Given the same input file, all structural and data-quality checks must produce **identical results on repeated execution**, so findings can be regenerated and audited rather than taken on trust.
- This extends to infrastructure adapters: reading the same file twice (whether via one instance or two) must yield byte-identical output.
- No component may introduce nondeterminism (e.g. via unordered collections, locale-dependent behavior, or time-dependent logic) into any structural or data-quality result.

---

## 12. Data Integrity Requirements

- **FR-14:** the system shall not modify, move, rename, rewrite, deduplicate, or reorder any source input file at any point during ingestion, validation, or profiling.
- **NFR-2:** all ingestion, validation, and profiling operations shall be read-only with respect to source files; no operation shall write to, overwrite, or transform the original input file.
- Non-destructiveness applies to **in-memory representations of file content**, not only the file on disk — no step in the pipeline may lose, reorder, deduplicate, or silently alter data as it flows between stages.
- Where a lossless decode is required to produce a workable in-memory text representation from arbitrary bytes, the chosen mechanism must be **provably lossless and non-failing** (e.g. reversible byte-to-codepoint mapping), so that no interpretation is smuggled into what is meant to be a purely mechanical step.
- **NFR-4 (data sensitivity):** all ingested genotype files are treated as sensitive personal data. No component may log, display, or persist raw genotype/allele/line content beyond what a Finding or Profile's own reporting design explicitly allows — and even then, only bounded, counted, or labeled representations, never full raw content, and never at default verbosity.

---

## 13. Constraints Future Modules Must Preserve

- No module may assume a fixed schema (column count, header placement, missing-value token, or chromosome-label vocabulary) — all such properties must be detected or configured per file (NFR-5).
- No module may perform cross-file comparison, concordance analysis, or merging of any kind (FR-15, CON-3).
- No module may resolve, interpret, or reconcile chromosome-notation differences, strand claims, or duplicate-cause explanations — these remain explicit open questions attached to the report, never silently resolved.
- No module may introduce biological, medical, ancestry-related, or phenotype interpretation of any kind.
- Every Finding/Profile-producing module must be independently unit-testable without file I/O.
- Every structural or data-quality finding must be traceable to a specific, named check or component (NFR-6).
- Configuration values must be injected, never read from global/environment state inside domain or infrastructure logic.
- Only one component may open a given source file for reading; all other components needing that file's content must consume it from that component's output.

---

## 14. Mandatory Engineering Constraints

These are non-negotiable and binding on all future modules:

1. Four-layer architecture with inward-only dependencies (CLI → Application → Domain ← Infrastructure).
2. Domain layer performs no file/network/external-service I/O of any kind.
3. FR-14/NFR-2: source files are never modified, moved, renamed, rewritten, deduplicated, or reordered, at any layer.
4. NFR-3: identical input must always produce identical output on repeated execution.
5. NFR-5: no hard-coded schema assumptions anywhere in domain code.
6. NFR-4/RISK-8: no raw genotype/allele/line content in logs, errors, or default-verbosity output.
7. Data-quality conditions are always Finding data, never exceptions; structural/infrastructure failures are always typed exceptions, never Findings.
8. No broad `except Exception`; all caught exceptions are specific and chained to their original cause.
9. No cross-file comparison, merging, or reconciliation logic anywhere in Version 1.
10. No module may exceed the scope explicitly defined for it by the SRS/Architecture — extension points are named, never built ahead of need.
11. Every domain component (`Detector`, `QualityCheck`, `GenomicProfiler`) must be unit-testable with plain data in/out, without file I/O.
12. Configuration values are injected via `ConfigProvider`; never read from environment/global state inside domain or infrastructure classes directly.

---

## 15. Recommended Practices

These are strongly encouraged but not held to the same binding standard as Section 14:

- Prefer composition over inheritance for all check/profiler/detector implementations.
- Keep interfaces minimal (single-method, data-in/data-out) to limit the cost of an abstraction later proving to be a poor fit.
- Mirror test module names to requirement IDs where practical, for direct SRS-to-test traceability.
- Bound any example/sample data held in a Finding (e.g. "first N examples") rather than storing unbounded lists, for memory and sensitivity reasons.
- Favor full in-memory processing over streaming at the current evidenced scale, deferring streaming complexity until a real need is demonstrated.
- Where a design decision is not fully specified by the SRS or Architecture, document it explicitly as an assumption requiring sign-off rather than deciding silently.

---

## 16. Explicitly Rejected Approaches

- **Rejected:** designing or stubbing cross-file comparison, chromosome-notation reconciliation, missing-value handling policy, or genotype-encoding unification logic in Version 1 — explicitly out of scope; only extension points may be named.
- **Rejected:** using exceptions to represent data-quality conditions (duplicates, malformed rows, missing tokens) — these must always be Finding data.
- **Rejected:** hard-coding any structural property (column count, delimiter, missing-value token, chromosome vocabulary) as a fixed assumption anywhere in domain code.
- **Rejected:** allowing more than one component to independently open/read a given source file — all byte/line-level access must flow from the single designated file-loading adapter's output.
- **Rejected:** broad `except Exception` handling anywhere in the codebase.
- **Rejected:** deep class hierarchies or shared behavioral base classes among checks/profilers/detectors, absent a genuine "is-a" relationship.
- **Rejected:** streaming/large-scale-optimized I/O design in Version 1, absent evidence that the current full in-memory approach is insufficient.
- **Rejected:** logging raw file/line/genotype content at any verbosity level by default.
- **Rejected:** silently resolving open questions (chromosome-notation equivalence, strand consistency, duplicate causes, etc.) instead of surfacing them as first-class, unresolved output.

---

*This document reflects the Stage 1 engineering review conclusions as established for the PhenoPred project and validated through the `raw_file_loader` module's design, implementation, and test cycles. It introduces no new decisions and supersedes no prior approval — it exists solely to consolidate what was already agreed, for reference in designing subsequent modules.*
