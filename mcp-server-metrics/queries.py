"""PromQL fragments used by the metrics MCP server."""

CONTAINERS = 'container!="",container!="POD"'
MEMORY = "container_memory_working_set_bytes"


def memory_query(pod: str) -> str:
    return f'sum({MEMORY}{{pod="{pod}",{CONTAINERS}}})'


def limit_query(pod: str) -> str:
    return f'max(container_spec_memory_limit_bytes{{pod="{pod}",{CONTAINERS}}})'


def cpu_query(pod: str) -> str:
    return f'sum(rate(container_cpu_usage_seconds_total{{pod="{pod}",{CONTAINERS}}}[5m]))'


def predict_query(pod: str, seconds_ahead: int) -> str:
    return f"predict_linear({memory_query(pod)}[30m], {int(seconds_ahead)})"
