# Benchmarking Guide

Quick guide to benchmark your distributed LLM system and compare single vs multiple Mac Studios.

## Quick Start (5 Minutes)

**Easiest way - Use the automated script:**
```bash
./scripts/quick_benchmark.sh
```

This script:
- Compares single Mac Studio vs your distributed setup
- Runs 10 requests at concurrency 5 and 15
- Shows speedup calculation automatically
- Completes in ~5 minutes
- Auto-creates `config/single_studio.json` if missing

**Output:**
```
Single Mac Studio:
  Concurrency 5: 8.2 req/s
  Concurrency 15: 10.5 req/s

Multiple Mac Studios:
  Concurrency 5: 8.5 req/s
  Concurrency 15: 28.3 req/s

Speedup Calculation:
  Concurrency 5: 1.04x speedup
  Concurrency 15: 2.69x speedup
```

## Manual Benchmarking

### Basic Commands

```bash
# Test your current setup (quick)
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --requests 10 \
  --concurrency-levels 5 15

# Full benchmark (thorough)
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --requests 100 \
  --mode both
```

### Compare Single vs Multiple

**Step 1:** Create `config/single_studio.json` with 1 worker
**Step 2:** Run benchmarks on both configs
```bash
uv run python scripts/benchmark.py -c config/single_studio.json -o results_single.json
uv run python scripts/benchmark.py -c config/my_workers.json -o results_multiple.json
```

**Step 3:** Compare with:
```bash
jq '.concurrency_benchmark[] | {concurrency, rps: .requests_per_second}' results_*.json
```

## Understanding the Tests

### Concurrency Scaling Test
Tests performance at different concurrency levels (1, 5, 10, 20, 50, 100).

**Purpose:** Find optimal concurrency for your worker configuration.

**Metrics:** Throughput (req/s), success rate, response times (avg/P95/P99)

### Worker Scaling Test
Tests performance with different numbers of workers (1, 2, 3, 5, 10).

**Purpose:** Verify linear scaling and identify bottlenecks.

## Performance Expectations

| Workers | Optimal Concurrency | Expected Speedup |
|---------|-------------------|------------------|
| 1       | 5                 | 1.0x (baseline)  |
| 3       | 15 (3 × 5)        | 2.5-2.8x         |
| 5       | 25 (5 × 5)        | 4.0-4.5x         |

**Formula:** Optimal Concurrency ≈ Workers × max_concurrent_requests

**Why not 3.0x with 3 workers?**
- Network latency (~10% overhead)
- Load balancer overhead (~5% overhead)
- Uneven request completion

## Example Config Files

**Single Mac Studio** (`config/single_studio.json`):
```json
{
  "workers": [{
    "id": "mac-studio-1",
    "host": "192.168.1.107",
    "port": 1234,
    "type": "lm_studio",
    "model": "mistral-7b-instruct-v0.2",
    "max_concurrent_requests": 5
  }]
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

## Interpreting Results

### Good Performance Indicators
- Success rate: 100%
- Linear scaling (3 workers ≈ 2.8x speedup)
- Even worker utilization (~33% each with 3 workers)
- P95 response time < 1.0s

### Performance Issues

**Poor Scaling (< 2x with 3 workers)**
- Check network latency: `ping 192.168.1.105`
- Ensure similar hardware specs across all Mac Studios
- Increase `max_concurrent_requests` (try 8-10 for Mac Studios)

**High Response Times (> 1.5s avg)**
- Reduce `max_concurrent_requests` per worker
- Use smaller models (Mistral 7B vs 13B)
- Close intensive apps on workers
- Use Ethernet instead of WiFi

**Uneven Worker Utilization**
- One worker is slower (check CPU/thermal throttling)
- Network issues to specific worker
- Load balancer automatically reduces load to slower workers

## Advanced Usage

### Custom Concurrency Levels
```bash
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --concurrency-levels 10 20 30 40 50 \
  --requests 50
```

### Test Specific Worker Counts
```bash
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --mode scaling \
  --worker-counts 1 3 5 \
  --requests 50
```

### Full Benchmark Suite
```bash
uv run python scripts/benchmark.py \
  --config config/my_workers.json \
  --mode both \
  --requests 100 \
  --output full_benchmark.json
```

## Real-World Example

**Scenario:** 100 research papers × 5 prompts = 500 tasks

**Single Mac Studio (M2 Ultra):**
- Time: ~20 minutes
- Throughput: ~25 tasks/min

**3 Mac Studios (distributed):**
- Time: ~7 minutes  
- Throughput: ~71 tasks/min
- **Speedup: 2.8x faster**

## Best Practices

1. **Warm up first** - Initial requests are slower
2. **Use consistent workload** - Same requests count for comparisons
3. **Test multiple times** - Average 3+ runs for accuracy
4. **Close other apps** - Ensure workers aren't busy
5. **Monitor temperature** - Mac Studios throttle when hot
6. **Use same model** - Don't compare different model sizes

## Metrics Explained

**Requests Per Second (RPS)**  
Higher is better. System throughput.

**Success Rate**  
Should be 100%. Lower means worker failures or timeouts.

**P95/P99 Response Time**  
95th/99th percentile. Shows worst-case performance.

**Load Percentage**  
Per-worker metric. Should be balanced (~33% each with 3 workers).

## Quick Comparison Script

```bash
# Test both configs in one command
for config in single_studio my_workers; do
  uv run python scripts/benchmark.py \
    -c config/${config}.json \
    --requests 10 \
    --concurrency-levels 10 \
    -o results_${config}.json
done

# View results
echo "Single:" && jq '.concurrency_benchmark[0].requests_per_second' results_single_studio.json
echo "Multiple:" && jq '.concurrency_benchmark[0].requests_per_second' results_my_workers.json
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `No workers available` | Check LM Studio is running on workers |
| `Connection refused` | Verify firewall allows connections on port 1234 |
| `Timeout errors` | Reduce concurrency or increase timeout in config |
| Negative frequency_penalty error | Update to latest version (fixed in load_balancer.py) |

## Next Steps

After benchmarking:
1. Use optimal concurrency from results in production workloads
2. Adjust `max_concurrent_requests` based on findings
3. Add more workers if scaling is linear
4. Process real research papers with optimized settings