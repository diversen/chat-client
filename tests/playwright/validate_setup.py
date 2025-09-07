#!/usr/bin/env python3
"""Simple test script to validate Playwright test setup."""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def check_imports():
    """Check that required imports work."""
    print("Checking imports...")
    
    try:
        import pytest
        print("✓ pytest imported successfully")
    except ImportError as e:
        print(f"✗ pytest import failed: {e}")
        return False
    
    try:
        import playwright
        print("✓ playwright imported successfully")
    except ImportError as e:
        print(f"✗ playwright import failed: {e}")
        return False
    
    try:
        from playwright.async_api import async_playwright
        print("✓ playwright async API imported successfully")
    except ImportError as e:
        print(f"✗ playwright async API import failed: {e}")
        return False
    
    try:
        import chat_client
        print("✓ chat_client imported successfully")
    except ImportError as e:
        print(f"✗ chat_client import failed: {e}")
        return False
    
    return True

def check_test_files():
    """Check that test files are properly structured."""
    print("\nChecking test file structure...")
    
    test_dir = Path(__file__).parent
    required_files = [
        "conftest.py",
        "test_auth.py", 
        "test_chat.py",
        "test_ui.py",
        "utils/helpers.py",
        "pytest.ini"
    ]
    
    all_present = True
    for file_path in required_files:
        full_path = test_dir / file_path
        if full_path.exists():
            print(f"✓ {file_path} exists")
        else:
            print(f"✗ {file_path} missing")
            all_present = False
    
    return all_present

def check_config_syntax():
    """Check that test configuration files have valid syntax."""
    print("\nChecking configuration syntax...")
    
    test_dir = Path(__file__).parent
    
    # Check conftest.py
    try:
        with open(test_dir / "conftest.py", 'r') as f:
            compile(f.read(), 'conftest.py', 'exec')
        print("✓ conftest.py syntax is valid")
    except SyntaxError as e:
        print(f"✗ conftest.py syntax error: {e}")
        return False
    except Exception as e:
        print(f"✗ conftest.py error: {e}")
        return False
    
    # Check test files
    test_files = ["test_auth.py", "test_chat.py", "test_ui.py"]
    for test_file in test_files:
        try:
            with open(test_dir / test_file, 'r') as f:
                compile(f.read(), test_file, 'exec')
            print(f"✓ {test_file} syntax is valid")
        except SyntaxError as e:
            print(f"✗ {test_file} syntax error: {e}")
            return False
        except Exception as e:
            print(f"✗ {test_file} error: {e}")
            return False
    
    return True

def main():
    """Run all checks."""
    print("Playwright Test Setup Validation")
    print("=" * 40)
    
    checks = [
        ("Import Check", check_imports),
        ("File Structure Check", check_test_files),
        ("Configuration Syntax Check", check_config_syntax),
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        print(f"\n{check_name}:")
        print("-" * 20)
        passed = check_func()
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("✓ All checks passed! Playwright test setup is ready.")
        print("\nNext steps:")
        print("1. Install browser binaries: python -m playwright install chromium")
        print("2. Run tests: pytest tests/playwright/")
        print("\nNote: If using uv, ensure you have activated your virtual environment:")
        print("   source .venv/bin/activate")
        return 0
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())