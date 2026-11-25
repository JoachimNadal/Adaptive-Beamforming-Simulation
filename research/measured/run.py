"""Study 5: the project's algorithms on measured array data (third-party measurement).

python -m research.measured.run
"""

import numpy as np

from dsp.signal_metrics import optimal_sinr, output_sinr
from research.covariance.methods import METHODS, Context, noise_loaded_weights
from research.harness import bootstrap_loss, loss_db, progress, save_results
from research.measured import dataset as ds
from simulations.doa.music import root_music

D = 2 * ds.SPACING_M * ds.CARRIER_HZ / 299792458.0  # spacing in half wavelengths
WAVELENGTH_M = 299792458.0 / ds.CARRIER_HZ
METHODS_USED = {
    "delay-and-sum": METHODS["delay-and-sum"],
    "sample": METHODS["sample"],
    "relative 1e-2": METHODS["relative 1e-2"],
    "noise x10": METHODS["noise x10"],
    "noise x30": lambda X, c: noise_loaded_weights(X, c, 30.0),
    "OAS": METHODS["OAS"],
    "eigenspace": METHODS["eigenspace"],
}


def load(name):
    """Per block: covariances (4 arrays, 8 x 8) in project conventions, and the position.

    Conventions were chosen on ``static_middle`` only: conjugate, flip the rows. Element m of the
    row vector is column m; rows are ordered so that index grows along the published up vector.
    """
    covariances, positions = [], []
    for csi, position, _ in ds.groups(name):
        x = csi.conj()[:, :, ::-1].reshape(len(csi), 4, 8, -1)
        covariances.append(np.einsum("pasn,patn->ast", x, x.conj()) / (len(csi) * x.shape[-1]))
        positions.append(position)
    return np.array(covariances), np.array(positions)


def element_offsets():
    rows, columns = np.meshgrid(np.arange(2), np.arange(4), indexing="ij")
    return (columns - 1.5).ravel(), (rows - 0.5).ravel()


def plane_wave(position):
    """(4 arrays, 8 elements) phase model from the published geometry, far field."""
    x, y = element_offsets()
    u = ds.direction_sines(position)
    return np.exp(-1j * np.pi * D * (np.outer(u[:, 0], x) + np.outer(u[:, 1], y)))


def spherical_wave(position):
    """Same with the exact distance to each element; the sign follows ``plane_wave``."""
    x, y = element_offsets()
    out = []
    for centre, right, up in ds.ARRAYS:
        right, up = (np.asarray(v) / np.linalg.norm(v) for v in (right, up))
        elements = np.asarray(centre) + ds.SPACING_M * (np.outer(x, right) + np.outer(y, up))
        distance = np.linalg.norm(np.asarray(position) - elements, axis=1)
        reference = np.linalg.norm(np.asarray(position) - centre)
        out.append(np.exp(2j * np.pi * (distance - reference) / WAVELENGTH_M))
    return np.array(out)


def principal(R):
    return np.linalg.eigh(R)[1][..., -1]


def calibration(R, position):
    """Complex gain of each element from one known position."""
    g = principal(R.mean(0)) / plane_wave(position)
    return g / np.exp(1j * np.angle(g.mean(axis=1, keepdims=True)))


def apply(R, gains):
    """Divide out the element gains, normalised so that no element amplifies noise on average."""
    g = gains / np.abs(gains).mean(axis=-1, keepdims=True)
    return R / (g[..., :, None] * g[..., None, :].conj())


def doa_errors(R, positions):
    """Errors (degrees) per block, array and row of root-MUSIC with one source."""
    errors, truths = [], []
    for block, position in zip(R, positions, strict=True):
        u = ds.direction_sines(position)[:, 0]
        for a in range(4):
            for row in range(2):
                index = slice(4 * row, 4 * row + 4)
                sine = np.sin(root_music(block[a, index, index], 1)[0]) / D
                errors.append(np.degrees(np.arcsin(np.clip(sine, -1, 1)) - np.arcsin(u[a])))
                truths.append(np.degrees(np.arcsin(u[a])))
    shape = (len(R), 4, 2)
    return np.reshape(errors, shape), np.reshape(truths, shape)


def summary(errors):
    e = np.abs(errors)
    return {
        "median": np.median(e),
        "p90": np.percentile(e, 90),
        "mean": e.mean(),
        "rmse": np.sqrt(np.mean(e**2)),
        "bias": np.median(errors),
        "median_by_array": np.median(e, axis=(0, 2)),
        "count": e.size,
    }


def phase_error(R, positions, model):
    """RMS phase (degrees) between the measured vector and the model, per block and array."""
    out = []
    for block, position in zip(R, positions, strict=True):
        residual = principal(block) * model(position).conj()
        residual *= np.exp(-1j * np.angle(residual.sum(axis=1, keepdims=True)))
        out.append(np.degrees(np.sqrt(np.mean(np.angle(residual) ** 2, axis=1))))
    return np.array(out)


def stability(R):
    """RMS drift (degrees) of the phases relative to the array mean over the static file."""
    v = principal(R)
    reference = principal(R.mean(0))
    r = v * reference.conj()
    r *= np.exp(-1j * np.angle(r.sum(axis=-1, keepdims=True)))
    phases = np.degrees(np.angle(r))
    return {
        "rms_deg": np.sqrt(np.mean((phases - phases.mean(0)) ** 2)),
        "worst_element_deg": np.max(phases.std(0)),
        "by_array_deg": np.sqrt(np.mean((phases - phases.mean(0)) ** 2, axis=(0, 2))),
    }


