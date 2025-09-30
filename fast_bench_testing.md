# FAST Bench Testing Strategy

## Overview
Testing coverage: **~85% automated**, 15% manual validation
CI Pipeline: Unit tests on all commits, integration tests on-demand/nightly

---

## Phase 1: Project Setup & Configuration System

### Automated Tests (`tests/test_config.py`)
```python
def test_valid_config_loads():
    """Load sample config, assert no exceptions"""

def test_missing_azure_fields_raises_error():
    """Remove azure_blob section, expect ValidationError"""

def test_invalid_paths_raises_error():
    """Set petrel.exe_path to non-existent, expect error"""

def test_azure_sas_urls_validated():
    """Malformed URLs → ValidationError"""

def test_defaults_applied():
    """Omit optional fields, verify defaults"""
```

### Manual Verification
- Run: `python -c "from fast_bench.config_schema import load_config; load_config('config/config.sample.yaml')"`
- Intentionally break config, verify helpful error messages

**Automation:** ✅ **100% automated** via pytest
**CI:** All commits

---

## Phase 2: Petrel UI Automation

### Automated Tests (`tests/test_relcoords.py`)
```python
def test_coordinate_roundtrip():
    """Verify to_rel() → to_abs() preserves original coords"""
    rect = {"L": 100, "T": 200, "R": 900, "B": 700}
    x, y = 500, 450
    rel = to_rel(x, y, rect)
    abs_x, abs_y = to_abs(rel[0], rel[1], rect)
    assert abs_x == x and abs_y == y

def test_rect_validation():
    """Invalid rects (R < L, B < T) → raise ValueError"""
```

### Manual Tests (`tests/manual/test_petrel_attach.py`)
```python
def manual_test_attach_running_petrel():
    """
    1. User launches Petrel manually
    2. Script attaches, prints rect, brings to foreground
    3. User verifies window activated
    """

def manual_test_attach_launches_petrel():
    """
    1. Close Petrel
    2. Script launches via config path, attaches
    3. User verifies Petrel opened
    """
```

**Automation:**
- 🟢 **Coordinate logic: 100% automated**
- 🔴 **Attach/focus: Manual** (requires human verification)

**CI:** Automated tests on all commits; manual checklist documented

---

## Phase 3: Metrics Agent

### Automated Tests (`tests/test_metrics_schema.py`)
```python
def test_metrics_csv_has_required_columns():
    """Mock run for 5 seconds, verify CSV columns"""

def test_metrics_agent_overhead():
    """
    Start agent, measure its own CPU/RAM via external psutil monitor
    Assert < 2% CPU, < 150 MB RAM
    """

def test_open_zgy_detection():
    """Mock proc.open_files() returning .zgy paths, verify CSV"""

def test_sampling_rate():
    """Run for 10s, verify ~10 rows (1 Hz)"""
```

### Manual Tests (`tests/manual/test_metrics_with_petrel.py`)
```python
def manual_test_metrics_with_real_project():
    """
    1. Launch Petrel with NAS .zgy project
    2. Start metrics agent for 60s
    3. Verify:
       - CSV has 60 rows
       - open_zgy_paths shows NAS path
       - GPU columns populated (if NVIDIA GPU)
    """
```

**Automation:**
- 🟢 **Schema/overhead: 90% automated** (mock open_files)
- 🟡 **Real .zgy detection: Manual** with Petrel

**CI:** Automated tests + manual validation checklist

---

## Phase 4: Baseline Probe

### Automated Tests (`tests/test_baseline_probe.py`)
```python
def test_machine_specs_collected():
    """Run with mock psutil/pynvml, verify JSON structure"""

def test_nas_throughput_mock():
    """Mock file copy, verify MB/s calculation"""

def test_azure_chunk_download_logic():
    """
    Mock requests.get with Range headers
    Verify parallel stream distribution
    """

def test_baseline_json_schema():
    """Validate output JSON has all required fields"""
```

### Integration Tests (`tests/integration/test_baseline_real.py`)
```python
@pytest.mark.integration
def test_real_nas_probe():
    """
    Requires config with valid nas_test_dir
    Runs actual ping + copy, verifies output
    """

@pytest.mark.integration
def test_real_azure_probe():
    """
    Requires valid SAS URLs in config
    Downloads from Azure, verifies MB/s > 0
    """
```

### Manual Tests
- Run: `python -m fast_bench.baseline_probe`
- Verify `baseline.json`, `baseline_summary.txt`, PNGs created
- Check Azure RTT and throughput numbers are realistic

