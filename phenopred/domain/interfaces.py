# phenopred/domain/interfaces.py
"""Protocol/ABC definitions decoupling the orchestrator from concrete
detectors, checks, profilers, and serializers (Architecture v1, Section
4 / Section 10).

Only the Detector[T] port is defined here for now. QualityCheck,
GenomicProfiler, ReportSerializer, and ConfigProvider belong to modules
that have not yet been designed or approved; adding them ahead of that
work would exceed the scope explicitly defined for the current module
(Stage 1 Engineering Review, Section 7 / Section 16).
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