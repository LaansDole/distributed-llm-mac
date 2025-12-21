"""
Main entry point for the distributed LLM load balancer
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add src to path for imports
sys.path.append(str(Path(__file__).parent))

from src.config import load_config, load_workers_config
from src.load_balancer import LoadBalancer
from src.worker import Worker, WorkerType


def create_workers_from_config(config_data: List[Dict[str, Any]]) -> List[Worker]:
    """Create worker instances from configuration data"""
    workers = []
    for worker_data in config_data:
        try:
            worker = Worker(
                id=worker_data["id"],
                host=worker_data["host"],
                port=worker_data["port"],
                worker_type=WorkerType(worker_data["type"]),
                model=worker_data["model"],
                max_concurrent_requests=worker_data.get("max_concurrent_requests", 5),
            )
            workers.append(worker)
            print(f"Added worker: {worker}")
        except KeyError as e:
            print(f"Error: Missing required field {e} in worker configuration")
            sys.exit(1)
        except ValueError as e:
            print(f"Error: Invalid worker type: {e}")
            sys.exit(1)

    return workers


async def test_workers(workers: List[Worker]):
    """Test connectivity to all workers"""
    print("\nTesting worker connectivity...")
    print("-" * 60)

    async with LoadBalancer(workers) as lb:
        # Wait for initial health checks
        await asyncio.sleep(2)

        healthy_workers = [w for w in workers if w.is_healthy]
        print(f"\nHealthy workers: {len(healthy_workers)}/{len(workers)}")

        if len(healthy_workers) == 0:
            print("ERROR: No healthy workers available!")
            return False

        # Test a simple request
        test_prompt = "Hello, how are you?"
        print(f"\nTesting with prompt: '{test_prompt}'")

        try:
            await lb.process_request(test_prompt)
            print("✓ Test request successful")
            return True
        except Exception as e:
            print(f"✗ Test request failed: {e}")
            return False


async def interactive_mode(workers: List[Worker]):
    """Interactive mode for testing requests"""
    async with LoadBalancer(workers) as lb:
        print("\n" + "=" * 60)
        print("INTERACTIVE MODE")
        print("=" * 60)
        print("Enter prompts to process (or 'quit' to exit, 'status' for metrics)")
        print("-" * 60)

        while True:
            try:
                prompt = input("\nPrompt> ").strip()

                if prompt.lower() in ["quit", "exit", "q"]:
                    break
                elif prompt.lower() == "status":
                    lb.print_status()
                    continue
                elif prompt.lower() == "metrics":
                    metrics = lb.get_metrics()
                    print(json.dumps(metrics, indent=2))
                    continue
                elif not prompt:
                    continue

                print("\nProcessing...")
                start_time = asyncio.get_event_loop().time()

                try:
                    result = await lb.process_request(prompt)
                    elapsed = asyncio.get_event_loop().time() - start_time

                    # Extract response based on worker type
                    if result and "response" in result:
                        response = result["response"]
                    elif result and "choices" in result and result["choices"]:
                        # Check for ChatGPT format (Exo)
                        if "message" in result["choices"][0]:
                            response = result["choices"][0]["message"]["content"]
                        else:
                            # LM Studio format
                            response = result["choices"][0]["text"]
                    else:
                        response = str(result)

                    print(f"\nResponse (took {elapsed:.2f}s):")
                    print("-" * 40)
                    print(response.strip())
                    print("-" * 40)

                except Exception as e:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    print(f"\nError after {elapsed:.2f}s: {e}")

            except KeyboardInterrupt:
                print("\n\nExiting...")
                break


async def benchmark_mode(workers: List[Worker], num_requests: int = 50):
    """Benchmark mode for performance testing"""
    print(f"\nRunning benchmark with {num_requests} concurrent requests...")

    test_prompts = [
        "What is the capital of France?",
        "Explain the concept of machine learning.",
        "Write a short poem about technology.",
        "What are the benefits of renewable energy?",
        "Describe the process of photosynthesis.",
    ] * (num_requests // 5 + 1)

    test_prompts = test_prompts[:num_requests]

    async with LoadBalancer(workers) as lb:
        start_time = asyncio.get_event_loop().time()

        results = await lb.process_batch(test_prompts, max_concurrent=num_requests)

        elapsed = asyncio.get_event_loop().time() - start_time

        # Calculate statistics
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        rps = len(results) / elapsed

        print("\nBenchmark Results:")
        print(f"  Total requests: {len(results)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Time taken: {elapsed:.2f}s")
        print(f"  Requests/sec: {rps:.2f}")
        print(f"  Success rate: {(successful / len(results)) * 100:.1f}%")

        # Show worker metrics
        lb.print_status()


def main():
    parser = argparse.ArgumentParser(description="Distributed LLM Load Balancer")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config/workers.json",
        help="Path to worker configuration file",
    )
    parser.add_argument("--settings", "-s", type=str, help="Path to load balancer settings file")
    parser.add_argument("--test", "-t", action="store_true", help="Test worker connectivity")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument(
        "--benchmark", "-b", type=int, metavar="N", help="Run benchmark with N requests"
    )
    parser.add_argument("--prompt", "-p", type=str, help="Process a single prompt")
    parser.add_argument("--output", "-o", type=str, help="Output file for results (JSON format)")

    args = parser.parse_args()

    # Load configuration
    if not os.path.exists(args.config):
        print(f"Error: Configuration file not found: {args.config}")
        print("Create a configuration file with worker definitions.")
        sys.exit(1)

    try:
        config_data = load_workers_config(args.config)
        workers = create_workers_from_config(config_data)

        # Load settings if provided
        settings = None
        if args.settings and os.path.exists(args.settings):
            settings = load_config(args.settings)

        print(f"Loaded {len(workers)} workers from configuration")
        print(
            f"Worker types: {len([w for w in workers if w.worker_type.value == 'ollama'])} Ollama, "
            f"{len([w for w in workers if w.worker_type.value == 'lm_studio'])} LM Studio, "
            f"{len([w for w in workers if w.worker_type.value == 'exo'])} Exo"
        )

        # Run appropriate mode
        if args.test:
            success = asyncio.run(test_workers(workers))
            sys.exit(0 if success else 1)

        elif args.interactive:
            asyncio.run(interactive_mode(workers))

        elif args.benchmark:
            asyncio.run(benchmark_mode(workers, args.benchmark))

        elif args.prompt:
            async def single_request():
                async with LoadBalancer(workers, config=settings) as lb:
                    result = await lb.process_request(args.prompt)
                    return result

            result = asyncio.run(single_request())
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(result, f, indent=2)
                print(f"Result saved to {args.output}")
            else:
                print("\nResult:")
                print(json.dumps(result, indent=2))

        else:
            # Default: show status
            async def show_status():
                async with LoadBalancer(workers, config=settings) as lb:
                    await asyncio.sleep(2)  # Let health checks run
                    lb.print_status()

            asyncio.run(show_status())

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
    