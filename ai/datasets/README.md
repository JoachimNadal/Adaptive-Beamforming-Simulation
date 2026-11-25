# Datasets

`generator.py` creates labelled complex baseband on the fly; nothing is stored in git.

| Class | Parameters drawn at random |
|---|---|
| `noise` | – |
| `cw` | frequency, phase |
| `chirp` | span, direction, period, centre |
| `qpsk` | samples per symbol (4–16), offset |
| `band_noise` | bandwidth (10–50 %), centre |
| `pulsed` | period, duty (10–40 %), carrier |

Unit noise power; SNR uniform in −5 to 20 dB. Frequencies are normalised to the sample rate.
Same seed, same data.

## Adding recordings

Put them in `ai/datasets/raw/` (ignored by git) as ABF1 files
([protocol](../../docs/architecture/iq_frame_protocol.md)), with a note on origin, date,
receiver, authorisation and labelling. Do not commit third-party communications
([legal notes](../../docs/safety/legal_and_ethics.md)).
