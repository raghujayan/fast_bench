"""File operations and utilities."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict
from datetime import datetime


def safe_write(path: Path | str, content: str, encoding: str = 'utf-8') -> None:
    """
    Safely write content to a file using atomic write pattern.

    Writes to a temporary file first, then renames to target path.

    Args:
        path: Target file path
        content: Content to write
        encoding: File encoding (default: utf-8)
    """
    path = Path(path)
    temp_path = path.with_suffix(path.suffix + '.tmp')

    try:
        with open(temp_path, 'w', encoding=encoding) as f:
            f.write(content)
        temp_path.replace(path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def safe_write_json(path: Path | str, data: Dict[str, Any], indent: int = 2) -> None:
    """
    Safely write JSON data to a file.

    Args:
        path: Target file path
        data: Dictionary to serialize
        indent: JSON indentation level
    """
    content = json.dumps(data, indent=indent, ensure_ascii=False)
    safe_write(path, content)


def ensure_dir(path: Path | str) -> Path:
    """
    Ensure directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_unique_path(base_path: Path | str, suffix: str = '') -> Path:
    """
    Get a unique file path by appending numbers if necessary.

    Args:
        base_path: Base file path
        suffix: Optional suffix before extension

    Returns:
        Unique path that doesn't exist yet
    """
    path = Path(base_path)
    if suffix:
        path = path.with_stem(f"{path.stem}{suffix}")

    if not path.exists():
        return path

    counter = 1
    while True:
        new_path = path.with_stem(f"{path.stem}_{counter}")
        if not new_path.exists():
            return new_path
        counter += 1


def rotate_old_files(directory: Path | str, pattern: str, keep_count: int = 10) -> None:
    """
    Rotate old files in a directory, keeping only the most recent N files.

    Args:
        directory: Directory to clean
        pattern: Glob pattern for files to rotate (e.g., "metrics_*.csv")
        keep_count: Number of most recent files to keep
    """
    directory = Path(directory)
    if not directory.exists():
        return

    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

    # Delete files beyond keep_count
    for old_file in files[keep_count:]:
        try:
            old_file.unlink()
        except OSError:
            pass


def copy_file_progress(src: Path | str, dst: Path | str, chunk_size: int = 1024 * 1024) -> float:
    """
    Copy a file and return the time taken.

    Args:
        src: Source file path
        dst: Destination file path
        chunk_size: Chunk size for copying (default: 1 MB)

    Returns:
        Time taken in seconds
    """
    src = Path(src)
    dst = Path(dst)

    start = datetime.now()
    shutil.copy2(src, dst)
    end = datetime.now()

    return (end - start).total_seconds()


def get_file_size_mb(path: Path | str) -> float:
    """
    Get file size in megabytes.

    Args:
        path: File path

    Returns:
        File size in MB
    """
    return Path(path).stat().st_size / (1024 * 1024)


def clear_directory(path: Path | str, pattern: str = '*') -> int:
    """
    Clear all files matching pattern in directory.

    Args:
        path: Directory path
        pattern: Glob pattern (default: all files)

    Returns:
        Number of files deleted
    """
    path = Path(path)
    if not path.exists() or not path.is_dir():
        return 0

    count = 0
    for item in path.glob(pattern):
        try:
            if item.is_file():
                item.unlink()
                count += 1
            elif item.is_dir():
                shutil.rmtree(item)
                count += 1
        except OSError:
            pass

    return count