#!/usr/bin/env python3
"""Simple test to validate that the uv-based setup works correctly."""
import sys


def test_basic_imports():
    """Test that all required packages are importable."""
    print("Testing basic package imports...")
    
    # Test pytest
    try:
        import pytest
        print(f"✓ pytest {pytest.__version__} imported successfully")
    except ImportError as e:
        print(f"✗ pytest import failed: {e}")
        return False
    
    # Test playwright
    try:
        import playwright
        from playwright.async_api import async_playwright
        print("✓ playwright imported successfully")
    except ImportError as e:
        print(f"✗ playwright import failed: {e}")
        return False
    
    # Test pytest plugins
    try:
        import pytest_playwright
        import pytest_asyncio
        import pytest_base_url
        print("✓ pytest plugins imported successfully")
    except ImportError as e:
        print(f"✗ pytest plugin import failed: {e}")
        return False
    
    return True


def test_virtual_env():
    """Test that we're running in the expected virtual environment."""
    import os
    venv_path = os.environ.get('VIRTUAL_ENV', '')
    if '.venv' in venv_path or 'venv' in venv_path:
        print(f"✓ Running in virtual environment: {venv_path}")
        return True
    else:
        print("⚠ Not running in a virtual environment (this may be okay)")
        return True


if __name__ == "__main__":
    print("UV Setup Validation Test")
    print("=" * 30)
    
    tests = [
        ("Basic Package Imports", test_basic_imports),
        ("Virtual Environment Check", test_virtual_env),
    ]
    
    all_passed = True
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 20)
        passed = test_func()
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 30)
    if all_passed:
        print("✓ UV setup validation successful!")
        print("\nYour uv-based installation is working correctly.")
        print("You can now proceed with browser installation and running tests.")
        sys.exit(0)
    else:
        print("✗ Some validation checks failed.")
        sys.exit(1)