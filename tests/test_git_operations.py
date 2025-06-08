import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys

# Mock external dependencies
sys.modules['openai'] = MagicMock()
sys.modules['yaml'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Add src to path to allow direct import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.git_operations import GitOperations
from src.config import Config

class TestGitOperations(unittest.TestCase):

    def setUp(self):
        """Set up a mock config and GitOperations instance."""
        self.mock_config = MagicMock(spec=Config)
        
        # Mock environment variables for a typical GitHub Actions run
        self.patcher = patch.dict(os.environ, {
            'GITHUB_ACTIONS': 'true',
            'GITHUB_TOKEN': 'test_token',
            'GITHUB_REPOSITORY': 'test_owner/test_repo',
            'GITHUB_API_URL': 'https://api.github.com',
            'GITHUB_REF': 'refs/heads/main'
        })
        self.mock_env = self.patcher.start()
        
        self.git_ops = GitOperations(self.mock_config)

    def tearDown(self):
        """Stop the environment patcher."""
        self.patcher.stop()

    @patch('src.git_operations.GitOperations._create_pr_with_cli')
    @patch('src.git_operations.requests')
    def test_create_pull_request_api_call(self, mock_requests, mock_create_pr_with_cli):
        """
        Tests that create_pull_request makes the correct API call
        by simulating a failure in the CLI method.
        """
        # Simulate that the CLI method fails, forcing a fallback to the API method
        mock_create_pr_with_cli.return_value = None
        
        # Configure the mock response from the GitHub API
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'number': 123, 'html_url': 'http://example.com/pr/123'}
        mock_requests.post.return_value = mock_response

        pr_number = self.git_ops.create_pull_request(
            branch_name='test-branch',
            title='Test PR',
            body_lines=['- Line 1', '- Line 2'],
            draft=True
        )

        self.assertEqual(pr_number, 123)
        
        # Verify the API call was made correctly
        expected_url = 'https://api.github.com/repos/test_owner/test_repo/pulls'
        expected_headers = {
            'Authorization': 'token test_token',
            'Accept': 'application/vnd.github.v3+json'
        }
        expected_data = {
            'title': 'Test PR',
            'body': '- Line 1\n- Line 2',
            'head': 'test-branch',
            'base': 'main',
            'draft': True
        }
        mock_requests.post.assert_called_once_with(
            expected_url, headers=expected_headers, json=expected_data
        )

    @patch('src.git_operations.requests')
    def test_update_pull_request_api_call(self, mock_requests):
        """Tests that update_pull_request makes the correct API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.patch.return_value = mock_response

        success = self.git_ops.update_pull_request(
            pr_number=123,
            title='Updated Title',
            body='Updated Body'
        )

        self.assertTrue(success)
        
        expected_url = 'https://api.github.com/repos/test_owner/test_repo/pulls/123'
        expected_data = {'title': 'Updated Title', 'body': 'Updated Body'}
        mock_requests.patch.assert_called_once_with(
            expected_url, headers=unittest.mock.ANY, json=expected_data
        )

if __name__ == '__main__':
    unittest.main()