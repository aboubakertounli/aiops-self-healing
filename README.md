# AIOps self-healing platform

Code for the Kubernetes bootstrap, the GitOps manifests, the three MCP servers, and the chat agent. OpenStack is installed from the CentOS multinode guide. It is not in this repository.

The cluster is three Ubuntu VMs on the OpenStack compute host:

| VM | Role |
|---|---|
| `K8s-Master` | API server, scheduler, controller manager, etcd |
| `K8s-Worker1` | kubelet, kube-proxy, application pods |
| `K8s-Worker2` | kubelet, kube-proxy, application pods |

The master does not run the application. Pods run on the two workers.

Two namespaces hold what this repo deploys:

| Namespace | Contents |
|---|---|
| `aiops` | Docker MCP server (one pod per node, Docker socket mounted), metrics MCP server, infra MCP server, Spring agent, Fluent Bit |
| `monitoring` | Prometheus and Grafana, from the `kube-prometheus-stack` chart |

The Docker MCP server is the only process here that restarts a container. The metrics server and the infra server only read. A restart happens on the worker whose pod received the call. The tool reply includes `node` so you can see which worker that was.

## Folders

| Folder | Role |
|---|---|
| `ansible/` | SSH playbook that installs Kubernetes on the three VMs |
| `gitops/` | Desired state Flux applies to the cluster |
| `mcp-server-docker/` | Container list, stats, logs, forecast, restart. Talks to `/var/run/docker.sock` |
| `mcp-server-metrics/` | PromQL queries and a memory forecast |
| `mcp-server-infra/` | Kubernetes and OpenStack reads, plus pod-log search |
| `agent-backend/` | Spring Boot. `POST /api/chat` runs the model and the MCP tools |
| `agent-frontend/index.html` | Chat page. Posts to `/api/chat` |
| `shared/` | `forecast.py`, the straight-line memory forecast used by the Docker server and the metrics server |
| `tests/` | Checks that forecast: a steady climb reaches the limit, a flat line does not |

`shared/` exists so the two servers do not each keep their own copy of the formula. `tests/` does not start a cluster. The GitLab job `test` runs it with `python -m unittest discover -s tests`.

## Ansible

Ansible connects to the three Ubuntu VMs over SSH and runs the same steps you would type, in order. Install it on the machine you run the command from (`sudo apt install ansible`), not inside the Kubernetes nodes. That machine needs an SSH key accepted by the `ubuntu` user on each VM.

Copy `ansible/inventory/hosts.yml.example` to `ansible/inventory/hosts.yml` and replace the three addresses with the ones Horizon shows. The inventory is the list of machines. `master` and `workers` are groups. `site.yml` is the playbook: which group runs which tasks.

`site.yml` has three plays:

1. On the master, roles `common` and `kubernetes_master`. `common` turns off swap, loads `overlay` and `br_netfilter`, installs Docker, cri-dockerd, kubeadm, kubelet, and kubectl. cri-dockerd is what lets kubelet start pods through Docker, so `/var/run/docker.sock` sees those containers. `kubernetes_master` runs `kubeadm init` and saves the join command.
2. On the master, role `kubernetes_network` installs Flannel. Pods need that network before the workers are useful.
3. On the workers, `common` again, then `kubernetes_worker`, which runs the join command from the master.

A role is a directory under `ansible/roles/<name>/tasks/main.yml`. `become: true` runs the tasks with sudo.

```bash
cd ansible
ansible-playbook -i inventory/hosts.yml site.yml
```

Done when `kubectl get nodes` on the master shows three nodes `Ready`.

`inventory/openstack.yml` is the other way to build that list. It asks Nova for the instances when the playbook starts, so a new address does not have to be copied into a file. Install the plugin once, then export the OpenStack credentials (`OS_AUTH_URL`, `OS_USERNAME`, `OS_PASSWORD`, `OS_PROJECT_NAME`, `OS_USER_DOMAIN_NAME`, `OS_PROJECT_DOMAIN_NAME`). `OS_AUTH_URL` is the Keystone URL. With Kolla it is the internal VIP.

```bash
ansible-galaxy collection install -r requirements.yml
ansible-playbook -i inventory/openstack.yml site.yml
```

