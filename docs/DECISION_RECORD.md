# Architectural Decision Record

This document records key architectural and design decisions made during the development of the distributed LLM system.

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Architectural Decisions](#core-architectural-decisions)
3. [Technology Stack Decisions](#technology-stack-decisions)
4. [Implementation Patterns](#implementation-patterns)
5. [Performance and Scalability](#performance-and-scalability)
6. [Error Handling and Resilience](#error-handling-and-resilience)
7. [Configuration and Extensibility](#configuration-and-extensibility)

## System Overview

The distributed LLM system is designed to process research papers and text documents across multiple Mac computers running local LLM inference servers (LM Studio or Ollama). The architecture follows a master-worker pattern where a central load balancer distributes requests to available workers.

## Core Architectural Decisions

### 1. Master-Worker Architecture

**Decision**: Adopted a centralized load balancer with distributed worker nodes.

**Rationale**:
- Simplifies coordination and request routing
- Enables centralized metrics collection and monitoring
- Provides a single point of configuration management
- Allows for dynamic load balancing across heterogeneous hardware

**Alternatives Considered**:
- Peer-to-peer architecture: Rejected due to complexity in coordination
- Message queue-based system: Rejected as overkill for local network use case

### 2. Async/Await Concurrency Model

**Decision**: Used Python's asyncio with aiohttp for all network operations.

**Rationale**:
- High concurrency with minimal thread overhead
- Native support for network I/O operations
- Efficient resource utilization for I/O-bound tasks
- Clean, readable code structure

**Implementation**: `LoadBalancer` class uses async context managers for session management and implements concurrent request processing with semaphores.

### 3. Worker Abstraction Layer

**Decision**: Created a unified `Worker` class that abstracts differences between Ollama and LM Studio.

**Rationale**:
- API compatibility between different LLM servers
- Simplified load balancer implementation
- Easy addition of new worker types in the future
- Consistent metrics and health checking

**Key Features**:
- Standardized API endpoints (`api_endpoint`, `health_endpoint`)
- Unified request payload formatting
- Worker-specific weight calculation for load balancing

## Technology Stack Decisions

### 4. HTTP REST APIs

**Decision**: Used HTTP REST for all worker communication.

**Rationale**:
- Universal compatibility with Ollama and LM Studio
- Simple debugging and monitoring
- Firewall-friendly for local networks
- Language-agnostic communication

**Endpoints**:
- Ollama: `/api/generate`, `/api/tags`
- LM Studio: `/v1/completions`, `/v1/models`

### 5. JSON Configuration

**Decision**: Used JSON files for worker and system configuration.

**Rationale**:
- Human-readable and editable
- Easy integration with other tools
- Version control friendly
- Supports nested configurations

**Configuration Structure**:
```json
{
  "workers": [
    {
      "id": "unique-identifier",
      "host": "ip-address",
      "port": 1234,
      "type": "lm_studio|ollama",
      "model": "model-name",
      "max_concurrent_requests": 5
    }
  ]
}
```

### 6. Python Packaging with uv

**Decision**: Adopted uv as the package manager.

**Rationale**:
- Faster dependency resolution than pip
- Better caching and performance
- Modern Python packaging standards
- Consistent development environment

## Implementation Patterns

### 7. Weighted Load Balancing Algorithm

**Decision**: Implemented weighted random selection based on worker metrics.

**Algorithm**:
```python
weight = availability_weight * 0.4 + success_rate_weight * 0.4 + response_time_weight * 0.2
```

**Factors Considered**:
- Current load (availability)
- Historical success rate
- Average response time

**Rationale**:
- Avoids overloaded workers
- Preferentially uses faster, more reliable workers
- Provides probabilistic distribution
- Self-adapting to performance changes

### 8. Health Checking System

**Decision**: Implemented periodic health checks with configurable intervals.

**Features**:
- Asynchronous health checks for all workers
- Configurable timeout (5 seconds)
- Automatic worker disablement on failure
- Response time tracking for load balancing

**Health Check Endpoints**:
- Ollama: `/api/tags` (lists available models)
- LM Studio: `/v1/models` (lists available models)

### 9. Request Retry Mechanism

**Decision**: Implemented exponential backoff retry with configurable maximum attempts.

**Implementation**:
- Default 3 retries per request
- Exponential backoff: `0.5 * (2 ** attempt)`
- Worker selection on each retry
- Request timeout protection

## Performance and Scalability

### 10. Connection Pooling

**Decision**: Used aiohttp connection pooling with configurable limits.

**Configuration**:
- `limit_per_host`: 100 connections per worker
- `ttl_dns_cache`: 300 seconds
- `keepalive_timeout`: 30 seconds
- Connection cleanup on close

**Rationale**:
- Reduces connection overhead
- Improves request throughput
- Maintains connection efficiency

### 11. Batch Processing with Concurrency Control

**Decision**: Implemented batch processing with semaphore-based concurrency control.

**Features**:
- Configurable `max_concurrent_batch` (default: 50)
- Progress tracking and ETA calculation
- Result ordering preservation
- Memory-efficient processing

**Implementation**:
```python
async def process_batch(self, prompts: List[str], **kwargs):
    max_concurrent = kwargs.pop('max_concurrent', self.config.max_concurrent_batch)
    semaphore = asyncio.Semaphore(max_concurrent)
    # Process with controlled concurrency
```

### 12. Metrics Collection

**Decision**: Implemented comprehensive metrics collection with configurable enablement.

**Metrics Tracked**:
- Total requests (successful/failed)
- Response times (min/max/avg)
- Success rate percentage
- Requests per second
- Worker-specific statistics

**Implementation**: Uses deque with maxlen for memory-efficient rolling metrics.

## Error Handling and Resilience

### 13. Graceful Degradation

**Decision**: System continues operating with subset of healthy workers.

**Behavior**:
- Unhealthy workers automatically removed from rotation
- Failed requests retried on other workers
- System functions with single healthy worker
- Health checks attempt recovery of failed workers

### 14. Timeout Protection

**Decision**: Multi-level timeout protection throughout the system.

**Timeouts**:
- Health check: 5 seconds
- Request timeout: 300 seconds (configurable)
- Connection timeout: 10 seconds
- Socket read timeout: 60 seconds

### 15. Circuit Breaking Pattern

**Decision**: Workers marked unhealthy after consecutive failures.

**Implementation**:
- Health checks determine worker status
- Failed workers excluded from selection
- Automatic recovery through periodic health checks
- No manual intervention required

## Configuration and Extensibility

### 16. Environment Variable Overrides

**Decision**: Configuration supports both file-based and environment variable overrides.

**Supported Variables**:
- `HEALTH_CHECK_INTERVAL`
- `REQUEST_TIMEOUT`
- `MAX_RETRIES`
- `MAX_CONCURRENT_BATCH`
- `LOG_LEVEL`
- `ENABLE_METRICS`

### 17. Pluggable Architecture

**Decision**: Designed system for easy extension of worker types and features.

**Extension Points**:
- New worker types via `WorkerType` enum
- Custom load balancing algorithms
- Additional metrics collection
- New request parameter handling

### 18. Preset System for Common Use Cases

**Decision**: Implemented preset configurations for research workflows.

**Built-in Presets**:
- `research`: 5 prompts for academic paper analysis
- `summary`: 3 prompts for document summarization
- `analysis`: 3 prompts for critical evaluation

## Security Considerations

### 19. Local Network Focus

**Decision**: Designed for trusted local network environments.

**Assumptions**:
- Workers on same local network
- No authentication required between nodes
- Firewall configured to allow worker ports
- No encryption for local communication

## Conclusion

These architectural decisions have resulted in a system that:

- **Simplicity**: Easy to understand and modify
- **Reliability**: Graceful failure handling and recovery
- **Performance**: Efficient resource utilization
- **Extensibility**: Clear extension points for new features
- **Maintainability**: Clean separation of concerns

The design prioritizes the target use case (research paper processing on Mac networks) while maintaining flexibility for future enhancements.