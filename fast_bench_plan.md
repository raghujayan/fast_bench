# FAST vs NAS vs Azure VDS A/B Bench Harness - Implementation Plan

## Project Overview
Building a repeatable A/B/C benchmark harness for comparing:
- **Mode A (NAS_ZGY)**: Petrel reads `.zgy` from NAS/SMB
- **Mode B (FAST_VZGY_AzureVDS)**: Petrel reads virtual `.zgy` via FAST streaming from Azure Blob VDS
- **Mode C**: Direct Azure path probes (baseline network ceilings)

**Target:** Windows 10/11, Python 3.10+, Petrel 2023+, production-quality packaging

---

## Phase 1: Project Setup & Configuration System
**Status:** Not Started
**Goal:** Fully functional configuration loading with validation

### Deliverables
- Project structure (directories, pyproject.toml, requirements.txt)
- `src/fast_bench/__init__.py`
- `src/fast_bench/config_schema.py` with complete Pydantic models
- `config/config.sample.yaml` with all Azure Blob fields
- `src/fast_bench/utils/files.py`, `src/fast_bench/utils/timeutil.py`
- `LICENSE` file

### Acceptance Criteria
- ✅ Valid config loads without errors
- ✅ Invalid config (missing Azure fields, bad paths) raises descriptive Pydantic errors
- ✅ Unit test: `tests/test_config.py` passes
- ✅ Dependencies pinned in requirements.txt

### Dependencies
None (foundational)

---

## Phase 2: Petrel UI Automation (Standalone)
**Status:** Not Started
**Goal:** Reliable Petrel window management

### Deliverables
- `src/fast_bench/ui_attach.py` complete with:
  - Petrel attach via pywinauto (UIA)
  - Window rect capture
  - Coordinate conversion: `to_rel()`, `to_abs()`
  - `ensure_foreground()`, optional `set_window_rect()`
- `tests/test_relcoords.py`
- `tests/manual/test_petrel_attach.py`

### Acceptance Criteria
- ✅ Launches Petrel (if not running), attaches within 180s
- ✅ Returns accurate window rect
- ✅ `to_rel()` and `to_abs()` round-trip correctly
- ✅ `ensure_foreground()` brings Petrel to front
- ✅ Unit test: `tests/test_relcoords.py` passes
- ✅ Manual test: Successfully attaches to running Petrel

### Dependencies
Phase 1 (config system for Petrel path)

---

## Phase 3: Metrics Agent (Standalone)
**Status:** Not Started
**Goal:** Low-overhead metrics collection proven

### Deliverables
- `src/fast_bench/metrics_agent.py` as runnable subprocess
- CSV output with all required columns:
  - `ts, pid, cpu_pct, rss_mb, vms_mb`
  - `read_bytes_s, write_bytes_s, read_cnt_s, write_cnt_s`
  - `sys_disk_read_mb_s, sys_disk_write_mb_s, sys_net_recv_mb_s, sys_net_sent_mb_s`
  - `gpu_util_pct, gpu_mem_used_mb, gpu_mem_total_mb`
  - `fast_req_latency_ms, fast_req_bytes, fast_req_cache_hit`
  - `open_zgy_paths`
- Optional FAST log tail parser
- `tests/test_metrics_schema.py`
- `tests/manual/test_metrics_with_petrel.py`

### Acceptance Criteria
- ✅ Runs for 60s idle → produces 60 rows of valid CSV
- ✅ CPU overhead < 2%, RAM < 150 MB (measured via separate monitor)
- ✅ `open_zgy_paths` column shows `.zgy` files when Petrel project is open
- ✅ GPU columns populated (if NVIDIA GPU present)
- ✅ Unit test: `tests/test_metrics_schema.py` validates CSV structure
- ✅ 1 Hz sampling rate maintained

### Dependencies
None (standalone tool)

---

## Phase 4: Baseline Probe (Standalone Tool)
**Status:** Not Started
**Goal:** Machine + NAS + Azure network ceilings measured

### Deliverables
- `src/fast_bench/baseline_probe.py` runnable independently
- `src/fast_bench/utils/charts.py` for plotting
- Outputs:
  - `baseline.json` (structured metrics)
  - `baseline_summary.txt` (human-readable)
  - Optional `baseline_*.png` charts
- `tests/test_baseline_probe.py`
- `tests/integration/test_baseline_real.py`

### Acceptance Criteria
- ✅ Collects machine specs (CPU, RAM, GPU, NIC)
- ✅ NAS: ping RTT (min/avg/p95) and throughput (single + parallel streams)
- ✅ Azure: ping RTT to blob.core.windows.net
- ✅ Azure: ranged multi-stream GET from SAS URLs with sustained MB/s and p95/p99 chunk times
- ✅ Optional: AzCopy cross-check (if available)
- ✅ Outputs valid JSON and human-readable summary
- ✅ Charts saved as PNGs (if matplotlib works)

