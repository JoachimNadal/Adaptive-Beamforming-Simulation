"""Tables and figures of REPORT.md, generated from the result files.

python -m research.covariance.report
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from research.harness import ROOT, load_results, markdown_table, replace_block
from simulations.plot_style import MUTED, REFERENCE, SERIES, TEXT, styled

REPORT = ROOT / "research" / "covariance" / "REPORT.md"
FIGURES = ROOT / "research" / "covariance" / "figures"
MAIN = (
    "sample",
    "relative 1e-2",
    "Phase 1 pipeline",
    "pipeline, noise loading",
    "noise x10",
    "OAS",
    "Ledoit-Wolf",
    "Toeplitz-FB",
    "Tyler",
    "eigenspace",
    "eigencanceler",
    "reconstruction",
)


def loss_table(experiment, keys, methods=MAIN, label=lambda key: key):
    data = load_results("covariance", experiment)
    rows = []
    for key in keys:
        best = min(data[key][m]["loss_db"] for m in methods)
        cells = []
        for m in methods:
            value = data[key][m]["loss_db"]
            text = f"{value:.2f}"
            cells.append(f"**{text}**" if value < best + 0.05 else text)
        rows.append([label(key), *cells])
    return markdown_table(["scene", *methods], rows)


def held_out_table(name, subset="all", methods=None):
    data = load_results("covariance", name)[subset]
    names = sorted(methods or data, key=lambda m: data[m]["p90"])
    rows = [
        [
            m,
            f"{data[m]['median']:.2f}",
            f"{data[m]['p90']:.2f}",
            f"{data[m]['p99']:.1f}",
            f"{100 * data[m]['over_10_db']:.1f} %",
        ]
        for m in names
    ]
    return markdown_table(["method", "median", "p90", "p99", "> 10 dB"], rows)


def cost_table():
    data = load_results("covariance", "cost")
    methods = [m for m in data["N=4"] if m != "delay-and-sum"]
    rows = [
        [m, *(f"{data[f'N={n}'][m]:.0f}" for n in (4, 8, 16)),
         f"{data['N=8'][m] / data['N=8']['relative 1e-2']:.1f}"]
        for m in methods
    ]  # fmt: skip
    return markdown_table(["method", "N=4 (us)", "N=8 (us)", "N=16 (us)", "ratio at N=8"], rows)


def calibration_figure():
    data = load_results("covariance", "calibration")
    phases = (0, 1, 2, 5, 10, 20)
    chosen = ("Phase 1 pipeline", "reconstruction", "noise x10", "relative 1e-2", "eigenspace")
    with styled():
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
        for ax, n in zip(axes, (4, 8), strict=True):
            for color, m in zip(SERIES, chosen, strict=True):
                losses = [data[f"N={n} phase={p} pointing=0"][m]["loss_db"] for p in phases]
                ax.plot(phases, losses, "o-", color=color, markersize=4, label=m)
            ax.set(xlabel="Channel phase error (deg RMS)", title=f"N = {n}")
        axes[0].set_ylabel("SINR loss (dB)")
        fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=5,
                   bbox_to_anchor=(0.5, -0.1))  # fmt: skip
        fig.savefig(FIGURES / "calibration.png", metadata={"Software": None})
        plt.close(fig)


def held_out_figure():
    data = load_results("covariance", "held_out")["all"]
    names = sorted((m for m in data if m != "delay-and-sum"), key=lambda m: -data[m]["p90"])
    with styled():
        fig, ax = plt.subplots(figsize=(7, 5))
        for i, m in enumerate(names):
            ax.plot([data[m]["median"], data[m]["p90"]], [i, i], color=REFERENCE, linewidth=1.2)
            ax.plot(data[m]["median"], i, "o", color=SERIES[0], markersize=7)
            ax.plot(data[m]["p90"], i, "o", color=SERIES[1], markersize=7)
        ax.set_yticks(range(len(names)), names, color=TEXT)
        ax.grid(axis="y", visible=False)
        ax.set(
            xlabel="SINR loss (dB)",
            title="2000 held-out scenes: median (blue) and 90th percentile (orange)",
        )
        ax.text(0.99, 0.02, "simulated", transform=ax.transAxes, ha="right", color=MUTED)
        fig.savefig(FIGURES / "held_out.png", metadata={"Software": None})
        plt.close(fig)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    calibration_figure()
    held_out_figure()
    replace_block(REPORT, "held_out", held_out_table("held_out"))
    replace_block(
        REPORT,
        "held_out_2",
        held_out_table("held_out_2"),
    )
    replace_block(
        REPORT,
        "snapshots",
        loss_table(
            "snapshots",
            [f"N=8 K={k}N INR={inr}" for inr in (20, 40, 60) for k in (2, 4, 32)]
            + [f"N=4 K={k}N INR={inr}" for inr in (20, 60) for k in (4, 32)],
        ),
    )
    replace_block(
        REPORT,
        "calibration",
        loss_table(
            "calibration",
            [f"N={n} phase={p} pointing=0" for n in (4, 8) for p in (0, 1, 2, 5, 10)],
        ),
    )
    replace_block(
        REPORT,
        "pointing",
        loss_table(
            "pointing", [f"N=8 SNR={s} error={e}" for s in (0, 10, 20) for e in (0, 1, 2, 4)]
        ),
    )
    replace_block(
        REPORT,
        "noise",
        loss_table(
            "noise_models",
            [
                f"N=8 K={k} {kind} INR={inr}"
                for k in (32, 256)
                for kind in ("gaussian", "student", "impulsive")
                for inr in (10, 30)
            ],
        ),
    )
    replace_block(
        REPORT,
        "special",
        loss_table("pulsed", [f"N=8 duty={d}" for d in (1.0, 0.1, 0.03)])
        + "\n\n"
        + loss_table("many", [f"N=8 interferers={c}" for c in (1, 3, 5, 6, 7)])
        + "\n\n"
        + loss_table("correlation", [f"N=8 correlation={c}" for c in (0.0, 0.3, 0.9)]),
    )
    replace_block(REPORT, "cost", cost_table())


if __name__ == "__main__":
    main()
