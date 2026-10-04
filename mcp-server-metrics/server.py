"""MCP server 2: Prometheus history, forecasts, and anomaly checks."""

import json
import os
import time

import requests
from fastmcp import FastMCP

from shared.forecast import linear_forecast

mcp = FastMCP("metrics")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://kube-prometheus-stack-prometheus.monitoring.svc:9090")


def _query(promql: str) -> list:
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": promql},
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("data", {}).get("result", [])


def _query_range(promql: str, seconds: int, step: str) -> list:
    end = time.time()
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        params={"query": promql, "start": end - seconds, "end": end, "step": step},
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("data", {}).get("result", [])


def _range_seconds(range_expr: str) -> int:
    unit = range_expr[-1]
    count = int(range_expr[:-1])
    return count * {"m": 60, "h": 3600}.get(unit, 60)


@mcp.tool()
def get_realtime_metrics(pod: str) -> str:
    """Current CPU rate and memory bytes for a pod, from Prometheus."""
    cpu = _query(f'sum(rate(container_cpu_usage_seconds_total{{pod="{pod}"}}[5m]))')
    memory = _query(f'sum(container_memory_usage_bytes{{pod="{pod}"}})')
    return json.dumps({"pod": pod, "cpu": _first_value(cpu), "memory_bytes": _first_value(memory)})


@mcp.tool()
def get_historical_metrics(pod: str, range_expr: str = "1h", step: str = "1m") -> str:
    """Memory samples for a pod over a Prometheus range such as 1h."""
    series = _query_range(
        f'sum(container_memory_usage_bytes{{pod="{pod}"}})',
        _range_seconds(range_expr),
        step,
    )
    values = []
    if series:
        values = [float(point[1]) for point in series[0].get("values", [])]
    return json.dumps({"pod": pod, "points": len(values), "memory_bytes": values[-20:]})


@mcp.tool()
def predict_container_state(pod: str, steps_ahead: int = 30) -> str:
    """Forecast memory one sample at a time. steps_ahead uses the 1m history."""
    history = json.loads(get_historical_metrics(pod, "1h", "1m"))
    samples = history["memory_bytes"]
    projected = linear_forecast(samples, steps_ahead)
    return json.dumps(
        {
            "pod": pod,
            "samples": len(samples),
            "steps_ahead": steps_ahead,
            "projected_memory_bytes": projected,
        }
    )


@mcp.tool()
def detect_anomalies(pod: str) -> str:
    """Flag the latest memory point when it sits more than 3 standard deviations above the mean."""
    history = json.loads(get_historical_metrics(pod, "1h", "1m"))
    samples = history["memory_bytes"]
    if len(samples) < 5:
        return json.dumps({"pod": pod, "anomaly": False, "reason": "not enough samples"})
    mean = sum(samples) / len(samples)
    variance = sum((value - mean) ** 2 for value in samples) / len(samples)
    deviation = variance ** 0.5
    latest = samples[-1]
    z_score = (latest - mean) / deviation if deviation else 0
    return json.dumps(
        {
            "pod": pod,
            "latest": latest,
            "mean": round(mean, 1),
            "z_score": round(z_score, 2),
            "anomaly": z_score > 3,
        }
    )


def _first_value(result: list):
    if not result:
        return None
    return result[0].get("value", [None, None])[1]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8002"))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
