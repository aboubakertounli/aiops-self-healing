# AIOps self-healing platform

Code for the OpenStack install, the Kubernetes bootstrap, the GitOps manifests, the three MCP servers, and the chat agent. OpenStack is installed with Kolla Ansible on two Ubuntu nodes. Kubernetes is a separate playbook, run after the three instances exist.

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
| `aiops` | Metrics MCP server, infra MCP server, and the Spring agent. All three run on the control-plane node, separate from `kube-system`. |
| `monitoring` | Prometheus and Grafana, from the `kube-prometheus-stack` chart |

The workers run the application pods. The infra MCP server can delete one application pod. containerd starts the replacement. It does not create a node and it does not edit a manifest. Fluent Bit still runs on every node, including the workers, because that is how the logs are collected.

## Folders

| Folder | Role |
|---|---|
| `kolla/` | Kolla Ansible inventory and `globals.yml` for the controller and the compute node |
| `ansible/` | SSH playbook that installs Kubernetes on the three VMs |
| `gitops/` | Desired state Flux applies to the cluster |
| `mcp-server-metrics/` | PromQL queries and a memory forecast |
| `mcp-server-infra/` | Kubernetes and OpenStack reads, plus pod-log search |
| `agent-backend/` | Spring Boot. `POST /api/chat` runs the model and the MCP tools |
| `agent-frontend/index.html` | Same console the agent serves at `/`. Shows the model, the MCP servers, the reply, and each tool call |
| `shared/` | `forecast.py`, the straight-line memory forecast used by the metrics server |
| `tests/` | Checks that forecast: a steady climb reaches the limit, a flat line does not |

`shared/` exists so the two servers do not each keep their own copy of the formula. `tests/` does not start a cluster. The GitLab job `test` runs it with `python -m unittest discover -s tests`.

## Ansible

Ansible connects to the three Ubuntu VMs over SSH and runs the same steps you would type, in order. Install it on the machine you run the command from (`sudo apt install ansible`), not inside the Kubernetes nodes. That machine needs an SSH key accepted by the `ubuntu` user on each VM.

Copy `ansible/inventory/hosts.yml.example` to `ansible/inventory/hosts.yml` and replace the three addresses with the ones Horizon shows. The inventory is the list of machines. `master` and `workers` are groups. `site.yml` is the playbook: which group runs which tasks.

`site.yml` has three plays:

1. On the master, roles `common` and `kubernetes_master`. `common` turns off swap, loads `overlay` and `br_netfilter`, installs containerd, kubeadm, kubelet, and kubectl. containerd is the runtime kubeadm uses. `kubernetes_master` runs `kubeadm init` and saves the join command.
2. On the master, role `kubernetes_network` installs Flannel. Pods need that network before the workers are useful.
3. On the workers, `common` again, then `kubernetes_worker`, which runs the join command from the master.

A role is a directory under `ansible/roles/<name>/tasks/main.yml`. `become: true` runs the tasks with sudo.

```bash
cd ansible
ansible-playbook -i inventory/hosts.yml site.yml
```

Done when `kubectl get nodes` on the master shows three nodes `Ready`. `inventory/openstack.yml` is the other inventory: the OpenStack plugin discovers the VMs from Nova instead of a static file. Set `OS_AUTH_URL` to the Kolla VIP (`http://10.0.0.10:5000/v3` unless you changed it), plus `OS_USERNAME`, `OS_PASSWORD`, and `OS_PROJECT_NAME`. Tag the master instance with metadata `k8s_role=master` and the two workers with `k8s_role=workers`, so the group names match `site.yml`.

## Kolla

`kolla/` installs OpenStack. It does not create the Kubernetes instances and it does not run `site.yml`.

Two Ubuntu 24.04 nodes, each with two NICs. The management NIC keeps its address (`10.0.0.11` on the controller, `10.0.0.31` on the compute). The provider NIC has no address. Kolla attaches that second NIC to `br-ex`. The names in `kolla/globals.yml` (`eth0`, `eth1`) have to be replaced with the names from `ip a` if they differ. `kolla_internal_vip_address` is a free address on `10.0.0.0/24`. Horizon and Keystone listen on that VIP, not on `10.0.0.11`.

From the machine that can SSH to both nodes as `ubuntu`:

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

`kolla-genpwd` writes `/etc/kolla/passwords.yml`. That file stays on the operator machine. Then open Horizon at `http://10.0.0.10` and launch the three Ubuntu instances on the `provider` network. Set `PROVIDER_GATEWAY` to the router that already exists on `172.16.99.0/24`.

## GitOps

`gitops/` is the desired state of the cluster. Flux watches this directory on `main` and creates, updates, or deletes objects until the cluster matches the files. Editing a live pod with `kubectl` and not committing the file means Flux will put the old spec back.

`kustomization.yaml` is the index of that directory. It names the YAML files to include:

- `namespace.yaml` creates `aiops` and `monitoring`, plus read access for the infra MCP server
- `agent.yaml` is the metrics server, the infra server, and the Spring agent, scheduled on the control-plane node
- `fluent-bit.yaml` tails container logs on every node
- `monitoring.yaml` is the Prometheus and Grafana chart

