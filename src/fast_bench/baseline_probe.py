"""
Baseline probe - measures machine specs and network performance ceilings.

Usage:
    python -m fast_bench.baseline_probe [config_path]

Example:
    python -m fast_bench.baseline_probe config/config.yaml
"""

import sys
import json
import time
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import psutil
import requests

# Platform-specific imports
if sys.platform == "win32":
    try:
        import pynvml
        PYNVML_AVAILABLE = True
    except ImportError:
        PYNVML_AVAILABLE = False
else:
    PYNVML_AVAILABLE = False


class BaselineProbe:
    """Baseline performance probe for machine and network."""

    def __init__(self, config):
        """
        Initialize baseline probe.

        Args:
            config: Configuration object from config_schema
        """
        self.config = config
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'machine': {},
            'nas': {},
            'azure': {},
        }

    def collect_machine_specs(self) -> Dict[str, Any]:
        """
        Collect machine hardware specifications.

        Returns:
            Dictionary of machine specs
        """
        print("\n" + "=" * 60)
        print("Collecting Machine Specifications")
        print("=" * 60)

        specs = {
            'os': platform.system(),
            'os_version': platform.version(),
            'os_release': platform.release(),
            'machine': platform.machine(),
            'processor': platform.processor(),
        }

        # CPU
        specs['cpu_count_physical'] = psutil.cpu_count(logical=False)
        specs['cpu_count_logical'] = psutil.cpu_count(logical=True)
        specs['cpu_freq_mhz'] = psutil.cpu_freq().current if psutil.cpu_freq() else 0

        print(f"  CPU: {specs['cpu_count_physical']} cores ({specs['cpu_count_logical']} threads)")
        print(f"  Frequency: {specs['cpu_freq_mhz']:.0f} MHz")

        # RAM
        mem = psutil.virtual_memory()
        specs['ram_total_gb'] = mem.total / (1024 ** 3)
        specs['ram_available_gb'] = mem.available / (1024 ** 3)

        print(f"  RAM: {specs['ram_total_gb']:.1f} GB total, {specs['ram_available_gb']:.1f} GB available")

        # GPU
        if PYNVML_AVAILABLE and sys.platform == "win32":
            try:
                pynvml.nvmlInit()
                gpu_count = pynvml.nvmlDeviceGetCount()
                specs['gpu_count'] = gpu_count

                gpus = []
                for i in range(gpu_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle)
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

                    gpu_info = {
                        'name': name,
                        'memory_gb': mem_info.total / (1024 ** 3)
                    }
                    gpus.append(gpu_info)
                    print(f"  GPU {i}: {name} ({gpu_info['memory_gb']:.1f} GB)")

                specs['gpus'] = gpus
                pynvml.nvmlShutdown()
            except Exception as e:
                print(f"  GPU: Detection failed ({e})")
                specs['gpu_count'] = 0
                specs['gpus'] = []
        else:
            specs['gpu_count'] = 0
            specs['gpus'] = []

        # Network interfaces
        net_if = psutil.net_if_stats()
        nics = []
        for name, stats in net_if.items():
            if stats.isup:
                nic_info = {
                    'name': name,
                    'speed_mbps': stats.speed
                }
                nics.append(nic_info)
                print(f"  NIC: {name} ({stats.speed} Mbps)")

        specs['nics'] = nics

        self.results['machine'] = specs
        return specs

    def ping_host(self, host: str, count: int = 10) -> Dict[str, Any]:
        """
        Ping a host and collect RTT statistics.

        Args:
            host: Hostname or IP to ping
            count: Number of ping packets

        Returns:
            Dictionary with min/avg/max/p95 RTT in milliseconds
        """
        print(f"\n  Pinging {host} ({count} packets)...")

        if sys.platform == "win32":
            cmd = ['ping', '-n', str(count), host]
        else:
            cmd = ['ping', '-c', str(count), host]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                print(f"    ❌ Ping failed")
                return {'host': host, 'success': False}

            # Parse RTT from output
            rtts = []
            for line in result.stdout.split('\n'):
                if 'time=' in line.lower() or 'time<' in line.lower():
                    # Extract time value (handles both "time=10ms" and "time<1ms")
                    try:
                        time_part = line.split('time')[-1]
                        time_val = ''.join(c for c in time_part if c.isdigit() or c == '.')
                        if time_val:
                            rtts.append(float(time_val))
                    except:
                        pass

            if not rtts:
                print(f"    ⚠️  Could not parse RTT values")
                return {'host': host, 'success': False}

            rtts.sort()
            p95_idx = int(len(rtts) * 0.95)

            stats = {
                'host': host,
                'success': True,
                'count': len(rtts),
                'min_ms': min(rtts),
                'avg_ms': sum(rtts) / len(rtts),
                'max_ms': max(rtts),
                'p95_ms': rtts[p95_idx] if p95_idx < len(rtts) else max(rtts)
            }

            print(f"    ✓ RTT: min={stats['min_ms']:.1f}ms avg={stats['avg_ms']:.1f}ms p95={stats['p95_ms']:.1f}ms")
            return stats

        except Exception as e:
            print(f"    ❌ Ping error: {e}")
            return {'host': host, 'success': False, 'error': str(e)}

    def test_nas_throughput(self, test_file: Path, chunk_size_mb: int = 8, duration_sec: int = 10) -> Dict[str, Any]:
        """
        Test NAS read throughput.

        Args:
            test_file: Path to a large file on NAS for testing
            chunk_size_mb: Chunk size in MB
            duration_sec: Duration to test

        Returns:
            Dictionary with throughput statistics
        """
        print(f"\n  Testing NAS throughput: {test_file}")

        if not test_file.exists():
            print(f"    ⚠️  Test file not found, skipping")
            return {'success': False, 'error': 'File not found'}

        chunk_size = chunk_size_mb * 1024 * 1024
        bytes_read = 0
        start_time = time.time()
        chunk_times = []

        # Get initial network stats for bandwidth calculation
        net_io_start = psutil.net_io_counters()

        try:
            with open(test_file, 'rb') as f:
                while time.time() - start_time < duration_sec:
                    chunk_start = time.time()
                    data = f.read(chunk_size)
                    chunk_elapsed = time.time() - chunk_start

                    if not data:
                        # Reached EOF, seek back to start
                        f.seek(0)
                        continue

                    bytes_read += len(data)
                    chunk_times.append(chunk_elapsed)

            elapsed = time.time() - start_time
            throughput_mbs = (bytes_read / (1024 * 1024)) / elapsed

            # Calculate actual network bandwidth used
            net_io_end = psutil.net_io_counters()
            net_bytes_recv = net_io_end.bytes_recv - net_io_start.bytes_recv
            net_bandwidth_mbs = (net_bytes_recv / (1024 * 1024)) / elapsed
            net_bandwidth_mbps = net_bandwidth_mbs * 8

            chunk_times.sort()
            p95_idx = int(len(chunk_times) * 0.95)
            p99_idx = int(len(chunk_times) * 0.99)

            stats = {
                'success': True,
                'duration_sec': elapsed,
                'bytes_read': bytes_read,
                'throughput_mbs': throughput_mbs,
                'network_bandwidth_mbs': net_bandwidth_mbs,
                'network_bandwidth_mbps': net_bandwidth_mbps,
                'chunk_count': len(chunk_times),
                'chunk_time_p95_ms': chunk_times[p95_idx] * 1000 if p95_idx < len(chunk_times) else 0,
                'chunk_time_p99_ms': chunk_times[p99_idx] * 1000 if p99_idx < len(chunk_times) else 0,
            }

            print(f"    ✓ Throughput: {throughput_mbs:.1f} MB/s ({net_bandwidth_mbps:.0f} Mbps network)")
            print(f"    ✓ Chunk times: p95={stats['chunk_time_p95_ms']:.1f}ms p99={stats['chunk_time_p99_ms']:.1f}ms")
            return stats

        except Exception as e:
            print(f"    ❌ Error: {e}")
            return {'success': False, 'error': str(e)}

    def test_azure_throughput(self, sas_urls: List[str], duration_sec: int = 10, chunk_size_mb: int = 8) -> Dict[str, Any]:
        """
        Test Azure Blob throughput using ranged GETs.

        Args:
            sas_urls: List of SAS URLs to test
            duration_sec: Duration to test
            chunk_size_mb: Chunk size in MB

        Returns:
            Dictionary with throughput statistics
        """
        print(f"\n  Testing Azure Blob throughput ({len(sas_urls)} URLs)")

        if not sas_urls:
            print(f"    ⚠️  No SAS URLs configured, skipping")
            return {'success': False, 'error': 'No SAS URLs'}

        chunk_size = chunk_size_mb * 1024 * 1024
        bytes_read = 0
        start_time = time.time()
        chunk_times = []
        url_idx = 0

        # Get initial network stats for bandwidth calculation
        net_io_start = psutil.net_io_counters()

        try:
            while time.time() - start_time < duration_sec:
                url = sas_urls[url_idx % len(sas_urls)]
                url_idx += 1

                # Ranged GET request
                range_start = (url_idx * chunk_size) % (100 * 1024 * 1024)  # Rotate through first 100MB
                range_end = range_start + chunk_size - 1

                headers = {'Range': f'bytes={range_start}-{range_end}'}

                chunk_start = time.time()
                response = requests.get(url, headers=headers, timeout=30)
                chunk_elapsed = time.time() - chunk_start

                if response.status_code in [200, 206]:  # 206 = Partial Content
                    bytes_read += len(response.content)
                    chunk_times.append(chunk_elapsed)
                else:
                    print(f"    ⚠️  HTTP {response.status_code}")

            elapsed = time.time() - start_time
            throughput_mbs = (bytes_read / (1024 * 1024)) / elapsed

            # Calculate actual network bandwidth used
            net_io_end = psutil.net_io_counters()
            net_bytes_recv = net_io_end.bytes_recv - net_io_start.bytes_recv
            net_bandwidth_mbs = (net_bytes_recv / (1024 * 1024)) / elapsed
            net_bandwidth_mbps = net_bandwidth_mbs * 8

            chunk_times.sort()
            p95_idx = int(len(chunk_times) * 0.95)
            p99_idx = int(len(chunk_times) * 0.99)

            stats = {
                'success': True,
                'duration_sec': elapsed,
                'bytes_read': bytes_read,
                'throughput_mbs': throughput_mbs,
                'network_bandwidth_mbs': net_bandwidth_mbs,
                'network_bandwidth_mbps': net_bandwidth_mbps,
                'chunk_count': len(chunk_times),
                'chunk_time_p95_ms': chunk_times[p95_idx] * 1000 if p95_idx < len(chunk_times) else 0,
                'chunk_time_p99_ms': chunk_times[p99_idx] * 1000 if p99_idx < len(chunk_times) else 0,
            }

            print(f"    ✓ Throughput: {throughput_mbs:.1f} MB/s ({net_bandwidth_mbps:.0f} Mbps network)")
            print(f"    ✓ Chunk times: p95={stats['chunk_time_p95_ms']:.1f}ms p99={stats['chunk_time_p99_ms']:.1f}ms")
            return stats

        except Exception as e:
            print(f"    ❌ Error: {e}")
            return {'success': False, 'error': str(e)}

    def run(self) -> Dict[str, Any]:
        """
        Run complete baseline probe.

        Returns:
            Complete results dictionary
        """
        print("\n" + "=" * 60)
        print("FAST Bench - Baseline Probe")
        print("=" * 60)

        # Machine specs
        self.collect_machine_specs()

        # NAS tests
        print("\n" + "=" * 60)
        print("NAS Performance Tests")
        print("=" * 60)

        nas_results = {}

        # NAS ping
        nas_results['ping'] = self.ping_host(self.config.benchmark.nas_ping_host)

        # NAS throughput (if test file exists)
        nas_test_path = Path(self.config.benchmark.nas_test_dir)
        if nas_test_path.exists():
            # Find a large file for testing
            test_files = list(nas_test_path.glob('*.zgy')) or list(nas_test_path.glob('*.*'))
            if test_files:
                nas_results['throughput'] = self.test_nas_throughput(test_files[0])
            else:
                print(f"  ⚠️  No test files found in {nas_test_path}")
                nas_results['throughput'] = {'success': False, 'error': 'No test files'}
        else:
            print(f"  ⚠️  NAS test directory not found: {nas_test_path}")
            nas_results['throughput'] = {'success': False, 'error': 'Directory not found'}

        self.results['nas'] = nas_results

        # Azure tests
        print("\n" + "=" * 60)
        print("Azure Blob Performance Tests")
        print("=" * 60)

        azure_results = {}

        # Azure ping
        for host in self.config.benchmark.azure_ping_hosts:
            azure_results[f'ping_{host}'] = self.ping_host(host)

        # Azure throughput
        if self.config.data_sources.azure_blob.sas_download_urls:
            azure_results['throughput'] = self.test_azure_throughput(
                self.config.data_sources.azure_blob.sas_download_urls
            )
        else:
            print(f"  ⚠️  No Azure SAS URLs configured")
            azure_results['throughput'] = {'success': False, 'error': 'No SAS URLs'}

        self.results['azure'] = azure_results

        return self.results

    def save_results(self, output_dir: Path):
        """
        Save baseline results to files.

        Args:
            output_dir: Directory to save results
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON
        json_path = output_dir / 'baseline.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n✓ Saved: {json_path}")

        # Save human-readable summary
        summary_path = output_dir / 'baseline_summary.txt'
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("FAST Bench - Baseline Summary\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Timestamp: {self.results['timestamp']}\n\n")

            # Machine specs
            machine = self.results['machine']
            f.write("MACHINE SPECS\n")
            f.write("-" * 60 + "\n")
            f.write(f"OS: {machine['os']} {machine['os_release']}\n")
            f.write(f"CPU: {machine['cpu_count_physical']} cores / {machine['cpu_count_logical']} threads @ {machine['cpu_freq_mhz']:.0f} MHz\n")
            f.write(f"RAM: {machine['ram_total_gb']:.1f} GB total\n")
            f.write(f"GPU: {machine['gpu_count']} device(s)\n")
            for i, gpu in enumerate(machine.get('gpus', [])):
                f.write(f"  - {gpu['name']} ({gpu['memory_gb']:.1f} GB)\n")
            f.write("\n")

            # NAS results
            nas = self.results['nas']
            f.write("NAS PERFORMANCE\n")
            f.write("-" * 60 + "\n")
            if nas.get('ping', {}).get('success'):
                ping = nas['ping']
                f.write(f"Ping: {ping['avg_ms']:.1f}ms avg, {ping['p95_ms']:.1f}ms p95\n")
            if nas.get('throughput', {}).get('success'):
                tp = nas['throughput']
                f.write(f"Throughput: {tp['throughput_mbs']:.1f} MB/s\n")
            f.write("\n")

            # Azure results
            azure = self.results['azure']
            f.write("AZURE BLOB PERFORMANCE\n")
            f.write("-" * 60 + "\n")
            for key, value in azure.items():
                if key.startswith('ping_') and value.get('success'):
                    f.write(f"Ping {value['host']}: {value['avg_ms']:.1f}ms avg, {value['p95_ms']:.1f}ms p95\n")
            if azure.get('throughput', {}).get('success'):
                tp = azure['throughput']
                f.write(f"Throughput: {tp['throughput_mbs']:.1f} MB/s\n")
            f.write("\n")

        print(f"✓ Saved: {summary_path}")


def main():
    """Main entry point for baseline probe."""
    import sys
    from fast_bench.config_schema import load_config

    config_path = sys.argv[1] if len(sys.argv) > 1 else 'config/config.yaml'

    print(f"Loading configuration: {config_path}")
    config = load_config(config_path)

    probe = BaselineProbe(config)
    results = probe.run()

    # Save results to output directory
    output_dir = config.out_dir / 'baseline'
    probe.save_results(output_dir)

    print("\n" + "=" * 60)
    print("Baseline Probe Complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
