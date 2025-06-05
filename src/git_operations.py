#!/usr/bin/env python3

import os
import sys
import subprocess
import json
import uuid
import requests
from typing import List, Dict, Optional, Any, Tuple


class GitOperations:
    """Handles all Git operations for the translation workflow"""
    
    def __init__(self, config):
        self.config = config
        
        # GitHub-specific environment variables
        self.github_token = self._get_github_token()
        self.github_repository = os.getenv('GITHUB_REPOSITORY', '')
        self.github_server_url = os.getenv('GITHUB_SERVER_URL', 'https://github.com')
        self.github_api_url = os.getenv('GITHUB_API_URL', 'https://api.github.com')
        self.github_ref = os.getenv('GITHUB_REF', '')
        self.github_actor = os.getenv('GITHUB_ACTOR', '')
        
        # Determine if running in GitHub Actions
        self.in_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
    
    def _get_github_token(self) -> str:
        """Get GitHub token from environment variables"""
        token = os.getenv('GITHUB_TOKEN', '')
        if not token:
            token = os.getenv('INPUT_GITHUB_TOKEN', '')
        if not token:
            token = os.getenv('INPUT_TOKEN', '')
        return token
    
    def run_command(self, command: List[str], check: bool = True) -> Tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, and stderr"""
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
            print("Not running in GitHub Actions, skipping Git setup")
            return True
        
        try:
            # Add GitHub workspace as safe directory to fix ownership issues
            code, _, stderr = self.run_command(['git', 'config', '--global', '--add', 'safe.directory', '/github/workspace'])
            if code != 0:
                print(f"Warning: Failed to set safe.directory: {stderr}")
            
            # Configure Git user - use global config to ensure it's applied everywhere
            code, _, stderr = self.run_command(['git', 'config', '--global', 'user.name', 'github-actions[bot]'])
            if code != 0:
                print(f"Error setting git user.name: {stderr}")
                return False
                
            code, _, stderr = self.run_command(['git', 'config', '--global', 'user.email', 'github-actions[bot]@users.noreply.github.com'])
            if code != 0:
                print(f"Error setting git user.email: {stderr}")
                return False
            
            # Verify the configuration was set correctly
            code, stdout, _ = self.run_command(['git', 'config', '--get', 'user.name'])
            if code != 0 or not stdout.strip():
                print("Warning: Failed to verify git user.name configuration")
            else:
                print(f"Git user.name configured as: {stdout.strip()}")
                
            code, stdout, _ = self.run_command(['git', 'config', '--get', 'user.email'])
            if code != 0 or not stdout.strip():
                print("Warning: Failed to verify git user.email configuration")
            else:
                print(f"Git user.email configured as: {stdout.strip()}")
            
            # Set remote URL with token for authentication
            if self.github_token and self.github_repository:
                remote_url = f"https://x-access-token:{self.github_token}@github.com/{self.github_repository}.git"
                code, _, stderr = self.run_command(['git', 'remote', 'set-url', 'origin', remote_url])
                if code != 0:
                    print(f"Error setting git remote URL: {stderr}")
                    return False
            
            return True
        except Exception as e:
            print(f"Error setting up Git: {e}")
            return False
    
    def commit_and_push(self, output_files: List[str], commit_message: str, batch_suffix: str = "") -> Optional[str]:
        """Commit changes and push to remote, return branch name if created"""
        if not self.in_github_actions:
            print("Not running in GitHub Actions, skipping commit and push")
            return None
        
        # Ensure Git is properly set up before committing
        if not self.setup_git():
            print("Failed to set up Git configuration, cannot commit changes")
            return None
        
        try:
            # Check if there are any changes to commit
            code, stdout, _ = self.run_command(['git', 'status', '--porcelain'])
            if code != 0:
                print("Error checking git status")
                return None
            
            if not stdout.strip():
                print("No changes to commit")
                return None
            
            # Create a new branch for the PR with optional batch suffix
            branch_name = f"translation{batch_suffix}-{uuid.uuid4().hex[:8]}"
            
            # Create and checkout branch
            code, _, stderr = self.run_command(['git', 'checkout', '-b', branch_name])
            if code != 0:
                print(f"Error creating branch: {stderr}")
                return None
            
            # Add files
            for file in output_files:
                self.run_command(['git', 'add', file])
            
            # Commit
            code, _, stderr = self.run_command(['git', 'commit', '-m', commit_message])
            if code != 0:
                if "nothing to commit" in stderr:
                    print("No changes to commit")
                    return None
                print(f"Error committing changes: {stderr}")
                return None
            
            # Push
            code, _, stderr = self.run_command(['git', 'push', '-u', 'origin', branch_name])
            if code != 0:
                print(f"Error pushing branch: {stderr}")
                return None
            
            print(f"Successfully pushed changes to branch: {branch_name}")
            return branch_name
        except Exception as e:
            print(f"Error in commit and push: {e}")
            return None
    
    def create_pull_request(self, branch_name: str, title: str, body_lines: List[str]) -> bool:
        """Create a pull request using GitHub CLI or API"""
        if not self.in_github_actions:
            print("Not running in GitHub Actions, skipping PR creation")
            return False
        
        if not branch_name or not self.github_token or not self.github_repository:
            print("Missing required information for PR creation")
            return False
        
        # Format PR body
        body = "\n".join(body_lines)
        
        # Try using GitHub CLI first
        if self._try_create_pr_with_cli(title, body):
            return True
        
        # Fall back to GitHub API
        return self._try_create_pr_with_api(branch_name, title, body)
    
    def _try_create_pr_with_cli(self, title: str, body: str) -> bool:
        """Try to create PR using GitHub CLI"""
        try:
            code, _, _ = self.run_command(['gh', 'pr', 'create', '--title', title, '--body', body, '--base', 'main'])
            if code == 0:
                print("Pull request created successfully using GitHub CLI")
                return True
            return False
        except Exception as e:
            print(f"GitHub CLI not available or error: {e}")
            return False
    
    def _try_create_pr_with_api(self, branch_name: str, title: str, body: str) -> bool:
        """Try to create PR using GitHub API"""
        try:
            # Extract owner and repo from GITHUB_REPOSITORY
            owner, repo = self.github_repository.split('/')
            
            # Determine base branch
            base_branch = 'main'
            if self.github_ref and self.github_ref.startswith('refs/heads/'):
                base_branch = self.github_ref.replace('refs/heads/', '')
            
            # Create PR using GitHub API
            url = f"{self.github_api_url}/repos/{owner}/{repo}/pulls"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            data = {
                'title': title,
                'body': body,
                'head': branch_name,
                'base': base_branch
            }
            
            response = requests.post(url, headers=headers, json=data)
            if response.status_code in (200, 201):
                pr_url = response.json().get('html_url', '')
                print(f"Pull request created successfully: {pr_url}")
                return True
            else:
                print(f"Error creating pull request via API: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Error creating pull request via API: {e}")
            return False
