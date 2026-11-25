"""Peak extraction from a sampled angular spectrum."""

import numpy as np


def find_spectrum_peaks(angles, spectrum, max_peaks, min_separation=0.0):
    """Angles of the highest *local maxima*, sorted by angle.

    Each peak is refined by a parabola through the three log-spectrum samples around it.
    Selecting the largest grid samples instead would return neighbours of a single peak
    (course listing 24.1). Fewer than ``max_peaks`` values are returned if the spectrum has
    fewer local maxima.
    """
    angles, s = np.asarray(angles, dtype=float), np.log(np.asarray(spectrum, dtype=float))
    interior = np.flatnonzero((s[1:-1] >= s[:-2]) & (s[1:-1] > s[2:])) + 1
    selected: list[int] = []
    for i in interior[np.argsort(s[interior])[::-1]]:
        if len(selected) == max_peaks:
            break
        if all(abs(angles[i] - angles[j]) > min_separation for j in selected):
            selected.append(i)
    refined = []
    for i in selected:
        curvature = s[i - 1] - 2 * s[i] + s[i + 1]
        offset = 0.5 * (s[i - 1] - s[i + 1]) / curvature if curvature < 0 else 0.0
        refined.append(angles[i] + offset * (angles[i + 1] - angles[i]))
    return np.sort(refined)
