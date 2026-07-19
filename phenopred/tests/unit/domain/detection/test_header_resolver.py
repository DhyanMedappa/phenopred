# tests/unit/domain/detection/test_header_resolver.py
"""Unit tests for HeaderResolver (FR-3), HeaderInfo, and ADR-8.

Mirrors the testing approach established by
tests/unit/domain/quality_checks/test_duplicate_header_check.py,
test_missing_value_scanner.py, and test_duplicate_rsid_check.py: small,
synthetic, in-memory fixtures only, no file I/O, exercising exactly the
structural properties named by the SRS, the frozen HeaderResolver
architecture decisions (uncommented-row precedence, commented-only
fallback, absent as a valid outcome, exact-token matching only,
HeaderInfo immutability, and determinism), and ADR-8 ("HeaderResolver
Must Produce Marker-Stripped Semantic Column Names for the
commented_only Header Form").

Contract note: the only comment-marker-to-keyword separation convention
evidenced by the real datasets and named by header_resolver.py's own
docstring is "marker + space + content" (e.g. "# rsid\t..."). A
marker-plus-delimiter convention (e.g. "#\trsid\t...") is not part of
the supported PhenoPred contract -- it is not evidenced by either real
dataset and is explicitly named in header_resolver.py's own docstring as
the pattern real vendor files do *not* use. Fixtures in this suite that
exercise other unevidenced marker shapes (no separating whitespace, a
multi-character marker) are explicitly labelled as generic
marker-handling robustness checks, not as contractual dataset-format
requirements.
"""

from __future__ import annotations

import dataclasses

from phenopred.domain.detection.header_resolver import HeaderResolver
from phenopred.domain.value_objects import CommentBlock, Delimiter, HeaderInfo


# ---------------------------------------------------------------------------
# 1. Normal cases
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


