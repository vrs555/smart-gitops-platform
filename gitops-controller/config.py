# gitops-controller/config.py
"""
Configuration for the GitOps Controller.
All settings in one place.
"""
import os

class Config:
    # Git Configuration
    GIT_REPO_URL = os.environ.get(
        'GIT_REPO_URL', 
        'https://github.com/vrs555/smart-gitops-platform.git'
    )
    GIT_BRANCH = os.environ.get('GIT_BRANCH', 'main')
    GIT_POLL_INTERVAL = int(os.environ.get('GIT_POLL_INTERVAL', '30'))  # seconds
    GIT_MANIFESTS_PATH = os.environ.get('GIT_MANIFESTS_PATH', 'k8s-manifests')
    LOCAL_REPO_PATH = os.environ.get('LOCAL_REPO_PATH', '/tmp/gitops-repo')
    
    # GitHub Personal Access Token (for private repos)
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
    
    # Kubernetes Configuration
    K8S_NAMESPACE = os.environ.get('K8S_NAMESPACE', 'smart-gitops')
    K8S_IN_CLUSTER = os.environ.get('K8S_IN_CLUSTER', 'false').lower() == 'true'
    
    # Prometheus Configuration
    PROMETHEUS_URL = os.environ.get(
        'PROMETHEUS_URL', 
        'http://localhost:30090'
    )
    
    # Health Monitoring
    HEALTH_CHECK_INTERVAL = int(os.environ.get('HEALTH_CHECK_INTERVAL', '15'))
    ANOMALY_THRESHOLD = float(os.environ.get('ANOMALY_THRESHOLD', '-0.5'))
    
    # Rollback Settings
    MAX_ROLLBACK_ATTEMPTS = int(os.environ.get('MAX_ROLLBACK_ATTEMPTS', '3'))
    ROLLBACK_COOLDOWN = int(os.environ.get('ROLLBACK_COOLDOWN', '120'))  # seconds
    
    # Notification Settings
    SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
    EMAIL_ENABLED = os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true'
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
    SMTP_USER = os.environ.get('SMTP_USER', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    ALERT_EMAIL = os.environ.get('ALERT_EMAIL', '')
    
    # Dashboard
    DASHBOARD_PORT = int(os.environ.get('DASHBOARD_PORT', '8080'))
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')