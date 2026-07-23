# tests/unit/domain/detection/test_delimiter_detector.py
"""Unit tests for DelimiterDetector (FR-2).

Mirrors the testing approach established by
tests/unit/domain/detection/test_header_resolver.py,
test_column_identity_resolver.py, test_chromosome_label_profiler.py,
test_genotype_layout_classifier.py, test_indel_haploid_classifier.py,
test_duplicate_rsid_check.py, test_duplicate_header_check.py, and
test_missing_value_scanner.py: small, synthetic, in-memory fixtures
only, no file I/O, exercising exactly the structural properties named
by FR-2, the Detector[T] Protocol (interfaces.py, which explicitly
names DelimiterDetector as one of the three implementers that
validated that Protocol's shape), Delimiter's frozen contract
(value_objects.py), and NFR-3/NFR-5 as documented directly in
delimiter_detector.py's own docstrings.

Scope discipline: this suite verifies DelimiterDetector only. It does
not test, anticipate, or stub HeaderResolver, ColumnIdentityResolver,
RowParser, any QualityCheck, or any GenomicProfiler. It does not lock
private helper methods, internal scoring implementation, Python
str.count() behaviour, exception message text, or exception
inheritance hierarchy -- only observable behavior and explicitly
documented architectural guarantees are tested.
"""

from __future__ import annotations

import ast

from phenopred.domain.detection import (
    delimiter_detector as delimiter_detector_module,
)
from phenopred.domain.detection.delimiter_detector import (
    DelimiterDetector,
    DelimiterNotDetectedError,
)
from phenopred.domain.interfaces import Detector
from phenopred.domain.value_objects import Delimiter


# ---------------------------------------------------------------------------
# 1. Normal behaviour: each candidate delimiter detected correctly
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 2. Selection criteria: count-based primary selection and fixed-order
#    tie-break (explicitly documented: "Fixed candidate set, in fixed
#    preference order... used solely as a deterministic tie-break...
#    it never overrides a clear, higher-scoring result.")
# ---------------------------------------------------------------------------


def test_higher_consistent_count_wins_even_when_later_in_fixed_preference_order() -> None:
    # Semicolon (later in fixed order: tab, comma, semicolon, pipe) is
    # consistently present 3 times per line; tab (earlier in fixed
    # order) is consistently present only 1 time per line. The higher,
    # equally-consistent count must win regardless of candidate order.
    lines = ["a\tb;c;d;e", "f\tg;h;i;j"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == ";"


def test_tie_break_uses_fixed_preference_order() -> None:
    # Comma and semicolon both occur exactly once per line -> tie.
    # Preference order (tab > comma > semicolon > pipe) must select comma.
    lines = ["a,b;c", "d,e;f", "g,h;i"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == ","


# ---------------------------------------------------------------------------
# 3. Consistency requirement
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 4. Fixed candidate set (explicitly documented as not configurable)
# ---------------------------------------------------------------------------


def test_whitespace_not_treated_as_delimiter() -> None:
    # Space-separated content must not be detected as delimited by
    # space; space is not part of the fixed candidate set, so no
    # candidate qualifies and detection fails.
    lines = ["rs1 1 100 A G", "rs2 1 200 C T"]
    try:
        DelimiterDetector(sample_size=10).detect(lines)
        raise AssertionError("expected DelimiterNotDetectedError")
    except DelimiterNotDetectedError:
        pass


# ---------------------------------------------------------------------------
# 5. Boundary cases: empty and sample-bounded input
# ---------------------------------------------------------------------------


def test_empty_lines_sequence_raises() -> None:
    try:
        DelimiterDetector(sample_size=10).detect([])
        raise AssertionError("expected DelimiterNotDetectedError")
    except DelimiterNotDetectedError:
        pass


def test_blank_lines_in_sample_are_ignored_not_altered() -> None:
    # A blank line contributes no delimiter evidence and is excluded
    # from consistency scoring, but no line's content is stripped or
    # altered.
    lines = ["rs1\t1\t100", "", "rs2\t1\t200"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == "\t"


def test_sample_size_bounds_lines_examined() -> None:
    # Only the first 2 lines (tab-consistent) are examined; a later,
    # comma-only line outside the sample must not affect the result.
    lines = ["rs1\t1\t100", "rs2\t1\t200", "rs3,1,300", "rs4,1,400"]
    result = DelimiterDetector(sample_size=2).detect(lines)
    assert result.character == "\t"


# ---------------------------------------------------------------------------
# 6. No content alteration or normalization (explicitly documented:
#    "Field values within each line are never altered, trimmed, or
#    otherwise normalized by this method.")
# ---------------------------------------------------------------------------


def test_no_content_alteration_trimming_or_normalization_of_line_values() -> None:
    # Quoted fields, a backslash-adjacent character, and leading/
    # trailing whitespace padding around fields are all left entirely
    # unaltered; tab remains the consistently detected delimiter
    # throughout, since none of this surrounding content is stripped,
    # trimmed, or otherwise normalized before counting.
    lines = [' "rs1" \t 1 \t100\\x', ' "rs2" \t 1 \t200\\y']
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert result.character == "\t"


# ---------------------------------------------------------------------------
# 7. Determinism
# ---------------------------------------------------------------------------


def test_deterministic_repeated_calls() -> None:
    lines = ["rs1\t1\t100", "rs2\t1\t200"]
    detector = DelimiterDetector(sample_size=10)
    first = detector.detect(lines)
    second = detector.detect(lines)
    assert first == second


# ---------------------------------------------------------------------------
# 8. Output contract: Delimiter shape
# ---------------------------------------------------------------------------


def test_return_type_is_delimiter() -> None:
    lines = ["rs1\t1\t100", "rs2\t1\t200"]
    result = DelimiterDetector(sample_size=10).detect(lines)
    assert isinstance(result, Delimiter)


# ---------------------------------------------------------------------------
# 9. Protocol compliance
# ---------------------------------------------------------------------------


def test_delimiter_detector_satisfies_detector_protocol() -> None:
    assert isinstance(DelimiterDetector(sample_size=10), Detector)


# ---------------------------------------------------------------------------
# 10. Dependency boundaries (structural, AST-based)
# ---------------------------------------------------------------------------


def _imported_module_names(module) -> list[str]:
    with open(module.__file__, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_delimiter_detector_never_imports_errors_module() -> None:
    imported = _imported_module_names(delimiter_detector_module)
    assert not any("errors" in name for name in imported)


def test_delimiter_detector_never_imports_upstream_or_sibling_modules() -> None:
    imported = _imported_module_names(delimiter_detector_module)
    forbidden_substrings = [
        "raw_file_loader",
        "encoding_detector",
        "raw_line_splitter",
        "header_resolver",
        "column_identity_resolver",
        "row_parser",
        "quality_checks",
        "malformed_row_check",
        "duplicate_header_check",
        "missing_value_scanner",
        "duplicate_rsid_check",
        "duplicate_chr_pos_check",
        "chromosome_label_profiler",
        "genotype_layout_classifier",
        "indel_haploid_classifier",
        "report_builder",
    ]
    for name in imported:
        for forbidden in forbidden_substrings:
            assert forbidden not in name, f"forbidden import found: {name}"


def test_delimiter_detector_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(delimiter_detector_module)
    domain_imports = [name for name in imported if name.startswith("phenopred.")]
    assert set(domain_imports) == {"phenopred.domain.value_objects"}


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()