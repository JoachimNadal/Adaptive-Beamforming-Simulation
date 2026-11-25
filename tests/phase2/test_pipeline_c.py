"""C pipeline against Python, through recordings and the replay tool."""

import json
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import replace

import numpy as np
import pytest

from dsp.signal_metrics import output_sinr, to_db
from embedded.common.config import PipelineConfig
from embedded.common.iq_frame import FrameFlag, pack_frame
from embedded.common.sources import SimulatedSource, record
from research.c_port import run

pytestmark = [
    pytest.mark.ccore,
    pytest.mark.skipif(not shutil.which("cmake"), reason="CMake not available"),
    pytest.mark.skipif(
        not any(map(shutil.which, ("gcc", "clang", "cc"))), reason="no C compiler available"
    ),
]


@pytest.fixture(scope="module")
def directory(tmp_path_factory):
    return run.build(tmp_path_factory.mktemp("abfp"))


def recording(tmp_path, n, angles, powers, blocks=5, seed=0):
    config = replace(PipelineConfig(), num_elements=n)
    source = SimulatedSource(config, angles, powers, blocks, rng=seed)
    path = tmp_path / "scene.abf"
    record(source, path)
    return config, path, source.scene()


@pytest.mark.parametrize("precision", ["f32", "f64"])
def test_c_unit_tests(directory, precision):
    done = subprocess.run(
        [str(run.program(directory, f"test_pipeline_{precision}"))], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stdout


SCENES = [
    (4, [0, -35], [1, 1000]),
    (4, [0, -35, 50, 20], [1, 1000, 1000, 1000]),  # saturated
    (4, [0, 4], [1, 1000]),  # falls back to delay-and-sum
    (8, [0, -25, 40], [1, 10**3.5, 10**3.5]),
    (8, [0], [1]),
    (16, [0, -20, 33, 61], [2, 300, 1000, 50]),
]


@pytest.mark.parametrize("n, angles, powers", SCENES)
@pytest.mark.parametrize("mode", ["phase1", "noise", "sqrt"])
def test_double_precision_equals_python(directory, tmp_path, n, angles, powers, mode):
    config, path, _ = recording(tmp_path, n, angles, powers)
    reference = run.python_reference(path, mode, config)
    records, output = run.replay(directory, "f64", path, mode, config)
    size = config.block_size
    for b, (p, c) in enumerate(zip(reference, records, strict=True)):
        w = np.array(c["weights"]) @ [1, 1j]
        np.testing.assert_allclose(w, p.weights, atol=1e-5 * np.linalg.norm(p.weights))
        assert run.METHODS[c["method"]] == p.method
        assert c["status"] == p.status.value
        np.testing.assert_allclose(
            output[b * size : (b + 1) * size], p.output, atol=1e-4 * np.abs(p.output).max()
        )
        if mode == "phase1":
            assert c["sources"] == p.num_sources
            np.testing.assert_allclose(np.degrees(c["doas"]), p.doas_deg, atol=1e-3)
            np.testing.assert_allclose(np.sort(np.degrees(c["nulls"])), p.nulls_deg, atol=1e-3)


@pytest.mark.parametrize("n", [4, 8, 16])
def test_single_precision_square_root_mode_at_80_db(directory, tmp_path, n):
    config, path, scene = recording(tmp_path, n, [0, -35], [1, 1e8])
    a, R_in = scene.A[:, 0], scene.R_interference_noise
    sinr = {}
    for precision in ("f32", "f64"):
        records, _ = run.replay(directory, precision, path, "sqrt", config)
        assert records[-1]["sources"] == 2
        w = np.array(records[-1]["weights"]) @ [1, 1j]
        sinr[precision] = to_db(output_sinr(w, a, 1.0, R_in))
    assert sinr["f32"] == pytest.approx(sinr["f64"], abs=0.05)


def test_flags_reach_the_c_pipeline(directory, tmp_path):
    config = PipelineConfig()
    frames = list(SimulatedSource(config, [0, -35], [1, 100], 4, rng=0))
    frames[1] = replace(frames[1], flags=FrameFlag.ADC_OVERFLOW)
    frames[2] = replace(frames[2], flags=FrameFlag.CLOCK_UNLOCKED)
    frames[3] = replace(frames[3], sequence=9)
    record(frames, tmp_path / "f.abf")
    reference = run.python_reference(tmp_path / "f.abf", "phase1", config)
    records, _ = run.replay(directory, "f64", tmp_path / "f.abf", "phase1", config)
    assert [c["status"] for c in records] == [p.status.value for p in reference]


def test_replay_rejects_corrupt_recordings(directory, tmp_path):
    config, path, _ = recording(tmp_path, 4, [0], [1], 2)
    data = bytearray(path.read_bytes())
    data[200] ^= 1
    path.write_bytes(data)
    with pytest.raises(RuntimeError, match="invalid frame"):
        run.replay(directory, "f32", path, "phase1", config)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX receiver")
def test_live_receiver_over_loopback(directory):
    config = PipelineConfig()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    receiver = subprocess.Popen(
        [str(run.program(directory, "abf_receiver")), str(port), "sqrt", "0", "0.5", "50"],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert json.loads(receiver.stdout.readline())["listening"] == port
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        sender.sendto(b"garbage", ("127.0.0.1", port))
        for frame in SimulatedSource(config, [0, -35], [1, 1000], 50, rng=0):
            sender.sendto(pack_frame(frame), ("127.0.0.1", port))
            time.sleep(0.001)
    summary = json.loads(receiver.communicate(timeout=20)[0].splitlines()[-1])
    assert summary["processed"] == 50 and summary["rejected"] == 1
    assert summary["dropped"] == 0 and summary["gaps"] == 0 and summary["sources"] == 2


def test_square_root_prototype():
    result = run.square_root(trials=10)
    assert result["N=8 INR=80"]["square root"]["correct_order"] == 1.0
    assert result["N=8 INR=80"]["square root"]["mean_loss_db"] < 0.1
    assert result["N=8 INR=80"]["covariance"]["correct_order"] < 0.5
