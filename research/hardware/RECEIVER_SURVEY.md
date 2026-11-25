# Receiver survey

Desk research, 25 November 2026. **Nothing was bought, borrowed or tested.** The question: which existing
receiver could validate the algorithms of this project experimentally, at 2.4 GHz, at the lowest cost.
Requirements: [docs/hardware/requirements.md](../../docs/hardware/requirements.md) (R1–R28, tests T1–T7).

## How to read the evidence

| Mark | Meaning |
|---|---|
| **M** | stated by the manufacturer, in a document read for this survey |
| **E** | measured by someone, in a publication read for this survey (in full or in part) |
| **S** | seen only in a search-result excerpt or a summary of a page: to be confirmed |
| **P** | price and stock read on the seller's page on 25 November 2026 |
| **Pₛ** | price seen only in a search-result excerpt: date unknown, to be confirmed |
| **?** | not found |

Two sites refused automated reading (Crowd Supply, Ettus knowledge base): facts that depend on them are
marked S or Pₛ. No exchange rate is applied: prices stay in the currency of the seller. Prices in USD exclude
import VAT, duty and shipping.

## Conclusion first

1. **LimeSDR USB is not recommended as the first platform.** Two receive channels only, and the
   manufacturer itself documents four causes of inconsistent phase between them, one of them a random
   180° flip after receiver PLL toggling (M). No European stock was found.
2. **ESPARGOS One is the best candidate on paper, if the buyer is eligible** (EU organisations, including
   freelancers; not private consumers): 8 phase-synchronous channels with antennas at λ/2 and a built-in
   phase reference for €350 excl. VAT. Reservations: no published phase accuracy, and the only measured
   data from this family that could be examined ([study 5](../measured/REPORT.md), 2024 hardware)
   do not meet R1.
3. **KrakenSDR is the best-measured option** (4.2° residual phase, E) but does not reach 2.4 GHz and has
   8 bits. It becomes the choice if the project accepts another band.
4. **No examined option with confirmed facts gives four continuous, calibrated 2.4 GHz channels below about
   2000 (either currency).** A $716 board advertised as "4R2T" (hgeek, Pₛ) was not verified: one AD9361 has two
   receivers.
5. **Two channels cannot validate this project**: see the table below. They can validate calibration.
6. **Zero-cost work remains**, and it just changed a recommendation: study 5 used public measured data.

## What each number of channels can validate

| Algorithm or claim | 2 | 4 | 5 (circular) | 8 (4 × 2) |
|---|---|---|---|---|
| Phase drift, restart repeatability, calibration (T1, T2) | yes | yes | yes | yes |
| One null, one DOA | yes | yes | yes | yes |
| MDL order, two sources, MUSIC resolution | no | yes | yes | yes |
| Phase 1 reference array (uniform, N = 4) | no | yes | no | yes (one row) |
| Robust beamforming, loading choice (studies 1, 5) | marginal | yes | yes | yes |
| Minimum-redundancy array 0, 1, 4, 6 (study 4) | no | needs movable antennas | no | needs two units (8 columns) |
| Real-time C pipeline on a continuous stream (study 3) | yes | yes | yes | only if continuous |

## Comparison

### RF, channels, converters

| Platform | 2.4 GHz | Coherent RX | ADC | Instantaneous bandwidth | Host interface |
|---|---|---|---|---|---|
| LimeSDR USB | yes, 100 kHz–3.8 GHz (S) | 2, one receive PLL (S) | 12 bits (S) | chip: up to 56 MHz on the digital interface (S) | USB 3.0, Cypress FX3 (M) |
| bladeRF 2.0 micro | yes, RX 70 MHz–6 GHz (M) | 2 | 12 bits (M) | 56 MHz, 61.44 MSPS (M) | USB 3.0 (M) |
| USRP B210 | yes, 70 MHz–6 GHz (S) | 2 | ? (page refused) | ? | ? |
| ADALM-PLUTO Rev C | yes | 2, internal second channel, 2R2T mode by firmware setting (S) | ? for this board | 30.72 MSPS in 2R2T (S) | USB |
| PLUTO+ (clone) | seller: 70 MHz–6 GHz (S) | 2 (S) | ? | ? | Gigabit Ethernet (S) |
| AD-FMCOMMS5 | 70 MHz–6 GHz (S) | 4, two AD9361 (S) | 12-bit output of the AD9361 (S) | up to 56 MHz (S) | FPGA carrier needed: ZC702, ZC706 or ZCU102 (M) |
| USRP X310 + 2 × TwinRX | 10 MHz–6 GHz (S) | 4, shared LO (S) | ? | 80 MHz per channel (S) | ? |
| RFSoC 4x2 | direct sampling, 6 GHz input bandwidth (S) | 4, 5 GSPS (S) | ? | wide | Linux on board |
| KrakenSDR | **no**, 24–1766 MHz (E) | 5 | 8 bits (earlier reading) | 2.56 MHz (earlier reading) | USB |
| ESPARGOS One | 2.402–2.482 GHz (M); I/Q tuning 2310–2640 MHz (M) | 8, dual polarised, one feed at a time (M) | raw I/Q 10 + 10 bits; CSI 12 or 8 bits (M) | I/Q: 4–80 MSa/s, 13–54 MHz analog (M); CSI 20 or 40 MHz (M) | 100BASE-TX with PoE, or USB-C (M) |