def test_commented_only_header_detected_via_base_rule_independent_of_marker_stripping() -> None:
    # The keyword appears as its own bare token at a non-zero position,
    # so this matches via the base exact-token rule alone -- the
    # marker-stripping fallback (see the ADR-8 section below) is not
    # needed for this fixture. Token 0 ("notes here") has no leading
    # marker run, so its marker-stripped form is a no-op and is passed
    # through unchanged in resolved_columns. This test exists as a
    # regression check that the base rule continues to match
    # independently of the fallback, using a fixture that makes no
    # claim about any particular comment-marker convention.
    comment_block = CommentBlock(
        lines=("#some metadata", "notes here\trsid\tchromosome\tposition\tgenotype"),
        count=2,
    )
    data_lines = ["rs1\t1\t100\tAA"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == (
        "notes here",
        "rsid",
        "chromosome",
        "position",
        "genotype",
    )
    assert result.source_line == "notes here\trsid\tchromosome\tposition\tgenotype"


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
# 2. ADR-8: comment-marker stripping and semantic resolved_columns
#    (evidenced format only: "marker + space + content", e.g. "# rsid")
# ---------------------------------------------------------------------------


def test_adr8_dataset_b_header_produces_semantic_resolved_columns() -> None:
    # Primary ADR-8 regression anchor: the real, evidenced 23andMe
    # comment-header format, where the comment marker is followed by a
    # space, not the field delimiter, so the first token after
    # splitting is "# rsid", not "rsid". Per ADR-8, resolved_columns
    # must hold the marker-stripped semantic column name at index 0
    # ("rsid", not "# rsid"), while source_line remains the exact,
    # unmodified original comment line, marker included.
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
    assert result.resolved_columns == ("rsid", "chromosome", "position", "genotype")
    assert result.source_line == "# rsid\tchromosome\tposition\tgenotype"


def test_adr8_marker_stripping_is_a_no_op_when_token_already_semantic() -> None:
    # A comment-line header with no marker prefix at all: token 0
    # already exactly equals header_keyword, so the marker-stripped
    # form must be identical to the original token -- proving stripping
    # never alters an already-clean semantic column name.
    comment_block = CommentBlock(lines=("rsid\tchromosome\tposition",), count=1)
    data_lines = ["rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == ("rsid", "chromosome", "position")
    assert result.source_line == "rsid\tchromosome\tposition"


def test_adr8_marker_stripping_never_applied_on_uncommented_row_path() -> None:
    # A literal marker-prefixed token appearing in an *uncommented* data
    # line must not be marker-stripped or matched: marker interpretation
    # applies only within the commented_only branch. If stripping logic
    # leaked into the uncommented_row path, this fixture would
    # incorrectly resolve as "uncommented_row"; it must not.
    comment_block = CommentBlock(lines=(), count=0)
    data_lines = ["# rsid\tchromosome\tposition\tallele1\tallele2"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "absent"
    assert result.resolved_columns is None
    assert result.source_line is None


def test_adr8_input_immutability_under_marker_stripped_match() -> None:
    # CommentBlock and data_lines must reflect original, unmodified
    # content, and source_line must remain fully verbatim -- the
    # marker-stripping interpretation must never leak into stored input
    # or mutate caller-supplied arguments, even though resolved_columns
    # is now semantically corrected per ADR-8.
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
    assert result.resolved_columns == ("rsid", "chromosome", "position", "genotype")


# ---------------------------------------------------------------------------
# 3. Matching rules: marker-handling robustness
#    (unevidenced marker shapes -- generic robustness checks only,
#    NOT contractual dataset-format requirements)
# ---------------------------------------------------------------------------


def test_marker_with_no_following_whitespace_still_matches() -> None:
    # Marker glued directly to the keyword with no separating
    # whitespace at all -- the whitespace-stripping step is optional
    # (zero or more whitespace characters), per the documented
    # _strip_marker contract, not mandatory. This format is not
    # evidenced by either real dataset; this is a generic robustness
    # check of the documented stripping rule, not a supported-format
    # assertion.
    comment_block = CommentBlock(lines=("#rsid\tchromosome",), count=1)
    data_lines = ["rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == ("rsid", "chromosome")
    assert result.source_line == "#rsid\tchromosome"


def test_multi_character_marker_still_matches() -> None:
    # Marker-stripping is generic (any leading non-alphanumeric,
    # non-whitespace run), not hard-coded to a single '#' character --
    # HeaderResolver has no access to the configured comment_prefix
    # value. This marker character is not evidenced by either real
    # dataset; this is a generic robustness/neutrality check of the
    # documented stripping rule, not a supported-format assertion.
    comment_block = CommentBlock(lines=(";; rsid\tchromosome",), count=1)
    data_lines = ["rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == ("rsid", "chromosome")
    assert result.source_line == ";; rsid\tchromosome"


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


# ---------------------------------------------------------------------------
# 4. False positives
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 5. Boundary cases
# ---------------------------------------------------------------------------


def test_empty_data_lines_falls_through_to_comment_check() -> None:
    comment_block = CommentBlock(lines=("# rsid\tchromosome",), count=1)
    data_lines: list[str] = []
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == ("rsid", "chromosome")
    assert result.source_line == "# rsid\tchromosome"


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
    # header_keyword appears both in the first data line and in a
    # comment line; uncommented_row detection must take precedence.
    comment_block = CommentBlock(lines=("# rsid\tchromosome",), count=1)
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
        lines=("#unrelated line", "# rsid\tchromosome", "# rsid\tposition"),
        count=3,
    )
    data_lines = ["rs1\t1\t100"]
    delimiter = Delimiter(character="\t", detection_method="character_frequency_analysis")

    result = HeaderResolver(header_keyword="rsid").detect(
        comment_block, data_lines, delimiter
    )

    assert result.form == "commented_only"
    assert result.resolved_columns == ("rsid", "chromosome")
    assert result.source_line == "# rsid\tchromosome"


# ---------------------------------------------------------------------------
# 6. Matching rules: base exact-token discipline
# ---------------------------------------------------------------------------


def test_exact_token_matching_only_no_substring_match() -> None:
    # "rsid" is a substring of "rsident", not an exact token, so this
    # must not be classified as an uncommented header; falls through to
    # absent since no comment line matches either.
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
# 7. Contract behavior
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


def test_deterministic_repeated_calls_for_commented_only_form() -> None:
    # Determinism must also hold for the ADR-8-affected commented_only
    # path specifically, not only the uncommented_row path.
    comment_block = CommentBlock(
        lines=("# rsid\tchromosome\tposition\tgenotype",), count=1
    )
    data_lines = ["rs1\t1\t100\tAA"]
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
        (CommentBlock(lines=("# rsid\tchrom",), count=1), ["rs1\t1\t100"]),
    ]

    for comment_block, data_lines in cases:
        result = resolver.detect(comment_block, data_lines, delimiter)  # must not raise
        assert isinstance(result, HeaderInfo)


# ---------------------------------------------------------------------------
# 8. Dependency guard
# ---------------------------------------------------------------------------


def test_header_resolver_never_imports_forbidden_modules() -> None:
    # Structural guard, not a behavioral test: confirms this module has
    # no *import* dependency on phenopred.domain.errors, any
    # infrastructure module, or any sibling detector/downstream module,
    # per the approved Stage 2 dependency-ownership resolution.
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