def packet_jitter():
    """Exploratory: packet-to-packet phase of each element against element 0, static file."""
    z = np.array([csi for csi, _, _ in ds.records("static_middle")]).reshape(-1, 4, 8, 117)
    relative = z[:, :, 1:] * z[:, :, :1].conj()
    phase = np.degrees(np.angle(np.sum(relative * relative.mean(0).conj(), axis=-1)))
    centred = phase - phase.mean(0)
    lag = np.median(np.mean(centred[1:] * centred[:-1], 0) / np.mean(centred**2, 0))
    return {
        "packets": len(z),
        "median_abs_deg": np.median(np.abs(phase)),
        "std_deg": phase.std(),
        "median_lag1_correlation": lag,
        "median_abs_by_array_deg": np.median(np.abs(phase), axis=(0, 2)),
    }


def conventions(R, positions):
    """Exploratory: beam power toward the known position for the four element orders (max 1)."""
    x, y = element_offsets()
    u = np.array([ds.direction_sines(p) for p in positions])
    out = {}
    for c in (1, -1):
        for r in (1, -1):
            s = np.exp(-1j * np.pi * D * (c * u[..., :1] * x + r * u[..., 1:] * y))
            power = np.einsum("gas,gast,gat->ga", s.conj(), R, s).real / 8
            total = np.einsum("gass->ga", R).real
            out[f"columns {c:+d} rows {r:+d}"] = np.mean(power / total)
    return out


def beamforming(
    R, positions, target_db, inr_db, trials=2000, snapshots=64, seed=0, separation=0.25
):
    """Measured channel vectors of two positions as target and interferer; synthetic waveforms.

    The data are rotated so that the plane-wave look direction, from geometry, is broadside.
    """
    rng = np.random.default_rng(0)
    context = Context(4)
    sines = np.array([ds.direction_sines(p)[:, 0] for p in positions])
    ratios = {name: [] for name in METHODS_USED}
    mismatch = []
    while len(mismatch) < trials:
        i, j = rng.integers(len(R), size=2)
        array, row = rng.integers(4), rng.integers(2)
        if abs(sines[i, array] - sines[j, array]) < separation:
            continue
        index = slice(4 * row, 4 * row + 4)
        rotate = np.exp(1j * np.pi * D * np.arange(4) * sines[i, array])
        ht, hi = (2 * rotate * principal(R[k, array][index, index]) for k in (i, j))
        mismatch.append(np.abs(ht.sum()) ** 2 / 16)
        signal, jam, noise = (
            np.sqrt(p / 2) * (rng.standard_normal(s) + 1j * rng.standard_normal(s))
            for p, s in (
                (10 ** (target_db / 10), snapshots),
                (10 ** (inr_db / 10), snapshots),
                (1.0, (4, snapshots)),
            )
        )
        X = np.outer(ht, signal) + np.outer(hi, jam) + noise
        Rn = 10 ** (inr_db / 10) * np.outer(hi, hi.conj()) + np.eye(4)
        best = optimal_sinr(ht, 10 ** (target_db / 10), Rn)
        for name, method in METHODS_USED.items():
            achieved = output_sinr(method(X, context), ht, 10 ** (target_db / 10), Rn)
            ratios[name].append(achieved / best)
    out = {"look_gain_db": {q: np.percentile(10 * np.log10(mismatch), q) for q in (10, 50)}}
    for name, values in ratios.items():
        loss = -10 * np.log10(np.maximum(values, 1e-12))
        out[name] = {
            "mean_db": loss_db(values),
            "interval": bootstrap_loss(values),
            "median": np.median(loss),
            "p90": np.percentile(loss, 90),
            "p99": np.percentile(loss, 99),
        }
    return out


def main():
    ds.fetch()
    static, static_positions = load("static_middle")
    moving, positions = load("meanders_ns1_continued")
    gains = calibration(static, static_positions.mean(0))
    calibrated = apply(moving, gains)
    progress(f"{len(static)} static blocks, {len(moving)} evaluation blocks")

    raw_errors, truths = doa_errors(moving, positions)
    cal_errors, _ = doa_errors(calibrated, positions)
    save_results(
        "measured",
        "doa",
        {
            "evaluation_blocks": len(moving),
            "true_angle_range_deg": [truths.min(), truths.max()],
            "true_angle_range_by_array": [
                [truths[:, a].min(), truths[:, a].max()] for a in range(4)
            ],
            "as published": summary(raw_errors),
            "calibrated": summary(cal_errors),
        },
    )
    save_results(
        "measured",
        "phases",
        {
            "stability": stability(static),
            "packet_jitter": packet_jitter(),
            "conventions static": conventions(static, static_positions),
            "conventions evaluation": conventions(moving, positions),
            "gain_phase_deg": np.degrees(np.angle(gains)),
            "gain_amplitude_db": 20
            * np.log10(np.abs(gains) / np.abs(gains).mean(1, keepdims=True)),
            **{
                f"{state}, {label}": {
                    "median": np.median(e),
                    "p10": np.percentile(e, 10),
                    "p90": np.percentile(e, 90),
                    "median_by_array": np.median(e, axis=0),
                }
                for state, data in (("as published", moving), ("calibrated", calibrated))
                for label, model in (("plane", plane_wave), ("spherical", spherical_wave))
                for e in [phase_error(data, positions, model)]
            },
        },
    )
    beam = {}
    for state, data in (("as published", moving), ("calibrated", calibrated)):
        for target in (10, 20):
            beam[f"{state} target={target}"] = beamforming(data, positions, target, 40)
            progress(f"beamforming {state} {target}")
    save_results("measured", "beamforming", beam)


if __name__ == "__main__":
    main()
