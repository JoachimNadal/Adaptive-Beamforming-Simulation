"""Every generated table in a study report must match the committed result files."""

import importlib

import pytest

STUDIES = ("covariance", "open_set", "c_port", "sparse", "measured")


@pytest.mark.parametrize("study", STUDIES)
def test_tables_match_the_result_files(study, monkeypatch):
    report = importlib.import_module(f"research.{study}.report")
    blocks = []

    def check(path, name, text):
        blocks.append(name)
        assert text.strip() in path.read_text(encoding="utf-8"), name

    monkeypatch.setattr(report, "replace_block", check)
    for name in list(vars(report)):
        if name.endswith(("figure", "figures")) and callable(getattr(report, name)):
            monkeypatch.setattr(report, name, lambda *_: None)
    report.main()
    assert blocks
