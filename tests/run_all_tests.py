"""
Test runner for all Starlette backend tests.
This module provides different levels of testing for the backend.
"""

import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_simple_tests():
    """Run simple backend tests (basic functionality)"""
    print("Running Simple Backend Tests...")
    print("=" * 50)

    try:
        from tests.test_starlette_simple import main

        success = main()
        return success
    except Exception as e:
        print(f"Error running simple tests: {e}")
        return False


def run_comprehensive_tests():
    """Run comprehensive backend tests (full functionality)"""
    print("Running Comprehensive Backend Tests...")
    print("=" * 60)

    try:
        from tests.test_starlette_comprehensive import main

        success = main()
        return success
    except Exception as e:
        print(f"Error running comprehensive tests: {e}")
        return False


def main():
    """Main test runner"""
    print("Starlette Backend Test Suite")
    print("=" * 70)
    print("This test suite validates all Starlette backend endpoints and functionality.")
    print()

    # Check if database is initialized
    db_path = project_root / "data" / "database.db"
    if not db_path.exists():
        print("⚠️  Database not found. Initializing...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "chat_client.cli", "init-system"], cwd=project_root, capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                print("✓ Database initialized successfully")
            else:
                print(f"❌ Failed to initialize database: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            return False

    all_passed = True

    # Run simple tests first
    try:
        simple_success = run_simple_tests()
        if not simple_success:
            all_passed = False
        print()
    except Exception as e:
        print(f"❌ Simple tests failed: {e}")
        all_passed = False

    # Run comprehensive tests
    try:
        comprehensive_success = run_comprehensive_tests()
        if not comprehensive_success:
            all_passed = False
        print()
    except Exception as e:
        print(f"❌ Comprehensive tests failed: {e}")
        all_passed = False

    # Final results
    print("=" * 70)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("The Starlette backend is working correctly.")
        print()
        print("Test Coverage:")
        print("- ✅ Basic route functionality")
        print("- ✅ Authentication and authorization")
        print("- ✅ User management (signup, login, profile)")
        print("- ✅ Chat functionality (streaming, dialogs, messages)")
        print("- ✅ Prompt management (CRUD operations)")
        print("- ✅ Error handling and logging")
        print("- ✅ Tool system")
        print("- ✅ Validation and error cases")
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        print("Please check the output above for details.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
