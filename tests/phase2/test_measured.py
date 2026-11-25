import numpy as np
import pytest

from research.measured import dataset as ds
from research.measured import run


def varint(value):
    out = b""
    while value > 0x7F:
        out += bytes([value & 0x7F | 0x80])
        value >>= 7
    return out + bytes([value])


def message(number, payload):
    return varint(number << 3 | 2) + varint(len(payload)) + payload


def test_protocol_buffer_reader():
    content = np.arange(300, dtype=np.float32).tobytes()
    tensor = varint(1 << 3) + varint(1) + message(4, content)
    feature = message(1, message(1, tensor))
    assert ds._tensor_content(feature) == content
    assert list(ds.fields(varint(5 << 3) + varint(300))) == [(5, 300)]
    with pytest.raises(ValueError):
        list(ds.fields(varint(1 << 3 | 3)))


def test_published_axes_are_unit_and_orthogonal():
    for _, right, up in ds.ARRAYS:
        assert np.linalg.norm(right) == pytest.approx(1, abs=0.01)
        assert np.linalg.norm(up) == pytest.approx(1, abs=0.01)
        assert np.dot(right, up) == pytest.approx(0, abs=0.06)


def test_direction_sines_on_the_axes():
    centre, right, up = (np.asarray(v) for v in ds.ARRAYS[0])
    assert ds.direction_sines(centre + 3 * right)[0, 0] == pytest.approx(1)
    assert ds.direction_sines(centre + 3 * up)[0, 1] == pytest.approx(1)


def test_spherical_model_tends_to_the_plane_wave_far_away():
    centre, right, up = (np.asarray(v) for v in ds.ARRAYS[2])
    position = centre + 5000 * (np.cross(right, up) + 0.4 * right - 0.2 * up)
    product = run.spherical_wave(position)[2] * run.plane_wave(position)[2].conj()
    np.testing.assert_allclose(np.angle(product * np.conj(product[0])), 0, atol=5e-3)


def test_calibration_recovers_known_gains_and_doa():
    rng = np.random.default_rng(0)
    centre, right, up = (np.asarray(v) for v in ds.ARRAYS[1])
    normal = np.cross(right, up)
    known, unknown = centre + 2 * normal, centre + 2 * normal + 0.8 * right
    gains = np.exp(1j * rng.uniform(-0.5, 0.5, (4, 8))) * rng.uniform(0.8, 1.2, (4, 8))

    def covariance(position):
        v = gains * run.plane_wave(position)
        return (v[..., None] * v[:, None].conj() + 1e-4 * np.eye(8))[None]

    estimated = run.calibration(covariance(known), known)
    corrected = run.apply(covariance(unknown), estimated)
    errors, truths = run.doa_errors(corrected, [unknown])
    assert np.abs(truths[0, 1, 0]) > 15
    assert np.max(np.abs(errors)) < 0.1


def test_perfect_phases_have_no_error():
    centre = np.asarray(ds.ARRAYS[3][0])
    position = centre + (0.3, 0.2, -1.5)
    v = run.plane_wave(position)
    R = (v[..., None] * v[:, None].conj())[None]
    assert np.max(run.phase_error(R, [position], run.plane_wave)) < 1e-4


@pytest.mark.skipif(not ds.available(), reason="dataset not downloaded")
def test_first_record_of_the_dataset():
    csi, position, time = next(ds.records("static_middle"))
    assert csi.shape == ds.SHAPE and np.isfinite(csi).all()
    assert 1.0 < position[2] < 2.0 and time > 1.6e9
