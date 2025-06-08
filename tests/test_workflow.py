import unittest
import os
from unittest.mock import patch, MagicMock
import sys

# Mock external dependencies to avoid ModuleNotFoundError
sys.modules['openai'] = MagicMock()
sys.modules['yaml'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Add src to path to allow direct import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from translate import TranslationWorkflow
from src.config import Config

class TestTranslationWorkflow(unittest.TestCase):

    def setUp(self):
        """Set up a mock config for testing."""
        self.mock_config = MagicMock(spec=Config)
        self.mock_config.input_files = "docs/en"
        self.mock_config.output_files = "docs/cn/**/{name}.{lang}.md"
        self.mock_config.target_lang = "Simplified-Chinese"
        self.mock_config.api_key = "test_api_key"
        self.mock_config.base_url = "https://example.com"
        self.mock_config.ai_model = "test-model"
        self.mock_config.temperature = 0.5
        self.mock_config.refine_enabled = False
        
        # Mock GitOperations to avoid actual git commands
        with patch('translate.GitOperations') as mock_git_ops, \
             patch('translate.Translator') as mock_translator:
            self.workflow = TranslationWorkflow(self.mock_config)
            self.workflow.git_ops = mock_git_ops.return_value
            self.workflow.translator = mock_translator.return_value
            self.workflow.git_ops.in_github_actions = False # Default to non-CI environment

    @patch('os.path.exists')
    @patch('os.path.isdir')
    def test_process_input_path_variations(self, mock_isdir, mock_exists):
        """
        Tests that process_input_path correctly resolves various path formats
        and returns a unified relative path.
        """
        # Simulate that the 'docs/en' directory exists
        def path_exists_side_effect(path):
            # This is the unified, relative path we expect to be checked
            return path == 'docs/en'

        mock_exists.side_effect = path_exists_side_effect
        mock_isdir.return_value = True

        # Mock the file finder to return a dummy file list
        self.workflow.file_processor.find_files_recursively = MagicMock(return_value=['docs/en/test.md'])

        test_cases = [
            "docs/en",
            "./docs/en",
            "/docs/en",
        ]

        for path_input in test_cases:
            with self.subTest(path_input=path_input):
                # Reset mocks for each subtest
                mock_exists.reset_mock()
                
                result = self.workflow.process_input_path(path_input)
                
                # Assert that the final check was done on the correct relative path
                mock_exists.assert_any_call('docs/en')
                
                # Assert that the method returns the correct list of files
                self.assertEqual(result, ['docs/en/test.md'])
                
                # Assert that the recursive finder was called with the correct relative path
                self.workflow.file_processor.find_files_recursively.assert_called_with('docs/en')

    def test_process_input_path_empty_input(self):
        """
        Tests that process_input_path correctly handles empty input paths.
        This is important for CI environments where no files may have changed.
        """
        # Test with empty string
        result = self.workflow.process_input_path('')
        self.assertEqual(result, [])
        
        # Test with None
        result = self.workflow.process_input_path(None)
        self.assertEqual(result, [])
        
        # Test with whitespace
        result = self.workflow.process_input_path('   ')
        self.assertEqual(result, [])
    
    def test_run_with_empty_input_files(self):
        """
        Tests that the run method handles empty input files gracefully.
        """
        # Set up the config with empty input_files
        self.mock_config.input_files = ''
        
        # Mock process_input_path to return empty list
        self.workflow.process_input_path = MagicMock(return_value=[])
        
        # Test non-CI environment
        self.workflow.git_ops.in_github_actions = False
        result = self.workflow.run()
        self.assertTrue(result)  # Should return True for successful completion
        
        # Test CI environment
        self.workflow.git_ops.in_github_actions = True
        result = self.workflow.run()
        self.assertTrue(result)  # Should return True for successful completion

if __name__ == '__main__':
    unittest.main()