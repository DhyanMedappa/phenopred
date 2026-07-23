# tests/unit/domain/ingestion/test_row_parser.py
"""Unit tests for RowParser (FR-4).

Mirrors the testing approach established by test_delimiter_detector.py,
test_column_identity_resolver.py, and test_header_resolver.py: small,
synthetic, in-memory fixtures only, no file I/O, exercising exactly the
structural properties named by the frozen RowParser design
specification.

Scope discipline: this suite verifies RowParser and its interaction with
DataRow/Delimiter only. It does not test, anticipate, or stub any other
module (MalformedRowCheck, MissingValueScanner, HeaderResolver's header-
exclusion hand-off, etc.). Per the frozen specification's own
instruction, no test is written for the manually-constructed-invalid-
Delimiter case, since the specification explicitly leaves that behavior
undefined. RowParser has no dataset-specific knowledge of any kind; test
names and fixtures avoid implying awareness of any particular vendor
file layout.
"""

from __future__ import annotations

import ast

from phenopred.domain.entities import DataRow
from phenopred.domain.ingestion import row_parser as row_parser_module
from phenopred.domain.ingestion.row_parser import RowParser
from phenopred.domain.value_objects import Delimiter


# ---------------------------------------------------------------------------
# 1. Normal behavior: single-line parsing
# ---------------------------------------------------------------------------


def test_single_line_multiple_fields() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["rs1\t1\t100\tA\tG"]
    result = RowParser().parse(lines, delimiter)
    assert result == (DataRow(line_index=0, fields=("rs1", "1", "100", "A", "G")),)


# ---------------------------------------------------------------------------
# 2. Normal behavior: multiple-line parsing and order preservation
# ---------------------------------------------------------------------------


def test_multiple_lines_produce_multiple_data_rows_in_order() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["rs1\t1\t100", "rs2\t1\t200", "rs3\t2\t300"]
    result = RowParser().parse(lines, delimiter)
    assert result == (
        DataRow(line_index=0, fields=("rs1", "1", "100")),
        DataRow(line_index=1, fields=("rs2", "1", "200")),
        DataRow(line_index=2, fields=("rs3", "2", "300")),
    )


def test_data_row_order_matches_input_line_order() -> None:
    delimiter = Delimiter(character=",", detection_method="character_frequency_analysis")
    lines = ["z,1", "a,2", "m,3"]
    result = RowParser().parse(lines, delimiter)
    assert [row.fields[0] for row in result] == ["z", "a", "m"]


# ---------------------------------------------------------------------------
# 3. Normal behavior: supported delimiters
# ---------------------------------------------------------------------------


def test_tab_delimiter() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    result = RowParser().parse(["a\tb\tc"], delimiter)
    assert result[0].fields == ("a", "b", "c")


def test_comma_delimiter() -> None:
    delimiter = Delimiter(character=",", detection_method="character_frequency_analysis")
    result = RowParser().parse(["a,b,c"], delimiter)
    assert result[0].fields == ("a", "b", "c")


def test_semicolon_delimiter() -> None:
    delimiter = Delimiter(character=";", detection_method="character_frequency_analysis")
    result = RowParser().parse(["a;b;c"], delimiter)
    assert result[0].fields == ("a", "b", "c")


def test_pipe_delimiter() -> None:
    delimiter = Delimiter(character="|", detection_method="character_frequency_analysis")
    result = RowParser().parse(["a|b|c"], delimiter)
    assert result[0].fields == ("a", "b", "c")


# ---------------------------------------------------------------------------
# 4. Normal behavior: tuple return type and generic field-count parsing
# ---------------------------------------------------------------------------


def test_return_type_is_tuple_of_data_row() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    result = RowParser().parse(["a\tb"], delimiter)
    assert isinstance(result, tuple)
    assert all(isinstance(row, DataRow) for row in result)


def test_five_field_lines_parse_to_five_element_fields_tuples() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["rs1\t1\t100\tA\tG", "rs2\t1\t200\tC\tT"]
    result = RowParser().parse(lines, delimiter)
    assert all(len(row.fields) == 5 for row in result)


def test_four_field_lines_parse_to_four_element_fields_tuples() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["rs1\t1\t100\tAG", "rs2\t1\t200\t--"]
    result = RowParser().parse(lines, delimiter)
    assert all(len(row.fields) == 4 for row in result)


# ---------------------------------------------------------------------------
# 5. FR-4 preservation rules: no trimming, no casting, no normalization
# ---------------------------------------------------------------------------


def test_no_trimming_of_field_whitespace() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    result = RowParser().parse([" rs1 \t 1 \t100"], delimiter)
    assert result[0].fields == (" rs1 ", " 1 ", "100")


def test_no_casting_of_numeric_looking_fields() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    result = RowParser().parse(["rs1\t1\t100"], delimiter)
    assert all(isinstance(field, str) for field in result[0].fields)
    assert result[0].fields[1] == "1"
    assert result[0].fields[2] == "100"


def test_no_case_or_unicode_normalization() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    result = RowParser().parse(["MixedCase\tÜNÏCÖDE\tcafé"], delimiter)
    assert result[0].fields == ("MixedCase", "ÜNÏCÖDE", "café")


