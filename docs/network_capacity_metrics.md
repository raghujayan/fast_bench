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

### 4. **iperf3 Bandwidth** (NEW - Path Capacity)
- **What it is**: Standard network bandwidth testing using iperf3 protocol
- **How we measure**: iperf3 client to Azure-region server (10 seconds)
- **What it tells you**: Raw TCP throughput capacity without HTTP overhead
- **Why it matters**: Pure bandwidth measurement, independent of Azure Blob API
- **Note**: Requires iperf3 server running in Azure region

## Comparison Table

| Metric | What | Bottleneck | Link Util | Use Case |
|--------|------|------------|-----------|----------|
| **NIC Speed** | 4294 Mbps | Hardware | 100% (theoretical) | Local link capacity |
| **Single Azure** | 45 MB/s (383 Mbps) | Latency | 9% | Baseline comparison |
| **Multi Azure** | ~250-400 MB/s | Bandwidth | 60-90% | FAST SDK ceiling |
| **iperf3** | ~300-500 MB/s | Bandwidth | 70-95% | Pure bandwidth |
| **FAST (actual)** | 428 MB/s (2981 Mbps) | Bandwidth | 69% | Production perf |

## Example Output

```
============================================================
Path Capacity Tests (VM ↔ Azure)
============================================================
These tests measure maximum achievable bandwidth on the VM-to-Azure path.

  Testing Azure Blob throughput - multi-threaded (8 parallel connections)
    ✓ Throughput: 312.5 MB/s (2500 Mbps, 58% link utilization)
    ✓ Chunk times: p95=245.3ms p99=312.1ms

  Testing iperf3 bandwidth to blob.core.windows.net
    Running: iperf3 -c blob.core.windows.net -t 10
    ✓ Bandwidth: 387.5 MB/s (3100 Mbps, 72% link utilization)
```

## Interpreting Results

### Scenario 1: High Link Utilization (>60%)
```
Multi Azure: 350 MB/s (2800 Mbps, 65% link utilization)
iperf3: 400 MB/s (3200 Mbps, 75% link utilization)
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
4. **Use iperf3** to diagnose network issues (requires server setup)

## Setup Notes

### Multi-threaded Azure Test
- **No setup required** - uses your existing SAS URLs
- **Automatic** - runs after single-threaded test
- **Time**: ~10 seconds

### iperf3 Test
- **Requires**: `iperf3` installed on VM (`choco install iperf3` on Windows)
- **Requires**: iperf3 server in Azure region (or skips gracefully)
- **Setup**: Deploy Azure VM in same region, run `iperf3 -s`
- **Optional**: Will show "iperf3 not found, skipping" if unavailable
- **Time**: ~10 seconds

## Technical Details

### Multi-threaded Implementation
```python
# 8 workers, each downloading 8MB chunks in parallel
ThreadPoolExecutor(max_workers=8)
# Measures actual network I/O via psutil.net_io_counters()
# Calculates throughput and link utilization
```

### iperf3 Implementation
```bash
# JSON output for parsing
iperf3 -c <azure_host> -t 10 -J
# Extracts bits_per_second, retransmits, bytes sent
```

## FAQ

**Q: Why is multi-threaded faster than single-threaded?**
A: Single connection is limited by latency (RTT). Multiple connections overlap requests, hiding latency.

**Q: Should iperf3 match multi-threaded Azure?**
A: Close, but iperf3 may be slightly higher (no HTTP overhead, pure TCP).

**Q: What if FAST is slower than multi-threaded Azure test?**
A: Check FAST SDK configuration - may need more parallel connections or tuning.

**Q: Do I need iperf3?**
A: No, it's optional. Multi-threaded Azure test is sufficient for FAST ceiling prediction.
