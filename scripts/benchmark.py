#!/usr/bin/env python3
"""
Benchmark script for testing distributed LLM performance
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
import statistics
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from src.load_balancer import LoadBalancer
from src.worker import Worker, WorkerType
from src.config import load_workers_config


def generate_test_prompts(count: int = 100) -> List[str]:
    """Generate diverse test prompts optimized for short answers"""
    # Short-answer prompts that naturally produce 10-50 token responses
    base_prompts = [
        "What is the capital of {country}?",
        "Define {concept} in one sentence.",
        "Name three benefits of {technology}.",
        "What year was {event}?",
        "List the primary colors.",
        "How many days in a week?",
        "What is 25 + 17?",
        "Name the largest planet.",
        "What is the speed of light?",
        "Who invented {invention}?"
    ]

    countries = ["France", "Japan", "Brazil", "Canada", "Australia", "Germany", "India", "Mexico"]
    concepts = ["AI", "blockchain", "encryption", "API", "cache"]
    technologies = ["solar panels", "electric cars", "5G", "cloud storage", "GPS"]
    events = ["WWI start", "moon landing", "internet creation", "first flight", "printing press invention"]
    inventions = ["the telephone", "the light bulb", "the airplane", "the computer", "the internet"]

    prompts = []
    for i in range(count):
        template = base_prompts[i % len(base_prompts)]

        # Fill in template
        if "{country}" in template:
            prompt = template.format(country=countries[i % len(countries)])
        elif "{concept}" in template:
            prompt = template.format(concept=concepts[i % len(concepts)])
        elif "{technology}" in template:
            prompt = template.format(technology=technologies[i % len(technologies)])
        elif "{event}" in template:
            prompt = template.format(event=events[i % len(events)])
        elif "{invention}" in template:
            prompt = template.format(invention=inventions[i % len(inventions)])
        else:
            prompt = template  # Use as-is for prompts without placeholders

        prompts.append(prompt)

    return prompts


async def benchmark_with_scaling(workers: List[Worker], num_requests: int = 100,
                                concurrency_levels: List[int] = None, max_tokens: int = 100):
    """Benchmark performance with different concurrency levels"""

    if concurrency_levels is None:
        concurrency_levels = [1, 5, 10, 20, 50, 100]

    test_prompts = generate_test_prompts(num_requests)

    results = []

    async with LoadBalancer(workers) as lb:
        # Wait for initial health checks to complete
        await asyncio.sleep(2)
        
        for concurrency in concurrency_levels:
            if concurrency > num_requests:
                continue

            print(f"\n{'='*60}")
            print(f"BENCHMARKING WITH CONCURRENCY: {concurrency}")
            print(f"{'='*60}")

            # Warmup
            print("Warming up...")
            await lb.process_batch(test_prompts[:5], max_concurrent=5)

            # Clear metrics before the actual benchmark
            lb.metrics['response_times'].clear()
            
            # Actual benchmark
            print(f"Running {num_requests} requests with concurrency {concurrency}...")
            start_time = time.time()

            # Get max_tokens from args if available (passed via kwargs)
            max_tokens = kwargs.get('max_tokens', 100)
            
            batch_results = await lb.process_batch(
                test_prompts,
                max_concurrent=concurrency,
                max_tokens=max_tokens
            )

            elapsed = time.time() - start_time

            # Calculate metrics
            successful = sum(1 for r in batch_results if r['success'])
            failed = num_requests - successful

            # Get response times from this batch only (metrics were cleared before)
            metrics = lb.get_metrics()
            response_times = list(lb.metrics['response_times'])

            result = {
                'concurrency': concurrency,
                'total_requests': num_requests,
                'successful': successful,
                'failed': failed,
                'success_rate': (successful / num_requests) * 100,
                'total_time': elapsed,
                'requests_per_second': num_requests / elapsed,
                'avg_response_time': statistics.mean(response_times) if response_times else 0,
                'min_response_time': min(response_times) if response_times else 0,
                'max_response_time': max(response_times) if response_times else 0,
                'p50_response_time': statistics.median(response_times) if response_times else 0,
                'p95_response_time': sorted(response_times)[int(0.95 * len(response_times))] if response_times else 0,
                'p99_response_time': sorted(response_times)[int(0.99 * len(response_times))] if response_times else 0
            }

            results.append(result)

            # Print summary
            print(f"\nResults:")
            print(f"  Requests/sec: {result['requests_per_second']:.2f}")
            print(f"  Success rate: {result['success_rate']:.1f}%")
            print(f"  Avg response time: {result['avg_response_time']:.2f}s")
            print(f"  P95 response time: {result['p95_response_time']:.2f}s")
            print(f"  P99 response time: {result['p99_response_time']:.2f}s")

            # Show worker stats
            print("\nWorker utilization:")
            for worker in workers:
                print(f"  {worker.id}: {worker.total_requests} requests, "
                      f"{worker.success_rate:.1%} success rate")

            # Wait between tests
            if concurrency != concurrency_levels[-1]:
                print("\nWaiting 10 seconds before next test...")
                await asyncio.sleep(10)

    return results


async def benchmark_worker_scaling(worker_counts: List[int], base_config: Dict,
                                  requests_per_test: int = 50):
    """Benchmark with different numbers of workers"""

    results = []

    for count in worker_counts:
        print(f"\n{'='*60}")
        print(f"TESTING WITH {count} WORKERS")
        print(f"{'='*60}")

        # Create subset of workers
        workers = []
        for i in range(min(count, len(base_config['workers']))):
            worker_data = base_config['workers'][i]
            workers.append(Worker(
                id=worker_data['id'],
                host=worker_data['host'],
                port=worker_data['port'],
                worker_type=WorkerType(worker_data['type'].value),
                model=worker_data['model'],
                max_concurrent_requests=worker_data.get('max_concurrent_requests', 5)
            ))

        test_prompts = generate_test_prompts(requests_per_test)

        async with LoadBalancer(workers) as lb:
            # Wait for health checks
            await asyncio.sleep(2)

            healthy_count = sum(1 for w in workers if w.is_healthy)
            print(f"Healthy workers: {healthy_count}/{count}")

            if healthy_count == 0:
                results.append({
                    'workers': count,
                    'healthy_workers': 0,
                    'requests_per_second': 0,
                    'success_rate': 0
                })
                continue

            start_time = time.time()
            batch_results = await lb.process_batch(test_prompts)
            elapsed = time.time() - start_time

            successful = sum(1 for r in batch_results if r['success'])

            result = {
                'workers': count,
                'healthy_workers': healthy_count,
                'requests_per_second': requests_per_test / elapsed,
                'success_rate': (successful / requests_per_test) * 100,
                'throughput_per_worker': (requests_per_test / elapsed) / healthy_count if healthy_count > 0 else 0
            }

            results.append(result)

            print(f"Throughput: {result['requests_per_second']:.2f} req/sec")
            print(f"Per worker: {result['throughput_per_worker']:.2f} req/sec")

    return results


def main():
    parser = argparse.ArgumentParser(description="Benchmark distributed LLM performance")
    parser.add_argument('-c', '--config', default='config/workers.json',
                       help='Worker configuration file')
    parser.add_argument('-o', '--output', default='benchmark_results.json',
                       help='Output file for results')
    parser.add_argument('--requests', type=int, default=100,
                       help='Number of requests for benchmark')
    parser.add_argument('--mode', choices=['concurrency', 'scaling', 'both'],
                       default='both', help='Benchmark mode')
    parser.add_argument('--concurrency-levels', nargs='+', type=int,
                       default=[1, 5, 10, 20, 50, 100],
                       help='Concurrency levels to test')
    parser.add_argument('--worker-counts', nargs='+', type=int,
                       default=[1, 2, 3, 5, 10],
                       help='Worker counts to test for scaling')
    parser.add_argument('--max-tokens', type=int, default=100,
                       help='Maximum tokens per response (default: 100, reduces from 512 for faster benchmarks)')

    args = parser.parse_args()

    # Load configuration
    if not Path(args.config).exists():
        print(f"Error: Configuration file not found: {args.config}")
        sys.exit(1)

    config_data = load_workers_config(args.config)

    # Create workers
    workers = []
    for worker_data in config_data:
        workers.append(Worker(
            id=worker_data['id'],
            host=worker_data['host'],
            port=worker_data['port'],
            worker_type=WorkerType(worker_data['type']),
            model=worker_data['model'],
            max_concurrent_requests=worker_data.get('max_concurrent_requests', 5)
        ))

    print(f"Loaded {len(workers)} workers")

    # Run benchmarks
    all_results = {
        'timestamp': datetime.now().isoformat(),
        'configuration': {
            'workers': len(workers),
            'requests': args.requests,
            'concurrency_levels': args.concurrency_levels,
            'worker_counts': args.worker_counts
        }
    }

    if args.mode in ['concurrency', 'both']:
        print("\nStarting concurrency benchmark...")
        concurrency_results = asyncio.run(
            benchmark_with_scaling(
                workers, 
                args.requests, 
                args.concurrency_levels,
                max_tokens=args.max_tokens
            )
        )
        all_results['concurrency_benchmark'] = concurrency_results

    if args.mode in ['scaling', 'both']:
        print("\nStarting worker scaling benchmark...")
        scaling_results = asyncio.run(
            benchmark_worker_scaling(args.worker_counts, config_data, args.requests)
        )
        all_results['scaling_benchmark'] = scaling_results

    # Save results
    with open(args.output, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n{'='*60}")
    print("BENCHMARK COMPLETE")
    print(f"{'='*60}")
    print(f"Results saved to: {args.output}")

    # Summary
    if 'concurrency_benchmark' in all_results:
        best_throughput = max(all_results['concurrency_benchmark'],
                            key=lambda x: x['requests_per_second'])
        print(f"\nBest concurrency: {best_throughput['concurrency']} "
              f"({best_throughput['requests_per_second']:.2f} req/sec)")

    if 'scaling_benchmark' in all_results:
        best_workers = max(all_results['scaling_benchmark'],
                          key=lambda x: x['requests_per_second'])
        print(f"Best worker count: {best_workers['workers']} "
              f"({best_workers['requests_per_second']:.2f} req/sec)")


if __name__ == "__main__":
    main()