# tests/unit/domain/ingestion/test_raw_line_splitter.py
"""Unit tests for RawLineSplitter (FR-1) and CommentBlock.

Mirrors the testing approach established by
tests/unit/domain/detection/test_delimiter_detector.py and
test_encoding_detector.py: small, synthetic, in-memory fixtures only, no
file I/O, exercising the structural properties named by the SRS and the
frozen RawLineSplitter architecture decisions (exact prefix matching, no
positional/contiguity assumption, no trimming/normalization, ordering and
verbatim preservation, empty-input validity, and CommentBlock
immutability).
"""

from __future__ import annotations

import dataclasses

from phenopred.domain.ingestion.raw_line_splitter import RawLineSplitter
from phenopred.domain.value_objects import CommentBlock


# ---------------------------------------------------------------------------
# Normal behavior
# ---------------------------------------------------------------------------


def test_comments_followed_by_data() -> None:
    lines = ["#meta1", "#meta2", "rs1\t1\t100", "rs2\t1\t200"]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ("#meta1", "#meta2")
    assert comment_block.count == 2
    assert data_lines == ("rs1\t1\t100", "rs2\t1\t200")


def test_multiple_comment_lines() -> None:
    lines = ["#a", "#b", "#c", "data1"]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ("#a", "#b", "#c")
    assert comment_block.count == 3
    assert data_lines == ("data1",)


def test_non_contiguous_comments_are_all_captured() -> None:
    # A comment line appearing after data lines must still be classified
    # as a comment: RawLineSplitter has no concept of a leading block or
    # contiguity, per Architecture v1 Section 6 ("all comment lines") and
    # Section 9 ("separate... by prefix").
    lines = ["#lead", "data1", "#trailing", "data2"]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ("#lead", "#trailing")
    assert comment_block.count == 2
    assert data_lines == ("data1", "data2")


def test_no_comments() -> None:
    lines = ["data1", "data2", "data3"]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ()
    assert comment_block.count == 0
    assert data_lines == ("data1", "data2", "data3")


def test_only_comments() -> None:
    lines = ["#a", "#b", "#c"]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ("#a", "#b", "#c")
    assert comment_block.count == 3
    assert data_lines == ()


# ---------------------------------------------------------------------------
# Boundary behavior
# ---------------------------------------------------------------------------


def test_empty_input_returns_empty_comment_block_and_empty_data_lines() -> None:
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split([])
    assert comment_block == CommentBlock(lines=(), count=0)
    assert data_lines == ()


def test_empty_comment_block_is_valid() -> None:
    lines = ["data1", "data2"]
    comment_block, _ = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ()
    assert comment_block.count == 0


def test_empty_candidate_data_lines_is_valid() -> None:
    lines = ["#only", "#comments"]
    _, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert data_lines == ()


def test_blank_lines_are_classified_as_data_not_special_cased() -> None:
    # A blank line does not start with the comment prefix, so it is a
    # candidate data line like any other non-prefixed line -- no special
    # blank-line category exists.
    lines = ["#meta", "", "data1", ""]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ("#meta",)
    assert data_lines == ("", "data1", "")


# ---------------------------------------------------------------------------
# Prefix behavior
# ---------------------------------------------------------------------------


def test_exact_prefix_matching() -> None:
    lines = ["#comment", "rs1#note", "data"]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    # "#comment" begins with '#' -> comment.
    # "rs1#note" contains '#' but does not begin with it -> data.
    assert comment_block.lines == ("#comment",)
    assert data_lines == ("rs1#note", "data")


def test_configurable_prefix_behavior() -> None:
    lines = [";;meta1", ";;meta2", "data1"]
    comment_block, data_lines = RawLineSplitter(comment_prefix=";;").split(lines)
    assert comment_block.lines == (";;meta1", ";;meta2")
    assert data_lines == ("data1",)
    # The default '#' character must not apply when a different prefix is
    # injected.
    lines_with_hash = ["#not_a_comment_here", ";;actual_comment"]
    comment_block2, data_lines2 = RawLineSplitter(comment_prefix=";;").split(
        lines_with_hash
    )
    assert comment_block2.lines == (";;actual_comment",)
    assert data_lines2 == ("#not_a_comment_here",)


def test_leading_whitespace_before_prefix_is_not_a_comment_match() -> None:
    lines = [" #comment", "#realcomment"]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ("#realcomment",)
    assert data_lines == (" #comment",)


# ---------------------------------------------------------------------------
# Preservation behavior
# ---------------------------------------------------------------------------


def test_original_content_preserved_exactly() -> None:
    lines = ["#  spaced   comment  ", "  data with spaces  ", "café -- naïve"]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ("#  spaced   comment  ",)
    assert data_lines == ("  data with spaces  ", "café -- naïve")


def test_ordering_preserved_within_each_output() -> None:
    lines = ["#1", "data1", "#2", "data2", "#3", "data3"]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ("#1", "#2", "#3")
    assert data_lines == ("data1", "data2", "data3")


def test_no_trimming_of_whitespace() -> None:
    lines = ["   leading and trailing   "]
    _, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert data_lines == ("   leading and trailing   ",)


def test_no_normalization_of_case_or_unicode() -> None:
    lines = ["#MixedCase", "MixedCaseData", "ÜNÏCÖDE"]
    comment_block, data_lines = RawLineSplitter(comment_prefix="#").split(lines)
    assert comment_block.lines == ("#MixedCase",)
    assert data_lines == ("MixedCaseData", "ÜNÏCÖDE")


# ---------------------------------------------------------------------------
# Contract behavior
# ---------------------------------------------------------------------------


def test_comment_block_is_immutable_reassignment_raises() -> None:
    comment_block = CommentBlock(lines=("#a",), count=1)
    try:
        comment_block.count = 2  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def test_comment_block_rejects_new_attribute() -> None:
    comment_block = CommentBlock(lines=("#a",), count=1)
    try:
        comment_block.extra = "not allowed"  # type: ignore[attr-defined]
        raise AssertionError("expected AttributeError or TypeError")
    except (AttributeError, TypeError):
        pass


def test_input_sequence_is_not_mutated() -> None:
    lines = ["#a", "data1", "#b", "data2"]
    original_copy = list(lines)
    RawLineSplitter(comment_prefix="#").split(lines)
    assert lines == original_copy


def test_no_mutation_when_input_is_a_tuple() -> None:
    lines = ("#a", "data1")
    RawLineSplitter(comment_prefix="#").split(lines)
    assert lines == ("#a", "data1")


def test_deterministic_repeated_calls() -> None:
    lines = ["#a", "data1", "#b", "data2"]
    splitter = RawLineSplitter(comment_prefix="#")
    first = splitter.split(lines)
    second = splitter.split(lines)
    assert first == second


def _run_all() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
    print(f"{passed} passed, 0 failed, 0 skipped")


if __name__ == "__main__":
    _run_all()
