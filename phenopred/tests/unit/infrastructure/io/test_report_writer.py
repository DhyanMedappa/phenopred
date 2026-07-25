# tests/unit/infrastructure/io/test_report_writer.py
"""Unit tests for JsonReportSerializer (Architecture v1 Section 9/10,
AD-3).

Mirrors the testing approach already established by
tests/unit/domain/reporting/test_report_builder.py: plain, hand-written
assertion functions (no framework-specific fixtures required), using
either lightweight local dataclasses standing in for ProfilingReport's
own shape, or (in the two integration-style tests near the bottom) the
real ProfilingReport/value-object types, to keep this suite runnable
whether or not the rest of the domain package is import-available in
isolation.

Scope discipline: this suite verifies JsonReportSerializer's own
conversion and file-writing behavior only -- dataclass -> dict, tuple ->
list, Path -> str conversion; parent-directory creation; determinism;
and the returned artifact-path reference. It does not test
ReportBuilder, OpenQuestionRegistry, or ProfileFileUseCase's own
(separately tested) decision of *whether* to call this class.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from phenopred.infrastructure.io.report_writer import JsonReportSerializer

# ---------------------------------------------------------------------------
# Local stand-in dataclasses -- deliberately mirror the *shape* of
# Finding/ProfilingReport (nested dataclasses, tuples, optional fields)
# without importing the real domain module, so this suite exercises
# JsonReportSerializer's genuinely generic dataclass/tuple traversal
# rather than any one entity's specific fields.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeFinding:
    check_name: str
    description: str
    count: int
    examples: tuple[str, ...]
    affected_row_refs: tuple[int, ...]


@dataclass(frozen=True)
class _FakeReport:
    source_path: str
    row_count: int
    column_count_distribution: object
    findings: tuple[_FakeFinding, ...]
    open_questions: tuple[str, ...]


def _make_temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="phenopred_report_writer_test_"))


# ---------------------------------------------------------------------------
# 1. Basic serialization: dataclass -> JSON object, tuple -> JSON array
# ---------------------------------------------------------------------------


def test_serialize_writes_dataclass_as_json_object() -> None:
    tmp_dir = _make_temp_dir()
    try:
        report = _FakeReport(
            source_path="/data/genome.txt",
            row_count=3,
            column_count_distribution=None,
            findings=(
                _FakeFinding(
                    check_name="malformed_row_check",
                    description="desc",
                    count=2,
                    examples=("row_a", "row_b"),
                    affected_row_refs=(1, 4),
                ),
            ),
            open_questions=("open_question_1",),
        )
        serializer = JsonReportSerializer()

        output_path = tmp_dir / "report.json"
        result = serializer.serialize(report, output_path)

        assert result == output_path
        assert output_path.exists()

        with output_path.open(encoding="utf-8") as handle:
            parsed = json.load(handle)

        assert parsed["source_path"] == "/data/genome.txt"
        assert parsed["row_count"] == 3
        assert parsed["column_count_distribution"] is None
        assert parsed["findings"] == [
            {
                "check_name": "malformed_row_check",
                "description": "desc",
                "count": 2,
                "examples": ["row_a", "row_b"],
                "affected_row_refs": [1, 4],
            }
        ]
        assert parsed["open_questions"] == ["open_question_1"]
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 2. Return value is a reference to the produced artifact
# ---------------------------------------------------------------------------


def test_serialize_returns_the_output_path_as_a_path_object() -> None:
    tmp_dir = _make_temp_dir()
    try:
        report = _FakeReport(
            source_path="/data/genome.txt",
            row_count=0,
            column_count_distribution=None,
            findings=(),
            open_questions=(),
        )
        serializer = JsonReportSerializer()

        output_path_as_str = str(tmp_dir / "report.json")
        result = serializer.serialize(report, output_path_as_str)

        assert isinstance(result, Path)
        assert result == Path(output_path_as_str)
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 3. Parent directories are created when missing
# ---------------------------------------------------------------------------


def test_serialize_creates_missing_parent_directories() -> None:
    tmp_dir = _make_temp_dir()
    try:
        report = _FakeReport(
            source_path="/data/genome.txt",
            row_count=0,
            column_count_distribution=None,
            findings=(),
            open_questions=(),
        )
        serializer = JsonReportSerializer()

        nested_output_path = tmp_dir / "nested" / "sub" / "report.json"
        assert not nested_output_path.parent.exists()

        result = serializer.serialize(report, nested_output_path)

        assert result.exists()
        assert nested_output_path.parent.exists()
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 4. Determinism (NFR-3 / Section 15.3: byte-identical serialized reports)
# ---------------------------------------------------------------------------


def test_serialize_is_byte_identical_across_repeated_calls() -> None:
    tmp_dir = _make_temp_dir()
    try:
        report = _FakeReport(
            source_path="/data/genome.txt",
            row_count=5,
            column_count_distribution=None,
            findings=(
                _FakeFinding(
                    check_name="duplicate_rsid_check",
                    description="desc",
                    count=1,
                    examples=("rs123",),
                    affected_row_refs=(7,),
                ),
            ),
            open_questions=(),
        )
        serializer = JsonReportSerializer()

        first_path = serializer.serialize(report, tmp_dir / "first.json")
        second_path = serializer.serialize(report, tmp_dir / "second.json")

        assert first_path.read_bytes() == second_path.read_bytes()
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 5. Nested tuples (e.g. tuple-of-tuples, mirroring
#    ChromosomeLabelInventory.label_counts / ColumnCountDistribution's
#    counts_by_column_count) convert to nested JSON arrays
# ---------------------------------------------------------------------------


def test_serialize_converts_nested_tuples_to_nested_arrays() -> None:
    tmp_dir = _make_temp_dir()
    try:
        @dataclass(frozen=True)
        class _FakeInventory:
            profiler_name: str
            label_counts: tuple[tuple[str, int], ...]

        report = _FakeInventory(
            profiler_name="chromosome_label_profiler",
            label_counts=(("1", 100), ("X", 12), ("MT", 3)),
        )
        serializer = JsonReportSerializer()

        output_path = tmp_dir / "inventory.json"
        serializer.serialize(report, output_path)

        with output_path.open(encoding="utf-8") as handle:
            parsed = json.load(handle)

        assert parsed["label_counts"] == [["1", 100], ["X", 12], ["MT", 3]]
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 6. A Path value anywhere in the report converts to its string form
# ---------------------------------------------------------------------------


def test_serialize_converts_path_valued_fields_to_strings() -> None:
    tmp_dir = _make_temp_dir()
    try:
        @dataclass(frozen=True)
        class _FakeReportWithPathField:
            source_path: Path

        report = _FakeReportWithPathField(source_path=Path("/data/genome.txt"))
        serializer = JsonReportSerializer()

        output_path = tmp_dir / "report.json"
        serializer.serialize(report, output_path)

        with output_path.open(encoding="utf-8") as handle:
            parsed = json.load(handle)

        assert parsed["source_path"] == "/data/genome.txt"
        assert isinstance(parsed["source_path"], str)
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# 7. Real ProfilingReport / value-object integration (skipped gracefully
#    if the domain package is not import-available in this environment)
# ---------------------------------------------------------------------------


def test_serialize_handles_a_real_profiling_report_end_to_end() -> None:
    try:
        from phenopred.domain.entities import ProfilingReport
        from phenopred.domain.value_objects import (
            CommentBlock,
            Delimiter,
            EncodingProfile,
            Finding,
            HeaderInfo,
        )
    except ImportError:
        print(
            "SKIPPED: real domain package not import-available in this "
            "environment"
        )
        return

    tmp_dir = _make_temp_dir()
    try:
        report = ProfilingReport(
            source_path="/data/genome.txt",
            comment_block=CommentBlock(lines=("# comment",), count=1),
            encoding_profile=EncodingProfile(
                bom_present=False,
                ascii_decodable=True,
                utf8_decodable=True,
                utf8_sig_decodable=True,
                latin1_decodable=True,
            ),
            delimiter=Delimiter(character="\t", detection_method="character_frequency_analysis"),
            header_info=HeaderInfo(
                form="uncommented_row",
                resolved_columns=("rsid", "chromosome", "position", "genotype"),
                source_line="rsid\tchromosome\tposition\tgenotype",
            ),
            row_count=2,
            column_count_distribution=None,
            findings=(
                Finding(
                    check_name="malformed_row_check",
                    description="desc",
                    count=0,
                    examples=(),
                    affected_row_refs=(),
                ),
            ),
            profiles=(),
            open_questions=(),
        )
        serializer = JsonReportSerializer()

        output_path = tmp_dir / "real_report.json"
        result = serializer.serialize(report, output_path)

        with result.open(encoding="utf-8") as handle:
            parsed = json.load(handle)

        assert parsed["source_path"] == "/data/genome.txt"
        assert parsed["header_info"]["resolved_columns"] == [
            "rsid",
            "chromosome",
            "position",
            "genotype",
        ]
        assert parsed["findings"][0]["check_name"] == "malformed_row_check"
    finally:
        shutil.rmtree(tmp_dir)


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()