**Automation:**
- 🟢 **Unit logic: 100% automated** (mocked)
- 🟡 **Integration: 50% automated** (requires real NAS/Azure, run with `pytest -m integration`)
- 🔴 **Full validation: Manual** (human reviews output files)

**CI:** Unit tests on all commits; integration tests on-demand or nightly (if secrets available)

---

## Phase 5: Recorder

### Automated Tests (`tests/test_recorder.py`)
```python
def test_recorder_json_schema():
    """Programmatically create events, verify JSON structure"""

def test_window_relative_conversion():
    """Given window rect + abs coords, verify rel coords calculated correctly"""

def test_marker_insertion():
    """Verify F6/F7/F8 markers appear in event stream"""
```

### Manual Tests (`tests/manual/test_recorder_interactive.py`)
```markdown
# Manual Test: Record Session
1. Run: `python -m fast_bench.recorder_mouse`
2. F9 to start recording
3. Move mouse to 4 corners, click, type "test"
4. F7 to insert marker
5. F12 to save
6. Verify:
   - JSON file created
   - Has petrel_rect
   - Events have monotonic timestamps
   - Marker appears in events
```

**Automation:**
- 🟢 **JSON schema: 100% automated**
- 🔴 **Recording: Manual** (requires human input)

**CI:** Schema tests automated; recording documented with step-by-step manual test

---

## Phase 6: Replayer

### Automated Tests (`tests/test_replayer.py`)
```python
def test_replayer_timing_calculation():
    """Mock events with t_ms delays, verify sleep calls"""

def test_coordinate_mapping():
    """Given recorded rect + new rect, verify coordinate adjustment"""

def test_replay_markers_written():
    """Verify replay_start/replay_end markers output"""
```

### Manual Tests (`tests/manual/test_replayer_accuracy.py`)
```markdown
# Manual Test: Replay Accuracy
1. Record a session moving to 4 screen corners
2. Run: `python -m fast_bench.replayer_mouse --session session.json`
3. Visually verify mouse hits same corners
4. Use screen recording tool, measure timing deltas
5. Assert all steps within ±50ms
```

**Automation:**
- 🟢 **Timing/mapping logic: 100% automated**
- 🔴 **Accuracy validation: Manual** (visual/timing verification)

**CI:** Logic tests automated; accuracy checklist in manual tests

---

## Phase 7: Scripted Workflows

### Automated Tests (`tests/test_workflows.py`)
```python
def test_scrub_workflow_sends_correct_count():
    """Mock keyboard.send_keys, verify called 100 times"""

def test_marker_tsv_format():
    """Verify TSV output is valid (UTC ISO8601, columns)"""

def test_workflow_timing():
    """Mock time.sleep, verify delays honored"""

def test_all_workflows_covered():
    """Ensure W_scrub100, W_attribute, W_horizon, W_export exist"""
```

### Manual Tests (`tests/manual/test_workflows_petrel.py`)
```markdown
# Manual Test: Scrub in Petrel
1. Open Petrel with inline view
2. Run: `python -m fast_bench.workflows W_scrub100`
3. Verify 100 inline advances occurred
4. Check markers.tsv has scrub_start/scrub_end
```

**Automation:**
- 🟢 **Logic: 100% automated** (mocked keyboard)
- 🟡 **Petrel effect: Manual** (verify Petrel actually responded)

**CI:** Mocked tests automated; Petrel validation manual

---

## Phase 8: Cache Management Scripts

### Automated Tests (`tests/test_cache_scripts.ps1` - PowerShell Pester)
```powershell
Describe "Clear-WindowsCache" {
    It "Runs without errors" {
        { .\tools\Clear-WindowsCache.ps1 } | Should -Not -Throw
    }
}

Describe "Rotate-FastCache" {
    It "Deletes cache directory contents" {
        # Create temp cache dir with dummy files
        New-Item -ItemType Directory -Path "TestDrive:\cache"
        New-Item -ItemType File -Path "TestDrive:\cache\file1.bin"

        # Run script (mocked path)
        # Verify files deleted
        (Get-ChildItem "TestDrive:\cache").Count | Should -Be 0
    }
}
```

### Manual Tests
```markdown
# Manual Test: Cache Clearing
1. Run as admin: `.\tools\Clear-WindowsCache.ps1`
2. Use RAMMap or SysInternals to verify standby cache cleared
3. Create dummy files in fast.cache_dir
4. Run: `.\tools\Rotate-FastCache.ps1`
5. Verify directory emptied
```

**Automation:**
- 🟡 **Script execution: 80% automated** (Pester tests, may need admin elevation)
- 🔴 **Cache verification: Manual** (RAMMap inspection)

**CI:** Pester tests on Windows runner; manual verification documented

