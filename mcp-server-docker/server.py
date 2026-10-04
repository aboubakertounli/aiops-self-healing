"""MCP server 1: Docker on the worker that mounts /var/run/docker.sock."""

import json
import os
from collections import defaultdict, deque

import docker
from fastmcp import FastMCP

from shared.forecast import minutes_to_limit

mcp = FastMCP("docker-ops")
STATS: dict[str, deque] = defaultdict(lambda: deque(maxlen=30))
INTERVAL_SECONDS = int(os.environ.get("STATS_INTERVAL_SECONDS", "60"))


def client() -> docker.DockerClient:
    return docker.DockerClient(base_url=os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock"))


def _summary(container) -> dict:
    return {
        "id": container.short_id,
        "name": container.name,
        "image": container.image.tags[0] if container.image.tags else container.image.short_id,
        "status": container.status,
    }


@mcp.tool()
def list_containers() -> str:
    """List containers on this Docker host: id, name, image, status."""
    with client() as docker_client:
        rows = [_summary(container) | {"node": os.environ.get("NODE_NAME", "local")} for container in docker_client.containers.list(all=True)]
    return json.dumps(rows)


@mcp.tool()
def get_container_stats(container_id: str) -> str:
    """Live CPU percent and memory usage for one container. Also stores the sample."""
    with client() as docker_client:
        container = docker_client.containers.get(container_id)
        stats = container.stats(stream=False)
    cpu = _cpu_percent(stats)
    memory = stats.get("memory_stats", {})
    used = memory.get("usage", 0)
    limit = memory.get("limit", 0)
    STATS[container_id].append(used)
    return json.dumps(
        {
            "container": container_id,
            "cpu_percent": round(cpu, 1),
            "memory_bytes": used,
            "memory_limit_bytes": limit,
            "memory_percent": round(100 * used / limit, 1) if limit else None,
            "samples_kept": len(STATS[container_id]),
        }
    )


@mcp.tool()
def get_container_logs(container_id: str, tail: int = 100) -> str:
    """Last log lines from one container."""
    with client() as docker_client:
        container = docker_client.containers.get(container_id)
        logs = container.logs(tail=tail).decode("utf-8", errors="replace")
    return logs


@mcp.tool()
def predict_container_anomaly(container_id: str) -> str:
    """Estimate minutes until this container's memory reaches its limit."""
    with client() as docker_client:
        container = docker_client.containers.get(container_id)
        stats = container.stats(stream=False)
    limit = stats.get("memory_stats", {}).get("limit", 0)
    samples = list(STATS[container_id])
    minutes = minutes_to_limit(samples, limit, INTERVAL_SECONDS)
    return json.dumps(
        {
            "container": container_id,
            "samples": len(samples),
            "memory_limit_bytes": limit,
            "minutes_to_limit": minutes,
            "will_breach": minutes is not None,
        }
    )


@mcp.tool()
def restart_container(container_id: str) -> str:
    """Restart one container. This is the only change this server can make."""
    with client() as docker_client:
        container = docker_client.containers.get(container_id)
        container.restart(timeout=15)
        container.reload()
    return json.dumps({"container": container.name, "status": container.status, "restarted": True})


@mcp.tool()
def collect_diagnostics(container_id: str) -> str:
    """Logs, current stats, and the memory forecast in one report."""
    return json.dumps(
        {
            "stats": json.loads(get_container_stats(container_id)),
            "forecast": json.loads(predict_container_anomaly(container_id)),
            "logs": get_container_logs(container_id, tail=50),
        }
    )


def _cpu_percent(stats: dict) -> float:
    cpu = stats.get("cpu_stats", {})
    previous = stats.get("precpu_stats", {})
    cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - previous.get("cpu_usage", {}).get("total_usage", 0)
    system_delta = cpu.get("system_cpu_usage", 0) - previous.get("system_cpu_usage", 0)
    online = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage") or []) or 1
    if system_delta <= 0 or cpu_delta <= 0:
        return 0.0
    return (cpu_delta / system_delta) * online * 100.0


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
