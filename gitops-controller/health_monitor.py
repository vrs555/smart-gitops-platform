# gitops-controller/health_monitor.py
"""
Health Monitor Module
Collects metrics from Prometheus and Kubernetes,
evaluates deployment health.
"""
import requests
import logging
import time
from datetime import datetime
from collections import deque
from config import Config

logger = logging.getLogger('gitops.health_monitor')


class HealthMonitor:
    def __init__(self):
        self.prometheus_url = Config.PROMETHEUS_URL
        self.metrics_history = deque(maxlen=500)
        self.health_status = 'UNKNOWN'
        self.last_check_time = None
        self.consecutive_failures = 0
        self.alert_history = []
        
    def query_prometheus(self, query):
        """Execute a PromQL query against Prometheus."""
        try:
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={'query': query},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('data', {}).get('result', [])
                return results
            else:
                logger.warning(
                    f"Prometheus query failed with status {response.status_code}"
                )
                return None
        except requests.exceptions.ConnectionError:
            logger.warning("Cannot connect to Prometheus. Is it running?")
            return None
        except Exception as e:
            logger.error(f"Prometheus query error: {e}")
            return None

    def get_request_rate(self):
        """Get the current request rate (requests per second)."""
        results = self.query_prometheus(
            'rate(app_request_total[2m])'
        )
        if results:
            total_rate = sum(float(r['value'][1]) for r in results)
            return round(total_rate, 4)
        return 0

    def get_error_rate(self):
        """Get the error rate percentage."""
        # Get error requests
        error_results = self.query_prometheus(
            'rate(app_request_total{status="500"}[2m])'
        )
        # Get total requests
        total_results = self.query_prometheus(
            'rate(app_request_total[2m])'
        )
        
        if error_results and total_results:
            error_rate = sum(float(r['value'][1]) for r in error_results)
            total_rate = sum(float(r['value'][1]) for r in total_results)
            
            if total_rate > 0:
                return round((error_rate / total_rate) * 100, 2)
        return 0

    def get_response_time(self):
        """Get average response time in seconds."""
        results = self.query_prometheus(
            'rate(app_request_latency_seconds_sum[2m]) / '
            'rate(app_request_latency_seconds_count[2m])'
        )
        if results:
            values = [float(r['value'][1]) for r in results if r['value'][1] != 'NaN']
            if values:
                return round(sum(values) / len(values), 4)
        return 0

    def get_cpu_usage(self):
        """Get CPU usage from app metrics."""
        results = self.query_prometheus('app_cpu_usage_percent')
        if results:
            values = [float(r['value'][1]) for r in results]
            if values:
                return round(sum(values) / len(values), 2)
        return 0

    def get_memory_usage(self):
        """Get memory usage from app metrics."""
        results = self.query_prometheus('app_memory_usage_percent')
        if results:
            values = [float(r['value'][1]) for r in results]
            if values:
                return round(sum(values) / len(values), 2)
        return 0

    def get_active_requests(self):
        """Get number of active requests."""
        results = self.query_prometheus('app_active_requests')
        if results:
            return sum(float(r['value'][1]) for r in results)
        return 0

    def collect_metrics(self):
        """Collect all metrics and return as a dictionary."""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'epoch': time.time(),
            'request_rate': self.get_request_rate(),
            'error_rate': self.get_error_rate(),
            'response_time': self.get_response_time(),
            'cpu_usage': self.get_cpu_usage(),
            'memory_usage': self.get_memory_usage(),
            'active_requests': self.get_active_requests()
        }
        
        self.metrics_history.append(metrics)
        self.last_check_time = datetime.now().isoformat()
        
        logger.info(
            f"Metrics collected - Error Rate: {metrics['error_rate']}%, "
            f"Response Time: {metrics['response_time']}s, "
            f"CPU: {metrics['cpu_usage']}%"
        )
        
        return metrics

    def evaluate_health(self, metrics):
        """
        Evaluate deployment health based on collected metrics.
        Returns health status and details.
        """
        issues = []
        severity = 'HEALTHY'
        
        # Rule 1: High error rate
        if metrics['error_rate'] > 20:
            issues.append(f"HIGH ERROR RATE: {metrics['error_rate']}% (threshold: 20%)")
            severity = 'CRITICAL'
        elif metrics['error_rate'] > 10:
            issues.append(f"Elevated error rate: {metrics['error_rate']}% (threshold: 10%)")
            if severity != 'CRITICAL':
                severity = 'WARNING'
        
        # Rule 2: High response time
        if metrics['response_time'] > 2.0:
            issues.append(
                f"HIGH RESPONSE TIME: {metrics['response_time']}s (threshold: 2s)"
            )
            severity = 'CRITICAL'
        elif metrics['response_time'] > 1.0:
            issues.append(
                f"Elevated response time: {metrics['response_time']}s (threshold: 1s)"
            )
            if severity != 'CRITICAL':
                severity = 'WARNING'
        
        # Rule 3: High CPU usage
        if metrics['cpu_usage'] > 90:
            issues.append(f"HIGH CPU USAGE: {metrics['cpu_usage']}% (threshold: 90%)")
            severity = 'CRITICAL'
        elif metrics['cpu_usage'] > 75:
            issues.append(f"Elevated CPU usage: {metrics['cpu_usage']}%")
            if severity != 'CRITICAL':
                severity = 'WARNING'
        
        # Rule 4: High memory usage
        if metrics['memory_usage'] > 90:
            issues.append(
                f"HIGH MEMORY USAGE: {metrics['memory_usage']}% (threshold: 90%)"
            )
            severity = 'CRITICAL'
        elif metrics['memory_usage'] > 80:
            issues.append(f"Elevated memory usage: {metrics['memory_usage']}%")
            if severity != 'CRITICAL':
                severity = 'WARNING'
        
        # Track consecutive failures
        if severity == 'CRITICAL':
            self.consecutive_failures += 1
        elif severity == 'HEALTHY':
            self.consecutive_failures = 0
        
        self.health_status = severity
        
        health_result = {
            'status': severity,
            'issues': issues,
            'metrics': metrics,
            'consecutive_failures': self.consecutive_failures,
            'needs_rollback': (
                severity == 'CRITICAL' and self.consecutive_failures >= 3
            ),
            'timestamp': datetime.now().isoformat()
        }
        
        if issues:
            logger.warning(
                f"Health Status: {severity} | Issues: {'; '.join(issues)}"
            )
            self.alert_history.append(health_result)
            self.alert_history = self.alert_history[-100:]
        else:
            logger.info(f"Health Status: {severity} - All metrics normal")
        
        return health_result

    def get_metrics_for_ai(self, window_size=30):
        """
        Get recent metrics formatted for the AI analyzer.
        Returns a list of metric dictionaries.
        """
        recent_metrics = list(self.metrics_history)[-window_size:]
        return [
            {
                'error_rate': m['error_rate'],
                'response_time': m['response_time'],
                'cpu_usage': m['cpu_usage'],
                'memory_usage': m['memory_usage'],
                'request_rate': m['request_rate']
            }
            for m in recent_metrics
        ]

    def get_status_summary(self):
        """Get a summary of current health status."""
        return {
            'health_status': self.health_status,
            'last_check': self.last_check_time,
            'consecutive_failures': self.consecutive_failures,
            'total_checks': len(self.metrics_history),
            'recent_alerts': self.alert_history[-5:],
            'latest_metrics': (
                dict(list(self.metrics_history)[-1]) 
                if self.metrics_history else {}
            )
        }