# FAST Bench Project - Claude Instructions

## Active Planning Documents

When working on this project, ALWAYS reference these documents:

- **Implementation Plan:** `./fast_bench_plan.md`
- **Testing Strategy:** `./fast_bench_testing.md`
- **Status Tracker:** `./fast_bench_status.md`
- **Original Requirements:** `../fast_bench_prompt.md`

## Working on This Project

### Before Starting Any Work
1. Read `fast_bench_status.md` to see current progress
2. Check `fast_bench_plan.md` for the phase you're working on
3. Review acceptance criteria and dependencies
4. Update status document when starting/completing tasks

### When Asked to Implement a Feature
1. Identify which phase it belongs to
2. Verify all dependency phases are complete
3. Follow the implementation plan exactly
4. Write tests according to testing strategy
5. Update status tracker with progress

### When Asked to Revise the Plan
1. Read the relevant planning document first
2. Make requested changes
3. Update any affected dependencies in other phases
4. Note changes in the status document's update log

### Code Style & Standards
- Python 3.10+ syntax
- Type hints where appropriate
- Pydantic for all configuration models
- Clear docstrings for all public functions
- Follow acceptance criteria precisely

### Testing Requirements
- ~85% automated test coverage target
- Write unit tests for all logic
- Document manual tests with step-by-step instructions
- Mark integration tests with `@pytest.mark.integration`
- Mark slow tests with `@pytest.mark.slow`

### Commit Strategy
- Commit at phase completion
- Include test results in commit message
- Reference phase number in commits
- Update status tracker before committing

## Project-Specific Conventions

### File Naming
- Python modules: snake_case
- Classes: PascalCase
- Config files: lowercase with extensions
- Test files: `test_*.py` or `*_test.py`

### Configuration
- All config via `config.yaml` (Pydantic validation)
- No hardcoded paths
- Azure SAS URLs in config
- Environment variables only for secrets (optional)

### Output Files
- Metrics: `metrics_YYYYMMDD_HHMMSS.csv`
- Markers: `markers_YYYYMMDD_HHMMSS.tsv`
- Run metadata: `run.json`
- Baseline: `baseline.json`, `baseline_summary.txt`

## Common Commands

### Development
```bash
# Setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Testing
pytest tests/ -v                          # All unit tests
pytest tests/ -m integration              # Integration tests only
pytest tests/ -m "not integration"        # Skip integration tests
pytest tests/test_config.py -v            # Specific test file

# Run modules
python -m fast_bench.baseline_probe
python -m fast_bench.run_bench A_shared W_scrub100 Cold
python -m fast_bench.analyze_runs
```

### Packaging
```bash
# Build EXE
.\packaging\build_exe.ps1

# Build installer
iscc .\packaging\installer.iss
```

## Important Notes

- This is a Windows-only tool (Windows 10/11 x64)
- Requires admin rights for cache clearing
- Petrel automation uses pywinauto (UIA backend)
- Metrics agent runs as subprocess to isolate overhead
- All coordinates stored as window-relative (0.0-1.0)
- Azure access via SAS URLs only (no SDK required)

## Questions?

If anything is unclear:
1. Check the implementation plan for details
2. Review the original prompt for requirements
3. Look at the testing strategy for validation approach
4. Update this file if you discover something that should be documented