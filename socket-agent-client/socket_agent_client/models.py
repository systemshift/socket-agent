"""Data models for socket-agent client."""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class EndpointInfo(BaseModel):
    """Information about a single API endpoint."""
    path: str
    method: str
    summary: str


class Descriptor(BaseModel):
    """Socket-agent API descriptor."""
    name: str
    description: str
    base_url: str
    endpoints: List[EndpointInfo]
    schema: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    auth: Dict[str, Any] = Field(default_factory=lambda: {"type": "none"})
    examples: List[str] = Field(default_factory=list)


class APICall(BaseModel):
    """Record of an API call."""
    method: str
    path: str
    params: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class APIResult(BaseModel):
    """Result of an API call."""
    status_code: int
    body: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float


class LearnedPattern(BaseModel):
    """A pattern learned from API usage."""
    intent_pattern: str = Field(..., description="Regex or pattern for matching user intent")
    api_pattern: Dict[str, Any] = Field(..., description="API call template")
    confidence: float = Field(..., ge=0, le=1)
    observations: int = Field(..., ge=1)
    success_rate: float = Field(..., ge=0, le=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "intent_pattern": "create|add|new .* todo|task",
                "api_pattern": {
                    "method": "POST",
                    "path": "/todo",
                    "extract_params": {
                        "text": "everything after create/add/new"
                    }
                },
                "confidence": 0.95,
                "observations": 47,
                "success_rate": 0.98
            }
        }


class Stub(BaseModel):
    """Optimized stub generated from learned patterns."""
    version: str = "1.0"
    source: str = Field(..., description="Original descriptor URL")
    learned_patterns: List[LearnedPattern]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def save(self, filepath: str):
        """Save stub to file."""
        import json
        with open(filepath, 'w') as f:
            json.dump(self.model_dump(), f, indent=2, default=str)
    
    @classmethod
    def load(cls, filepath: str) -> "Stub":
        """Load stub from file."""
        import json
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(**data)
