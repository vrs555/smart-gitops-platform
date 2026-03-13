#!/bin/bash
# scripts/generate-traffic.sh
# Generates traffic to the app so Prometheus has metrics to scrape

echo "🔄 Generating traffic to the demo app..."
echo "Press Ctrl+C to stop"
echo ""

while true; do
    # Hit various endpoints
    curl -s http://localhost:30080/ > /dev/null 2>&1
    curl -s http://localhost:30080/health > /dev/null 2>&1
    curl -s http://localhost:30080/api/data > /dev/null 2>&1
    curl -s http://localhost:30080/info > /dev/null 2>&1
    
    # Random small delay
    sleep 0.$(( RANDOM % 5 + 1 ))
done