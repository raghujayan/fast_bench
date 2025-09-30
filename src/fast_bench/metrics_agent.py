"""
Metrics collection agent - runs as subprocess to monitor process metrics.

Usage:
    python -m fast_bench.metrics_agent <pid> <output_csv> [--duration SECONDS]

Example:
    python -m fast_bench.metrics_agent 12345 metrics.csv --duration 60
"""

import sys
import time
import csv
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

import psutil

# Platform-specific imports
if sys.platform == "win32":
    try:
        import pynvml
        PYNVML_AVAILABLE = True
    except ImportError:
        PYNVML_AVAILABLE = False
else:
    PYNVML_AVAILABLE = False


class MetricsAgent:
    """Low-overhead metrics collection agent."""

    def __init__(self, pid: int, output_csv: Path):
        """
        Initialize metrics agent.

        Args:
            pid: Process ID to monitor (typically Petrel)
            output_csv: Path to output CSV file
        """
        self.pid = pid
        self.output_csv = Path(output_csv)
        self.process = psutil.Process(pid)
        self.gpu_initialized = False
        self.gpu_handle = None

        # Initialize GPU monitoring if available
        if PYNVML_AVAILABLE and sys.platform == "win32":
            try:
                pynvml.nvmlInit()
                self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                self.gpu_initialized = True
            except Exception as e:
                print(f"Warning: GPU monitoring not available: {e}", file=sys.stderr)

        # Track previous I/O counters for rate calculation
        self.prev_io = None
        self.prev_net = None
        self.prev_time = None

    def collect_sample(self) -> Dict[str, Any]:
        """
        Collect a single metrics sample.

        Returns:
            Dictionary of metrics
        """
        now = time.time()
        sample = {
            'ts': datetime.now().isoformat(),
            'pid': self.pid,
        }

        # CPU and Memory
        try:
            sample['cpu_pct'] = self.process.cpu_percent(interval=None)
            mem_info = self.process.memory_info()
            sample['rss_mb'] = mem_info.rss / (1024 * 1024)
            sample['vms_mb'] = mem_info.vms / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"Error collecting CPU/memory: {e}", file=sys.stderr)
            sample['cpu_pct'] = 0.0
            sample['rss_mb'] = 0.0
            sample['vms_mb'] = 0.0

        # Disk I/O (per-process) - Windows only
        try:
            if sys.platform == "win32":
                io_counters = self.process.io_counters()

                if self.prev_io and self.prev_time:
                    elapsed = now - self.prev_time
                    if elapsed > 0:
                        read_bytes = io_counters.read_bytes - self.prev_io.read_bytes
                        write_bytes = io_counters.write_bytes - self.prev_io.write_bytes
                        read_count = io_counters.read_count - self.prev_io.read_count
                        write_count = io_counters.write_count - self.prev_io.write_count

                        sample['read_bytes_s'] = read_bytes / elapsed
                        sample['write_bytes_s'] = write_bytes / elapsed
                        sample['read_cnt_s'] = read_count / elapsed
                        sample['write_cnt_s'] = write_count / elapsed
                    else:
                        sample['read_bytes_s'] = 0.0
                        sample['write_bytes_s'] = 0.0
                        sample['read_cnt_s'] = 0.0
                        sample['write_cnt_s'] = 0.0
                else:
                    sample['read_bytes_s'] = 0.0
                    sample['write_bytes_s'] = 0.0
                    sample['read_cnt_s'] = 0.0
                    sample['write_cnt_s'] = 0.0

                self.prev_io = io_counters
            else:
                # macOS/Linux: io_counters not available per-process
                sample['read_bytes_s'] = 0.0
                sample['write_bytes_s'] = 0.0
                sample['read_cnt_s'] = 0.0
                sample['write_cnt_s'] = 0.0
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            sample['read_bytes_s'] = 0.0
            sample['write_bytes_s'] = 0.0
            sample['read_cnt_s'] = 0.0
            sample['write_cnt_s'] = 0.0

        # System-wide disk I/O
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                sample['sys_disk_read_mb_s'] = 0.0  # Will calculate on next sample
                sample['sys_disk_write_mb_s'] = 0.0
            else:
                sample['sys_disk_read_mb_s'] = 0.0
                sample['sys_disk_write_mb_s'] = 0.0
        except Exception:
            sample['sys_disk_read_mb_s'] = 0.0
            sample['sys_disk_write_mb_s'] = 0.0

        # System-wide network I/O
        try:
            net_io = psutil.net_io_counters()
            if net_io and self.prev_net and self.prev_time:
                elapsed = now - self.prev_time
                if elapsed > 0:
                    recv_bytes = net_io.bytes_recv - self.prev_net.bytes_recv
                    sent_bytes = net_io.bytes_sent - self.prev_net.bytes_sent
                    sample['sys_net_recv_mb_s'] = (recv_bytes / elapsed) / (1024 * 1024)
                    sample['sys_net_sent_mb_s'] = (sent_bytes / elapsed) / (1024 * 1024)
                else:
                    sample['sys_net_recv_mb_s'] = 0.0
                    sample['sys_net_sent_mb_s'] = 0.0
            else:
                sample['sys_net_recv_mb_s'] = 0.0
                sample['sys_net_sent_mb_s'] = 0.0

            if net_io:
                self.prev_net = net_io
        except Exception:
            sample['sys_net_recv_mb_s'] = 0.0
            sample['sys_net_sent_mb_s'] = 0.0

        # GPU metrics
        if self.gpu_initialized and self.gpu_handle:
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
                sample['gpu_util_pct'] = util.gpu
                sample['gpu_mem_used_mb'] = mem_info.used / (1024 * 1024)
                sample['gpu_mem_total_mb'] = mem_info.total / (1024 * 1024)
            except Exception as e:
                sample['gpu_util_pct'] = 0.0
                sample['gpu_mem_used_mb'] = 0.0
                sample['gpu_mem_total_mb'] = 0.0
        else:
            sample['gpu_util_pct'] = 0.0
            sample['gpu_mem_used_mb'] = 0.0
            sample['gpu_mem_total_mb'] = 0.0

        # FAST log metrics (optional, not implemented yet)
        sample['fast_req_latency_ms'] = 0.0
        sample['fast_req_bytes'] = 0.0
        sample['fast_req_cache_hit'] = 0

        # Open ZGY paths detection
        sample['open_zgy_paths'] = self._get_open_zgy_paths()

        self.prev_time = now
        return sample

    def _get_open_zgy_paths(self) -> str:
        """
        Detect open .zgy files from process open files.

        Returns:
            Semicolon-separated list of .zgy file paths
        """
        try:
            open_files = self.process.open_files()
            zgy_files = [f.path for f in open_files if f.path.lower().endswith('.zgy')]
            return ';'.join(zgy_files) if zgy_files else ''
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return ''

    def run(self, duration: Optional[int] = None):
        """
        Run metrics collection loop.

        Args:
            duration: Optional duration in seconds (None = run indefinitely)
        """
        # CSV column headers
        fieldnames = [
            'ts', 'pid', 'cpu_pct', 'rss_mb', 'vms_mb',
            'read_bytes_s', 'write_bytes_s', 'read_cnt_s', 'write_cnt_s',
            'sys_disk_read_mb_s', 'sys_disk_write_mb_s',
            'sys_net_recv_mb_s', 'sys_net_sent_mb_s',
            'gpu_util_pct', 'gpu_mem_used_mb', 'gpu_mem_total_mb',
            'fast_req_latency_ms', 'fast_req_bytes', 'fast_req_cache_hit',
            'open_zgy_paths'
        ]

        start_time = time.time()
        sample_count = 0

        # Open CSV file
        with open(self.output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            f.flush()

            print(f"Metrics agent started: monitoring PID {self.pid}", file=sys.stderr)
            print(f"Output: {self.output_csv}", file=sys.stderr)

            try:
                while True:
                    sample_start = time.time()

                    # Check duration limit
                    if duration and (time.time() - start_time) >= duration:
                        break

                    # Collect and write sample
                    try:
                        sample = self.collect_sample()
                        writer.writerow(sample)
                        f.flush()
                        sample_count += 1
                    except psutil.NoSuchProcess:
                        print(f"Process {self.pid} no longer exists", file=sys.stderr)
                        break
                    except Exception as e:
                        print(f"Error collecting sample: {e}", file=sys.stderr)

                    # Sleep to maintain 1 Hz sampling rate
                    elapsed = time.time() - sample_start
                    sleep_time = max(0, 1.0 - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)

            except KeyboardInterrupt:
                print("\nMetrics collection stopped by user", file=sys.stderr)

        elapsed_total = time.time() - start_time
        print(f"Metrics collection complete: {sample_count} samples in {elapsed_total:.1f}s", file=sys.stderr)

    def cleanup(self):
        """Clean up resources."""
        if self.gpu_initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass


def main():
    """Main entry point for metrics agent."""
    parser = argparse.ArgumentParser(description='Metrics collection agent')
    parser.add_argument('pid', type=int, help='Process ID to monitor')
    parser.add_argument('output_csv', type=Path, help='Output CSV file path')
    parser.add_argument('--duration', type=int, default=None,
                       help='Duration in seconds (default: run until stopped)')

    args = parser.parse_args()

    # Verify process exists
    if not psutil.pid_exists(args.pid):
        print(f"Error: Process {args.pid} does not exist", file=sys.stderr)
        sys.exit(1)

    agent = MetricsAgent(args.pid, args.output_csv)

    try:
        agent.run(duration=args.duration)
    finally:
        agent.cleanup()


if __name__ == '__main__':
    main()
