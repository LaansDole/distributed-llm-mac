#!/bin/bash
# Quick benchmark script - runs in ~5 minutes
# Compares single Mac Studio vs multiple Mac Studios

set -e

echo "========================================"
echo "QUICK BENCHMARK TEST (~5 minutes)"
echo "========================================"
echo ""

# Check if configs exist
if [ ! -f "config/single_studio.json" ]; then
    echo "⚠️  Warning: config/single_studio.json not found"
    echo "Creating example single studio config..."
    
    mkdir -p config
    cat > config/single_studio.json <<EOF
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
EOF
    echo "✓ Created config/single_studio.json"
    echo "  Please update the 'host' IP address to match your Mac Studio"
    echo ""
fi

if [ ! -f "config/my_workers.json" ]; then
    echo "❌ Error: config/my_workers.json not found"
    echo "Please create config/my_workers.json with your worker configuration"
    exit 1
fi

# Run quick benchmarks
echo "Step 1/2: Benchmarking single Mac Studio..."
echo "--------------------------------------------"
uv run python scripts/benchmark.py \
  -c config/single_studio.json \
  --requests 10 \
  --concurrency-levels 6 12 \
  --max-tokens 100 \
  --mode concurrency \
  -o results_single.json

echo ""
echo "Step 2/2: Benchmarking multiple Mac Studios..."
echo "--------------------------------------------"
uv run python scripts/benchmark.py \
  -c config/my_workers.json \
  --requests 10 \
  --concurrency-levels 6 12 \
  --max-tokens 100 \
  --mode concurrency \
  -o results_multiple.json

echo ""
echo "========================================"
echo "RESULTS COMPARISON"
echo "========================================"
echo ""

# Check if jq is available
if command -v jq &> /dev/null; then
    echo "Single Mac Studio:"
    jq -r '.concurrency_benchmark[] | "  Concurrency \(.concurrency): \(.requests_per_second | tonumber | . * 100 | round / 100) req/s"' results_single.json
    
    echo ""
    echo "Multiple Mac Studios:"
    jq -r '.concurrency_benchmark[] | "  Concurrency \(.concurrency): \(.requests_per_second | tonumber | . * 100 | round / 100) req/s"' results_multiple.json
    
    echo ""
    echo "Speedup Calculation:"
    python3 <<EOF
import json

single = json.load(open('results_single.json'))
multiple = json.load(open('results_multiple.json'))

for s, m in zip(single['concurrency_benchmark'], multiple['concurrency_benchmark']):
    conc = s['concurrency']
    single_rps = s['requests_per_second']
    multi_rps = m['requests_per_second']
    speedup = multi_rps / single_rps if single_rps > 0 else 0
    print(f"  Concurrency {conc}: {speedup:.2f}x speedup")
EOF
else
    echo "Results saved to results_single.json and results_multiple.json"
    echo "Install jq for formatted output: brew install jq"
fi

echo ""
echo "✓ Benchmark complete!"
echo "Full results saved to:"
echo "  - results_single.json"
echo "  - results_multiple.json"
