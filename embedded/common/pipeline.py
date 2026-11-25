"""Block-based adaptive receive chain (course chapter 24).

calibrate -> covariance -> count sources -> locate them -> constrain -> solve -> apply

Two corrections to course listing 24.1: sources are counted on the *unloaded* covariance,
and directions come from root-MUSIC rather than from the largest spectrum samples.

Degradation is explicit. When a step cannot be trusted the pipeline moves down the ladder
LCMV -> loaded MVDR -> delay-and-sum, or keeps the previous weights, and says so in
:class:`Status`. It never raises for bad *data*, only for a programming or setup error.
"""

import time
from dataclasses import dataclass, field
from enum import Flag, auto

import numpy as np

from dsp.adaptive_weights import das_weights, lcmv_weights, mvdr_weights
from dsp.calibration import apply_calibration, estimate_calibration
from dsp.covariance_matrix import RecursiveCovariance, loading_level
from dsp.signal_metrics import from_db, to_db, white_noise_gain
from embedded.common.iq_frame import FrameFlag
from simulations.antenna_array.linear_array import LinearArray
from simulations.beamforming.lcmv import LCMVBeamformer
from simulations.doa.music import root_music
from simulations.doa.order_estimation import estimate_order_mdl


class Status(Flag):
    NOMINAL = 0
    UNCALIBRATED = auto()  # no calibration loaded, or invalidated by a clock loss
    SEQUENCE_GAP = auto()  # frames were lost
    ADC_OVERFLOW = auto()  # clipped block: not used for adaptation
    CLOCK_UNLOCKED = auto()  # channel phases meaningless: adaptation stopped
    INVALID_DATA = auto()  # NaN or infinity in the block: output muted
    TOO_MANY_SOURCES = auto()  # array saturated: no explicit null, no derivative constraint
    NULLS_DROPPED = auto()  # more interferers than degrees of freedom
    FALLBACK_MVDR = auto()
    FALLBACK_DAS = auto()
    WEIGHTS_HELD = auto()


@dataclass
class BlockResult:
    output: np.ndarray
    weights: np.ndarray
    status: Status
    method: str = "held"
    num_sources: int = 0
    doas_deg: np.ndarray = field(default_factory=lambda: np.empty(0))
    nulls_deg: np.ndarray = field(default_factory=lambda: np.empty(0))
    wng_db: float = float("nan")
    latency_s: float = 0.0
    sequence: int = 0


