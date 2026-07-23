# tests/unit/domain/detection/test_column_identity_resolver.py
"""Unit tests for ColumnIdentityResolver.

Mirrors the testing approach established by
tests/unit/domain/detection/test_header_resolver.py,
test_chromosome_label_profiler.py, test_genotype_layout_classifier.py,
test_indel_haploid_classifier.py, test_duplicate_rsid_check.py,
test_duplicate_header_check.py, and test_missing_value_scanner.py: small,
synthetic, in-memory fixtures only, no file I/O, exercising exactly the
structural properties named by the Column Identity Resolution contract,
the Detector[T] Protocol (interfaces.py), ColumnLayout's frozen contract
(value_objects.py), and NFR-5/AD-5 (neutrality across input layout, no
fixed schema).

Scope discipline: this suite verifies ColumnIdentityResolver only. It
does not test, anticipate, or stub HeaderResolver, any QualityCheck, or
any GenomicProfiler. It does not lock private helper methods, internal
call ordering, tuple.index() first-match behavior on duplicate
keywords, or any other incidental implementation detail lacking an
explicit documented contract.
"""

from __future__ import annotations

import ast

from phenopred.domain.detection import (
    column_identity_resolver as column_identity_resolver_module,
)
from phenopred.domain.detection.column_identity_resolver import (
    ColumnIdentityNotResolvedError,
    ColumnIdentityResolver,
)
from phenopred.domain.interfaces import Detector
from phenopred.domain.value_objects import ColumnLayout, HeaderInfo


# ---------------------------------------------------------------------------
# 1. Normal behaviour: full resolution
# ---------------------------------------------------------------------------


def test_all_four_roles_resolved_correctly_from_full_header() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "allele1", "allele2"),
        source_line="rsid\tchromosome\tposition\tallele1\tallele2",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=("allele1", "allele2"),
    )
    layout = resolver.detect(header_info)
    assert layout.rsid_column_index == 0
    assert layout.chromosome_column_index == 1
    assert layout.position_column_index == 2
    assert layout.designated_column_indices == (3, 4)


def test_single_designated_column_layout_resolved_correctly() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="rsid\tchromosome\tposition\tgenotype",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=("genotype",),
    )
    layout = resolver.detect(header_info)
    assert layout.designated_column_indices == (3,)


# ---------------------------------------------------------------------------
# 2. Mandatory-role failure -- each role independently
# ---------------------------------------------------------------------------


def test_missing_rsid_keyword_raises_column_identity_not_resolved_error() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("chromosome", "position", "genotype"),
        source_line="chromosome\tposition\tgenotype",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=("genotype",),
    )
    try:
        resolver.detect(header_info)
        raise AssertionError("expected ColumnIdentityNotResolvedError")
    except ColumnIdentityNotResolvedError:
        pass


def test_missing_chromosome_keyword_raises_column_identity_not_resolved_error() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "position", "genotype"),
        source_line="rsid\tposition\tgenotype",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=("genotype",),
    )
    try:
        resolver.detect(header_info)
        raise AssertionError("expected ColumnIdentityNotResolvedError")
    except ColumnIdentityNotResolvedError:
        pass


def test_missing_position_keyword_raises_column_identity_not_resolved_error() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "genotype"),
        source_line="rsid\tchromosome\tgenotype",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=("genotype",),
    )
    try:
        resolver.detect(header_info)
        raise AssertionError("expected ColumnIdentityNotResolvedError")
    except ColumnIdentityNotResolvedError:
        pass


def test_resolved_columns_none_raises_column_identity_not_resolved_error() -> None:
    header_info = HeaderInfo(form="absent", resolved_columns=None, source_line=None)
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=("genotype",),
    )
    try:
        resolver.detect(header_info)
        raise AssertionError("expected ColumnIdentityNotResolvedError")
    except ColumnIdentityNotResolvedError:
        pass


# ---------------------------------------------------------------------------
# 3. Designated columns -- non-mandatory behaviour
# ---------------------------------------------------------------------------


def test_no_designated_column_keyword_found_returns_empty_tuple_not_exception() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position"),
        source_line="rsid\tchromosome\tposition",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=("genotype",),
    )
    layout = resolver.detect(header_info)
    assert layout.designated_column_indices == ()


