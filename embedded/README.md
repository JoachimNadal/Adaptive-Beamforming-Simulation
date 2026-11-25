# embedded

| Folder | Content | Executed on |
|---|---|---|
| `common/` | ABF1 frames, configuration, sources, adaptive pipeline | PC, CI |
| `config/` | TOML configuration of the reference array | PC, CI |
| `core/` | C99 kernels, tests, benchmark | PC, CI (x86-64, arm64) |
| `raspberry_pi/` | receiver application, notes | PC, CI — **not on a Raspberry Pi** |
| `jetson/` | batched subband MVDR, notes | PC, desktop GPU — **not on a Jetson** |
| `fpga/` | design notes | nothing |

```bash
python -m embedded.raspberry_pi.pi_receiver --source sim --frames 20
python -m embedded.raspberry_pi.pi_receiver --benchmark
python -m embedded.jetson.orin_pipeline --backend numpy
```

Documents: [pipeline](../docs/architecture/signal_pipeline.md),
[protocol](../docs/architecture/iq_frame_protocol.md),
[targets](../docs/architecture/embedded_targets.md),
[hardware requirements](../docs/hardware/requirements.md).