### Phase

| Platform | Phase behaviour | Calibration | Measured by someone |
|---|---|---|---|
| LimeSDR USB | four documented issues: one-sample, one-clock, 0–3 clock offsets, and 0/180° after toggling the LO generator, receiver path or synthesiser (M) | software repeats resets until aligned; document of 2018, uses internal loopback at 450 MHz (M); users report random offsets at each start (S) | no bearing measurement found |
| USRP B210 | offset changes at each tune or reset, constant during operation according to users (S) | reference tone through a splitter (S) | **E**: two channels, one switched over 8 antennas: mean error 4.7°, standard deviation 4.5° in an anechoic chamber at 2.4 GHz; real-world result "impossible" to quantify |
| ADALM-PLUTO | ADI blog: offset should hold across power-ups (S) | boresight transmitter (M) | no number found |
| AD-FMCOMMS5 | **internal LO: random, changes with each LO change; external LO: 0 or 180°, randomised at power cycle** (M, partly from a summary) | two ADG918 switches and FPGA; libad9361 function (M) | no accuracy stated in the pages read |
| X310 + TwinRX | offsets repeatable on one X310, drift between two (S) | one-time estimate of constant offsets (S) | Ettus application note not read |
| KrakenSDR | one clock, noise source, switches (S) | automatic at start (E) | **E**: residual 4.16 ± 1.42° (pairs 1.67–6.94°) at 900 MHz, 71.6° uncalibrated; angle error about 2.5° on average at 900 MHz, with one unreproduced run at ±19°; 23–25° off in a hurried field test at 1575 MHz with an uncalibrated active array (angles from a summary, four directions tested) |
| ESPARGOS One | new phase after reset or frequency change: "Recalibrate" after reboot (M) | built-in 2.4 GHz reference, phase and delay; **not gain** (M) | 2024 hardware, dataset processed here: 15° median packet jitter, 9° RMS over 10 packets (**E**, study 5). The published paper gives no numbers |

### Price and availability in Europe

| Platform | Price | Stock |
|---|---|---|
| LimeSDR USB | €849 incl. VAT (hackmod.de, P); €379 incl. VAT (welectron, P); $625 to $730 in different excerpts of Crowd Supply (Pₛ) | hackmod: not in stock; welectron: out of stock; wimo (€449): no longer available (earlier reading); Crowd Supply: in stock (Pₛ) |
| bladeRF 2.0 micro xA4 | $540 (Nuand, P, page date unknown); about €931 (sdrstore, P, decimals inferred) | sdrstore: out of stock |
| USRP B210 | $2,483 (NI, Pₛ); $2,387 (Ettus quick order, Pₛ) | NI 12–13 weeks (Pₛ); Passion Radio: no longer available (P); TME: withdrawn (P) |
| ADALM-PLUTO | €233.25 (Mouser EU, Pₛ) | lead time 10 weeks (Pₛ) |
| PLUTO+ | about €384 (sdrstore, P, decimals inferred) | in stock (P) |
| AD-FMCOMMS5 | $1,872.99 (DigiKey, Pₛ) + carrier **?** | 1 expected 10 December 2026 (Pₛ) |
| X310 + 2 × TwinRX | $12,036 + 2 × $5,800 = $23,636 (Pₛ) | 18–19 weeks for the X310 (Pₛ) |
| RFSoC 4x2 | $2,499, academic staff only (Pₛ) | ? |
| KrakenSDR | €995 incl. VAT, €829.17 excl. (Passion Radio, P) | to order, 3–4 weeks (P; the page also shows 0 items) |
| ESPARGOS One | €350 excl. VAT per array; 3 arrays €1,385; 4 arrays €1,735 (M) | by quote, EU organisations only (M) |

