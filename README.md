# FAST Bench

An A/B benchmark harness that measures Petrel seismic data-access performance across three data paths: NAS/SMB reads (ZGY), FAST-streamed Azure VDS reads (VZGY), and direct Azure network probes — so you can compare streaming vs. direct data access for 3D seismic volumes.

## How it works

Three benchmark modes:

- **Mode A (NAS_ZGY)** — Petrel opens ZGY files from a NAS/SMB share (baseline).
- **Mode B (FAST_VZGY_AzureVDS)** — Petrel opens virtual VZGY files streamed via FAST from Azure Blob (VDS).
- **Mode C (direct Azure probes)** — Baseline network/storage ceilings without Petrel.

Components:

- `baseline_probe.py` — Records machine specs (CPU/RAM/GPU/NIC) and measures NAS read throughput (chunked reads) plus Azure Blob throughput (single-threaded and 8-worker parallel ranged GETs over SAS URLs); optional azcopy benchmark.
- `metrics_agent.py` — 1 Hz per-process sampler recording CPU/RAM, disk I/O, network, GPU utilization, and open `.zgy` file paths.
- `ui_attach.py` — Attaches to the Petrel window via pywinauto (UIA) for automated interaction.
- `config_schema.py` — Pydantic schema validation for `config/config.yaml`.
- `utils/` — File utilities, time helpers, and chart plotting.

## Requirements

- Windows 10/11 (x64)
- Python 3.10+
- Petrel 2023+
- Azure SAS URLs (env `FB_BLOB_URL_*`) for Azure probes

Install dependencies:

```
pip install -r requirements.txt
```

## How to run

Baseline probe (machine specs + NAS/Azure throughput ceilings):

```
python -m fast_bench.baseline_probe [config_path]
```

(default config: `config/config.yaml`; writes `baseline.json` and `baseline_summary.txt` under `<out_dir>/baseline/`)

Per-process metrics sampler:

```
python -m fast_bench.metrics_agent <pid> <output_csv> [--duration SECONDS]
```

Example:

```
python -m fast_bench.metrics_agent 1234 metrics_petrel.csv --duration 60
```

Run the test suite:

```
pytest
```

## What the output looks like

- `baseline.json` / `baseline_summary.txt` — machine specs, NAS throughput (MB/s), Azure single-threaded + parallel blob throughput, azcopy results (if enabled).
- `metrics_*.csv` — 1 Hz rows of timestamp, CPU %, RAM, disk read/write rates, network rates, GPU %, and open `.zgy` paths.
- `markers_*.tsv` — Event markers for aligning actions with metrics.
- `run.json` — Run metadata and configuration snapshot.

## License

MIT License — Copyright (c) 2025 Bluware Corp
