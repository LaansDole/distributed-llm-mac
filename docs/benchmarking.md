# Benchmarking Guide

This guide explains how to benchmark your distributed LLM system and compare performance between single and multiple Mac Studios.

## What the Benchmark Script Does

The `benchmark.py` script measures your system's performance with two test modes:

### 1. Concurrency Scaling Test
Tests how performance changes with different concurrency levels (1, 5, 10, 20, 50, 100).

**Purpose:** Find the optimal concurrency level for your worker configuration.

**Metrics:**
- Requests per second (throughput)
- Success rate
- Average/P50/P95/P99 response times
- Per-worker utilization

### 2. Worker Scaling Test
Tests how performance scales with different numbers of workers (1, 2, 3, 5, 10).

**Purpose:** Verify linear scaling and identify bottlenecks.

**Metrics:**
- Throughput with N workers
- Throughput per worker
- Scaling efficiency

## Quick Start

### Basic Benchmark
```bash
# Test your current setup
uv run python scripts/benchmark.py --config config/my_workers.json
```

### Concurrency Test Only
```bash
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --mode concurrency \
  --requests 100
```

### Worker Scaling Test Only
```bash
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --mode scaling \
  --requests 50 \
  --worker-counts 1 2 3
```

## Comparing Single vs Multiple Mac Studios

### Step 1: Create Config Files

**Single Mac Studio** (`config/single_studio.json`):
```json
{
  "workers": [
    {
      "id": "mac-studio-1",
      "host": "192.168.1.107",
      "port": 1234,
      "type": "lm_studio",
      "model": "mistral-7b-instruct-v0.2",
      "max_concurrent_requests": 5
    }
  ]
}
```

**Multiple Mac Studios** (`config/my_workers.json`):
```json
{
  "workers": [
    {
      "id": "mac-studio-1",
      "host": "192.168.1.105",
      "port": 1234,
      "type": "lm_studio",
      "model": "mistral-7b-instruct-v0.2",
      "max_concurrent_requests": 5
    },
    {
      "id": "mac-studio-2",
      "host": "192.168.1.106",
      "port": 1234,
      "type": "lm_studio",
      "model": "mistral-7b-instruct-v0.2",
      "max_concurrent_requests": 5
    },
    {
      "id": "mac-studio-3",
      "host": "192.168.1.107",
      "port": 1234,
      "type": "lm_studio",
      "model": "mistral-7b-instruct-v0.2",
      "max_concurrent_requests": 5
    }
  ]
}
```

### Step 2: Run Benchmarks

```bash
# Benchmark single Mac Studio
uv run python scripts/benchmark.py \
  --config config/single_studio.json \
  --requests 100 \
  --mode concurrency \
  --output results_single.json

# Benchmark multiple Mac Studios
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --requests 100 \
  --mode concurrency \
  --output results_multiple.json
```

### Step 3: Compare Results

**Manual Comparison:**
```bash
# View single studio results
cat results_single.json | jq '.concurrency_benchmark[] | {concurrency, rps: .requests_per_second, success: .success_rate}'

# View multiple studio results
cat results_multiple.json | jq '.concurrency_benchmark[] | {concurrency, rps: .requests_per_second, success: .success_rate}'
```

**Automated Comparison Script:**
```python
import json

# Load results
single = json.load(open('results_single.json'))
multiple = json.load(open('results_multiple.json'))

print("PERFORMANCE COMPARISON")
print("=" * 70)
print(f"{'Concurrency':<12} {'Single (req/s)':<15} {'Multiple (req/s)':<17} {'Speedup':<10}")
print("-" * 70)

for s, m in zip(single['concurrency_benchmark'], multiple['concurrency_benchmark']):
    conc = s['concurrency']
    single_rps = s['requests_per_second']
    multi_rps = m['requests_per_second']
    speedup = multi_rps / single_rps if single_rps > 0 else 0
    
    print(f"{conc:<12} {single_rps:<15.2f} {multi_rps:<17.2f} {speedup:<10.2f}x")
```

## Example Output Interpretation

### Single Mac Studio Results
```
BENCHMARKING WITH CONCURRENCY: 5
Results:
  Requests/sec: 10.2
  Success rate: 100.0%
  Avg response time: 0.49s
  P95 response time: 0.65s

Worker utilization:
  mac-studio-1: 100 requests, 100.0% success rate
```

**Interpretation:** 
- One worker handles all 100 requests
- Throughput plateaus at ~10 req/s due to `max_concurrent_requests: 5`
- Increasing concurrency beyond 10 won't help (worker is saturated)

