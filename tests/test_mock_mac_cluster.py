#!/usr/bin/env python3
"""
Mock Mac Cluster Integration Tests
Tests the distributed LLM system with simulated Mac-based research lab environment
"""

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List

# Add src to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Import modules directly to avoid relative import issues
import importlib.util

# Import worker module
worker_spec = importlib.util.spec_from_file_location("worker", "../src/worker.py")
worker_module = importlib.util.module_from_spec(worker_spec)
worker_spec.loader.exec_module(worker_module)
Worker = worker_module.Worker
WorkerType = worker_module.WorkerType


@dataclass
class MockMacConfig:
    """Configuration for a mock Mac in the research cluster"""

    name: str
    model: str
    max_concurrent: int
    avg_response_time: float
    hardware_type: str  # 'M1 Air', 'M2 Pro', 'M2 Ultra', etc.


class MockMacCluster:
    """Simulates a research lab Mac cluster for testing"""

    def __init__(self):
        self.macs = self._create_mock_macs()
        self.workers = []
        self._create_workers()

    def _create_mock_macs(self) -> List[MockMacConfig]:
        """Create realistic Mac configurations for a research lab"""
        return [
            MockMacConfig(
                name="imac-office-m2",
                model="mistral-7b-instruct-v0.2",
                max_concurrent=4,
                avg_response_time=2.1,
                hardware_type="iMac M2",
            ),
            MockMacConfig(
                name="macbook-pro-research-m2-pro",
                model="mistral-7b-instruct-v0.2",
                max_concurrent=5,
                avg_response_time=1.8,
                hardware_type="MacBook Pro M2 Pro",
            ),
            MockMacConfig(
                name="mac-studio-lab-m2-ultra",
                model="mistral-7b-instruct-v0.2",
                max_concurrent=8,
                avg_response_time=1.2,
                hardware_type="Mac Studio M2 Ultra",
            ),
            MockMacConfig(
                name="macbook-air-grad-m1",
                model="mistral-7b-instruct-v0.2",
                max_concurrent=2,
                avg_response_time=3.2,
                hardware_type="MacBook Air M1",
            ),
            MockMacConfig(
                name="imac-data-m1",
                model="mistral-7b-instruct-v0.2",
                max_concurrent=3,
                avg_response_time=2.5,
                hardware_type="iMac M1",
            ),
        ]

    def _create_workers(self):
        """Create worker objects from mock Mac configurations"""
        ip_base = "192.168.1."

        for i, mac in enumerate(self.macs):
            worker = Worker(
                id=mac.name,
                host=f"{ip_base}{100 + i}",  # 192.168.1.100-104
                port=1234,
                worker_type=WorkerType.LM_STUDIO,
                model=mac.model,
                max_concurrent_requests=mac.max_concurrent,
            )

            # Simulate historical performance data
            for _ in range(10):
                worker.update_response_time(mac.avg_response_time + (time.time() % 1) - 0.5)
                worker.record_success()

            self.workers.append(worker)

    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get comprehensive cluster statistics"""
        total_concurrent = sum(w.max_concurrent_requests for w in self.workers)
        avg_response_time = sum(w.average_response_time for w in self.workers) / len(self.workers)

        return {
            "total_macs": len(self.macs),
            "total_concurrent_capacity": total_concurrent,
            "average_response_time": avg_response_time,
            "hardware_distribution": {
                "M1 Ultra": 0,
                "M1 Pro/Max": 0,
                "M1 base": len(
                    [
                        m
                        for m in self.macs
                        if "M1" in m.name and "Ultra" not in m.name and "Pro" not in m.name
                    ]
                ),
                "M2 Ultra": len([m for m in self.macs if "M2 Ultra" in m.name]),
                "M2 Pro/Max": len([m for m in self.macs if "M2 Pro" in m.name]),
                "M2 base": len(
                    [
                        m
                        for m in self.macs
                        if "M2" in m.name and "Ultra" not in m.name and "Pro" not in m.name
                    ]
                ),
            },
        }


class MockLoadBalancer:
    """Mock load balancer for testing without actual network calls"""

    def __init__(self, workers: List[Worker], mock_macs: List[MockMacConfig] = None):
        self.workers = workers
        self.mock_macs = mock_macs or []
        self.request_count = 0
        self.response_times = []
        self.worker_usage = {w.id: 0 for w in workers}

    def get_available_workers(self) -> List[Worker]:
        """Get workers that are available for requests"""
        return [w for w in self.workers if w.is_available]

    def select_worker(self) -> Worker:
        """Select best available worker using weighted selection"""
        available = self.get_available_workers()
        if not available:
            raise Exception("No available workers")

        # Simple weighted selection based on load and response time
        weights = []
        for worker in available:
            load_factor = (
                worker.max_concurrent_requests - worker.current_requests
            ) / worker.max_concurrent_requests
            speed_factor = 1.0 / max(worker.average_response_time, 0.1)
            weight = load_factor * speed_factor * worker.success_rate
            weights.append(weight)

        total_weight = sum(weights)
        if total_weight == 0:
            return available[0]

        # Select weighted random worker
        import random

        rand_val = random.uniform(0, total_weight)
        current_weight = 0
        for worker, weight in zip(available, weights):
            current_weight += weight
            if rand_val <= current_weight:
                return worker

        return available[-1]

    async def process_request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Simulate processing a request"""
        start_time = time.time()
        worker = self.select_worker()

        # Simulate request processing
        worker.current_requests += 1
        self.worker_usage[worker.id] += 1
        self.request_count += 1

        # Simulate network latency + processing time
        processing_time = worker.average_response_time * (0.8 + (time.time() % 0.4))
        await asyncio.sleep(0.01)  # Simulate minimal async processing

        response_time = time.time() - start_time
        self.response_times.append(response_time)
        worker.update_response_time(response_time)
        worker.current_requests -= 1
        worker.record_success()

        # Get hardware type from the mock config
        hardware_type = next(
            (mac.hardware_type for mac in self.mock_macs if mac.name == worker.id), "Unknown Mac"
        )

        return {
            "worker_id": worker.id,
            "model": worker.model,
            "hardware_type": hardware_type,
            "response": f"[Mock Response from {hardware_type}] Analysis of research paper complete.",
            "processing_time": processing_time,
            "total_time": response_time,
        }


