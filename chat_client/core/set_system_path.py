"""Backward-compatible wrappers for runtime bootstrap helpers."""

import sys


def get_system_paths():
    """Get system paths."""
    return sys.path
