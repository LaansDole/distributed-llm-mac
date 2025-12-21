"""
Worker node abstraction for Ollama, LM Studio, and Exo clusters
"""

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict


class WorkerType(Enum):
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    EXO = "exo"


@dataclass
class Worker:
    """Represents a worker node (Ollama, LM Studio, or Exo cluster instance)"""

    id: str
    host: str
    port: int
    worker_type: WorkerType
    model: str
    max_concurrent_requests: int = 5
    current_requests: int = 0
    is_healthy: bool = True
    last_health_check: float = field(default_factory=time.time)
    response_times: Deque[float] = field(default_factory=lambda: deque(maxlen=10))
    total_requests: int = 0
    failed_requests: int = 0
    last_used: float = field(default_factory=time.time)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def api_endpoint(self) -> str:
        if self.worker_type == WorkerType.OLLAMA:
            return f"{self.base_url}/api/generate"
        elif self.worker_type == WorkerType.LM_STUDIO:
            return f"{self.base_url}/v1/completions"
        else:  # EXO
            return f"{self.base_url}/v1/chat/completions"

    @property
    def health_endpoint(self) -> str:
        if self.worker_type == WorkerType.OLLAMA:
            return f"{self.base_url}/api/tags"
        else:  # LM Studio or EXO
            return f"{self.base_url}/v1/models"

    @property
    def is_chat_format(self) -> bool:
        """Check if worker uses ChatGPT-compatible messages format"""
        return self.worker_type == WorkerType.EXO

    @property
    def is_available(self) -> bool:
        """Check if worker is available for new requests"""
        return self.is_healthy and self.current_requests < self.max_concurrent_requests

    @property
    def load_percentage(self) -> float:
        """Get current load as percentage"""
        return (self.current_requests / self.max_concurrent_requests) * 100

    @property
    def average_response_time(self) -> float:
        """Calculate average response time"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 1.0
        return (self.total_requests - self.failed_requests) / self.total_requests

    @property
    def weight(self) -> float:
        """Calculate worker weight for load balancing"""
        # Based on availability, response time, and success rate
        if not self.is_available:
            return 0.0

        # Availability weight (inverse of current load)
        availability_weight = (
            self.max_concurrent_requests - self.current_requests
        ) / self.max_concurrent_requests

        # Response time weight (normalized to avoid extreme values)
        if self.average_response_time > 0:
            # Normalize response times: fastest gets weight 1.0, slowest gets weight 0.3
            # This prevents extreme weight variations
            response_time_weight = max(0.3, 1.0 / (1.0 + self.average_response_time))
        else:
            response_time_weight = 0.8  # Neutral weight for new workers

        # Success rate weight
        success_rate_weight = self.success_rate

        # Combined weight with emphasis on availability and success rate
        # Reduced response time impact to prevent oscillation
        return availability_weight * 0.5 + success_rate_weight * 0.4 + response_time_weight * 0.1

    def update_response_time(self, response_time: float):
        """Update response time history"""
        self.response_times.append(response_time)
        self.last_used = time.time()

    def record_success(self):
        """Record a successful request"""
        self.total_requests += 1

    def record_failure(self):
        """Record a failed request"""
        self.total_requests += 1
        self.failed_requests += 1

    def to_dict(self) -> Dict:
        """Convert worker to dictionary"""
        return {
            "id": self.id,
            "host": self.host,
            "port": self.port,
            "type": self.worker_type.value,
            "model": self.model,
            "is_healthy": self.is_healthy,
            "is_available": self.is_available,
            "current_requests": self.current_requests,
            "max_concurrent_requests": self.max_concurrent_requests,
            "load_percentage": self.load_percentage,
            "average_response_time": self.average_response_time,
            "success_rate": self.success_rate,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "last_used": self.last_used,
            "last_health_check": self.last_health_check,
        }

    def __str__(self) -> str:
        """String representation"""
        status = "✓" if self.is_healthy else "✗"
        return f"{self.id} ({status}) {self.host}:{self.port} - {self.load_percentage:.0f}% load"

    @classmethod
    def from_dict(cls, data: Dict) -> "Worker":
        """Create worker from dictionary"""
        return cls(
            id=data["id"],
            host=data["host"],
            port=data["port"],
            worker_type=WorkerType(data["type"]),
            model=data["model"],
            max_concurrent_requests=data.get("max_concurrent_requests", 5),
        )
