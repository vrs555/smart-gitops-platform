# gitops-controller/k8s_deployer.py
"""
Kubernetes Deployer Module
Applies manifests to the Kubernetes cluster.
Manages deployments, tracks versions, and handles rollbacks.
"""
import yaml
import logging
import time
import subprocess
from datetime import datetime
from config import Config

logger = logging.getLogger('gitops.k8s_deployer')


class K8sDeployer:
    def __init__(self):
        self.namespace = Config.K8S_NAMESPACE
        self.deployment_history = []
        self.current_version = None
        self.current_image = None
        
    def _run_kubectl(self, args, input_data=None):
        """Run a kubectl command."""
        cmd = ['kubectl'] + args
        try:
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"kubectl command timed out: {' '.join(cmd)}")
            return None
        except Exception as e:
            logger.error(f"kubectl error: {e}")
            return None

    def ensure_namespace(self):
        """Create namespace if it doesn't exist."""
        result = self._run_kubectl([
            'get', 'namespace', self.namespace
        ])
        
        if result and result.returncode != 0:
            logger.info(f"Creating namespace: {self.namespace}")
            self._run_kubectl([
                'create', 'namespace', self.namespace
            ])

    def apply_manifest(self, filepath):
        """Apply a single Kubernetes manifest file."""
        logger.info(f"Applying manifest: {filepath}")
        
        result = self._run_kubectl([
            'apply', '-f', filepath, '--namespace', self.namespace
        ])
        
        if result and result.returncode == 0:
            logger.info(f"Successfully applied: {filepath}")
            return True
        else:
            stderr = result.stderr if result else 'Command failed'
            logger.error(f"Failed to apply {filepath}: {stderr}")
            return False

    def apply_all_manifests(self, manifest_files):
        """Apply all manifest files in order."""
        self.ensure_namespace()
        
        results = {
            'success': [],
            'failed': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # Apply namespace first, then other resources
        ordered_files = sorted(manifest_files, key=lambda f: (
            0 if 'namespace' in f else
            1 if 'rbac' in f or 'serviceaccount' in f else
            2 if 'config' in f else
            3 if 'service' in f and 'deployment' not in f else
            4
        ))
        
        for filepath in ordered_files:
            success = self.apply_manifest(filepath)
            if success:
                results['success'].append(filepath)
            else:
                results['failed'].append(filepath)
        
        # Track deployment
        deployment_record = {
            'timestamp': datetime.now().isoformat(),
            'manifests_applied': len(results['success']),
            'manifests_failed': len(results['failed']),
            'status': 'success' if not results['failed'] else 'partial_failure'
        }
        self.deployment_history.append(deployment_record)
        self.deployment_history = self.deployment_history[-100:]
        
        logger.info(
            f"Deployment complete: {len(results['success'])} succeeded, "
            f"{len(results['failed'])} failed"
        )
        
        return results

    def get_deployment_status(self, deployment_name='gitops-demo-app'):
        """Get the current status of a deployment."""
        result = self._run_kubectl([
            'get', 'deployment', deployment_name,
            '-n', self.namespace,
            '-o', 'json'
        ])
        
        if result and result.returncode == 0:
            import json
            try:
                deployment = json.loads(result.stdout)
                status = deployment.get('status', {})
                spec = deployment.get('spec', {})
                
                containers = spec.get('template', {}).get('spec', {}).get('containers', [])
                current_image = containers[0]['image'] if containers else 'unknown'
                self.current_image = current_image
                
                return {
                    'name': deployment_name,
                    'replicas': spec.get('replicas', 0),
                    'ready_replicas': status.get('readyReplicas', 0),
                    'available_replicas': status.get('availableReplicas', 0),
                    'unavailable_replicas': status.get('unavailableReplicas', 0),
                    'updated_replicas': status.get('updatedReplicas', 0),
                    'current_image': current_image,
                    'conditions': status.get('conditions', []),
                    'observed_generation': status.get('observedGeneration', 0)
                }
            except Exception as e:
                logger.error(f"Error parsing deployment status: {e}")
                return None
        return None

    def get_pods_status(self, app_label='gitops-demo-app'):
        """Get status of all pods for the app."""
        result = self._run_kubectl([
            'get', 'pods', '-n', self.namespace,
            '-l', f'app={app_label}',
            '-o', 'json'
        ])
        
        if result and result.returncode == 0:
            import json
            try:
                pods_data = json.loads(result.stdout)
                pods = []
                for pod in pods_data.get('items', []):
                    pod_status = pod.get('status', {})
                    container_statuses = pod_status.get('containerStatuses', [])
                    
                    restart_count = 0
                    if container_statuses:
                        restart_count = container_statuses[0].get('restartCount', 0)
                    
                    pods.append({
                        'name': pod['metadata']['name'],
                        'phase': pod_status.get('phase', 'Unknown'),
                        'restart_count': restart_count,
                        'ready': all(
                            cs.get('ready', False) 
                            for cs in container_statuses
                        ),
                        'start_time': pod_status.get('startTime', '')
                    })
                return pods
            except Exception as e:
                logger.error(f"Error parsing pods status: {e}")
                return []
        return []

    def wait_for_rollout(self, deployment_name='gitops-demo-app', timeout=180):
        """Wait for a deployment rollout to complete."""
        logger.info(f"Waiting for rollout of {deployment_name}...")
        
        result = self._run_kubectl([
            'rollout', 'status', 'deployment', deployment_name,
            '-n', self.namespace,
            f'--timeout={timeout}s'
        ])
        
        if result and result.returncode == 0:
            logger.info(f"Rollout completed successfully for {deployment_name}")
            return True
        else:
            logger.error(f"Rollout failed or timed out for {deployment_name}")
            return False

    def get_rollout_history(self, deployment_name='gitops-demo-app'):
        """Get rollout history of a deployment."""
        result = self._run_kubectl([
            'rollout', 'history', 'deployment', deployment_name,
            '-n', self.namespace
        ])
        
        if result and result.returncode == 0:
            return result.stdout
        return "No history available"

    def get_deployment_history(self):
        """Get controller's deployment history."""
        return self.deployment_history