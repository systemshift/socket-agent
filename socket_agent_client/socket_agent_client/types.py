"""Type definitions for socket-agent client."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    """Type of routing decision made."""
    DIRECT = "direct"  # High confidence, direct stub call
    CONFIRM = "confirm"  # Medium confidence, needs confirmation
    FALLBACK = "fallback"  # Low confidence, use LLM


@dataclass
class RouteResult:
    """Result of routing analysis."""
    endpoint: str
    method: str
    path: str
    args: Dict[str, Any]
    confidence: float
    decision: DecisionType
    reasoning: Optional[str] = None
    extraction_hints: Optional[Dict[str, str]] = None


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    ttl: Optional[int] = None
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.ttl is None:
            return False
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl


class EndpointInfo(BaseModel):
    """Information about an API endpoint."""
    path: str = Field(..., description="URL path")
    method: str = Field(..., description="HTTP method")
    summary: str = Field(..., description="Brief description")


class Descriptor(BaseModel):
    """Socket-agent API descriptor."""
    name: str
    description: str
    base_url: str
    endpoints: List[EndpointInfo]
    schemas: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    auth: Dict[str, Any] = Field(default_factory=lambda: {"type": "none"})
    examples: List[str] = Field(default_factory=list)
    response_templates: Dict[str, str] = Field(default_factory=dict)
    cache_hints: Dict[str, int] = Field(default_factory=dict)
    specVersion: str = Field(default="2025-01-01")


class Stub(BaseModel):
    """Compiled stub from descriptor."""
    name: str
    method: str
    url: str
    path: str
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    cache_ttl: Optional[int] = None
    response_template: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)
    version: str = "1.0"
    
    def cache_key(self, args: Dict[str, Any]) -> str:
        """Generate cache key for given arguments."""
        import hashlib
        import json
        
        # Normalize args for consistent hashing
        normalized = json.dumps(args, sort_keys=True)
        key_data = f"{self.name}:{self.version}:{normalized}"
        return hashlib.sha256(key_data.encode()).hexdigest()


class APICall(BaseModel):
    """Record of an API call."""
    endpoint: str
    method: str
    path: str
    args: Dict[str, Any] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    via: str = Field(default="direct")  # "direct" or "llm"


class APIResult(BaseModel):
    """Result of an API call."""
    success: bool
    status_code: Optional[int] = None
    result: Optional[Any] = None
    rendered_text: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float
    tokens_used: int = 0
    cache_hit: bool = False


class TelemetryEvent(BaseModel):
    """Telemetry event."""
    timestamp: datetime = Field(default_factory=datetime.now)
    endpoint: str
    via: str  # "direct" or "llm"
    tokens: int
    latency_ms: float
    success: bool
    cache_hit: bool = False
    confidence: Optional[float] = None


class TelemetrySummary(BaseModel):
    """Telemetry summary statistics."""
    total_calls: int
    direct_calls: int
    llm_calls: int
    tokens_saved: int
    tokens_used: int
    cache_hits: int
    cache_hit_rate: float
    short_circuit_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    success_rate: float
    
    
class Policy(BaseModel):
    """Client policy configuration."""
    short_circuit_threshold: float = Field(
        default=0.88,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for direct calls"
    )
    confirm_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for confirmation"
    )
    cache_ttl_default: int = Field(
        default=300,
        description="Default cache TTL in seconds"
    )
    enable_semantic_cache: bool = Field(
        default=False,
        description="Enable semantic similarity caching"
    )
    semantic_cache_radius: float = Field(
        default=0.85,
        description="Similarity threshold for semantic cache"
    )
    max_cache_size_mb: int = Field(
        default=100,
        description="Maximum cache size in MB"
    )
    enable_learning: bool = Field(
        default=False,
        description="Enable pattern learning from usage"
    )
    tiny_model_path: Optional[str] = Field(
        default=None,
        description="Path to tiny model for reranking"
    )
    telemetry_enabled: bool = Field(
        default=True,
        description="Enable telemetry collection"
    )
    telemetry_export_interval: int = Field(
        default=300,
        description="Telemetry export interval in seconds"
    )