VAT status is not shown for sdrstore. **Antennas, cables, splitter, noise source and travel to an open site are
extra in every case** except for the antennas of ESPARGOS.

## Assessment against the requirements

Scale: ✔ met on paper, ✘ not met, ~ partly or unknown.

| Requirement | LimeSDR | FMCOMMS5 | Kraken | ESPARGOS |
|---|---|---|---|---|
| R1 phase ≤ 1° (limit 5°) | ~ not found | ~ not found | average within the limit, not the target; some pairs exceed it (E) | ~ not stated |
| R3–R4 common LO, clock | ✔ one chip (S) | ✔ with external LO, 0/180° (M) | ✔ clock (S) | ✔ clock; LO phase corrected in software (M) |
| R6 phase after restart | ✘ known problem (M) | ✘ randomised (M) | ~ recalibrates itself | ✘ recalibrate (M) |
| R7 calibration source | ~ internal loopback only, external needed | ✔ on board (M) | ✔ | ✔ on board (M) |
| R8 ≥ 10 bits for 40 dB | ✔ 12 bits | ✔ 12 bits | ✘ 8 bits | ✔ 10 bits I/Q; ✘ 8-bit CSI |
| R9 common gain | ~ | ~ | ~ | per-sensor manual or AGC, gains not calibrated (M) |
| R13 2.4 GHz narrowband | ✔ | ✔ | ✘ | ✔ |
| R15 continuous stream | ✔ USB 3.0 | ~ depends on the carrier | ✔ | ✘ low-duty-cycle bursts; each up to 14 336 samples in the example seen (M) |
| R17 spacing ≤ λ/2 | free antennas | free antennas | free antennas | fixed 60 mm, ✔ |
| Sparse geometries | 2 antennas only | ✔ any | 5 antennas | ~ needs two units |

## ESPARGOS One in detail

Strengths (M): antennas, reference and clocks are integrated, which removes the largest practical
difficulty (a calibrated RF front end). It records raw samples on all eight channels at once, not
only channel estimates. The Python library is open source and the device works over Ethernet.

Weaknesses (M): the I/Q path is described as undocumented debugging path of the Wi-Fi chip; the library
is "very early in its development"; bursts rather than continuous samples, so it cannot feed the
real-time C pipeline at full rate (recorded bursts can be replayed through `abf_replay`); dual polarisation ±45°,
one feed at a time; gain differences not calibrated; the documentation says "Enable transmit authorization for the
reference generator first" without explaining it: to be clarified before use.

Not stated: phase accuracy in degrees, noise figure, dynamic range, maximum burst length and repetition rate.

Two units sharing a reference would make 8 columns: elements 0, 1, 4 and 6 of one row would then give the
minimum-redundancy array of study 4 **and** a uniform array of 8 on the same data, the cleanest comparison
available. This requires coherent combination, which the manual calls "research use only".

## Recommended path

| Step | Cost | Gate to continue |
|---|---:|---|
| 0. Public measured data (study 5), other files of espargos-0001 and -0005 | 0 | done once; next: more rooms |
| 1. Ask the maker: phase stability figure, gain calibration, burst rate, reference authorisation; check that the buyer is eligible | 0 | an answer on phase stability |
| 2. One ESPARGOS One; acceptance tests T1, T2, T7 | €350 excl. VAT | T1: phase drift < 5° RMS between calibrations over 10 minutes, after restart and after a frequency change. **If not, stop** (check the return conditions before buying). |
| 3. Null depth with two sources, recorded bursts through the C pipeline | signal sources | null deeper than 25 dB on a real source |
| 4. Second unit (or continuous 4-channel platform) | €350, or $1,873 plus a carrier (FMCOMMS5) | only if step 3 succeeds |

If no private or professional status qualifies for ESPARGOS: KrakenSDR with antennas at a lower band (about
€995 incl. VAT) validates DOA, calibration and the pipeline at N = 5, not at 2.4 GHz and with a
known 8-bit loss (4.2 dB at 40 dB INR in the error budget). A two-channel radio alone is not recommended as the
only purchase: it validates too little.

