"""End-to-end chain: uncalibrated array, calibration, then adaptive reception.

1. A reference source at a known direction calibrates eight channels with random errors.
2. The pipeline receives a weak target under a strong, slowly moving interferer.
3. Its SINR is compared with the theoretical optimum and with plain delay-and-sum.
"""

from dataclasses import replace

import matplotlib.pyplot as plt
import numpy as np

from dsp.adaptive_weights import das_weights
from dsp.calibration import calibration_residual
from dsp.signal_metrics import optimal_sinr, output_sinr, to_db
from embedded.common.config import PipelineConfig
from embedded.common.pipeline import BeamformingPipeline
from embedded.common.sources import SimulatedSource
from examples.common import SEED, show
from simulations.plot_style import REFERENCE, styled
from simulations.scenarios.array_snapshots import random_channel_gains

BLOCKS = 120


def interferer_angle(block):
    return -20 - 25 * block / BLOCKS


def main():
    config = replace(PipelineConfig(), num_elements=8)
    gains = random_channel_gains(8, gain_std_db=1.0, phase_std_deg=40.0, rng=SEED)
    pipeline = BeamformingPipeline(config)

    reference = SimulatedSource(config, [10.0], [100.0], 1, channel_gains=gains, rng=SEED)
    estimate = pipeline.calibrate_from(next(iter(reference)), 10.0)
    for label, g in (("before", np.ones(8)), ("after", estimate)):
        gain_db, phase_deg = calibration_residual(g, gains)
        print(f"{label} calibration: residual {gain_db:.2f} dB, {phase_deg:.2f} deg RMS")

    powers = [1.0, 1000.0]
    source = SimulatedSource(
        config,
        lambda block: [0.0, interferer_angle(block)],
        powers,
        BLOCKS,
        channel_gains=gains,
        rng=SEED + 1,
    )
    sinr: dict[str, list[float]] = {"optimum": [], "pipeline": [], "delay-and-sum": []}
    for block, frame in enumerate(source):
        result = pipeline.process(frame)
        scene = source.scene(block)
        a, R_in = scene.A_effective[:, 0], scene.R_interference_noise
        uncorrected = 1 / pipeline.calibration.conj()  # back to the domain of the raw scene
        sinr["optimum"].append(to_db(optimal_sinr(a, powers[0], R_in)))
        for name, w in (
            ("pipeline", result.weights),
            ("delay-and-sum", das_weights(pipeline.a_target)),
        ):
            sinr[name].append(to_db(output_sinr(w * uncorrected, a, powers[0], R_in)))
    for name, values in sinr.items():
        print(f"{name:14s} mean SINR {np.mean(values):6.2f} dB, minimum {np.min(values):6.2f} dB")

    with styled():
        _, ax = plt.subplots(figsize=(7, 4))
        for name, values in sinr.items():
            style = {"color": REFERENCE, "linestyle": "--"} if name == "optimum" else {}
            ax.plot(values, label=name, **style)
        ax.set(xlabel="Block", ylabel="SINR (dB)", title="Output SINR with a moving interferer")
        ax.legend(loc="center right")
    show()


if __name__ == "__main__":
    main()
