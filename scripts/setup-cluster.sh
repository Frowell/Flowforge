#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="flowforge"
REGISTRY_NAME="flowforge-registry"
REGISTRY_PORT="5111"

echo "=== FlowForge Cluster Setup ==="

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found"; exit 1; }
command -v k3d >/dev/null 2>&1 || { echo "ERROR: k3d not found. Install: curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "ERROR: kubectl not found"; exit 1; }
command -v tilt >/dev/null 2>&1 || { echo "ERROR: tilt not found. Install: curl -fsSL https://raw.githubusercontent.com/tilt-dev/tilt/master/scripts/install.sh | bash"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "ERROR: helm not found. Install: curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"; exit 1; }

# Delete existing cluster if present
if k3d cluster list | grep -q "$CLUSTER_NAME"; then
  echo "Deleting existing cluster..."
  k3d cluster delete "$CLUSTER_NAME"
fi

echo "Creating k3d cluster: $CLUSTER_NAME"
k3d cluster create "$CLUSTER_NAME" \
  --servers 1 \
  --agents 2 \
  --registry-create "${REGISTRY_NAME}:0:${REGISTRY_PORT}" \
  --port "8000:80@loadbalancer" \
  --port "5173:5173@loadbalancer" \
  --port "8123:8123@loadbalancer" \
  --port "8180:8180@loadbalancer" \
  --port "8280:8280@loadbalancer" \
  --port "6875:6875@loadbalancer" \
  --port "9092:9092@loadbalancer" \
  --port "9644:9644@loadbalancer" \
  --port "6379:6379@loadbalancer" \
  --port "5432:5432@loadbalancer" \
  --k3s-arg "--disable=traefik@server:0" \
  --wait

echo "Cluster created. Verifying..."
kubectl cluster-info
kubectl get nodes

# Create namespace
kubectl create namespace flowforge --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "=== Cluster Ready ==="
echo "Registry: localhost:${REGISTRY_PORT}"
echo "Namespace: flowforge"
echo ""
echo "Next steps:"
echo "  1. cd to project root"
echo "  2. Run: tilt up"
echo "  3. Open: http://localhost:10350 (Tilt UI)"
