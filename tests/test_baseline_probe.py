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
            'throughput': {
                'success': True,
                'throughput_mbs': 100.0,
                'network_bandwidth_mbps': 800.0,
                'link_utilization_pct': 80.0
            }
        },
        'azure': {
            'throughput_single': {
                'success': True,
                'throughput_mbs': 200.0,
                'network_bandwidth_mbps': 1600.0,
                'link_utilization_pct': 40.0
            }
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


def test_azure_throughput_parallel_no_urls(mock_config):
    """Test parallel Azure throughput when no URLs configured."""
    probe = BaselineProbe(mock_config)
    probe.link_speed_mbps = 1000

    result = probe.test_azure_throughput_parallel([])

    assert result['success'] is False
    assert 'error' in result


@pytest.mark.mock
def test_azure_throughput_parallel_success(mock_config, mocker):
    """Test parallel Azure throughput with mocked requests."""
    probe = BaselineProbe(mock_config)
    probe.link_speed_mbps = 1000

    # Mock successful HTTP responses
    mock_response = mocker.Mock()
    mock_response.status_code = 206
    mock_response.content = b'x' * (8 * 1024 * 1024)  # 8MB
    mocker.patch('requests.get', return_value=mock_response)

    # Mock network counters
    mock_net_start = mocker.Mock(bytes_recv=0)
    mock_net_end = mocker.Mock(bytes_recv=80 * 1024 * 1024)  # 80MB received
    mocker.patch('psutil.net_io_counters', side_effect=[mock_net_start, mock_net_end])

    sas_urls = ['https://example.blob.core.windows.net/test.vds?sas=token']
    result = probe.test_azure_throughput_parallel(sas_urls, duration_sec=1, workers=4)

    assert result['success'] is True
    assert result['throughput_mbs'] > 0
    assert result['network_bandwidth_mbps'] > 0
    assert result['link_utilization_pct'] >= 0
    assert result['workers'] == 4
    assert result['chunk_count'] > 0


def test_azcopy_not_installed(mock_config, mocker):
    """Test azcopy benchmark when azcopy is not installed."""
    probe = BaselineProbe(mock_config)
    probe.link_speed_mbps = 1000

    # Mock azcopy not found
    mocker.patch('subprocess.run', side_effect=FileNotFoundError())

    result = probe.test_azcopy_benchmark('https://example.blob.core.windows.net/container?sas=token')

    assert result['success'] is False
    assert 'not installed' in result['error']


@pytest.mark.mock
def test_azcopy_success(mock_config, mocker):
    """Test azcopy benchmark with mocked subprocess."""
    probe = BaselineProbe(mock_config)
    probe.link_speed_mbps = 1000

    # Mock _find_azcopy to return a path
    mocker.patch.object(probe, '_find_azcopy', return_value='/usr/local/bin/azcopy')

    # Mock azcopy bench output
    azcopy_output = """
Job ... Started
Throughput (MB/s): 450.25
Total bytes transferred: 524288000
Files Completed: 8 of 10
Job ... completed
"""
    mock_bench = mocker.Mock(returncode=0, stdout=azcopy_output, stderr='')

    # Mock network counters
    mock_net_start = mocker.Mock(bytes_recv=0)
    mock_net_end = mocker.Mock(bytes_recv=500 * 1024 * 1024)  # 500 MB
    mocker.patch('psutil.net_io_counters', side_effect=[mock_net_start, mock_net_end])

    mocker.patch('subprocess.run', return_value=mock_bench)

    result = probe.test_azcopy_benchmark('https://example.blob.core.windows.net/container?sas=token', duration_sec=10)

    assert result['success'] is True
    assert result['throughput_mbs'] > 0
    assert result['network_bandwidth_mbps'] > 0
    assert result['link_utilization_pct'] >= 0
    assert result['files_transferred'] == 8
