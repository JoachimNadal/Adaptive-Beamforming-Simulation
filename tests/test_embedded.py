import json
import threading
from dataclasses import replace

import numpy as np
import pytest

from dsp.adaptive_weights import das_weights, mvdr_weights
from dsp.covariance_matrix import compute_covariance_matrix, loading_level
from dsp.signal_metrics import optimal_sinr, output_sinr, to_db
from embedded.common.config import ConfigError, PipelineConfig, load_config
from embedded.common.iq_frame import (
    HEADER_SIZE,
    FrameError,
    FrameFlag,
    IQFrame,
    SampleFormat,
    pack_frame,
    unpack_frame,
)
from embedded.common.pipeline import BeamformingPipeline, Status
from embedded.common.sources import FileSource, SimulatedSource, UdpSource, record, send_udp
from embedded.jetson import orin_pipeline
from embedded.raspberry_pi import pi_receiver
from simulations.channels.awgn import complex_noise
from simulations.scenarios.array_snapshots import random_channel_gains

CONFIG = PipelineConfig()


def make_frame(samples=None, sequence=0, flags=FrameFlag.NONE):
    if samples is None:
        samples = complex_noise((4, 256), 0.01, rng=0)
    return IQFrame(samples.astype(np.complex64), sequence, 123456789, 1e6, 2.4e9, flags)


# ----------------------------------------------------------------------- IQ frames


def test_frame_round_trip_float():
    frame = make_frame(sequence=7, flags=FrameFlag.ADC_OVERFLOW | FrameFlag.GAIN_CHANGED)
    out = unpack_frame(pack_frame(frame))
    np.testing.assert_array_equal(out.samples, frame.samples)
    assert (out.sequence, out.timestamp_ns, out.sample_rate_hz) == (7, 123456789, 1e6)
    assert out.center_frequency_hz == 2.4e9 and out.flags == frame.flags


def test_frame_round_trip_int16_quantises_within_half_lsb():
    frame = make_frame()
    out = unpack_frame(pack_frame(frame, SampleFormat.CI16, scale=1 / 32768))
    error = out.samples - frame.samples
    assert np.abs(error.real).max() <= 0.51 / 32768
    assert np.abs(error.imag).max() <= 0.51 / 32768


def test_every_corrupted_byte_is_detected():
    data = pack_frame(make_frame(complex_noise((2, 4), 1.0, 0)))
    for i in range(len(data)):
        corrupt = bytearray(data)
        corrupt[i] ^= 0x10
        with pytest.raises(FrameError):
            unpack_frame(corrupt)


def test_truncated_and_oversized_frames_are_rejected():
    data = pack_frame(make_frame())
    for bad in (b"", data[:10], data[:HEADER_SIZE], data[:-1], data + b"\0"):
        with pytest.raises(FrameError):
            unpack_frame(bad)


@pytest.mark.parametrize("seed", range(20))
def test_parser_survives_random_bytes(seed):
    rng = np.random.default_rng(seed)
    with pytest.raises(FrameError):
        unpack_frame(rng.integers(0, 256, rng.integers(0, 300), dtype=np.uint8).tobytes())


def test_pack_validation():
    with pytest.raises(FrameError):
        pack_frame(make_frame(np.ones((4, 8)) * 2), SampleFormat.CI16, scale=1 / 32768)
    with pytest.raises(FrameError):
        pack_frame(make_frame(np.ones(8)))
    for scale in (0.0, -1.0, float("nan")):
        with pytest.raises(FrameError):
            pack_frame(make_frame(), scale=scale)
    with pytest.raises(FrameError):  # invalid metadata is refused on reception
        unpack_frame(pack_frame(replace(make_frame(), sample_rate_hz=0.0)))


# -------------------------------------------------------------------- configuration


def test_reference_configuration_file():
    assert load_config(pi_receiver.DEFAULT_CONFIG) == CONFIG
    assert pytest.approx(0.5, abs=1e-3) == CONFIG.d_over_lambda


