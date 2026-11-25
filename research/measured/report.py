"""Tables of REPORT.md, generated from the result files.

python -m research.measured.report
"""

from research.harness import ROOT, load_results, markdown_table, replace_block
from research.measured.dataset import NAMES

REPORT = ROOT / "research" / "measured" / "REPORT.md"


def doa_table():
    data = load_results("measured", "doa")
    rows = []
    for state in ("as published", "calibrated"):
        v = data[state]
        rows.append(
            [
                state,
                *(f"{v[k]:.1f}" for k in ("median", "p90", "mean", "rmse", "bias")),
                *(f"{m:.1f}" for m in v["median_by_array"]),
            ]
        )
    return markdown_table(
        ["data", "median", "90th percentile", "mean", "RMSE", "median signed error",
         *(f"median, {n}" for n in NAMES)],
        rows,
    )  # fmt: skip


def phase_table():
    data = load_results("measured", "phases")
    rows = []
    for state in ("as published", "calibrated"):
        for model in ("plane", "spherical"):
            v = data[f"{state}, {model}"]
            rows.append(
                [
                    state,
                    model,
                    *(f"{v[k]:.0f}" for k in ("p10", "median", "p90")),
                    *(f"{m:.0f}" for m in v["median_by_array"]),
                ]
            )
    return markdown_table(
        ["data", "wave model", "10th percentile", "median", "90th percentile",
         *(f"median, {n}" for n in NAMES)],
        rows,
    )  # fmt: skip


def stability_table():
    data = load_results("measured", "phases")
    s, j = data["stability"], data["packet_jitter"]
    return markdown_table(
        ["quantity (degrees)", "value"],
        [
            ["10-packet blocks: RMS deviation, all elements", f"{s['rms_deg']:.1f}"],
            ["same, by array", " / ".join(f"{x:.1f}" for x in s["by_array_deg"])],
            ["same, worst element", f"{s['worst_element_deg']:.1f}"],
            ["single packets: median absolute deviation", f"{j['median_abs_deg']:.1f}"],
            ["single packets: standard deviation", f"{j['std_deg']:.1f}"],
            ["single packets: lag-1 correlation (no unit)", f"{j['median_lag1_correlation']:.2f}"],
        ],
    )


def conventions_table():
    data = load_results("measured", "phases")
    static, moving = data["conventions static"], data["conventions evaluation"]
    return markdown_table(
        ["element order", "calibration file", "evaluation file"],
        [[k, f"{static[k]:.2f}", f"{moving[k]:.2f}"] for k in static],
    )


def beam_table():
    rows = []
    for key, methods in load_results("measured", "beamforming").items():
        state, target = key.rsplit(" target=", 1)
        for name, v in methods.items():
            if name != "look_gain_db":
                rows.append(
                    [
                        target,
                        state,
                        name,
                        *(f"{v[k]:.1f}" for k in ("median", "p90", "p99")),
                    ]
                )
    rows.sort(key=lambda r: (r[0], r[1]))
    return markdown_table(
        ["target (dB)", "data", "method", "median loss (dB)", "90th percentile", "99th"], rows
    )


def main():
    for name, table in (
        ("doa", doa_table()),
        ("phase", phase_table()),
        ("stability", stability_table()),
        ("conventions", conventions_table()),
        ("beam", beam_table()),
    ):
        replace_block(REPORT, name, table)


if __name__ == "__main__":
    main()
