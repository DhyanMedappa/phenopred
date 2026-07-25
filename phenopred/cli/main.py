# phenopred/cli/main.py
"""Command-line entry point for the PhenoPred Stage 1 pipeline.

Per Architecture v1 Section 4/5, cli/main.py "parses command-line
arguments (input file path(s), optional config path); invokes the
composition root and one ProfileFileUseCase per input file; translates
domain/infra exceptions into process exit codes and user-facing
messages. Contains no business logic."

This module does exactly that and nothing more:
    - parses a file-path argument and an optional output-path argument,
    - obtains a fully wired ProfileFileUseCase from
      application/composition_root.py (never constructing any domain,
      detection, or infrastructure component itself),
    - calls ProfileFileUseCase.execute() exactly once, forwarding the
      resolved output path so the report-persistence step the
      composition root already wires in (a JsonReportSerializer, per
      Architecture v1 Section 9/10, AD-3) is actually reached -- without
      this, the composition root's ReportSerializer wiring would be
      unreachable from the only current entry point, leaving the
      pipeline's own final documented step (Section 6, step 10:
      "report_writer ... serializes and persists the ProfilingReport to
      a per-file output artifact") never executed,
    - catches PhenoPredIngestionError (the existing, unmodified
      exception hierarchy already owned by ProfileFileUseCase's own
      exception-ownership contract) and translates it into a
      user-facing message and a non-zero process exit status,
    - prints a minimal, purely descriptive execution summary from the
      values ProfileFileUseCase.execute() already returned -- never
      constructing, formatting, or serializing a report itself; only
      the already-injected JsonReportSerializer (reached via
      ProfileFileUseCase) ever does that.

    Resolving *where* to write a report when `--output` is omitted is a
    plain path-string computation (input file's own stem plus a fixed
    suffix, in the current working directory), not a business rule --
    it carries no interpretation of file content and involves no
    domain, detection, or infrastructure component construction, so it
    remains within this module's own "argument parsing" responsibility
    rather than crossing into the composition root's or
    ProfileFileUseCase's territory.

Dependency direction: this module depends on
application/composition_root.py and application/profile_file_use_case.py
only. It never imports a domain or infrastructure module directly,
mirroring composition_root.py's own stated purpose of isolating wiring
so "no other module needs to know concrete classes."
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from phenopred.application.composition_root import build_profile_file_use_case
from phenopred.domain.errors import PhenoPredIngestionError


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the Stage 1 pipeline for one file, and print
    a minimal execution summary.

    Args:
        argv: Command-line arguments, excluding the program name.
            Defaults to `sys.argv[1:]` when None (the standard argparse
            convention), so this function is directly callable from
            tests without touching real process arguments.

    Returns:
        A process exit status: 0 on successful execution, 1 if the
        file could not be ingested (any PhenoPredIngestionError
        subclass), 2 for any other, unexpected failure.
    """
    args = _parse_args(argv)

    use_case = build_profile_file_use_case()

    output_path = args.output or _default_output_path(args.file_path)

    try:
        result = use_case.execute(args.file_path, output_path=output_path)
    except PhenoPredIngestionError as exc:
        print(f"Failed to process '{args.file_path}': {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 -- CLI boundary: report, don't crash
        print(
            f"Unexpected error while processing '{args.file_path}': {exc}",
            file=sys.stderr,
        )
        return 2

    _print_summary(args.file_path, result)
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the required file-path argument and the optional
    report-output-path argument.

    No pipeline *behavior* configuration flags are accepted yet:
    build_profile_file_use_case() is still called with its own
    temporary defaults (application/composition_root.py), since a real
    ConfigProvider is explicitly out of scope for this task. `--output`
    is not a pipeline-behavior flag -- it names only where this run's
    report artifact is written, mirroring output_location's own
    Section-11 framing as a per-run destination, not a detection or
    quality-check parameter.
    """
    parser = argparse.ArgumentParser(
        prog="phenopred",
        description=(
            "Run the PhenoPred Stage 1 pipeline (ingestion, structural "
            "detection, column identity resolution, row parsing, "
            "quality checks FR-5..FR-9, genomic profiling FR-10..FR-12, "
            "and report building/persistence) against a single genotype "
            "file."
        ),
    )
    parser.add_argument(
        "file_path",
        type=Path,
        help="Path to the input genotype file to profile.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help=(
            "Destination path for the serialized report artifact. "
            "Defaults to '<file_path stem>.profilingreport.json' in "
            "the current working directory."
        ),
    )
    return parser.parse_args(argv)


def _default_output_path(file_path: Path) -> Path:
    """Compute the default report-artifact destination when `--output`
    is not supplied: the input file's own stem plus a fixed suffix, in
    the current working directory.

    A plain path-string computation only -- no file is read, written,
    or interpreted here; the file's content plays no role in the
    result.
    """
    return Path.cwd() / f"{file_path.stem}.profilingreport.json"


def _print_summary(file_path: Path, result: dict) -> None:
    """Print a minimal, purely descriptive execution summary.

    Only reports what ProfileFileUseCase.execute() already returned:
    which file was processed, how many/which quality checks produced a
    Finding, and -- when persistence was attempted -- where the report
    artifact was written. This never assembles, formats, or serializes
    a report itself; `report_artifact_path` is exactly what the
    injected JsonReportSerializer (via ProfileFileUseCase) already
    returned.
    """
    findings = result["findings"]
    print(f"Processed: {file_path}")
    print(f"Findings produced: {len(findings)}")
    if findings:
        print(f"Quality checks completed: {', '.join(sorted(findings))}")
    report_artifact_path = result.get("report_artifact_path")
    if report_artifact_path is not None:
        print(f"Report written to: {report_artifact_path}")


if __name__ == "__main__":
    raise SystemExit(main())