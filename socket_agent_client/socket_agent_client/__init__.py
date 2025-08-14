"""Socket Agent Client - Smart, zero-token client for Socket Agent APIs."""

from .cache import Cache, create_cache_key
from .client import Client, create_client
from .descriptor import Descriptor, DescriptorFetcher, fetch_descriptor
from .exceptions import (
    AuthenticationError,
    CacheError,
    DiscoveryError,
    ExecutionError,
    ModelLoadError,
    PolicyViolationError,
    RateLimitError,
    RoutingError,
    SocketAgentError,
    StubCompilationError,
    TemplateError,
    TelemetryError,
)
from .executor import BatchExecutor, Executor
from .policy import Policy, PolicyPresets, create_policy
from .router import ConfidenceScorer, ParameterExtractor, RulesEngine
from .stubs import Stub, StubCompiler, StubStore
from .telemetry import Telemetry, TelemetrySummary, create_telemetry
from .templates import Renderer, TemplateBuilder, create_renderer
from .types import (
    APICall,
    APIResult,
    CacheEntry,
    DecisionType,
    EndpointInfo,
    RouteResult,
    TelemetryEvent,
)

__version__ = "1.0.0"

__all__ = [
    # Main client
    "Client",
    "create_client",
    # Descriptor
    "Descriptor",
    "DescriptorFetcher",
    "fetch_descriptor",
    "EndpointInfo",
    # Stubs
    "Stub",
    "StubStore",
    "StubCompiler",
    # Router
    "RulesEngine",
    "ParameterExtractor",
    "ConfidenceScorer",
    "RouteResult",
    "DecisionType",
    # Executor
    "Executor",
    "BatchExecutor",
    # Cache
    "Cache",
    "CacheEntry",
    "create_cache_key",
    # Templates
    "Renderer",
    "TemplateBuilder",
    "create_renderer",
    # Policy
    "Policy",
    "PolicyPresets",
    "create_policy",
    # Telemetry
    "Telemetry",
    "TelemetryEvent",
    "TelemetrySummary",
    "create_telemetry",
    # Types
    "APICall",
    "APIResult",
    # Exceptions
    "SocketAgentError",
    "DiscoveryError",
    "RoutingError",
    "ExecutionError",
    "CacheError",
    "StubCompilationError",
    "TemplateError",
    "PolicyViolationError",
    "TelemetryError",
    "ModelLoadError",
    "AuthenticationError",
    "RateLimitError",
]
