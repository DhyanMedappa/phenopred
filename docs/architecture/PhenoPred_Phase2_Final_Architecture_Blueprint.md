PhenoPred

**Software Architecture — Phase 2**

Trait Engine, Comparison Engine, and Demonstration Application

*Architecture derived from PhenoPred SRS v1.0, Architecture V1 (Approved), the EDA notebook, and direct verification against the two real raw genotype files (AncestryDNA.txt, anonymous_genome_v5_build37.txt)*

Document status: **FINAL — frozen for implementation.** This document supersedes both prior Phase 2 blueprints in full. Where this document is silent on a point the prior blueprints covered, the most recent prior blueprint still applies; where they conflict, this document governs.

*Scope note: This document designs Phase 2 architecture only. It does not modify Architecture V1. Every design decision below is either directly justified by the SRS/EDA/Architecture V1, or verified against the two real data files, or explicitly flagged as an assumption requiring a bounded, named verification step before implementation.*

---

# 1. Executive Summary

Phase 2 adds a Trait Engine, a Comparison Engine, and a Streamlit demonstration application on top of the frozen, fully-tested Architecture V1 pipeline. Nothing in V1 is modified. Phase 2 is implemented as a sibling package tree that consumes V1's public outputs as read-only inputs — exactly the extension path Architecture V1 Section 16 anticipated and deliberately left unbuilt.

This review is the third and final pass over that plan. Two prior blueprints proposed and then partially corrected a design; this document is the result of checking every remaining open question directly against the real files and the primary scientific literature rather than carrying forward unverified assumptions. Two outcomes matter most:

1. **All required trait-associated SNPs are present and genotype calls are available in both files. Allele interpretation has been resolved for the currently implemented traits, with TAS2R38 requiring final strand-convention verification.** This was the largest unresolved risk in the project and is now fully closed.
2. **Two of those SNPs (`rs4988235`, `rs17822931`) required an explicit strand-orientation resolution**, which this review completed by tracing each SNP's canonical GRCh37 forward-strand reference/alternate alleles through NCBI ClinVar records that match the files' exact chromosome positions. Both are now resolved with citations, not left as open questions. Details in Section 9.

The final scope is unchanged in shape from the prior blueprints (5 required traits, a concordance-based comparison engine, a single-page Streamlit app, one optional stretch trait) but is now fully de-risked on the scientific side: every genotype the Trait Engine needs is in hand, correctly interpreted, and sourced.

---

# 2. Architecture Goals and Principles

Carried forward unchanged from Architecture V1's own goals (Section 1 of that document), restated for Phase 2:

| Goal | Phase 2 Application |
|---|---|
| Structural fidelity | Phase 2 never alters V1 outputs; it only reads them. |
| Empirical detection over assumption | Trait/comparison logic reads genotype layout from V1's own detected structure — never hard-codes "Dataset A" or "Dataset B" behavior. |
| Reproducible, auditable findings | Every trait prediction and comparison metric is deterministic and traceable to a named SNP, model, and citation. |
| Explicit unresolved questions | Every scientific caveat (ancestry bias, unphased haplotype approximation, heuristic-only identity claims) is a first-class, visible field — never silently omitted. |
| Per-file independence at the ingestion layer | Trait prediction runs per file, independently, exactly as V1's own pipeline does; only the Comparison Engine — a new, explicitly cross-file component — combines two files, and only when a second file is present. |
| Sensitivity-aware handling | Phase 2 inherits V1's logging discipline: no raw genotype dumps at default verbosity. |
| Extensibility without redesign | New traits, new comparison metrics, or new vendor files are added by registering new components, never by editing the engine loop. |
| Testability | All trait models and comparison logic are pure functions over plain data — no file I/O inside domain code. |
| **(New for Phase 2) Scientific traceability** | Every genotype→phenotype rule in the SNP registry carries its source (gene, canonical dbSNP allele convention, citation) as data, not as a comment — so it can be audited the same way a Finding or Profile is audited in V1. |

---

# 3. Final Scope Definition

