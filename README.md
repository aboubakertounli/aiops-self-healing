# AIOps self-healing platform

The code for the agent, the three MCP servers, the Ansible bootstrap, and the manifests Flux applies. OpenStack itself is installed from the CentOS guide, not from this repo.

## What each folder does

| Folder | Role |
|---|---|
| `ansible/` | Turns the three Ubuntu VMs into a Kubernetes cluster |
| `gitops/` | What Flux applies: Prometheus, Fluent Bit, the MCP servers, the agent |
| `mcp-server-docker/` | Reads and restarts containers through the Docker socket on a worker |
| `mcp-server-metrics/` | Reads Prometheus and forecasts memory |
| `mcp-server-infra/` | Reads Kubernetes and OpenStack. It does not change them |
| `agent-backend/` | Spring Boot chat API. The model calls the three servers |
| `agent-frontend/index.html` | The chat page. It posts to `/api/chat` |

## Execution order

Do these in order. Each step needs the one before it.

1. **OpenStack on CentOS.** Controller and compute, Horizon up at `http://10.0.0.11/dashboard`. No file from this repo.
2. **Three Ubuntu instances.** `K8s-Master`, `K8s-Worker1`, `K8s-Worker2`, launched from Horizon.
3. **Ansible.** Copy `ansible/inventory/hosts.yml.example` to `hosts.yml`, set the three addresses, then from a machine that can SSH in:

   ```bash
   cd ansible
   ansible-playbook -i inventory/hosts.yml site.yml
   ```

   Done when `kubectl get nodes` shows three nodes Ready. The playbook installs Docker and cri-dockerd so the Docker socket sees the pod containers.

4. **Flux.** On the master:

   ```bash
   curl -s https://fluxcd.io/install.sh | sudo bash
   flux bootstrap github \
     --owner=aboubakertounli \
     --repository=aiops-self-healing \
     --branch=main \
     --path=gitops \
     --personal
   ```

   Flux then installs Prometheus and the manifests in `gitops/`.

5. **Images.** Build and push before the deployments can start:

   ```bash
   docker build -f mcp-server-docker/Dockerfile -t docker.io/aboubakertounli/mcp-docker:dev .
   docker build -f mcp-server-metrics/Dockerfile -t docker.io/aboubakertounli/mcp-metrics:dev .
   docker build -f mcp-server-infra/Dockerfile -t docker.io/aboubakertounli/mcp-infra:dev .
   docker build -f agent-backend/Dockerfile -t docker.io/aboubakertounli/aiops-agent:dev .
   ```

   Create the secret the agent needs:

   ```bash
   kubectl -n aiops create secret generic llm --from-literal=OPENAI_API_KEY=sk-...
   ```

6. **Train Ticket.** After the cluster is Ready, deploy a slice first (UI, auth, travel, order, payment, and their databases) from the Train Ticket Helm chart. The full set comes later.
7. **Chat.** Open `agent-frontend/index.html`. Ask it to list containers, then to check one pod. A restart is the only change it can make.

## Checks along the way

| After | You should see |
|---|---|
| Horizon | Three running instances |
| Ansible | `kubectl get nodes` → 3 Ready |
| Flux | Pods in `monitoring` and `aiops` |
| Chat | A reply that names a real container or pod |

The Docker MCP service reaches one worker per call. The reply includes `node`, so you can see which worker answered. A restart happens on that worker only.
