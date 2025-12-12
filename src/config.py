"""
Configuration settings for the distributed LLM system
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class LoadBalancerConfig:
    """Load balancer configuration"""
    health_check_interval: int = 30
    request_timeout: int = 300
    max_retries: int = 3
    max_concurrent_batch: int = 50
    connection_pool_size: int = 100
    dns_cache_ttl: int = 300
    enable_metrics: bool = True
    log_level: str = "INFO"


@dataclass
class RequestConfig:
    """Request configuration"""
    temperature: float = 0.7
    max_tokens: int = 512
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    stop: Optional[List[str]] = None


DEFAULT_CONFIG = LoadBalancerConfig()
DEFAULT_REQUEST_CONFIG = RequestConfig()


def load_workers_config(config_path: str) -> List[Dict[str, Any]]:
    """Load worker configuration from JSON file"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Worker configuration file not found: {config_path}")

    with open(config_path, 'r') as f:
        config = json.load(f)

    if 'workers' not in config:
        raise ValueError("Configuration must contain 'workers' key")

    return config['workers']


def save_workers_config(workers: List[Dict[str, Any]], config_path: str):
    """Save worker configuration to JSON file"""
    config = {'workers': workers}

    # Create directory if it doesn't exist
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


def load_config(config_path: Optional[str] = None) -> LoadBalancerConfig:
    """Load load balancer configuration from JSON file"""
    if config_path is None:
        config_path = os.getenv('CONFIG_PATH', 'config/settings.json')

    if not os.path.exists(config_path):
        return DEFAULT_CONFIG

    with open(config_path, 'r') as f:
        config_data = json.load(f)

    return LoadBalancerConfig(**config_data)


def merge_request_configs(base: RequestConfig, override: Dict[str, Any]) -> RequestConfig:
    """Merge request configuration with override parameters"""
    base_dict = base.__dict__.copy()
    base_dict.update({k: v for k, v in override.items() if k in base_dict})
    return RequestConfig(**base_dict)


# Environment variable overrides
def get_config_from_env() -> LoadBalancerConfig:
    """Get configuration from environment variables"""
    return LoadBalancerConfig(
        health_check_interval=int(os.getenv('HEALTH_CHECK_INTERVAL', DEFAULT_CONFIG.health_check_interval)),
        request_timeout=int(os.getenv('REQUEST_TIMEOUT', DEFAULT_CONFIG.request_timeout)),
        max_retries=int(os.getenv('MAX_RETRIES', DEFAULT_CONFIG.max_retries)),
        max_concurrent_batch=int(os.getenv('MAX_CONCURRENT_BATCH', DEFAULT_CONFIG.max_concurrent_batch)),
        connection_pool_size=int(os.getenv('CONNECTION_POOL_SIZE', DEFAULT_CONFIG.connection_pool_size)),
        dns_cache_ttl=int(os.getenv('DNS_CACHE_TTL', DEFAULT_CONFIG.dns_cache_ttl)),
        enable_metrics=os.getenv('ENABLE_METRICS', str(DEFAULT_CONFIG.enable_metrics)).lower() == 'true',
        log_level=os.getenv('LOG_LEVEL', DEFAULT_CONFIG.log_level)
    )