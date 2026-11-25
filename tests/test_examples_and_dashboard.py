"""Every demo must run headless, and the dashboard must process frames."""

import runpy
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from dashboard import app
from dashboard.metrics_panel import format_metrics
from embedded.common.config import PipelineConfig
from examples import run_realtime_beam_scan

DEMOS = sorted((Path(__file__).parents[1] / "examples").glob("run_*.py"))


def test_every_demo_is_collected():
    assert len(DEMOS) == 14


@pytest.mark.parametrize("path", DEMOS, ids=lambda p: p.stem)
def test_demo_runs(path, monkeypatch):
    monkeypatch.setattr("sys.argv", [path.name])
    runpy.run_path(str(path), run_name="__main__")


def test_beam_scan_writes_a_gif(tmp_path):
    run_realtime_beam_scan.main(["--save", str(tmp_path / "scan.gif"), "--frames", "3"])
    with Image.open(tmp_path / "scan.gif") as image:
        assert image.n_frames == 3


def test_dashboard_snapshot(tmp_path):
    assert app.main(["--snapshot", str(tmp_path / "d.png"), "--frames", "5"]) == 0
    assert (tmp_path / "d.png").stat().st_size > 10_000


def test_dashboard_panels_show_the_pipeline_state():
    config = PipelineConfig()
    frames = list(app.demo_source(config, 6))
    dashboard = app.Dashboard(config, frames[0].sample_rate_hz)
    for frame in frames:
        result = dashboard.update(frame)
    brightest = dashboard.heatmap.angles_deg[np.nanargmax(dashboard.heatmap.data[-1])]
    assert brightest == pytest.approx(-40, abs=3)
    rows = dict(format_metrics(result, 1e-3))
    assert rows["method"] == "lcmv" and rows["status"] == "nominal"
    assert rows["sources detected"] == "2"


def test_dashboard_without_frames(capsys, monkeypatch):
    monkeypatch.setattr(app, "UdpSource", lambda **_: [])
    assert app.main(["--udp", "1"]) == 1
    assert "no frame" in capsys.readouterr().err
