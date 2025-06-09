import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import tempfile
from pathlib import Path

# Mock external dependencies to avoid ModuleNotFoundError
sys.modules['openai'] = MagicMock()
sys.modules['yaml'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Add src to path to allow direct import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.file_processor import FileProcessor
from src.config import Config

class TestFileProcessor(unittest.TestCase):

    def setUp(self):
        """Set up a mock config and FileProcessor instance for testing."""
        self.mock_config = MagicMock(spec=Config)
        self.file_processor = FileProcessor(self.mock_config)
        
        # Create a temporary directory for file-based tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
    def tearDown(self):
        """Clean up temporary files after tests."""
        self.temp_dir.cleanup()

    def test_get_output_path_mirroring(self):
        """
        Tests that get_output_path correctly mirrors the directory structure
        from a source ('en') to a target ('cn') directory.
        """
        # Configure the mock for a directory mirroring scenario
        self.mock_config.input_files = "docs/en"
        self.mock_config.output_files = "docs/cn/**"
        self.mock_config.target_lang = "Simplified-Chinese" # This should be ignored

        test_cases = {
            "docs/en/guides/getting-started.md": "docs/cn/guides/getting-started.md",
            "docs/en/index.md": "docs/cn/index.md",
            "docs/en/folder/subfolder/file.md": "docs/cn/folder/subfolder/file.md",
        }

        for input_path, expected_output in test_cases.items():
            with self.subTest(input_path=input_path):
                actual_output = self.file_processor.get_output_path(input_path)
                self.assertEqual(actual_output, expected_output)

    def test_get_output_path_with_wildcards(self):
        """
        Tests that get_output_path correctly handles wildcard patterns like docs/cn/**/*.{md,json}
        """
        self.mock_config.input_files = "docs/en"
        self.mock_config.output_files = "docs/cn/**/*.{md,json}"
        self.mock_config.target_lang = "Simplified-Chinese"

        # Test with a file in a subdirectory
        input_path = "docs/en/guides/intro.md"
        expected_output = "docs/cn/guides/intro.md"
        
        actual_output = self.file_processor.get_output_path(input_path)
        self.assertEqual(actual_output, expected_output)

    def test_get_input_files_single_path(self):
        """Test get_input_files with a single file path"""
        # Create a test file
        test_file = self.test_dir / "test_file.md"
        test_file.touch()
        
        # Configure mock
        self.mock_config.input_files = str(test_file)
        
        # Test with absolute path
        with patch('os.path.exists', return_value=True):
            result = self.file_processor.get_input_files()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], str(test_file))
    
    def test_get_input_files_multiple_paths(self):
        """Test get_input_files with multiple space-separated paths"""
        # Create test files
        test_file1 = self.test_dir / "test_file1.md"
        test_file2 = self.test_dir / "test_file2.md"
        test_file1.touch()
        test_file2.touch()
        
        # Configure mock with space-separated paths
        self.mock_config.input_files = f"{test_file1} {test_file2}"
        
        # Mock os.path.exists to return True for our test files
        def mock_exists(path):
            return path in (str(test_file1), str(test_file2))
        
        with patch('os.path.exists', side_effect=mock_exists):
            with patch('os.listdir', return_value=[]):
                result = self.file_processor.get_input_files()
                self.assertEqual(len(result), 2)
                self.assertEqual(result[0], str(test_file1))
                self.assertEqual(result[1], str(test_file2))
    
    def test_get_input_files_with_leading_dot_slash(self):
        """Test get_input_files with paths that have leading './'"""
        # Create test files
        docs_dir = self.test_dir / "docs"
        docs_dir.mkdir(exist_ok=True)
        en_dir = docs_dir / "en"
        en_dir.mkdir(exist_ok=True)
        
        test_file1 = en_dir / "file1.md"
        test_file2 = en_dir / "file2.md"
        test_file1.touch()
        test_file2.touch()
        
        # Paths with leading './' as would come from git diff
        path1_with_dot = f"./docs/en/file1.md"
        path2_with_dot = f"./docs/en/file2.md"
        
        # Normalized paths (without './')
        path1_normalized = "docs/en/file1.md"
        path2_normalized = "docs/en/file2.md"
        
        # Configure mock with space-separated paths that have leading './'
        self.mock_config.input_files = f"{path1_with_dot} {path2_with_dot}"
        
        # Mock exists to return True for normalized paths (without './')
        def mock_exists(path):
            return path in (path1_normalized, path2_normalized)
        
        with patch('os.path.exists', side_effect=mock_exists):
            with patch('os.listdir', return_value=[]):
                with patch('os.getcwd', return_value=str(self.test_dir)):
                    result = self.file_processor.get_input_files()
                    self.assertEqual(len(result), 2)
                    self.assertEqual(result[0], path1_normalized)
                    self.assertEqual(result[1], path2_normalized)
    
    def test_get_input_files_git_diff_output(self):
        """Test get_input_files with output similar to git diff command"""
        # Simulate output from: git diff --name-only | grep '.md$' | sed -e 's/^/.\/' | tr '\n' ' '
        git_diff_output = "./docs/en/guide.md ./docs/en/index.md ./docs/en/reference/api.md"
        
        # Configure mock
        self.mock_config.input_files = git_diff_output
        
        # Mock paths that would exist after normalization
        normalized_paths = [
            "docs/en/guide.md",
            "docs/en/index.md",
            "docs/en/reference/api.md"
        ]
        
        def mock_exists(path):
            return path in normalized_paths
        
        with patch('os.path.exists', side_effect=mock_exists):
            with patch('os.listdir', return_value=[]):
                result = self.file_processor.get_input_files()
                self.assertEqual(len(result), 3)
                self.assertEqual(result, normalized_paths)
    
    def test_get_input_files_empty_input(self):
        """Test get_input_files with empty input"""
        # Configure mock
        self.mock_config.input_files = ""
        
        result = self.file_processor.get_input_files()
        self.assertEqual(result, [])
    
    def test_get_input_files_no_valid_paths(self):
        """Test get_input_files when no valid paths are found"""
        # Configure mock with non-existent paths
        self.mock_config.input_files = "non_existent1.md non_existent2.md"
        
        # Mock os.path.exists to always return False
        with patch('os.path.exists', return_value=False):
            with patch('os.listdir', return_value=[]):
                result = self.file_processor.get_input_files()
                self.assertEqual(result, [])
                
    def test_get_input_files_github_actions_issue(self):
        """Test the specific issue occurring in GitHub Actions environment"""
        # This is the exact format of input we're seeing in GitHub Actions
        github_actions_input = "./docs/en/sql-reference/200-sql-functions/006-string-functions/char.md ./docs/en/sql-reference/200-sql-functions/006-string-functions/index.md"
        self.mock_config.input_files = github_actions_input
        
        # First, test the error case - no files exist
        with patch('os.path.exists', return_value=False):
            with patch('os.getcwd', return_value='/github/workspace'):
                with patch('os.listdir', return_value=['README.md', 'docs']):
                    # This should return an empty list since no files exist
                    result = self.file_processor.get_input_files()
                    self.assertEqual(result, [])
                    
        # Now test the case where the entire string is mistakenly treated as one path
        def mock_exists(path):
            # Return True only for the entire string, simulating the bug
            return path == github_actions_input
            
        with patch('os.path.exists', side_effect=mock_exists):
            with patch('os.getcwd', return_value='/github/workspace'):
                with patch('os.listdir', return_value=['README.md', 'docs']):
                    # This should NOT return the entire string as one path
                    result = self.file_processor.get_input_files()
                    self.assertNotEqual(result, [github_actions_input])
                    
        # Test that paths are correctly split by spaces
        def mock_exists_individual_paths(path):
            # Return True for individual paths after splitting
            valid_paths = [
                "./docs/en/sql-reference/200-sql-functions/006-string-functions/char.md",
                "docs/en/sql-reference/200-sql-functions/006-string-functions/char.md",
                "./docs/en/sql-reference/200-sql-functions/006-string-functions/index.md",
                "docs/en/sql-reference/200-sql-functions/006-string-functions/index.md"
            ]
            return path in valid_paths
            
        with patch('os.path.exists', side_effect=mock_exists_individual_paths):
            with patch('os.getcwd', return_value='/github/workspace'):
                with patch('os.listdir', return_value=['README.md', 'docs']):
                    # This should return the two individual paths
                    result = self.file_processor.get_input_files()
                    self.assertEqual(len(result), 2)
                    self.assertIn("docs/en/sql-reference/200-sql-functions/006-string-functions/char.md", result)
                    self.assertIn("docs/en/sql-reference/200-sql-functions/006-string-functions/index.md", result)

    def test_get_input_files_space_separator(self):
        """Test that input_files with space separator is correctly parsed into multiple paths"""
        # Set up a simple space-separated input string
        self.mock_config.input_files = "path1.md path2.md"
        
        # Mock os.path.exists to return True for both paths
        def mock_exists(path):
            return path in ["path1.md", "path2.md"]
        
        with patch('os.path.exists', side_effect=mock_exists):
            # Get the input files
            result = self.file_processor.get_input_files()
            
            # Verify that both paths were correctly parsed
            self.assertEqual(len(result), 2)
            self.assertIn("path1.md", result)
            self.assertIn("path2.md", result)

if __name__ == '__main__':
    unittest.main()