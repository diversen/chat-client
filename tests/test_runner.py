"""
Test runner for all Starlette backend tests.
Run this file to execute all backend endpoint tests.
"""

import unittest
import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tests.test_user_endpoints import TestUserEndpoints
from tests.test_chat_endpoints import TestChatEndpoints
from tests.test_prompt_endpoints import TestPromptEndpoints
from tests.test_error_endpoints import TestErrorEndpoints


def run_all_tests():
    """Run all backend tests"""

    # Create test suite
    test_suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestUserEndpoints,
        TestChatEndpoints,
        TestPromptEndpoints,
        TestErrorEndpoints,
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Return success/failure
    return result.wasSuccessful()


if __name__ == "__main__":
    print("Running Starlette Backend Tests...")
    print("=" * 50)

    success = run_all_tests()

    print("\n" + "=" * 50)
    if success:
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)