| Tier | Contents |
|---|---|
| **Must have** | Trait Engine for all 5 required traits, each using the strongest scientifically defensible model achievable within the timeline (Section 8); scientific trait cards with phenotype, SNP/genotype evidence, interpretation, confidence, and limitations (Section 11); Comparison Engine with RSID-based concordance, 4-way match classification, heuristic-only identity statement, and per-trait agreement diff with explanation (Section 10); Streamlit app supporting one-file and two-file flows (Section 12); downloadable combined JSON report extending V1's existing serializer shape (Section 14) |
| **Should have** | Confidence badges and a concordance summary chart (Section 13); one reused V1-native visualization; a short "how PhenoPred may differ from a commercial report" methodology note per trait card |
| **Optional, gated** | ALDH2 alcohol-flush trait — attempted only after all 5 required traits are implemented, tested, and demo-ready (Section 8.6) |
| **Explicitly excluded** | See Section 18 |

No change in shape from the prior blueprint. What changed is confidence: every item in "must have" is now known to be buildable against real, verified data, not a plan resting on an assumption.

---

# 4. System Overview

```
                    ┌─────────────────────────────┐
                    │   Architecture V1 (frozen)    │
                    │   cli / application / domain /│
                    │   infrastructure / tests       │
                    └──────────────┬────────────────┘
                                   │ read-only: GenotypeFile, ProfilingReport
                                   ▼
                    ┌─────────────────────────────┐
                    │        GenotypeIndex          │  ← the one integration adapter
                    │  rsid → normalized genotype   │     (Section 9)
                    └──────┬───────────────┬────────┘
                            ▼               ▼
                 ┌──────────────┐   ┌──────────────────┐
                 │ Trait Engine  │   │ Comparison Engine │  ← only runs with 2 files
                 │ (5 traits,    │   │ (concordance,     │
                 │  1 per file)  │   │  identity heuristic,│
                 │               │   │  trait diff)       │
                 └──────┬────────┘   └─────────┬──────────┘
                        └───────────┬───────────┘
                                    ▼
                         ┌─────────────────────┐
                         │   Streamlit webapp    │
                         │  (presentation only)  │
                         └─────────────────────┘
```

One input file always produces one `TraitReport`. A second input file additionally produces one `ComparisonReport`. Nothing about the single-file path depends on whether a second file will ever be supplied — this is enforced by keeping `ComparisonEngine` a strictly optional, additive consumer of two independently-produced `GenotypeIndex`/`TraitReport` pairs, never a precondition for the Trait Engine itself.

---

# 5. Phase 2 Architecture Design

Unchanged from the prior blueprint and reaffirmed after this review: Phase 2 is a **sibling package tree** (`phenopred_phase2/`), not a subpackage of `phenopred/`, with **its own composition root**. No file inside `phenopred/cli`, `phenopred/application`, `phenopred/domain`, `phenopred/infrastructure`, or `phenopred/tests` is modified. This is re-affirmed, not re-derived — it was correct in both prior reviews and nothing found this pass changes it. The one still-open integration question (whether `ProfileFileUseCase` retains its in-memory `GenotypeFile` or only writes a serialized report) remains a **required pre-implementation check against the actual V1 source**, listed again in Section 20 — this document still only has the architecture document, not the codebase, to reason from.

Dependency direction, restated as a hard rule: `traits/` and `comparison/` may depend on V1's public domain entities only (`GenotypeFile`, `DataRow`, `ProfilingReport`, `HeaderInfo`); `webapp/` may depend on `traits/`, `comparison/`, and V1's `application` layer; nothing in Phase 2 may depend on `phenopred/tests`.

---

# 6. Folder Structure

