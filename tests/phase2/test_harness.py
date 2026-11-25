import numpy as np
import pytest

from research import harness


def test_auroc_known_values():
    assert harness.auroc([0, 1, 2], [3, 4]) == 1.0
    assert harness.auroc([3, 4], [0, 1]) == 0.0
    assert harness.auroc([1, 1], [1, 1]) == 0.5
    rng = np.random.default_rng(0)
    a, b = rng.standard_normal(300), rng.standard_normal(200) + 1
    brute = np.mean((b[:, None] > a) + 0.5 * (b[:, None] == a))
    assert harness.auroc(a, b) == pytest.approx(brute)


def test_intervals_contain_the_estimate():
    ratios = np.random.default_rng(0).uniform(0.5, 1, 200)
    low, high = harness.bootstrap_loss(ratios)
    assert low < harness.loss_db(ratios) < high
    low, high = harness.proportion_interval(50, 50)
    assert 0.9 < low < 1 and high == pytest.approx(1)


def test_results_round_trip_and_report_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    harness.save_results("demo", "x", {"a": np.arange(2), "b": np.float64(1.5)})
    assert harness.load_results("demo", "x") == {"a": [0, 1], "b": 1.5}
    page = tmp_path / "r.md"
    page.write_text("top\n<!-- t -->old<!-- /t -->\nend", encoding="utf-8")
    harness.replace_block(page, "t", harness.markdown_table(["a"], [[1]]))
    assert "| 1 |" in page.read_text(encoding="utf-8") and "old" not in page.read_text()
    with pytest.raises(ValueError):
        harness.replace_block(page, "missing", "")
