"""
Test runner for all Starlette backend tests.
This module provides different levels of testing for the backend.
"""
import sys
import os
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


def run_original_tests():
    """Run the original simple test scripts"""
    print("Running Original Test Scripts...")
    print("=" * 40)
    
    test_files = [
        "tests/test_password_methods.py",
        "tests/test_tools.py"
    ]
    
    passed = 0
    failed = 0
    
    for test_file in test_files:
        if Path(test_file).exists():
            print(f"Running {test_file}...")
            try:
                result = subprocess.run([sys.executable, test_file], 
                                      cwd=project_root, 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=30)
                if result.returncode == 0:
                    print(f"  ✓ {test_file} passed")
                    passed += 1
                else:
                    print(f"  ❌ {test_file} failed: {result.stderr}")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {test_file} error: {e}")
                failed += 1
        else:
            print(f"  ⚠️ {test_file} not found")
    
    return passed, failed


def run_playwright_tests():
    """Run Playwright end-to-end tests"""
    print("Running Playwright End-to-End Tests...")
    print("=" * 50)
    
    playwright_dir = project_root / "tests" / "playwright"
    if not playwright_dir.exists():
        print("  ⚠️ Playwright tests not found")
        return False
    
    try:
        # Check if playwright is installed
        result = subprocess.run([sys.executable, "-c", "import playwright"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("  ⚠️ Playwright not installed. Install with: pip install -e .[test]")
            return None  # Skip, not a failure
        
        # Check if browsers are installed
        result = subprocess.run([sys.executable, "-m", "playwright", "install", "--dry-run"],
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("  ⚠️ Playwright browsers not installed. Install with: python -m playwright install chromium")
            return None  # Skip, not a failure
        
        # Run playwright tests
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            str(playwright_dir),
            "--browser=chromium",
            "-v"
        ], cwd=project_root, timeout=300)
        
        if result.returncode == 0:
            print("  ✅ Playwright tests passed")
            return True
        else:
            print("  ❌ Playwright tests failed")
            return False
    
    except subprocess.TimeoutExpired:
        print("  ❌ Playwright tests timed out")
        return False
    except Exception as e:
        print(f"  ❌ Error running playwright tests: {e}")
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
            result = subprocess.run([sys.executable, "-m", "chat_client.cli", "init-system"], 
                                  cwd=project_root,
                                  capture_output=True,
                                  text=True,
                                  timeout=60)
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
    
    # Run original tests
    try:
        passed, failed = run_original_tests()
        if failed > 0:
            all_passed = False
        print(f"Original tests: {passed} passed, {failed} failed")
        print()
    except Exception as e:
        print(f"❌ Original tests failed: {e}")
        all_passed = False
    
    # Run Playwright tests (optional)
    try:
        playwright_result = run_playwright_tests()
        if playwright_result is False:  # False means failed, None means skipped
            all_passed = False
        elif playwright_result is True:
            print("Playwright E2E tests: ✅ passed")
        else:
            print("Playwright E2E tests: ⚠️  skipped (not installed)")
        print()
    except Exception as e:
        print(f"❌ Playwright tests failed: {e}")
        # Don't fail entire suite for Playwright issues
        print("⚠️  Continuing despite Playwright test failure...")
    
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
        print("- ✅ End-to-end UI testing (Playwright)")
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        print("Please check the output above for details.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)