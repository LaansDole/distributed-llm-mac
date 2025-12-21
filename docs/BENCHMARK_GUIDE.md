# Benchmarking Guide: Network Validation First

**⚠️ CRITICAL UPDATE**: Due to network connectivity failures (100% packet loss), **DO NOT RUN BENCHMARKS until network issues are resolved**. Load balancer performance is excellent (4x improvement achieved), but network infrastructure must be validated first.

## 🚨 STEP 1: Network Validation (MANDATORY - 2 Minutes)

**Before ANY benchmarking, verify network connectivity:**

```bash
# Test basic connectivity to ALL workers
WORKERS="10.247.162.71 10.247.162.90"  # Update with your worker IPs
PORT=1234

echo "=== CRITICAL: Network Connectivity Test ==="
for worker in $WORKERS; do
    echo "Testing $worker:$PORT"
    if nc -z -v $worker $PORT; then
        echo "✅ $worker is reachable"
    else
        echo "❌ $worker is NOT reachable - FIX THIS FIRST"
        echo "   Check: LM Studio running? Firewall? Network?"
    fi
done

# Additional tests
echo "=== Ping Tests ==="
for worker in $WORKERS; do
    ping -c 3 $worker
done
```

**If ANY worker shows "❌ NOT reachable", DO NOT PROCEED with benchmarking.**

### Network Issues Found?

**Common Solutions:**
1. **LM Studio not running** on worker machine
2. **Firewall blocking** port 1234
3. **Wrong IP addresses** in config files
4. **Network segmentation** (different subnets)
5. **WiFi vs Ethernet** connectivity issues

### Expected Network Results:
```
✅ 10.247.162.71:1234 is reachable
✅ 10.247.162.90:1234 is reachable
PING 10.247.162.71 (10.247.162.71): 56 data bytes
64 bytes from 10.247.162.71: icmp_seq=0 ttl=64 time=2.123 ms
```

If you see `ping: sendto: Host is down` or `100% packet loss`, **STOP** and fix network first.

## Quick Start (AFTER Network Validation - 5 Minutes)

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

### Expected Performance (With Healthy Network)

**✅ Single Worker Baseline (Achieved):**
- Throughput: 1.77 req/s (concurrency 12)
- Response time: ~0.6s average
- Success rate: 100%

**✅ Multiple Workers (Target after network fix):**
- Throughput: 2.5-3.0 req/s (1.5-1.7x speedup)
- Response time: 0.6-1.0s average
- Success rate: 95%+

### 🚨 Problem Indicators (Current State)

**❌ Multiple Workers Slower Than Single:**
```
Multiple Workers: 1.04 req/s (concurrency 12)
Single Worker:   1.77 req/s (concurrency 12)
Speedup: 0.59x (41% slower)
```
**Root Cause**: Network connectivity failure (100% packet loss)

**❌ Response Time Inflation:**
```
Single Worker:   ~0.6s average
Multiple Workers: 8.14s average (13x slower!)
```
**Root Cause**: Network timeout accumulation + retry overhead

### Network Failure Symptoms

**Immediate Red Flags:**
- Multiple workers slower than single worker
- Response times > 3x single worker baseline
- Average response time > 5 seconds
- Ping tests show packet loss

**Network-Specific Issues to Fix:**

**Critical Packet Loss (Current Issue):**
```bash
ping -c 10 10.247.162.99
# Result: 100% packet loss - CATASTROPHIC
```

**High Latency (>10ms):**
```bash
ping -c 10 10.247.162.99
# Result: 50ms average - TOO HIGH for LLM workloads
```

**Connection Timeouts:**
```bash
telnet 10.247.162.99 1234
# Result: Connection refused/timed out
```

### Performance Recovery Steps

**Step 1: Fix Network (Priority: CRITICAL)**
1. Verify LM Studio running on all workers
2. Check firewall allows port 1234
3. Confirm IP addresses are correct
4. Test with Ethernet instead of WiFi

**Step 2: Validate Fix**
```bash
# Should now show reachable workers
./scripts/network_validation.sh

# Should show <5ms ping times
ping -c 10 10.247.162.71
```

**Step 3: Re-run Benchmarks**
```bash
# Expected: 1.5-1.7x speedup with multiple workers
./scripts/quick_benchmark.sh
```

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

## 🚨 Critical Troubleshooting (Network Focus)

| Symptom | Root Cause | Immediate Action |
|---------|-----------|------------------|
| `Multiple workers slower than single` | **Network connectivity failure** | ❌ STOP - Fix network first |
| `100% packet loss` in ping tests | Workers unreachable | Check LM Studio running + firewall |
| `Connection refused` | LM Studio not running or firewall | Start LM Studio, open port 1234 |
| `Response times > 5s` | Network timeout accumulation | Verify all workers reachable |
| `Load balancer retries` | Network failures causing cascading delays | Fix underlying network issues |

## Network Validation Checklist ✅

**Before running ANY benchmarks, ensure:**

- [ ] **All workers reachable via ping**: `ping -c 3 <worker_ip>`
- [ ] **Port 1234 open on all workers**: `telnet <worker_ip> 1234`
- [ ] **No packet loss**: 0% loss in ping tests
- [ ] **Latency < 10ms**: Ping times under 10 milliseconds
- [ ] **LM Studio running**: Verify process on each worker
- [ ] **Same network subnet**: All machines on 10.247.x.x network

**If ANY item above fails, DO NOT run benchmarks.**

## Quick Network Fix Commands

```bash
# On each worker machine (if LM Studio not running):
# 1. Start LM Studio
open -a "LM Studio"

# 2. Verify port is listening
lsof -i :1234

# 3. Check firewall (macOS)
sudo pfctl -sr | grep 1234

# On load balancer machine:
# 1. Test connectivity
for ip in 10.247.162.71 10.247.162.90; do
    echo "Testing $ip"
    nc -z -v $ip 1234 && echo "✅ OK" || echo "❌ FAILED"
done
```

## Legacy Issues (Less Critical)

| Issue | Solution |
|-------|----------|
| `Negative frequency_penalty error` | ✅ **FIXED** - Updated in latest load_balancer.py |
| `Load imbalance` | ✅ **OPTIMIZED** - Hybrid algorithm now works correctly |
| `Connection pooling` | ✅ **ENHANCED** - 4x single-worker improvement achieved |

## Next Steps

After benchmarking:
1. Use optimal concurrency from results in production workloads
2. Adjust `max_concurrent_requests` based on findings
3. Add more workers if scaling is linear
4. Process real research papers with optimized settings
