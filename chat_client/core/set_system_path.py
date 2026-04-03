"""Backward-compatible wrappers for runtime bootstrap helpers."""

from chat_client.core.bootstrap import ConfigBootstrapResult, ensure_runtime_config
import sys


def get_system_paths():
    """Get system paths."""
    return sys.path
