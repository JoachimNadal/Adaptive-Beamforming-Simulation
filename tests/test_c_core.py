"""Cross-checks of the C core against the Python reference, through its shared library."""

import ctypes
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from dsp.adaptive_weights import das_weights, lms_update, mvdr_weights, nlms_update, rls_update
from dsp.covariance_matrix import RecursiveCovariance, compute_covariance_matrix, loading_level
from dsp.signal_metrics import white_noise_gain
from dsp.steering import ula_steering_vector
from embedded.common.iq_frame import FrameFlag, IQFrame, SampleFormat, pack_frame
from simulations.channels.awgn import complex_noise

SOURCE = Path(__file__).parents[1] / "embedded" / "core"
ERR_ARG, ERR_NOT_POSDEF, ERR_FRAME = 1, 2, 4

pytestmark = [
    pytest.mark.ccore,
    pytest.mark.skipif(not shutil.which("cmake"), reason="CMake not available"),
    pytest.mark.skipif(
        not any(map(shutil.which, ("gcc", "clang", "cc"))), reason="no C compiler available"
    ),
]


@pytest.fixture(scope="module")
def build(tmp_path_factory):
    directory = tmp_path_factory.mktemp("abf_build")
    generator = ["-G", "Ninja"] if shutil.which("ninja") else []
    for command in (
        ["cmake", "-S", SOURCE, "-B", directory, *generator, "-DCMAKE_BUILD_TYPE=Release"],
        ["cmake", "--build", directory, "--config", "Release"],
    ):
        done = subprocess.run(command, capture_output=True, text=True)
        assert done.returncode == 0, done.stdout + done.stderr
    return directory


@pytest.fixture(scope="module")
def lib(build):
    library = next(p for p in build.rglob("*abf_shared*") if p.suffix in (".dll", ".so", ".dylib"))
    handle = ctypes.CDLL(str(library))
    handle.abf_white_noise_gain.restype = ctypes.c_float
    handle.abf_crc32.restype = ctypes.c_uint32
    return handle


def c64(x):
    return np.ascontiguousarray(x, dtype=np.complex64)


def ptr(x):
    return x.ctypes.data_as(ctypes.c_void_p)


def size(n):
    return ctypes.c_size_t(n)


def f32(x):
    return ctypes.c_float(x)


class CF32(ctypes.Structure):
    _fields_ = [("re", ctypes.c_float), ("im", ctypes.c_float)]


