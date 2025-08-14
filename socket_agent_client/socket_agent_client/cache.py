"""Multi-level caching system for socket-agent client."""

import hashlib
import json
import sys
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional, Tuple

from .exceptions import CacheError
from .types import CacheEntry


class LRUCache:
    """Simple LRU cache implementation."""
    
    def __init__(self, max_size: int = 1000, max_size_mb: int = 100):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            max_size_mb: Maximum size in megabytes
        """
        self.max_size = max_size
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._total_size = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        # Check expiration
        if entry.is_expired():
            del self._cache[key]
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        
        # Update hit count
        entry.hit_count += 1
        
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache."""
        # Create entry
        entry = CacheEntry(key=key, value=value, ttl=ttl)
        
        # Estimate size
        try:
            size = sys.getsizeof(json.dumps(value, default=str))
        except (TypeError, ValueError):
            size = sys.getsizeof(value)
        
        # Check if we need to evict
        while self._cache and (
            len(self._cache) >= self.max_size or 
            self._total_size + size > self.max_size_bytes
        ):
            # Remove least recently used
            oldest_key = next(iter(self._cache))
            self._evict(oldest_key)
        
        # Add to cache
        self._cache[key] = entry
        self._total_size += size
    
    def _evict(self, key: str):
        """Evict an entry from cache."""
        if key in self._cache:
            entry = self._cache[key]
            try:
                size = sys.getsizeof(json.dumps(entry.value, default=str))
            except (TypeError, ValueError):
                size = sys.getsizeof(entry.value)
            
            del self._cache[key]
            self._total_size = max(0, self._total_size - size)
    
    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        self._total_size = 0
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_hits = sum(e.hit_count for e in self._cache.values())
        return {
            "entries": len(self._cache),
            "size_bytes": self._total_size,
            "size_mb": self._total_size / (1024 * 1024),
            "total_hits": total_hits,
            "max_size": self.max_size,
            "max_size_mb": self.max_size_bytes / (1024 * 1024),
        }


class SemanticCache:
    """Semantic similarity-based cache (optional, requires embeddings)."""
    
    def __init__(self, radius: float = 0.85):
        """
        Initialize semantic cache.
        
        Args:
            radius: Similarity threshold for cache hits
        """
        self.radius = radius
        self._embeddings: Dict[str, Tuple[Any, Any]] = {}  # key -> (embedding, value)
        self._encoder = None
        
        # Try to load sentence-transformers if available
        try:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            pass
    
    def get(self, text: str) -> Optional[Any]:
        """Get value from semantic cache."""
        if not self._encoder or not self._embeddings:
            return None
        
        # Encode query
        query_embedding = self._encoder.encode(text)
        
        # Find similar entries
        best_score = 0
        best_value = None
        
        for key, (embedding, value) in self._embeddings.items():
            # Compute cosine similarity
            score = self._cosine_similarity(query_embedding, embedding)
            if score >= self.radius and score > best_score:
                best_score = score
                best_value = value
        
        return best_value
    
    def set(self, text: str, value: Any):
        """Set value in semantic cache."""
        if not self._encoder:
            return
        
        # Encode text
        embedding = self._encoder.encode(text)
        
        # Store
        key = hashlib.md5(text.encode()).hexdigest()
        self._embeddings[key] = (embedding, value)
        
        # Limit size
        if len(self._embeddings) > 1000:
            # Remove oldest entries
            keys = list(self._embeddings.keys())
            for k in keys[:100]:
                del self._embeddings[k]
    
    def _cosine_similarity(self, a, b):
        """Compute cosine similarity between two vectors."""
        import numpy as np
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def clear(self):
        """Clear semantic cache."""
        self._embeddings.clear()
    
    @property
    def enabled(self) -> bool:
        """Check if semantic cache is enabled."""
        return self._encoder is not None


