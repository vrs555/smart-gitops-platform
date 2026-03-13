# gitops-controller/rollback_manager.py
"""
Rollback Manager Module
Handles automatic rollback when unhealthy deployments are detected.
"""
import subprocess
import logging
import time
from datetime import datetime
from config import Config

logger = logging.getLogger('gitops.rollback_manager')


class RollbackManager:
    def __init__(self):
        self.rollback_history = []
        self.rollback_count = 0
        self.last_rollback_time = None
        self.cooldown_seconds = Config.ROLLBACK_COOLDOWN
        self.max_rollbacks = Config.MAX_ROLLBACK_ATTEMPTS
        self.is_in_cooldown = False
        
    def _run_kubectl(self, args):
        """Run a kubectl command."""
        cmd = ['kubectl'] + args
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            return result
        except Exception as e:
            logger.error(f"kubectl error: {e}")
            return None

    def can_rollback(self):
        """Check if rollback is allowed (cooldown and max attempts)."""
        # Check cooldown
        if self.last_rollback_time:
            elapsed = time.time() - self.last_rollback_time
            if elapsed < self.cooldown_seconds:
                remaining = int(self.cooldown_seconds - elapsed)
                logger.warning(
                    f"Rollback cooldown active. {remaining}s remaining."
                )
                self.is_in_cooldown = True
                return False
        
        self.is_in_cooldown = False
        
        # Check max rollback attempts (reset counter after successful period)
        if self.rollback_count >= self.max_rollbacks:
            logger.error(
                f"Maximum rollback attempts ({self.max_rollbacks}) reached! "
                f"Manual intervention required."
            )
            return False
        
        return True

    def rollback_deployment(
        self, 
        deployment_name='gitops-demo-app', 
        namespace=None,
        reason='Automatic rollback due to unhealthy deployment'
    ):
        """Perform a rollback to the previous deployment version."""
        namespace = namespace or Config.K8S_NAMESPACE
        
        if not self.can_rollback():
            return {
                'success': False,
                'reason': 'Rollback not allowed (cooldown or max attempts)'
            }
        
        logger.warning(
            f"🔄 INITIATING ROLLBACK for {deployment_name} | Reason: {reason}"
        )
        
        # Get current revision before rollback
        current_revision = self._get_current_revision(
            deployment_name, namespace
        )
        
        # Perform rollback
        result = self._run_kubectl([
            'rollout', 'undo', 'deployment', deployment_name,
            '-n', namespace
        ])
        
        if result and result.returncode == 0:
            logger.info(f"Rollback command executed successfully")
            
            # Wait for rollback to complete
            time.sleep(5)
            rollout_result = self._run_kubectl([
                'rollout', 'status', 'deployment', deployment_name,
                '-n', namespace, '--timeout=120s'
            ])
            
            rollback_success = (
                rollout_result and rollout_result.returncode == 0
            )
            
            # Get new revision after rollback
            new_revision = self._get_current_revision(
                deployment_name, namespace
            )
            
            # Record rollback
            rollback_record = {
                'timestamp': datetime.now().isoformat(),
                'deployment': deployment_name,
                'namespace': namespace,
                'reason': reason,
                'from_revision': current_revision,
                'to_revision': new_revision,
                'success': rollback_success,
                'rollback_number': self.rollback_count + 1
            }
            
            self.rollback_history.append(rollback_record)
            self.rollback_count += 1
            self.last_rollback_time = time.time()
            
            if rollback_success:
                logger.info(
                    f"✅ Rollback SUCCESSFUL! "
                    f"Revision {current_revision} → {new_revision}"
                )
            else:
                logger.error(
                    f"❌ Rollback completed but rollout status check failed"
                )
            
            return {
                'success': rollback_success,
                'details': rollback_record
            }
        else:
            stderr = result.stderr if result else 'Command failed'
            logger.error(f"Rollback FAILED: {stderr}")
            
            rollback_record = {
                'timestamp': datetime.now().isoformat(),
                'deployment': deployment_name,
                'reason': reason,
                'success': False,
                'error': stderr
            }
            self.rollback_history.append(rollback_record)
            
            return {
                'success': False,
                'error': stderr,
                'details': rollback_record
            }

    def _get_current_revision(self, deployment_name, namespace):
        """Get current revision number of a deployment."""
        result = self._run_kubectl([
            'get', 'deployment', deployment_name,
            '-n', namespace,
            '-o', 'jsonpath={.metadata.annotations.deployment\\.kubernetes\\.io/revision}'
        ])
        if result and result.returncode == 0:
            return result.stdout.strip()
        return 'unknown'

    def reset_rollback_counter(self):
        """Reset the rollback counter (called after stable period)."""
        if self.rollback_count > 0:
            logger.info("Resetting rollback counter after stable period")
            self.rollback_count = 0

    def get_rollback_status(self):
        """Get current rollback status."""
        return {
            'total_rollbacks': len(self.rollback_history),
            'recent_rollback_count': self.rollback_count,
            'max_rollbacks': self.max_rollbacks,
            'is_in_cooldown': self.is_in_cooldown,
            'last_rollback_time': (
                datetime.fromtimestamp(self.last_rollback_time).isoformat()
                if self.last_rollback_time else None
            ),
            'rollback_history': self.rollback_history[-10:]
        }