### Dependencies
Phase 1 (config for NAS/Azure settings)

---

## Phase 5: Recorder (Standalone Tool)
**Status:** Not Started
**Goal:** Capture keyboard+mouse with window-relative coords

### Deliverables
- `src/fast_bench/recorder_mouse.py` with pynput hooks
- Controls: F9 start/pause, F12 stop, F6/F7/F8 markers
- JSON output with events (version 2 schema)
- `tests/test_recorder.py`
- `tests/manual/test_recorder_interactive.py`

### Acceptance Criteria
- ✅ Records a 30s session with mouse moves, clicks, keys, markers
- ✅ Outputs valid JSON with `petrel_rect` and window-relative positions
- ✅ No crashes during recording
- ✅ Event timestamps are monotonic
- ✅ Window-relative coordinates (0.0-1.0 range)

### Dependencies
Phase 2 (Petrel attach for window rect capture)

---

## Phase 6: Replayer (Standalone Tool)
**Status:** Not Started
**Goal:** Deterministic playback from recorded JSON

### Deliverables
- `src/fast_bench/replayer_mouse.py` reads JSON and replays
- Optional window normalization
- Marker output during replay
- Failsafe on top-left corner
- `tests/test_replayer.py`
- `tests/manual/test_replayer_accuracy.py`

### Acceptance Criteria
- ✅ Replays session from Phase 5 within ±50ms per-step timing
- ✅ Mouse moves to correct absolute positions
- ✅ Keys sent correctly (verified in Petrel or Notepad)
- ✅ Writes `replay_start` and `replay_end` markers
- ✅ Failsafe triggers on top-left corner slam

### Dependencies
Phase 2 (Petrel attach), Phase 5 (recorder JSON format)

---

## Phase 7: Scripted Workflows (Standalone)
**Status:** Not Started
**Goal:** Deterministic Petrel interactions without recording

### Deliverables
- `src/fast_bench/workflows.py` with:
  - `W_scrub100` (inline scrubbing)
  - `W_attribute` (compute attribute)
  - `W_horizon` (autotrack)
  - `W_export` (slice export)
- TSV marker output
- `tests/test_workflows.py`
- `tests/manual/test_workflows_petrel.py`

### Acceptance Criteria
- ✅ W_scrub100: sends PGDN 100 times with 40ms delay, writes markers
- ✅ W_attribute: sends Alt+1, waits specified time, writes markers
- ✅ W_horizon: sends Alt+2, waits 45s, writes markers
- ✅ W_export: sends Alt+3, writes markers
- ✅ Markers are valid TSV (UTC ISO8601, event, comment)

### Dependencies
Phase 1 (config for hotkeys), Phase 2 (Petrel attach)

---

## Phase 8: Cache Management Scripts
**Status:** Not Started
**Goal:** Reliable cache clearing for Cold runs

### Deliverables
- `tools/Clear-WindowsCache.ps1` (Windows FS cache)
- `tools/Rotate-FastCache.ps1` (FAST cache dir purge)
- `tests/test_cache_scripts.ps1` (Pester tests)

### Acceptance Criteria
- ✅ Clears Windows standby cache (requires admin)
- ✅ Purges `fast.cache_dir` contents
- ✅ Scripts run without errors on Windows 10/11
- ✅ Pester tests pass

### Dependencies
Phase 1 (config for cache paths)

---

## Phase 9: Run Orchestrator (Integration)
**Status:** Not Started
**Goal:** End-to-end benchmark execution

### Deliverables
- `src/fast_bench/run_bench.py` CLI with mode/workflow/cache args
- Integrates Phases 2, 3, 6, 7, 8
- Outputs `run.json` and markers
- `tests/test_run_bench.py`
- `tests/integration/test_full_runs.py`

### CLI Interface
```bash
# Scripted
python -m fast_bench.run_bench A_shared W_scrub100 Cold
python -m fast_bench.run_bench B_fast W_scrub100 Cold

# Replay
python -m fast_bench.run_bench A_shared replay Cold --session recordings/session.json
python -m fast_bench.run_bench B_fast replay Cold --session recordings/session.json
```

### Acceptance Criteria
- ✅ Scripted run completes successfully for both A_shared and B_fast modes
- ✅ Replay run completes with pre-recorded session
- ✅ Metrics CSV written with >0 rows
- ✅ `run.json` contains mode, workflow, cache_state, hostname, operator
- ✅ Cold cache policy executes PS1 scripts before Petrel launch
- ✅ Markers written at all key phases (open_start, first_pixel, session_end)

