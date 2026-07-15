# tests/unit/domain/detection/test_header_resolver.py
"""Unit tests for HeaderResolver (FR-3) and HeaderInfo.

Mirrors the testing approach established by
tests/unit/domain/detection/test_delimiter_detector.py and
tests/unit/domain/ingestion/test_raw_line_splitter.py: small, synthetic,
in-memory fixtures only, no file I/O, exercising the structural properties
named by the SRS and the frozen HeaderResolver architecture decisions
(uncommented-row precedence, commented-only fallback, absent as a valid
outcome, exact-token matching only, HeaderInfo immutability, and
determinism).
"""

from __future__ import annotations

import dataclasses

from phenopred.domain.detection.header_resolver import HeaderResolver
from phenopred.domain.value_objects import CommentBlock, Delimiter, HeaderInfo


# ---------------------------------------------------------------------------
# Normal cases
# ---------------------------------------------------------------------------


def test_uncommented_header_detected() -> None:
    comment_block = CommentBlock(lines=(), count=0)
    data_lines = ["rsid\tchromosome\tposition\tallele1\tallele2", "rs1\t1\t100\tA\tG"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "uncommented_row"
    assert result.resolved_columns == (
        "rsid",
        "chromosome",
        "position",
        "allele1",
        "allele2",
    )
    assert result.source_line == "rsid\tchromosome\tposition\tallele1\tallele2"


def test_commented_only_header_detected() -> None:
    # The comment prefix is its own token (separated from "rsid" by the
    # delimiter itself), so "rsid" appears as an exact token after
    # splitting and matches via the base exact-token rule alone -- the
    # marker-stripping fallback (see test_commented_only_header_real_
    # dataset_b_format below) is not needed for this fixture. This test
    # exists as a regression check that the base rule continues to match
    # independently of the fallback.
    comment_block = CommentBlock(
        lines=("#some metadata", "#\trsid\tchromosome\tposition\tgenotype"),
        count=2,
    )
    data_lines = ["rs1\t1\t100\tAA"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == ("#", "rsid", "chromosome", "position", "genotype")
    assert result.source_line == "#\trsid\tchromosome\tposition\tgenotype"


def test_absent_header_detected() -> None:
    comment_block = CommentBlock(lines=("#some metadata",), count=1)
    data_lines = ["rs1\t1\t100\tAA"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "absent"
    assert result.resolved_columns is None
    assert result.source_line is None


# ---------------------------------------------------------------------------
# Comment-marker amendment: real vendor comment-header formats
# ---------------------------------------------------------------------------


def test_commented_only_header_real_dataset_b_format() -> None:
    # Real evidenced Dataset B (23andMe-style) comment-header format: the
    # comment marker is followed by a space, not the field delimiter, so
    # the first token after splitting is "# rsid", not "rsid". This must
    # now match via the marker-stripping, match-only interpretation.
    comment_block = CommentBlock(
        lines=("#some metadata", "# rsid\tchromosome\tposition\tgenotype"),
        count=2,
    )
    data_lines = ["rs1\t1\t100\tAA"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    # Stored output remains the original, unmodified split -- the marker
    # and its following space remain attached to the first entry exactly
    # as they appeared in the file. Nothing is cleaned or stripped in the
    # returned value.
    assert result.resolved_columns == ("# rsid", "chromosome", "position", "genotype")
    assert result.source_line == "# rsid\tchromosome\tposition\tgenotype"


def test_commented_only_header_delimiter_separated_format_still_matches() -> None:
    # Pre-existing delimiter-separated marker format must continue to
    # match via the unmodified base rule, unaffected by the amendment.
    comment_block = CommentBlock(
        lines=("#\trsid\tchromosome\tposition\tgenotype",),
        count=1,
    )
    data_lines = ["rs1\t1\t100\tAA"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == ("#", "rsid", "chromosome", "position", "genotype")
    assert result.source_line == "#\trsid\tchromosome\tposition\tgenotype"


def test_marker_with_no_following_whitespace_still_matches() -> None:
    # Marker glued directly to the keyword with no separating whitespace
    # at all -- the whitespace-stripping step is optional (zero or more
    # whitespace characters), not mandatory.
    comment_block = CommentBlock(lines=("#rsid\tchromosome",), count=1)
    data_lines = ["rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == ("#rsid", "chromosome")
    assert result.source_line == "#rsid\tchromosome"


def test_dataset_a_uncommented_header_regression() -> None:
    # Explicit regression check for the AncestryDNA-style uncommented
    # header row, confirming the amendment leaves this path untouched.
    comment_block = CommentBlock(lines=(), count=0)
    data_lines = ["rsid\tchromosome\tposition\tallele1\tallele2"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "uncommented_row"
    assert result.resolved_columns == (
        "rsid",
        "chromosome",
        "position",
        "allele1",
        "allele2",
    )
    assert result.source_line == "rsid\tchromosome\tposition\tallele1\tallele2"


def test_false_positive_prose_comment_not_detected_as_header() -> None:
    # No delimiter present in the line, so it is a single token. The
    # marker-stripped remainder is a full sentence, not an exact match
    # for header_keyword -- must not be detected as a header.
    comment_block = CommentBlock(
        lines=("# this file contains rsid information",), count=1
    )
    data_lines = ["rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "absent"
    assert result.resolved_columns is None
    assert result.source_line is None


def test_false_positive_embedded_keyword_not_detected_as_header() -> None:
    # "notarealrsid" is one unbroken alphanumeric word ending in "rsid";
    # marker-stripping only removes a leading non-alphanumeric run and
    # cannot isolate a keyword embedded inside a contiguous word.
    comment_block = CommentBlock(lines=("#notarealrsid\tfoo",), count=1)
    data_lines = ["rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "absent"
    assert result.resolved_columns is None
    assert result.source_line is None


def test_case_sensitivity_preserved_under_marker_stripping() -> None:
    # The marker-stripping fallback must not introduce case-folding.
    comment_block = CommentBlock(lines=("# RSID\tchromosome",), count=1)
    data_lines = ["rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "absent"
    assert result.resolved_columns is None
    assert result.source_line is None


def test_multi_character_marker_still_matches() -> None:
    # Marker-stripping is generic (any leading non-alphanumeric,
    # non-whitespace run), not hard-coded to a single '#' character --
    # HeaderResolver has no access to the configured comment_prefix value.
    comment_block = CommentBlock(lines=(";; rsid\tchromosome",), count=1)
    data_lines = ["rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == (";; rsid", "chromosome")
    assert result.source_line == ";; rsid\tchromosome"


def test_input_immutability_under_marker_stripped_match() -> None:
    # CommentBlock, data_lines, and the returned source_line/
    # resolved_columns must all reflect original, unmodified content --
    # the marker-stripping interpretation must never leak into stored
    # output or mutate caller-supplied input.
    comment_block = CommentBlock(
        lines=("# rsid\tchromosome\tposition\tgenotype",), count=1
    )
    original_comment_block = CommentBlock(
        lines=("# rsid\tchromosome\tposition\tgenotype",), count=1
    )
    data_lines = ["rs1\t1\t100\tAA"]
    original_data_lines = list(data_lines)
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert comment_block == original_comment_block
    assert data_lines == original_data_lines
    assert result.source_line == "# rsid\tchromosome\tposition\tgenotype"
    assert result.resolved_columns == ("# rsid", "chromosome", "position", "genotype")


# ---------------------------------------------------------------------------
# Boundary cases
# ---------------------------------------------------------------------------


def test_empty_data_lines_falls_through_to_comment_check() -> None:
    comment_block = CommentBlock(lines=("#\trsid\tchromosome",), count=1)
    data_lines: list[str] = []
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == ("#", "rsid", "chromosome")
    assert result.source_line == "#\trsid\tchromosome"


def test_empty_comment_block_and_no_header_yields_absent() -> None:
    comment_block = CommentBlock(lines=(), count=0)
    data_lines = ["rs1\t1\t100\tAA"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "absent"
    assert result.resolved_columns is None
    assert result.source_line is None


def test_header_keyword_present_in_both_locations_data_line_wins() -> None:
    # header_keyword appears both in the first data line and in a comment
    # line; uncommented_row detection must take precedence.
    comment_block = CommentBlock(lines=("#\trsid\tchromosome",), count=1)
    data_lines = ["rsid\tchromosome\tposition", "rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "uncommented_row"
    assert result.resolved_columns == ("rsid", "chromosome", "position")
    assert result.source_line == "rsid\tchromosome\tposition"


def test_multiple_comment_lines_first_match_in_order_wins() -> None:
    comment_block = CommentBlock(
        lines=("#unrelated line", "#\trsid\tchromosome", "#\trsid\tposition"),
        count=3,
    )
    data_lines = ["rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == ("#", "rsid", "chromosome")
    assert result.source_line == "#\trsid\tchromosome"


def test_exact_token_matching_only_no_substring_match() -> None:
    # "rsid" is a substring of "rsident", not an exact token, so this must
    # not be classified as an uncommented header; falls through to absent
    # since no comment line matches either.
    comment_block = CommentBlock(lines=(), count=0)
    data_lines = ["rsident\tchromosome\tposition"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "absent"
    assert result.resolved_columns is None
    assert result.source_line is None


def test_no_trimming_or_normalization_of_tokens() -> None:
    # Padded whitespace around the keyword token must not match; exact
    # token equality only, no trimming applied to either side.
    comment_block = CommentBlock(lines=(), count=0)
    data_lines = [" rsid \tchromosome\tposition"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "absent"


def test_case_sensitive_matching() -> None:
    # "RSID" must not match the injected keyword "rsid"; no case-folding.
    comment_block = CommentBlock(lines=(), count=0)
    data_lines = ["RSID\tchromosome\tposition"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "absent"


def test_configurable_header_keyword() -> None:
    comment_block = CommentBlock(lines=(), count=0)
    data_lines = ["identifier\tchrom\tpos"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="identifier").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "uncommented_row"
    assert result.resolved_columns == ("identifier", "chrom", "pos")


# ---------------------------------------------------------------------------
# Contract behavior
# ---------------------------------------------------------------------------


def test_header_info_is_immutable_reassignment_raises() -> None:
    info = HeaderInfo(form="absent", resolved_columns=None, source_line=None)
    try:
        info.form = "uncommented_row"  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def test_header_info_rejects_new_attribute() -> None:
    info = HeaderInfo(form="absent", resolved_columns=None, source_line=None)
    try:
        info.confidence = 0.9  # type: ignore[attr-defined]
        raise AssertionError("expected AttributeError or TypeError")
    except (AttributeError, TypeError):
        pass


def test_no_mutation_of_input_data_lines_or_comment_block() -> None:
    comment_block = CommentBlock(lines=("#rsid\tchromosome",), count=1)
    data_lines = ["rs1\t1\t100"]
    original_data_lines = list(data_lines)
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    HeaderResolver(header_keyword="rsid").detect(comment_block, data_lines, delimiter)

    assert data_lines == original_data_lines
    assert comment_block == CommentBlock(lines=("#rsid\tchromosome",), count=1)


def test_deterministic_repeated_calls() -> None:
    comment_block = CommentBlock(lines=(), count=0)
    data_lines = ["rsid\tchromosome\tposition", "rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    resolver = HeaderResolver(header_keyword="rsid")

    first = resolver.detect(comment_block, data_lines, delimiter)
    second = resolver.detect(comment_block, data_lines, delimiter)

    assert first == second


def test_detect_never_raises_across_varied_inputs() -> None:
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")
    resolver = HeaderResolver(header_keyword="rsid")

    cases = [
        (CommentBlock(lines=(), count=0), []),
        (CommentBlock(lines=(), count=0), [""]),
        (CommentBlock(lines=("",), count=1), []),
        (CommentBlock(lines=(), count=0), ["rs1\t1\t100"]),
        (CommentBlock(lines=("#rsid\tchrom",), count=1), ["rs1\t1\t100"]),
    ]

    for comment_block, data_lines in cases:
        result = resolver.detect(comment_block, data_lines, delimiter)  # must not raise
        assert isinstance(result, HeaderInfo)


# ---------------------------------------------------------------------------
# Dependency guard
# ---------------------------------------------------------------------------


def test_header_resolver_never_imports_forbidden_modules() -> None:
    # Structural guard, not a behavioral test: confirms this module has no
    # *import* dependency on phenopred.domain.errors, any infrastructure
    # module, or any sibling detector/downstream module, per the approved
    # Stage 2 dependency-ownership resolution.
    import ast

    import phenopred.domain.detection.header_resolver as module

    with open(module.__file__, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden_substrings = (
        "errors",
        "infrastructure",
        "raw_file_loader",
        "raw_line_splitter",
        "delimiter_detector",
        "encoding_detector",
        "row_parser",
        "quality_checks",
        "genomic_profiling",
    )
    for name in imported_modules:
        assert not any(forbidden in name for forbidden in forbidden_substrings), (
            f"forbidden import found: {name}"
        )


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()
