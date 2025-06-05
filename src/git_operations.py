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
    
    def commit_and_push(self, output_files: List[str], commit_message: str, branch_name: Optional[str] = None) -> Optional[str]:
        """
        Commit and push changes to a branch
        
        Args:
            output_files: List of files to commit
            commit_message: Commit message
            branch_name: Optional custom branch name to use
            
        Returns:
            Branch name if successful, None otherwise
        """
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
            
            # Use provided branch name or create a new one
            if not branch_name:
                branch_name = f"translation-{uuid.uuid4().hex[:8]}"
            
            # Check if branch exists
            code, stdout, _ = self.run_command(['git', 'branch', '--list', branch_name])
            branch_exists = stdout.strip() != ""
            
            if branch_exists:
                # Checkout existing branch
                code, _, stderr = self.run_command(['git', 'checkout', branch_name])
                if code != 0:
                    print(f"Error checking out existing branch: {stderr}")
                    return None
            else:
                # Create and checkout new branch
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
            print(f"  ✅ Added {added_files}/{len(output_files)} files to git staging area")
            
            # Commit
            print(f"📦 Committing changes...")
            code, stdout, stderr = self.run_command(['git', 'commit', '-m', commit_message])
            if code != 0:
                if "nothing to commit" in stderr:
                    print("  ℹ️ No changes to commit")
                    return None
                print(f"  ❌ Error committing changes: {stderr}")
                return None
            else:
                # Extract commit hash from output
                commit_hash = ""
                for line in stdout.splitlines():
                    if line.startswith("["): # Usually like [branch hash] message
                        parts = line.split()
                        if len(parts) > 1:
                            commit_hash = parts[1]
                            break
                if commit_hash:
                    print(f"  ✅ Changes committed successfully (commit: {commit_hash})")
                else:
                    print(f"  ✅ Changes committed successfully")
            
            # Push
            print(f"🚀 Pushing changes to remote branch '{branch_name}'...")
            code, stdout, stderr = self.run_command(['git', 'push', '-u', 'origin', branch_name])
            if code != 0:
                print(f"  ❌ Error pushing branch: {stderr}")
                return None
            else:
                print(f"  ✅ Successfully pushed changes to branch: {branch_name}")
            return branch_name
        except Exception as e:
            print(f"Error in commit and push: {e}")
            return None
    
    def create_pull_request(self, branch_name: str, title: str, body_lines: List[str], draft: bool = False) -> Optional[int]:
        """Create a pull request using GitHub CLI or API
        
        Args:
            branch_name: The name of the branch to create PR from
            title: PR title
            body_lines: List of strings to form the PR body
            draft: Whether to create PR as draft
            
        Returns:
            PR number if successful, None otherwise
        """
        if not self.in_github_actions:
            print("🔄 Not running in GitHub Actions, skipping PR creation")
            return None
        
        if not branch_name or not self.github_token or not self.github_repository:
            print("⚠️ Missing required information for PR creation")
            return None
        
        # Format PR body
        body = "\n".join(body_lines)
        
        print(f"🔄 Creating {'draft ' if draft else ''}PR from branch '{branch_name}'")
        print(f"  📝 PR Title: {title}")
        print(f"  📊 PR Body length: {len(body)} characters")
        
        # Try using GitHub CLI first
        print("  🛠️ Attempting to create PR using GitHub CLI...")
        pr_number = self._try_create_pr_with_cli(title, body, draft)
        if pr_number is not None:
            print(f"  ✅ PR #{pr_number} created successfully using GitHub CLI")
            return pr_number
        
        # Fall back to GitHub API
        print("  🔄 Falling back to GitHub API for PR creation...")
        pr_number = self._try_create_pr_with_api(branch_name, title, body, draft)
        if pr_number is not None:
            print(f"  ✅ PR #{pr_number} created successfully using GitHub API")
        else:
            print("  ❌ Failed to create PR using both GitHub CLI and API")
        return pr_number
    
    def _try_create_pr_with_cli(self, title: str, body: str, draft: bool = False) -> Optional[int]:
        """Try to create PR using GitHub CLI
        
        Returns:
            PR number if successful, None otherwise
        """
        try:
            cmd = ['gh', 'pr', 'create', '--title', title, '--body', body, '--base', 'main']
            if draft:
                cmd.append('--draft')
            
            print(f"    🔄 Running GitHub CLI command: gh pr create...")
            code, stdout, stderr = self.run_command(cmd)
            if code == 0:
                # Try to extract PR number from stdout (usually contains the PR URL)
                pr_url = stdout.strip()
                pr_number = self._extract_pr_number_from_url(pr_url)
                if pr_number:
                    print(f"    ✅ PR #{pr_number} created successfully")
                    print(f"    🔗 PR URL: {pr_url}")
                    return pr_number
                else:
                    print(f"    ⚠️ PR created but couldn't extract PR number from URL: {pr_url}")
                    return None
            print(f"    ❌ Failed to create PR with GitHub CLI: {stderr}")
            return None
        except Exception as e:
            print(f"GitHub CLI not available or error: {e}")
            return None
            
    def _extract_pr_number_from_url(self, pr_url: str) -> Optional[int]:
        """Extract PR number from GitHub PR URL
        
        Args:
            pr_url: GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
            
        Returns:
            PR number if found, None otherwise
        """
        try:
            # Try to extract PR number from URL
            if '/pull/' in pr_url:
                pr_number = int(pr_url.split('/pull/')[1].split('/')[0].split('#')[0])
                return pr_number
            return None
        except Exception:
            return None
    
    def _try_create_pr_with_api(self, branch_name: str, title: str, body: str, draft: bool = False) -> Optional[int]:
        """Try to create PR using GitHub API
        
        Args:
            branch_name: The name of the branch to create PR from
            title: PR title
            body: PR body
            draft: Whether to create PR as draft
            
        Returns:
            PR number if successful, None otherwise
        """
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
                'base': base_branch,
                'draft': draft
            }
            
            response = requests.post(url, headers=headers, json=data)
            if response.status_code in (200, 201):
                pr_data = response.json()
                pr_url = pr_data.get('html_url', '')
                pr_number = pr_data.get('number')
                print(f"Pull request #{pr_number} created successfully: {pr_url}")
                return pr_number
            else:
                print(f"Error creating pull request via API: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error creating pull request via API: {e}")
            return None
    
    def update_pull_request(self, pr_number: int, title: str = None, body: str = None) -> bool:
        """Update an existing pull request
        
        Args:
            pr_number: PR number to update
            title: New PR title (optional)
            body: New PR body (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.in_github_actions or not self.github_token or not self.github_repository:
            print("🔄 Not running in GitHub Actions or missing credentials, skipping PR update")
            return False
            
        try:
            # Extract owner and repo from GITHUB_REPOSITORY
            owner, repo = self.github_repository.split('/')
            
            print(f"🔄 Updating PR #{pr_number} via GitHub API...")
            if title is not None:
                print(f"  📝 New PR title: {title}")
            if body is not None:
                print(f"  📊 New PR body length: {len(body)} characters")
            
            # Update PR using GitHub API
            url = f"{self.github_api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Only include fields that need to be updated
            data = {}
            if title is not None:
                data['title'] = title
            if body is not None:
                data['body'] = body
                
            # Only make API call if there's something to update
            if data:
                print(f"  🛠️ Making API request to {url}")
                response = requests.patch(url, headers=headers, json=data)
                if response.status_code in (200, 201):
                    print(f"  ✅ Pull request #{pr_number} updated successfully (Status: {response.status_code})")
                    return True
                else:
                    print(f"  ❌ Error updating pull request via API: {response.status_code} - {response.text}")
                    return False
            else:
                print("  ℹ️ No changes to update in PR")
            return True
        except Exception as e:
            print(f"  Error updating pull request via API: {e}")
            return False
    
    def mark_pr_ready_for_review(self, pr_number: int) -> bool:
        """Mark a pull request as ready for review using GitHub CLI
        
        Args:
            pr_number: PR number to mark as ready
            
        Returns:
            True if successful, False otherwise
        """
        if not self.in_github_actions:
            print("🔄 Not running in GitHub Actions, skipping PR ready for review")
            return False
            
        try:
            # 确保 GitHub CLI 已经安装并配置
            # GitHub Actions 环境中已预装 gh CLI
            print(f"🚀 Marking PR #{pr_number} as ready for review using GitHub CLI...")
            
            # 使用 GitHub CLI 将 PR 标记为 ready for review
            # 这是 GitHub Actions 环境中最可靠的方法
            code, stdout, stderr = self.run_command(['gh', 'pr', 'ready', str(pr_number)])
            
            if code == 0:
                print(f"  ✅ Pull request #{pr_number} marked as ready for review successfully")
                if stdout.strip():
                    print(f"  💬 Output: {stdout.strip()}")
                return True
            else:
                print(f"  ❌ Failed to mark PR as ready for review: {stderr}")
                return False
        except Exception as e:
            print(f"  ❌ Error marking PR as ready for review: {e}")
            return False
            
    def _mark_ready_using_rest_api(self, owner: str, repo: str, pr_number: int) -> bool:
        """Try to mark PR as ready for review using REST API"""
        try:
            # Ready for review endpoint - using PATCH to update draft status
            url = f"{self.github_api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'X-GitHub-Api-Version': '2022-11-28'
            }
            
            # Set draft to false to mark as ready for review
            data = {
                'draft': False
            }
            
            print(f"  🛠️ Making REST API request to {url}")
            response = requests.patch(url, headers=headers, json=data)
            
            if response.status_code in (200, 201):
                print(f"  ✅ REST API: Pull request #{pr_number} marked as ready for review (Status: {response.status_code})")
                return True
            else:
                print(f"  ❌ REST API failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"  ❌ REST API error: {e}")
            return False
            
    def _mark_ready_using_graphql_api(self, owner: str, repo: str, pr_number: int) -> bool:
        """Try to mark PR as ready for review using GraphQL API"""
        try:
            # GraphQL endpoint
            url = "https://api.github.com/graphql"
            headers = {
                'Authorization': f'bearer {self.github_token}',
                'Content-Type': 'application/json'
            }
            
            # First, get the PR node ID
            query_pr = f"""
            query {{
              repository(owner: "{owner}", name: "{repo}") {{
                pullRequest(number: {pr_number}) {{
                  id
                }}
              }}
            }}
            """
            
            print(f"  🛠️ Getting PR node ID using GraphQL")
            response = requests.post(url, headers=headers, json={'query': query_pr})
            
            if response.status_code != 200:
                print(f"  ❌ GraphQL query failed: {response.status_code} - {response.text}")
                return False
                
            data = response.json()
            if 'errors' in data:
                print(f"  ❌ GraphQL errors: {data['errors']}")
                return False
                
            pr_id = data.get('data', {}).get('repository', {}).get('pullRequest', {}).get('id')
            if not pr_id:
                print(f"  ❌ Could not get PR node ID")
                return False
                
            # Now mark the PR as ready for review
            ready_mutation = f"""
            mutation {{
              markPullRequestReadyForReview(input: {{pullRequestId: "{pr_id}"}}) {{
                pullRequest {{
                  number
                  url
                }}
              }}
            }}
            """
            
            print(f"  🛠️ Marking PR as ready using GraphQL mutation")
            response = requests.post(url, headers=headers, json={'query': ready_mutation})
            
            if response.status_code != 200:
                print(f"  ❌ GraphQL mutation failed: {response.status_code} - {response.text}")
                return False
                
            data = response.json()
            if 'errors' in data:
                print(f"  ❌ GraphQL mutation errors: {data['errors']}")
                return False
                
            pr_url = data.get('data', {}).get('markPullRequestReadyForReview', {}).get('pullRequest', {}).get('url')
            if pr_url:
                print(f"  ✅ GraphQL API: Pull request #{pr_number} marked as ready for review")
                print(f"  🔗 PR URL: {pr_url}")
                return True
            else:
                print(f"  ❌ GraphQL mutation did not return PR URL")
                return False
        except Exception as e:
            print(f"  ❌ GraphQL API error: {e}")
            return False
            
    def _mark_ready_using_gh_cli(self, pr_number: int) -> bool:
        """Try to mark PR as ready for review using GitHub CLI"""
        try:
            print(f"  🛠️ Attempting to use 'gh pr ready {pr_number}' command")
            code, stdout, stderr = self.run_command(['gh', 'pr', 'ready', str(pr_number)])
            
            if code == 0:
                print(f"  ✅ GitHub CLI: Pull request #{pr_number} marked as ready for review")
                if stdout.strip():
                    print(f"  💬 CLI output: {stdout.strip()}")
                return True
            else:
                print(f"  ❌ GitHub CLI failed: {stderr}")
                return False
        except Exception as e:
            print(f"  ❌ GitHub CLI error: {e}")
            return False
