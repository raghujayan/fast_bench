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
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        self.link_speed_mbps = None  # Will be detected from NIC

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
        max_speed = 0
        for name, stats in net_if.items():
            if stats.isup:
                nic_info = {
                    'name': name,
                    'speed_mbps': stats.speed
                }
                nics.append(nic_info)
                print(f"  NIC: {name} ({stats.speed} Mbps)")

                # Track maximum link speed (excluding loopback)
                if 'loopback' not in name.lower() and stats.speed > max_speed:
                    max_speed = stats.speed

        specs['nics'] = nics

        # Store max link speed for utilization calculations
        if max_speed > 0:
            self.link_speed_mbps = max_speed
            print(f"  Primary link speed: {self.link_speed_mbps} Mbps")

        self.results['machine'] = specs
        return specs

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

        # Debug: Print file size to verify file is readable
        try:
            file_size_mb = test_file.stat().st_size / (1024 * 1024)
            print(f"    File size: {file_size_mb:.1f} MB")
        except Exception as e:
            print(f"    ⚠️  Cannot stat file: {e}")
            return {'success': False, 'error': f'Cannot access file: {e}'}

        chunk_size = chunk_size_mb * 1024 * 1024
        bytes_read = 0
        start_time = time.time()
        chunk_times = []

        # Get initial network stats for bandwidth calculation
        try:
            net_io_start = psutil.net_io_counters()
        except Exception as e:
            print(f"    ⚠️  Cannot get network stats: {e}")
            net_io_start = None

        # Debug: Show path details
        print(f"    Path type: {type(test_file)}")
        print(f"    Path string: {str(test_file)}")
        print(f"    Path repr: {repr(test_file)}")
        print(f"    Path absolute: {test_file.absolute()}")

        # Try multiple approaches
        try:
            print(f"    Attempting to open file...")
            # Try with string conversion first
            path_str = str(test_file)
            print(f"    Using path string: {path_str!r}")
            with open(path_str, 'rb') as f:
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

            # Calculate actual network bandwidth used (if we got initial stats)
            if net_io_start:
                try:
                    net_io_end = psutil.net_io_counters()
                    net_bytes_recv = net_io_end.bytes_recv - net_io_start.bytes_recv
                    net_bandwidth_mbs = (net_bytes_recv / (1024 * 1024)) / elapsed
                    net_bandwidth_mbps = net_bandwidth_mbs * 8
                except Exception as e:
                    print(f"    ⚠️  Cannot calculate network bandwidth: {e}")
                    # Fallback: estimate from throughput
                    net_bandwidth_mbs = throughput_mbs
                    net_bandwidth_mbps = throughput_mbs * 8
            else:
                # Fallback if we couldn't get initial stats
                net_bandwidth_mbs = throughput_mbs
                net_bandwidth_mbps = throughput_mbs * 8

            chunk_times.sort()
            p95_idx = int(len(chunk_times) * 0.95)
            p99_idx = int(len(chunk_times) * 0.99)

            # Calculate link utilization if we know link speed
            link_utilization_pct = 0
            if self.link_speed_mbps and self.link_speed_mbps > 0:
                link_utilization_pct = (net_bandwidth_mbps / self.link_speed_mbps) * 100

            stats = {
                'success': True,
                'duration_sec': elapsed,
                'bytes_read': bytes_read,
                'throughput_mbs': throughput_mbs,
                'network_bandwidth_mbs': net_bandwidth_mbs,
                'network_bandwidth_mbps': net_bandwidth_mbps,
                'link_utilization_pct': link_utilization_pct,
                'chunk_count': len(chunk_times),
                'chunk_time_p95_ms': chunk_times[p95_idx] * 1000 if p95_idx < len(chunk_times) else 0,
                'chunk_time_p99_ms': chunk_times[p99_idx] * 1000 if p99_idx < len(chunk_times) else 0,
            }

            if link_utilization_pct > 0:
                print(f"    ✓ Throughput: {throughput_mbs:.1f} MB/s ({net_bandwidth_mbps:.0f} Mbps, {link_utilization_pct:.0f}% link utilization)")
            else:
                print(f"    ✓ Throughput: {throughput_mbs:.1f} MB/s ({net_bandwidth_mbps:.0f} Mbps network)")
            print(f"    ✓ Chunk times: p95={stats['chunk_time_p95_ms']:.1f}ms p99={stats['chunk_time_p99_ms']:.1f}ms")
            return stats

        except Exception as e:
            print(f"    ❌ Error: {e}")
            return {'success': False, 'error': str(e)}

    def test_azure_throughput(self, sas_urls: List[str], duration_sec: int = 10, chunk_size_mb: int = 8) -> Dict[str, Any]:
        """
        Test Azure Blob throughput using single-threaded ranged GETs.

        Args:
            sas_urls: List of SAS URLs to test
            duration_sec: Duration to test
            chunk_size_mb: Chunk size in MB

        Returns:
            Dictionary with throughput statistics
        """
        print(f"\n  Testing Azure Blob throughput - single-threaded ({len(sas_urls)} URLs)")

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

            # Calculate link utilization if we know link speed
            link_utilization_pct = 0
            if self.link_speed_mbps and self.link_speed_mbps > 0:
                link_utilization_pct = (net_bandwidth_mbps / self.link_speed_mbps) * 100

            stats = {
                'success': True,
                'duration_sec': elapsed,
                'bytes_read': bytes_read,
                'throughput_mbs': throughput_mbs,
                'network_bandwidth_mbs': net_bandwidth_mbs,
                'network_bandwidth_mbps': net_bandwidth_mbps,
                'link_utilization_pct': link_utilization_pct,
                'chunk_count': len(chunk_times),
                'chunk_time_p95_ms': chunk_times[p95_idx] * 1000 if p95_idx < len(chunk_times) else 0,
                'chunk_time_p99_ms': chunk_times[p99_idx] * 1000 if p99_idx < len(chunk_times) else 0,
            }

            if link_utilization_pct > 0:
                print(f"    ✓ Throughput: {throughput_mbs:.1f} MB/s ({net_bandwidth_mbps:.0f} Mbps, {link_utilization_pct:.0f}% link utilization)")
            else:
                print(f"    ✓ Throughput: {throughput_mbs:.1f} MB/s ({net_bandwidth_mbps:.0f} Mbps network)")
            print(f"    ✓ Chunk times: p95={stats['chunk_time_p95_ms']:.1f}ms p99={stats['chunk_time_p99_ms']:.1f}ms")
            return stats

        except Exception as e:
            print(f"    ❌ Error: {e}")
            return {'success': False, 'error': str(e)}

    def _download_chunk_worker(self, url: str, chunk_idx: int, chunk_size: int) -> tuple[int, float]:
        """
        Worker function for parallel Azure downloads.

        Args:
            url: SAS URL to download from
            chunk_idx: Chunk index
            chunk_size: Size of chunk in bytes

        Returns:
            Tuple of (bytes_downloaded, elapsed_time)
        """
        range_start = (chunk_idx * chunk_size) % (100 * 1024 * 1024)
        range_end = range_start + chunk_size - 1
        headers = {'Range': f'bytes={range_start}-{range_end}'}

        start = time.time()
        response = requests.get(url, headers=headers, timeout=30)
        elapsed = time.time() - start

        if response.status_code in [200, 206]:
            return (len(response.content), elapsed)
        return (0, elapsed)

    def test_azure_throughput_parallel(self, sas_urls: List[str], duration_sec: int = 15,
                                       chunk_size_mb: int = 8, workers: int = 8) -> Dict[str, Any]:
        """
        Test Azure Blob throughput using parallel ranged GETs.
        This simulates how FAST SDK and modern download tools work.

        Args:
            sas_urls: List of SAS URLs to test
            duration_sec: Duration to test (default 15s for better saturation)
            chunk_size_mb: Chunk size in MB
            workers: Number of parallel download threads

        Returns:
            Dictionary with throughput statistics
        """
        print(f"\n  Testing Azure Blob throughput - multi-threaded ({workers} parallel connections)")

        if not sas_urls:
            print(f"    ⚠️  No SAS URLs configured, skipping")
            return {'success': False, 'error': 'No SAS URLs'}

        chunk_size = chunk_size_mb * 1024 * 1024
        bytes_read = 0
        start_time = time.time()
        chunk_times = []
        chunk_idx = 0

        # Get initial network stats for bandwidth calculation
        net_io_start = psutil.net_io_counters()

        try:
            last_print = start_time
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {}

                # Keep submitting work until duration expires
                while time.time() - start_time < duration_sec:
                    # Submit new work if we have capacity
                    while len(futures) < workers and time.time() - start_time < duration_sec:
                        url = sas_urls[chunk_idx % len(sas_urls)]
                        future = executor.submit(self._download_chunk_worker, url, chunk_idx, chunk_size)
                        futures[future] = time.time()
                        chunk_idx += 1

                    # Check for completed futures
                    done_futures = [f for f in futures if f.done()]
                    for future in done_futures:
                        try:
                            chunk_bytes, chunk_time = future.result()
                            bytes_read += chunk_bytes
                            chunk_times.append(chunk_time)
                        except Exception as e:
                            print(f"    ⚠️  Download error: {e}")
                        finally:
                            del futures[future]

                    # Progress indicator every 3 seconds
                    now = time.time()
                    if now - last_print >= 3:
                        elapsed = now - start_time
                        interim_throughput = (bytes_read / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                        print(f"    ... {elapsed:.0f}s: {interim_throughput:.1f} MB/s ({len(chunk_times)} chunks)")
                        last_print = now

                    # Small sleep to avoid busy loop
                    time.sleep(0.01)

                # Wait for remaining futures
                for future in as_completed(futures.keys(), timeout=5):
                    try:
                        chunk_bytes, chunk_time = future.result()
                        bytes_read += chunk_bytes
                        chunk_times.append(chunk_time)
                    except Exception as e:
                        print(f"    ⚠️  Download error: {e}")

            elapsed = time.time() - start_time
            throughput_mbs = (bytes_read / (1024 * 1024)) / elapsed

            # Calculate actual network bandwidth used
            net_io_end = psutil.net_io_counters()
            net_bytes_recv = net_io_end.bytes_recv - net_io_start.bytes_recv
            net_bandwidth_mbs = (net_bytes_recv / (1024 * 1024)) / elapsed
            net_bandwidth_mbps = net_bandwidth_mbs * 8

            chunk_times.sort()
            p95_idx = int(len(chunk_times) * 0.95) if chunk_times else 0
            p99_idx = int(len(chunk_times) * 0.99) if chunk_times else 0

            # Calculate link utilization if we know link speed
            link_utilization_pct = 0
            if self.link_speed_mbps and self.link_speed_mbps > 0:
                link_utilization_pct = (net_bandwidth_mbps / self.link_speed_mbps) * 100

            stats = {
                'success': True,
                'duration_sec': elapsed,
                'bytes_read': bytes_read,
                'throughput_mbs': throughput_mbs,
                'network_bandwidth_mbs': net_bandwidth_mbs,
                'network_bandwidth_mbps': net_bandwidth_mbps,
                'link_utilization_pct': link_utilization_pct,
                'workers': workers,
                'chunk_count': len(chunk_times),
                'chunk_time_p95_ms': chunk_times[p95_idx] * 1000 if p95_idx < len(chunk_times) else 0,
                'chunk_time_p99_ms': chunk_times[p99_idx] * 1000 if p99_idx < len(chunk_times) else 0,
            }

            if link_utilization_pct > 0:
                print(f"    ✓ Throughput: {throughput_mbs:.1f} MB/s ({net_bandwidth_mbps:.0f} Mbps, {link_utilization_pct:.0f}% link utilization)")
            else:
                print(f"    ✓ Throughput: {throughput_mbs:.1f} MB/s ({net_bandwidth_mbps:.0f} Mbps network)")
            print(f"    ✓ Chunk times: p95={stats['chunk_time_p95_ms']:.1f}ms p99={stats['chunk_time_p99_ms']:.1f}ms")
            return stats

        except Exception as e:
            print(f"    ❌ Error: {e}")
            return {'success': False, 'error': str(e)}

    def _find_azcopy(self) -> Optional[str]:
        """
        Find azcopy executable, checking common installation locations.

        Returns:
            Path to azcopy executable, or None if not found
        """
        import shutil

        # Try standard PATH first
        azcopy_path = shutil.which('azcopy')
        if azcopy_path:
            return azcopy_path

        # Windows-specific: check winget installation location
        if sys.platform == "win32":
            # Winget installs to deep paths like:
            # C:\Users\{user}\AppData\Local\Microsoft\WinGet\Packages\Microsoft.Azure.AZCopy.10_...\azcopy_windows_amd64_10.30.0\azcopy.exe
            winget_base = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"

            if winget_base.exists():
                # Search for azcopy.exe in WinGet packages
                for package_dir in winget_base.glob("Microsoft.Azure.AZCopy.*"):
                    for azcopy_exe in package_dir.rglob("azcopy.exe"):
                        # Verify it works
                        try:
                            result = subprocess.run([str(azcopy_exe), '--version'],
                                                   capture_output=True, timeout=5)
                            if result.returncode == 0:
                                return str(azcopy_exe)
                        except:
                            pass

            # Also check Program Files
            program_files = [
                Path("C:/Program Files/azcopy"),
                Path("C:/Program Files (x86)/azcopy"),
            ]
            for pf in program_files:
                if pf.exists():
                    azcopy_exe = pf / "azcopy.exe"
                    if azcopy_exe.exists():
                        return str(azcopy_exe)

        return None

    def test_azcopy_benchmark(self, sas_url: str, duration_sec: int = 10) -> Dict[str, Any]:
        """
        Test Azure Blob throughput using azcopy benchmark mode.
        azcopy bench uploads/downloads data to measure maximum throughput with optimized parallelism.

        Args:
            sas_url: SAS URL to an Azure Blob container or file
            duration_sec: Duration to test (azcopy uses block count instead)

        Returns:
            Dictionary with throughput statistics
        """
        print(f"    Testing azcopy benchmark to Azure Blob")

        # Find azcopy executable
        azcopy_path = self._find_azcopy()
        if not azcopy_path:
            print(f"    ⚠️  azcopy not found, skipping")
            print(f"    Hint: Install with 'winget install azcopy' or download from https://aka.ms/downloadazcopy")
            return {'success': False, 'error': 'azcopy not installed'}

        # azcopy bench mode: downloads random data to measure throughput
        # --size-per-file: size of each file (default 256MB)
        # --num-files: number of files to transfer (we'll use duration to estimate)
        # Mode: download from blob to null (doesn't write to disk)

        # Estimate number of 64MB files to download for desired duration
        # Assuming ~200 MB/s, we need ~3 files per second
        num_files = max(5, duration_sec * 3)
        file_size_mb = 64

        # Get initial network stats
        net_io_start = psutil.net_io_counters()

        # Run azcopy bench in download mode
        cmd = [
            azcopy_path, 'bench',
            sas_url,
            '--mode', 'download',
            '--size-per-file', f'{file_size_mb}M',
            '--file-count', str(num_files),
            '--delete-test-data'  # Clean up after test
        ]

        try:
            print(f"    Running: azcopy bench (download {num_files} x {file_size_mb}MB files)")
            print(f"    Using: {azcopy_path}")
            print(f"    This may take 3-5 minutes...")
            print(f"    Command: {' '.join(cmd)}")
            start_time = time.time()

            # Run azcopy without capturing output so we can see progress in real-time
            result = subprocess.run(cmd, text=True, timeout=300)
            elapsed = time.time() - start_time
            print(f"    Completed in {elapsed:.1f} seconds")

            # Get final network stats
            net_io_end = psutil.net_io_counters()
            net_bytes_recv = net_io_end.bytes_recv - net_io_start.bytes_recv
            net_bandwidth_mbs = (net_bytes_recv / (1024 * 1024)) / elapsed
            net_bandwidth_mbps = net_bandwidth_mbs * 8

            if result.returncode != 0:
                print(f"    ⚠️  azcopy benchmark failed (exit code {result.returncode}), skipping")
                return {'success': False, 'error': f'azcopy exit code {result.returncode}'}

            # Since we're not capturing output, calculate throughput from network stats
            # azcopy bench output goes directly to console for user to see
            throughput_mbs = net_bandwidth_mbs
            bytes_transferred = net_bytes_recv
            files_transferred = num_files  # Assume all completed if exit code 0

            # Calculate link utilization
            link_utilization_pct = 0
            if self.link_speed_mbps and self.link_speed_mbps > 0:
                link_utilization_pct = (net_bandwidth_mbps / self.link_speed_mbps) * 100

            stats = {
                'success': True,
                'duration_sec': elapsed,
                'throughput_mbs': throughput_mbs,
                'network_bandwidth_mbs': net_bandwidth_mbs,
                'network_bandwidth_mbps': net_bandwidth_mbps,
                'link_utilization_pct': link_utilization_pct,
                'bytes_transferred': bytes_transferred if bytes_transferred > 0 else net_bytes_recv,
                'files_transferred': files_transferred,
                'num_files_requested': num_files,
                'file_size_mb': file_size_mb
            }

            if link_utilization_pct > 0:
                print(f"    ✓ Throughput: {throughput_mbs:.1f} MB/s ({net_bandwidth_mbps:.0f} Mbps, {link_utilization_pct:.0f}% link utilization)")
            else:
                print(f"    ✓ Throughput: {throughput_mbs:.1f} MB/s ({net_bandwidth_mbps:.0f} Mbps)")

            if files_transferred > 0:
                print(f"    ✓ Transferred: {files_transferred}/{num_files} files ({bytes_transferred / (1024**2):.1f} MB)")

            return stats

        except subprocess.TimeoutExpired:
            print(f"    ⚠️  azcopy benchmark timeout, skipping")
            return {'success': False, 'error': 'timeout'}
        except Exception as e:
            print(f"    ⚠️  azcopy benchmark error, skipping")
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

        # Azure throughput - single-threaded
        if self.config.data_sources.azure_blob.sas_download_urls:
            azure_results['throughput_single'] = self.test_azure_throughput(
                self.config.data_sources.azure_blob.sas_download_urls
            )
        else:
            print(f"  ⚠️  No Azure SAS URLs configured")
            azure_results['throughput_single'] = {'success': False, 'error': 'No SAS URLs'}

        self.results['azure'] = azure_results

        # Path Capacity Tests
        print("\n" + "=" * 60)
        print("Path Capacity Tests (VM ↔ Azure)")
        print("=" * 60)
        print("These tests measure maximum achievable bandwidth on the VM-to-Azure path.")

        capacity_results = {}

        # Multi-threaded Azure download (simulates FAST SDK behavior)
        if self.config.data_sources.azure_blob.sas_download_urls:
            capacity_results['azure_parallel'] = self.test_azure_throughput_parallel(
                self.config.data_sources.azure_blob.sas_download_urls,
                workers=8
            )
        else:
            capacity_results['azure_parallel'] = {'success': False, 'error': 'No SAS URLs'}

        # azcopy benchmark test (if configured)
        # azcopy bench mode measures maximum Azure throughput with optimized parallelism
        # Requires container-level SAS URL with write permissions
        if self.config.data_sources.azure_blob.azcopy_benchmark_url:
            print(f"\n  Note: azcopy benchmark uploads/downloads test data to measure max throughput")
            capacity_results['azcopy_bench'] = self.test_azcopy_benchmark(
                self.config.data_sources.azure_blob.azcopy_benchmark_url
            )
        else:
            print(f"\n  ⚠️  azcopy benchmark skipped (no container-level SAS URL configured)")
            print(f"  Hint: Add 'azcopy_benchmark_url' in config with write permissions")
            capacity_results['azcopy_bench'] = {'success': False, 'error': 'No azcopy benchmark URL configured'}

        self.results['capacity'] = capacity_results

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
            if nas.get('throughput', {}).get('success'):
                tp = nas['throughput']
                f.write(f"Throughput: {tp['throughput_mbs']:.1f} MB/s ({tp['network_bandwidth_mbps']:.0f} Mbps, {tp['link_utilization_pct']:.0f}% link util)\n")
            f.write("\n")

            # Azure results
            azure = self.results['azure']
            f.write("AZURE BLOB PERFORMANCE\n")
            f.write("-" * 60 + "\n")
            if azure.get('throughput_single', {}).get('success'):
                tp = azure['throughput_single']
                f.write(f"Throughput (single-threaded): {tp['throughput_mbs']:.1f} MB/s ({tp['network_bandwidth_mbps']:.0f} Mbps, {tp['link_utilization_pct']:.0f}% link util)\n")
            f.write("\n")

            # Path Capacity results
            if 'capacity' in self.results:
                capacity = self.results['capacity']
                f.write("PATH CAPACITY (VM ↔ AZURE)\n")
                f.write("-" * 60 + "\n")
                if capacity.get('azure_parallel', {}).get('success'):
                    ap = capacity['azure_parallel']
                    f.write(f"Azure Multi-threaded ({ap['workers']} workers): {ap['throughput_mbs']:.1f} MB/s ({ap['network_bandwidth_mbps']:.0f} Mbps, {ap['link_utilization_pct']:.0f}% link util)\n")
                if capacity.get('azcopy_bench', {}).get('success'):
                    az = capacity['azcopy_bench']
                    f.write(f"azcopy benchmark: {az['throughput_mbs']:.1f} MB/s ({az['network_bandwidth_mbps']:.0f} Mbps, {az['link_utilization_pct']:.0f}% link util)\n")
                    if az.get('files_transferred', 0) > 0:
                        f.write(f"  Files: {az['files_transferred']}/{az['num_files_requested']} transferred\n")
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
