"""Reader of two files of the public dataset espargos-0001. The data are never committed.

F. Euchner, S. ten Brink, "CSI Dataset espargos-0001: Four antenna arrays in indoor lab room",
DaRUS, 2024, doi:10.18419/DARUS-4352, licence CC BY 4.0. Array positions and vectors are those of
the dataset page (espargos.net/datasets/data/espargos-0001).

python -m research.measured.dataset       # downloads 230 MB and checks the published MD5 sums
"""

import hashlib
import struct
import urllib.request

import numpy as np

from research.harness import ROOT, progress

RAW = ROOT / "ai" / "datasets" / "raw" / "espargos"
URL = (
    "https://darus.uni-stuttgart.de/api/access/datafile/:persistentId"
    "?persistentId=doi:10.18419/darus-4352/"
)
FILES = {  # name: (file number in the record, MD5)
    "static_middle": ("10", "e47ca0c69bdc87de2dccde80f0ef554b"),
    "meanders_ns1_continued": ("5", "a95465a61297cbf08b2c6223bb01c806"),
}
CARRIER_HZ = 2.462e9
SPACING_M = 0.06
SHAPE = (4, 2, 4, 117)  # 4 x 2 x 4 antennas, subcarriers; axis meaning is not documented

ARRAYS = (  # centre, right, up (metres; right and up as seen from the front)
    ((9.3525, -24.0696, 2.6093), (-0.9991, -0.0378, -0.0169), (-0.0328, 0.7042, 0.7092)),
    ((9.2331, -20.7883, 2.5842), (0.9971, 0.0669, 0.0353), (0.0205, -0.6801, 0.7329)),
    ((11.2143, -22.4548, 2.6041), (0.0945, -0.9941, 0.0532), (-0.8007, -0.0427, 0.5975)),
    ((7.2405, -22.7075, 2.6025), (-0.1099, 0.9939, -0.0017), (0.6823, 0.0786, 0.7268)),
)
NAMES = ("north", "south", "west", "east")


def path(name):
    return RAW / f"{name}.tfrecords"


def available():
    return all(path(name).exists() for name in FILES)


def fetch():
    """Download the missing files and verify the published checksums."""
    RAW.mkdir(parents=True, exist_ok=True)
    for name, (number, md5) in FILES.items():
        target = path(name)
        if not target.exists():
            progress(f"downloading {name}")
            urllib.request.urlretrieve(URL + number, target)
        if hashlib.md5(target.read_bytes(), usedforsecurity=False).hexdigest() != md5:
            raise ValueError(f"{target} does not have the published checksum")


def _varint(data, i):
    value = shift = 0
    while True:
        byte = data[i]
        i += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, i
        shift += 7


def fields(data):
    """(number, value) pairs of one protocol-buffer message; nested messages stay bytes."""
    i = 0
    while i < len(data):
        key, i = _varint(data, i)
        wire = key & 7
        if wire == 0:
            value, i = _varint(data, i)
        elif wire == 2:
            size, i = _varint(data, i)
            value, i = data[i : i + size], i + size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value, i = data[i : i + size], i + size
        else:
            raise ValueError("unsupported wire type")
        yield key >> 3, value


def _tensor_content(feature):
    """Raw bytes of the serialised tensor inside a ``Feature`` holding one byte string."""
    bytes_list = dict(fields(feature))[1]
    tensor = dict(fields(bytes_list))[1]
    return dict(fields(tensor))[4]


def records(name):
    """Yield (csi, position, time) of each packet."""
    with path(name).open("rb") as stream:
        while header := stream.read(12):
            (size,) = struct.unpack("<Q", header[:8])
            example = stream.read(size)
            stream.read(4)
            features = dict(fields(example))[1]
            entry = {}
            for _, item in fields(features):
                pair = dict(fields(item))
                entry[pair[1].decode()] = pair[2]
            yield (
                np.frombuffer(_tensor_content(entry["csi"]), np.complex64).reshape(SHAPE),
                np.frombuffer(_tensor_content(entry["pos"]), np.float64),
                float(np.frombuffer(_tensor_content(entry["time"]), np.float64)[0]),
            )


def groups(name, size=10):
    """Blocks of consecutive packets: (csi stacked on the first axis, mean position, time)."""
    block = []
    for record in records(name):
        block.append(record)
        if len(block) == size:
            yield (
                np.stack([r[0] for r in block]),
                np.mean([r[1] for r in block], axis=0),
                block[0][2],
            )
            block = []


def direction_sines(position):
    """Sine towards the right and up vector of each array, shape (4, 2), from published geometry."""
    out = []
    for centre, right, up in ARRAYS:
        v = np.asarray(position) - centre
        v = v / np.linalg.norm(v)
        out.append([v @ np.asarray(axis) / np.linalg.norm(axis) for axis in (right, up)])
    return np.array(out)


if __name__ == "__main__":
    fetch()
