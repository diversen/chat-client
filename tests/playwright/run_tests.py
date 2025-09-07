#!/usr/bin/env python3
"""Run Playwright tests for chat-client."""
import subprocess
import sys
import os
from pathlib import Path
import argparse


def check_browser_installation():
    """Check if Playwright browsers are installed."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def install_browsers():
    """Install Playwright browsers."""
    print("Installing Playwright browsers...")
    try:
        subprocess.run([
            sys.executable, "-m", "playwright", "install", "chromium"
        ], check=True)
        print("✓ Browsers installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("✗ Failed to install browsers")
        return False


def run_tests(args):
    """Run the Playwright tests."""
    test_dir = Path(__file__).parent
    
    # Change to test directory
    old_cwd = os.getcwd()
    os.chdir(test_dir)
    
    try:
        # Build pytest command
        cmd = [sys.executable, "-m", "pytest"]
        
        if args.verbose:
            cmd.append("-v")
        
        if args.headed:
            cmd.extend(["--headed"])
        
        if args.browser:
            cmd.extend([f"--browser={args.browser}"])
            
        if args.test:
            cmd.append(args.test)
        else:
            cmd.append(".")  # Run all tests
        
        if args.parallel:
            cmd.extend(["-n", str(args.parallel)])
        
        # Run tests
        result = subprocess.run(cmd)
        return result.returncode
        
    finally:
        os.chdir(old_cwd)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Playwright tests for chat-client")
    parser.add_argument("--install-browsers", action="store_true", 
                       help="Install Playwright browsers before running tests")
    parser.add_argument("--headed", action="store_true",
                       help="Run tests in headed mode (show browser)")
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"],
                       default="chromium", help="Browser to use for tests")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Run tests in verbose mode")
    parser.add_argument("--test", help="Run specific test file or test case")
    parser.add_argument("--parallel", "-j", type=int, 
                       help="Run tests in parallel (requires pytest-xdist)")
    
    args = parser.parse_args()
    
    print("Chat-Client Playwright Test Runner")
    print("=" * 40)
    
    # Install browsers if requested or if not already installed
    if args.install_browsers or not check_browser_installation():
        if not install_browsers():
            return 1
    
    # Run tests
    print("Running Playwright tests...")
    return run_tests(args)


if __name__ == "__main__":
    sys.exit(main())