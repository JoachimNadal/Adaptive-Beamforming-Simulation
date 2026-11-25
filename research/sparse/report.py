"""Tables and figures of REPORT.md, generated from the result files.

python -m research.sparse.report
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from research.harness import ROOT, load_results, markdown_table, replace_block
from research.sparse import arrays as sp
from simulations.plot_style import REFERENCE, SERIES, styled

REPORT = ROOT / "research" / "sparse" / "REPORT.md"
FIGURES = ROOT / "research" / "sparse" / "figures"


def geometry_table():
    data = load_results("sparse", "geometry")
    order = [k for k in sp.GEOMETRIES if k in data]
    rows = []
    for name in order:
        v = data[name]
        width = v["beamwidth_deg"]
        rows.append(
            [
                name,
                " ".join(map(str, v["positions"])),
                v["aperture"],
                v["contiguous_lags"],
                "–" if np.isnan(width) else f"{width:.1f}",
                f"{v['sidelobe_db']:.1f}",
                f"{20 * np.log10(v['worst_ambiguity']):.1f}",
                f"{v['worst_ambiguity_at_sine']:.2f}",
                "yes" if v["grating_lobe"] else "no",
            ]
        )
    return markdown_table(
        ["geometry", "positions (λ/2)", "aperture", "contiguous lags", "beamwidth (deg)",
         "sidelobe (dB)", "worst response off the main lobe (dB)", "at sine difference",
         "grating lobe"],
        rows,
    )  # fmt: skip


def stress_table(prefix, values, label, unit="", crb=False):
    data = load_results("sparse", "stress")
    header = [label, "success", "95 % interval", "weakest source found", "RMSE of successes (deg)"]
    if crb:
        header.append("Cramér–Rao bound (deg)")
    rows = []
    for value in values:
        v = data[f"{prefix}={value}"]
        row = [
            f"{value}{unit}",
            f"{100 * v['success']:.1f} %",
            f"{100 * v['interval'][0]:.0f}–{100 * v['interval'][1]:.0f} %",
            f"{100 * v['weakest_found']:.0f} %",
            f"{v['rmse_deg']:.2f}",
        ]
        if crb:
            row.append(f"{v['crb_deg']:.2f}")
        rows.append(row)
    return markdown_table(header, rows)


def combined_table():
    rows = []
    for key, v in load_results("sparse", "combined").items():
        level, sources, name = key.split(" ")
        rows.append(
            [
                sources.removeprefix("sources="),
                level,
                name,
                f"{100 * v['success']:.1f} %",
                f"{100 * v['interval'][0]:.0f}–{100 * v['interval'][1]:.0f} %",
                f"{v['median_error_deg']:.2f}",
                f"{v['rmse_deg']:.2f}",
            ]
        )
    rows.sort(key=lambda r: (r[0] == "2", r[1], r[2]))
    return markdown_table(
        ["sources", "level", "array", "success", "95 % interval", "median error (deg)",
         "RMSE, all trials (deg)"],
        rows,
    )  # fmt: skip


def comparison_table():
    data = load_results("sparse", "comparison")
    rows = []
    for separation in (2, 4, 6, 8, 16):
        for name in ("ULA-4", "nested-4", "MRA-4", "ULA-8"):
            v = data[f"{name} separation={separation}"]
            rows.append(
                [
                    separation,
                    name,
                    f"{100 * v['direct']['resolved']:.0f} %",
                    f"{v['direct']['rmse_deg']:.2f}",
                    f"{100 * v['coarray']['resolved']:.0f} %",
                    f"{v['coarray']['rmse_deg']:.2f}",
                    f"{v['crb_deg']:.2f}",
                ]
            )
    return markdown_table(
        ["separation (deg)", "array", "MUSIC resolved", "RMSE", "coarray resolved", "RMSE",
         "Cramér–Rao bound"],
        rows,
    )  # fmt: skip


def beam_table():
    data = load_results("sparse", "beamforming")
    rows = []
    for name, v in data.items():
        angles = np.array(v["angles"])
        near, far = (angles >= 5) & (angles <= 12), angles > 15
        rows.append(
            [
                name,
                *(
                    f"{np.mean(np.array(v[k])[mask]):.2f}"
                    for mask in (near, far)
                    for k in ("optimum_db", "sample_db")
                ),
                f"{np.min(np.array(v['optimum_db'])[far]):.2f}",
            ]
        )
    return markdown_table(
        ["array", "5–12°: optimum", "5–12°: K=256", "> 15°: optimum", "> 15°: K=256",
         "> 15°: worst optimum"],
        rows,
    )  # fmt: skip


def figures():
    FIGURES.mkdir(parents=True, exist_ok=True)
    stress = load_results("sparse", "stress")
    panels = (
        ("snapshots", (50, 100, 200, 500, 1000, 4000), "Snapshots", "log"),
        ("spacing", (25, 20, 15, 12, 10, 8, 6), "Angular spacing (deg)", "linear"),
        ("spread", (0, 3, 6, 10, 15, 20), "Weakest source (dB below others)", "linear"),
        ("phase", (0, 1, 2, 5, 10, 20), "Channel phase error (deg RMS)", "linear"),
    )
    with styled():
        fig, axes = plt.subplots(1, 4, figsize=(12, 3), sharey=True)
        for ax, (key, values, label, scale) in zip(axes, panels, strict=True):
            success = [100 * stress[f"{key}={v}"]["success"] for v in values]
            ax.plot(values, success, "o-", color=SERIES[0], markersize=5)
            ax.set_xscale(scale)
            ax.set(xlabel=label)
            ax.set_ylim(-5, 105)
        axes[0].set_ylabel("Success (%)")
        axes[0].set_title("Five sources, four antennas (one factor at a time)")
        fig.savefig(FIGURES / "stress.png", metadata={"Software": None})
        plt.close(fig)

        beam = load_results("sparse", "beamforming")
        fig, ax = plt.subplots(figsize=(6.6, 3.6))
        for color, name in zip(SERIES, ("ULA-4", "nested-4", "MRA-4"), strict=False):
            ax.plot(beam[name]["angles"], beam[name]["optimum_db"], color=color, label=name)
        ax.axhline(10 * np.log10(4), color=REFERENCE, linestyle="--", linewidth=1)
        ax.text(60, 6.15, "4 antennas, no interferer", color=REFERENCE, fontsize=8, ha="center")
        ax.set(xlabel="Interferer angle (deg)", ylabel="Optimum SINR (dB)",
               title="MVDR with a 30 dB interferer")  # fmt: skip
        ax.legend(loc="lower right")
        fig.savefig(FIGURES / "beamforming.png", metadata={"Software": None})
        plt.close(fig)

        u = np.linspace(0, 2, 1000)
        fig, ax = plt.subplots(figsize=(6.6, 3.4))
        for color, name in zip(
            SERIES, ("ULA-4", "MRA-4", "4 elements, wavelength spacing"), strict=False
        ):
            gain = 20 * np.log10(np.maximum(sp.ambiguity(sp.GEOMETRIES[name], u), 1e-3))
            ax.plot(u, gain, color=color, label=name)
        ax.set_ylim(-35, 2)
        ax.set(xlabel="Difference of sines", ylabel="Response (dB)", title="Ambiguity function")
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.45), ncol=3)
        fig.savefig(FIGURES / "ambiguity.png", metadata={"Software": None})
        plt.close(fig)


def main():
    figures()
    replace_block(REPORT, "geometry", geometry_table())
    replace_block(
        REPORT,
        "single",
        "\n\n".join(
            (
                stress_table("snapshots", (50, 100, 200, 500, 1000, 4000), "snapshots"),
                stress_table("snr", (-10, -5, 0, 10, 20, 40), "SNR (dB), K=1000", crb=True),
                stress_table("spacing", (25, 15, 12, 10, 8), "spacing (deg)"),
                stress_table("spread", (0, 6, 10, 15, 20), "power spread (dB), K=1000"),
                stress_table("correlation", (0.0, 0.3, 0.5, 0.9), "correlation"),
                stress_table("phase", (0, 2, 5, 10, 20), "phase error (deg RMS)"),
                stress_table("position", (0, 0.01, 0.02, 0.05), "position error (λ RMS)"),
                stress_table("coupling", (0, 0.1, 0.2, 0.3), "coupling"),
            )
        ),
    )
    replace_block(REPORT, "combined", combined_table())
    replace_block(REPORT, "comparison", comparison_table())
    replace_block(REPORT, "beam", beam_table())


if __name__ == "__main__":
    main()
