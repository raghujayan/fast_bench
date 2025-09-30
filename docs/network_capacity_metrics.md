# Network Capacity Metrics

## Overview

The baseline probe now includes **Path Capacity Tests** to measure the maximum achievable bandwidth between the VM and Azure Blob Storage. These tests help distinguish between **latency-limited** and **bandwidth-limited** performance.

## Metrics Explained

### 1. **NIC Link Speed** (Primary link speed: 4294 Mbps)
- **What it is**: The physical/configured capacity of your network interface card
- **How we get it**: Read from OS via `psutil.net_if_stats().speed`
- **What it means**: Maximum theoretical throughput on the local link (VM ↔ switch)
- **Example**: 4294 Mbps ≈ 4 Gbps Ethernet adapter

### 2. **Single-threaded Azure Throughput** (45.5 MB/s, 383 Mbps, 9% link utilization)
- **What it is**: Sequential HTTP downloads using single connection
- **How we measure**: Ranged GET requests with 8MB chunks for 10 seconds
- **What it tells you**: Baseline latency-limited performance
- **Interpretation**: Low link utilization (9%) indicates latency bottleneck, not bandwidth

### 3. **Multi-threaded Azure Throughput** (NEW - Path Capacity)
- **What it is**: Parallel HTTP downloads using 8 simultaneous connections
- **How we measure**: ThreadPoolExecutor with 8 workers downloading chunks in parallel
- **What it tells you**: Maximum achievable Azure Blob throughput (simulates FAST SDK)
- **Why it matters**: Shows realistic upper bound for FAST performance
- **Expected result**: Should saturate available bandwidth (60-90% link utilization)

### 4. **azcopy Benchmark** (NEW - Path Capacity)
- **What it is**: Azure's official copy tool in benchmark mode
- **How we measure**: azcopy bench downloads test data with optimized parallelism (15 seconds)
- **What it tells you**: Maximum Azure Blob throughput using Microsoft's optimized client
- **Why it matters**: Shows best-case Azure performance with official tooling
- **Note**: Requires azcopy installed (likely already available in Azure environments)

## Comparison Table

| Metric | What | Bottleneck | Link Util | Use Case |
|--------|------|------------|-----------|----------|
| **NIC Speed** | 4294 Mbps | Hardware | 100% (theoretical) | Local link capacity |
| **Single Azure** | 45 MB/s (383 Mbps) | Latency | 9% | Baseline comparison |
| **Multi Azure** | ~250-400 MB/s | Bandwidth | 60-90% | FAST SDK ceiling |
| **azcopy bench** | ~300-500 MB/s | Bandwidth | 70-95% | Microsoft optimized |
| **FAST (actual)** | 428 MB/s (2981 Mbps) | Bandwidth | 69% | Production perf |

## Example Output

```
============================================================
Path Capacity Tests (VM ↔ Azure)
============================================================
These tests measure maximum achievable bandwidth on the VM-to-Azure path.

  Testing Azure Blob throughput - multi-threaded (8 parallel connections)
    ... 3s: 280.5 MB/s (112 chunks)
    ... 6s: 295.3 MB/s (224 chunks)
    ✓ Throughput: 312.5 MB/s (2500 Mbps, 58% link utilization)
    ✓ Chunk times: p95=245.3ms p99=312.1ms

  Note: azcopy benchmark uploads/downloads test data to measure max throughput
    Testing azcopy benchmark to Azure Blob
    Running: azcopy bench (download 30 x 64MB files)
    ✓ Throughput: 387.5 MB/s (3100 Mbps, 72% link utilization)
    ✓ Transferred: 28/30 files (1792.0 MB)
```

## Interpreting Results

### Scenario 1: High Link Utilization (>60%)
```
Multi Azure: 350 MB/s (2800 Mbps, 65% link utilization)
azcopy bench: 400 MB/s (3200 Mbps, 75% link utilization)
```
**Interpretation**: Path is **bandwidth-limited**. You're approaching the ceiling of VM↔Azure bandwidth.
**FAST Expectation**: 300-400 MB/s is realistic maximum

### Scenario 2: Low Link Utilization (<30%)
```
Multi Azure: 120 MB/s (960 Mbps, 22% link utilization)
iperf3: 150 MB/s (1200 Mbps, 28% link utilization)
```
**Interpretation**: Path is **latency-limited** or has network issues (packet loss, routing problems).
**FAST Expectation**: 100-150 MB/s ceiling due to path quality issues

### Scenario 3: Multi-threaded vs Single-threaded Gap
```
Single Azure: 45 MB/s (9% util)
Multi Azure: 320 MB/s (62% util)
```
**Interpretation**: Parallelization provides **7x improvement**. This is why FAST SDK uses multiple connections.

## When to Use Each Metric

1. **Use NIC Speed** to understand local hardware limits
2. **Use Single-threaded Azure** to establish baseline and measure latency impact
3. **Use Multi-threaded Azure** to predict FAST SDK ceiling (most relevant for A/B testing)
4. **Use azcopy benchmark** to verify maximum Azure performance with official tooling

## Setup Notes

### Multi-threaded Azure Test
- **No setup required** - uses your existing SAS URLs
- **Automatic** - runs after single-threaded test
- **Time**: ~15 seconds

### azcopy Benchmark Test
- **Requires**: `azcopy` installed on VM (often pre-installed in Azure environments)
- **Windows**: Download from https://aka.ms/downloadazcopy or use `winget install azcopy`
- **SAS URL**: Uses your configured SAS URL (needs container-level permissions)
- **Optional**: Will show "azcopy not found, skipping" if unavailable
- **Time**: ~15-30 seconds (downloads 30 x 64MB test files)

## Technical Details

### Multi-threaded Implementation
```python
# 8 workers, each downloading 8MB chunks in parallel
ThreadPoolExecutor(max_workers=8)
# Measures actual network I/O via psutil.net_io_counters()
# Calculates throughput and link utilization
# Shows progress updates every 3 seconds
```

### azcopy Benchmark Implementation
```bash
# Benchmark mode with optimized parallelism
azcopy bench <container_sas_url> \
  --mode download \
  --size-per-file 64M \
  --num-of-files 30 \
  --delete-test-data
# Parses throughput from azcopy output
# Measures network I/O via psutil for link utilization
```

## FAQ

**Q: Why is multi-threaded faster than single-threaded?**
A: Single connection is limited by latency (RTT). Multiple connections overlap requests, hiding latency.

**Q: Should azcopy benchmark match multi-threaded Azure?**
A: azcopy may be 10-20% higher due to optimizations in Microsoft's tool. Both are good upper bounds.

**Q: What if FAST is slower than multi-threaded Azure test?**
A: Check FAST SDK configuration - may need more parallel connections or tuning.

**Q: Do I need azcopy?**
A: No, it's optional. Multi-threaded Azure test is sufficient for FAST ceiling prediction. azcopy provides validation.
