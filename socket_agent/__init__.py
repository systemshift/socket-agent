"""socket-agent: Minimal API discovery for LLM agents."""

from .decorators import socket
from .fastapi_middleware import SocketAgentMiddleware
from .schemas import SocketDescriptor

__version__ = "0.1.0"
__all__ = ["socket", "SocketAgentMiddleware", "SocketDescriptor"]