class Cache:
    """Multi-level cache system."""
    
    def __init__(
        self,
        max_size: int = 1000,
        max_size_mb: int = 100,
        enable_semantic: bool = False,
        semantic_radius: float = 0.85,
    ):
        """
        Initialize cache system.
        
        Args:
            max_size: Maximum number of entries in L1 cache
            max_size_mb: Maximum size in MB for L1 cache
            enable_semantic: Enable semantic similarity cache
            semantic_radius: Similarity threshold for semantic cache
        """
        # L1: Deterministic cache
        self.l1 = LRUCache(max_size=max_size, max_size_mb=max_size_mb)
        
        # L2: Semantic cache (optional)
        self.l2 = SemanticCache(radius=semantic_radius) if enable_semantic else None
        
        # Statistics
        self._stats = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "total_requests": 0,
        }
    
    def get(self, key: str, semantic_key: Optional[str] = None) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Deterministic cache key
            semantic_key: Optional text for semantic lookup
            
        Returns:
            Cached value or None
        """
        self._stats["total_requests"] += 1
        
        # Try L1 (deterministic)
        value = self.l1.get(key)
        if value is not None:
            self._stats["l1_hits"] += 1
            return value
        
        self._stats["l1_misses"] += 1
        
        # Try L2 (semantic) if enabled and key provided
        if self.l2 and semantic_key:
            value = self.l2.get(semantic_key)
            if value is not None:
                self._stats["l2_hits"] += 1
                # Promote to L1
                self.l1.set(key, value)
                return value
            
            self._stats["l2_misses"] += 1
        
        return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        semantic_key: Optional[str] = None,
    ):
        """
        Set value in cache.
        
        Args:
            key: Deterministic cache key
            value: Value to cache
            ttl: Time to live in seconds
            semantic_key: Optional text for semantic caching
        """
        # Set in L1
        self.l1.set(key, value, ttl=ttl)
        
        # Set in L2 if enabled
        if self.l2 and semantic_key:
            self.l2.set(semantic_key, value)
    
    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: Optional[int] = None,
        semantic_key: Optional[str] = None,
    ) -> Any:
        """
        Get from cache or compute if missing.
        
        Args:
            key: Cache key
            compute_fn: Function to compute value if not cached
            ttl: Time to live for cached value
            semantic_key: Optional text for semantic caching
            
        Returns:
            Cached or computed value
        """
        # Try to get from cache
        value = self.get(key, semantic_key=semantic_key)
        if value is not None:
            return value
        
        # Compute value
        try:
            value = compute_fn()
        except Exception as e:
            raise CacheError(f"Failed to compute value: {e}") from e
        
        # Cache the result
        self.set(key, value, ttl=ttl, semantic_key=semantic_key)
        
        return value
    
    def invalidate(self, key: str):
        """Invalidate a cache entry."""
        if key in self.l1._cache:
            self.l1._evict(key)
    
    def clear(self):
        """Clear all caches."""
        self.l1.clear()
        if self.l2:
            self.l2.clear()
        
        # Reset stats
        self._stats = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "total_requests": 0,
        }
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = dict(self._stats)
        
        # Calculate hit rates
        if stats["total_requests"] > 0:
            stats["l1_hit_rate"] = stats["l1_hits"] / stats["total_requests"]
            stats["overall_hit_rate"] = (
                (stats["l1_hits"] + stats["l2_hits"]) / stats["total_requests"]
            )
        else:
            stats["l1_hit_rate"] = 0
            stats["overall_hit_rate"] = 0
        
        # Add L1 stats
        stats["l1_cache"] = self.l1.stats()
        
        # Add L2 stats if enabled
        if self.l2:
            stats["l2_enabled"] = self.l2.enabled
            stats["l2_entries"] = len(self.l2._embeddings)
        else:
            stats["l2_enabled"] = False
        
        return stats


def create_cache_key(endpoint: str, args: Dict[str, Any], version: str = "1.0") -> str:
    """
    Create a deterministic cache key.
    
    Args:
        endpoint: Endpoint name
        args: Arguments dictionary
        version: Version string
        
    Returns:
        Cache key string
    """
    # Normalize arguments
    normalized = json.dumps(args, sort_keys=True, default=str)
    
    # Create key
    key_data = f"{endpoint}:{version}:{normalized}"
    
    # Hash for consistent length
    return hashlib.sha256(key_data.encode()).hexdigest()
