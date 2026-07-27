# phenopred_phase2/traits/domain/interfaces.py
"""Phase 2 Trait Contract Layer -- shared model protocol.

Per the frozen "Trait Contract Layer -- Frozen Architecture Specification
v1", this module defines the single contract every future TraitModel
implementation is built against:

- A single method, data-in/data-out, mirroring Architecture V1's own
  QualityCheck/GenomicProfiler protocol shape (AD-2, AD-8) exactly --
  no shared base-class behavior, composition over inheritance.
- The input is restricted to this file's already-resolved GenotypeCall
  data for the specific RSID(s) a given model requires -- never a raw
  GenotypeIndex, never a raw ProfilingReport, never file I/O of any
  kind. A concrete TraitModel is expected to consult SNP_REGISTRY
  directly, by static import, for the fixed biological reference data
  it needs -- mirroring the SNP Registry's own frozen design, which is
  deliberately not runtime-configurable or injected.
- No exception is ever raised by a conforming predict() implementation
  for any external, per-file data condition (a missing required RSID, a
  NO_CALL, or an INDEL/UNRECOGNIZED call where a SNP genotype was
  expected). Each such condition is represented as
  TraitPrediction(status=PredictionStatus.INSUFFICIENT_DATA), never an
  exception, mirroring GenotypeIndex's identical "represent as data,
  never raise" discipline.

This module defines no concrete TraitModel implementation, no
TraitEngine orchestration logic, and no TraitCard/reporting logic --
all of these remain separate, later components built against this
contract.

See "Trait Contract Layer -- Frozen Architecture Specification v1" for
the complete, authoritative contract this module implements. No V1
file, GenotypeIndex file, or SNP Registry file is read, imported beyond
its public entities, or modified by this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from phenopred_phase2.traits.domain.entities import GenotypeCall, TraitPrediction


class TraitModel(Protocol):
    """The shared contract every concrete trait model implements.

    A conforming implementation is permanently bound to one specific
    trait's specific, known RSID(s) -- it does not receive its required
    RSIDs as an argument, since that would introduce a second,
    potentially-diverging source of truth alongside its own hardcoded
    interpretation logic.
    """

    def predict(self, genotype_calls: Mapping[str, GenotypeCall]) -> TraitPrediction:
        """Produce one TraitPrediction from this file's observed
        genotype call(s).

        Args:
            genotype_calls: This file's already-resolved GenotypeCall(s)
                for this model's required RSID(s), keyed by RSID. An
                RSID this model requires but that was not observed in
                this file is simply absent as a key -- mirroring
                GenotypeIndex.get()'s own None-for-absent convention,
                projected onto a mapping. No GenotypeIndex, DataRow, or
                other V1/GenotypeIndex object is passed here.

        Returns:
            Exactly one TraitPrediction. Never raises for any external,
            per-file data condition -- returns a TraitPrediction with
            status=PredictionStatus.INSUFFICIENT_DATA when the required
            data is absent or not interpretable as this trait's
            expected genotype shape.
        """
        ...