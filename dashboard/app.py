"""Live view of the adaptive pipeline.

    python -m dashboard.app                       # simulated moving interferer
    python -m dashboard.app --udp 5600            # ABF1 frames from the network
    python -m dashboard.app --snapshot view.png   # no window: process and save one image

Matplotlib is used instead of PyQtGraph: at the 1-20 Hz update rate of the weights it is
fast enough and adds no dependency (docs/architecture/decisions.md).
"""

import argparse
import sys

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

from dashboard.heatmap import DoaHeatmapPanel
from dashboard.metrics_panel import MetricsPanel
from dashboard.polar_plot import PolarPatternPanel
from dashboard.spectrum_view import SpectrumPanel
from embedded.common.config import load_config
from embedded.common.pipeline import BeamformingPipeline
from embedded.common.sources import SimulatedSource, UdpSource
from embedded.raspberry_pi.pi_receiver import DEFAULT_CONFIG
from simulations.plot_style import styled


class Dashboard:
    """Four panels fed by successive frames."""

    def __init__(self, config, sample_rate_hz):
        self.pipeline = BeamformingPipeline(config, np.ones(config.num_elements))
        array, wavelength = self.pipeline.array, config.wavelength_m
        self.figure = plt.figure(figsize=(11, 7.5))
        grid = self.figure.add_gridspec(2, 2, hspace=0.35, wspace=0.25)
        self.polar = PolarPatternPanel(
            self.figure.add_subplot(grid[0, 0], projection="polar"),
            array,
            wavelength,
            config.target_deg,
        )
        self.heatmap = DoaHeatmapPanel(self.figure.add_subplot(grid[0, 1]), array, wavelength)
        self.spectrum = SpectrumPanel(self.figure.add_subplot(grid[1, 0]), sample_rate_hz)
        self.metrics = MetricsPanel(
            self.figure.add_subplot(grid[1, 1]), config.block_size / sample_rate_hz
        )

    def update(self, frame):
        result = self.pipeline.process(frame)
        self.polar.update(result.weights, result.nulls_deg)
        self.heatmap.update(frame.samples)
        self.spectrum.update(frame.samples[0], result.output)
        self.metrics.update(result)
        return result


def demo_source(config, num_frames=None):
    """A target at the configured angle and a slowly moving interferer.

    Motion must be slow compared with the covariance memory: an interferer that moves by
    about 1 degree per block spreads over two eigenvalues and is counted as two sources.
    """

    def angles(index):
        return [config.target_deg, config.target_deg - 40 + 15 * np.sin(index / 60)]

    return SimulatedSource(config, angles, [1.0, 100.0], num_frames, rng=0)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--udp", type=int, metavar="PORT")
    parser.add_argument("--snapshot", metavar="PATH", help="save one image instead of a window")
    parser.add_argument("--frames", type=int, default=80, help="frames before --snapshot")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    frames = iter(UdpSource(port=args.udp, timeout_s=30.0) if args.udp else demo_source(config))
    first = next(frames, None)
    if first is None:
        print("error: no frame received", file=sys.stderr)
        return 1
    with styled():
        dashboard = Dashboard(config, first.sample_rate_hz)
        dashboard.update(first)
        if args.snapshot:
            for _, frame in zip(range(args.frames - 1), frames, strict=False):
                dashboard.update(frame)
            dashboard.figure.savefig(args.snapshot)
            plt.close(dashboard.figure)
            return 0

        def step(_):
            frame = next(frames, None)
            if frame is not None:
                dashboard.update(frame)

        animation = FuncAnimation(dashboard.figure, step, interval=50, cache_frame_data=False)
        plt.show()
        del animation
    return 0


if __name__ == "__main__":
    sys.exit(main())
