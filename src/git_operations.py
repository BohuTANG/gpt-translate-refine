#!/usr/bin/env python3

import os
import subprocess
import json
import uuid
import requests
from typing import List, Dict, Optional, Tuple


class GitOperations:
    """Handles Git operations for translation workflow"""
    
    def __init__(self, config):
        self.config = config
        
        # GitHub environment variables
        self.github_token = self._get_github_token()
        self.github_repository = os.getenv('GITHUB_REPOSITORY', '')
        self.github_server_url = os.getenv('GITHUB_SERVER_URL', 'https://github.com')
        self.github_api_url = os.getenv('GITHUB_API_URL', 'https://api.github.com')
        self.github_ref = os.getenv('GITHUB_REF', '')
        self.github_actor = os.getenv('GITHUB_ACTOR', '')
        
        self.in_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
        print(f"GitOps: Initializing. Running in GitHub Actions: {self.in_github_actions}")
    
    def _get_github_token(self) -> str:
        """Get GitHub token from environment"""
        for env_var in ['GITHUB_TOKEN', 'INPUT_GITHUB_TOKEN', 'INPUT_TOKEN']:
            if token := os.getenv(env_var, ''):
                return token
        return ''
    
    def run_command(self, command: List[str]) -> Tuple[int, str, str]:
        """Run shell command and return exit code, stdout, stderr"""
        try:
            process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            return process.returncode, process.stdout, process.stderr
        except Exception as e:
            print(f"Error running command {' '.join(command)}: {e}")
            return 1, "", str(e)
    
    def setup_git(self) -> bool:
        """Set up Git configuration for GitHub Actions"""
        if not self.in_github_actions:
            # This print is fine for local testing clarity
            # print("GitOps: Not running in GitHub Actions, skipping Git setup.") 
            return True
        print("GitOps: Setting up Git configuration for GitHub Actions...")
        
        try:
            # Configure safe directory
            self.run_command(['git', 'config', '--global', '--add', 'safe.directory', '/github/workspace'])
            
            # Configure Git user
            commands = [
                (['git', 'config', '--global', 'user.name', 'github-actions[bot]'], 'user.name'),
                (['git', 'config', '--global', 'user.email', 'github-actions[bot]@users.noreply.github.com'], 'user.email')
            ]
            
            for cmd, setting in commands:
                code, _, stderr = self.run_command(cmd)
                if code != 0:
                    print(f"Error setting git {setting}: {stderr}")
                    return False
            
            # Set remote URL with token
            if self.github_token and self.github_repository:
                remote_url = f"https://x-access-token:{self.github_token}@github.com/{self.github_repository}.git"
                code, _, stderr = self.run_command(['git', 'remote', 'set-url', 'origin', remote_url])
                if code != 0:
                    print(f"Error setting git remote URL: {stderr}")
                    return False
            
            print("GitOps: Git configuration setup successful.")
            return True
        except Exception as e:
            print(f"GitOps: Error setting up Git: {e}")
            return False
    
    def commit_and_push(self, output_files: List[str], commit_message: str, 
                       branch_name: Optional[str] = None) -> Optional[str]:
        """Commit and push changes to branch"""
        if not self.in_github_actions:
            # print("GitOps: Not running in GitHub Actions, skipping commit and push.")
            return None
        
        target_branch_name = branch_name or f"translation-{uuid.uuid4().hex[:8]}" # Determine early for logging
        print(f"GitOps: Attempting to commit and push to branch: {target_branch_name}")
        
        if not self.setup_git():
            print("Failed to set up Git configuration")
            return None
        
        try:
            # Check for changes
            code, stdout, _ = self.run_command(['git', 'status', '--porcelain'])
            if code != 0 or not stdout.strip():
                print("GitOps: No changes detected to commit.")
                return None
            
            # Create or checkout branch
            branch_name = target_branch_name # Use the already determined name
            
            code, stdout, _ = self.run_command(['git', 'branch', '--list', branch_name])
            if stdout.strip():
                # Checkout existing branch
                code, _, stderr = self.run_command(['git', 'checkout', branch_name])
                if code != 0:
                    print(f"Error checking out branch: {stderr}")
                    return None
            else:
                # Create new branch
                code, _, stderr = self.run_command(['git', 'checkout', '-b', branch_name])
                if code != 0:
                    print(f"Error creating branch: {stderr}")
                    return None
            
            # Add files
            print(f"📝 Adding {len(output_files)} files to git...")
            added_files = 0
            for file in output_files:
                code, _, stderr = self.run_command(['git', 'add', file])
                if code == 0:
                    added_files += 1
                else:
                    print(f"  ⚠️ Failed to add file: {file} - {stderr}")
            
            print(f"  ✅ Added {added_files}/{len(output_files)} files")
            
            # Commit
            print("📦 Committing changes...")
            code, stdout, stderr = self.run_command(['git', 'commit', '-m', commit_message])
            if code != 0:
                if "nothing to commit" in stderr:
                    print("  ℹ️ No changes to commit")
                    return None
                print(f"  ❌ Error committing: {stderr}")
                return None
            
            print("  GitOps: Changes committed successfully.")
            
            # Push
            print(f"🚀 Pushing to branch '{branch_name}'...")
            code, _, stderr = self.run_command(['git', 'push', '-u', 'origin', branch_name])
            if code != 0:
                print(f"  ❌ Error pushing: {stderr}")
                return None
            
            print(f"  GitOps: Successfully pushed to branch: {branch_name}.")
            return branch_name
            
        except Exception as e:
            print(f"GitOps: Error in commit and push: {e}")
            return None
    
    def create_pull_request(self, branch_name: str, title: str, body_lines: List[str], 
                          draft: bool = False) -> Optional[int]:
        """Create pull request using GitHub CLI or API"""
        if not self.in_github_actions or not all([branch_name, self.github_token, self.github_repository]):
            print("GitOps: Missing requirements for PR creation (not in Actions, or missing token/repo/branch_name).")
            return None
        
        body = "\n".join(body_lines)
        # Determine base branch for logging, similar to how it's done in _create_pr_with_api
        base_branch_for_log = 'main'
        if self.github_ref and self.github_ref.startswith('refs/heads/'):
            base_branch_for_log = self.github_ref.replace('refs/heads/', '')
        print(f"GitOps: Creating {'draft ' if draft else ''}PR from branch '{branch_name}' to base '{base_branch_for_log}'.")
        
        # Try GitHub CLI first
        if pr_number := self._create_pr_with_cli(title, body, draft):
            # CLI helper will log its own success/failure
            return pr_number
        
        # Fallback to API
        if pr_number := self._create_pr_with_api(branch_name, title, body, draft):
            # API helper will log its own success/failure
            return pr_number
        
        print("GitOps: Failed to create Pull Request (both CLI and API methods failed or were skipped).")
        return None
    
    def _create_pr_with_cli(self, title: str, body: str, draft: bool = False) -> Optional[int]:
        """Create PR using GitHub CLI"""
        try:
            cmd = ['gh', 'pr', 'create', '--title', title, '--body', body, '--base', 'main']
            if draft:
                cmd.append('--draft')
            
            code, stdout, stderr = self.run_command(cmd)
            if code == 0:
                pr_url = stdout.strip()
                if '/pull/' in pr_url:
                    pr_number = int(pr_url.split('/pull/')[1].split('/')[0])
                    print(f"  GitOps: PR #{pr_number} created via CLI. URL: {pr_url}")
                    return pr_number
            
            print(f"  GitOps: GitHub CLI PR creation failed: {stderr}")
            return None
        except Exception as e:
            print(f"GitOps: GitHub CLI error during PR creation: {e}")
            return None
    
    def _create_pr_with_api(self, branch_name: str, title: str, body: str, 
                          draft: bool = False) -> Optional[int]:
        """Create PR using GitHub API"""
        try:
            owner, repo = self.github_repository.split('/')
            base_branch = 'main'
            if self.github_ref and self.github_ref.startswith('refs/heads/'):
                base_branch = self.github_ref.replace('refs/heads/', '')
            
            url = f"{self.github_api_url}/repos/{owner}/{repo}/pulls"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            data = {
                'title': title,
                'body': body,
                'head': branch_name,
                'base': base_branch,
                'draft': draft
            }
            
            response = requests.post(url, headers=headers, json=data)
            if response.status_code in (200, 201):
                pr_data = response.json()
                pr_number = pr_data.get('number')
                pr_url = pr_data.get('html_url', '')
                print(f"  GitOps: PR #{pr_number} created via API. URL: {pr_url}")
                return pr_number
            else:
                print(f"  GitOps: GitHub API PR creation failed. Status: {response.status_code}, Response: {response.text[:200]}") # Truncate response
                return None
        except Exception as e:
            print(f"GitOps: GitHub API error during PR creation: {e}")
            return None
    
    def update_pull_request(self, pr_number: int, title: str = None, body: str = None) -> bool:
        """Update existing pull request"""
        if not self.in_github_actions or not all([self.github_token, self.github_repository]):
            print("GitOps: Missing requirements for PR update (not in Actions, or missing token/repo).")
            return False
        
        update_details = []
        if title is not None:
            update_details.append(f"title to '{title}'")
        if body is not None:
            update_details.append("body/summary")
        
        if not update_details:
            print(f"GitOps: No updates specified for PR #{pr_number}. Skipping.")
            return True # No action needed, considered success
        
        print(f"GitOps: Updating PR #{pr_number}: setting {' and '.join(update_details)}...")
        
        try:
            owner, repo = self.github_repository.split('/')
            url = f"{self.github_api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            data = {}
            if title is not None:
                data['title'] = title
            if body is not None:
                data['body'] = body
            
            if data:
                response = requests.patch(url, headers=headers, json=data)
                if response.status_code in (200, 201):
                    print(f"  GitOps: PR #{pr_number} API update successful.")
                    return True
                else:
                    print(f"  GitOps: Failed to update PR #{pr_number}. Status: {response.status_code}, Response: {response.text[:200]}") # Truncate response
                    return False
            else:
                # This case should ideally not be reached if we check for empty data earlier
                print(f"  GitOps: No data provided for PR #{pr_number} update.")
                return True # No changes made, but not an error
        except Exception as e:
            print(f"GitOps: Error updating PR #{pr_number}: {e}")
            return False
    
    def mark_pr_ready_for_review(self, pr_number: int) -> bool:
        """Mark PR as ready for review using GitHub CLI"""
        if not self.in_github_actions:
            # print("GitOps: Not in GitHub Actions, skipping mark PR ready.")
            return False
        
        try:
            print(f"GitOps: Marking PR #{pr_number} as ready for review...")
            code, stdout, stderr = self.run_command(['gh', 'pr', 'ready', str(pr_number)])
            
            if code == 0:
                print(f"  GitOps: PR #{pr_number} marked as ready for review.")
                return True
            else:
                print(f"  GitOps: Failed to mark PR #{pr_number} as ready. CLI stderr: {stderr}")
                return False
        except Exception as e:
            print(f"  GitOps: Error marking PR #{pr_number} as ready: {e}")
            return False
