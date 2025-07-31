"""Socket-Agent Client Library - Tools for interacting with socket-agent APIs."""

from .client import SocketAgentClient
from .discovery import DiscoveryClient
from .learner import PatternLearner
from .models import (
    Descriptor,
    EndpointInfo,
    APICall,
    APIResult,
    LearnedPattern,
    Stub,
)

__version__ = "0.1.0"

__all__ = [
    "SocketAgentClient",
    "DiscoveryClient",
    "PatternLearner",
    "Descriptor",
    "EndpointInfo",
    "APICall",
    "APIResult",
    "LearnedPattern",
    "Stub",
]
