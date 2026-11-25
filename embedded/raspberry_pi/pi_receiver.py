"""Receiver application for a Linux single-board computer.

Reads ABF1 frames from a source, runs the adaptive pipeline and prints one JSON line of
telemetry per frame. Runs identically on a PC; **it has not been run on a Raspberry Pi**.

    python -m embedded.raspberry_pi.pi_receiver --source sim --frames 20
    python -m embedded.raspberry_pi.pi_receiver --source udp --port 5600
    python -m embedded.raspberry_pi.pi_receiver --benchmark
"""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

from embedded.common.config import ConfigError, PipelineConfig, load_config
from embedded.common.iq_frame import FrameError
from embedded.common.pipeline import BeamformingPipeline
from embedded.common.sources import FileSource, SimulatedSource, UdpSource

DEFAULT_CONFIG = Path(__file__).parents[1] / "config" / "reference_2g4.toml"


def telemetry(result, frame):
    """JSON-serialisable summary of one block."""
    duration = frame.samples.shape[1] / frame.sample_rate_hz
    return {
        "seq": result.sequence,
        "t_ns": frame.timestamp_ns,
        "method": result.method,
        "status": [flag.name for flag in result.status],
        "sources": result.num_sources,
        "doa_deg": np.round(result.doas_deg, 2).tolist(),
        "nulls_deg": np.round(result.nulls_deg, 2).tolist(),
        "wng_db": round(result.wng_db, 2),
        "output_power_db": round(
            float(10 * np.log10(np.mean(np.abs(result.output) ** 2) + 1e-30)), 2
        ),
        "latency_ms": round(result.latency_s * 1e3, 3),
        "realtime": result.latency_s < duration,
    }


def run(source, pipeline, emit):
    """Process every frame of a source; returns the number processed."""
    count = 0
    for frame in source:
        emit(telemetry(pipeline.process(frame), frame))
        count += 1
    return count


def benchmark(config, blocks=200):
    """Processing latency on this machine for several array sizes."""
    rows = []
    for n in (4, 8, 16):
        for block in (64, 256, 1024):
            cfg = replace(config, num_elements=n, block_size=block)
            source = SimulatedSource(cfg, [0.0, -35.0], [1.0, 1000.0], blocks, rng=0)
            pipeline = BeamformingPipeline(cfg, np.ones(n))
            latency = [pipeline.process(f).latency_s for f in list(source)][blocks // 10 :]
            median, p99 = np.percentile(latency, [50, 99])
            rows.append(
                {
                    "antennas": n,
                    "block": block,
                    "median_ms": round(median * 1e3, 3),
                    "p99_ms": round(p99 * 1e3, 3),
                    "max_rate_msps": round(block / median / 1e6, 3),
                }
            )
    return rows


def build_source(args, config):
    if args.source == "file":
        return FileSource(args.path)
    if args.source == "udp":
        return UdpSource(args.host, args.port, args.timeout)
    return SimulatedSource(
        config, [config.target_deg, config.target_deg - 35.0], [1.0, 1000.0], args.frames, rng=0
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--calibration", help=".npy file with one complex gain per channel")
    parser.add_argument("--source", choices=("sim", "file", "udp"), default="sim")
    parser.add_argument("--path", help="recording, for --source file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5600)
    parser.add_argument("--timeout", type=float, default=5.0, help="UDP silence before exit (s)")
    parser.add_argument("--frames", type=int, default=20, help="frames, for --source sim")
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args(argv)
    if args.source == "file" and not args.path:
        parser.error("--source file needs --path")

    try:
        config: PipelineConfig = load_config(args.config)
        if args.benchmark:
            for row in benchmark(config):
                print(json.dumps(row))
            return 0
        gains = np.load(args.calibration) if args.calibration else None
        source = build_source(args, config)
        run(
            source,
            BeamformingPipeline(config, gains),
            lambda entry: print(json.dumps(entry), flush=True),
        )
    except (ConfigError, FrameError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
