"""Decorator for describing API endpoints."""

from typing import Any, Callable, Dict, Optional



class SocketDecorator:
    """Main decorator class for socket-agent."""

    def describe(
        self,
        summary: str,
        *,
        request_schema: Optional[Dict[str, Any]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        examples: Optional[list[str]] = None,
    ) -> Callable:
        """
        Decorator to describe an API endpoint for socket-agent.

        Args:
            summary: Brief description of what the endpoint does
            request_schema: JSON Schema for request body
            response_schema: JSON Schema for response body
            examples: List of example curl commands

        Returns:
            Decorated function with socket metadata attached
        """

        def decorator(func: Callable) -> Callable:
            # Store metadata on the function
            if not hasattr(func, "_socket_meta"):
                func._socket_meta = {}

            func._socket_meta.update(
                {
                    "summary": summary,
                    "request_schema": request_schema,
                    "response_schema": response_schema,
                    "examples": examples or [],
                }
            )

            return func

        return decorator


# Create a singleton instance
socket = SocketDecorator()
