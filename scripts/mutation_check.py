"""Re-inject known bugs and check that the test suite notices each of them.

The original suite passed while MVDR attenuated the wanted signal by 46 dB. This script
guards against that kind of blind test: every mutation below must make pytest fail.
Files are restored afterwards, even on error. Run from the repository root:

    python scripts/mutation_check.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (description, file, original text, mutated text)
MUTATIONS = [
    (
        "D1 sign flip in time-series generator",
        "simulations/scenarios/spatiotemporal_signal.py",
        "    return A @ S +",
        "    return A.conj() @ S +",
    ),
    (
        "D1b global sign flip in steering",
        "dsp/steering.py",
        "return np.exp(-2j * np.pi / wavelength * path)",
        "return np.exp(2j * np.pi / wavelength * path)",
    ),
    (
        "D3 coherent default",
        "simulations/scenarios/snapshot_generator.py",
        "coherent=False",
        "coherent=True",
    ),
    (
        "D4 doubled noise",
        "simulations/channels/awgn.py",
        "np.sqrt(power / 2)",
        "np.sqrt(power)",
    ),
    (
        "D7 unit used for scan grid",
        "simulations/beamforming/base.py",
        'angles_deg, wavelength, "deg")',
        'angles_deg, wavelength, "rad")',
    ),
    (
        "D8 unknown unit accepted",
        "dsp/steering.py",
        "if unite not in _UNITS:",
        "if False:",
    ),
    (
        "D9 no conditioning check",
        "dsp/adaptive_weights.py",
        "if not cond <= MAX_CONDITION:",
        "if False:",
    ),
    (
        "D11 no RLS symmetrisation",
        "dsp/adaptive_weights.py",
        "P = hermitian((P - np.outer(gain, u.conj())) / forgetting)",
        "P = (P - np.outer(gain, input_vector.conj()) @ P) / forgetting",
    ),
    (
        "MVDR conj error",
        "dsp/adaptive_weights.py",
        "u = np.linalg.solve(Rl, a)\n    return u",
        "u = np.linalg.solve(Rl, a).conj()\n    return u",
    ),
    (
        "E1 svd full_matrices",
        "simulations/doa/esprit.py",
        "full_matrices=True)\n",
        "full_matrices=False)\n",
    ),
    (
        "E4 grid samples not peaks",
        "simulations/doa/peaks.py",
        "interior = np.flatnonzero((s[1:-1] >= s[:-2]) & (s[1:-1] > s[2:])) + 1",
        "interior = np.arange(1, len(s) - 1)",
    ),
    (
        "E7 edge derivative",
        "simulations/beamforming/lcmv.py",
        "d = d - a * np.vdot(a, d) / np.vdot(a, a).real",
        "pass",
    ),
    (
        "LMS missing conj",
        "dsp/adaptive_weights.py",
        "return weights + mu * input_vector * np.conjugate(error)",
        "return weights + mu * input_vector * error",
    ),
    (
        "CRB transpose",
        "simulations/doa/crb.py",
        "2 * num_snapshots",
        "num_snapshots",
    ),
    (
        "ESPRIT sign",
        "simulations/doa/music.py",
        "sine = -np.angle(z)",
        "sine = np.angle(z)",
    ),
    (
        "calibration mean",
        "dsp/calibration.py",
        "g = vectors[:, -1] / a_reference",
        "g = vectors[:, 0] / a_reference",
    ),
    (
        "PSD norm",
        "dsp/fft.py",
        "np.sum(w**2)",
        "np.sum(w)**2",
    ),
    (
        "MDL penalty",
        "simulations/doa/order_estimation.py",
        "0.5 * p * np.log(num_snapshots)",
        "0 * p",
    ),
]


def is_caught(relative_path, original, mutated):
    path = ROOT / relative_path
    source = path.read_text(encoding="utf-8")
    if original not in source:
        raise SystemExit(f"mutation out of date: {original!r} not in {relative_path}")
    try:
        path.write_text(source.replace(original, mutated, 1), encoding="utf-8", newline="\n")
        command = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"]
        return subprocess.run(command, cwd=ROOT, capture_output=True).returncode == 1
    finally:
        path.write_text(source, encoding="utf-8", newline="\n")


def main():
    survivors = []
    for name, *mutation in MUTATIONS:
        caught = is_caught(*mutation)
        print(f"{'caught  ' if caught else 'SURVIVED'} {name}", flush=True)
        if not caught:
            survivors.append(name)
    print(f"{len(MUTATIONS) - len(survivors)}/{len(MUTATIONS)} mutations caught")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
