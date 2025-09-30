"""Chart generation utilities for baseline probe and analysis."""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def create_throughput_chart(
    nas_throughput: float,
    azure_throughput: float,
    output_path: Path
) -> bool:
    """
    Create bar chart comparing NAS vs Azure throughput.

    Args:
        nas_throughput: NAS throughput in MB/s
        azure_throughput: Azure throughput in MB/s
        output_path: Path to save PNG

    Returns:
        True if chart created successfully
    """
    if not MATPLOTLIB_AVAILABLE:
        print("  ⚠️  matplotlib not available, skipping chart generation")
        return False

    try:
        fig, ax = plt.subplots(figsize=(10, 6))

        sources = ['NAS', 'Azure Blob']
        throughputs = [nas_throughput, azure_throughput]
        colors = ['#3498db', '#e74c3c']

        bars = ax.bar(sources, throughputs, color=colors, alpha=0.8)

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f} MB/s',
                   ha='center', va='bottom', fontsize=12, fontweight='bold')

        ax.set_ylabel('Throughput (MB/s)', fontsize=12)
        ax.set_title('Storage Throughput Comparison', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

        return True

    except Exception as e:
        print(f"  ⚠️  Chart generation failed: {e}")
        return False


def create_latency_chart(
    nas_rtt: Dict[str, float],
    azure_rtt: Dict[str, float],
    output_path: Path
) -> bool:
    """
    Create bar chart comparing NAS vs Azure network latency.

    Args:
        nas_rtt: Dictionary with min/avg/p95 RTT in ms
        azure_rtt: Dictionary with min/avg/p95 RTT in ms
        output_path: Path to save PNG

    Returns:
        True if chart created successfully
    """
    if not MATPLOTLIB_AVAILABLE:
        return False

    try:
        fig, ax = plt.subplots(figsize=(10, 6))

        metrics = ['Min', 'Avg', 'P95']
        nas_values = [nas_rtt.get('min_ms', 0), nas_rtt.get('avg_ms', 0), nas_rtt.get('p95_ms', 0)]
        azure_values = [azure_rtt.get('min_ms', 0), azure_rtt.get('avg_ms', 0), azure_rtt.get('p95_ms', 0)]

        x = range(len(metrics))
        width = 0.35

        bars1 = ax.bar([i - width/2 for i in x], nas_values, width, label='NAS', color='#3498db', alpha=0.8)
        bars2 = ax.bar([i + width/2 for i in x], azure_values, width, label='Azure', color='#e74c3c', alpha=0.8)

        # Add value labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}ms',
                       ha='center', va='bottom', fontsize=10)

        ax.set_ylabel('Round-Trip Time (ms)', fontsize=12)
        ax.set_title('Network Latency Comparison', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(metrics)
        ax.legend()
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

        return True

    except Exception as e:
        print(f"  ⚠️  Latency chart generation failed: {e}")
        return False


def create_comparison_chart(
    data: Dict[str, List[float]],
    title: str,
    ylabel: str,
    output_path: Path
) -> bool:
    """
    Create generic bar chart for metric comparisons.

    Args:
        data: Dictionary mapping labels to values
        title: Chart title
        ylabel: Y-axis label
        output_path: Path to save PNG

    Returns:
        True if chart created successfully
    """
    if not MATPLOTLIB_AVAILABLE:
        return False

    try:
        fig, ax = plt.subplots(figsize=(12, 6))

        labels = list(data.keys())
        values = list(data.values())

        colors = plt.cm.Set3(range(len(labels)))
        bars = ax.bar(labels, values, color=colors, alpha=0.8)

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}',
                   ha='center', va='bottom', fontsize=10)

        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        plt.xticks(rotation=45, ha='right')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

        return True

    except Exception as e:
        print(f"  ⚠️  Chart generation failed: {e}")
        return False
