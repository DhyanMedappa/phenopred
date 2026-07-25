# tests/unit/integration/test_cli_end_to_end.py
"""CLI-boundary end-to-end integration tests for the PhenoPred Stage 1
pipeline (Architecture v1 Step 4).

Scope discipline -- this suite is deliberately narrow and does not
duplicate any existing suite:

    - tests/unit/integration/test_profile_pipeline.py already proves the
      real, composition-root-assembled pipeline (every concrete
      detector, quality check, and genomic profiler) works correctly
      end to end, by calling build_profile_file_use_case() and
      ProfileFileUseCase.execute() directly. This suite does not repeat
      that coverage.
    - tests/unit/integration/test_profile_file_use_case.py unit-tests
      ProfileFileUseCase's own orchestration logic against fakes.
    - tests/unit/integration/test_report_writer.py unit-tests
      JsonReportSerializer's dataclass -> JSON conversion in isolation.

None of the three ever invokes phenopred/cli/main.py. This suite is the
only place that does: it answers, concretely, "can a user run PhenoPred
from the command line and receive a valid, persisted profiling report?"
(Architecture v1 Section 5's cli/main.py responsibility; Section 6 step
10; Section 9/10, AD-3).

Design choices:

    - The CLI is invoked via `subprocess.run([sys.executable, "-m",
      "phenopred.cli.main", ...])` -- a real, external process
      invocation, exactly mirroring what a user types at a shell
      (`python -m phenopred.cli.main <file> --output <path>`). This is
      deliberate: calling build_profile_file_use_case() or
      ProfileFileUseCase.execute() directly (as the other suites do)
      would not exercise argparse, main.py's own exception-to-exit-code
      translation, or the `if __name__ == "__main__": raise
      SystemExit(main())` module guard -- all of which are part of the
      actual command-line boundary this suite exists to validate.
    - Every generated report artifact is written under pytest's
      `tmp_path`, via an explicit `--output` argument. main.py's own
      `_default_output_path` fallback (cwd-relative) is intentionally
      never exercised here, so this suite never writes into the
      repository regardless of where pytest is invoked from; `cwd` is
      also pinned to `tmp_path` for the subprocess as a second,
      redundant safeguard against that.
    - Reuses the same two real datasets, at the same
      tests/unit/integration/data/raw/ location, that
      test_profile_pipeline.py already uses -- no new test data is
      introduced.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

from phenopred.domain.entities import ProfilingReport

DATA_DIR = Path(__file__).resolve().parent / "data" / "raw"

ANCESTRYDNA = DATA_DIR / "AncestryDNA.txt"
TWENTYTHREEANDME = DATA_DIR / "anonymous_genome_v5_build37.txt"

_EXPECTED_QUALITY_CHECK_NAMES = {
    "malformed_row_check",
    "duplicate_header_check",
    "missing_value_scanner",
    "duplicate_rsid_check",
    "duplicate_chr_pos_check",
}

_EXPECTED_GENOMIC_PROFILER_NAMES = {
    "chromosome_label_profiler",
    "genotype_layout_classifier",
    "indel_haploid_classifier",
}

# Derived directly from the real ProfilingReport dataclass -- never a
# hand-copied literal set -- so this suite's structural assertion always
# reflects whatever fields ReportBuilder/JsonReportSerializer actually
# produce, rather than a guess that could silently drift out of sync.
_EXPECTED_REPORT_TOP_LEVEL_KEYS = {field.name for field in fields(ProfilingReport)}


def _run_cli(input_path: Path, output_path: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the real CLI exactly as a user would from a shell.

    A subprocess is used deliberately, not a direct call into the
    application layer, so this test genuinely proves the external
    command-line boundary -- argparse parsing, composition-root wiring,
    full pipeline execution, and process exit-code translation in
    main.py -- all work together.
    """
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "phenopred.cli.main",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _assert_well_formed_report(payload: dict) -> None:
    """Structural assertions shared by both datasets' generated JSON
    artifact. Confirms the artifact's shape matches ProfilingReport's
    own field set exactly (via JsonReportSerializer's dataclass -> dict
    conversion), and that each Finding/Profile carries the fields the
    rest of the codebase (report_writer.py, report_builder.py) already
    documents.
    """
    assert set(payload.keys()) == _EXPECTED_REPORT_TOP_LEVEL_KEYS

    assert isinstance(payload["source_path"], str)
    assert isinstance(payload["row_count"], int)
    assert payload["row_count"] > 0

    assert isinstance(payload["findings"], list)
    assert {finding["check_name"] for finding in payload["findings"]} == (
        _EXPECTED_QUALITY_CHECK_NAMES
    )
    for finding in payload["findings"]:
        assert {
            "check_name",
            "description",
            "count",
            "examples",
            "affected_row_refs",
        } <= set(finding.keys())

    assert isinstance(payload["profiles"], list)
    assert {profile["profiler_name"] for profile in payload["profiles"]} == (
        _EXPECTED_GENOMIC_PROFILER_NAMES
    )

    assert isinstance(payload["open_questions"], list)
    assert len(payload["open_questions"]) > 0


# ---------------------------------------------------------------------------
# 1. AncestryDNA.txt through the real CLI
# ---------------------------------------------------------------------------


def test_cli_processes_ancestrydna_and_persists_valid_report(tmp_path: Path) -> None:
    output_path = tmp_path / "ancestrydna.profilingreport.json"

    result = _run_cli(ANCESTRYDNA, output_path, cwd=tmp_path)

    assert result.returncode == 0, (
        f"CLI exited non-zero.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert output_path.exists()
    assert f"Report written to: {output_path}" in result.stdout

    with output_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    _assert_well_formed_report(payload)
    assert Path(payload["source_path"]) == ANCESTRYDNA.resolve()
    assert payload["header_info"]["form"] == "uncommented_row"
    assert payload["header_info"]["resolved_columns"] == [
        "rsid",
        "chromosome",
        "position",
        "allele1",
        "allele2",
    ]


# ---------------------------------------------------------------------------
# 2. anonymous_genome_v5_build37.txt through the real CLI
# ---------------------------------------------------------------------------


def test_cli_processes_23andme_and_persists_valid_report(tmp_path: Path) -> None:
    output_path = tmp_path / "anonymous_genome_v5_build37.profilingreport.json"

    result = _run_cli(TWENTYTHREEANDME, output_path, cwd=tmp_path)

    assert result.returncode == 0, (
        f"CLI exited non-zero.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert output_path.exists()
    assert f"Report written to: {output_path}" in result.stdout

    with output_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    _assert_well_formed_report(payload)
    assert Path(payload["source_path"]) == TWENTYTHREEANDME.resolve()
    assert payload["header_info"]["form"] == "commented_only"
    assert payload["header_info"]["resolved_columns"] == [
        "rsid",
        "chromosome",
        "position",
        "genotype",
    ]


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            test(Path(tmp))
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()
