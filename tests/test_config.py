import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Mock external dependencies to avoid ModuleNotFoundError in a clean test environment
sys.modules['openai'] = MagicMock()
sys.modules['yaml'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Add src to path to allow direct import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import Config

class TestConfig(unittest.TestCase):

    @patch.dict(os.environ, {
        'API_KEY': ' test_key ',
        'INPUT_FILES': ' /path/to/files/ ',
        'OUTPUT_FILES': ' ./output/ ',
        'TARGET_LANG': '  Simplified-Chinese  ',
        'BASE_URL': ' https://example.com/api/v1  '
    })
    def test_config_strips_whitespace_from_env_vars(self):
        """
        Tests that the Config class correctly strips leading/trailing whitespace
        from environment variables during initialization.
        """
        # We need to mock the prompts as they read from files
        with patch('src.config.Config._read_prompt', return_value="dummy_prompt"):
            config = Config()

            # Assert that all string-based configurations have been stripped
            self.assertEqual(config.api_key, 'test_key')
            self.assertEqual(config.input_files, '/path/to/files/')
            self.assertEqual(config.output_files, './output/')
            self.assertEqual(config.target_lang, 'Simplified-Chinese')
            self.assertEqual(config.base_url, 'https://example.com/api/v1')

    @patch.dict(os.environ, {
        'API_KEY': 'test_key',
        'INPUT_FILES': '',
        'OUTPUT_FILES': './output/',
        'TARGET_LANG': 'Simplified-Chinese',
    })
    def test_config_accepts_empty_input_files(self):
        """
        Tests that the Config class accepts empty INPUT_FILES environment variable.
        This is important for CI environments where no files may have changed.
        """
        # We need to mock the prompts as they read from files
        with patch('src.config.Config._read_prompt', return_value="dummy_prompt"):
            config = Config()

            # Assert that input_files is empty string but doesn't cause an error
            self.assertEqual(config.input_files, '')
            # Other required parameters should still be validated
            self.assertEqual(config.api_key, 'test_key')
            self.assertEqual(config.output_files, './output/')
            self.assertEqual(config.target_lang, 'Simplified-Chinese')

if __name__ == '__main__':
    unittest.main()