@pytest.mark.parametrize(
    "changes",
    [
        {"num_elements": 1},
        {"spacing_m": -1.0},
        {"spacing_m": 0.07},  # beyond half a wavelength: ambiguous angles
        {"target_deg": 100.0},
        {"block_size": 2},
        {"covariance_beta": 1.0},
        {"relative_loading": 0.0},
        {"max_interferers": 4},
        {"min_wng_ratio": 1.0},
        {"guard_deg": 0.0},
    ],
)
def test_invalid_configurations(changes):
    with pytest.raises(ConfigError):
        replace(CONFIG, **changes)


@pytest.mark.parametrize("text", ["typo_key = 1", "not toml [", 'num_elements = "four"'])
def test_invalid_configuration_files(tmp_path, text):
    path = tmp_path / "bad.toml"
    path.write_text(text)
    with pytest.raises(ConfigError):
        load_config(path)


# -------------------------------------------------------------------------- sources


def test_file_source_round_trip(tmp_path):
    frames = list(SimulatedSource(CONFIG, [0, -35], [1, 100], 3, rng=0))
    assert record(frames, tmp_path / "capture.abf") == 3
    back = list(FileSource(tmp_path / "capture.abf"))
    assert [f.sequence for f in back] == [0, 1, 2]
    np.testing.assert_array_equal(back[2].samples, frames[2].samples)


def test_truncated_recording_is_an_error(tmp_path):
    path = tmp_path / "capture.abf"
    record(SimulatedSource(CONFIG, [0], [1], 2, rng=0), path)
    path.write_bytes(path.read_bytes()[:-5])
    with pytest.raises(FrameError):
        list(FileSource(path))


def test_udp_source_skips_corrupt_datagrams():
    frames = list(SimulatedSource(CONFIG, [0], [1], 3, rng=0))
    with UdpSource(timeout_s=2.0, max_frames=3) as source:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(b"garbage", source.address)
        sender = threading.Thread(target=send_udp, args=(frames, source.address))
        sender.start()
        received = list(source)
        sender.join()
        assert source.rejected == 1
    assert [f.sequence for f in received] == [0, 1, 2]


def test_udp_source_times_out():
    with UdpSource(timeout_s=0.05) as source:
        assert list(source) == []


# ------------------------------------------------------------------------- pipeline


def run_scene(config, angles, powers, frames=12, calibration=None, rng=0, **options):
    source = SimulatedSource(config, angles, powers, frames, rng=rng, **options)
    pipeline = BeamformingPipeline(config, calibration)
    for frame in source:
        result = pipeline.process(frame)
    scene = source.scene()
    best = optimal_sinr(scene.A_effective[:, 0], powers[0], scene.R_interference_noise)
    # the pipeline sees calibrated data: score its weights in the uncorrected domain
    w = result.weights
    if pipeline.calibration is not None:
        w = w / pipeline.calibration.conj()
    sinr = output_sinr(w, scene.A_effective[:, 0], powers[0], scene.R_interference_noise)
    return result, to_db(sinr), to_db(best)


@pytest.mark.parametrize(
    "n, angles, powers",
    [
        (4, [0, -35], [1, 1000]),
        (8, [0, -25, 40], [1, 10**3.5, 10**3.5]),  # course scene, erratum E3
        (4, [2, -35], [10, 1000]),  # pointing error
    ],
)
def test_pipeline_is_close_to_optimum(n, angles, powers):
    result, sinr, best = run_scene(
        replace(CONFIG, num_elements=n), angles, powers, calibration=np.ones(n)
    )
    assert best - sinr < 0.5
    assert result.status == Status.NOMINAL and result.method == "lcmv"
    np.testing.assert_allclose(result.nulls_deg, np.sort(angles[1:]), atol=0.5)


def test_pipeline_without_interference_is_delay_and_sum_like():
    result, sinr, best = run_scene(CONFIG, [0], [1.0], calibration=np.ones(4))
    assert best - sinr < 0.2 and result.nulls_deg.size == 0


