#!/bin/bash
# scripts/simulate-bad-deploy.sh
# Simulates a bad deployment to test rollback

echo "🔴 Simulating a BAD deployment..."
echo "This will deploy a version with high error rate and slow responses"
echo ""

# Update the deployment with the bad version
kubectl set image deployment/gitops-demo-app \
    app=smart-gitops-app:v2.0.0-bad \
    -n smart-gitops

kubectl set env deployment/gitops-demo-app \
    SIMULATE_FAILURE=true \
    APP_VERSION=2.0.0-bad \
    -n smart-gitops

echo "✅ Bad deployment applied!"
echo ""
echo "Watch the GitOps controller detect the anomaly and auto-rollback."
echo "Check the dashboard at http://localhost:3001"