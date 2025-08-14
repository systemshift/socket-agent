"""Adapters for integrating socket-agent client with various frameworks."""

from .langchain import create_langchain_tool
from .mcp import create_mcp_tool
from .openai import create_openai_function

__all__ = ["create_mcp_tool", "create_openai_function", "create_langchain_tool"]
