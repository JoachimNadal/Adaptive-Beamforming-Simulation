"""Python against C on identical recordings: accuracy, time, memory.

    python -m research.c_port.run            # needs CMake and a C compiler

Frames are written once to an ABF1 file, which both implementations read.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from dsp.adaptive_weights import das_weights, mvdr_weights
from dsp.signal_metrics import optimal_sinr, output_sinr, to_db
from embedded.common.config import PipelineConfig
from embedded.common.pipeline import BeamformingPipeline, Status
from embedded.common.sources import FileSource, SimulatedSource, record
from research.covariance.estimators import noise_loaded
from research.harness import ROOT, progress, save_results
from simulations.channels.awgn import make_rng

SOURCE = ROOT / "embedded" / "pipeline_c"
METHODS = ("held", "lcmv", "mvdr", "das")


class NoiseLoadedPipeline(BeamformingPipeline):
    """Python reference of the C mode ABFP_NOISE_LOADED."""

    factor = 10.0

    def _adapt(self, X, result):
        R = self._covariance.update(X)
        snapshots = X.shape[1] * self._covariance.effective_blocks
        w = mvdr_weights(noise_loaded(R, snapshots, self.factor), self.a_target)
        if self._acceptable(w):
            self.weights, result.method = w, "mvdr"
        else:
            result.status |= Status.FALLBACK_DAS
            self.weights, result.method = das_weights(self.a_target), "das"


def build(directory, *options):
    """Configure and build; returns the directory."""
    if not shutil.which("cmake"):
        raise RuntimeError("CMake not found")
    generator = ["-G", "Ninja"] if shutil.which("ninja") else []
    for command in (
        [
            "cmake",
            "-S",
            SOURCE,
            "-B",
            directory,
            *generator,
            "-DCMAKE_BUILD_TYPE=Release",
            *options,
        ],
        ["cmake", "--build", directory],
    ):
        done = subprocess.run(command, capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError(done.stdout + done.stderr)
    return Path(directory)


def program(directory, name):
    return next(
        p
        for p in Path(directory).rglob(f"{name}*")
        if p.is_file() and p.name in (name, f"{name}.exe")
    )


def replay(directory, precision, recording, mode, config, calibrated=True):
    """Run the C tool; returns its per-block records."""
    with tempfile.TemporaryDirectory() as temporary:
        command = [
            program(directory, f"abf_replay_{precision}"),
            recording,
            Path(temporary) / "out.cf32",
            mode,
            repr(config.target_deg),
            repr(config.d_over_lambda),
            *(["calibrated"] if calibrated else []),
        ]
        done = subprocess.run([str(c) for c in command], capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError(done.stderr)
        output = np.fromfile(Path(temporary) / "out.cf32", np.complex64)
    return [json.loads(line) for line in done.stdout.splitlines()], output


def python_reference(recording, mode, config):
    pipeline = (BeamformingPipeline if mode == "phase1" else NoiseLoadedPipeline)(
        config, np.ones(config.num_elements)
    )
    return [pipeline.process(frame) for frame in FileSource(recording)]


def random_scene(rng, n):
    count = int(rng.integers(1, max(2, n - 2)))
    sines = []
    while len(sines) < count:  # at least 1.5 / N apart in sine, and from the target
        s = rng.uniform(-0.9, 0.9)
        if all(abs(s - other) > 1.5 / n for other in [0.0, *sines]):
            sines.append(s)
    return (
        [float(np.degrees(np.arcsin(s))) for s in sines],
        [float(rng.uniform(10, 60)) for _ in sines],
        float(rng.uniform(-5, 10)),
    )


def accuracy(directory, scenes=120, blocks=10):
    """Differences per block, over random scenes, for each mode, precision and array size."""
    result = {}
    with tempfile.TemporaryDirectory() as temporary:
        for n in (4, 8, 16):
            config = replace(PipelineConfig(), num_elements=n)
            rows: dict[str, dict[str, list]] = {}
            for seed in range(scenes):
                rng = make_rng([4242, n, seed])
                angles, inr, snr = random_scene(rng, n)
                powers = [10 ** (snr / 10), *(10 ** (v / 10) for v in inr)]
                source = SimulatedSource(config, [0.0, *angles], powers, blocks, rng=rng)
                recording = Path(temporary) / "scene.abf"
                record(source, recording)
                scene = source.scene()
                a, R_in = scene.A[:, 0], scene.R_interference_noise
                best = optimal_sinr(a, powers[0], R_in)
                for mode in ("phase1", "noise", "sqrt"):
                    reference = python_reference(recording, mode, config)
                    for precision in ("f32", "f64"):
                        records, output = replay(directory, precision, recording, mode, config)
                        key = f"{mode} {precision}"
                        row = rows.setdefault(
                            key,
                            {k: [] for k in ("sinr", "loss_py", "loss_c", "weights", "doa",
                                             "order", "status", "method", "output", "limited")},
                        )  # fmt: skip
                        for b, (p, c) in enumerate(zip(reference, records, strict=True)):
                            w = np.array(c["weights"]) @ [1, 1j]
                            sinr_p = to_db(output_sinr(p.weights, a, powers[0], R_in))
                            sinr_c = to_db(output_sinr(w, a, powers[0], R_in))
                            row["sinr"].append(abs(sinr_p - sinr_c))
                            row["loss_py"].append(to_db(best) - sinr_p)
                            row["loss_c"].append(to_db(best) - sinr_c)
                            row["weights"].append(
                                np.linalg.norm(w - p.weights) / np.linalg.norm(p.weights)
                            )
                            same = c["sources"] == p.num_sources or mode != "phase1"
                            row["order"].append(same)
                            row["status"].append(c["status"] & 0x3FF == p.status.value)
                            row["limited"].append(bool(c["status"] & 0x400))
                            row["method"].append(METHODS[c["method"]] == p.method)
                            doas = np.degrees(c["doas"])
                            if same and len(doas) == len(p.doas_deg) and len(doas):
                                row["doa"].append(float(np.max(np.abs(doas - p.doas_deg))))
                            size = config.block_size
                            y = output[b * size : (b + 1) * size]
                            row["output"].append(
                                np.linalg.norm(y - p.output) / np.linalg.norm(p.output)
                            )
            for key, row in rows.items():
                sinr = np.array(row["sinr"])
                result[f"N={n} {key}"] = {
                    "blocks": len(sinr),
                    "within_0.1_db": float(np.mean(sinr <= 0.1)),
                    "within_0.5_db": float(np.mean(sinr <= 0.5)),
                    "max_sinr_difference_db": float(sinr.max()),
                    "mean_loss_python_db": float(np.mean(row["loss_py"])),
                    "mean_loss_c_db": float(np.mean(row["loss_c"])),
                    "median_weight_difference": float(np.median(row["weights"])),
                    "max_weight_difference": float(np.max(row["weights"])),
                    "median_output_difference": float(np.median(row["output"])),
                    "max_doa_difference_deg": float(max(row["doa"], default=float("nan"))),
                    "same_order": float(np.mean(row["order"])),
                    "same_status": float(np.mean(row["status"])),
                    "same_method": float(np.mean(row["method"])),
                    "precision_flagged": float(np.mean(row["limited"])),
                    "unflagged_over_0.1_db": float(
                        np.mean((sinr > 0.1) & ~np.array(row["limited"]))
                    ),
                }
            progress(f"accuracy N={n}")
    return result


def precision(directory, trials=60):
    """SINR lost by float32 against float64, as a function of the interferer level."""
    result = {}
    with tempfile.TemporaryDirectory() as temporary:
        for n in (4, 8, 16):
            config = replace(PipelineConfig(), num_elements=n)
            for inr in (20, 40, 50, 60, 70, 80):
                losses: dict[str, list] = {"phase1": [], "noise": [], "sqrt": []}
                orders = []
                for seed in range(trials):
                    source = SimulatedSource(
                        config, [0.0, -35.0], [1.0, 10 ** (inr / 10)], 6, rng=[7, n, inr, seed]
                    )
                    recording = Path(temporary) / "p.abf"
                    record(source, recording)
                    scene = source.scene()
                    a, R_in = scene.A[:, 0], scene.R_interference_noise
                    for mode in losses:
                        sinr = {}
                        for bits in ("f32", "f64"):
                            records, _ = replay(directory, bits, recording, mode, config)
                            w = np.array(records[-1]["weights"]) @ [1, 1j]
                            sinr[bits] = output_sinr(w, a, 1.0, R_in)
                            orders.append((f"{mode} {bits}", records[-1]["sources"]))
                        losses[mode].append(to_db(sinr["f64"]) - to_db(sinr["f32"]))
                result[f"N={n} INR={inr}"] = {
                    "mean_loss_db": {m: float(np.mean(v)) for m, v in losses.items()},
                    "max_loss_db": {m: float(np.max(v)) for m, v in losses.items()},
                    "correct_order": {
                        key: float(np.mean([o == 2 for k, o in orders if k == key]))
                        for key in sorted({k for k, _ in orders})
                    },
                }
            progress(f"precision N={n}")
    return result


def python_timing(repeats=150):
    """Median latency per block of the Python pipelines, microseconds."""
    result = {}
    for n in (4, 8, 16):
        for k in (64, 256, 1024):
            config = replace(PipelineConfig(), num_elements=n, block_size=k)
            frames = list(SimulatedSource(config, [0.0, -35.0], [1.0, 1000.0], 8, rng=0))
            for mode, cls in (("phase1", BeamformingPipeline), ("noise", NoiseLoadedPipeline)):
                pipeline = cls(config, np.ones(n))
                latency = []
                for i in range(repeats):
                    frame = replace(frames[i % 8], sequence=i)
                    start = time.perf_counter()
                    pipeline.process(frame)
                    latency.append(time.perf_counter() - start)
                result[f"{mode} N={n} K={k}"] = float(np.median(latency[20:]) * 1e6)
    return result


def c_timing(directory):
    """Output of the benchmark programs, best of three runs."""
    result: dict[str, float] = {}
    for bits in ("f32", "f64"):
        for _ in range(3):
            done = subprocess.run(
                [str(program(directory, f"bench_pipeline_{bits}"))], capture_output=True, text=True
            )
            for line in done.stdout.splitlines():
                match = re.match(r"\s*(\d)\s+(\d+)\s+(\d+)\s+([\d.]+)\s", line)
                if match:
                    mode = ("phase1", "noise", "sqrt")[int(match[1])]
                    key = f"{bits} {mode} N={match[2]} K={match[3]}"
                    result[key] = min(result.get(key, 1e9), float(match[4]))
    return result


def timing(directory):
    result = {"python": python_timing(), "c": c_timing(directory)}
    with tempfile.TemporaryDirectory() as temporary:
        native = build(temporary, "-DABFP_NATIVE=ON")
        result["c_native"] = c_timing(native)
    return result


def total(stack, *names):
    return sum(stack.get(name, 0) for name in names)


def memory():
    """State size, worst stack frame chain and code size, from the compiler."""
    result = {}
    core = SOURCE.parent / "core"
    files = [
        SOURCE / "src" / "abfp_numeric.c",
        SOURCE / "src" / "abfp_pipeline.c",
        SOURCE / "src" / "abfp_sqrt.c",
        core / "src" / "abf_weights.c",
        core / "src" / "abf_frame.c",
    ]
    compiler = shutil.which("gcc")
    if not compiler:
        return {"error": "gcc not available"}
    for bits, define in (("f32", []), ("f64", ["-DABFP_DOUBLE"])):
        with tempfile.TemporaryDirectory() as temporary:
            stack, sizes = {}, {"text": 0, "data": 0, "bss": 0}
            for file in files:
                target = Path(temporary) / (file.stem + ".o")
                subprocess.run(
                    [compiler, "-std=c99", "-Os", "-fstack-usage", *define,
                     f"-I{SOURCE / 'include'}", f"-I{core / 'include'}", "-c", str(file),
                     "-o", str(target)],
                    check=True, capture_output=True, cwd=temporary,
                )  # fmt: skip
                for usage in Path(temporary).glob(f"{file.stem}*.su"):
                    for line in usage.read_text().splitlines():
                        name, used, _ = line.split("\t")
                        stack[name.rsplit(":", 1)[1]] = int(used)
                out = subprocess.run(["size", str(target)], capture_output=True, text=True).stdout
                text, data, bss = out.splitlines()[1].split()[:3]
                for key, value in zip(sizes, (text, data, bss), strict=True):
                    sizes[key] += int(value)
            probe = Path(temporary) / "probe.c"
            probe.write_text(
                '#include <stdio.h>\n#include "abf_pipeline.h"\n'
                'int main(void){printf("%u",(unsigned)sizeof(abfp_state));return 0;}\n'
            )
            exe = Path(temporary) / "probe.exe"
            subprocess.run(
                [compiler, "-std=c99", *define, f"-I{SOURCE / 'include'}",
                 f"-I{core / 'include'}", str(probe), "-o", str(exe)],
                check=True, capture_output=True,
            )  # fmt: skip
            state = int(subprocess.run([str(exe)], capture_output=True, text=True).stdout)

        # deepest chain: process -> adapt -> (root-MUSIC -> roots | select -> powers -> solve)
        #                                  | (lcmv -> accept -> gain)
        paths = {
            "root-MUSIC": ("adapt", "abfp_root_music", "abfp_polynomial_roots"),
            "selection": ("adapt", "select_interferers", "source_powers", "cholesky_solve"),
            "LCMV": ("adapt", "solve_lcmv", "accept", "gain_of"),
            "square root": ("adapt_sqrt", "abfp_sqrt_mvdr", "absorb_row"),
        }
        chains = {k: total(stack, "abfp_process", *names) for k, names in paths.items()}
        result[bits] = {
            "state_bytes": state,
            "stack_chains_bytes": chains,
            "code_bytes": sizes,
            "largest_frames": dict(sorted(stack.items(), key=lambda t: -t[1])[:6]),
        }
    return result


def square_root(trials=200):
    """Float32 covariance against float32 square-root processing (NumPy prototype)."""

    def analyse(values_squared, n, k):
        """MDL on eigenvalues in descending order, single precision."""
        ev = np.sort(values_squared)[::-1].astype(np.float32)
        ev = np.maximum(ev, np.finfo(np.float32).tiny)
        scores = []
        for order in range(n):
            tail = ev[order:]
            sphericity = np.log(np.mean(tail)) - np.mean(np.log(tail))
            scores.append(k * (n - order) * sphericity + 0.5 * order * (2 * n - order) * np.log(k))
        order = int(np.argmin(scores))
        return order, float(np.mean(ev[order:]))

    result = {}
    for n in (4, 8, 16):
        array_steering = np.exp(-1j * np.pi * np.outer(np.arange(n), np.sin(np.radians([0, -35]))))
        a = array_steering[:, 0]
        for inr in (40, 60, 70, 80):
            power = 10 ** (inr / 10)
            R_in = power * np.outer(array_steering[:, 1], array_steering[:, 1].conj()) + np.eye(n)
            k = 256
            counts: dict[str, list] = {"covariance": [], "square root": []}
            losses: dict[str, list] = {"covariance": [], "square root": []}
            for seed in range(trials):
                rng = make_rng([31, n, inr, seed])
                z = rng.standard_normal((n + 2, k)) + 1j * rng.standard_normal((n + 2, k))
                z = z / np.sqrt(2)
                X = np.outer(a, z[0]) + np.sqrt(power) * np.outer(array_steering[:, 1], z[1])
                X = (X + z[2:]).astype(np.complex64)
                S = X.astype(complex) @ X.conj().T.astype(complex) / k
                _, noise = analyse64(S, k)
                reference = mvdr_weights(S, a, 10 * noise)
                best = output_sinr(reference, a, 1.0, R_in)

                S32 = (X @ X.conj().T / np.float32(k)).astype(np.complex64)
                order, noise = analyse(np.linalg.eigvalsh(S32), n, k)
                counts["covariance"].append(order == 2)
                loaded = S32 + np.complex64(10 * noise) * np.eye(n, dtype=np.complex64)
                u = np.linalg.solve(loaded, a.astype(np.complex64))
                losses["covariance"].append(output_sinr(u.astype(complex), a, 1.0, R_in) / best)

                T = np.linalg.qr(X.conj().T / np.float32(np.sqrt(k)), mode="r")  # T^H T = S
                sigma = np.linalg.svd(T, compute_uv=False)
                order, noise = analyse(sigma**2, n, k)
                counts["square root"].append(order == 2)
                stacked = np.vstack((T, np.float32(np.sqrt(10 * noise)) * np.eye(n, dtype="f4")))
                L = np.linalg.qr(stacked.astype(np.complex64), mode="r")  # loading by QR
                v = np.linalg.solve(L.conj().T, a.astype(np.complex64))
                u = np.linalg.solve(L, v)
                losses["square root"].append(output_sinr(u.astype(complex), a, 1.0, R_in) / best)
            result[f"N={n} INR={inr}"] = {
                name: {
                    "correct_order": float(np.mean(counts[name])),
                    "mean_loss_db": float(-to_db(np.mean(losses[name]))),
                    "worst_loss_db": float(-to_db(max(np.min(losses[name]), 1e-12))),
                }
                for name in counts
            }
    return result


def analyse64(S, k):
    """Order and noise power in double precision (reference)."""
    from simulations.doa.order_estimation import estimate_order_mdl

    order = estimate_order_mdl(S, k)
    return order, float(np.mean(np.linalg.eigvalsh(S)[: len(S) - order]))


def main(names):
    with tempfile.TemporaryDirectory() as temporary:
        directory = build(temporary)
        for name, experiment in (
            ("accuracy", lambda: accuracy(directory)),
            ("precision", lambda: precision(directory)),
            ("timing", lambda: timing(directory)),
            ("memory", memory),
            ("square_root", square_root),
        ):
            if names and name not in names:
                continue
            start = time.perf_counter()
            save_results("c_port", name, experiment())
            progress(f"{name}: {time.perf_counter() - start:.0f} s")


if __name__ == "__main__":
    main(sys.argv[1:])
