#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing FlowForge Development Tools ==="

# k3d
if ! command -v k3d &>/dev/null; then
  echo "Installing k3d..."
  curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
fi

# kubectl
if ! command -v kubectl &>/dev/null; then
  echo "Installing kubectl..."
  curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  sudo install kubectl /usr/local/bin/
  rm kubectl
fi

# Helm
if ! command -v helm &>/dev/null; then
  echo "Installing Helm..."
  curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

# Tilt
if ! command -v tilt &>/dev/null; then
  echo "Installing Tilt..."
  curl -fsSL https://raw.githubusercontent.com/tilt-dev/tilt/master/scripts/install.sh | bash
fi

# k9s
if ! command -v k9s &>/dev/null; then
  echo "Installing k9s..."
  curl -sS https://webinstall.dev/k9s | bash
fi

# rpk (Redpanda CLI)
if ! command -v rpk &>/dev/null; then
  echo "Installing rpk..."
  curl -LO https://github.com/redpanda-data/redpanda/releases/latest/download/rpk-linux-amd64.zip
  unzip rpk-linux-amd64.zip -d /tmp/rpk
  sudo install /tmp/rpk/rpk /usr/local/bin/
  rm -rf rpk-linux-amd64.zip /tmp/rpk
fi

echo ""
echo "=== All tools installed ==="
echo "Versions:"
k3d version
kubectl version --client --short 2>/dev/null || kubectl version --client
helm version --short
tilt version
k9s version --short 2>/dev/null || echo "k9s installed"
rpk version
