"""
Tools package - Claude-native tool definitions and executors.

Replaces the old Skills layer. Tools return raw/trimmed data,
letting the model do its own interpretation.
"""
from src.tools.definitions import TOOL_DEFINITIONS
from src.tools.executors import execute_tool

__all__ = ["TOOL_DEFINITIONS", "execute_tool"]