The decision needed from the owner: **eligibility to buy ESPARGOS, and a budget**. Nothing was ordered, contacted
or reserved.

## Open questions and limits of this survey

- Prices come from a few sellers; stock changes quickly; several pages were unreadable or outdated.
- 2.4 GHz coherence of the X310 and B210 was not confirmed from Ettus pages (refused); the comparison of
  boards such as PLUTO+ depends on sellers' descriptions.
- No platform was found with a published long-term phase stability figure for several channels after
  repeated power cycles. This is why acceptance test T1 comes first.
- Not examined: two 2-channel radios sharing a clock, RSPduo, Red Pitaya, N310, ADRV9009 boards, Phaser (10 GHz), second-hand equipment.
- The European regulations on receiving and recording radio signals are outside this survey
  ([notes](../../docs/safety/legal_and_ethics.md)).

## Sources

Read: [ESPARGOS One product page](https://espargos.net/espargos-one/),
[its datasheet](https://espargos.net/espargos-one/espargos-one-datasheet.pdf) and
[manual](https://espargos.net/espargos-one/espargos-one-manual.pdf),
[calibration](https://espargos.net/docs/calibration.html) and
[I/Q reception](https://espargos.net/docs/iq-reception.html) documentation,
[ESPARGOS paper](https://arxiv.org/html/2502.09405v1);
[LimeSDR-USB channel alignment](https://github.com/myriadrf/LMS7002M-docs/blob/master/LimeSDR-USB_channel_alignment_v01r00.pdf)
and [hardware description](https://wiki.myriadrf.org/LimeSDR-USB_hardware_description);
[KrakenSDR evaluation, Sensors 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10781236/);
[switched array with USRP B210](https://arxiv.org/html/2502.08592v1);
[FMCOMMS5 phase synchronisation](https://analogdevicesinc.github.io/system-level/solutions/reference-designs/fmcomms5/phase-sync/);
[ADALM-PLUTO second channel](https://analogdevicesinc.github.io/system-level/solutions/platforms/pluto/setup/hacking/);
[bladeRF 2.0 micro](https://www.nuand.com/bladerf-2-0-micro/).

Prices read on 25 November 2026: [hackmod](https://www.hackmod.de/en/p/limesdr-usb-open-source-2-2-mimo-sdr-from-100-khz-to-3-8-ghz),
[welectron](https://www.welectron.com/Lime-Microsystems-LimeSDR_1),
[sdrstore, bladeRF](https://www.sdrstore.eu/software-defined-radio/instruments/bladerf/),
[sdrstore, PLUTO](https://www.sdrstore.eu/software-defined-radio/instruments/plutosdr/),
[Passion Radio, KrakenSDR](https://www.passion-radio.com/sdr-receivers/kraken-sdr-3012.html),
[Passion Radio, B210](https://www.passion-radio.com/sdr-transceivers/b210-515.html),
[TME, B210](https://www.tme.eu/en/details/471-043/development-kits-for-data-transmission/digilent/ettus-usrp-b210-with-enclosure-kit/).

Excerpts only: [Crowd Supply, LimeSDR](https://www.crowdsupply.com/lime-micro/limesdr),
[LMS7002M datasheet](https://www.mouser.com/datasheet/2/982/LMS7002M-Data-Sheet-v3.1r00-1600568.pdf),
[AD9361 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9361.pdf),
[NI, B210](https://www.ni.com/en/shop/hardware/software-defined-radios/model-usrp-b210),
[NI, X310](https://www.ni.com/en/shop/hardware/software-defined-radios/model-usrp-x310),
[Ettus quick order](https://www.ettus.com/products/quick-order/),
[TwinRX direction finding](https://kb.ettus.com/Direction_Finding_with_the_USRP%E2%84%A2_X-Series_and_TwinRX%E2%84%A2),
[DigiKey, FMCOMMS5](https://www.digikey.com/en/products/detail/analog-devices-inc/AD-FMCOMMS5-EBZ/5004764),
[Mouser, ADALM-PLUTO](https://eu.mouser.com/ProductDetail/Analog-Devices/ADALM-PLUTO?qs=xbccQsLEe0ffoUoi%2FjfIWA%3D%3D),
[RFSoC 4x2](https://www.realdigital.org/hardware/rfsoc-4x2).