async def test_mock_cluster_performance():
    """Test mock Mac cluster performance"""
    print("Mock Mac Cluster Performance Test")
    print("=" * 50)

    # Create mock cluster
    cluster = MockMacCluster()
    lb = MockLoadBalancer(cluster.workers, cluster.macs)

    # Display cluster configuration
    stats = cluster.get_cluster_stats()
    print("Cluster Configuration:")
    print(f"  Total Macs: {stats['total_macs']}")
    print(f"  Concurrent Capacity: {stats['total_concurrent_capacity']} requests")
    print(f"  Avg Response Time: {stats['average_response_time']:.2f}s")

    print("\nHardware Distribution:")
    for hw_type, count in stats["hardware_distribution"].items():
        if count > 0:
            print(f"  {hw_type}: {count}")

    # Test concurrent request processing
    print("\nTesting Concurrent Request Processing:")

    research_prompts = [
        "What is the main research question in this paper?",
        "Summarize the methodology used in this study.",
        "What are the key findings?",
        "Identify the limitations mentioned by the authors.",
        "What future research directions are suggested?",
        "Extract the statistical significance of the results.",
        "How does this paper compare to related work in the field?",
        "What datasets were used in this research?",
        "What are the practical applications of these findings?",
        "Critique the experimental design of this study.",
    ]

    start_time = time.time()

    # Process requests with different concurrency levels
    concurrency_tests = [1, 3, 5, 8, 10]

    for concurrency in concurrency_tests:
        print(f"\nConcurrency Level: {concurrency}")

        test_start = time.time()
        tasks = []

        for i in range(concurrency):
            prompt = research_prompts[i % len(research_prompts)]
            task = lb.process_request(prompt, temperature=0.7)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        test_time = time.time() - test_start

        # Calculate metrics
        avg_response = sum(r["total_time"] for r in results) / len(results)
        requests_per_second = len(results) / test_time

        print(f"  Requests processed: {len(results)}")
        print(f"  Total time: {test_time:.2f}s")
        print(f"  Avg response time: {avg_response:.2f}s")
        print(f"  Requests/second: {requests_per_second:.2f}")

        # Show worker distribution
        worker_usage = {k: v for k, v in lb.worker_usage.items() if v > 0}
        print(f"  Worker usage: {worker_usage}")

    total_time = time.time() - start_time
    print("\nOverall Performance:")
    print(f"  Total requests processed: {lb.request_count}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Overall RPS: {lb.request_count / total_time:.2f}")
    print(f"  Average response time: {sum(lb.response_times) / len(lb.response_times):.2f}s")

    return True


