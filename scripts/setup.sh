#!/bin/bash
# scripts/setup.sh
# Complete setup script for Smart GitOps Platform

set -e

echo "============================================"
echo "  Smart GitOps Platform - Setup Script"
echo "============================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_step() {
    echo -e "\n${GREEN}[STEP]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Step 1: Verify prerequisites
print_step "Verifying prerequisites..."

if ! command -v docker &> /dev/null; then
    print_error "Docker not found. Install Docker Desktop first."
    exit 1
fi
echo "  ✅ Docker: $(docker --version)"

if ! command -v kubectl &> /dev/null; then
    print_error "kubectl not found. Enable Kubernetes in Docker Desktop."
    exit 1
fi
echo "  ✅ kubectl: $(kubectl version --client --short 2>/dev/null)"

if ! command -v git &> /dev/null; then
    print_error "Git not found."
    exit 1
fi
echo "  ✅ Git: $(git --version)"

# Check if Kubernetes is running
if ! kubectl cluster-info &> /dev/null; then
    print_error "Kubernetes is not running!"
    echo "  Go to Docker Desktop → Settings → Kubernetes → Enable"
    exit 1
fi
echo "  ✅ Kubernetes cluster is running"

# Step 2: Build Docker images
print_step "Building Docker images..."

echo "  Building sample app..."
docker build -t smart-gitops-app:v1.0.0 ./sample-app/
echo "  ✅ smart-gitops-app:v1.0.0 built"

# Build a "bad" version for testing rollback
echo "  Building bad version (for testing)..."
docker build -t smart-gitops-app:v2.0.0-bad \
    --build-arg SIMULATE_FAILURE=true ./sample-app/
echo "  ✅ smart-gitops-app:v2.0.0-bad built"

echo "  Building dashboard..."
docker build -t gitops-dashboard:latest ./dashboard/
echo "  ✅ gitops-dashboard built"

# Step 3: Create Kubernetes namespace and deploy
print_step "Deploying to Kubernetes..."

# Apply manifests in order
kubectl apply -f k8s-manifests/namespace.yaml
echo "  ✅ Namespace created"

kubectl apply -f k8s-manifests/prometheus-rbac.yaml
echo "  ✅ Prometheus RBAC configured"

kubectl apply -f k8s-manifests/prometheus-config.yaml
echo "  ✅ Prometheus config created"

kubectl apply -f k8s-manifests/prometheus-deployment.yaml
echo "  ✅ Prometheus deployed"

kubectl apply -f k8s-manifests/grafana-deployment.yaml
echo "  ✅ Grafana deployed"

kubectl apply -f k8s-manifests/app-deployment.yaml
echo "  ✅ Demo app deployed"

kubectl apply -f k8s-manifests/app-service.yaml
echo "  ✅ App service created"

# Step 4: Wait for pods to be ready
print_step "Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod \
    -l app=gitops-demo-app \
    -n smart-gitops \
    --timeout=120s 2>/dev/null || print_warn "Some pods may still be starting"

kubectl wait --for=condition=ready pod \
    -l app=prometheus \
    -n smart-gitops \
    --timeout=120s 2>/dev/null || print_warn "Prometheus still starting"

# Step 5: Install Python dependencies for controller
print_step "Installing GitOps controller dependencies..."
cd gitops-controller
pip install -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt
cd ..

# Step 6: Install dashboard dependencies
print_step "Installing dashboard dependencies..."
cd dashboard
pip install -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt
cd ..

# Step 7: Display status
print_step "Checking deployment status..."
echo ""
kubectl get all -n smart-gitops
echo ""

echo "============================================"
echo -e "  ${GREEN}SETUP COMPLETE!${NC}"
echo "============================================"
echo ""
echo "  Access Points:"
echo "  ─────────────────────────────────────"
echo "  Demo App:     http://localhost:30080"
echo "  App Metrics:  http://localhost:30080/metrics"
echo "  Prometheus:   http://localhost:30090"
echo "  Grafana:      http://localhost:30030"
echo "      Login:    admin / gitops123"
echo ""
echo "  Next Steps:"
echo "  ─────────────────────────────────────"
echo "  1. Start the GitOps controller:"
echo "     cd gitops-controller && python main.py"
echo ""
echo "  2. Start the dashboard (new terminal):"
echo "     cd dashboard && python app.py"
echo "     Then open: http://localhost:3001"
echo ""
echo "  3. Push a change to your GitHub repo"
echo "     and watch the magic happen!"
echo "============================================"