Each instance needs metadata `k8s_role`. The value `master` fills the `master` group. The value `worker` or `workers` fills the `workers` group that `site.yml` uses. Set that key in Horizon when you launch the instance.

## GitOps

`gitops/` is the desired state of the cluster. Flux watches this directory on `main` and creates, updates, or deletes objects until the cluster matches the files. Editing a live pod with `kubectl` and not committing the file means Flux will put the old spec back.

`kustomization.yaml` is the index of that directory. It names the YAML files to include:

- `namespace.yaml` creates `aiops` and `monitoring`, plus read access for the infra MCP server
- `mcp-docker.yaml` is the DaemonSet that mounts the Docker socket
- `agent.yaml` is the metrics server, the infra server, and the Spring agent
- `fluent-bit.yaml` tails container logs on every node
- `monitoring.yaml` is the Prometheus and Grafana chart

The Deployments use short image names (`mcp-docker`, `aiops-agent`). The `images:` block in `kustomization.yaml` rewrites them to `docker.io/aboubakertounli/<name>:dev` before anything is applied. Change `newTag` when you push a new image.

Grafana is not a separate manifest. `monitoring.yaml` is a Flux HelmRelease for `kube-prometheus-stack`. That chart installs Prometheus and Grafana into `monitoring`. The password in the file is `admin`. After Flux has applied it, the service name is `kube-prometheus-stack-grafana`.

## What is not in this repo

Train Ticket is not here. It is the separate project [FudanSELab/train-ticket](https://github.com/FudanSELab/train-ticket). This repo also has no DevSecOps pipeline for it: no SonarQube, Maven build of those services, OWASP check, or Trivy scan of those images.

`.gitlab-ci.yml` only does two things for this platform: run `tests/`, then build and push the three MCP images and the agent image. It does not deploy Train Ticket and it does not update `gitops/`.

## Execution order

Each step needs the one before it.

1. **OpenStack.** Controller and compute on CentOS, Horizon at `http://10.0.0.11/dashboard`.
2. **Instances.** From Horizon, launch `K8s-Master`, `K8s-Worker1`, and `K8s-Worker2` from an Ubuntu 24.04 image.
3. **Ansible.** Fill `hosts.yml` and run the playbook above.
4. **Images.** From the repo root, build and push:

   ```bash
   docker build -f mcp-server-docker/Dockerfile -t docker.io/aboubakertounli/mcp-docker:dev .
   docker build -f mcp-server-metrics/Dockerfile -t docker.io/aboubakertounli/mcp-metrics:dev .
   docker build -f mcp-server-infra/Dockerfile -t docker.io/aboubakertounli/mcp-infra:dev .
   docker build -f agent-backend/Dockerfile -t docker.io/aboubakertounli/aiops-agent:dev .
   docker push docker.io/aboubakertounli/mcp-docker:dev
   docker push docker.io/aboubakertounli/mcp-metrics:dev
   docker push docker.io/aboubakertounli/mcp-infra:dev
   docker push docker.io/aboubakertounli/aiops-agent:dev
   ```

5. **Flux.** On the master, after `kubectl` works:

   ```bash
   curl -s https://fluxcd.io/install.sh | sudo bash
   flux bootstrap github \
     --owner=aboubakertounli \
     --repository=aiops-self-healing \
     --branch=main \
     --path=gitops \
     --personal
   ```

6. **Secret.** The agent pod stays down until this exists:

   ```bash
   kubectl -n aiops create secret generic llm --from-literal=OPENAI_API_KEY=sk-...
   ```

7. **Chat.** Port-forward the agent and open `agent-frontend/index.html`. The page calls `http://localhost:8080` unless `localStorage.agentUrl` is set.

   ```bash
   kubectl -n aiops port-forward svc/aiops-agent 8080:8080
   ```

## Checks

| After | You should see |
|---|---|
| Horizon | Three running instances |
| Ansible | `kubectl get nodes` shows 3 Ready |
| Flux | Pods in `monitoring` and `aiops` |
| Secret | `aiops-agent` pod Running |
| Chat | A reply that names a real container or pod |

Grafana, once the chart is installed:

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80
```

Open `http://localhost:3000`. User `admin`, password `admin`.