class BeamformingPipeline:
    """Stateful processing of successive :class:`IQFrame` objects."""

    def __init__(self, config, calibration=None):
        self.config = config
        self.array = LinearArray(config.num_elements, config.spacing_m)
        self.a_target = self.array.compute_steering_vector(
            config.target_deg, config.wavelength_m, "deg"
        )
        self._lcmv = LCMVBeamformer(self.array, derivative_constraint=config.derivative_constraint)
        self._lcmv_saturated = LCMVBeamformer(self.array)
        self._covariance = RecursiveCovariance(config.num_elements, config.covariance_beta)
        self._last_sequence: int | None = None
        self.calibration: np.ndarray | None = None
        if calibration is not None:
            self.set_calibration(calibration)
        self.weights = das_weights(self.a_target)

    # ------------------------------------------------------------------ calibration

    def set_calibration(self, gains):
        """Use known channel gains; the covariance history is discarded."""
        gains = np.asarray(gains, dtype=complex)
        if gains.shape != (self.config.num_elements,) or not np.all(np.isfinite(gains)):
            raise ValueError("calibration must hold one finite gain per channel")
        self.calibration = gains
        self._covariance.reset()

    def calibrate_from(self, frame, source_deg):
        """Estimate the channel gains from a block dominated by one known source."""
        a = self.array.compute_steering_vector(source_deg, self.config.wavelength_m, "deg")
        self.set_calibration(estimate_calibration(frame.samples.astype(complex), a))
        return self.calibration

    # ------------------------------------------------------------------- processing

    def process(self, frame):
        """Process one frame and return its beamformed output with diagnostics."""
        start = time.perf_counter()
        X = np.asarray(frame.samples, dtype=complex)
        if X.ndim != 2 or X.shape[0] != self.config.num_elements:
            raise ValueError(f"expected {self.config.num_elements} channels, got shape {X.shape}")
        status = self._track_link(frame)
        result = BlockResult(
            output=np.zeros(X.shape[1], dtype=complex),
            weights=self.weights,
            status=status,
            sequence=frame.sequence,
        )
        if not np.all(np.isfinite(X)):
            result.status |= Status.INVALID_DATA | Status.WEIGHTS_HELD
        else:
            if self.calibration is not None:
                X = apply_calibration(X, self.calibration)
            if status & (Status.ADC_OVERFLOW | Status.CLOCK_UNLOCKED):
                result.status |= Status.WEIGHTS_HELD
            else:
                self._adapt(X, result)
            result.weights = self.weights
            result.output = self.weights.conj() @ X
        result.wng_db = float(to_db(white_noise_gain(self.weights, self.a_target)))
        result.latency_s = time.perf_counter() - start
        return result

    def _track_link(self, frame):
        status = Status.NOMINAL
        if self._last_sequence is not None:
            if frame.sequence != (self._last_sequence + 1) & 0xFFFFFFFF:
                status |= Status.SEQUENCE_GAP
        self._last_sequence = frame.sequence
        if frame.flags & FrameFlag.ADC_OVERFLOW:
            status |= Status.ADC_OVERFLOW
        if frame.flags & FrameFlag.CLOCK_UNLOCKED:
            # LO/ADC phases restart at random after relock: the calibration is lost
            status |= Status.CLOCK_UNLOCKED
            self.calibration = None
            self._covariance.reset()
        if frame.flags & FrameFlag.GAIN_CHANGED:
            self._covariance.reset()
        if self.calibration is None:
            status |= Status.UNCALIBRATED
        return status

    def _adapt(self, X, result):
        R = self._covariance.update(X)
        if np.trace(R).real <= np.finfo(float).tiny:  # no signal at all: nothing to learn
            result.status |= Status.WEIGHTS_HELD
            return
        interferers = self._locate(R, X.shape[1], result)
        loading = loading_level(R, self.config.relative_loading)
        for method, solve in (
            ("lcmv", lambda: self._solve_lcmv(R, interferers, loading, result)),
            ("mvdr", lambda: mvdr_weights(R, self.a_target, loading)),
        ):
            try:
                w = solve()
            except (np.linalg.LinAlgError, ValueError):
                w = None
            if w is not None and self._acceptable(w):
                self.weights, result.method = w, method
                return
            result.status |= Status.FALLBACK_MVDR if method == "lcmv" else Status.FALLBACK_DAS
        self.weights, result.method = das_weights(self.a_target), "das"

    def _acceptable(self, w):
        minimum = self.config.min_wng_ratio * self.config.num_elements
        return np.all(np.isfinite(w)) and white_noise_gain(w, self.a_target) >= minimum

    def _locate(self, R, block_size, result):
        """Directions of interferers strong enough to deserve an explicit null."""
        n = self.config.num_elements
        snapshots = block_size * self._covariance.effective_blocks
        order = estimate_order_mdl(R, snapshots)
        result.num_sources = order
        if order >= n - 1:
            result.status |= Status.TOO_MANY_SOURCES
            return np.empty(0)
        if order == 0:
            return np.empty(0)
        doas = np.degrees(root_music(R, order, self.config.d_over_lambda))
        result.doas_deg = doas
        A = self.array.compute_steering_matrix(doas, self.config.wavelength_m, "deg")
        noise = np.mean(np.linalg.eigvalsh(R)[: n - order])
        pinv = np.linalg.pinv(A)
        powers = np.diag(pinv @ (R - noise * np.eye(n)) @ pinv.conj().T).real
        strong = powers > noise * from_db(self.config.min_interferer_inr_db)
        outside = np.abs(doas - self.config.target_deg) > self.config.guard_deg
        keep = np.flatnonzero(strong & outside)
        keep = keep[np.argsort(powers[keep])[::-1]]
        limit = min(self.config.max_interferers, n - 1 - self.config.derivative_constraint)
        if keep.size > limit:
            result.status |= Status.NULLS_DROPPED
        return doas[keep[:limit]]

    def _solve_lcmv(self, R, interferers, loading, result):
        # With as many sources as the array can handle, the degree of freedom spent on the
        # derivative constraint is worth more as a null.
        saturated = Status.TOO_MANY_SOURCES in result.status
        C, f = (self._lcmv_saturated if saturated else self._lcmv).constraints(
            self.config.target_deg, interferers, self.config.wavelength_m, "deg"
        )
        w = lcmv_weights(R, C, f, loading)
        result.nulls_deg = np.sort(interferers)
        return w
