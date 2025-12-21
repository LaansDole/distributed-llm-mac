"""
Distributed LLM Load Balancer
Supports Ollama, LM Studio, and Exo cluster workers
"""

import asyncio
import logging
import random
import time
from collections import deque
from typing import Any, Dict, List, Optional

import aiohttp

from .config import LoadBalancerConfig, get_config_from_env
from .worker import Worker, WorkerType

# Configure logging
logger = logging.getLogger(__name__)


class LoadBalancer:
    """Load balancer for distributing LLM inference requests across Ollama, LM Studio, and Exo workers"""

    def __init__(self, workers: List[Worker], config: Optional[LoadBalancerConfig] = None):
        self.workers = workers
        self.config = config or get_config_from_env()
        self.session: Optional[aiohttp.ClientSession] = None
        self.health_check_task: Optional[asyncio.Task] = None
        self._shutdown = False

        # Request metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": deque(maxlen=1000),
            "start_time": time.time(),
        }

        # Setup logging
        logging.basicConfig(level=getattr(logging, self.config.log_level.upper()))
        logger.info(f"Initialized load balancer with {len(self.workers)} workers")

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop()

    async def start(self):
        """Start the load balancer"""
        # Optimized connection pooling: limit based on worker count, not total pool size
        # Each worker should have reasonable connection limit matching their capacity
        connector = aiohttp.TCPConnector(
            limit=len(self.workers) * 20,  # 20 connections per worker
            limit_per_host=10,  # Fixed reasonable limit per backend
            ttl_dns_cache=self.config.dns_cache_ttl,
            use_dns_cache=True,
            keepalive_timeout=90,  # Extended keepalive for LLM workloads
            enable_cleanup_closed=True,
            force_close=False,  # Keep connections alive for better performance
        )

        timeout = aiohttp.ClientTimeout(
            total=self.config.request_timeout,
            connect=getattr(self.config, 'connection_timeout', 10),
            sock_read=getattr(self.config, 'socket_read_timeout', 60)
        )

        self.session = aiohttp.ClientSession(
            connector=connector, timeout=timeout, headers={"Content-Type": "application/json"}
        )

        # Start health check task
        if self.config.health_check_interval > 0:
            self.health_check_task = asyncio.create_task(self._health_check_loop())

        logger.info("Load balancer started successfully")

    async def stop(self):
        """Stop the load balancer"""
        self._shutdown = True

        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        if self.session:
            await self.session.close()

        logger.info("Load balancer stopped")

    def _select_worker(self) -> Optional[Worker]:
        """Select the best available worker using weighted random selection"""
        available_workers = [w for w in self.workers if w.is_available]

        if not available_workers:
            return None

        # Calculate weights based on worker metrics
        weights = []
        for worker in available_workers:
            weight = worker.weight
            weights.append(weight)

        # Weighted random selection with bias for less-loaded workers
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(available_workers)

        rand_val = random.uniform(0, total_weight)
        current_weight = 0

        for worker, weight in zip(available_workers, weights):
            current_weight += weight
            if rand_val <= current_weight:
                return worker

        return available_workers[-1]

    async def _health_check_loop(self):
        """Periodically check worker health"""
        while not self._shutdown:
            try:
                await asyncio.gather(
                    *[self._check_worker_health(worker) for worker in self.workers],
                    return_exceptions=True,
                )
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(5)

    async def _check_worker_health(self, worker: Worker):
        """Check if a worker is healthy"""
        try:
            if not self.session:
                return

            start_time = time.time()
            timeout = aiohttp.ClientTimeout(total=5)
            async with self.session.get(worker.health_endpoint, timeout=timeout) as response:
                response_time = time.time() - start_time
                worker.last_health_check = time.time()

                if response.status == 200:
                    worker.is_healthy = True
                    worker.update_response_time(response_time)
                else:
                    worker.is_healthy = False
                    logger.warning(f"Worker {worker.id} unhealthy: HTTP {response.status}")

        except asyncio.TimeoutError:
            worker.is_healthy = False
            logger.warning(f"Worker {worker.id} health check timeout")
        except Exception as e:
            worker.is_healthy = False
            logger.warning(f"Worker {worker.id} health check failed: {e}")

    async def _make_request(self, worker: Worker, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make a request to a specific worker"""
        worker.current_requests += 1

        try:
            start_time = time.time()

            # Prepare payload based on worker type
            if worker.worker_type == WorkerType.OLLAMA:
                payload = {
                    "model": worker.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": kwargs.get("temperature", 0.7),
                        "num_predict": kwargs.get("max_tokens", 512),
                        "top_p": kwargs.get("top_p", 0.9),
                        "top_k": kwargs.get("top_k", 40),
                        "repeat_penalty": kwargs.get("repeat_penalty", 1.1),
                    },
                }
                if kwargs.get("stop"):
                    payload["options"]["stop"] = kwargs["stop"]
            elif worker.worker_type == WorkerType.LM_STUDIO:
                # Convert repeat_penalty to frequency_penalty (range [0, 2])
                # repeat_penalty typically ranges from 0.0 to 2.0, with 1.0 being neutral
                # frequency_penalty for LM Studio expects positive values [0, 2.0]
                repeat_penalty = kwargs.get("repeat_penalty", 1.1)
                frequency_penalty = max(0.0, min(2.0, repeat_penalty - 1.0))
                
                payload = {
                    "model": worker.model,
                    "prompt": prompt,
                    "max_tokens": kwargs.get("max_tokens", 512),
                    "temperature": kwargs.get("temperature", 0.7),
                    "top_p": kwargs.get("top_p", 0.9),
                    "frequency_penalty": frequency_penalty,
                    "stop": kwargs.get("stop"),
                    "stream": False,
                }
            else:  # EXO - ChatGPT-compatible format
                messages = []
                system_prompt = kwargs.get("system_prompt", "")
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                payload = {
                    "model": worker.model,
                    "messages": messages,
                    "max_tokens": kwargs.get("max_tokens", 512),
                    "temperature": kwargs.get("temperature", 0.7),
                    "top_p": kwargs.get("top_p", 0.9),
                    "frequency_penalty": kwargs.get("frequency_penalty", 0.0),
                    "presence_penalty": kwargs.get("presence_penalty", 0.0),
                    "stop": kwargs.get("stop"),
                    "stream": False,
                }

            async with self.session.post(worker.api_endpoint, json=payload) as response:
                response_time = time.time() - start_time

                if response.status == 200:
                    result = await response.json()
                    worker.update_response_time(response_time)
                    worker.record_success()

                    # Update metrics
                    if self.config.enable_metrics:
                        self.metrics["response_times"].append(response_time)
                        self.metrics["successful_requests"] += 1

                    return result
                else:
                    error_text = await response.text()
                    worker.record_failure()
                    self.metrics["failed_requests"] += 1
                    raise Exception(f"HTTP {response.status}: {error_text}")

        except asyncio.TimeoutError:
            worker.record_failure()
            self.metrics["failed_requests"] += 1
            raise  # Preserve original TimeoutError type and context
        except Exception as e:
            worker.record_failure()
            self.metrics["failed_requests"] += 1
            raise  # Preserve original exception type and context
        finally:
            worker.current_requests -= 1
            self.metrics["total_requests"] += 1

    async def process_request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Process a single request with retries"""
        last_error = None

        for attempt in range(self.config.max_retries + 1):
            worker = self._select_worker()

            if not worker:
                if attempt == self.config.max_retries:
                    raise Exception("No available workers")
                await asyncio.sleep(0.5 * (attempt + 1))
                continue

            try:
                logger.debug(f"Sending request to {worker.id} (attempt {attempt + 1})")
                result = await self._make_request(worker, prompt, **kwargs)
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Request to worker {worker.id} failed (attempt {attempt + 1}): {e}")

                if attempt == self.config.max_retries:
                    break

                # Exponential backoff
                await asyncio.sleep(0.5 * (2**attempt))

        raise Exception(
            f"Request failed after {self.config.max_retries + 1} attempts. Last error: {last_error}"
        )

    async def process_batch(self, prompts: List[str], **kwargs) -> List[Dict[str, Any]]:
        """Process a batch of requests concurrently"""
        max_concurrent = kwargs.pop("max_concurrent", self.config.max_concurrent_batch)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_single(prompt: str, index: int) -> Dict[str, Any]:
            async with semaphore:
                try:
                    result = await self.process_request(prompt, **kwargs)
                    return {"index": index, "success": True, "result": result}
                except Exception as e:
                    return {"index": index, "success": False, "error": str(e)}

        tasks = [process_single(prompt, i) for i, prompt in enumerate(prompts)]
        results = await asyncio.gather(*tasks)

        # Sort by original index
        results.sort(key=lambda x: x["index"])
        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        uptime = time.time() - self.metrics["start_time"]

        # Calculate average response time
        if self.metrics["response_times"]:
            avg_response_time = sum(self.metrics["response_times"]) / len(
                self.metrics["response_times"]
            )
        else:
            avg_response_time = 0.0

        # Calculate requests per second
        rps = self.metrics["total_requests"] / uptime if uptime > 0 else 0

        # Calculate success rate
        if self.metrics["total_requests"] > 0:
            success_rate = (
                self.metrics["successful_requests"] / self.metrics["total_requests"]
            ) * 100
        else:
            success_rate = 0.0

        return {
            "uptime_seconds": uptime,
            "requests": {
                "total": self.metrics["total_requests"],
                "successful": self.metrics["successful_requests"],
                "failed": self.metrics["failed_requests"],
                "success_rate_percent": success_rate,
                "requests_per_second": rps,
            },
            "performance": {
                "average_response_time": avg_response_time,
                "min_response_time": min(self.metrics["response_times"])
                if self.metrics["response_times"]
                else 0,
                "max_response_time": max(self.metrics["response_times"])
                if self.metrics["response_times"]
                else 0,
            },
            "workers": [worker.to_dict() for worker in self.workers],
            "load_balancer_config": {
                "health_check_interval": self.config.health_check_interval,
                "request_timeout": self.config.request_timeout,
                "max_retries": self.config.max_retries,
                "max_concurrent_batch": self.config.max_concurrent_batch,
            },
        }

    def print_status(self):
        """Print current status of all workers"""
        print("\n" + "=" * 80)
        print("DISTRIBUTED LLM LOAD BALANCER STATUS")
        print("=" * 80)

        metrics = self.get_metrics()
        print("\nRequest Metrics:")
        print(f"  Total Requests: {metrics['requests']['total']}")
        print(f"  Success Rate: {metrics['requests']['success_rate_percent']:.1f}%")
        print(f"  Requests/sec: {metrics['requests']['requests_per_second']:.2f}")
        print(f"  Avg Response Time: {metrics['performance']['average_response_time']:.2f}s")

        print(f"\nWorkers ({len(self.workers)} total):")
        print("-" * 80)
        print(
            f"{'ID':<20} {'HOST':<15} {'PORT':<6} {'TYPE':<11} {'LOAD':<6} {'HEALTH':<8} {'RESP_TIME':<10}"
        )
        print("-" * 80)

        for worker in self.workers:
            health = "✓" if worker.is_healthy else "✗"
            load_pct = f"{worker.load_percentage:.0f}%"
            resp_time = (
                f"{worker.average_response_time:.2f}s"
                if worker.average_response_time > 0
                else "N/A"
            )

            print(
                f"{worker.id:<20} {worker.host:<15} {worker.port:<6} "
                f"{worker.worker_type.value:<11} {load_pct:<6} {health:<8} {resp_time:<10}"
            )

        print("=" * 80 + "\n")
