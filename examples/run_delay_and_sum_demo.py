"""Conventional beam steered to 30 degrees."""

from dsp.signal_metrics import half_power_beamwidth, peak_sidelobe_db
from examples.common import WAVELENGTH, reference_array, show
from simulations.beamforming.delay_and_sum import DelayAndSumBeamformer


def main():
    beamformer = DelayAndSumBeamformer(reference_array())
    angles, gain = beamformer.compute_beam_pattern(30, WAVELENGTH)
    print(f"beamwidth {half_power_beamwidth(angles, gain):.1f} deg")
    print(f"peak sidelobe {peak_sidelobe_db(gain):.1f} dB")
    beamformer.plot_polar_beam_pattern(30, WAVELENGTH)
    show()


if __name__ == "__main__":
    main()