def test_saturated_array_is_reported_and_still_useful():
    result, sinr, best = run_scene(
        CONFIG, [0, -35, 50, 20], [1, 1000, 1000, 1000], calibration=np.ones(4)
    )
    assert Status.TOO_MANY_SOURCES in result.status
    assert best - sinr < 2


def test_more_interferers_than_nulls_allowed():
    config = replace(CONFIG, num_elements=8, max_interferers=1)
    result, sinr, best = run_scene(config, [0, -25, 40], [1, 1000, 100], calibration=np.ones(8))
    assert Status.NULLS_DROPPED in result.status
    np.testing.assert_allclose(result.nulls_deg, [-25], atol=0.5)
    assert best - sinr < 1  # the covariance still rejects the other one


def test_interferer_in_main_lobe_falls_back():
    result, _, _ = run_scene(CONFIG, [0, 4], [1, 1000], calibration=np.ones(4))
    assert Status.FALLBACK_DAS in result.status
    np.testing.assert_allclose(result.weights, das_weights(np.ones(4)), atol=1e-12)


def test_calibration_restores_performance():
    gains = random_channel_gains(8, 1.0, 40.0, rng=4)
    config = replace(CONFIG, num_elements=8)
    angles, powers = [0, -35], [1, 1000]
    raw, raw_sinr, best = run_scene(config, angles, powers, channel_gains=gains)
    assert Status.UNCALIBRATED in raw.status

    pipeline = BeamformingPipeline(config)
    reference = next(iter(SimulatedSource(config, [10.0], [1000.0], 1, channel_gains=gains, rng=9)))
    estimate = pipeline.calibrate_from(reference, 10.0)
    result, sinr, best = run_scene(
        config, angles, powers, channel_gains=gains, calibration=estimate
    )
    assert result.status == Status.NOMINAL
    assert best - sinr < 1 and sinr > raw_sinr + 2


def test_bad_blocks_do_not_disturb_adaptation():
    pipeline = BeamformingPipeline(CONFIG, np.ones(4))
    good = list(SimulatedSource(CONFIG, [0, -35], [1, 1000], 5, rng=0))
    for frame in good:
        reference = pipeline.process(frame).weights
    corrupted = np.full((4, 256), 1e6 + 0j)
    result = pipeline.process(make_frame(corrupted, 5, FrameFlag.ADC_OVERFLOW))
    assert Status.ADC_OVERFLOW | Status.WEIGHTS_HELD in result.status
    np.testing.assert_array_equal(result.weights, reference)

    corrupted[0, 0] = np.nan
    result = pipeline.process(make_frame(corrupted, 6))
    assert Status.INVALID_DATA in result.status
    assert np.all(result.output == 0)
    np.testing.assert_array_equal(result.weights, reference)


def test_clock_loss_invalidates_calibration():
    pipeline = BeamformingPipeline(CONFIG, np.ones(4))
    result = pipeline.process(make_frame(flags=FrameFlag.CLOCK_UNLOCKED))
    assert Status.CLOCK_UNLOCKED | Status.UNCALIBRATED | Status.WEIGHTS_HELD in result.status
    assert Status.UNCALIBRATED in pipeline.process(make_frame(sequence=1)).status


def test_sequence_gap_and_wrap():
    pipeline = BeamformingPipeline(CONFIG, np.ones(4))
    assert Status.SEQUENCE_GAP not in pipeline.process(make_frame(sequence=0xFFFFFFFF)).status
    assert Status.SEQUENCE_GAP not in pipeline.process(make_frame(sequence=0)).status
    assert Status.SEQUENCE_GAP in pipeline.process(make_frame(sequence=2)).status


