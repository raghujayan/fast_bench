"""Configuration schema and validation using Pydantic."""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import yaml


class PetrelConfig(BaseModel):
    """Petrel executable configuration."""
    exe_path: Path = Field(..., description="Path to Petrel.exe")
    project_arg_supported: bool = Field(True, description="Whether Petrel supports --project argument")

    @field_validator('exe_path')
    @classmethod
    def validate_exe_path(cls, v: Path) -> Path:
        """Validate that Petrel executable exists."""
        if not v.exists():
            raise ValueError(f"Petrel executable not found: {v}")
        if not v.is_file():
            raise ValueError(f"Petrel path is not a file: {v}")
        return v


class PathsConfig(BaseModel):
    """Project paths configuration."""
    project_shared_zgy_local: Path = Field(..., description="Local Petrel project using NAS ZGY")
    project_fast_vzgy_local: Path = Field(..., description="Local Petrel project using FAST virtual ZGY")

    @field_validator('project_shared_zgy_local', 'project_fast_vzgy_local')
    @classmethod
    def validate_project_path(cls, v: Path) -> Path:
        """Validate that project path exists."""
        if not v.exists():
            raise ValueError(f"Petrel project not found: {v}")
        if not v.is_file():
            raise ValueError(f"Project path is not a file: {v}")
        return v


class AzureBlobConfig(BaseModel):
    """Azure Blob Storage configuration for baseline probes."""
    account: str = Field(..., description="Azure storage account name")
    container: str = Field(..., description="Azure Blob container name")
    example_vds_prefix: Optional[str] = Field(None, description="Example VDS prefix URL")
    sas_download_urls: List[str] = Field(default_factory=list, description="SAS URLs for download probes")
    sas_upload_urls: List[str] = Field(default_factory=list, description="SAS URLs for upload probes")

    @field_validator('sas_download_urls', 'sas_upload_urls')
    @classmethod
    def validate_urls(cls, v: List[str]) -> List[str]:
        """Validate that URLs are well-formed."""
        for url in v:
            if not url.startswith('https://'):
                raise ValueError(f"SAS URL must start with https://: {url}")
            if 'blob.core.windows.net' not in url:
                raise ValueError(f"Invalid Azure Blob URL: {url}")
        return v


class DataSourcesConfig(BaseModel):
    """Data sources configuration."""
    shared_zgy_hint: str = Field(..., description="Hint path for NAS ZGY location")
    fast_vzgy_hint: str = Field(..., description="Hint path for FAST virtual ZGY location")
    azure_blob: AzureBlobConfig = Field(..., description="Azure Blob configuration")


class HotkeysConfig(BaseModel):
    """Petrel hotkey configuration."""
    scrub_next_inline: str = Field("PGDN", description="Key for inline scrubbing")
    attribute_compute: str = Field("%1", description="Hotkey for attribute compute (Alt+1)")
    horizon_autotrack: str = Field("%2", description="Hotkey for horizon autotrack (Alt+2)")
    export_slice: str = Field("%3", description="Hotkey for slice export (Alt+3)")


class FastLogsConfig(BaseModel):
    """FAST logs configuration."""
    logs: List[Path] = Field(default_factory=list, description="Paths to FAST log files")
    cache_dir: Path = Field(..., description="FAST cache directory")

    @field_validator('cache_dir')
    @classmethod
    def validate_cache_dir(cls, v: Path) -> Path:
        """Validate that cache directory exists or can be created."""
        # Cache dir may not exist yet, but parent should
        if not v.parent.exists():
            raise ValueError(f"Parent directory for cache does not exist: {v.parent}")
        return v


class DefaultsConfig(BaseModel):
    """Default values for workflows."""
    scrub_count: int = Field(100, ge=1, description="Number of scrub iterations")
    scrub_delay_sec: float = Field(0.04, ge=0.0, description="Delay between scrub iterations (seconds)")
    horizon_run_seconds: int = Field(45, ge=1, description="Duration for horizon autotrack (seconds)")


class BenchmarkConfig(BaseModel):
    """Benchmark probe configuration."""
    nas_test_dir: str = Field(..., description="NAS directory for throughput tests")
    nas_ping_host: str = Field(..., description="NAS hostname for ping tests")
    azure_ping_hosts: List[str] = Field(default_factory=list, description="Azure hostnames for ping tests")
    parallel_streams: int = Field(4, ge=1, le=16, description="Number of parallel streams for throughput tests")
    http_chunk_bytes: int = Field(8388608, ge=1024, description="HTTP chunk size for ranged GETs (bytes)")


class Config(BaseModel):
    """Main configuration model."""
    petrel: PetrelConfig
    paths: PathsConfig
    data_sources: DataSourcesConfig
    hotkeys: HotkeysConfig = Field(default_factory=HotkeysConfig)
    fast: FastLogsConfig
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    out_dir: Path = Field(..., description="Output directory for benchmark runs")
    benchmark: BenchmarkConfig

    @field_validator('out_dir')
    @classmethod
    def validate_out_dir(cls, v: Path) -> Path:
        """Validate that output directory exists or can be created."""
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
        if not v.is_dir():
            raise ValueError(f"Output path is not a directory: {v}")
        return v


def load_config(config_path: str | Path) -> Config:
    """
    Load and validate configuration from YAML file.

    Args:
        config_path: Path to config YAML file

    Returns:
        Validated Config object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config validation fails
        yaml.YAMLError: If YAML parsing fails
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = yaml.safe_load(f)

    if config_dict is None:
        raise ValueError(f"Configuration file is empty: {config_path}")

    return Config(**config_dict)