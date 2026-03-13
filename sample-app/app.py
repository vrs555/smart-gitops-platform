# sample-app/app.py
from flask import Flask, jsonify, Response
import random
import time
import os
import psutil
import threading
from prometheus_client import (
    Counter, Histogram, Gauge, 
    generate_latest, CONTENT_TYPE_LATEST
)

app = Flask(__name__)

# ============== PROMETHEUS METRICS ==============
REQUEST_COUNT = Counter(
    'app_request_total', 
    'Total request count', 
    ['method', 'endpoint', 'status']
)
REQUEST_LATENCY = Histogram(
    'app_request_latency_seconds', 
    'Request latency in seconds',
    ['endpoint']
)
CPU_USAGE = Gauge(
    'app_cpu_usage_percent', 
    'Current CPU usage percentage'
)
MEMORY_USAGE = Gauge(
    'app_memory_usage_percent', 
    'Current memory usage percentage'
)
ERROR_RATE = Gauge(
    'app_error_rate', 
    'Current error rate'
)
ACTIVE_REQUESTS = Gauge(
    'app_active_requests', 
    'Number of active requests'
)

# Track errors for rate calculation
error_count = 0
total_count = 0
lock = threading.Lock()

# Simulate a "bad deployment" flag
SIMULATE_FAILURE = os.environ.get('SIMULATE_FAILURE', 'false').lower() == 'true'

def update_system_metrics():
    """Background thread to update system metrics."""
    while True:
        CPU_USAGE.set(psutil.cpu_percent(interval=1))
        MEMORY_USAGE.set(psutil.virtual_memory().percent)
        with lock:
            if total_count > 0:
                ERROR_RATE.set((error_count / total_count) * 100)
            else:
                ERROR_RATE.set(0)
        time.sleep(5)

# Start background metrics collection
metrics_thread = threading.Thread(target=update_system_metrics, daemon=True)
metrics_thread.start()


@app.route('/')
def home():
    global error_count, total_count
    start_time = time.time()
    ACTIVE_REQUESTS.inc()
    
    with lock:
        total_count += 1
    
    # Simulate failure in bad deployments
    if SIMULATE_FAILURE and random.random() < 0.4:
        with lock:
            error_count += 1
        REQUEST_COUNT.labels('GET', '/', '500').inc()
        ACTIVE_REQUESTS.dec()
        latency = time.time() - start_time
        REQUEST_LATENCY.labels('/').observe(latency)
        return jsonify({
            'status': 'error',
            'message': 'Internal server error (simulated failure)'
        }), 500
    
    # Simulate variable response time
    if SIMULATE_FAILURE:
        time.sleep(random.uniform(0.5, 2.0))  # Slow response in bad deploy
    else:
        time.sleep(random.uniform(0.01, 0.1))  # Normal response time
    
    latency = time.time() - start_time
    REQUEST_LATENCY.labels('/').observe(latency)
    REQUEST_COUNT.labels('GET', '/', '200').inc()
    ACTIVE_REQUESTS.dec()
    
    version = os.environ.get('APP_VERSION', '1.0.0')
    
    return jsonify({
        'status': 'healthy',
        'version': version,
        'message': 'Smart GitOps Demo Application',
        'timestamp': time.time()
    })


@app.route('/health')
def health():
    """Health check endpoint for Kubernetes."""
    REQUEST_COUNT.labels('GET', '/health', '200').inc()
    
    if SIMULATE_FAILURE and random.random() < 0.3:
        return jsonify({'status': 'unhealthy'}), 503
    
    return jsonify({
        'status': 'healthy',
        'version': os.environ.get('APP_VERSION', '1.0.0'),
        'uptime': time.time()
    })


@app.route('/ready')
def ready():
    """Readiness check endpoint."""
    return jsonify({'status': 'ready'})


@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        generate_latest(), 
        mimetype=CONTENT_TYPE_LATEST
    )


@app.route('/info')
def info():
    """Application info endpoint."""
    return jsonify({
        'app_name': 'smart-gitops-demo',
        'version': os.environ.get('APP_VERSION', '1.0.0'),
        'environment': os.environ.get('ENVIRONMENT', 'development'),
        'simulate_failure': SIMULATE_FAILURE
    })


@app.route('/api/data')
def api_data():
    """Sample API endpoint."""
    global error_count, total_count
    start_time = time.time()
    
    with lock:
        total_count += 1
    
    if SIMULATE_FAILURE and random.random() < 0.5:
        with lock:
            error_count += 1
        REQUEST_COUNT.labels('GET', '/api/data', '500').inc()
        return jsonify({'error': 'Failed to fetch data'}), 500
    
    data = {
        'items': [
            {'id': i, 'value': random.randint(1, 100)} 
            for i in range(5)
        ],
        'generated_at': time.time()
    }
    
    latency = time.time() - start_time
    REQUEST_LATENCY.labels('/api/data').observe(latency)
    REQUEST_COUNT.labels('GET', '/api/data', '200').inc()
    
    return jsonify(data)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Smart GitOps Demo App v{os.environ.get('APP_VERSION', '1.0.0')}")
    print(f"Failure simulation: {SIMULATE_FAILURE}")
    app.run(host='0.0.0.0', port=port, debug=False)