def test_no_interpretation_of_missing_value_tokens() -> None:
    # RowParser must not recognize or transform documented missing-value
    # tokens; they pass through as ordinary, unmodified field strings.
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    result = RowParser().parse(["rs1\t1\t100\t0\t--"], delimiter)
    assert result[0].fields == ("rs1", "1", "100", "0", "--")


def test_delimiter_character_inside_field_content_is_split_naively() -> None:
    # No quoting/escaping convention exists in this pipeline; a delimiter
    # occurrence is always a field boundary, even if it happens to fall
    # inside what a human might consider one logical value.
    delimiter = Delimiter(character=",", detection_method="character_frequency_analysis")
    result = RowParser().parse(['"quoted,value",b'], delimiter)
    assert result[0].fields == ('"quoted', 'value"', "b")


# ---------------------------------------------------------------------------
# 6. Scope boundaries: no judgment leaks into RowParser
# ---------------------------------------------------------------------------


def test_no_malformed_row_judgement_short_row() -> None:
    # A row with fewer fields than its neighbors is not flagged, rejected,
    # or padded -- MalformedRowCheck's exclusive future responsibility.
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["rs1\t1\t100\tA\tG", "rs2\t1\t200"]
    result = RowParser().parse(lines, delimiter)
    assert len(result[0].fields) == 5
    assert len(result[1].fields) == 3


def test_no_malformed_row_judgement_long_row() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["rs1\t1\t100", "rs2\t1\t200\tA\tG\textra"]
    result = RowParser().parse(lines, delimiter)
    assert len(result[0].fields) == 3
    assert len(result[1].fields) == 6


def test_no_missing_value_detection_or_flagging() -> None:
    # RowParser produces no Finding, no flag, no side channel about
    # missing-value tokens -- only the raw DataRow tuple.
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    result = RowParser().parse(["rs1\t1\t100\t--\t--"], delimiter)
    assert isinstance(result, tuple)
    assert not hasattr(result, "findings")
    assert not hasattr(result[0], "is_missing")


def test_no_column_count_validation_across_file() -> None:
    # Even a file where every row has a different field count parses
    # successfully with no exception and no aggregate validation.
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["a", "a\tb", "a\tb\tc", "a\tb\tc\td"]
    result = RowParser().parse(lines, delimiter)
    assert [len(row.fields) for row in result] == [1, 2, 3, 4]


def test_no_header_or_comment_handling() -> None:
    # RowParser has no concept of a header line or a comment line; a line
    # that would have been recognized as a header/comment upstream is
    # parsed identically to any other line if it reaches RowParser.
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["rsid\tchromosome\tposition", "#some comment\tvalue"]
    result = RowParser().parse(lines, delimiter)
    assert result[0].fields == ("rsid", "chromosome", "position")
    assert result[1].fields == ("#some comment", "value")


# ---------------------------------------------------------------------------
# 7. Dependency boundaries (structural, AST-based)
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


def test_row_parser_never_imports_ingestion_errors() -> None:
    imported = _imported_module_names(row_parser_module)
    assert not any("errors" in name for name in imported)


def test_row_parser_never_imports_upstream_or_sibling_modules() -> None:
    imported = _imported_module_names(row_parser_module)
    forbidden_substrings = [
        "raw_file_loader",
        "encoding_detector",
        "raw_line_splitter",
        "delimiter_detector",
        "header_resolver",
        "column_identity_resolver",
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


def test_row_parser_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(row_parser_module)
    domain_imports = [name for name in imported if name.startswith("phenopred.")]
    assert set(domain_imports) == {
        "phenopred.domain.entities",
        "phenopred.domain.value_objects",
    }


# ---------------------------------------------------------------------------
# 8. Edge cases explicitly allowed by the specification
# ---------------------------------------------------------------------------


def test_empty_lines_sequence_returns_empty_result() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    result = RowParser().parse([], delimiter)
    assert result == ()


def test_line_with_no_delimiter_occurrences_yields_single_field() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    result = RowParser().parse(["no_delimiter_here"], delimiter)
    assert result[0].fields == ("no_delimiter_here",)


def test_line_with_extra_delimiter_occurrences_yields_extra_fields() -> None:
    delimiter = Delimiter(character=",", detection_method="character_frequency_analysis")
    result = RowParser().parse(["a,b,c,d,e,f"], delimiter)
    assert result[0].fields == ("a", "b", "c", "d", "e", "f")


def test_empty_string_line_yields_single_empty_field() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    result = RowParser().parse([""], delimiter)
    assert result[0].fields == ("",)


# ---------------------------------------------------------------------------
# 9. Additional required properties: line_index assignment, determinism,
#    non-mutation of caller input
# ---------------------------------------------------------------------------


def test_line_index_assigned_positionally_from_zero() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["a", "b", "c"]
    result = RowParser().parse(lines, delimiter)
    assert [row.line_index for row in result] == [0, 1, 2]


def test_deterministic_repeated_calls() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["rs1\t1\t100", "rs2\t1\t200"]
    parser = RowParser()
    first = parser.parse(lines, delimiter)
    second = parser.parse(lines, delimiter)
    assert first == second


def test_input_lines_sequence_is_not_mutated() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    lines = ["a\tb", "c\td"]
    original_copy = list(lines)
    RowParser().parse(lines, delimiter)
    assert lines == original_copy


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()