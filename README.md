# AIOps self-healing platform

OpenStack (Kolla Ansible), a three-node kubeadm cluster, Flux, Prometheus, and a Spring agent that can restart one application pod. The agent and the two MCP servers run on a fourth Nova VM, next to the cluster, not inside it.

| VM | Role |
|---|---|
| `K8s-Master` | API server, scheduler, controller manager, etcd |
| `K8s-Worker1` | Application pods |
| `K8s-Worker2` | Application pods |
| `AIOps-Agent` | docker compose: metrics MCP, infra MCP, Spring console |

The only write the agent can make is `restart_pod`: delete one pod that has an owner controller. containerd starts the replacement. It does not edit manifests, scale nodes, or change OpenStack.

Alertmanager calls `POST /api/alerts` when working-set memory is near the limit or `predict_linear` says it will be within an hour. The chat at `http://<agent-vm>:8080` is for questions you type.

A smaller GitLab repo, [AIOps kind lab](https://gitlab.com/aboubakertounli/aiops-kind-lab), is the laptop demo (kind + a stressable site). This repo is the CentOS lab.

## Folders

| Folder | Role |
|---|---|
| `kolla/` | Kolla Ansible inventory and `globals.yml` |
| `ansible/` | `instances.yml` creates the four VMs; `site.yml` installs Kubernetes on the three K8s VMs |
| `gitops/` | Flux: namespaces, RBAC, kube-prometheus-stack, our PrometheusRules |
| `compose/` | Agent stack on `AIOps-Agent` |
| `mcp-server-metrics/` | PromQL, including `predict_linear` |
| `mcp-server-infra/` | Kubernetes and OpenStack reads, guarded `restart_pod` |
| `agent-backend/` | Spring Boot. `POST /api/chat` and `POST /api/alerts` |

## Deploy from the CentOS server

The CentOS Stream 9 machine is the KVM hypervisor. Do not install kubeadm on it.

1. Install KVM. Create management `10.0.0.0/24` and provider `172.16.99.0/24`.
2. Two Ubuntu 24.04 guests, two NICs each. Controller `10.0.0.11`, compute `10.0.0.31`. Leave the provider NIC without an IP. Enable nested virtualization on the compute guest.
3. Install OpenStack with Kolla (section below). Horizon and Keystone listen on VIP `10.0.0.10`. That VIP is on the management network; the laptop and the provider-LAN VMs cannot reach it until a later network change.
4. Create the four VMs:

   ```bash
   cd ansible
   ansible-galaxy collection install -r requirements.yml
   # export OS_* toward the Kolla VIP
   cp vars/instances.yml.example vars/instances.yml
   ansible-playbook -e @vars/instances.yml instances.yml
   ```

   Horizon is the fallback. Tag metadata `k8s_role=master`, `workers`, or `agent`.
5. Copy `ansible/inventory/hosts.yml.example` to `hosts.yml` and run `ansible-playbook -i inventory/hosts.yml site.yml`. That playbook never touches the agent VM.
6. Bootstrap Flux against this GitLab repo:

   ```bash
   flux bootstrap gitlab \
     --hostname=gitlab.com \
     --owner=aboubakertounli \
     --repository=aiops-self-healing-agent \
     --branch=main \
     --path=gitops \
     --personal \
     --token-auth
   ```

7. Replace `AGENT_VM_IP` in `gitops/monitoring.yaml` with the address Nova gave `AIOps-Agent`. Copy a kubeconfig for ServiceAccount `mcp-infra` onto that VM (`secret/mcp-infra-token` in namespace `aiops`). Set `PROMETHEUS_URL=http://<worker>:30090` in `compose/.env`.
8. On `AIOps-Agent`, build or pull the three images and run `docker compose -f compose/docker-compose.yml up -d`. Open `http://<agent-vm>:8080`.

Grafana: `http://<any-node>:30000` (user `admin`, password `admin`). Prometheus: `http://<any-node>:30090`.

## Kolla

Two Ubuntu 24.04 nodes, each with two NICs. The management NIC keeps its address. The provider NIC has no address; Kolla attaches it to `br-ex`. Kolla 2025.1 uses Open vSwitch, not OVN. `kolla_internal_vip_address` is still required even with a single controller.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r kolla/requirements.txt
sudo mkdir -p /etc/kolla
sudo cp kolla/globals.yml /etc/kolla/globals.yml
sudo chown -R "$USER" /etc/kolla
kolla-genpwd
kolla-ansible bootstrap-servers -i kolla/inventory/multinode
kolla-ansible prechecks -i kolla/inventory/multinode
kolla-ansible deploy -i kolla/inventory/multinode
kolla-ansible post-deploy -i kolla/inventory/multinode
PROVIDER_GATEWAY=172.16.99.1 bash kolla/init-provider-network.sh
```

`kolla-genpwd` writes `/etc/kolla/passwords.yml`. That file stays off git.

Kolla Prometheus exporters (node, libvirt, openstack-exporter) are a later change. They are not Fluent Bit. Fluent Bit is not in this repo: the agent reads live pod logs through the Kubernetes API.

## Ansible

`instances.yml` uses `openstack.cloud` modules: keypair, security group, four servers. `site.yml` installs containerd, kubeadm 1.32, Flannel (`10.244.0.0/16`).

`inventory/openstack.yml` is the dynamic inventory (`plugin: openstack.cloud.openstack`). `expand_hostvars` is off because it queries Cinder, which this Kolla cloud does not install. Groups match metadata `k8s_role`.

## GitOps

Flux applies `gitops/`. The cluster holds collectors and RBAC only:

- `namespace.yaml` — `aiops`, `monitoring`, ServiceAccount `mcp-infra`, a token Secret, ClusterRole that can get/list pods and delete pods
- `monitoring.yaml` — kube-prometheus-stack, NodePorts 30090 / 30000, Alertmanager webhook
- `alerts.yaml` — `MemoryBreachSoon` (`predict_linear` of `container_memory_working_set_bytes`) and `MemoryNearLimit`

The agent Deployments are not here. They run in `compose/`.

## Agent VM

`compose/docker-compose.yml` starts the two MCP servers (Streamable HTTP at `/mcp`) and the Spring app (Spring AI 1.1). `restart_pod` refuses `kube-system`, pods with no owner, namespaces outside `RESTART_NAMESPACES` when that list is set, and a second delete of the same pod during `RESTART_COOLDOWN_SECONDS` (default 300). Each accepted delete writes one log line.

Ollama on the CentOS GPU: set `OPENAI_BASE_URL=http://<centos>:11434`, `OPENAI_API_KEY=ollama`, and a tool-capable model such as `qwen2.5:7b`.

## What is not in this repo

Train Ticket is later. The kind/laptop demo is the other GitLab project. There is no Loki and no Fluent Bit. OpenStack host metrics from Kolla exporters come later.

`.gitlab-ci.yml` runs `tests/` then builds and pushes the three images to the GitLab registry.
