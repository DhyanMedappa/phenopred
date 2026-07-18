# phenopred/cli/main.py
"""Command-line entry point for the PhenoPred Stage 1 pipeline.

Per Architecture v1 Section 4/5, cli/main.py "parses command-line
arguments (input file path(s), optional config path); invokes the
composition root and one ProfileFileUseCase per input file; translates
domain/infra exceptions into process exit codes and user-facing
messages. Contains no business logic."

This module does exactly that and nothing more:
    - parses a single file-path argument,
    - obtains a fully wired ProfileFileUseCase from
      application/composition_root.py (never constructing any domain,
      detection, or infrastructure component itself),
    - calls ProfileFileUseCase.execute() exactly once,
    - catches PhenoPredIngestionError (the existing, unmodified
      exception hierarchy already owned by ProfileFileUseCase's own
      exception-ownership contract) and translates it into a
      user-facing message and a non-zero process exit status,
    - prints a minimal, purely descriptive execution summary from the
      values ProfileFileUseCase.execute() already returned -- never
      constructing, formatting, or serializing a report.

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

    try:
        result = use_case.execute(args.file_path)
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
    """Parse the single required file-path argument.

    No configuration flags are accepted yet: build_profile_file_use_case()
    is called with its own temporary defaults (application/
    composition_root.py), since a real ConfigProvider is explicitly out
    of scope for this task.
    """
    parser = argparse.ArgumentParser(
        prog="phenopred",
        description=(
            "Run the PhenoPred Stage 1 pipeline (ingestion, structural "
            "detection, column identity resolution, row parsing, and "
            "quality checks FR-5..FR-9) against a single genotype file."
        ),
    )
    parser.add_argument(
        "file_path",
        type=Path,
        help="Path to the input genotype file to profile.",
    )
    return parser.parse_args(argv)


def _print_summary(file_path: Path, result: dict) -> None:
    """Print a minimal, purely descriptive execution summary.

    Only reports what ProfileFileUseCase.execute() already returned:
    which file was processed, and how many/which quality checks
    produced a Finding. This never assembles, formats, or persists a
    report -- ReportBuilder/ReportSerializer remain unimplemented and
    out of scope.
    """
    findings = result["findings"]
    print(f"Processed: {file_path}")
    print(f"Findings produced: {len(findings)}")
    if findings:
        print(f"Quality checks completed: {', '.join(sorted(findings))}")


if __name__ == "__main__":
    raise SystemExit(main())
