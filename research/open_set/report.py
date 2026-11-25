"""Tables and figure of REPORT.md, generated from the result files.

python -m research.open_set.report
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from research.harness import ROOT, load_results, markdown_table, replace_block
from simulations.plot_style import REFERENCE, SERIES, TEXT, styled

REPORT = ROOT / "research" / "open_set" / "REPORT.md"
FIGURES = ROOT / "research" / "open_set" / "figures"
DETECTORS = (
    "softmax",
    "energy",
    "CNN Mahalanobis",
    "CNN k-NN",
    "features Mahalanobis",
    "features k-NN",
    "extended Mahalanobis",
    "extended k-NN",
    "fusion",
    "spectrogram residual",
)


def percent(value):
    return f"{100 * value:.1f} %"


def auroc_table(name):
    unseen = load_results("open_set", name)["unseen"]
    rows = [[family, *(f"{v['auroc'][k]:.2f}" for k in DETECTORS)] for family, v in unseen.items()]
    for label, reduce in (("mean", np.mean), ("worst", np.min)):
        values = [reduce([v["auroc"][k] for v in unseen.values()]) for k in DETECTORS]
        rows.append([f"**{label}**", *(f"**{v:.2f}**" for v in values)])
    detected = [np.mean([v["detected"][k] for v in unseen.values()]) for k in DETECTORS]
    rows.append(["mean detected at 5 % false alarms", *(percent(v) for v in detected)])
    return markdown_table(["family", *DETECTORS], rows)


def impairment_table():
    base, augmented = (load_results("open_set", n) for n in ("baseline", "augmented"))
    chosen = ("softmax", "CNN k-NN", "extended Mahalanobis")
    rows = []
    for name in base["impaired"]:
        row = [name]
        for data in (base, augmented):
            row.append(percent(data["impaired"][name]["accuracy"]))
            row += [percent(data["impaired"][name]["false_alarm"][k]) for k in chosen]
        rows.append(row)
    header = ["impairment"]
    for label in ("baseline", "augmented"):
        header += [f"{label}: accuracy", *(f"{label}: {k}" for k in chosen)]
    return markdown_table(header, rows)


def real_table(kind):
    chosen = ("softmax", "energy", "CNN Mahalanobis", "CNN k-NN", "extended Mahalanobis",
              "extended k-NN", "fusion")  # fmt: skip
    rows = []
    for name in ("baseline", "augmented"):
        real = load_results("open_set", name)["real"]
        for part in (
            ("noise_white", "noise_other")
            if kind == "noise"
            else (
                "signal_ism",
                "signal_adsb",
            )
        ):
            e = real[part]
            cells = []
            for k in chosen:
                text = percent(e["flagged"][k])
                if e["interval"][k]:
                    low, high = e["interval"][k]
                    text += f" ({100 * low:.0f}–{100 * high:.0f})"
                cells.append(text)
            rows.append([name, part, f"{e['windows']} / {e['recordings']}", *cells])
    return markdown_table(["CNN", "set", "windows / recordings", *chosen], rows)


def prediction_table():
    rows = []
    for name in ("baseline", "augmented"):
        real = load_results("open_set", name)["real"]
        for part in ("noise_white", "noise_other", "signal_ism", "signal_adsb"):
            counts = np.array(real[part]["predicted"])
            rows.append([name, part, *(percent(c) for c in counts / counts.sum())])
    return markdown_table(
        ["CNN", "set", "noise", "cw", "chirp", "qpsk", "band_noise", "pulsed"], rows
    )


def leave_one_out_table():
    data = load_results("open_set", "leave_one_out")
    rows = [
        [name, percent(v["accuracy"]), *(f"{v['auroc'][k]:.2f}" for k in DETECTORS[:-1])]
        for name, v in data.items()
    ]
    worst = [min(v["auroc"][k] for v in data.values()) for k in DETECTORS[:-1]]
    rows.append(["**worst**", "", *(f"**{v:.2f}**" for v in worst)])
    return markdown_table(["class removed", "accuracy on others", *DETECTORS[:-1]], rows)


def figure():
    data = load_results("open_set", "baseline")["unseen"]
    chosen = ("softmax", "CNN k-NN", "extended k-NN")
    families = sorted(data, key=lambda f: data[f]["auroc"]["CNN k-NN"])
    with styled():
        fig, ax = plt.subplots(figsize=(7, 4.4))
        for i, family in enumerate(families):
            values = [data[family]["auroc"][k] for k in chosen]
            ax.plot([min(values), max(values)], [i, i], color=REFERENCE, linewidth=1)
        for color, marker, k in zip(SERIES, ("o", "s", "^"), chosen, strict=False):
            ax.plot(
                [data[f]["auroc"][k] for f in families], range(len(families)), marker,
                color=color, markersize=7, label=k,
            )  # fmt: skip
        ax.axvline(0.5, color=REFERENCE, linestyle=(0, (2, 2)), linewidth=1)
        ax.set_yticks(range(len(families)), families, color=TEXT)
        ax.grid(axis="y", visible=False)
        ax.set(xlabel="AUROC against known classes", title="Unseen synthetic families")
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.28), ncol=3)
        FIGURES.mkdir(parents=True, exist_ok=True)
        fig.savefig(FIGURES / "unseen.png", metadata={"Software": None})
        plt.close(fig)


def main():
    figure()
    replace_block(REPORT, "auroc", auroc_table("baseline"))
    replace_block(REPORT, "auroc_augmented", auroc_table("augmented"))
    replace_block(REPORT, "impaired", impairment_table())
    replace_block(REPORT, "real_noise", real_table("noise"))
    replace_block(REPORT, "real_signal", real_table("signal"))
    replace_block(REPORT, "predictions", prediction_table())
    replace_block(REPORT, "leave_one_out", leave_one_out_table())


if __name__ == "__main__":
    main()