The Deployments use short image names (`mcp-metrics`, `aiops-agent`). The `images:` block in `kustomization.yaml` rewrites them to `docker.io/aboubakertounli/<name>:dev` before anything is applied. Change `newTag` when you push a new image.

Grafana is not a separate manifest. `monitoring.yaml` is a Flux HelmRelease for `kube-prometheus-stack`. That chart installs Prometheus and Grafana into `monitoring`. The password in the file is `admin`. After Flux has applied it, the service name is `kube-prometheus-stack-grafana`.

## What is not in this repo

Train Ticket is not here. It is the separate project [FudanSELab/train-ticket](https://github.com/FudanSELab/train-ticket). This repo also has no DevSecOps pipeline for it: no SonarQube, Maven build of those services, OWASP check, or Trivy scan of those images.

`.gitlab-ci.yml` only does two things for this platform: run `tests/`, then build and push the three MCP images and the agent image. It does not deploy Train Ticket and it does not update `gitops/`.

## Deploy from the CentOS server

The CentOS Stream 9 machine is the hypervisor. Kolla 2025.1 installs OpenStack on Ubuntu 24.04 guests, and the Kubernetes playbook also targets Ubuntu. Do not install kubeadm on the CentOS host.

1. On CentOS, install KVM and allow the compute guest to run VMs: `dnf install -y qemu-kvm libvirt virt-install`, then `systemctl enable --now libvirtd`.
2. Create the two networks. Management is `10.0.0.0/24`. The provider bridge is attached to the physical NIC and uses `172.16.99.0/24`.
3. Create two Ubuntu 24.04 guests, each with one NIC on each network. Controller `10.0.0.11`. Compute `10.0.0.31`. Leave the provider NIC without an address. Enable nested virtualization on the compute guest.
4. From a machine that can SSH to both guests, run the Kolla commands in the section above. Edit `eth0` and `eth1` in `kolla/globals.yml` first if `ip a` shows other names.
5. Open Horizon at `http://10.0.0.10`. Launch `K8s-Master`, `K8s-Worker1`, and `K8s-Worker2` from an Ubuntu 24.04 image on the `provider` network. Tag them `k8s_role=master` or `k8s_role=workers`.
6. Copy `ansible/inventory/hosts.yml.example` to `hosts.yml`, set the three addresses, and run `ansible-playbook -i inventory/hosts.yml site.yml`.
7. Build and push the three images listed below, bootstrap Flux, then open the console. For OpenAI, create the `llm` secret. For Ollama on the CentOS GPU, set `OPENAI_BASE_URL` and `OPENAI_MODEL` in `gitops/agent.yaml`.

Workers receive Train Ticket only. The agent, the metrics server, and the infra server stay in the namespace `aiops` on `K8s-Master`.

## Execution order

Each step needs the one before it.

1. **OpenStack.** Kolla on the two Ubuntu nodes, then the provider network. Horizon at `http://10.0.0.10`.
2. **Instances.** From Horizon, launch `K8s-Master`, `K8s-Worker1`, and `K8s-Worker2` on the `provider` network from an Ubuntu 24.04 image.
3. **Ansible.** Fill `hosts.yml` and run the playbook above.
4. **Images.** From the repo root, build and push:

   ```bash
   docker build -f mcp-server-metrics/Dockerfile -t docker.io/aboubakertounli/mcp-metrics:dev .
   docker build -f mcp-server-infra/Dockerfile -t docker.io/aboubakertounli/mcp-infra:dev .
   docker build -f agent-backend/Dockerfile -t docker.io/aboubakertounli/aiops-agent:dev .
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

6. **Secret and model.** For OpenAI, create the key the pod reads:

   ```bash
   kubectl -n aiops create secret generic llm --from-literal=OPENAI_API_KEY=sk-...
   ```

   For a model on your own GPU, install Ollama on the CentOS host (the machine that has the GPU) and change `OPENAI_BASE_URL` and `OPENAI_MODEL` in `gitops/agent.yaml`. Example: base URL `http://<centos-host>:11434` and model `qwen2.5:7b`. The model has to support tool calls. The secret can stay absent: the key defaults to `ollama`.

7. **Console.** Port-forward the agent and open the page it serves:

   ```bash
   kubectl -n aiops port-forward svc/aiops-agent 8080:8080
   ```

   Open `http://localhost:8080`. The page shows the model, the two MCP servers, the reply, and each tool call. `AGENT_WATCH_SECONDS` stays `0`, so the model runs when you send a message. Set it to `300` when you want the same inspection to repeat every five minutes.

## Checks

| After | You should see |
|---|---|
| Horizon | Three running instances |
| Ansible | `kubectl get nodes` shows 3 Ready |
| Flux | Pods in `monitoring` and `aiops` |
| Secret or Ollama URL | `aiops-agent` pod Running |
| Console | `http://localhost:8080` shows the model and a reply that names a real pod |

Grafana, once the chart is installed:

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80
```

Open `http://localhost:3000`. User `admin`, password `admin`.
