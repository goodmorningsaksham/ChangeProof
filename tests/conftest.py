import pytest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def sample_experiment_spec() -> dict:
    return {
        "id": "exp-test-01",
        "version": "1.0",
        "description": "Test experiment specification",
        "target": {
            "compose_file": "docker-compose.yml",
            "git_commit": "HEAD",
        },
        "fault": {
            "tool": "toxiproxy",
            "proxy": "payment-proxy",
            "toxic": {
                "type": "latency",
                "attributes": {
                    "latency": 2000,
                    "jitter": 100,
                },
            },
        },
        "workload": {
            "tool": "k6",
            "script": "workloads/checkout_load.js",
            "vus": 10,
            "duration": "10s",
            "rps_target": 20,
        },
        "measurements": {
            "prometheus_url": "http://localhost:9090",
            "scrape_interval_s": 1,
            "metrics": [
                {"name": "retry_count_total", "labels": {"service": "checkout"}},
                {"name": "http_errors_total", "labels": {"service": "checkout"}},
            ],
        },
        "assertions": {
            "pre_patch": [
                {"metric": "retry_count_total", "condition": "rate_per_min > 50", "description": "Retry storm visible"},
            ],
            "post_patch": [
                {"metric": "retry_count_total", "condition": "rate_per_min < 20", "description": "Retries bounded"},
            ],
        },
    }
