"""Policy configuration for socket-agent client."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .types import Policy as PolicyModel


class Policy:
    """Manages client policy and configuration."""
    
    def __init__(
        self,
        short_circuit_threshold: float = 0.88,
        confirm_threshold: float = 0.70,
        cache_ttl_default: int = 300,
        enable_semantic_cache: bool = False,
        semantic_cache_radius: float = 0.85,
        max_cache_size_mb: int = 100,
        enable_learning: bool = False,
        tiny_model_path: Optional[str] = None,
        telemetry_enabled: bool = True,
        telemetry_export_interval: int = 300,
        **kwargs,
    ):
        """
        Initialize policy.
        
        Args:
            short_circuit_threshold: Confidence for direct calls
            confirm_threshold: Confidence for confirmation
            cache_ttl_default: Default cache TTL in seconds
            enable_semantic_cache: Enable semantic caching
            semantic_cache_radius: Similarity threshold
            max_cache_size_mb: Max cache size in MB
            enable_learning: Enable pattern learning
            tiny_model_path: Path to tiny model
            telemetry_enabled: Enable telemetry
            telemetry_export_interval: Export interval
            **kwargs: Additional policy parameters
        """
        self.model = PolicyModel(
            short_circuit_threshold=short_circuit_threshold,
            confirm_threshold=confirm_threshold,
            cache_ttl_default=cache_ttl_default,
            enable_semantic_cache=enable_semantic_cache,
            semantic_cache_radius=semantic_cache_radius,
            max_cache_size_mb=max_cache_size_mb,
            enable_learning=enable_learning,
            tiny_model_path=tiny_model_path,
            telemetry_enabled=telemetry_enabled,
            telemetry_export_interval=telemetry_export_interval,
        )
        
        # Store additional parameters
        self.extra = kwargs
    
    @property
    def short_circuit_threshold(self) -> float:
        """Get short-circuit threshold."""
        return self.model.short_circuit_threshold
    
    @property
    def confirm_threshold(self) -> float:
        """Get confirmation threshold."""
        return self.model.confirm_threshold
    
    @property
    def cache_ttl_default(self) -> int:
        """Get default cache TTL."""
        return self.model.cache_ttl_default
    
    @property
    def enable_semantic_cache(self) -> bool:
        """Check if semantic cache is enabled."""
        return self.model.enable_semantic_cache
    
    @property
    def semantic_cache_radius(self) -> float:
        """Get semantic cache radius."""
        return self.model.semantic_cache_radius
    
    @property
    def max_cache_size_mb(self) -> int:
        """Get max cache size in MB."""
        return self.model.max_cache_size_mb
    
    @property
    def enable_learning(self) -> bool:
        """Check if learning is enabled."""
        return self.model.enable_learning
    
    @property
    def tiny_model_path(self) -> Optional[str]:
        """Get tiny model path."""
        return self.model.tiny_model_path
    
    @property
    def telemetry_enabled(self) -> bool:
        """Check if telemetry is enabled."""
        return self.model.telemetry_enabled
    
    @property
    def telemetry_export_interval(self) -> int:
        """Get telemetry export interval."""
        return self.model.telemetry_export_interval
    
    def ttl(self, stub) -> int:
        """
        Get TTL for a stub.
        
        Args:
            stub: Stub object
            
        Returns:
            TTL in seconds
        """
        # Use stub's cache TTL if available
        if hasattr(stub, 'cache_ttl') and stub.cache_ttl:
            return stub.cache_ttl
        
        # Check endpoint-specific overrides
        endpoint_ttls = self.extra.get('endpoint_ttls', {})
        if hasattr(stub, 'name') and stub.name in endpoint_ttls:
            return endpoint_ttls[stub.name]
        
        # Use default
        return self.cache_ttl_default
    
    def should_short_circuit(self, confidence: float) -> bool:
        """
        Check if we should short-circuit based on confidence.
        
        Args:
            confidence: Confidence score
            
        Returns:
            True if should short-circuit
        """
        return confidence >= self.short_circuit_threshold
    
    def should_confirm(self, confidence: float) -> bool:
        """
        Check if we should ask for confirmation.
        
        Args:
            confidence: Confidence score
            
        Returns:
            True if should confirm
        """
        return (
            confidence >= self.confirm_threshold and
            confidence < self.short_circuit_threshold
        )
    
    def should_fallback(self, confidence: float) -> bool:
        """
        Check if we should fallback to LLM.
        
        Args:
            confidence: Confidence score
            
        Returns:
            True if should fallback
        """
        return confidence < self.confirm_threshold
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary."""
        data = self.model.model_dump()
        data.update(self.extra)
        return data
    
    def save(self, filepath: str):
        """
        Save policy to file.
        
        Args:
            filepath: Path to save to
        """
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> "Policy":
        """
        Load policy from file.
        
        Args:
            filepath: Path to load from
            
        Returns:
            Policy instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> "Policy":
        """
        Create policy from environment variables.
        
        Returns:
            Policy instance
        """
        import os
        
        kwargs = {}
        
        # Map environment variables to policy parameters
        env_mapping = {
            "SOCKET_AGENT_SHORT_CIRCUIT_THRESHOLD": ("short_circuit_threshold", float),
            "SOCKET_AGENT_CONFIRM_THRESHOLD": ("confirm_threshold", float),
            "SOCKET_AGENT_CACHE_TTL": ("cache_ttl_default", int),
            "SOCKET_AGENT_SEMANTIC_CACHE": ("enable_semantic_cache", lambda x: x.lower() == "true"),
            "SOCKET_AGENT_SEMANTIC_RADIUS": ("semantic_cache_radius", float),
            "SOCKET_AGENT_MAX_CACHE_MB": ("max_cache_size_mb", int),
            "SOCKET_AGENT_LEARNING": ("enable_learning", lambda x: x.lower() == "true"),
            "SOCKET_AGENT_MODEL_PATH": ("tiny_model_path", str),
            "SOCKET_AGENT_TELEMETRY": ("telemetry_enabled", lambda x: x.lower() == "true"),
            "SOCKET_AGENT_TELEMETRY_INTERVAL": ("telemetry_export_interval", int),
        }
        
        for env_var, (param, converter) in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    kwargs[param] = converter(value)
                except (ValueError, TypeError):
                    pass
        
        return cls(**kwargs)


class PolicyPresets:
    """Predefined policy configurations."""
    
    @staticmethod
    def aggressive() -> Policy:
        """
        Aggressive short-circuiting policy.
        
        Maximizes direct calls at the cost of potential errors.
        """
        return Policy(
            short_circuit_threshold=0.75,
            confirm_threshold=0.60,
            cache_ttl_default=600,
            enable_semantic_cache=True,
            semantic_cache_radius=0.80,
        )
    
    @staticmethod
    def balanced() -> Policy:
        """
        Balanced policy (default).
        
        Good balance between performance and accuracy.
        """
        return Policy()
    
    @staticmethod
    def conservative() -> Policy:
        """
        Conservative policy.
        
        Prioritizes accuracy over performance.
        """
        return Policy(
            short_circuit_threshold=0.95,
            confirm_threshold=0.85,
            cache_ttl_default=180,
            enable_semantic_cache=False,
        )
    
    @staticmethod
    def development() -> Policy:
        """
        Development/debugging policy.
        
        Enables all features for testing.
        """
        return Policy(
            short_circuit_threshold=0.80,
            confirm_threshold=0.60,
            cache_ttl_default=60,
            enable_semantic_cache=True,
            semantic_cache_radius=0.75,
            enable_learning=True,
            telemetry_enabled=True,
            telemetry_export_interval=60,
        )
    
    @staticmethod
    def production() -> Policy:
        """
        Production policy.
        
        Optimized for production use.
        """
        return Policy(
            short_circuit_threshold=0.90,
            confirm_threshold=0.75,
            cache_ttl_default=300,
            enable_semantic_cache=False,
            enable_learning=False,
            telemetry_enabled=True,
            telemetry_export_interval=3600,
        )


def create_policy(preset: Optional[str] = None, **kwargs) -> Policy:
    """
    Create a policy with optional preset.
    
    Args:
        preset: Preset name ("aggressive", "balanced", "conservative", "development", "production")
        **kwargs: Override parameters
        
    Returns:
        Policy instance
    """
    if preset:
        preset_map = {
            "aggressive": PolicyPresets.aggressive,
            "balanced": PolicyPresets.balanced,
            "conservative": PolicyPresets.conservative,
            "development": PolicyPresets.development,
            "production": PolicyPresets.production,
        }
        
        if preset in preset_map:
            policy = preset_map[preset]()
            # Apply overrides
            if kwargs:
                for key, value in kwargs.items():
                    if hasattr(policy.model, key):
                        setattr(policy.model, key, value)
                    else:
                        policy.extra[key] = value
            return policy
    
    return Policy(**kwargs)
