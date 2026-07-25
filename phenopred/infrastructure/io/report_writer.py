# phenopred/infrastructure/io/report_writer.py
"""Infrastructure adapter serializing a ProfilingReport to a persisted
JSON artifact (Architecture v1, Section 3/4/9/10/11; AD-3).

JsonReportSerializer is the Version 1 concrete implementation of the
domain-level ReportSerializer port (phenopred/domain/interfaces.py). Per
Architecture v1's "Layered Architecture" table (Section 3) and AD-3
("ProfilingReport is a plain domain object; persistence format is
behind a ReportSerializer interface, not fixed to a concrete format in
the domain layer"):

- This module lives in the infrastructure layer and is the only
  component in the pipeline permitted to write a report artifact to
  disk, mirroring RawFileLoader's identical "only this component
  touches this side of the filesystem" discipline for reads (Section
  9, "infrastructure/io/report_writer.py -- Implements the
  ReportSerializer interface; converts a ProfilingReport into a
  concrete artifact ... and writes it to a per-file output location").
- It performs no aggregation, no selection, and no interpretation of
  ProfilingReport's contents -- every field is already fully computed
  by ReportBuilder (and, transitively, by every check/profiler/
  detector that fed it) before this module ever sees it. This module's
  only responsibility is converting an already-assembled report object
  into a JSON-compatible structure and writing it to a caller-supplied
  path, then returning a reference to what was written.
- No business logic, quality-check logic, or genomic-notation logic of
  any kind is performed here.
- output_location (Section 11) remains a per-run configuration concern
  resolved by the caller (the composition root / cli/main.py); this
  class never hard-codes, defaults, or guesses a destination -- every
  call to `serialize()` is given an explicit `output_path`.
- NFR-3 (determinism/reproducibility): given the same report object,
  `serialize()` always produces byte-identical output. Every field
  already carries a fixed, deterministic order (Finding/Profile
  ordering was already resolved by ReportBuilder itself, per its own
  ordering contract); this module introduces no additional ordering
  decision of its own (no sorting by dict key, no reliance on any
  non-deterministic iteration such as set iteration), and uses a fixed
  JSON encoding (UTF-8, fixed indentation, insertion-order preserved,
  no locale-dependent formatting).
"""

from __future__ import annotations

import logging
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import json

logger = logging.getLogger(__name__)


class JsonReportSerializer:
    """Serializes a ProfilingReport to a JSON file (Version 1's sole
    ReportSerializer implementation, per AD-3).

    Stateless: holds no constructor-injected configuration and no
    mutable state, mirroring OpenQuestionRegistry's identical
    "no per-run configuration value" pattern. Every value this class
    needs -- the report to serialize, and where to write it -- is
    supplied per call to `serialize()`, never read from global state,
    environment variables, or a hard-coded default path (AD-10).
    """

    def serialize(self, report: Any, output_path: Path | str) -> Path:
        """Convert `report` into a JSON-compatible structure and write
        it to `output_path`.

        This method performs no computation over `report`'s content
        beyond structural conversion (dataclass -> dict, tuple -> list,
        Path -> str) -- every value written is exactly what `report`
        already carries, in the order it already carries it.

        Args:
            report: The already-assembled report to persist -- e.g. a
                ProfilingReport, the output of ReportBuilder.build().
                Any nested dataclass, tuple, list, mapping, or plain
                JSON-primitive scalar field is supported; this method
                does not require `report` to be exactly a
                ProfilingReport instance, only that it (and everything
                it references) is built from dataclasses, tuples,
                mappings, and JSON-primitive scalars -- true of every
                value object already defined in
                phenopred/domain/value_objects.py and
                phenopred/domain/entities.py.
            output_path: The destination file path to write the JSON
                artifact to, supplied by the caller. Parent directories
                are created if they do not already exist. The source
                file itself is never touched by this method -- only
                `output_path` is written to (FR-14/NFR-2's "never
                modify the source" discipline extends here to "never
                write anywhere but the given destination").

        Returns:
            The `output_path` this method wrote to, as a resolved
            `pathlib.Path` -- a reference to the produced artifact, per
            the ReportSerializer interface contract ("persist it as an
            artifact and return a reference to it").
        """
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        jsonable_report = self._to_jsonable(report)

        with destination.open("w", encoding="utf-8") as handle:
            json.dump(
                jsonable_report,
                handle,
                indent=2,
                ensure_ascii=True,
                sort_keys=False,
            )
            handle.write("\n")

        logger.info("Wrote report artifact: path=%s", destination)

        return destination

    def _to_jsonable(self, value: Any) -> Any:
        """Recursively convert `value` into a JSON-compatible structure.

        Dataclass instances become dicts keyed by their own declared
        field order (`dataclasses.fields()`), which is fixed and
        deterministic per class definition -- never by attribute
        introspection order or `__dict__` iteration. Tuples and lists
        become JSON arrays, preserving their existing element order
        unaltered. Mappings become JSON objects, preserving their
        existing iteration order unaltered -- never re-sorted, since
        every mapping this module is ever handed by already-computed
        pipeline data is already ordered deterministically by its own
        producer (e.g. ReportBuilder's own `sorted(..., key=...)`
        ordering of findings/profiles). `Path` values become their
        string form. Every other value (str, int, float, bool, None)
        is returned unchanged, since these are already JSON-primitive.

        This method performs no filtering, renaming, or reordering of
        its own -- it introduces no ordering or content decision beyond
        what `value` already carries.
        """
        if is_dataclass(value) and not isinstance(value, type):
            return {
                field.name: self._to_jsonable(getattr(value, field.name))
                for field in fields(value)
            }
        if isinstance(value, Path):
            return value.as_posix()
        if isinstance(value, (tuple, list)):
            return [self._to_jsonable(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): self._to_jsonable(item) for key, item in value.items()
            }
        return value