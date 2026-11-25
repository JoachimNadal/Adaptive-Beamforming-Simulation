"""Bartlett, Capon and MUSIC spectra, then grid-free root-MUSIC and ESPRIT."""

import matplotlib.pyplot as plt
import numpy as np

from dsp.covariance_matrix import compute_covariance_matrix
from dsp.signal_metrics import to_db
from examples.common import SEED, WAVELENGTH, reference_array, show
from simulations.doa.capon import bartlett_spectrum, capon_spectrum
from simulations.doa.crb import crb_stochastic
from simulations.doa.esprit import esprit
from simulations.doa.music import music_spectrum, root_music
from simulations.doa.order_estimation import estimate_order_mdl
from simulations.scenarios.array_snapshots import simulate_array_snapshots

TRUE_ANGLES = (-10.0, 0.0, 35.0)  # the first two are closer than the 12.8 deg beamwidth
SNAPSHOTS = 200


def main():
    array = reference_array(8)
    scene = simulate_array_snapshots(
        array, WAVELENGTH, TRUE_ANGLES, [10.0] * 3, SNAPSHOTS, noise_power=1.0, rng=SEED
    )
    R = compute_covariance_matrix(scene.X)
    order = estimate_order_mdl(R, SNAPSHOTS)
    angles = np.arange(-90, 90.1, 0.1)
    A = array.compute_steering_matrix(angles, WAVELENGTH, "deg")

    D = np.column_stack(
        [array.compute_steering_derivative(t, WAVELENGTH, "deg") for t in TRUE_ANGLES]
    )
    crb = crb_stochastic(scene.A, D, np.diag(scene.powers), 1.0, SNAPSHOTS)
    print(f"true angles      {TRUE_ANGLES}, MDL order {order}")
    print("root-MUSIC (deg)", np.round(np.degrees(root_music(R, order)), 2))
    print("TLS-ESPRIT (deg)", np.round(np.degrees(esprit(R, order)), 2))
    print("CRB std (deg)   ", np.round(np.degrees(np.sqrt(np.diag(crb))), 3))

    _, ax = plt.subplots()
    for name, spectrum in (
        ("Bartlett", bartlett_spectrum(R, A)),
        ("Capon", capon_spectrum(R, A)),
        ("MUSIC", music_spectrum(R, A, order)),
    ):
        ax.plot(angles, to_db(spectrum / spectrum.max()), label=name)
    for angle in TRUE_ANGLES:
        ax.axvline(angle, color="gray", linestyle=":")
    ax.set(xlabel="Angle (degrees)", ylabel="Normalized spectrum (dB)", title="DOA spectra")
    ax.grid(True)
    ax.legend()
    show()


if __name__ == "__main__":
    main()
