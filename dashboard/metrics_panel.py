"""Numeric status panel."""

from simulations.plot_style import MUTED, TEXT


def format_metrics(result, block_duration_s):
    """Rows ``(name, value)`` shown by the panel."""
    load = 100 * result.latency_s / block_duration_s
    flags = ", ".join(flag.name.lower().replace("_", " ") for flag in result.status)
    return [
        ("method", result.method),
        ("sources detected", str(result.num_sources)),
        ("directions", "  ".join(f"{a:+.1f}" for a in result.doas_deg) or "none"),
        ("white noise gain", f"{result.wng_db:.1f} dB"),
        ("latency", f"{result.latency_s * 1e3:.2f} ms ({load:.0f} % of block)"),
        ("status", flags or "nominal"),
    ]


class MetricsPanel:
    def __init__(self, ax, block_duration_s):
        self.ax, self.block_duration_s = ax, block_duration_s
        ax.axis("off")
        ax.set_title("Pipeline")
        self.texts = []

    def update(self, result):
        for text in self.texts:
            text.remove()
        self.texts = []
        rows = format_metrics(result, self.block_duration_s)
        for i, (name, value) in enumerate(rows):
            y = 0.9 - 0.16 * i
            self.texts.append(self.ax.text(0.0, y, name, color=MUTED, fontsize=9))
            self.texts.append(self.ax.text(0.42, y, value, color=TEXT, fontsize=9, wrap=True))
