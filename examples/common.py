"""Reference scene shared by the demos (2.4 GHz, 4 elements at half-wavelength, in cm)."""

import matplotlib.pyplot as plt

from simulations.antenna_array.linear_array import LinearArray

WAVELENGTH = 12.5
SPACING = WAVELENGTH / 2
TARGET_DEG = 20.0
INTERFERER_DEG = -25.0  # on a delay-and-sum sidelobe; -40 is almost in a natural null
SEED = 2026


def reference_array(num_elements=4):
    return LinearArray(num_elements=num_elements, spacing=SPACING)


def mark_directions(ax, target=TARGET_DEG, interferers=(INTERFERER_DEG,)):
    """Vertical lines at the true directions."""
    ax.axvline(target, color="tab:green", linestyle=":", label="target")
    for i, angle in enumerate(interferers):
        ax.axvline(angle, color="tab:red", linestyle=":", label="interferer" if i == 0 else None)
    ax.legend()


def is_headless():
    return plt.get_backend().lower() == "agg"


def show():
    """Display figures; does nothing under a non-interactive backend (tests, CI)."""
    if not is_headless():
        plt.show()
    plt.close("all")
