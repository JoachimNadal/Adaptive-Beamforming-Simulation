"""Pipeline configuration: one validated object, loadable from TOML."""

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

SPEED_OF_LIGHT = 299_792_458.0


class ConfigError(ValueError):
    """The configuration is inconsistent."""


@dataclass(frozen=True)
class PipelineConfig:
    """All tunable parameters. Defaults describe the 4-element, 2.4 GHz reference array."""

    num_elements: int = 4
    spacing_m: float = 0.0625
    carrier_hz: float = 2.4e9
    target_deg: float = 0.0

    block_size: int = 256  # snapshots per frame
    covariance_beta: float = 0.5  # memory of the covariance: about 1 / (1 - beta) blocks
    relative_loading: float = 1e-2  # diagonal loading relative to tr(R) / N
    max_interferers: int = 2  # explicit nulls, at most N - 2 with the derivative constraint
    guard_deg: float = 6.0  # estimates this close to the target are the target
    min_interferer_inr_db: float = 3.0  # weaker estimates do not get an explicit null
    derivative_constraint: bool = True
    min_wng_ratio: float = 0.1  # fall back when WNG < ratio * N (course 23.4.2)

    def __post_init__(self):
        checks = {
            "num_elements must be in [2, 16]": 2 <= self.num_elements <= 16,
            "spacing_m must be positive": self.spacing_m > 0,
            "carrier_hz must be positive": self.carrier_hz > 0,
            "target_deg must be in [-90, 90]": -90 <= self.target_deg <= 90,
            "block_size must be in [num_elements, 65536]": (
                self.num_elements <= self.block_size <= 1 << 16
            ),
            "covariance_beta must be in [0, 1)": 0 <= self.covariance_beta < 1,
            "relative_loading must be in (0, 1]": 0 < self.relative_loading <= 1,
            "max_interferers must be in [0, num_elements - 1]": (
                0 <= self.max_interferers < self.num_elements
            ),
            "guard_deg must be positive": self.guard_deg > 0,
            "min_wng_ratio must be in [0, 1)": 0 <= self.min_wng_ratio < 1,
        }
        failed = [message for message, ok in checks.items() if not ok]
        if failed:
            raise ConfigError("; ".join(failed))
        if self.spacing_m > self.wavelength_m / 2 * (1 + 1e-3):
            raise ConfigError(
                f"spacing {self.spacing_m} m exceeds lambda/2 = {self.wavelength_m / 2:.4f} m: "
                "angles would be ambiguous"
            )

    @property
    def wavelength_m(self):
        return SPEED_OF_LIGHT / self.carrier_hz

    @property
    def d_over_lambda(self):
        return self.spacing_m / self.wavelength_m


def load_config(path):
    """Read a TOML file; unknown keys are errors so that typos cannot pass silently."""
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: {error}") from error
    flat: dict = {}
    for key, value in data.items():
        flat.update(value if isinstance(value, dict) else {key: value})
    unknown = set(flat) - {f.name for f in fields(PipelineConfig)}
    if unknown:
        raise ConfigError(f"{path}: unknown keys {sorted(unknown)}")
    try:
        return PipelineConfig(**flat)
    except TypeError as error:
        raise ConfigError(f"{path}: {error}") from error
