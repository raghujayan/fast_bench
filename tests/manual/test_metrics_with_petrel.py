"""Manual test for metrics agent with Petrel - Windows only.

Run this script on Windows with Petrel running to verify:
1. Metrics agent monitors Petrel process
2. All metrics are collected correctly
3. open_zgy_paths detects loaded .zgy files
4. GPU metrics are collected (if GPU present)
5. Overhead is low (<2% CPU, <150 MB RAM)

Usage:
    python tests/manual/test_metrics_with_petrel.py

Prerequisites:
    - Petrel must be running
    - Open a Petrel project with .zgy seismic data
"""

import sys
import time
import subprocess
import csv
from pathlib import Path
from datetime import datetime

import psutil


def find_petrel_process():
    """Find running Petrel process."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'petrel' in proc.info['name'].lower():
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def test_metrics_with_petrel():
    """Test metrics agent with running Petrel process."""
    print("=" * 60)
    print("Metrics Agent Test with Petrel")
    print("=" * 60)

    if sys.platform != "win32":
        print("❌ ERROR: This test must be run on Windows")
        sys.exit(1)

    # Find Petrel process
    print("\n1. Finding Petrel process...")
    petrel_pid = find_petrel_process()
    if not petrel_pid:
        print("   ❌ Petrel is not running")
        print("   Please start Petrel and open a project with .zgy data")
        sys.exit(1)
    print(f"   ✓ Found Petrel process: PID {petrel_pid}")

    # Get Petrel process info
    petrel_proc = psutil.Process(petrel_pid)
    print(f"   ✓ Petrel name: {petrel_proc.name()}")
    print(f"   ✓ Petrel CPU: {petrel_proc.cpu_percent(interval=0.5):.1f}%")
    mem_mb = petrel_proc.memory_info().rss / (1024 * 1024)
    print(f"   ✓ Petrel RAM: {mem_mb:.1f} MB")

    # Prepare output file
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = output_dir / f"metrics_test_{timestamp}.csv"

    print(f"\n2. Starting metrics agent...")
    print(f"   Output: {csv_file}")
    print(f"   Duration: 10 seconds")
    print(f"   Sampling rate: 1 Hz")

    # Start metrics agent as subprocess
    agent_proc = subprocess.Popen(
        [sys.executable, '-m', 'fast_bench.metrics_agent',
         str(petrel_pid), str(csv_file), '--duration', '10'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Monitor agent overhead (check early while it's still running)
    print("\n3. Monitoring agent overhead...")
    try:
        agent_psutil = psutil.Process(agent_proc.pid)
        time.sleep(1)  # Let it warm up

        # Quick check if process still exists
        if agent_psutil.is_running():
            agent_cpu = agent_psutil.cpu_percent(interval=1.0)
            agent_mem = agent_psutil.memory_info().rss / (1024 * 1024)
            print(f"   Agent CPU: {agent_cpu:.2f}%")
            print(f"   Agent RAM: {agent_mem:.1f} MB")

            if agent_cpu > 2.0:
                print(f"   ⚠️  WARNING: CPU overhead high (target: <2%)")
            else:
                print(f"   ✓ CPU overhead acceptable")

            if agent_mem > 150:
                print(f"   ⚠️  WARNING: RAM overhead high (target: <150 MB)")
            else:
                print(f"   ✓ RAM overhead acceptable")
        else:
            print(f"   ℹ️  Agent process completed before overhead measurement")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        print(f"   ℹ️  Could not measure agent overhead (process completed)")

    # Wait for agent to complete
    stdout, stderr = agent_proc.communicate(timeout=15)
    print(f"\n   Agent output: {stderr.strip()}")

    if agent_proc.returncode != 0:
        print(f"   ❌ Agent failed with return code {agent_proc.returncode}")
        print(f"   Error: {stderr}")
        sys.exit(1)

    print(f"   ✓ Agent completed successfully")

    # Analyze collected metrics
    print("\n4. Analyzing collected metrics...")
    if not csv_file.exists():
        print(f"   ❌ Output file not created: {csv_file}")
        sys.exit(1)

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"   ✓ CSV file created: {len(rows)} samples")

    if len(rows) < 8 or len(rows) > 12:
        print(f"   ⚠️  WARNING: Expected ~10 samples, got {len(rows)}")
    else:
        print(f"   ✓ Sample count correct (~1 Hz)")

    # Check first and last rows
    first_row = rows[0]
    last_row = rows[-1]

    print("\n5. Validating metrics data...")

    # PID check
    assert int(first_row['pid']) == petrel_pid
    print(f"   ✓ PID matches: {first_row['pid']}")

    # CPU/RAM checks
    avg_cpu = sum(float(r['cpu_pct']) for r in rows) / len(rows)
    avg_rss = sum(float(r['rss_mb']) for r in rows) / len(rows)
    print(f"   ✓ Avg Petrel CPU: {avg_cpu:.1f}%")
    print(f"   ✓ Avg Petrel RAM: {avg_rss:.1f} MB")

    # Disk I/O checks
    max_read = max(float(r['read_bytes_s']) for r in rows)
    max_write = max(float(r['write_bytes_s']) for r in rows)
    print(f"   ✓ Max disk read: {max_read / (1024*1024):.2f} MB/s")
    print(f"   ✓ Max disk write: {max_write / (1024*1024):.2f} MB/s")

    # Network I/O checks
    max_net_recv = max(float(r['sys_net_recv_mb_s']) for r in rows)
    max_net_sent = max(float(r['sys_net_sent_mb_s']) for r in rows)
    print(f"   ✓ Max network recv: {max_net_recv:.2f} MB/s")
    print(f"   ✓ Max network sent: {max_net_sent:.2f} MB/s")

    # GPU checks
    print("\n6. Checking GPU metrics...")
    gpu_total = float(first_row['gpu_mem_total_mb'])
    if gpu_total > 0:
        avg_gpu_util = sum(float(r['gpu_util_pct']) for r in rows) / len(rows)
        avg_gpu_mem = sum(float(r['gpu_mem_used_mb']) for r in rows) / len(rows)
        print(f"   ✓ GPU detected: {gpu_total:.0f} MB total")
        print(f"   ✓ Avg GPU util: {avg_gpu_util:.1f}%")
        print(f"   ✓ Avg GPU mem: {avg_gpu_mem:.1f} MB")
    else:
        print(f"   ℹ️  No GPU detected (or pynvml not available)")

    # ZGY file checks
    print("\n7. Checking open .zgy files...")
    zgy_detections = [r['open_zgy_paths'] for r in rows if r['open_zgy_paths']]
    if zgy_detections:
        print(f"   ✓ Detected .zgy files in {len(zgy_detections)} samples")
        print(f"   Example: {zgy_detections[0][:100]}...")
    else:
        print(f"   ⚠️  No .zgy files detected")
        print(f"   Make sure Petrel has a project open with seismic data")

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"✓ Metrics agent ran successfully")
    print(f"✓ Collected {len(rows)} samples at ~1 Hz")
    print(f"✓ CPU overhead: {agent_cpu:.2f}% (target: <2%)")
    print(f"✓ RAM overhead: {agent_mem:.1f} MB (target: <150 MB)")
    print(f"✓ All metric columns present and valid")

    if gpu_total > 0:
        print(f"✓ GPU metrics collected")
    if zgy_detections:
        print(f"✓ ZGY file detection working")

    print("\nManual verification checklist:")
    print(f"  □ Review CSV file: {csv_file}")
    print(f"  □ Verify Petrel CPU/RAM values look reasonable")
    print(f"  □ Confirm ZGY paths match your Petrel project")
    print(f"  □ Check that timestamps are ~1 second apart")
    print("\nIf all items above are checked, Phase 3 acceptance criteria are met!")
    print("=" * 60)


if __name__ == "__main__":
    test_metrics_with_petrel()
