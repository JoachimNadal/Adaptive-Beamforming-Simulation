"""One look for every figure of the project.

The colour order was checked for colour-vision deficiency (adjacent pairs). Orange, aqua and
yellow are under 3:1 contrast on white, so series are also identified by a legend or a
direct label, never by colour alone.
"""

from typing import Any

import matplotlib as mpl
import numpy as np
from cycler import cycler
from matplotlib.colors import LinearSegmentedColormap

SERIES = ("#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac")
TEXT = "#191919"
MUTED = "#666666"
GRID = "#e6e6e6"
REFERENCE = "#8c8c8c"  # truth, bounds and other non-series marks
SEQUENTIAL = LinearSegmentedColormap.from_list("abf", ["#ffffff", "#9cc5f2", "#257de0", "#0b3a75"])

STYLE: Any = {
    "figure.dpi": 110,
    "figure.facecolor": "white",
    "axes.prop_cycle": cycler(color=SERIES),
    "axes.edgecolor": "#bdbdbd",
    "axes.labelcolor": MUTED,
    "axes.titlecolor": TEXT,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.labelsize": 9,
    "axes.grid": True,
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "grid.linestyle": "-",
    "lines.linewidth": 1.8,
    "lines.solid_capstyle": "round",
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.frameon": False,
    "legend.fontsize": 8,
    "legend.labelcolor": TEXT,
    "savefig.bbox": "tight",
}


def styled():
    """Context manager applying the style without touching global settings."""
    return mpl.rc_context(STYLE)


def mark_angles(ax, angles_deg, label=None):
    """Thin vertical reference lines at true directions."""
    for i, angle in enumerate(np.atleast_1d(angles_deg)):
        ax.axvline(
            angle,
            color=REFERENCE,
            linewidth=1.0,
            linestyle=(0, (2, 2)),
            zorder=1,
            label=label if i == 0 else None,
        )