async def test_research_workflow_integration():
    """Test research paper processing workflow"""
    print("\n\nResearch Workflow Integration Test")
    print("=" * 50)

    cluster = MockMacCluster()
    lb = MockLoadBalancer(cluster.workers, cluster.macs)

    # Simulate batch processing of research papers
    research_papers = [
        {
            "filename": "paper1.pdf",
            "content": "This paper discusses machine learning applications...",
        },
        {
            "filename": "paper2.pdf",
            "content": "A comprehensive study on natural language processing...",
        },
        {
            "filename": "paper3.pdf",
            "content": "Novel approaches to computer vision using deep learning...",
        },
        {
            "filename": "paper4.pdf",
            "content": "Analysis of climate change impacts on biodiversity...",
        },
        {"filename": "paper5.pdf", "content": "Recent advances in quantum computing algorithms..."},
    ]

    research_prompts = [
        "Extract the main research question from {filename}: {content}",
        "Summarize the methodology in {filename}: {content}",
        "Identify key findings in {filename}: {content}",
        "Note limitations in {filename}: {content}",
        "Suggest future research directions for {filename}: {content}",
    ]

    print(f"Processing {len(research_papers)} papers with {len(research_prompts)} prompts each")
    print(f"Total tasks: {len(research_papers) * len(research_prompts)}")

    start_time = time.time()
    all_tasks = []

    for paper in research_papers:
        for prompt_template in research_prompts:
            prompt = prompt_template.format(filename=paper["filename"], content=paper["content"])
            task = lb.process_request(prompt)
            all_tasks.append(task)

    # Process all tasks
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    successful_results = [r for r in results if not isinstance(r, Exception)]
    failed_results = [r for r in results if isinstance(r, Exception)]

    total_time = time.time() - start_time

    print("\nResults Summary:")
    print(f"  Total tasks: {len(all_tasks)}")
    print(f"  Successful: {len(successful_results)}")
    print(f"  Failed: {len(failed_results)}")
    print(f"  Success rate: {len(successful_results) / len(all_tasks) * 100:.1f}%")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Tasks per second: {len(successful_results) / total_time:.2f}")
    print(f"  Average time per task: {total_time / len(successful_results):.2f}s")

    # Show worker load distribution
    print("\nWorker Load Distribution:")
    for worker in cluster.workers:
        usage = lb.worker_usage.get(worker.id, 0)
        load_pct = (usage / worker.max_concurrent_requests) * 100
        print(f"  {worker.id}: {usage}/{worker.max_concurrent_requests} ({load_pct:.1f}%)")

    return len(failed_results) == 0


def main():
    """Run all mock Mac cluster tests"""
    print("MOCK MAC CLUSTER INTEGRATION TESTS")
    print("=" * 60)
    print("Testing Distributed LLM System with Simulated Research Lab")
    print("=" * 60)

    async def run_all_tests():
        try:
            # Test 1: Mock cluster performance
            perf_success = await test_mock_cluster_performance()

            # Test 2: Research workflow integration
            workflow_success = await test_research_workflow_integration()

            return perf_success and workflow_success

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    # Run tests
    success = asyncio.run(run_all_tests())

    if success:
        print("\n" + "=" * 60)
        print("ALL MOCK MAC CLUSTER TESTS PASSED!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ SOME TESTS FAILED")
        print("Check the errors above for details")
        print("=" * 60)

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
