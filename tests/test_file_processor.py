import unittest
from unittest.mock import MagicMock
import sys
import os

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

if __name__ == '__main__':
    unittest.main()