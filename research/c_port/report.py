"""Tables of REPORT.md, generated from the result files.

python -m research.c_port.report
"""

from research.harness import ROOT, load_results, markdown_table, replace_block

REPORT = ROOT / "research" / "c_port" / "REPORT.md"


def accuracy_table():
    rows = []
    for key, v in sorted(load_results("c_port", "accuracy").items(), key=lambda t: t[0].split()[1]):
        n, mode, precision = key.split()
        rows.append(
            [
                mode,
                precision,
                n.removeprefix("N="),
                f"{100 * v['within_0.1_db']:.2f} %",
                f"{v['max_sinr_difference_db']:.4f}",
                f"{v['median_weight_difference']:.0e}",
                f"{100 * v['same_order']:.1f} %" if mode == "phase1" else "–",
                f"{100 * v['same_method']:.1f} %",
                f"{100 * v['precision_flagged']:.1f} %",
                f"{100 * v['unflagged_over_0.1_db']:.2f} %",
            ]
        )
    rows.sort(key=lambda r: (r[0], r[1], int(r[2])))
    return markdown_table(
        [
            "mode",
            "precision",
            "N",
            "blocks within 0.1 dB",
            "max difference (dB)",
            "median weight difference",
            "same order",
            "same method",
            "flagged",
            "unflagged > 0.1 dB",
        ],
        rows,
    )


def precision_table():
    data = load_results("c_port", "precision")
    rows = []
    for n in (4, 8, 16):
        for inr in (40, 60, 70, 80):
            v = data[f"N={n} INR={inr}"]
            rows.append(
                [
                    n,
                    inr,
                    *(f"{max(v['mean_loss_db'][m], 0):.3f}" for m in ("phase1", "noise", "sqrt")),
                    *(f"{max(v['max_loss_db'][m], 0):.3f}" for m in ("phase1", "noise", "sqrt")),
                ]
            )
    return markdown_table(
        ["N", "INR (dB)", "phase1 mean", "noise mean", "sqrt mean", "phase1 max", "noise max",
         "sqrt max"],
        rows,
    )  # fmt: skip


def square_root_table():
    data = load_results("c_port", "square_root")
    rows = []
    for n in (4, 8, 16):
        for inr in (40, 60, 70, 80):
            v = data[f"N={n} INR={inr}"]
            row = [n, inr]
            for m in ("covariance", "square root"):
                row += [f"{100 * v[m]['correct_order']:.0f} %", f"{v[m]['mean_loss_db']:.3f}"]
            rows.append(row)
    return markdown_table(
        ["N", "INR (dB)", "covariance: order", "covariance: loss (dB)", "square root: order",
         "square root: loss (dB)"],
        rows,
    )  # fmt: skip


def timing_table():
    t = load_results("c_port", "timing")
    rows = []
    for mode in ("phase1", "noise", "sqrt"):
        for n in (4, 8, 16):
            key = f"{mode} N={n} K=256"
            python = t["python"].get(key)
            f32, f64 = (t["c"][f"{p} {key}"] for p in ("f32", "f64"))
            rows.append(
                [
                    mode,
                    n,
                    f"{python:.0f}" if python else "–",
                    f"{f32:.1f}",
                    f"{f64:.1f}",
                    f"{t['c_native'][f'f32 {key}']:.1f}",
                    f"{python / f64:.0f} ×" if python else "–",
                    f"{256 / f32:.1f}",
                ]
            )
    return markdown_table(
        ["mode", "N", "Python (µs)", "C float32 (µs)", "C float64 (µs)",
         "float32, -march=native (µs)", "Python / float64", "float32 MS/s"],
        rows,
    )  # fmt: skip


def memory_table():
    m = load_results("c_port", "memory")
    rows = []
    for precision in ("f32", "f64"):
        v = m[precision]
        rows.append(
            [
                precision,
                v["state_bytes"],
                max(v["stack_chains_bytes"].values()),
                v["stack_chains_bytes"]["square root"],
                v["code_bytes"]["text"],
                v["code_bytes"]["data"] + v["code_bytes"]["bss"],
            ]
        )
    return markdown_table(
        ["precision", "state (bytes)", "deepest stack chain (bytes)",
         "stack, square-root mode (bytes)", "code, x86-64 -Os (bytes)", "static data (bytes)"],
        rows,
    )  # fmt: skip


def main():
    replace_block(REPORT, "accuracy", accuracy_table())
    replace_block(REPORT, "precision", precision_table())
    replace_block(REPORT, "square_root", square_root_table())
    replace_block(REPORT, "timing", timing_table())
    replace_block(REPORT, "memory", memory_table())


if __name__ == "__main__":
    main()