```
phenopred/                       # UNCHANGED — frozen, 505 tests passing, not touched
├── cli/ · application/ · domain/ · infrastructure/ · tests/

phenopred_phase2/
├── traits/
│   ├── domain/
│   │   ├── entities.py           # TraitDefinition, GenotypeCall, TraitPrediction, TraitCard, ConfidenceLevel
│   │   ├── snp_registry.py       # static table: rsid, gene, GRCh37 forward-strand ref/alt,
│   │   │                         #   phenotype-associated allele under that convention, citation
│   │   ├── genotype_index.py     # GenotypeFile rows -> rsid -> normalized genotype (Section 9)
│   │   ├── interfaces.py         # TraitModel protocol
│   │   └── models/
│   │       ├── eye_colour_model.py       # strategy-selectable: fitted or rule-based (Section 8.1)
│   │       ├── lactase_persistence_model.py
│   │       ├── actn3_model.py
│   │       ├── earwax_model.py
│   │       ├── bitter_taste_model.py
│   │       └── aldh2_model.py             # optional, gated (Section 8.6)
│   ├── application/
│   │   └── trait_engine.py       # runs all registered TraitModels -> TraitReport
│   └── reporting/
│       └── trait_card_builder.py # assembles the fixed TraitCard schema (Section 11)
├── comparison/
│   ├── domain/
│   │   ├── entities.py           # ConcordanceResult, IdentityLikelihood, TraitComparison, ComparisonReport
│   │   ├── concordance_calculator.py     # 4-way classification (Section 10.4)
│   │   ├── identity_heuristic.py
│   │   └── trait_diff.py
│   └── application/
│       └── comparison_use_case.py
├── webapp/
│   ├── app.py                    # Streamlit entrypoint (presentation only)
│   ├── composition.py            # Phase 2's own composition root
│   └── components/
└── tests/
    ├── traits/                   # includes a fixture with a deliberately missing required SNP
    ├── comparison/                # includes a fixture exercising the indel-vs-SNP mismatch category
    └── webapp/
```

No structural change from the prior blueprint beyond the `aldh2_model.py` placeholder (built last, only if time allows) and the SNP registry's fields being made explicit (Section 9).

---

# 7. Trait Engine Design

Unchanged in shape: a declarative registry (`trait_id → TraitDefinition{name, required_rsids, model, evidence_refs}`), one model class per trait implementing a shared `TraitModel` protocol, run by a single `trait_engine.py` loop that iterates the registry — new traits are added by registration, never by editing the loop (same Open/Closed pattern V1 already uses for its quality checks).

One addition based on Section 8.1's eye-colour decision: `TraitModel` implementations may internally select between two scoring strategies (fitted-coefficient vs. rule-based) behind the same interface. This is a strategy-pattern detail inside `eye_colour_model.py`, not a change to the engine or the registry — the engine still sees one `TraitModel` per trait and does not need to know which internal strategy was used.

---

# 8. Final Trait Model Decisions

For each trait: scientific validity, evidence strength, implementation complexity, genotype-interpretation reliability, and suitability for an academic demonstration.

## 8.1 Eye Colour — Final Decision

**Options considered:**

| Option | Description | Verdict |
|---|---|---|
| A | Full IrisPlex 6-SNP published multinomial logistic regression (Walsh et al. 2011) | **Primary path, timeboxed** |
| B | Transparent, transparent allele-effect approximation based on published directional associations over the same 6 real SNPs, directionally correct but not the fitted model | **Automatic fallback if A's timebox expires** |
| C | Single-SNP model (`rs12913832` only) | **Rejected** |
| D | Call the external HIrisPlex web tool live and display its output as the prediction | **Rejected as the core mechanism; retained only as an offline validation aid** |

