"""Animated beam scan. Use --save PATH to write a GIF instead of opening a window."""

import argparse

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

from examples.common import WAVELENGTH, is_headless, reference_array, show
from simulations.beamforming.delay_and_sum import DelayAndSumBeamformer


def build_animation(frames=121):
    beamformer = DelayAndSumBeamformer(reference_array())
    angles_deg = np.arange(-90, 91)
    fig, ax = plt.subplots(subplot_kw={"projection": "polar"})

    def update(frame):
        ax.clear()
        target = -60 + frame
        angles, gain = beamformer.compute_beam_pattern(target, WAVELENGTH, angles_deg=angles_deg)
        beamformer.plot_polar_pattern(angles, gain, ax, f"Beam scan - target: {target} deg")
        ax.set_rmax(1.05)

    return FuncAnimation(fig, update, frames=frames, interval=50)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", metavar="PATH", help="write an animated GIF and exit")
    parser.add_argument("--frames", type=int, default=121)
    args = parser.parse_args(argv)
    animation = build_animation(args.frames)
    if args.save:
        animation.save(args.save, writer="pillow")
        plt.close("all")
    else:
        animation._draw_was_started = is_headless()  # nothing to animate without a window
        show()


if __name__ == "__main__":
    main()
