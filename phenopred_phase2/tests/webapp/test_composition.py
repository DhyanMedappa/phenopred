# tests/webapp/test_composition.py
"""Unit tests for phenopred_phase2/webapp/composition.py."""

from __future__ import annotations

from phenopred_phase2.reporting.entities import PhenoPredReport
from phenopred_phase2.traits.domain.trait_registry import TRAIT_REGISTRY
from phenopred_phase2.webapp import composition


class _FakeProfilingReport:
    def __init__(self, source_path: str) -> None:
        self.source_path = source_path


class _FakeDataRow:
    def __init__(self, line_index: int, fields: tuple[str, ...]) -> None:
        self.line_index = line_index
        self.fields = fields


class _FakeColumnLayout:
    def __init__(self) -> None:
        self.rsid_column_index = 0
        self.chromosome_column_index = 1
        self.position_column_index = 2
        self.designated_column_indices = (3,)


def _fake_profile_result(source_path: str = "a.txt"):
    return {
        "data_rows": (_FakeDataRow(0, ("rs_unrelated", "1", "100", "AG")),),
        "column_layout": _FakeColumnLayout(),
        "report": _FakeProfilingReport(source_path),
    }


class _FakeUseCase:
    def __init__(self, profile_result) -> None:
        self._profile_result = profile_result
        self.executed_with = None

    def execute(self, file_path):
        self.executed_with = file_path
        return self._profile_result


def test_profile_file_delegates_to_composition_root(monkeypatch) -> None:
    fake_result = _fake_profile_result()
    fake_use_case = _FakeUseCase(fake_result)
    monkeypatch.setattr(
        composition, "build_profile_file_use_case", lambda: fake_use_case
    )

    result = composition.profile_file("some/path.txt")

    assert fake_use_case.executed_with == "some/path.txt"
    assert result is fake_result


def test_build_report_assembles_a_single_file_phenopred_report() -> None:
    profile_result = _fake_profile_result("a.txt")

    report = composition.build_report(profile_result)

    assert isinstance(report, PhenoPredReport)
    assert report.file_a_profiling_report is profile_result["report"]
    assert set(report.file_a_trait_cards.keys()) == set(TRAIT_REGISTRY.keys())
    assert report.file_b_profiling_report is None
    assert report.file_b_trait_cards is None
    assert report.comparison is None


def test_build_report_does_not_mutate_profile_result() -> None:
    profile_result = _fake_profile_result("a.txt")
    profile_result_before = dict(profile_result)

    composition.build_report(profile_result)

    assert profile_result["report"] is profile_result_before["report"]
    assert profile_result["data_rows"] == profile_result_before["data_rows"]


def test_run_single_file_pipeline_wires_profile_file_and_build_report(
    monkeypatch,
) -> None:
    fake_result = _fake_profile_result("a.txt")
    fake_use_case = _FakeUseCase(fake_result)
    monkeypatch.setattr(
        composition, "build_profile_file_use_case", lambda: fake_use_case
    )

    report = composition.run_single_file_pipeline("a.txt")

    assert fake_use_case.executed_with == "a.txt"
    assert isinstance(report, PhenoPredReport)
    assert report.file_a_profiling_report is fake_result["report"]
    assert set(report.file_a_trait_cards.keys()) == set(TRAIT_REGISTRY.keys())


class _FakeTwoFileUseCase:
    def __init__(self, results_by_path) -> None:
        self._results_by_path = results_by_path
        self.executed_with: list = []

    def execute(self, file_path):
        self.executed_with.append(file_path)
        return self._results_by_path[file_path]


def test_run_two_file_pipeline_assembles_a_combined_report(monkeypatch) -> None:
    result_a = _fake_profile_result("a.txt")
    result_b = _fake_profile_result("b.txt")
    fake_use_case = _FakeTwoFileUseCase({"a.txt": result_a, "b.txt": result_b})
    monkeypatch.setattr(
        composition, "build_profile_file_use_case", lambda: fake_use_case
    )

    report = composition.run_two_file_pipeline("a.txt", "b.txt")

    assert fake_use_case.executed_with == ["a.txt", "b.txt"]
    assert isinstance(report, PhenoPredReport)
    assert report.file_a_profiling_report is result_a["report"]
    assert report.file_b_profiling_report is result_b["report"]
    assert set(report.file_a_trait_cards.keys()) == set(TRAIT_REGISTRY.keys())
    assert set(report.file_b_trait_cards.keys()) == set(TRAIT_REGISTRY.keys())
    assert report.comparison is not None


def test_run_two_file_pipeline_computes_real_concordance_not_fabricated(
    monkeypatch,
) -> None:
    # rs_shared_match: identical genotype in both files -> SNP_MATCH.
    # rs_shared_conflict: differing genotype in both files -> SNP_MISMATCH.
    # rs_unrelated is only present in file A and is not shared, so it must
    # not affect the concordance count at all.
    result_a = {
        "data_rows": (
            _FakeDataRow(0, ("rs_shared_match", "1", "100", "AG")),
            _FakeDataRow(1, ("rs_shared_conflict", "1", "200", "AA")),
            _FakeDataRow(2, ("rs_unrelated", "1", "300", "TT")),
        ),
        "column_layout": _FakeColumnLayout(),
        "report": _FakeProfilingReport("a.txt"),
    }
    result_b = {
        "data_rows": (
            _FakeDataRow(0, ("rs_shared_match", "1", "100", "AG")),
            _FakeDataRow(1, ("rs_shared_conflict", "1", "200", "GG")),
        ),
        "column_layout": _FakeColumnLayout(),
        "report": _FakeProfilingReport("b.txt"),
    }
    fake_use_case = _FakeTwoFileUseCase({"a.txt": result_a, "b.txt": result_b})
    monkeypatch.setattr(
        composition, "build_profile_file_use_case", lambda: fake_use_case
    )

    report = composition.run_two_file_pipeline("a.txt", "b.txt")

    concordance = report.comparison.concordance
    assert concordance.total_shared_rsids == 2
    assert concordance.shared_snp_count == 1
    assert concordance.conflicting_snp_count == 1


def test_run_two_file_pipeline_does_not_mutate_its_profile_results(
    monkeypatch,
) -> None:
    result_a = _fake_profile_result("a.txt")
    result_b = _fake_profile_result("b.txt")
    result_a_before = dict(result_a)
    result_b_before = dict(result_b)
    fake_use_case = _FakeTwoFileUseCase({"a.txt": result_a, "b.txt": result_b})
    monkeypatch.setattr(
        composition, "build_profile_file_use_case", lambda: fake_use_case
    )

    composition.run_two_file_pipeline("a.txt", "b.txt")

    assert result_a["report"] is result_a_before["report"]
    assert result_b["report"] is result_b_before["report"]