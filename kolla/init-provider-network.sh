#!/bin/bash
# Run after kolla-ansible post-deploy. Creates the flat provider network
# on br-ex. Does not launch the Kubernetes instances.
set -euo pipefail

PROVIDER_CIDR="${PROVIDER_CIDR:-172.16.99.0/24}"
PROVIDER_GATEWAY="${PROVIDER_GATEWAY:?Set PROVIDER_GATEWAY to the router on 172.16.99.0/24}"
PROVIDER_POOL_START="${PROVIDER_POOL_START:-172.16.99.100}"
PROVIDER_POOL_END="${PROVIDER_POOL_END:-172.16.99.200}"

# shellcheck disable=SC1091
source /etc/kolla/admin-openrc.sh

if openstack network show provider >/dev/null 2>&1; then
  echo "provider network already exists"
  exit 0
fi

openstack network create \
  --external \
  --provider-physical-network physnet1 \
  --provider-network-type flat \
  provider

openstack subnet create \
  --network provider \
  --subnet-range "$PROVIDER_CIDR" \
  --gateway "$PROVIDER_GATEWAY" \
  --dns-nameserver 8.8.8.8 \
  --allocation-pool "start=${PROVIDER_POOL_START},end=${PROVIDER_POOL_END}" \
  provider-subnet

echo "provider network ready. Launch K8s-Master, K8s-Worker1, and K8s-Worker2 from Horizon."
