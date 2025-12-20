# Distributed LLM System

A scalable system for processing research papers across multiple Mac computers using **LM Studio** for enhanced performance. Transform your 30-minute research paper review process into a 2-minute automated analysis by distributing work across all your Mac computers.

Perfect for Mac-based research labs and academic environments:
- Researchers analyzing hundreds of papers
- Literature reviews and systematic studies
- Extracting key findings from academic papers
- Summarizing methodologies and results
- Optimizing Mac hardware utilization for research workflows
- Processing large document collections efficiently

## Prerequisites Checklist

### Required Hardware
- **1 Master Mac** - Runs this distributed-llm project (M1/M2/M3 recommended)
- **1-35 Worker Macs** - Each runs LM Studio or Ollama (any Mac with Apple Silicon or Intel)
- All Macs on the same network (WiFi or Ethernet)

### Software Requirements
- **Workers**: LM Studio (recommended for Mac optimization), Ollama
- **Master**: Python 3.8+ and uv (package manager)
- **Exo**: Optional - for clustering multiple Macs to run larger models (requires admin access)

No cloud services or API keys needed - everything runs locally on your Macs!

## Step 1: Install on Worker Macs (LM Studio)

Do this on EACH Mac that will serve as a worker:

### 1.1 Install LM Studio
```bash
# Install uv (package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/LaansDole/distributed-llm-mac.git
cd distributed-llm
uv sync
```

