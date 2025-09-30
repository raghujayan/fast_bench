"""
Integration test for baseline probe with real network/storage.

This test requires:
- Network connectivity
- Valid config.yaml with NAS and Azure settings

Usage:
    pytest tests/integration/test_baseline_real.py -v -s
"""

import sys
import pytest
from pathlib import Path

from fast_bench.config_schema import load_config
from fast_bench.baseline_probe import BaselineProbe


@pytest.mark.integration
@pytest.mark.skipif(not Path('config/config.yaml').exists(),
                   reason="config/config.yaml not found")
def test_baseline_probe_real_network():
    """
    Integration test: Run baseline probe with real network/storage.

    This test validates:
    - Configuration loading
    - Machine specs collection
    - Real network ping tests
    - Real storage throughput (if accessible)
    """
    print("\n" + "=" * 60)
    print("Integration Test: Baseline Probe with Real Network")
    print("=" * 60)

    # Load real configuration
    config = load_config('config/config.yaml')
    print(f"✓ Loaded configuration")

    # Create probe
    probe = BaselineProbe(config)
    print(f"✓ Created baseline probe")

    # Run full baseline probe
    results = probe.run()
    print(f"✓ Baseline probe completed")

    # Validate results structure
    assert 'timestamp' in results
    assert 'machine' in results
    assert 'nas' in results
    assert 'azure' in results

    # Validate machine specs
    machine = results['machine']
    assert machine['cpu_count_physical'] > 0
    assert machine['ram_total_gb'] > 0
    print(f"✓ Machine specs: {machine['cpu_count_physical']} CPU cores, {machine['ram_total_gb']:.1f} GB RAM")

    # Validate NAS results (ping should work even if throughput doesn't)
    nas = results['nas']
    if nas.get('ping', {}).get('success'):
        ping = nas['ping']
        assert ping['avg_ms'] > 0
        assert ping['min_ms'] <= ping['avg_ms'] <= ping['max_ms']
        print(f"✓ NAS ping: {ping['avg_ms']:.1f}ms avg")
    else:
        print(f"⚠️  NAS ping failed (expected if NAS not accessible)")

    # Validate Azure results
    azure = results['azure']
    azure_ping_success = False
    for key, value in azure.items():
        if key.startswith('ping_') and value.get('success'):
            assert value['avg_ms'] > 0
            print(f"✓ Azure ping ({value['host']}): {value['avg_ms']:.1f}ms avg")
            azure_ping_success = True

    # At least one Azure ping should work if we have internet
    if not azure_ping_success:
        pytest.skip("No Azure connectivity")

    # Save results
    output_dir = config.out_dir / 'baseline_integration_test'
    probe.save_results(output_dir)
    print(f"✓ Results saved to: {output_dir}")

    # Verify output files exist
    assert (output_dir / 'baseline.json').exists()
    assert (output_dir / 'baseline_summary.txt').exists()
    print(f"✓ Output files created")

    print("\n" + "=" * 60)
    print("Integration Test: PASSED")
    print("=" * 60)


@pytest.mark.integration
def test_baseline_machine_specs_only():
    """
    Integration test: Collect machine specs without network tests.

    This test should always pass as it doesn't require network.
    """
    from unittest.mock import Mock

    # Create minimal mock config
    config = Mock()
    config.benchmark = Mock()
    config.benchmark.nas_ping_host = "localhost"
    config.benchmark.nas_test_dir = "/tmp"
    config.benchmark.azure_ping_hosts = []
    config.data_sources = Mock()
    config.data_sources.azure_blob = Mock()
    config.data_sources.azure_blob.sas_download_urls = []

    probe = BaselineProbe(config)
    specs = probe.collect_machine_specs()

    # Validate all required fields
    required_fields = [
        'os', 'cpu_count_physical', 'cpu_count_logical',
        'ram_total_gb', 'gpu_count', 'nics'
    ]

    for field in required_fields:
        assert field in specs, f"Missing field: {field}"

    print(f"\n✓ Machine specs collected successfully:")
    print(f"  OS: {specs['os']}")
    print(f"  CPU: {specs['cpu_count_physical']} cores / {specs['cpu_count_logical']} threads")
    print(f"  RAM: {specs['ram_total_gb']:.1f} GB")
    print(f"  GPU: {specs['gpu_count']} device(s)")
    print(f"  NICs: {len(specs['nics'])} interface(s)")
