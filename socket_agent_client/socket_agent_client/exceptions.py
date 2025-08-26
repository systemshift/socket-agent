"""Custom exceptions for socket-agent client."""


class SocketAgentError(Exception):
    """Base exception for socket-agent client."""
    pass


class DiscoveryError(SocketAgentError):
    """Error during API discovery."""
    pass


class RoutingError(SocketAgentError):
    """Error during request routing."""
    pass


class ExecutionError(SocketAgentError):
    """Error during API execution."""
    pass


class CacheError(SocketAgentError):
    """Error in cache operations."""
    pass


class StubCompilationError(SocketAgentError):
    """Error compiling stubs from descriptor."""
    pass


class TemplateError(SocketAgentError):
    """Error rendering response template."""
    pass


class PolicyViolationError(SocketAgentError):
    """Policy constraint violation."""
    pass


class TelemetryError(SocketAgentError):
    """Error in telemetry operations."""
    pass


class ModelLoadError(SocketAgentError):
    """Error loading tiny model."""
    pass


class AuthenticationError(SocketAgentError):
    """Authentication failure."""
    pass


class RateLimitError(SocketAgentError):
    """Rate limit exceeded."""
    pass
