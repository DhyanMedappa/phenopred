# phenopred/cli/main.py
"""Command-line entry point for the PhenoPred Stage 1 pipeline.

Per Architecture v1 Section 4/5, cli/main.py "parses command-line
arguments (input file path(s), optional config path); invokes the
composition root and one ProfileFileUseCase per input file; translates
domain/infra exceptions into process exit codes and user-facing
messages. Contains no business logic."

This module does exactly that and nothing more:
    - parses a file-path argument, an optional output-path argument, and
      an optional `--config` path argument (Section 5's "optional config
      path", now implemented -- see below),
    - calls application/composition_root.py's configure_logging(),
      build_profile_file_use_case(), and resolve_output_location(),
      each given the same `--config` value, exactly once each, before
      any pipeline execution -- this module never imports ConfigLoader
      or LoggerSetup directly (both remain known only to
      composition_root.py, per Section 3's layer table restricting
      this module to depending on the Application layer only); it
      catches ConfigLoadError (re-exported by composition_root.py for
      exactly this reason) and translates it into a user-facing message
      and exit code 3, rather than letting a raw traceback escape,
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

    Resolving *where* to write a report when `--output` is omitted is
    still a plain path-string computation (input file's own stem plus a
    fixed suffix), now optionally rooted at `output_location` (Section
    11) when a config file sets it, rather than always the current
    working directory -- it carries no interpretation of file content
    and involves no domain, detection, or infrastructure component
    construction, so it remains within this module's own "argument
    parsing" responsibility rather than crossing into the composition
    root's or ProfileFileUseCase's territory.

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

from phenopred.application.composition_root import (
    ConfigLoadError,
    build_profile_file_use_case,
    configure_logging,
    resolve_output_location,
)
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
        subclass), 2 for any other, unexpected failure, 3 if the
        `--config` configuration file could not be loaded or contained
        an invalid value.
    """
    args = _parse_args(argv)

    try:
        configure_logging(config_path=args.config)
        use_case = build_profile_file_use_case(config_path=args.config)
        output_location = resolve_output_location(config_path=args.config)
    except ConfigLoadError as exc:
        print(f"Failed to load configuration '{args.config}': {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001 -- CLI boundary: report, don't crash
        # Mirrors this function's own second try/except block below: a
        # specific, typed exception first (ConfigLoadError, above), then
        # a broad safety net so an invalid *value* inside an otherwise
        # loadable --config file (e.g. an unrecognized logging_level,
        # caught here as ValueError from LoggerSetup, or a non-string
        # value, caught here as AttributeError) is still translated into
        # a clean message and exit code, never an unhandled traceback --
        # Architecture v1 Section 5's own cli/main.py responsibility.
        print(f"Invalid configuration '{args.config}': {exc}", file=sys.stderr)
        return 3

    output_path = args.output or _default_output_path(args.file_path, output_location)

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
    report-output-path and configuration-file-path arguments.

    `--config` (Architecture v1 Section 5's "optional config path") is
    passed through, unread and unopened by this module, to
    composition_root.py's configure_logging(),
    build_profile_file_use_case(), and resolve_output_location() --
    this module never reads the file itself or constructs a ConfigLoader
    or LoggerSetup. `--output` is not a pipeline-behavior flag -- it
    names only where this run's report artifact is written, mirroring
    output_location's own Section-11 framing as a per-run destination,
    not a detection or quality-check parameter; when omitted, the
    default output path now optionally honors `output_location` from a
    supplied `--config` file (see `_default_output_path()`).
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
            "Defaults to '<file_path stem>.profilingreport.json', in "
            "the directory named by --config's own output_location "
            "value if supplied and set, otherwise the current working "
            "directory."
        ),
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        help=(
            "Path to an optional JSON configuration file (Architecture "
            "v1 Section 11), supplying comment_prefix, header_keyword, "
            "output_location, logging_level, delimiter_sample_size, "
            "and/or raw_loader_sample_size. Defaults to None (no "
            "configuration file; every value falls back to its own "
            "documented default)."
        ),
    )
    return parser.parse_args(argv)


def _default_output_path(file_path: Path, output_location: str | None) -> Path:
    """Compute the default report-artifact destination when `--output`
    is not supplied: the input file's own stem plus a fixed suffix, in
    `output_location` (Section 11) if a `--config` file supplied one,
    otherwise the current working directory (this function's original,
    unchanged behavior when `output_location` is None -- e.g. no
    `--config` given at all, exactly every existing test's case).

    A plain path-string computation only -- no file is read, written,
    or interpreted here; the file's content plays no role in the
    result, and `output_location` is used exactly as ConfigLoader
    already resolved it, never re-read or re-interpreted by this
    function.

    Args:
        file_path: The input genotype file whose stem names the
            default artifact.
        output_location: The already-resolved `RunConfig.output_location`
            value (via composition_root.resolve_output_location()), or
            None when no `--config` file was given or it did not set
            this key.
    """
    base_directory = Path(output_location) if output_location is not None else Path.cwd()
    return base_directory / f"{file_path.stem}.profilingreport.json"


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