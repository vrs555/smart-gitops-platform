# gitops-controller/main.py
"""
Main GitOps Controller
Orchestrates all modules: Git watching, deploying,
health monitoring, AI analysis, and rollback.
"""
import logging
import time
import threading
import json
import sys
from datetime import datetime
from flask import Flask, jsonify, request
from config import Config
from git_watcher import GitWatcher
from k8s_deployer import K8sDeployer
from health_monitor import HealthMonitor
from ai_analyzer import AIAnalyzer
from rollback_manager import RollbackManager
from notifier import Notifier

# ============== LOGGING SETUP ==============
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/gitops-controller.log')
    ]
)
logger = logging.getLogger('gitops.main')

# ============== INITIALIZE MODULES ==============
git_watcher = GitWatcher()
k8s_deployer = K8sDeployer()
health_monitor = HealthMonitor()
ai_analyzer = AIAnalyzer()
rollback_manager = RollbackManager()
notifier = Notifier()

# ============== STATE ==============
controller_state = {
    'status': 'initializing',
    'start_time': datetime.now().isoformat(),
    'total_deployments': 0,
    'total_rollbacks': 0,
    'current_commit': None,
    'last_deployment_time': None,
    'ai_training_cycles': 0,
    'stable_period_count': 0
}

# ============== FLASK API FOR DASHBOARD ==============
api_app = Flask(__name__)


@api_app.route('/api/status')
def api_status():
    """Get overall system status."""
    return jsonify({
        'controller': controller_state,
        'git': git_watcher.get_sync_status(),
        'deployment': k8s_deployer.get_deployment_status(),
        'pods': k8s_deployer.get_pods_status(),
        'health': health_monitor.get_status_summary(),
        'ai': ai_analyzer.get_analysis_summary(),
        'rollback': rollback_manager.get_rollback_status(),
        'notifications': notifier.get_notification_history()[-10:]
    })


@api_app.route('/api/metrics')
def api_metrics():
    """Get current metrics."""
    metrics = health_monitor.collect_metrics()
    return jsonify(metrics)


@api_app.route('/api/metrics/history')
def api_metrics_history():
    """Get metrics history."""
    return jsonify(list(health_monitor.metrics_history))


@api_app.route('/api/deployments')
def api_deployments():
    """Get deployment history."""
    return jsonify({
        'history': k8s_deployer.get_deployment_history(),
        'current': k8s_deployer.get_deployment_status(),
        'pods': k8s_deployer.get_pods_status()
    })


@api_app.route('/api/rollbacks')
def api_rollbacks():
    """Get rollback history."""
    return jsonify(rollback_manager.get_rollback_status())


@api_app.route('/api/ai')
def api_ai():
    """Get AI analysis status."""
    return jsonify(ai_analyzer.get_analysis_summary())


@api_app.route('/api/force-rollback', methods=['POST'])
def api_force_rollback():
    """Manually trigger a rollback."""
    result = rollback_manager.rollback_deployment(
        reason='Manual rollback triggered via API'
    )
    notifier.notify_rollback(result)
    return jsonify(result)


@api_app.route('/api/train-ai', methods=['POST'])
def api_train_ai():
    """Manually trigger AI model training."""
    success = ai_analyzer.train_model()
    return jsonify({'success': success})


# ============== MAIN CONTROL LOOPS ==============

def git_sync_loop():
    """
    Main loop: Watch Git for changes and deploy.
    Runs every GIT_POLL_INTERVAL seconds.
    """
    logger.info("Starting Git sync loop...")
    
    while True:
        try:
            has_changes, commit = git_watcher.has_changes()
            
            if has_changes and commit:
                logger.info(f"{'='*50}")
                logger.info(f"NEW CHANGES DETECTED! Commit: {commit[:8]}")
                logger.info(f"{'='*50}")
                
                # Get manifest files
                manifest_files = git_watcher.get_manifest_files()
                
                if manifest_files:
                    # Deploy to Kubernetes
                    result = k8s_deployer.apply_all_manifests(manifest_files)
                    
                    controller_state['total_deployments'] += 1
                    controller_state['current_commit'] = commit[:8]
                    controller_state['last_deployment_time'] = (
                        datetime.now().isoformat()
                    )
                    
                    # Wait for rollout
                    rollout_success = k8s_deployer.wait_for_rollout()
                    
                    # Notify
                    status = 'success' if rollout_success else 'failed'
                    notifier.notify_deployment(
                        commit[:8], status,
                        f"{len(result['success'])} manifests applied"
                    )
                    
                    if rollout_success:
                        # Reset rollback counter on successful deploy
                        rollback_manager.reset_rollback_counter()
                        controller_state['stable_period_count'] = 0
                        
                    logger.info(f"Deployment {status} for commit {commit[:8]}")
                else:
                    logger.warning("No manifest files found in repository")
                    
        except Exception as e:
            logger.error(f"Git sync loop error: {e}", exc_info=True)
        
        time.sleep(Config.GIT_POLL_INTERVAL)


