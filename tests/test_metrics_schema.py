"""Tests for metrics agent CSV schema and data validation."""

import sys
import csv
import time
import subprocess
import tempfile
from pathlib import Path
import pytest
import psutil


def test_metrics_csv_schema():
    """Test that metrics CSV has all required columns."""
    expected_columns = [
        'ts', 'pid', 'cpu_pct', 'rss_mb', 'vms_mb',
        'read_bytes_s', 'write_bytes_s', 'read_cnt_s', 'write_cnt_s',
        'sys_disk_read_mb_s', 'sys_disk_write_mb_s',
        'sys_net_recv_mb_s', 'sys_net_sent_mb_s',
        'gpu_util_pct', 'gpu_mem_used_mb', 'gpu_mem_total_mb',
        'fast_req_latency_ms', 'fast_req_bytes', 'fast_req_cache_hit',
        'open_zgy_paths'
    ]

    # Create a temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = Path(f.name)

    try:
        # Start a simple process to monitor (ourselves)
        target_pid = psutil.Process().pid

        # Run metrics agent for 3 seconds
        result = subprocess.run(
            [sys.executable, '-m', 'fast_bench.metrics_agent',
             str(target_pid), str(csv_path), '--duration', '3'],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Check that metrics agent ran successfully
        assert result.returncode == 0, f"Metrics agent failed: {result.stderr}"

        # Read and validate CSV
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames

            # Check all expected columns are present
            assert header == expected_columns, f"CSV columns mismatch: {header}"

            # Check we got approximately 3 rows (1 Hz sampling)
            rows = list(reader)
            assert 2 <= len(rows) <= 4, f"Expected ~3 rows, got {len(rows)}"

            # Validate first row has valid data
            if rows:
                row = rows[0]
                assert row['pid'] == str(target_pid)
                assert float(row['cpu_pct']) >= 0.0
                assert float(row['rss_mb']) > 0.0
                assert float(row['vms_mb']) > 0.0

    finally:
        # Clean up temp file
        if csv_path.exists():
            csv_path.unlink()


def test_metrics_csv_numeric_types():
    """Test that numeric columns contain valid numbers."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = Path(f.name)

    try:
        target_pid = psutil.Process().pid

        # Run for 2 seconds
        subprocess.run(
            [sys.executable, '-m', 'fast_bench.metrics_agent',
             str(target_pid), str(csv_path), '--duration', '2'],
            capture_output=True,
            timeout=10
        )

        # Validate numeric types
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            assert len(rows) > 0, "No data rows"

            for row in rows:
                # These should be valid numbers
                assert float(row['cpu_pct']) >= 0.0
                assert float(row['rss_mb']) >= 0.0
                assert float(row['vms_mb']) >= 0.0
                assert float(row['read_bytes_s']) >= 0.0
                assert float(row['write_bytes_s']) >= 0.0
                assert float(row['sys_net_recv_mb_s']) >= 0.0
                assert float(row['sys_net_sent_mb_s']) >= 0.0
                assert float(row['gpu_util_pct']) >= 0.0
                assert float(row['gpu_mem_used_mb']) >= 0.0
                assert float(row['gpu_mem_total_mb']) >= 0.0

                # PID should match
                assert int(row['pid']) == target_pid

                # Timestamp should be ISO format
                assert 'T' in row['ts']  # ISO format has 'T' separator

    finally:
        if csv_path.exists():
            csv_path.unlink()


def test_metrics_sampling_rate():
    """Test that metrics agent maintains ~1 Hz sampling rate."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = Path(f.name)

    try:
        target_pid = psutil.Process().pid
        duration = 5

        start_time = time.time()
        subprocess.run(
            [sys.executable, '-m', 'fast_bench.metrics_agent',
             str(target_pid), str(csv_path), '--duration', str(duration)],
            capture_output=True,
            timeout=duration + 5
        )
        elapsed = time.time() - start_time

        # Read CSV
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have approximately 'duration' samples (±1)
        assert duration - 1 <= len(rows) <= duration + 1, \
            f"Expected ~{duration} samples, got {len(rows)}"

        # Total time should be close to duration
        assert elapsed < duration + 2, \
            f"Took too long: {elapsed:.1f}s for {duration}s duration"

    finally:
        if csv_path.exists():
            csv_path.unlink()


def test_metrics_agent_nonexistent_pid():
    """Test that metrics agent handles non-existent PID gracefully."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = Path(f.name)

    try:
        # Use a PID that definitely doesn't exist
        fake_pid = 999999

        result = subprocess.run(
            [sys.executable, '-m', 'fast_bench.metrics_agent',
             str(fake_pid), str(csv_path), '--duration', '1'],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should exit with error
        assert result.returncode != 0
        assert 'does not exist' in result.stderr.lower()

    finally:
        if csv_path.exists():
            csv_path.unlink()


def test_open_zgy_paths_column_exists():
    """Test that open_zgy_paths column is present and accessible."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = Path(f.name)

    try:
        target_pid = psutil.Process().pid

        subprocess.run(
            [sys.executable, '-m', 'fast_bench.metrics_agent',
             str(target_pid), str(csv_path), '--duration', '1'],
            capture_output=True,
            timeout=5
        )

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            assert len(rows) > 0
            # Column should exist (may be empty string)
            assert 'open_zgy_paths' in rows[0]

    finally:
        if csv_path.exists():
            csv_path.unlink()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only GPU test")
def test_gpu_metrics_on_windows():
    """Test that GPU metrics are collected on Windows (if GPU present)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = Path(f.name)

    try:
        target_pid = psutil.Process().pid

        subprocess.run(
            [sys.executable, '-m', 'fast_bench.metrics_agent',
             str(target_pid), str(csv_path), '--duration', '2'],
            capture_output=True,
            timeout=10
        )

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            assert len(rows) > 0

            # GPU columns should exist (may be 0 if no GPU)
            row = rows[0]
            gpu_util = float(row['gpu_util_pct'])
            gpu_mem_used = float(row['gpu_mem_used_mb'])
            gpu_mem_total = float(row['gpu_mem_total_mb'])

            # If GPU is present, total should be > 0
            # If no GPU, all should be 0
            if gpu_mem_total > 0:
                assert gpu_mem_used >= 0
                assert gpu_util >= 0
            else:
                # No GPU detected
                assert gpu_mem_used == 0
                assert gpu_util == 0

    finally:
        if csv_path.exists():
            csv_path.unlink()


def test_metrics_overhead():
    """Test that metrics agent has low CPU overhead."""
    # This is a basic test - full overhead testing requires manual validation
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = Path(f.name)

    try:
        target_pid = psutil.Process().pid

        # Start metrics agent
        proc = subprocess.Popen(
            [sys.executable, '-m', 'fast_bench.metrics_agent',
             str(target_pid), str(csv_path), '--duration', '3'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Monitor the metrics agent process itself
        agent_process = psutil.Process(proc.pid)
        time.sleep(2)  # Let it run for a bit

        # Check CPU usage (should be very low)
        cpu_percent = agent_process.cpu_percent(interval=1.0)
        mem_info = agent_process.memory_info()
        mem_mb = mem_info.rss / (1024 * 1024)

        proc.wait(timeout=5)

        # Overhead checks (generous limits for CI)
        assert cpu_percent < 10.0, f"Metrics agent CPU too high: {cpu_percent}%"
        assert mem_mb < 200, f"Metrics agent memory too high: {mem_mb} MB"

    finally:
        if csv_path.exists():
            csv_path.unlink()
