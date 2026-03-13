#!/bin/bash
# scripts/cleanup.sh
# Clean up all resources

echo "🧹 Cleaning up Smart GitOps Platform..."

kubectl delete namespace smart-gitops --ignore-not-found
kubectl delete clusterrole prometheus --ignore-not-found
kubectl delete clusterrolebinding prometheus --ignore-not-found

docker rmi smart-gitops-app:v1.0.0 2>/dev/null
docker rmi smart-gitops-app:v2.0.0-bad 2>/dev/null
docker rmi gitops-dashboard:latest 2>/dev/null

rm -rf /tmp/gitops-repo
rm -f /tmp/gitops_ai_model.pkl
rm -f /tmp/gitops-controller.log

echo "✅ Cleanup complete!"