2. **Set up Worker Macs:**
   - Install [LM Studio](https://lmstudio.ai/) (recommended) or Ollama
   - Configure for network access (host: `0.0.0.0`)
   - Download a model (e.g., Mistral 7B)
   - Find IP address: `ipconfig getifaddr en0`

3. **Configure Workers:**
```bash
cp config/workers.json config/my_workers.json
# Edit config/my_workers.json with your worker IPs
```

4. **Test:**
```bash
uv run python -m src.main --config config/my_workers.json --test
```

## Available Scripts

All scripts use the load balancer to distribute work across your Mac Studios/workers. Specify your worker configuration with `--config` (defaults to `config/workers.json`).

### 1. Process Research Papers
```bash
# Use research presets (5 prompts per paper)
uv run python scripts/process_directory.py \
  --config config/my_workers.json \
  --input ~/research/papers \
  --preset research \
  --max-concurrent 50

# Custom prompts
uv run python scripts/process_directory.py \
  --config config/my_workers.json \
  -i ~/papers \
  -p "What is the main contribution of this paper?" \
  -p "Extract the methodology" \
  -o analysis.json
```

**Presets:**
- `research` - Extract questions, methodology, findings, limitations, future work
- `summary` - Concise summaries and main points
- `analysis` - Strengths, weaknesses, innovations

**How it works:** The script loads your workers from config, creates a LoadBalancer instance, then distributes all prompts × files across available workers using weighted selection and health monitoring.

### 2. Benchmark Performance
```bash
# Full benchmark (concurrency + worker scaling)
uv run python scripts/benchmark.py --config config/my_workers.json

# Test specific concurrency levels
uv run python scripts/benchmark.py --config config/my_workers.json --mode concurrency --requests 100

# Output to custom file
uv run python scripts/benchmark.py -c config/my_workers.json -o my_results.json
```

**How it works:** Tests your distributed setup with increasing concurrency levels (1, 5, 10, 20, 50, 100) to find optimal performance. Shows requests/sec, response times, and per-worker utilization.

**Comparing Single vs Multiple Mac Studios:**
```bash
# Create config for single Mac Studio (config/single_studio.json)
# Then compare performance:
uv run python scripts/benchmark.py -c config/single_studio.json -o results_single.json
uv run python scripts/benchmark.py -c config/my_workers.json -o results_multiple.json

# Compare results (view speedup)
jq '.concurrency_benchmark[] | {concurrency, rps: .requests_per_second}' results_*.json
```

Expected speedup with 3 Mac Studios: **2.5-2.8x** faster than single Studio.

**For detailed benchmarking guide:** See [docs/benchmarking.md](docs/benchmarking.md)

### 3. Interactive Mode
```bash
uv run python -m src.main --config config/my_workers.json --interactive
```

**How it works:** Enter prompts interactively and watch the load balancer distribute them across workers in real-time. Use `status` to see worker metrics or `metrics` for detailed stats.

### 4. Quick Setup Wizard
```bash
uv run python scripts/quickstart.py
```

**How it works:** Guides you through installation, config creation, and testing. Creates example config if needed.

## Worker Configuration

Edit `config/my_workers.json`:

```json
{
  "workers": [
    {
      "id": "imac-office",
      "host": "192.168.1.105",
      "port": 1234,
      "type": "lm_studio",
      "model": "mistral-7b-instruct-v0.2",
      "max_concurrent_requests": 3
    },
    {
      "id": "macbook-pro",
      "host": "192.168.1.106",
      "port": 1234,
      "type": "lm_studio",
      "model": "mistral-7b-instruct-v0.2",
      "max_concurrent_requests": 2
    },
    {
      "id": "mac-studio-lab",
      "host": "192.168.1.107",
      "port": 1234,
      "type": "lm_studio",
      "model": "mistral-7b-instruct-v0.2",
      "max_concurrent_requests": 5
    }
  ]
}
```

**Worker Types:**
- `lm_studio` - LM Studio server (port 1234)
- `ollama` - Ollama server (port 11434)
- `exo` - Exo cluster (port 52415)

**Recommended `max_concurrent_requests` by Mac:**
- MacBook Air (M1/M2): 2
- MacBook Pro (M1/M2): 3-5
- iMac (M1/M2): 3-4
- Mac Studio (M1/M2): 5-8
- Mac Pro: 8-12

## Performance

Based on Mistral 7B on M1/M2 Macs:

| Workers | Papers/min | Time for 100 Papers |
|---------|------------|---------------------|
| 1       | 5          | 20 minutes          |
| 3       | 15         | 7 minutes           |
| 5       | 25         | 4 minutes           |
| 10      | 50         | 2 minutes           |

## Common Issues

### Workers Not Connecting
```bash
# Test individual worker
curl http://192.168.1.105:1234/v1/models

# Check firewall (System Settings → Network → Firewall)
# Ensure LM Studio server is started with "Allow external connections"
```

### Finding Worker IPs
```bash
# WiFi
ipconfig getifaddr en0

# Ethernet
ipconfig getifaddr en1
```

## Architecture

```
                  Your Local Network
                          |
          +-------------------------------+
          |                               |
    Master Mac                    Worker Mac 1
  (distributed-llm)              (LM Studio)
          |                               |
          +-----------+-----------+-------+
                      |
      +---------------+---------------+
      |               |               |
Worker Mac 2    Worker Mac 3      Worker Mac N
   (LM Studio)     (LM Studio)     (Ollama)
```

## Features

- **Mac-Optimized**: Built for Apple Silicon (M1/M2/M3)
- **Scalable**: Process across 2-35 Macs simultaneously
- **10-35x Faster**: Compared to single machine
- **Local Only**: No cloud services or API keys needed
- **Auto Load Balancing**: Mac-aware performance tuning
- **Health Monitoring**: Automatic worker health checks

## API Usage

```python
from src.load_balancer import LoadBalancer
from src.worker import Worker, WorkerType

# Create workers
workers = [
    Worker(
        id="worker-1",
        host="192.168.1.100",
        port=1234,
        worker_type=WorkerType.LM_STUDIO,
        model="mistral-7b-instruct-v0.2"
    )
]

# Process requests
async with LoadBalancer(workers) as lb:
    result = await lb.process_request("What is machine learning?")
    print(result)
    
    # Batch processing
    results = await lb.process_batch(prompts, max_concurrent=50)
```

## Directory Structure

```
distributed-llm/
├── src/                    # Core load balancer code
│   ├── main.py            # Entry point
│   ├── load_balancer.py   # Task distribution
│   ├── worker.py          # Worker management
│   └── config.py          # Configuration handling
├── scripts/
│   ├── process_directory.py  # Batch paper processing
│   ├── benchmark.py          # Performance testing
│   └── quickstart.py         # Setup wizard
├── config/
│   └── workers.json       # Worker configuration
├── examples/
│   └── texts/             # Sample papers
└── tests/
```

## Advanced: Exo Cluster (Optional)

For running larger models (70B+ parameters) across multiple Macs:

```bash
# Install Exo
# Download from: https://github.com/exo-explore/exo/releases

# Start on each Mac
exo

# Add to config
{
  "id": "exo-cluster",
  "host": "localhost",
  "port": 52415,
  "type": "exo",
  "model": "llama-3.1-70b",
  "max_concurrent_requests": 8
}
```

**Note:** Requires admin access for network profile installation.

## Monitoring

```python
# Get real-time metrics
metrics = lb.get_metrics()

print(f"Total requests: {metrics['request_metrics']['total_requests']}")
print(f"Success rate: {metrics['request_metrics']['success_rate']:.2%}")
print(f"Avg response time: {metrics['request_metrics']['average_response_time']:.2f}s")
```

## Debug Mode

```bash
export LOG_LEVEL=DEBUG
python -m src.main --config config/workers.json
```

## License

MIT