def health_check_loop():
    """
    Health monitoring loop: Collect metrics, analyze, rollback if needed.
    Runs every HEALTH_CHECK_INTERVAL seconds.
    """
    logger.info("Starting health check loop...")
    time.sleep(30)  # Wait for initial deployment
    
    previous_health = 'UNKNOWN'
    stable_checks = 0
    
    while True:
        try:
            # Step 1: Collect metrics
            metrics = health_monitor.collect_metrics()
            
            # Step 2: Rule-based health evaluation
            health_result = health_monitor.evaluate_health(metrics)
            
            # Step 3: Feed data to AI
            ai_metrics = health_monitor.get_metrics_for_ai(window_size=1)
            if ai_metrics:
                ai_analyzer.add_training_data(ai_metrics)
            
            # Step 4: AI prediction
            ai_result = ai_analyzer.predict(metrics)
            
            # Step 5: Notify on health status change
            current_health = health_result['status']
            if current_health != previous_health and previous_health != 'UNKNOWN':
                notifier.notify_health_change(
                    previous_health, current_health,
                    '; '.join(health_result.get('issues', []))
                )
            previous_health = current_health
            
            # Step 6: Check if rollback is needed
            needs_rollback = (
                health_result.get('needs_rollback', False) or 
                (ai_result.get('is_anomaly', False) and 
                 health_result['status'] == 'CRITICAL')
            )
            
            if needs_rollback:
                logger.warning(
                    "⚠️ UNHEALTHY DEPLOYMENT DETECTED - "
                    "Initiating automatic rollback!"
                )
                
                # Notify about anomaly
                notifier.notify_anomaly(metrics, ai_result)
                
                # Perform rollback
                rollback_result = rollback_manager.rollback_deployment(
                    reason=(
                        f"Auto-rollback: {'; '.join(health_result.get('issues', []))}"
                    )
                )
                
                if rollback_result['success']:
                    controller_state['total_rollbacks'] += 1
                    notifier.notify_rollback(rollback_result)
                    stable_checks = 0
                    
                    # Wait before checking health again
                    time.sleep(30)
            else:
                # Track stable period
                if current_health == 'HEALTHY':
                    stable_checks += 1
                    controller_state['stable_period_count'] = stable_checks
                    
                    # Reset rollback counter after sustained stability
                    if stable_checks >= 20:  # ~5 minutes of health
                        rollback_manager.reset_rollback_counter()
                        stable_checks = 0
                
            # Step 7: Periodically retrain AI model
            if (len(health_monitor.metrics_history) % 50 == 0 and 
                    len(health_monitor.metrics_history) > 0):
                logger.info("Triggering periodic AI model retraining...")
                ai_analyzer.train_model()
                controller_state['ai_training_cycles'] += 1
                
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
        
        time.sleep(Config.HEALTH_CHECK_INTERVAL)


def main():
    """Main entry point for the GitOps Controller."""
    logger.info("=" * 60)
    logger.info("  SMART GITOPS CONTROLLER STARTING")
    logger.info("=" * 60)
    logger.info(f"  Repository: {Config.GIT_REPO_URL}")
    logger.info(f"  Branch: {Config.GIT_BRANCH}")
    logger.info(f"  Namespace: {Config.K8S_NAMESPACE}")
    logger.info(f"  Poll Interval: {Config.GIT_POLL_INTERVAL}s")
    logger.info(f"  Health Check Interval: {Config.HEALTH_CHECK_INTERVAL}s")
    logger.info("=" * 60)
    
    controller_state['status'] = 'running'
    
    # Start Git sync loop in a thread
    git_thread = threading.Thread(target=git_sync_loop, daemon=True)
    git_thread.start()
    logger.info("Git sync loop started")
    
    # Start health check loop in a thread
    health_thread = threading.Thread(target=health_check_loop, daemon=True)
    health_thread.start()
    logger.info("Health check loop started")
    
    # Start API server (for dashboard to query)
    logger.info(f"Starting API server on port {Config.DASHBOARD_PORT}")
    api_app.run(
        host='0.0.0.0', 
        port=Config.DASHBOARD_PORT, 
        debug=False,
        use_reloader=False
    )


if __name__ == '__main__':
    main()