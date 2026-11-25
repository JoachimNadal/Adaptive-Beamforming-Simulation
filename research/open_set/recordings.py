"""Real recordings used to test generalisation.

    python -m research.open_set.recordings     # download what is missing (about 20 MB)

Files are listed in ``recordings.json`` with their git blob hash, which is verified after the
download. They go to ``ai/datasets/raw``, which git ignores: recordings of third parties are
evaluated locally and never redistributed from this repository. Nothing is demodulated.
"""

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from research.harness import ROOT, progress

MANIFEST = Path(__file__).with_name("recordings.json")
STORE = ROOT / "ai" / "datasets" / "raw"


def git_blob_hash(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def local_path(source, entry):
    """Flat, safe file name: remote paths never choose a directory."""
    name = "".join(c if c.isalnum() or c in "._-" else "_" for c in entry["path"])
    return STORE / source / name.replace("..", "_")


def fetch(timeout=60):
    """Download missing files; raises if a hash does not match."""
    for source, info in json.loads(MANIFEST.read_text(encoding="utf-8")).items():
        for entry in info["files"]:
            target = local_path(source, entry)
            if target.exists():
                continue
            url = (
                f"https://raw.githubusercontent.com/{info['repository']}/{info['commit']}/"
                + urllib.parse.quote(entry["path"])
            )
            with urllib.request.urlopen(url, timeout=timeout) as response:
                data = response.read(entry["size"] + 1)
            if git_blob_hash(data) != entry["git_blob"]:
                raise ValueError(f"hash mismatch for {entry['path']}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            progress(f"fetched {target.name}")


def load(source):
    """Yield ``(name, complex64 IQ)`` of a source, unsigned 8-bit offset binary."""
    info = json.loads(MANIFEST.read_text(encoding="utf-8"))[source]
    for entry in info["files"]:
        path = local_path(source, entry)
        if path.exists():
            raw = np.fromfile(path, dtype=np.uint8)[: entry["size"] // 2 * 2]
            iq = (raw.astype(np.float32) - 127.5) / 127.5
            yield entry["path"], iq[0::2] + 1j * iq[1::2]


def available():
    return any(True for _ in load("rtl_433_tests")) and any(True for _ in load("dump1090"))


def windows(iq, length=1024, hop=1024):
    """Non-overlapping windows and their powers in dB."""
    count = (len(iq) - length) // hop + 1
    if count < 1:
        return np.empty((0, length), np.complex64), np.empty(0)
    view = np.lib.stride_tricks.sliding_window_view(iq, length)[::hop][:count]
    # per-window mean removed: direct-conversion receivers have a DC spur that is not a signal
    w = view - view.mean(axis=1, keepdims=True)
    return w.astype(np.complex64), 10 * np.log10(np.mean(np.abs(w) ** 2, axis=1) + 1e-12)


def split(iq, signal_margin_db=6.0, noise_margin_db=1.0):
    """Separate signal windows from noise-only windows by power.

    The floor is the 20th percentile of window powers. Windows within 1 dB of it are noise,
    windows 6 dB above are signal, the others are ambiguous and dropped.
    """
    w, power = windows(iq)
    if len(power) < 10:
        return w[:0], w[:0]
    floor = np.percentile(power, 20)
    return w[power > floor + signal_margin_db], w[np.abs(power - floor) < noise_margin_db]


def noise_statistics(noise):
    """Kurtosis ``E|x|^4 / E|x|^2^2`` (2 for Gaussian noise) and spectral flatness in dB."""
    power = np.abs(noise) ** 2
    kurtosis = np.mean(power**2) / np.mean(power) ** 2
    psd = np.mean(np.abs(np.fft.fft(noise, axis=1)) ** 2, axis=0) + 1e-30
    return float(kurtosis), float(10 * np.log10(np.exp(np.mean(np.log(psd))) / np.mean(psd)))


def collect(max_per_file=40):
    """Curated real windows, as a dictionary of arrays with the recording index of each window.

    Curation looks at signal statistics only, never at a detector:

    * files whose floor is under -40 dB full scale are excluded: they sit on the 8-bit
      quantisation step with a kurtosis near 1.4, so they are generated or undriven;
    * duplicated files are used once;
    * noise is ``white`` if kurtosis is in 1.8 to 2.3 and flatness above -0.6 dB, else ``other``;
    * at most ``max_per_file`` windows per kind and file, so that no recording dominates.
    """
    parts: dict[str, list] = {
        "noise_white": [], "noise_other": [], "signal_ism": [], "signal_adsb": [],
    }  # fmt: skip
    origin: dict[str, list] = {key: [] for key in parts}
    seen, excluded, index = set(), 0, 0
    for source, kind in (("rtl_433_tests", "signal_ism"), ("dump1090", "signal_adsb")):
        for _, iq in load(source):
            fingerprint = hashlib.sha1(iq.tobytes(), usedforsecurity=False).hexdigest()
            _, power = windows(iq)
            if fingerprint in seen or len(power) < 10 or np.percentile(power, 20) < -40:
                excluded += 1
                continue
            seen.add(fingerprint)
            signal, noise = split(iq)
            pairs = [(kind, signal)]
            if len(noise) >= 3:
                kurtosis, flatness = noise_statistics(noise)
                clean = 1.8 <= kurtosis <= 2.3 and flatness > -0.6
                pairs.append(("noise_white" if clean else "noise_other", noise))
            for key, w in pairs:
                step = max(1, len(w) // max_per_file)
                w = w[::step][:max_per_file]
                parts[key].append(w)
                origin[key] += [index] * len(w)
            index += 1
    data = {
        key: np.concatenate(v) if v else np.empty((0, 1024), np.complex64)
        for key, v in parts.items()
    }
    return data, {k: np.array(v) for k, v in origin.items()}, {"used": index, "excluded": excluded}


if __name__ == "__main__":
    fetch()
    collected, origins, counts = collect()
    print(counts, {k: (len(v), len(set(origins[k]))) for k, v in collected.items()})
