"""Tests for baseline probe functionality."""

import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from fast_bench.baseline_probe import BaselineProbe


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = Mock()
    config.benchmark = Mock()
    config.benchmark.nas_ping_host = "nas.example.com"
    config.benchmark.nas_test_dir = "/nas/test"
    config.benchmark.azure_ping_hosts = ["blob.core.windows.net"]
    config.benchmark.parallel_streams = 4
    config.benchmark.http_chunk_bytes = 8388608

    config.data_sources = Mock()
    config.data_sources.azure_blob = Mock()
    config.data_sources.azure_blob.sas_download_urls = [
        "https://test.blob.core.windows.net/container/file.bin?sig=test"
    ]

    config.out_dir = Path(tempfile.mkdtemp())

    return config


def test_baseline_probe_initialization(mock_config):
    """Test that BaselineProbe initializes correctly."""
    probe = BaselineProbe(mock_config)

    assert probe.config == mock_config
    assert 'timestamp' in probe.results
    assert 'machine' in probe.results
    assert 'nas' in probe.results
    assert 'azure' in probe.results


def test_collect_machine_specs(mock_config):
    """Test machine specifications collection."""
    probe = BaselineProbe(mock_config)
    specs = probe.collect_machine_specs()

    # Check required fields
    assert 'os' in specs
    assert 'cpu_count_physical' in specs
    assert 'cpu_count_logical' in specs
    assert 'ram_total_gb' in specs
    assert 'gpu_count' in specs
    assert 'nics' in specs

    # Check values are reasonable
    assert specs['cpu_count_physical'] > 0
    assert specs['cpu_count_logical'] >= specs['cpu_count_physical']
    assert specs['ram_total_gb'] > 0
    assert specs['gpu_count'] >= 0


@patch('subprocess.run')
def test_ping_host_success(mock_run, mock_config):
    """Test successful ping operation."""
    # Mock ping output (Windows format)
    mock_run.return_value = Mock(
        returncode=0,
        stdout="""
Reply from 10.0.0.1: bytes=32 time=10ms TTL=64
Reply from 10.0.0.1: bytes=32 time=12ms TTL=64
Reply from 10.0.0.1: bytes=32 time=11ms TTL=64
"""
    )

    probe = BaselineProbe(mock_config)
    result = probe.ping_host("test.example.com", count=3)

    assert result['success'] == True
    assert result['host'] == "test.example.com"
    assert 'min_ms' in result
    assert 'avg_ms' in result
    assert 'p95_ms' in result
    assert result['min_ms'] <= result['avg_ms'] <= result['max_ms']


@patch('subprocess.run')
def test_ping_host_failure(mock_run, mock_config):
    """Test failed ping operation."""
    mock_run.return_value = Mock(returncode=1, stdout="")

    probe = BaselineProbe(mock_config)
    result = probe.ping_host("nonexistent.example.com", count=3)

    assert result['success'] == False


def test_nas_throughput_file_not_found(mock_config):
    """Test NAS throughput when test file doesn't exist."""
    probe = BaselineProbe(mock_config)
    result = probe.test_nas_throughput(Path("/nonexistent/file.bin"))

    assert result['success'] == False
    assert 'error' in result


def test_nas_throughput_with_temp_file(mock_config):
    """Test NAS throughput with a temporary test file."""
    # Create a temporary file with some data
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
        test_file = Path(f.name)
        # Write 50 MB of data
        f.write(b'0' * (50 * 1024 * 1024))

    try:
        probe = BaselineProbe(mock_config)
        result = probe.test_nas_throughput(test_file, chunk_size_mb=8, duration_sec=2)

        assert result['success'] == True
        assert result['throughput_mbs'] > 0
        assert result['bytes_read'] > 0
        assert result['chunk_count'] > 0
        assert 'chunk_time_p95_ms' in result
        assert 'chunk_time_p99_ms' in result

    finally:
        test_file.unlink()


@patch('requests.get')
def test_azure_throughput_success(mock_get, mock_config):
    """Test Azure throughput measurement."""
    # Mock successful HTTP responses
    mock_response = Mock()
    mock_response.status_code = 206  # Partial content
    mock_response.content = b'0' * (8 * 1024 * 1024)  # 8 MB
    mock_get.return_value = mock_response

    probe = BaselineProbe(mock_config)
    result = probe.test_azure_throughput(
        mock_config.data_sources.azure_blob.sas_download_urls,
        duration_sec=2,
        chunk_size_mb=8
    )

    assert result['success'] == True
    assert result['throughput_mbs'] > 0
    assert result['bytes_read'] > 0
    assert result['chunk_count'] > 0


def test_azure_throughput_no_urls(mock_config):
    """Test Azure throughput with no SAS URLs."""
    probe = BaselineProbe(mock_config)
    result = probe.test_azure_throughput([], duration_sec=2)

    assert result['success'] == False
    assert 'error' in result


def test_save_results(mock_config):
    """Test saving baseline results to files."""
    probe = BaselineProbe(mock_config)

    # Populate some test data
    probe.results = {
        'timestamp': '2025-09-30T12:00:00',
        'machine': {
            'os': 'Test OS',
            'os_release': '10.0',
            'os_version': 'Test Version',
            'machine': 'x86_64',
            'processor': 'Test Processor',
            'cpu_count_physical': 8,
            'cpu_count_logical': 16,
            'cpu_freq_mhz': 3000,
            'ram_total_gb': 32.0,
            'ram_available_gb': 24.0,
            'gpu_count': 1,
            'gpus': [{'name': 'Test GPU', 'memory_gb': 16.0}],
            'nics': [{'name': 'eth0', 'speed_mbps': 1000}]
        },
        'nas': {
            'ping': {'success': True, 'avg_ms': 5.0, 'p95_ms': 10.0},
            'throughput': {'success': True, 'throughput_mbs': 100.0}
        },
        'azure': {
            'ping_blob.core.windows.net': {'success': True, 'host': 'blob.core.windows.net', 'avg_ms': 20.0, 'p95_ms': 30.0},
            'throughput': {'success': True, 'throughput_mbs': 200.0}
        }
    }

    output_dir = Path(tempfile.mkdtemp())

    try:
        probe.save_results(output_dir)

        # Check JSON file
        json_path = output_dir / 'baseline.json'
        assert json_path.exists()

        with open(json_path) as f:
            data = json.load(f)
            assert data['timestamp'] == '2025-09-30T12:00:00'
            assert data['machine']['cpu_count_physical'] == 8

        # Check summary file
        summary_path = output_dir / 'baseline_summary.txt'
        assert summary_path.exists()

        summary_text = summary_path.read_text()
        assert 'FAST Bench' in summary_text
        assert 'MACHINE SPECS' in summary_text
        assert 'NAS PERFORMANCE' in summary_text
        assert 'AZURE BLOB PERFORMANCE' in summary_text

    finally:
        # Cleanup
        if json_path.exists():
            json_path.unlink()
        if summary_path.exists():
            summary_path.unlink()
        output_dir.rmdir()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only GPU test")
def test_gpu_detection_on_windows(mock_config):
    """Test GPU detection on Windows."""
    probe = BaselineProbe(mock_config)
    specs = probe.collect_machine_specs()

    # GPU detection should work or gracefully fail
    assert 'gpu_count' in specs
    assert specs['gpu_count'] >= 0


def test_baseline_probe_json_serializable(mock_config):
    """Test that baseline results are JSON serializable."""
    probe = BaselineProbe(mock_config)
    probe.collect_machine_specs()

    # Should not raise exception
    json_str = json.dumps(probe.results)
    assert isinstance(json_str, str)
    assert len(json_str) > 0
