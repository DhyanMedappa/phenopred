# tests/unit/domain/detection/test_delimiter_detector.py
"""Unit tests for DelimiterDetector (FR-2).

Mirrors the testing approach established by
tests/unit/domain/detection/test_encoding_detector.py: small, synthetic,
in-memory fixtures only, no file I/O, exercising the structural properties
named by the SRS and the Stage 2 design review (candidate set, tie-break
ordering, consistency requirement, sample-size injection, and the
detector-local failure exception).
"""

from __future__ import annotations

import dataclasses

from phenopred.domain.detection.delimiter_detector import (
    DelimiterDetector,
    DelimiterNotDetectedError,
)
from phenopred.domain.value_objects import Delimiter


def test_detects_tab_delimiter() -> None:
    lines = ["rs1\t1\t100\tA\tG", "rs2\t1\t200\tC\tT", "rs3\t2\t300\tA\tA"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == "\t"
    assert result.detection_method == "character_frequency_analysis"


def test_detects_comma_delimiter() -> None:
    lines = ["rs1,1,100,A,G", "rs2,1,200,C,T", "rs3,2,300,A,A"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == ","


def test_detects_semicolon_delimiter() -> None:
    lines = ["rs1;1;100;A", "rs2;1;200;C", "rs3;2;300;A"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == ";"


def test_detects_pipe_delimiter() -> None:
    lines = ["rs1|1|100|A", "rs2|1|200|C", "rs3|2|300|A"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == "|"


def test_prefers_higher_field_count_over_lower() -> None:
    # Every line has 1 comma but 4 tabs; tab is stronger structural
    # evidence (more consistent fields), so tab must win even though
    # comma is not tab's preference-order superior.
    lines = ["a\tb\tc\td,e", "f\tg\th\ti,j"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == "\t"


def test_tie_break_uses_fixed_preference_order() -> None:
    # Comma and semicolon both occur exactly once per line -> tie.
    # Preference order (tab > comma > semicolon > pipe) must select comma.
    lines = ["a,b;c", "d,e;f", "g,h;i"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == ","


def test_inconsistent_counts_are_not_detected() -> None:
    # Comma count varies per line (1, 2, 1) -> not consistent -> no
    # candidate qualifies -> exception.
    lines = ["a,b", "c,d,e", "f,g"]
    try:
        DelimiterDetector(sample_size=10).detect(lines)
        raise AssertionError("expected DelimiterNotDetectedError")
    except DelimiterNotDetectedError:
        pass


def test_no_candidate_present_raises() -> None:
    lines = ["abcdefg", "hijklmnop", "qrstuv"]
    try:
        DelimiterDetector(sample_size=10).detect(lines)
        raise AssertionError("expected DelimiterNotDetectedError")
    except DelimiterNotDetectedError:
        pass


def test_empty_lines_sequence_raises() -> None:
    try:
        DelimiterDetector(sample_size=10).detect([])
        raise AssertionError("expected DelimiterNotDetectedError")
    except DelimiterNotDetectedError:
        pass


def test_blank_lines_in_sample_are_ignored_not_altered() -> None:
    # A blank line contributes no delimiter evidence and is excluded from
    # consistency scoring, but no line's *content* is stripped/altered.
    lines = ["rs1\t1\t100", "", "rs2\t1\t200"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == "\t"


def test_sample_size_bounds_lines_examined() -> None:
    # Only the first 2 lines (tab-consistent) are examined; a later,
    # comma-only line outside the sample must not affect the result.
    lines = ["rs1\t1\t100", "rs2\t1\t200", "rs3,1,300", "rs4,1,400"]
    result = DelimiterDetector(sample_size=2).detect(lines)
    assert result.character == "\t"


def test_deterministic_repeated_calls() -> None:
    lines = ["rs1\t1\t100", "rs2\t1\t200"]
    detector = DelimiterDetector(sample_size=10)
    first = detector.detect(lines)
    second = detector.detect(lines)
    assert first == second


def test_no_quote_handling() -> None:
    # Quote characters are treated as ordinary literal characters; a
    # quoted comma-delimited field is not specially interpreted, and tab
    # remains the consistent, winning candidate here.
    lines = ['"rs1"\t1\t100', '"rs2"\t1\t200']
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == "\t"


def test_no_escape_sequence_handling() -> None:
    # Backslash escaping is not interpreted. The comma after the backslash
    # is counted as a normal comma character. Because comma counts differ
    # across lines, detection must fail rather than treating "\\," as escaped.
    lines = ["a\\,b,c", "d\\,e,f,g"]

    try:
        DelimiterDetector(sample_size=10).detect(lines)
        raise AssertionError("expected DelimiterNotDetectedError")
    except DelimiterNotDetectedError:
        pass


def test_whitespace_not_treated_as_delimiter() -> None:
    # Space-separated content must not be detected as delimited by space;
    # since no candidate is present/consistent, detection fails.
    lines = ["rs1 1 100 A G", "rs2 1 200 C T"]
    try:
        DelimiterDetector(sample_size=10).detect(lines)
        raise AssertionError("expected DelimiterNotDetectedError")
    except DelimiterNotDetectedError:
        pass


def test_no_whitespace_stripping_of_fields() -> None:
    # Leading/trailing whitespace around fields must survive untouched in
    # terms of what informs detection; tab count is unaffected by padding.
    lines = [" rs1 \t 1 \t100", " rs2 \t 1 \t200"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == "\t"


def test_delimiter_value_object_shape() -> None:
    result = Delimiter(character="\t", detection_method="character_frequency_analysis")
    assert result.character == "\t"
    assert result.detection_method == "character_frequency_analysis"


def test_delimiter_is_immutable() -> None:
    result = Delimiter(character="\t", detection_method="character_frequency_analysis")
    try:
        result.character = ","  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def test_delimiter_rejects_new_attribute() -> None:
    result = Delimiter(character="\t", detection_method="character_frequency_analysis")
    try:
        result.confidence = 0.9  # type: ignore[attr-defined]
        raise AssertionError("expected AttributeError or TypeError")
    except (AttributeError, TypeError):
        pass


def test_delimiter_detector_never_imports_ingestion_errors() -> None:
    # Structural guard, not a behavioral test: confirms this module has no
    # *import* dependency on phenopred.domain.errors, per the approved
    # Stage 2 exception-ownership resolution. (The module's own docstrings
    # mention PhenoPredIngestionError in prose, to explain the boundary --
    # that is not an import and is intentionally not flagged here.)
    import ast

    import phenopred.domain.detection.delimiter_detector as module

    with open(module.__file__, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any("errors" in name for name in imported_modules)


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()