def test_designated_column_indices_returned_in_ascending_index_order() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "allele2", "chromosome", "position", "allele1"),
        source_line="rsid\tallele2\tchromosome\tposition\tallele1",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=("allele1", "allele2"),
    )
    layout = resolver.detect(header_info)
    assert layout.designated_column_indices == (1, 4)


def test_multiple_designated_column_keywords_all_resolved() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "allele1", "allele2"),
        source_line="rsid\tchromosome\tposition\tallele1\tallele2",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=("allele1", "allele2"),
    )
    layout = resolver.detect(header_info)
    assert layout.designated_column_indices == (3,4)


# ---------------------------------------------------------------------------
# 4. Exact-match discipline
# ---------------------------------------------------------------------------


def test_no_case_folding_in_keyword_matching() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("RSID", "chromosome", "position"),
        source_line="RSID\tchromosome\tposition",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=(),
    )
    try:
        resolver.detect(header_info)
        raise AssertionError("expected ColumnIdentityNotResolvedError")
    except ColumnIdentityNotResolvedError:
        pass


def test_no_substring_matching_in_keyword_matching() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsident", "chromosome", "position"),
        source_line="rsident\tchromosome\tposition",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=(),
    )
    try:
        resolver.detect(header_info)
        raise AssertionError("expected ColumnIdentityNotResolvedError")
    except ColumnIdentityNotResolvedError:
        pass


# ---------------------------------------------------------------------------
# 5. Dataset neutrality (no fixed schema)
# ---------------------------------------------------------------------------


def test_arbitrary_non_standard_keyword_configuration_resolves_correctly() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("identifier", "chrom", "pos", "call"),
        source_line="identifier\tchrom\tpos\tcall",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="identifier",
        chromosome_keyword="chrom",
        position_keyword="pos",
        designated_column_keywords=("call",),
    )
    layout = resolver.detect(header_info)
    assert layout.rsid_column_index == 0
    assert layout.chromosome_column_index == 1
    assert layout.position_column_index == 2
    assert layout.designated_column_indices == (3,)


# ---------------------------------------------------------------------------
# 6. Determinism
# ---------------------------------------------------------------------------


def test_repeated_execution_produces_identical_column_layout() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position", "genotype"),
        source_line="rsid\tchromosome\tposition\tgenotype",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=("genotype",),
    )
    first = resolver.detect(header_info)
    second = resolver.detect(header_info)
    assert first == second


# ---------------------------------------------------------------------------
# 7. Output contract: ColumnLayout shape
# ---------------------------------------------------------------------------


def test_return_type_is_column_layout() -> None:
    header_info = HeaderInfo(
        form="uncommented_row",
        resolved_columns=("rsid", "chromosome", "position"),
        source_line="rsid\tchromosome\tposition",
    )
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=(),
    )
    layout = resolver.detect(header_info)
    assert isinstance(layout, ColumnLayout)


# ---------------------------------------------------------------------------
# 8. Protocol compliance
# ---------------------------------------------------------------------------


def test_column_identity_resolver_satisfies_detector_protocol() -> None:
    resolver = ColumnIdentityResolver(
        rsid_keyword="rsid",
        chromosome_keyword="chromosome",
        position_keyword="position",
        designated_column_keywords=(),
    )
    assert isinstance(resolver, Detector)


# ---------------------------------------------------------------------------
# 9. Dependency boundaries (structural, AST-based)
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


def test_column_identity_resolver_never_imports_errors_module() -> None:
    imported = _imported_module_names(column_identity_resolver_module)
    assert not any("errors" in name for name in imported)


def test_column_identity_resolver_never_imports_upstream_or_sibling_modules() -> None:
    imported = _imported_module_names(column_identity_resolver_module)
    forbidden_substrings = [
        "raw_file_loader",
        "encoding_detector",
        "raw_line_splitter",
        "delimiter_detector",
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


def test_column_identity_resolver_only_imports_allowed_domain_modules() -> None:
    imported = _imported_module_names(column_identity_resolver_module)
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