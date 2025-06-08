import unittest
import sys

def run_tests():
    """Discovers and runs all tests in the 'tests' directory."""
    # Add the 'tests' directory to the Python path to allow discovery
    loader = unittest.TestLoader()
    suite = loader.discover('tests')
    
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n✅ All tests passed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)

if __name__ == '__main__':
    run_tests()