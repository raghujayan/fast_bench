"""Tests for configuration schema and validation."""

import pytest
import tempfile
from pathlib import Path
from pydantic import ValidationError
import yaml

from fast_bench.config_schema import (
    Config,
    load_config,
    PetrelConfig,
    PathsConfig,
    AzureBlobConfig,
    DataSourcesConfig,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_petrel_exe(temp_dir):
    """Create a mock Petrel executable."""
    exe_path = temp_dir / "Petrel.exe"
    exe_path.write_text("mock")
    return exe_path


@pytest.fixture
def mock_project_files(temp_dir):
    """Create mock Petrel project files."""
    project_a = temp_dir / "ProjectA.Petrel"
    project_b = temp_dir / "ProjectB.Petrel"
    project_a.write_text("mock project A")
    project_b.write_text("mock project B")
    return project_a, project_b


@pytest.fixture
def valid_config_dict(temp_dir, mock_petrel_exe, mock_project_files):
    """Create a valid configuration dictionary."""
    project_a, project_b = mock_project_files
    out_dir = temp_dir / "output"
    cache_dir = temp_dir / "cache"
    out_dir.mkdir()
    cache_dir.mkdir()

    return {
        "petrel": {
            "exe_path": str(mock_petrel_exe),
            "project_arg_supported": True,
        },
        "paths": {
            "project_shared_zgy_local": str(project_a),
            "project_fast_vzgy_local": str(project_b),
        },
        "data_sources": {
            "shared_zgy_hint": "\\\\NAS01\\SEISMIC\\field.zgy",
            "fast_vzgy_hint": "\\\\FAST\\field.zgy",
            "azure_blob": {
                "account": "testaccount",
                "container": "testcontainer",
                "sas_download_urls": [
                    "https://testaccount.blob.core.windows.net/testcontainer/file1.bin?sv=2023&sig=abc"
                ],
            },
        },
        "hotkeys": {
            "scrub_next_inline": "PGDN",
            "attribute_compute": "%1",
            "horizon_autotrack": "%2",
            "export_slice": "%3",
        },
        "fast": {
            "logs": ["C:\\ProgramData\\Bluware\\FAST\\logs\\fast_trace.log"],
            "cache_dir": str(cache_dir),
        },
        "defaults": {
            "scrub_count": 100,
            "scrub_delay_sec": 0.04,
            "horizon_run_seconds": 45,
        },
        "out_dir": str(out_dir),
        "benchmark": {
            "nas_test_dir": "\\\\NAS01\\BENCH",
            "nas_ping_host": "nas01.example.com",
            "azure_ping_hosts": ["blob.core.windows.net"],
            "parallel_streams": 4,
            "http_chunk_bytes": 8388608,
        },
    }


def test_valid_config_loads(valid_config_dict):
    """Test that a valid configuration loads without errors."""
    config = Config(**valid_config_dict)
    assert config.petrel.exe_path.exists()
    assert config.paths.project_shared_zgy_local.exists()
    assert config.data_sources.azure_blob.account == "testaccount"


def test_valid_config_loads_from_yaml(temp_dir, valid_config_dict):
    """Test that a valid configuration loads from YAML file."""
    config_path = temp_dir / "config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(valid_config_dict, f)

    config = load_config(config_path)
    assert config.petrel.exe_path.exists()
    assert config.paths.project_shared_zgy_local.exists()


def test_missing_azure_fields_raises_error(valid_config_dict):
    """Test that missing Azure Blob fields raise ValidationError."""
    # Remove azure_blob section
    del valid_config_dict["data_sources"]["azure_blob"]

    with pytest.raises(ValidationError) as exc_info:
        Config(**valid_config_dict)

    assert "azure_blob" in str(exc_info.value)


def test_invalid_petrel_path_raises_error(valid_config_dict):
    """Test that non-existent Petrel path raises ValidationError."""
    valid_config_dict["petrel"]["exe_path"] = "C:\\NonExistent\\Petrel.exe"

    with pytest.raises(ValidationError) as exc_info:
        Config(**valid_config_dict)

    assert "not found" in str(exc_info.value).lower()


def test_invalid_project_path_raises_error(valid_config_dict):
    """Test that non-existent project path raises ValidationError."""
    valid_config_dict["paths"]["project_shared_zgy_local"] = "D:\\NonExistent\\Project.Petrel"

    with pytest.raises(ValidationError) as exc_info:
        Config(**valid_config_dict)

    assert "not found" in str(exc_info.value).lower()


def test_azure_sas_urls_validated():
    """Test that malformed Azure SAS URLs raise ValidationError."""
    # Invalid URL (not HTTPS)
    with pytest.raises(ValidationError) as exc_info:
        AzureBlobConfig(
            account="test",
            container="test",
            sas_download_urls=["http://example.com/file.bin"]
        )
    assert "https://" in str(exc_info.value).lower()

    # Invalid URL (not Azure Blob)
    with pytest.raises(ValidationError) as exc_info:
        AzureBlobConfig(
            account="test",
            container="test",
            sas_download_urls=["https://example.com/file.bin"]
        )
    assert "azure blob" in str(exc_info.value).lower()


def test_defaults_applied(temp_dir, mock_petrel_exe, mock_project_files):
    """Test that default values are applied when optional fields are omitted."""
    project_a, project_b = mock_project_files
    out_dir = temp_dir / "output"
    cache_dir = temp_dir / "cache"
    out_dir.mkdir()
    cache_dir.mkdir()

    # Minimal config without hotkeys and defaults
    config_dict = {
        "petrel": {
            "exe_path": str(mock_petrel_exe),
        },
        "paths": {
            "project_shared_zgy_local": str(project_a),
            "project_fast_vzgy_local": str(project_b),
        },
        "data_sources": {
            "shared_zgy_hint": "\\\\NAS\\field.zgy",
            "fast_vzgy_hint": "\\\\FAST\\field.zgy",
            "azure_blob": {
                "account": "test",
                "container": "test",
            },
        },
        "fast": {
            "cache_dir": str(cache_dir),
        },
        "out_dir": str(out_dir),
        "benchmark": {
            "nas_test_dir": "\\\\NAS\\BENCH",
            "nas_ping_host": "nas.example.com",
        },
    }

    config = Config(**config_dict)

    # Check defaults
    assert config.petrel.project_arg_supported is True
    assert config.hotkeys.scrub_next_inline == "PGDN"
    assert config.defaults.scrub_count == 100
    assert config.defaults.scrub_delay_sec == 0.04
    assert config.benchmark.parallel_streams == 4
    assert config.benchmark.http_chunk_bytes == 8388608


def test_config_file_not_found():
    """Test that loading non-existent config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent_config.yaml")


def test_empty_config_file_raises_error(temp_dir):
    """Test that empty config file raises ValueError."""
    config_path = temp_dir / "empty.yaml"
    config_path.write_text("")

    with pytest.raises(ValueError) as exc_info:
        load_config(config_path)

    assert "empty" in str(exc_info.value).lower()


def test_out_dir_created_if_not_exists(temp_dir, mock_petrel_exe, mock_project_files):
    """Test that output directory is created if it doesn't exist."""
    project_a, project_b = mock_project_files
    out_dir = temp_dir / "new_output_dir"
    cache_dir = temp_dir / "cache"
    cache_dir.mkdir()

    config_dict = {
        "petrel": {"exe_path": str(mock_petrel_exe)},
        "paths": {
            "project_shared_zgy_local": str(project_a),
            "project_fast_vzgy_local": str(project_b),
        },
        "data_sources": {
            "shared_zgy_hint": "\\\\NAS\\field.zgy",
            "fast_vzgy_hint": "\\\\FAST\\field.zgy",
            "azure_blob": {"account": "test", "container": "test"},
        },
        "fast": {"cache_dir": str(cache_dir)},
        "out_dir": str(out_dir),
        "benchmark": {
            "nas_test_dir": "\\\\NAS\\BENCH",
            "nas_ping_host": "nas.example.com",
        },
    }

    config = Config(**config_dict)

    # Verify directory was created
    assert out_dir.exists()
    assert out_dir.is_dir()


def test_invalid_parallel_streams_raises_error(valid_config_dict):
    """Test that invalid parallel_streams value raises ValidationError."""
    valid_config_dict["benchmark"]["parallel_streams"] = 0

    with pytest.raises(ValidationError):
        Config(**valid_config_dict)

    valid_config_dict["benchmark"]["parallel_streams"] = 100

    with pytest.raises(ValidationError):
        Config(**valid_config_dict)