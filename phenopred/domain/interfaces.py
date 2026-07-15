# phenopred/domain/interfaces.py
"""Protocol/ABC definitions decoupling the orchestrator from concrete
detectors, checks, profilers, and serializers (Architecture v1, Section
4 / Section 10).

Detector[T] and a provisional QualityCheck port are defined here.
GenomicProfiler, ReportSerializer, and ConfigProvider belong to modules
that have not yet been designed or approved; adding them ahead of that
work would exceed the scope explicitly defined for the current module
(Stage 1 Engineering Review, Section 7 / Section 16).

QualityCheck's shape below is PROVISIONAL. It is validated against
exactly one implementer (DuplicateHeaderCheck) at this stage. Per the
Detector[T] precedent -- which was only treated as settled after three
independent implementers (EncodingDetector, DelimiterDetector,
HeaderResolver) confirmed its shape -- QualityCheck's method signature
must not be treated as finally frozen until at least one further
QualityCheck implementation (e.g. MalformedRowCheck, which has different
context needs) has validated it. This mirrors Architecture v1 Section 17's
named risk of premature abstraction from too few observed cases.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class Detector(Protocol[T]):
    """A port for components that inspect raw input and produce a single
    detected value-object (e.g. EncodingProfile, Delimiter, HeaderInfo).

    Kept minimal and single-method (data-in/data-out) per the Stage 1
    Engineering Review's instruction to limit the cost of an abstraction
    later proving to be a poor fit (composition over inheritance; no
    behavior beyond the one method).
    """

    def detect(self, data: object) -> T:
        """Inspect `data` and return the corresponding detected value.

        Concrete implementations narrow the input type (e.g. `bytes` for
        an encoding detector, a sequence of lines for a delimiter or
        header detector) in their own signatures; this Protocol only
        fixes the single-method, data-in/data-out shape.
        """
        ...


@runtime_checkable
class QualityCheck(Protocol):
    """A port for components that inspect parsed data rows (plus any
    per-check context) and produce exactly one Finding (Architecture v1,
    Section 10: "Given DataRows (+ context), produce exactly one
    Finding").

    PROVISIONAL: kept minimal and single-method (data-in/data-out), like
    Detector[T], but its exact signature -- in particular, the generic,
    untyped `context` parameter -- has not yet been validated against a
    second implementer with different context needs (e.g. a check
    requiring no context at all, or one requiring column-identity
    context). This shape must be revisited once at least one further
    QualityCheck is designed, rather than treated as final now.
    """

    def check(self, data_rows: object, context: object = None) -> object:
        """Inspect `data_rows` (and optional `context`) and return the
        corresponding Finding.

        Concrete implementations narrow the input and context types
        (e.g. `Sequence[DataRow]` and `HeaderInfo` for a duplicate-header
        check) in their own signatures, and narrow the return type to
        `Finding`; this Protocol only fixes the single-method,
        data-in/data-out shape, mirroring Detector[T].
        """
        ...