# gitops-controller/git_watcher.py
"""
Git Watcher Module
Monitors a GitHub repository for changes and pulls latest manifests.
This replaces ArgoCD's Git sync functionality.
"""
import os
import subprocess
import hashlib
import json
import logging
import time
from datetime import datetime
from config import Config

logger = logging.getLogger('gitops.git_watcher')


class GitWatcher:
    def __init__(self):
        self.repo_url = Config.GIT_REPO_URL
        self.branch = Config.GIT_BRANCH
        self.local_path = Config.LOCAL_REPO_PATH
        self.manifests_path = Config.GIT_MANIFESTS_PATH
        self.last_commit = None
        self.last_sync_time = None
        self.sync_history = []
        
    def _run_git_command(self, args, cwd=None):
        """Run a git command and return output."""
        cmd = ['git'] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.local_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                logger.error(f"Git command failed: {' '.join(cmd)}")
                logger.error(f"stderr: {result.stderr}")
                return None
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"Git command timed out: {' '.join(cmd)}")
            return None
        except Exception as e:
            logger.error(f"Git command error: {e}")
            return None

    def clone_or_pull(self):
        """Clone the repo if it doesn't exist, otherwise pull latest."""
        if not os.path.exists(self.local_path):
            logger.info(f"Cloning repository: {self.repo_url}")
            
            clone_url = self.repo_url
            if Config.GITHUB_TOKEN:
                # Insert token for authentication
                clone_url = self.repo_url.replace(
                    'https://', 
                    f'https://{Config.GITHUB_TOKEN}@'
                )
            
            result = subprocess.run(
                ['git', 'clone', '-b', self.branch, clone_url, self.local_path],
                capture_output=True, text=True, timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"Clone failed: {result.stderr}")
                return False
                
            logger.info("Repository cloned successfully")
            return True
        else:
            logger.debug("Pulling latest changes...")
            
            # Reset any local changes
            self._run_git_command(['checkout', self.branch])
            self._run_git_command(['reset', '--hard', f'origin/{self.branch}'])
            
            result = self._run_git_command(['pull', 'origin', self.branch])
            if result is None:
                return False
                
            logger.debug("Pull completed")
            return True

    def get_current_commit(self):
        """Get the current commit SHA."""
        return self._run_git_command(['rev-parse', 'HEAD'])

    def get_commit_message(self):
        """Get the latest commit message."""
        return self._run_git_command(['log', '-1', '--pretty=%B'])

    def get_commit_author(self):
        """Get the latest commit author."""
        return self._run_git_command(['log', '-1', '--pretty=%an'])

    def has_changes(self):
        """Check if there are new changes in the repository."""
        if not self.clone_or_pull():
            return False, None
            
        current_commit = self.get_current_commit()
        
        if current_commit is None:
            return False, None
            
        if self.last_commit is None:
            # First run — treat as a change
            self.last_commit = current_commit
            logger.info(f"Initial commit detected: {current_commit[:8]}")
            return True, current_commit
            
        if current_commit != self.last_commit:
            logger.info(
                f"New commit detected: {self.last_commit[:8]} → {current_commit[:8]}"
            )
            old_commit = self.last_commit
            self.last_commit = current_commit
            
            # Record sync history
            self.sync_history.append({
                'timestamp': datetime.now().isoformat(),
                'old_commit': old_commit[:8],
                'new_commit': current_commit[:8],
                'message': self.get_commit_message(),
                'author': self.get_commit_author()
            })
            
            # Keep only last 50 entries
            self.sync_history = self.sync_history[-50:]
            
            return True, current_commit
            
        logger.debug(f"No changes. Current commit: {current_commit[:8]}")
        return False, current_commit

    def get_manifest_files(self):
        """Get all YAML manifest files from the repository."""
        manifests_dir = os.path.join(self.local_path, self.manifests_path)
        
        if not os.path.exists(manifests_dir):
            logger.error(f"Manifests directory not found: {manifests_dir}")
            return []
            
        manifest_files = []
        for root, dirs, files in os.walk(manifests_dir):
            for file in sorted(files):
                if file.endswith(('.yaml', '.yml')):
                    full_path = os.path.join(root, file)
                    manifest_files.append(full_path)
                    
        logger.info(f"Found {len(manifest_files)} manifest files")
        return manifest_files

    def get_manifests_hash(self):
        """Generate a hash of all manifest files for change detection."""
        manifest_files = self.get_manifest_files()
        hasher = hashlib.sha256()
        
        for filepath in manifest_files:
            with open(filepath, 'rb') as f:
                hasher.update(f.read())
                
        return hasher.hexdigest()[:12]

    def get_sync_status(self):
        """Get current sync status information."""
        return {
            'repo_url': self.repo_url,
            'branch': self.branch,
            'last_commit': self.last_commit[:8] if self.last_commit else 'N/A',
            'last_sync_time': self.last_sync_time,
            'total_syncs': len(self.sync_history),
            'recent_syncs': self.sync_history[-5:]
        }