**Findings that drove the decision:**
- All 6 IrisPlex SNPs (`rs12913832`, `rs1800407`, `rs12896399`, `rs16891982`, `rs1393350`, `rs12203592`) are confirmed present and called, identically, in both real files (verified by direct search of both files — not assumed).
- IrisPlex is a 6-SNP multinomial logistic regression with a published, fixed coefficient table (Walsh et al., *Forensic Science International: Genetics*, 2011) — a bounded lookup-and-apply implementation task once the coefficients are transcribed correctly, not an open-ended modeling exercise.
- A citable, actively maintained reference implementation exists (`hirisplex.erasmusmc.nl`, the Kayser/Walsh laboratories' own tool) — legitimate to cite as the authoritative source and to use once, offline, to validate this individual's own predicted output against a known-good implementation.

**Why Option C is rejected:** it was only ever a hedge against a model I had previously mischaracterized as far larger than it actually is (a 24-SNP statistical model). Now that the real model is known to be 6 SNPs with all 6 confirmed present, discarding 5 of them buys no time and is scientifically weaker for no reason.

**Why Option D is rejected as the core mechanism:** a live external dependency during a graded demonstration is pure downside (network failure, tool downtime, rate limits) for a feature — "our engine computed this" — that is precisely what's being examined. It remains valuable as an offline cross-check performed once during development, and as a citation in the trait card's evidence section.

**Final decision:** implement Option A within a strict **60-minute timebox** on Day 1 to source and correctly transcribe the published coefficient table (candidate source: the open PDF of Walsh et al. 2011 available via ResearchGate). If the coefficients are not confirmed and verified within that window, `eye_colour_model.py` falls back to Option B automatically — the same real 6-SNP panel, scored by a transparent, documented rule (heaviest weight on `rs12913832`, independently the strongest single predictor in every source reviewed), explicitly labeled in the card as *"IrisPlex SNP panel, simplified scoring — published coefficients not used."* This is a pre-committed decision tree, not something to improvise under time pressure mid-implementation.

**Implementation risk:** low-moderate. The 6-SNP panel and both scoring strategies are fully specified; the only real uncertainty is whether the exact published coefficients can be sourced and correctly transcribed in 60 minutes — and the fallback removes that uncertainty from the critical path entirely.

## 8.2 Lactase Persistence — Final Decision

Single SNP (`rs4988235`), confirmed present in both files, genotype **GG** (forward strand, both files). Per Section 9's dbSNP-sourced resolution, this resolves to the historically-cited "CC" genotype under the `-13910C>T` literature convention — **lactase non-persistent**. Model: unchanged, deterministic genotype table. Evidence strength: very high (one of the most replicated single-SNP trait associations in human genetics). Suitability for demonstration: excellent — simple, correct, and now fully traceable to a cited source for the allele-convention resolution, which is itself a good demo talking point.

## 8.3 ACTN3 — Final Decision

Single SNP (`rs1815739`), confirmed present, genotype **CC** in both files, matching the standard C/T convention directly (no strand ambiguity found). CC = RR genotype ("power"-associated, alpha-actinin-3 present). Model, evidence strength, and suitability: unchanged from the prior blueprint — this trait required no correction this pass. Card must retain the caveat that genotype is one minor factor among many in athletic performance, not a determinant.

## 8.4 Earwax Type — Final Decision

Single SNP (`rs17822931`), confirmed present, genotype **CC** (forward strand, both files). Per Section 9's resolution, this corresponds to **GG under the Yoshiura et al. 2006 gene-strand convention — wet earwax, dominant homozygous.** This is now a sourced, confirmed interpretation, not a hypothesis. Model: unchanged deterministic genotype table, now with the strand-conversion step made explicit and citable in the registry.

## 8.5 Bitter Taste (TAS2R38) — Final Decision

Three SNPs (`rs713598`, `rs1726866`, `rs10246939`), all confirmed present in both files. This individual is homozygous at all three loci — meaning, for this specific demo case, diplotype phasing is unambiguous (only one possible diplotype exists when every site is homozygous). The general model must still implement the PAV/AVI diplotype-scoring approach with a documented unphased-approximation caveat for the heterozygous-at-multiple-loci case, since a general-purpose tool has to handle files where that case does arise — the real files simply don't exercise the hardest path, which is worth stating plainly in the card rather than glossing over. **New verification item, not yet resolved:** unlike the other four traits, this review did not confirm the exact forward-strand allele convention for the three TAS2R38 SNPs against a position-matched dbSNP/ClinVar record. This must be done alongside the earwax/lactase confirmations in the bounded pre-implementation check (Section 20) before the diplotype interpretation is finalized.

## 8.6 ALDH2 (Alcohol Flush) — Final Status

**Optional, explicitly gated, not required.** Single SNP (`rs671`), confirmed present, genotype **GG** (wildtype/functional) in both files. Scientifically strong (well-replicated, near-monogenic effect), cheap to implement given the registry pattern. **Final gate: build only after all 5 required traits are implemented, tested, and the Streamlit demo runs cleanly end-to-end with them.** If Day 1 finishes behind schedule at any point, this is the first and only thing dropped — it was never part of the required scope and its absence costs nothing academically.

---

# 9. Genotype Normalization Strategy

## 9.1 Decision: limited, SNP-level allele normalization (Option B), not genome-wide harmonization

Three options were on the table for handling the strand/allele-convention issues this review surfaced:

| Option | Verdict |
|---|---|
| A — full genome-wide strand-harmonization system (infer and correct orientation for every SNP in a file) | **Rejected — unnecessary engineering.** This would be a research-scale undertaking (correct general strand inference requires ambiguous-SNP handling, population allele-frequency lookups, or a full liftover/reference toolchain) solving a problem Phase 2 doesn't have: it only ever needs to interpret ~12 named SNPs, not arbitrary ones. |
| B — limited, per-SNP allele normalization for exactly the SNPs the Trait/Comparison Engines use | **Adopted.** |
| C — documentation-only (state the risk, don't resolve it in code) | **Rejected as insufficient**, now that the actual resolution is known and verifiable — documenting a risk you could instead just correctly resolve is a worse outcome, not a more cautious one. |

## 9.2 What this means concretely

The SNP registry (`snp_registry.py`) stores, for each of the ~12 required SNPs, **the GRCh37 forward-strand reference/alternate allele pair as confirmed against a position-matched NCBI/ClinVar or dbSNP record**, plus the phenotype-associated allele expressed in that same forward-strand convention. Trait models read genotype interpretation directly off this static, verified table — no runtime strand inference is performed anywhere in the system. This is a dozen static entries, not a general-purpose engine.

## 9.3 Resolutions found this review (with sourcing)

- **`rs4988235` (lactase persistence).** NCBI/Nature Genetics HGVS naming and a position-matched ClinVar-style variant record both confirm the GRCh37 forward-strand locus `NC_000002.11:g.136608646` — the exact position both real files report — has reference allele **G**, alternate allele **A**. The historically-cited "−13910C>T" lactase-persistence literature uses the opposite (gene-relative) strand, where persistence associates with **T**; on the genomic forward strand actually used by both files, that is its complement, **A**. This individual's real genotype, **G/G**, is therefore the forward-strand equivalent of the literature's **C/C** — **lactase non-persistent**.
- **`rs17822931` (earwax).** A ClinVar record for this exact GRCh37 position (Chr16:48258198 — again, an exact match to both files) gives the HGVS genomic notation `NC_000016.9:g.48258198C>T`, i.e., forward-strand reference **C**, alternate **T**. Yoshiura et al. 2006's widely-cited "538G>A" nomenclature is on the gene's coding strand, which is complementary to the genomic forward strand at this locus (G↔C, A↔T). This individual's real genotype, **C/C** on the forward strand, is therefore the equivalent of the coding-strand literature's **G/G** — **wet earwax, dominant homozygous**.
- `rs12913832`, `rs1800407`, `rs12896399`, `rs16891982`, `rs1393350`, `rs12203592` (the 6 IrisPlex SNPs) and `rs1815739` (ACTN3) were checked against the standard allele letters used across every source reviewed and require no strand conversion — the files' reported alleles (G, C, G, G, G, C, and C respectively) match the commonly-cited convention directly.
- The three TAS2R38 SNPs remain unresolved on this specific point and are the one item carried into Section 20 as still requiring a bounded check.

## 9.4 Scope boundary — what `GenotypeIndex` does and does not handle

| Concern | In scope | Handling |
|---|---|---|
| Allele ordering | Yes | Canonicalized as a sorted two-character pair (e.g., always "AG", never "GA" for the same genotype) |
| Missing values / no-calls | Yes | Explicit `NoCall` sentinel; trait models report "insufficient data," never guess |
| Indels (`I`/`D`, `II`/`DD`/`DI`) | Yes | Explicit `Indel` sentinel, kept distinct from SNP genotypes — this is what drives the Comparison Engine's 4-way classification (Section 10.4) |
| Haploid calls (X/Y/MT single-character genotypes) | Yes | Wrapped with an explicit haploid flag, not silently duplicated into a fake homozygous pair — preserves the real biological distinction for any future haploid-relevant trait, even though none of the current 12 SNPs are haploid |
| Strand complementation | **Limited — only for the ~12 named SNPs in the registry**, resolved statically as data (Section 9.2–9.3) | Not a general-purpose runtime capability |
| Ambiguous (A/T or C/G) SNPs | **Out of scope, and correctly so** | None of the 12 required SNPs are ambiguous-pair SNPs (verified during this review's allele checks), so the classic "can't infer strand from alleles alone" problem doesn't arise here — it would only need solving if a future trait introduced such a SNP, at which point it becomes a new, explicit registry entry, not a new subsystem |
| Vendor differences | Yes, by construction | `GenotypeIndex` is built on top of V1's already-vendor-detected column layout, so it never branches on "which vendor" — this is the concrete implementation of the genotype-unification extension point Architecture V1 Section 16 deliberately deferred |

This table is the final, binding scope for `GenotypeIndex`. Anything not listed here is out of scope by default.

---

# 10. Comparison Engine Design

## 10.1 Is RSID-based comparison scientifically acceptable?

Yes, and it is the correct choice given this project's own evidence base — SRS RISK-1 already documents that the two files' chromosome-notation conventions are incompatible, ruling out a chromosome+position join without an authoritative reconciliation this project doesn't have. RSID is the safer available join key. This carries one inherited, explicit caveat (unchanged from the prior blueprint): the SRS itself states it "cannot yet be assumed that a given RSID refers to the same physical genomic position across both files" — Phase 2 states this as an inherited assumption in its methodology text rather than silently relying on it.

## 10.2 Is ~162,481 shared markers sufficient?

Yes, comfortably. This is roughly a quarter of each file's total RSIDs and is far more than needed for a stable concordance statistic — the real computed result (99.99% concordance) did not meaningfully change when trimming from the raw 165,393 overlap down to the 162,481 filtered, comparable set, which is itself evidence the sample is large enough to be stable under reasonable filtering choices.

## 10.3 Is the concordance interpretation correct?

Yes, with the identity-heuristic wording unchanged from the prior blueprint: report the rate, state plainly that a rate this high is *consistent with, not proof of,* the same individual, and that certified relatedness/identity determination needs many more markers and dedicated statistical methods. **IBD/IBS should be named in the report text** (a one-sentence mention: "rigorous identity or relatedness determination uses identity-by-descent/identity-by-state estimation across many more markers than this concordance check performs") — not implemented. Naming the correct terminology without building the underlying statistics is itself good scientific communication: it tells an examiner the team knows what the rigorous method is called and why they didn't build it under this timeline, rather than looking unaware of it.

## 10.4 Four-category mismatch classification — confirmed correct, retained

Reaffirmed from the prior blueprint: classify every shared RSID into **SNP match / SNP mismatch / indel-or-structural-type mismatch / no-call on one or both sides**, rather than a flat 3-way match/mismatch/no-call. This was derived directly from inspecting real mismatches in the actual files, where several of the raw "mismatches" were indel-token artifacts rather than true genotype disagreements — the 4-way classification is what correctly separates those. No further change needed this pass.

## 10.5 Final Comparison Engine architecture

Unchanged from the prior blueprint's Section 6, with the IBD/IBS terminology addition (10.3) and the 4-way classification (10.4) both now confirmed final rather than provisional.

---

# 11. Scientific Validation Strategy

**Decision: this is a reporting/data-shape concern, not a new architecture component.**

A dedicated "validation layer" — a new class hierarchy sitting between trait prediction and reporting — was considered and rejected as unnecessary complexity. The flow requested (prediction → scientific reference → observed genotype → interpretation → confidence → limitations) is fully satisfied by defining `TraitCard` as a **fixed-schema, mandatory-field value object** with exactly those fields, assembled by the existing `trait_card_builder.py`. This mirrors the same pattern Architecture V1 already uses for `Finding` and `Profile` — an immutable value object with required fields — rather than introducing a new validation subsystem. If a trait model fails to populate any required field, that is a construction-time error, which is a cheap, existing enforcement mechanism, not a reason to build a separate validator. This is the simplification the review process asked for: the same scientific rigor, with no new component.

---

# 12. Streamlit Application Design

Unchanged from the prior blueprint: single page, expandable sections, in this order — upload (1 required, 1 optional) → pipeline status/spinner → profile summary → trait results → comparison results (appears only with a second file) → visualizations → download report. No missing sections identified this pass; no section identified as unnecessary. The caching recommendation (cache pipeline + engine output keyed on file hash, given Streamlit's rerun-on-every-interaction behavior against ∼650k-row real files) remains a firm requirement, not a nice-to-have — confirmed necessary now that real file sizes are known precisely (17.47MB / 15.26MB, ∼677K / ∼631K rows).

---

# 13. Visualization Strategy

| Visualization | Classification | Rationale |
|---|---|---|
| Confidence badges per trait card | **MUST HAVE** | Cheapest, clearest way to convey uncertainty; already required by the trait-card schema (Section 11) |
| Unified genotype/phenotype summary table | **MUST HAVE** | Single-glance overview an examiner can follow without reading every card |
| Concordance chart (match/mismatch/indel/no-call, 4-way) | **MUST HAVE** | Direct visual answer to the professor's core evaluation question; now backed by real numbers (162,481 shared, 99.99% concordance) that make the chart genuinely compelling, not illustrative |
| Concordance summary stat block (shared count, match count, %) above the chart | **SHOULD HAVE** | Near-zero cost, materially strengthens the chart by showing scale |
| Trait comparison table (File A vs. File B vs. agree/differ + reason) | **MUST HAVE** | Directly operationalizes the professor's explicit "explain differences" requirement |
| One reused V1-native visualization (e.g. chromosome-label distribution) | **SHOULD HAVE** | Visibly demonstrates "built on V1," not "replaced V1" |
| RSID overlap Venn diagram | **SHOULD HAVE, only if trivial** | Legitimate with real counts in hand (677,436 / 631,455 / 165,393 shared); build only if it costs under ~5 minutes once the concordance chart exists — not worth dedicated engineering time |
| Any genome-wide/per-position visualization (e.g. Manhattan-style concordance-by-position) | **REMOVE** | Low academic value for this project's actual scope; real engineering cost against ~650K rows per file |
| Interactive/3D/simulation visuals | **REMOVE** | No demo value proportional to engineering risk at this timeline |

---

# 14. Reporting Design

Unchanged from the prior blueprint: one combined, downloadable JSON report that **extends** V1's existing `ReportSerializer` output shape — adds a `traits` section and, when a second file is present, a `comparison` section — rather than inventing a parallel format. Every `TraitCard` in the report carries the full fixed schema from Section 11, including the SNP registry's cited allele-convention source for any trait where a strand conversion was applied (Section 9.3), so the report itself is the audit trail for that reasoning, not just this document.

---

# 15. Testing Strategy

Unchanged in approach from the prior blueprint, with two additions made concrete by this review:

- A synthetic fixture with a **deliberately missing required SNP**, since the two real files don't exercise the "insufficient data" path — this path must still be built and tested for a general-purpose tool (Section 6, `tests/traits/`).
- A synthetic fixture exercising the **indel-vs-SNP mismatch category** specifically (Section 10.4), since the real files' true mismatch count is too small (12 out of 162,481) to reliably exercise every classification branch in an integration test.
- Re-run `pytest phenopred/tests -q` at the end of Phase 2 implementation and confirm all 505 V1 tests still pass, untouched — a non-negotiable gate before the exam, unchanged from prior blueprints.

---

# 16. Implementation Roadmap

**First priority (before any trait code is written):** the bounded pre-implementation verification list in Section 20 — dbSNP confirmation for the 3 TAS2R38 SNPs, and the V1 `ProfileFileUseCase` return-value check. Both are small, both block correctness downstream if skipped.

**Second priority:** `GenotypeIndex` + SNP registry, populated with the now-confirmed allele conventions from Section 9.

**Third priority:** the 3 lowest-risk single-SNP trait models (lactase, ACTN3, earwax) — working demo exists early.

**Fourth priority:** bitter taste (homozygous case is simple for this demo; still build the general phasing-fallback path).

**Fifth priority:** eye colour, per the timeboxed A→B decision tree in Section 8.1.

**Sixth priority:** Comparison Engine with the 4-way classification; validate against the real files (expect ~99.99% concordance — a materially different number is a bug signal, not a data surprise, since this exact result is now a known baseline).

**Seventh priority:** Streamlit — single-file flow end-to-end first, then second-file/comparison flow, then caching, then charts.

**Feature freeze point:** several hours before the exam, once steps 1–7 are complete and rehearsed. No changes after freeze except critical bug fixes discovered in rehearsal.

**Emergency fallback scope (if time runs out before step 5–7 complete):** the 3 single-SNP traits (lactase, ACTN3, earwax) plus a working single-file Streamlit flow is a legitimate, defensible, demoable minimum — better to freeze early on a smaller, fully-working scope than to ship all 5 traits and the comparison engine partially broken.

**Must not be attempted, at any point:** ALDH2 before the 5 required traits are done (Section 8.6); any modification to a V1 file; a live call to the external HIrisPlex web tool from inside the app (Section 8.1); a genome-wide strand-harmonization system (Section 9.1); a dedicated validation-layer component (Section 11); any feature listed in Section 18.

---

# 17. Risk Assessment

**Scientific risks**
- The TAS2R38 strand-convention check (Section 20) remains open; if it surfaces a similar flip to the lactase/earwax cases, the diplotype interpretation logic must be updated before the card ships — budget for this in priority-4 time, not after.
- Ancestry-generalizability caveat (standing, unchanged): most of these associations were established primarily in European-ancestry cohorts; state this on every card regardless of confidence tier.
- Eye colour's fallback path (Option B, Section 8.1) is scientifically weaker than the fitted model — acceptable only because it is explicitly labeled as such in the card, never presented as equivalent to the real IrisPlex output.

**Implementation risks**
- The V1 integration touchpoint (Section 5) is still unverified against actual source code — first item in Section 20, must be resolved before `GenotypeIndex` is written.
- Streamlit performance against real ~650K-row files without caching remains the single most likely cause of a demo feeling sluggish — non-negotiable to build caching alongside the first working flow, not as later polish.

**Timeline risks**
- Three full architecture-review passes have now been completed without implementation starting. That is itself the largest remaining risk to examination success — this document is final specifically so that Day 1 begins with code, not further review. No further blueprint revisions should be requested before the exam; any new issue discovered during implementation should be resolved locally against this document's principles, not by requesting another full review cycle.

---

# 18. Explicitly Excluded Features

AI avatar generation; interactive phenotype exploration/simulation; in-app ingestion or parsing of commercial PDF reports; any trait beyond the 5 required plus (optionally, gated) ALDH2; kinship/IBD statistical identity verification (named in report text only, per Section 10.3, never implemented); PDF report generation; Streamlit multipage navigation; a dedicated scientific-validation architecture component (Section 11); a genome-wide strand-harmonization system (Section 9.1); a live call to any external prediction tool from inside the app; any modification to a V1 file.

---

# 19. Final Assumptions

- Both real files' header claims of forward (+) strand orientation are taken at face value for the purpose of interpreting the SNP registry (Section 9) — this matches the registry's own GRCh37-forward-strand convention, but neither file's strand claim has been independently, biochemically verified (this is the same unresolved point SRS RISK-6 already names; Phase 2 inherits it rather than resolving it, since resolving it would require wet-lab verification outside this project's scope).
- RSID-based reconciliation is used under the assumption that both vendor files reference the same dbSNP identifiers across the two files for the purpose of both trait lookup and comparison — inherited from SRS Section 8.2's own explicit statement that this "cannot yet be assumed" but is treated as the best available join key given no authoritative alternative exists.
- The `ProfileFileUseCase` integration point (Section 5) is assumed to either expose the in-memory `GenotypeFile` or to be safely re-composable from V1's already-public domain classes without modification — pending the Section 20 verification.

# 20. Final Open Questions

These are the only remaining items requiring resolution before or during early implementation. Everything else in this document is final.

1. **Confirm the GRCh37 forward-strand reference/alternate alleles for the three TAS2R38 SNPs (`rs713598`, `rs1726866`, `rs10246939`) against position-matched dbSNP/ClinVar records**, the same way Section 9.3 resolved lactase and earwax. This is the one trait-interpretation question this review did not close.
2. **Read the actual `ProfileFileUseCase` implementation** to confirm whether it exposes the in-memory `GenotypeFile`/`DataRow` collection post-run, or whether `GenotypeIndex` needs a thin re-composition adapter using V1's already-public ingestion/detection/parsing classes (Section 5). Architecture-blocking; do this first.
3. **Source and verify the exact Walsh et al. 2011 published IrisPlex coefficient table within the 60-minute timebox** (Section 8.1) — resolved either way by the fallback design, but the attempt should still happen first, since Option A is scientifically stronger if it succeeds.

---

*This document contains no code and is the final source of truth for Phase 2. It supersedes both prior blueprints. Implementation should begin immediately following resolution of the three items in Section 20.*