def test_gain_change_resets_the_covariance():
    pipeline = BeamformingPipeline(CONFIG, np.ones(4))
    pipeline.process(make_frame(1000 * complex_noise((4, 256), 1.0, 0)))
    pipeline.process(make_frame(sequence=1, flags=FrameFlag.GAIN_CHANGED))
    assert np.trace(pipeline._covariance.value).real < 1


def test_silence_keeps_the_weights():
    result = BeamformingPipeline(CONFIG, np.ones(4)).process(make_frame(np.zeros((4, 256))))
    assert Status.WEIGHTS_HELD in result.status


def test_setup_errors_are_raised():
    pipeline = BeamformingPipeline(CONFIG)
    with pytest.raises(ValueError):
        pipeline.process(make_frame(np.ones((3, 256))))
    for bad in (np.ones(3), np.full(4, np.nan)):
        with pytest.raises(ValueError):
            pipeline.set_calibration(bad)


# --------------------------------------------------------------------- applications


def test_receiver_application(tmp_path, capsys):
    assert pi_receiver.main(["--frames", "4"]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(lines) == 4 and lines[-1]["method"] == "lcmv"

    record(SimulatedSource(CONFIG, [0, -35], [1, 1000], 2, rng=0), tmp_path / "c.abf")
    np.save(tmp_path / "g.npy", np.ones(4))
    arguments = ["--source", "file", "--path", str(tmp_path / "c.abf")]
    assert pi_receiver.main([*arguments, "--calibration", str(tmp_path / "g.npy")]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["status"] == []

    assert pi_receiver.main(["--config", str(tmp_path / "missing.toml")]) == 1
    assert "error" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        pi_receiver.main(["--source", "file"])


def test_batched_mvdr_matches_single_solves():
    X = np.stack([complex_noise((4, 64), 1.0, seed) for seed in range(6)])
    a = np.exp(1j * np.random.default_rng(0).uniform(0, 6, (6, 4)))
    w, y = orin_pipeline.batched_mvdr(X, a, 1e-2)
    for p in range(6):
        R = compute_covariance_matrix(X[p])
        expected = mvdr_weights(R, a[p], loading_level(R, 1e-2))
        np.testing.assert_allclose(w[p], expected, atol=1e-12)
        np.testing.assert_allclose(y[p], expected.conj() @ X[p], atol=1e-12)
    with pytest.raises(ValueError):
        orin_pipeline.batched_mvdr(X, a[:, :3])


def test_subband_steering_corrects_beam_squint():
    """With one fixed vector the loss is the Dirichlet kernel: 4.1 dB for this wideband case."""
    n, d, theta, fc, fs, subbands = 16, 0.0625, np.radians(50), 2.4e9, 400e6, 32
    a = orin_pipeline.subband_steering(np.arange(n) * d, theta, fc, fs, subbands)
    assert np.allclose(np.abs(np.sum((a / n).conj() * a, axis=1)), 1)
    fixed = np.abs(a @ a[0].conj() / n)
    psi = 2 * np.pi * np.fft.fftfreq(subbands, 1 / fs)[1:] * d * np.sin(theta) / 299_792_458.0
    dirichlet = np.abs(np.sin(n * psi / 2) / (n * np.sin(psi / 2)))
    np.testing.assert_allclose(fixed[1:], dirichlet, rtol=1e-9)
    assert to_db(fixed.min() ** 2) == pytest.approx(-4.1, abs=0.1)


def test_channelizer_places_tones():
    x = np.tile(np.exp(2j * np.pi * 5 / 32 * np.arange(512)), (4, 1))
    energy = np.sum(np.abs(orin_pipeline.channelize(x, 32)) ** 2, axis=(1, 2))
    assert np.argmax(energy) == 5


def test_backend_selection(capsys):
    assert orin_pipeline.get_backend("numpy") is np
    with pytest.raises(ValueError):
        orin_pipeline.get_backend("tensor")
    assert orin_pipeline.main(["--backend", "numpy", "--subbands", "8"]) == 0
    assert json.loads(capsys.readouterr().out)["backend"] == "numpy"