class Frame(ctypes.Structure):
    _fields_ = [
        ("format", ctypes.c_int),
        ("channels", ctypes.c_uint16),
        ("samples", ctypes.c_uint32),
        ("sequence", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("timestamp_ns", ctypes.c_uint64),
        ("sample_rate_hz", ctypes.c_double),
        ("center_frequency_hz", ctypes.c_double),
        ("scale", ctypes.c_float),
        ("payload", ctypes.c_void_p),
        ("payload_size", ctypes.c_size_t),
    ]


def test_c_unit_tests_pass(build):
    names = ("test_abf", "test_abf.exe")
    executable = next(p for p in build.rglob("test_abf*") if p.is_file() and p.name in names)
    done = subprocess.run([str(executable)], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout


@pytest.mark.parametrize("n", [1, 4, 8, 16])
def test_steering(lib, n):
    a = np.zeros(n, np.complex64)
    assert lib.abf_steering_ula(f32(0.7), f32(0.5), size(n), ptr(a)) == 0
    np.testing.assert_allclose(a, ula_steering_vector(0.7, n), atol=3e-6)


@pytest.mark.parametrize("n", [2, 4, 8, 16])
def test_covariance_and_weights(lib, n):
    a = c64(ula_steering_vector(0.1, n))
    b = ula_steering_vector(-0.6, n)
    r, w = np.zeros((n, n), np.complex64), np.zeros(n, np.complex64)
    reference = RecursiveCovariance(n, beta=0.5)
    reference._weight = 1.0  # the C version has no bias correction: start from R = 0
    for seed in range(4):
        X = complex_noise((n, 64), 1.0, seed) + 10 * np.outer(b, complex_noise(64, 1.0, seed + 50))
        x = c64(X.T)
        assert lib.abf_covariance_update(ptr(r), ptr(x), size(n), size(64), f32(0.5)) == 0
        expected = reference.update(x.T.astype(complex))
    np.testing.assert_allclose(r, expected, rtol=1e-4, atol=1e-3)

    assert lib.abf_mvdr_weights(ptr(r), ptr(a), size(n), f32(1e-2), ptr(w)) == 0
    R = r.astype(complex)
    expected_w = mvdr_weights(R, a.astype(complex), loading_level(R, 1e-2))
    np.testing.assert_allclose(w, expected_w, atol=2e-4 * np.linalg.norm(expected_w))

    gain = lib.abf_white_noise_gain(ptr(w), ptr(a), size(n))
    assert gain == pytest.approx(white_noise_gain(expected_w, a), rel=1e-3)

    y = np.zeros(64, np.complex64)
    assert lib.abf_apply_weights(ptr(w), ptr(x), size(n), size(64), ptr(y)) == 0
    np.testing.assert_allclose(y, w.conj() @ x.T, rtol=1e-3, atol=1e-5)

    assert lib.abf_das_weights(ptr(a), size(n), ptr(w)) == 0
    np.testing.assert_allclose(w, das_weights(a), atol=1e-6)


@pytest.mark.parametrize("inr_db", [0, 20, 40, 60])
def test_mvdr_single_precision_accuracy(lib, inr_db):
    """SINR lost by the float32 solver compared with float64, up to a 60 dB interferer."""
    n, power = 8, 10 ** (inr_db / 10)
    a, b = ula_steering_vector(0.0, n), ula_steering_vector(-0.5, n)
    R_in = power * np.outer(b, b.conj()) + np.eye(n)
    R = R_in + np.outer(a, a.conj())
    w = np.zeros(n, np.complex64)
    assert lib.abf_mvdr_weights(ptr(c64(R)), ptr(c64(a)), size(n), f32(0.0), ptr(w)) == 0

    def sinr(weights):
        return abs(np.vdot(weights, a)) ** 2 / np.vdot(weights, R_in @ weights).real

    loss_db = 10 * np.log10(sinr(mvdr_weights(R, a)) / sinr(w.astype(complex)))
    assert loss_db < 0.1


def test_recursive_filters_match_python(lib):
    n, mu, lam = 4, 0.02, 0.97
    rng = np.random.default_rng(0)
    state = {k: np.zeros(n, np.complex64) for k in ("lms", "nlms", "rls")}
    reference = {k: np.zeros(n, complex) for k in state}
    P, P_ref = np.eye(n, dtype=np.complex64) * 10, np.eye(n, dtype=complex) * 10
    e = CF32()
    for k in range(300):
        x = c64(complex_noise(n, 1.0, rng))
        d = complex(np.exp(1j * k))
        args = (ptr(x), CF32(d.real, d.imag), size(n))
        out = ctypes.byref(e)
        error = {m: d - np.vdot(reference[m], x) for m in state}
        assert lib.abf_lms_step(ptr(state["lms"]), *args, f32(mu), out) == 0
        assert complex(e.re, e.im) == pytest.approx(error["lms"], abs=1e-4)
        assert lib.abf_nlms_step(ptr(state["nlms"]), *args, f32(0.5), f32(1e-9), None) == 0
        assert lib.abf_rls_step(ptr(state["rls"]), ptr(P), *args, f32(lam), None) == 0
        reference["lms"] = lms_update(reference["lms"], x, error["lms"], mu)
        reference["nlms"] = nlms_update(reference["nlms"], x, error["nlms"], 0.5)
        reference["rls"], P_ref = rls_update(reference["rls"], P_ref, x, error["rls"], lam)
    for name, value in state.items():
        np.testing.assert_allclose(value, reference[name], atol=1e-4, err_msg=name)
    np.testing.assert_allclose(P, P_ref, atol=1e-4)
    np.testing.assert_array_equal(P, P.conj().T)


def test_errors(lib):
    a, w = c64(np.ones(4)), np.full(4, 9, np.complex64)
    singular = c64(np.outer(a, a))
    code = lib.abf_mvdr_weights(ptr(singular), ptr(a), size(4), f32(0.0), ptr(w))
    assert code == ERR_NOT_POSDEF and np.all(w == 9)
    assert lib.abf_mvdr_weights(ptr(singular), ptr(a), size(17), f32(0.1), ptr(w)) == ERR_ARG
    assert lib.abf_apply_weights(None, ptr(a), size(4), size(1), ptr(w)) == ERR_ARG


@pytest.mark.parametrize("sample_format", list(SampleFormat))
def test_frame_interoperability(lib, sample_format):
    X = complex_noise((3, 50), 0.01, 0).astype(np.complex64)
    flags = FrameFlag.ADC_OVERFLOW | FrameFlag.CALIBRATION_ON
    data = pack_frame(
        IQFrame(X, 0xFFFFFFFE, 2**60 + 1, 1e6, 2.4e9, flags), sample_format, 1 / 16384
    )
    frame = Frame()
    assert lib.abf_frame_parse(data, size(len(data)), ctypes.byref(frame)) == 0
    assert (frame.channels, frame.samples, frame.sequence) == (3, 50, 0xFFFFFFFE)
    assert (frame.timestamp_ns, frame.flags) == (2**60 + 1, int(flags))
    assert (frame.sample_rate_hz, frame.center_frequency_hz) == (1e6, 2.4e9)
    out = np.zeros((50, 3), np.complex64)
    assert lib.abf_frame_samples(ctypes.byref(frame), ptr(out), size(149)) == ERR_ARG
    assert lib.abf_frame_samples(ctypes.byref(frame), ptr(out), size(150)) == 0
    np.testing.assert_allclose(out.T, X, atol=1 / 16384)


def test_frame_corruption_is_detected_by_c(lib):
    data = pack_frame(IQFrame(complex_noise((2, 4), 1.0, 0), 1, 2, 1e6, 2.4e9))
    frame = Frame()
    for i in range(len(data)):
        corrupt = bytearray(data)
        corrupt[i] ^= 0x10
        code = lib.abf_frame_parse(bytes(corrupt), size(len(data)), ctypes.byref(frame))
        assert code == ERR_FRAME, f"byte {i}"
    for cut in (0, 10, 64, len(data) - 1):
        assert lib.abf_frame_parse(data, size(cut), ctypes.byref(frame)) == ERR_FRAME


def test_covariance_definition(lib):
    x = c64(complex_noise((32, 5), 1.0, 3))  # (snapshots, antennas)
    r = np.full((5, 5), np.nan, np.complex64)
    assert lib.abf_covariance_update(ptr(r), ptr(x), size(5), size(32), f32(0.0)) == 0
    np.testing.assert_allclose(r, compute_covariance_matrix(x.T), atol=1e-6)
    np.testing.assert_array_equal(r, r.conj().T)
