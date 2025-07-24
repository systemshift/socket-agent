"""FastAPI middleware for serving socket-agent descriptor."""

from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .schemas import SocketDescriptor
from .spec_builder import build_descriptor


class SocketAgentMiddleware:
    """Middleware to serve socket-agent descriptor at /.well-known/socket-agent."""

    def __init__(
        self,
        app: FastAPI,
        *,
        name: str,
        description: str,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the middleware.

        Args:
            app: FastAPI application instance
            name: API name
            description: API description
            base_url: Base URL of the API (defaults to request URL)
        """
        self.app = app
        self.name = name
        self.description = description
        self.base_url = base_url
        self._descriptor: Optional[SocketDescriptor] = None

        # Add middleware to app
        app.add_api_route(
            "/.well-known/socket-agent",
            self._serve_descriptor,
            methods=["GET"],
            include_in_schema=False,
        )

    def _build_descriptor(self, request: Request) -> SocketDescriptor:
        """Build or return cached descriptor."""
        if self._descriptor is None:
            # Determine base URL
            base_url = self.base_url
            if base_url is None:
                # Construct from request
                base_url = f"{request.url.scheme}://{request.url.netloc}"

            # Build descriptor
            self._descriptor = build_descriptor(
                self.app,
                name=self.name,
                description=self.description,
                base_url=base_url,
            )

        return self._descriptor

    async def _serve_descriptor(self, request: Request) -> Response:
        """Serve the socket-agent descriptor."""
        try:
            descriptor = self._build_descriptor(request)
            return JSONResponse(
                content=descriptor.model_dump(exclude_none=True),
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "public, max-age=3600",
                },
            )
        except Exception as e:
            return JSONResponse(
                content={"error": str(e)},
                status_code=500,
            )
