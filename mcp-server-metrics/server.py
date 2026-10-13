"""MCP server: Prometheus reads and PromQL forecasts."""

import json
import os
import time

import requests
from fastmcp import FastMCP

from queries import cpu_query, limit_query, memory_query, predict_query

mcp = FastMCP("metrics")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://127.0.0.1:30090")


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
    """Current CPU rate, working-set memory, limit, and percent for one pod, from Prometheus."""
    cpu = _query(cpu_query(pod))
    memory = _query(memory_query(pod))
    limit = _query(limit_query(pod))
    used = _as_float(_first_value(memory))
    limit_bytes = _as_float(_first_value(limit))
    percent = round(100 * used / limit_bytes, 1) if used is not None and limit_bytes else None
    return json.dumps(
        {
            "pod": pod,
            "cpu": _first_value(cpu),
            "memory_bytes": used,
            "memory_limit_bytes": limit_bytes,
            "memory_percent": percent,
        }
    )


@mcp.tool()
def get_historical_metrics(pod: str, range_expr: str = "1h", step: str = "1m") -> str:
    """Working-set memory samples for a pod over a Prometheus range such as 1h."""
    series = _query_range(memory_query(pod), _range_seconds(range_expr), step)
    values = []
    if series:
        values = [float(point[1]) for point in series[0].get("values", [])]
    return json.dumps({"pod": pod, "points": len(values), "memory_bytes": values[-20:]})


@mcp.tool()
def predict_container_state(pod: str, seconds_ahead: int = 1800) -> str:
    """Prometheus predict_linear of working-set memory, seconds_ahead from now."""
    projected = _as_float(_first_value(_query(predict_query(pod, seconds_ahead))))
    return json.dumps(
        {
            "pod": pod,
            "seconds_ahead": seconds_ahead,
            "projected_memory_bytes": projected,
            "promql": predict_query(pod, seconds_ahead),
        }
    )


@mcp.tool()
def predict_memory_breach(pod: str) -> str:
    """Whether predict_linear of working-set memory crosses the limit within one hour."""
    limit = _as_float(_first_value(_query(limit_query(pod))))
    projected = _as_float(_first_value(_query(predict_query(pod, 3600))))
    will_breach = (
        projected is not None and limit is not None and projected >= limit
    )
    return json.dumps(
        {
            "pod": pod,
            "memory_limit_bytes": limit,
            "projected_memory_bytes_1h": projected,
            "will_breach": will_breach,
            "promql": predict_query(pod, 3600),
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


def _as_float(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8002"))
    mcp.run(transport="http", host="0.0.0.0", port=port, path="/mcp")