### Multiple Mac Studios Results
```
BENCHMARKING WITH CONCURRENCY: 20
Results:
  Requests/sec: 30.4
  Success rate: 100.0%
  Avg response time: 0.66s
  P95 response time: 0.85s

Worker utilization:
  mac-studio-1: 33 requests, 100.0% success rate
  mac-studio-2: 34 requests, 100.0% success rate
  mac-studio-3: 33 requests, 100.0% success rate
```

**Interpretation:**
- Load is evenly distributed across 3 workers
- Throughput is ~3x higher (30.4 vs 10.2 req/s)
- Each worker handles ~33 requests (balanced distribution)
- Response time only slightly higher despite 3x throughput

## Performance Expectations

### Theoretical vs Actual Scaling

**Theoretical:** 3 workers = 3x performance  
**Actual:** Usually 2.5-2.8x due to:
- Network latency
- Load balancer overhead
- Uneven request completion times

### Expected Results by Worker Count

| Workers | Concurrency | Expected Throughput | Notes |
|---------|-------------|---------------------|-------|
| 1       | 5           | ~10 req/s          | Baseline |
| 1       | 10          | ~11 req/s          | Worker saturated |
| 3       | 15          | ~28 req/s          | 2.8x speedup |
| 3       | 30          | ~30 req/s          | Optimal |
| 5       | 25          | ~45 req/s          | 4.5x speedup |

## Advanced Benchmarking

### Custom Concurrency Levels
```bash
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --concurrency-levels 10 20 30 40 50 \
  --requests 200
```

### Testing Specific Worker Counts
```bash
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --mode scaling \
  --worker-counts 1 3 5 \
  --requests 100
```

### Full Benchmark Suite
```bash
# Run all tests
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --mode both \
  --requests 100 \
  --output full_benchmark.json
```

## Real-World Example

### Scenario: Processing 100 Research Papers

Each paper gets 5 prompts = 500 total tasks

**Single Mac Studio (M2 Ultra):**
```bash
uv run python scripts/process_directory.py \
  --config config/single_studio.json \
  --input papers/ \
  --preset research
```
- Time: ~20 minutes
- Throughput: ~25 tasks/min
- Worker utilization: 100%

**3 Mac Studios (distributed):**
```bash
uv run python scripts/process_directory.py \
  --config config/my_workers.json \
  --input papers/ \
  --preset research
```
- Time: ~7 minutes
- Throughput: ~71 tasks/min
- Speedup: **2.8x faster**
- Worker utilization: ~33% each (balanced)

## Troubleshooting

### Poor Scaling (< 2x with 3 workers)

**Check:**
1. Network bottleneck - Use `ping` to check latency between workers
2. Uneven worker specs - Ensure all Mac Studios have similar hardware
3. Model loading time - First requests are slower, benchmark warms up workers
4. `max_concurrent_requests` too low - Increase from 5 to 8-10 for Mac Studios

### High Response Times

**Solutions:**
1. Reduce `max_concurrent_requests` per worker
2. Use smaller models (Mistral 7B instead of 13B)
3. Ensure workers aren't running other intensive apps
4. Check network speed (use Ethernet instead of WiFi)

### Uneven Worker Utilization

**Causes:**
- One worker is slower (older Mac, thermal throttling)
- Network issues to specific worker
- Worker running background tasks

**Fix:** The load balancer automatically reduces load to slower workers based on response times

## Quick Comparison Commands

```bash
# Test both configs quickly
for config in single_studio my_workers; do
  echo "Testing $config"
  uv run python scripts/benchmark.py \
    -c config/${config}.json \
    --requests 50 \
    --concurrency-levels 5 10 20 \
    -o results_${config}.json
done

# Compare with jq
echo "=== Single Studio ==="
jq '.concurrency_benchmark[] | "\(.concurrency): \(.requests_per_second) req/s"' results_single_studio.json

echo "=== Multiple Studios ==="
jq '.concurrency_benchmark[] | "\(.concurrency): \(.requests_per_second) req/s"' results_my_workers.json
```

## Benchmark Best Practices

1. **Warm up workers first** - Run small test before benchmark
2. **Use consistent workload** - Same number of requests for comparisons
3. **Test multiple times** - Average results from 3+ runs
4. **Close other apps** - Ensure workers aren't doing other work
5. **Use same model** - Don't compare different model sizes
6. **Monitor temperature** - Mac Studios may throttle if hot

## Understanding Metrics

### Requests Per Second (RPS)
Higher is better. Shows system throughput.

### Success Rate
Should be 100%. Lower means worker failures or timeouts.

### P95/P99 Response Time
95th/99th percentile response times. Shows worst-case performance.

### Load Percentage
Per-worker metric. Should be balanced across workers (~33% each with 3 workers).

## Next Steps

After benchmarking:
1. Use optimal concurrency level from results
2. Adjust `max_concurrent_requests` based on findings
3. Add more workers if scaling is linear
4. Process real workloads with optimized settings
