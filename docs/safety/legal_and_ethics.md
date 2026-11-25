# Safety, Legal and Ethical Notes

This page is a description of the project's scope, not legal advice.

## Scope

| In scope | Out of scope |
|---|---|
| Receiving, simulating and analysing signals | Transmitting |
| Rejecting interference at the receiver | Jamming or disrupting communications |
| Estimating directions of arrival | Targeting, tracking of persons |
| Classifying waveform types | Demodulating or decoding third-party communications |

The code contains no transmit path. The waveforms of
`simulations/channels/interference_models.py` are arrays used to test receivers; nothing in the
repository converts them to RF.

## Reception

Rules differ by country. Points to check before connecting a receiver:

- whether the band may be received without authorisation;
- secrecy of correspondence: receiving a signal and *using its content* are different acts;
- privacy law when locations or identifiers can be linked to people (in the EU, GDPR);
- rules of the site (airport, military, industrial).

## Calibration sources

A radiating reference source is a transmitter, whatever its power. Prefer a conducted, switched
noise source inside the receiver. Otherwise use licence-exempt bands within their limits, or an
anechoic chamber.

## Dual use

Null steering and direction finding exist in civil (Wi-Fi, 5G, radio astronomy, GNSS protection)
and military systems. Some multi-channel receivers, antennas and related technology can be
subject to export control; check before sharing *hardware* designs across borders. The algorithms
here are textbook material.

## Data

Do not commit recordings of third-party communications. `.gitignore` excludes `*.iq`, `*.bin`,
`*.wav`, `*.dat` and `captures/`; `ai/datasets/raw/` is excluded as well. Document the origin and
the authorisation of any dataset.

## Physical safety

- Antennas on masts: lightning, falls, overhead lines.
- Never connect an antenna port to a transmitter or an unknown DC bias.
- Battery-powered set-ups: fuse and charge control.

## AI results

The classifier is trained on synthetic signals and does **not** reject unknown ones: 2.8 % of
unseen waveforms were flagged, against 2.9 % of known ones. Do not base decisions affecting
people or safety on it.
