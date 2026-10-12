"""MCP server for Kubernetes, OpenStack, and pod logs.

The only change it can make is deleting one pod. containerd and the
Deployment then start a new one. It does not create nodes or edit manifests.
"""

import json
import os

from fastmcp import FastMCP

mcp = FastMCP("infra")


def _kube():
    from kubernetes import client, config

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client


def _cloud():
    import openstack

    return openstack.connect()


@mcp.tool()
def get_cluster_status() -> str:
    """Node conditions and pod counts for the whole cluster."""
    client = _kube()
    core = client.CoreV1Api()
    nodes = []
    for node in core.list_node().items:
        conditions = {item.type: item.status for item in node.status.conditions or []}
        nodes.append({"name": node.metadata.name, "conditions": conditions})
    phases: dict[str, int] = {}
    for pod in core.list_pod_for_all_namespaces().items:
        phase = pod.status.phase or "Unknown"
        phases[phase] = phases.get(phase, 0) + 1
    return json.dumps({"nodes": nodes, "pods_by_phase": phases})


@mcp.tool()
def get_node_details(node_name: str) -> str:
    """Conditions, capacity, and allocatable resources for one node."""
    client = _kube()
    node = client.CoreV1Api().read_node(node_name)
    return json.dumps(
        {
            "name": node.metadata.name,
            "conditions": {item.type: item.status for item in node.status.conditions or []},
            "capacity": node.status.capacity,
            "allocatable": node.status.allocatable,
        }
    )


@mcp.tool()
def list_pods(namespace: str = "") -> str:
    """Pods with phase, node, and restart count. Empty namespace means all namespaces."""
    client = _kube()
    core = client.CoreV1Api()
    pods = (
        core.list_namespaced_pod(namespace)
        if namespace
        else core.list_pod_for_all_namespaces()
    )
    rows = []
    for pod in pods.items:
        restarts = sum((status.restart_count or 0) for status in pod.status.container_statuses or [])
        rows.append(
            {
                "namespace": pod.metadata.namespace,
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "node": pod.spec.node_name,
                "restarts": restarts,
            }
        )
    return json.dumps(rows)


@mcp.tool()
def get_pod_logs(namespace: str, pod: str, tail: int = 100) -> str:
    """Last log lines of a pod."""
    client = _kube()
    return client.CoreV1Api().read_namespaced_pod_log(pod, namespace, tail_lines=tail)


@mcp.tool()
def get_openstack_services_status() -> str:
    """Nova, Neutron, and the other OpenStack services as the controller reports them."""
    cloud = _cloud()
    services = []
    for service in cloud.compute.services():
        services.append(
            {
                "binary": service.binary,
                "host": service.host,
                "state": service.state,
                "status": service.status,
            }
        )
    return json.dumps(services)


@mcp.tool()
def list_instances() -> str:
    """OpenStack VMs: name, status, flavor, and the compute host."""
    cloud = _cloud()
    rows = []
    for server in cloud.compute.servers(details=True):
        rows.append(
            {
                "name": server.name,
                "status": server.status,
                "flavor": server.flavor.get("original_name") or server.flavor.get("id"),
                "host": server.get("hypervisor_hostname") or server.get("OS-EXT-SRV-ATTR:host"),
            }
        )
    return json.dumps(rows)


@mcp.tool()
def get_compute_node_metrics() -> str:
    """vCPU and memory on each hypervisor, so a full worker can be tied to its host."""
    cloud = _cloud()
    rows = []
    for hypervisor in cloud.compute.hypervisors(details=True):
        rows.append(
            {
                "hostname": hypervisor.name,
                "vcpus": hypervisor.vcpus,
                "vcpus_used": hypervisor.vcpus_used,
                "memory_mb": hypervisor.memory_size,
                "memory_mb_used": hypervisor.memory_used,
                "running_vms": hypervisor.running_vms,
            }
        )
    return json.dumps(rows)


@mcp.tool()
def search_logs(namespace: str, pod: str, keyword: str, tail: int = 200) -> str:
    """Lines from a pod log that contain the keyword."""
    logs = get_pod_logs(namespace, pod, tail)
    matched = [line for line in logs.splitlines() if keyword.lower() in line.lower()]
    return json.dumps({"matches": matched[-50:]})


@mcp.tool()
def correlate_events(namespace: str, pod: str) -> str:
    """Pod phase plus the warning events for that pod."""
    client = _kube()
    core = client.CoreV1Api()
    pod_obj = core.read_namespaced_pod(pod, namespace)
    events = core.list_namespaced_event(namespace, field_selector=f"involvedObject.name={pod}")
    warnings = [
        {"reason": event.reason, "message": event.message}
        for event in events.items
        if (event.type or "").lower() == "warning"
    ]
    return json.dumps(
        {
            "pod": pod,
            "phase": pod_obj.status.phase,
            "node": pod_obj.spec.node_name,
            "warnings": warnings,
        }
    )


@mcp.tool()
def collect_pod_diagnostics(namespace: str, pod: str) -> str:
    """Phase, node, warning events, and recent logs for one pod."""
    client = _kube()
    core = client.CoreV1Api()
    pod_obj = core.read_namespaced_pod(pod, namespace)
    events = core.list_namespaced_event(namespace, field_selector=f"involvedObject.name={pod}")
    warnings = [
        {"reason": event.reason, "message": event.message}
        for event in events.items
        if (event.type or "").lower() == "warning"
    ]
    return json.dumps(
        {
            "pod": pod,
            "namespace": namespace,
            "phase": pod_obj.status.phase,
            "node": pod_obj.spec.node_name,
            "warnings": warnings,
            "logs": get_pod_logs(namespace, pod, 50),
        }
    )


@mcp.tool()
def restart_pod(namespace: str, pod: str) -> str:
    """Delete one pod so its controller starts a replacement."""
    client = _kube()
    core = client.CoreV1Api()
    current = core.read_namespaced_pod(pod, namespace)
    owner = current.metadata.owner_references[0].kind if current.metadata.owner_references else None
    core.delete_namespaced_pod(pod, namespace)
    return json.dumps({"namespace": namespace, "pod": pod, "deleted": True, "owner": owner})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8003"))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