### Dependencies
Phases 2, 3, 6, 7, 8

---

## Phase 10: Analysis & Reporting (Standalone)
**Status:** Not Started
**Goal:** Aggregate KPIs and generate comparison outputs

### Deliverables
- `src/fast_bench/analyze_runs.py` parses all run dirs
- `comparison_kpis.csv` export
- PNG charts (matplotlib)
- `tests/test_analyze_runs.py`
- `tests/integration/test_analyze_real_runs.py`

### KPIs Computed
- `open_time_s` (open_start → first_pixel)
- `scrub_time_s`, `attr_time_s`, `horizon_time_s`, `export_time_s`
- `cpu_mean`, `gpu_mean`
- `read_MB_s_p95` (per-process)
- If FAST log parsed: `lat_p50_ms/p95_ms/p99_ms`, `fast_cache_hit_rate`
- `observed_source` (classify NAS_ZGY vs FAST_VZGY_AzureVDS)

### Charts
- Bar: Median Project Open (s) by mode
- Bar: Median Scrub-100 (s) by mode
- Latency CDF for FAST per-read latency (if available)

### Acceptance Criteria
- ✅ Computes all KPIs correctly from markers and metrics CSV
- ✅ Classifies `observed_source` from `open_zgy_paths`
- ✅ Exports CSV with all required columns
- ✅ Generates bar charts (median open time, scrub time by mode)
- ✅ Optional: FAST latency CDF if log data present

### Dependencies
Phase 9 (run outputs)

---

## Phase 11: Packaging (Deployment)
**Status:** Not Started
**Goal:** Distributable EXE and installer

### Deliverables
- `packaging/build_exe.ps1` (PyInstaller)
- `packaging/installer.iss` (Inno Setup)
- Venv setup documentation
- `tests/test_packaging.ps1`

### Acceptance Criteria
- ✅ PyInstaller produces one-file `fast_bench.exe` that runs baseline probe
- ✅ Inno Setup installer creates Start Menu shortcuts:
  - "FAST Bench — Baseline Probe"
  - "FAST Bench — Run (Scripted)"
  - "FAST Bench — Run (Replay)"
  - "FAST Bench — Analyze"
- ✅ Installed tool runs baseline probe successfully
- ✅ README documents both venv and EXE installation

### Dependencies
All phases complete

---

## Phase 12: Documentation & Final Testing
**Status:** Not Started
**Goal:** Production-ready deliverable

### Deliverables
- Comprehensive `README.md` with operator cookbook
- `LICENSE` file
- Optional `.github/workflows/ci.yml`
- All acceptance tests from original prompt pass

### README Sections Required
- Installation (venv + EXE)
- Configuration (emphasizing Azure Blob SAS setup)
- Baseline probe
- Recording sessions
- Replay runs
- Scripted runs
- Analysis
- Sample outputs/screenshots

### Acceptance Criteria
- ✅ README covers all required sections
- ✅ Sample outputs/screenshots included
- ✅ All 8 acceptance tests from original prompt pass:
  1. Config validation with pydantic errors
  2. Petrel attach within 180s
  3. Scripted workflows send correct counts/timings
  4. Recorder/Replayer within ±50ms timing
  5. Metrics CSV with correct columns, open_zgy_paths
  6. Azure baseline with MB/s and RTTs
  7. Packaging (EXE + installer)
  8. Docs with install, config, run commands
- ✅ Runs successfully on fresh Windows 10 VM

### Dependencies
All phases complete

---

## Execution Notes

### Independent Phases (Can Start Anytime)
- Phase 1: Configuration foundation
- Phase 3: Metrics agent (standalone)
- Phase 4: Baseline probe (needs config)

### Sequential Dependencies
- Phase 2 → Phase 5 (recorder needs attach)
- Phase 5 → Phase 6 (replayer needs recorder format)
- Phase 2,7 → Phase 7 (workflows need attach + config)
- Phases 2,3,6,7,8 → Phase 9 (orchestrator integrates all)
- Phase 9 → Phase 10 (analysis needs run outputs)
- All → Phase 11,12 (packaging + docs)

### Testing Strategy
- Unit tests run on all commits
- Integration tests require real NAS/Azure (on-demand)
- Manual tests documented with checklists
- Overall automation: ~85%

---

## References
- Original prompt: `/Users/raghu/code/fast_bench_prompt.md`
- Testing plan: `/Users/raghu/code/fast_bench/fast_bench_testing.md`
- Status tracker: `/Users/raghu/code/fast_bench/fast_bench_status.md`