"""Pydantic models for socket-agent descriptor format."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EndpointInfo(BaseModel):
    """Information about a single API endpoint."""

    path: str = Field(..., description="The URL path of the endpoint")
    method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    summary: str = Field(..., description="Brief description of what the endpoint does")


class AuthInfo(BaseModel):
    """Authentication configuration."""

    type: str = Field("none", description="Authentication type (none, bearer, etc.)")
    description: Optional[str] = Field(None, description="Additional auth details")


class UIHints(BaseModel):
    """Optional UI generation hints."""

    form: Optional[Dict[str, Any]] = Field(None, description="Form layout hints")


class SocketDescriptor(BaseModel):
    """Complete socket-agent API descriptor."""

    name: str = Field(..., description="API name")
    description: str = Field(..., description="API description")
    base_url: str = Field(..., description="Base URL of the API")
    endpoints: List[EndpointInfo] = Field(..., description="List of available endpoints")
    schema: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Request/response schemas for each endpoint",
    )
    auth: AuthInfo = Field(
        default_factory=lambda: AuthInfo(type="none"),
        description="Authentication configuration",
    )
    examples: List[str] = Field(
        default_factory=list, description="Example API calls"
    )
    ui: Optional[Dict[str, UIHints]] = Field(
        None, description="Optional UI generation hints"
    )
    specVersion: str = Field(
        "2025-01-01", description="Specification version"
    )

    def size_kb(self) -> float:
        """Calculate the size of the descriptor in KB."""
        import json

        json_str = json.dumps(self.model_dump(exclude_none=True), separators=(",", ":"))
        return len(json_str.encode("utf-8")) / 1024