---

## Phase 9: Run Orchestrator

### Automated Tests (`tests/test_run_bench.py`)
```python
@pytest.mark.unit
def test_mode_selection():
    """Verify A_shared → project_shared_zgy_local, B_fast → project_fast_vzgy_local"""

@pytest.mark.unit
def test_cache_policy_selection():
    """Verify Cold → calls cache scripts, Warm → skips"""

@pytest.mark.integration
def test_scripted_run_mocked():
    """Mock Petrel attach, metrics agent, workflow. Verify orchestration flow, run.json created"""
```

### Integration Tests (`tests/integration/test_full_runs.py`)
```python
@pytest.mark.slow
def integration_test_full_scripted_run():
    """
    Actual Petrel launch, metrics, workflow
    Assert metrics CSV, run.json, markers exist
    """

@pytest.mark.slow
def integration_test_replay_run():
    """
    Use pre-recorded session
    Assert replay completes, output files valid
    """
```

### Manual Tests
```markdown
# Manual Test: Full Run Validation
1. Run: `python -m fast_bench.run_bench A_shared W_scrub100 Cold`
2. Verify:
   - Petrel launches with correct project (check window title)
   - Metrics CSV created
   - run.json has correct mode/workflow/cache_state
   - Cache cleared before run (check with Process Monitor)
3. Run: `python -m fast_bench.run_bench B_fast replay Cold --session recordings/session.json`
4. Verify replay completes, outputs created
```

**Automation:**
- 🟢 **Orchestration logic: 100% automated** (mocked)
- 🟡 **Integration: 70% automated** (requires Petrel, marked slow)
- 🔴 **End-to-end validation: Manual**

**CI:** Mocked tests on all commits; integration tests nightly or manual trigger

---

## Phase 10: Analysis & Reporting

### Automated Tests (`tests/test_analyze_runs.py`)
```python
def test_kpi_calculation():
    """Mock run dirs with markers, CSV. Verify open_time_s, scrub_time_s computed correctly"""

def test_source_classification():
    """Given open_zgy_paths with NAS/FAST paths, verify classification"""

def test_csv_export():
    """Verify comparison_kpis.csv has required columns"""

def test_chart_generation():
    """Mock matplotlib, verify save_fig called"""

def test_marker_parsing():
    """Verify TSV markers parsed correctly (open_start, first_pixel, etc.)"""
```

### Integration Tests (`tests/integration/test_analyze_real_runs.py`)
```python
@pytest.mark.integration
def test_analyze_real_runs():
    """
    Use fixture data from real runs (checked into repo)
    Run analyzer, verify outputs match expected
    """
```

### Manual Tests
```markdown
# Manual Test: Analysis Validation
1. Run analyzer on diverse run sets (A/B, Cold/Warm, scripted/replay)
2. Visually inspect charts for correctness
3. Open CSV in Excel, verify all columns populated
4. Check source classification matches actual run modes
```

**Automation:**
- 🟢 **KPI logic: 100% automated**
- 🟡 **Chart validation: 80% automated** (structure, not visual correctness)
- 🔴 **Visual inspection: Manual**

**CI:** All logic automated; fixture-based integration tests; manual chart review

---

## Phase 11: Packaging

### Automated Tests (`tests/test_packaging.ps1`)
```powershell
Describe "PyInstaller Build" {
    It "Produces fast_bench.exe" {
        .\packaging\build_exe.ps1
        Test-Path "dist\fast_bench.exe" | Should -Be $true
    }

    It "EXE runs --help" {
        $output = .\dist\fast_bench.exe --help
        $output | Should -Contain "usage:"
    }
}

Describe "Inno Setup Installer" {
    It "Produces installer.exe" {
        # Requires Inno Setup installed
        iscc .\packaging\installer.iss
        Test-Path "Output\FASTBench_Setup.exe" | Should -Be $true
    }
}
```

### Manual Tests
```markdown
# Manual Test: Installation Validation
1. Build installer on dev machine
2. Copy to clean Windows 10 VM
3. Run installer
4. Verify Start Menu shortcuts created
5. Launch "FAST Bench — Baseline Probe" from Start Menu
6. Verify tool runs without errors
```

**Automation:**
- 🟡 **Build process: 90% automated** (PS scripts, requires tooling installed)
- 🔴 **Installation validation: Manual** (VM testing)

**CI:** Build scripts on Windows runner; manual VM validation documented

---

## Phase 12: Documentation & Final Testing

### Automated Tests (`tests/test_readme.py`)
```python
def test_readme_exists():
    """Verify README.md exists"""

def test_readme_has_required_sections():
    """Check for Installation, Configuration, Azure SAS, Operator Cookbook sections"""

def test_license_exists():
    """Verify LICENSE file exists"""

def test_sample_config_documented():
    """Verify README references config.sample.yaml"""
```

### Manual Tests
```markdown
# Manual Test: Documentation Walkthrough
1. Provision fresh Windows 10 VM
2. Follow README installation instructions exactly
3. Configure config.yaml with real Azure SAS URLs
4. Run baseline probe
5. Record a session
6. Run scripted and replay benchmarks
7. Analyze results
8. Document any unclear steps or errors
```

**Automation:**
- 🟢 **README structure: 100% automated**
- 🔴 **Documentation correctness: Manual** (human follows instructions)

**CI:** Structure tests automated; full walkthrough manual checklist

---

## Overall Automation Summary

| Phase | Automated % | Manual % | CI Status |
|-------|-------------|----------|-----------|
| 1. Config | 100% | 0% | ✅ All commits |
| 2. Petrel UI | 80% | 20% | ✅ Unit tests, 🔴 Manual attach |
| 3. Metrics | 90% | 10% | ✅ Unit tests, 🟡 Integration |
| 4. Baseline | 70% | 30% | ✅ Unit tests, 🟡 Integration |
| 5. Recorder | 80% | 20% | ✅ Schema tests, 🔴 Manual recording |
| 6. Replayer | 80% | 20% | ✅ Logic tests, 🔴 Manual accuracy |
| 7. Workflows | 90% | 10% | ✅ Mocked tests, 🔴 Manual Petrel |
| 8. Cache Scripts | 80% | 20% | ✅ Pester tests, 🔴 Manual verify |
| 9. Orchestrator | 85% | 15% | ✅ Unit tests, 🟡 Integration |
| 10. Analysis | 95% | 5% | ✅ All automated, 🔴 Visual review |
| 11. Packaging | 90% | 10% | ✅ Build tests, 🔴 Manual install |
| 12. Docs | 90% | 10% | ✅ Structure tests, 🔴 Manual walkthrough |

**Overall:** ~85% automated testing coverage

---

## CI Pipeline Structure

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  unit-tests:
    name: Unit Tests
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --ignore=tests/integration --ignore=tests/manual -v

  integration-tests:
    name: Integration Tests
    runs-on: windows-latest
    if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/integration -m integration -v
    # Note: Requires secrets for NAS/Azure access

  build:
    name: Build Executable
    runs-on: windows-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pip install pyinstaller
      - run: .\packaging\build_exe.ps1
      - uses: actions/upload-artifact@v3
        with:
          name: fast_bench_exe
          path: dist/fast_bench.exe
```

---

## Manual Test Execution Schedule

### Weekly (Developer)
- Phase 2: Petrel attach tests
- Phase 5: Record session
- Phase 6: Replay accuracy
- Phase 7: Workflows in Petrel

### Pre-Release (QA)
- All manual tests from all phases
- Full installation on clean VM
- Documentation walkthrough
- Azure baseline with real resources

### Ad-Hoc (As Needed)
- Phase 4: Azure integration tests (when SAS URLs change)
- Phase 9: Full orchestrator runs (after major changes)

---

## Test Data & Fixtures

### Required Test Fixtures
- `tests/fixtures/sample_run_output/` - Example run.json, metrics CSV, markers
- `tests/fixtures/sample_recording.json` - Valid recorder session
- `tests/fixtures/sample_baseline.json` - Example baseline output

### Mock Data Strategy
- Use `pytest-mock` for psutil, pynvml, pywinauto
- Use `responses` library for Azure HTTP requests
- Store golden outputs for regression testing

---

## Acceptance Criteria from Original Prompt

All 8 acceptance tests must pass:

1. ✅ **Config validation** with pydantic errors on missing/invalid fields
2. ✅ **Petrel attach**: launch and attach within 180s; focus maintained
3. ✅ **Scripted workflows** send correct counts/timings; markers bracket phases
4. ✅ **Recorder/Replayer**: short session replays within ±50 ms step timing
5. ✅ **Metrics CSV**: correct columns; 60s idle → 60 rows; `open_zgy_paths` shows `.zgy`
6. ✅ **Azure baseline**: sustained MB/s and p95/p99 chunk times; ping RTTs
7. ✅ **Packaging**: EXE and installer built; Start Menu shortcut works
8. ✅ **Docs**: README shows install, config, run commands, sample outputs/screenshots

---

## References
- Implementation plan: `/Users/raghu/code/fast_bench/fast_bench_plan.md`
- Status tracker: `/Users/raghu/code/fast_bench/fast_bench_status.md`