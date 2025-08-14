"""Telemetry and metrics tracking for socket-agent client."""

import json
import statistics
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .types import TelemetryEvent, TelemetrySummary


class Telemetry:
    """Tracks and reports client telemetry."""
    
    def __init__(
        self,
        enabled: bool = True,
        max_events: int = 10000,
        export_interval: int = 300,
    ):
        """
        Initialize telemetry.
        
        Args:
            enabled: Whether telemetry is enabled
            max_events: Maximum events to keep in memory
            export_interval: Export interval in seconds
        """
        self.enabled = enabled
        self.max_events = max_events
        self.export_interval = export_interval
        
        self._events: deque[TelemetryEvent] = deque(maxlen=max_events)
        self._last_export = time.time()
        
        # Counters
        self._total_calls = 0
        self._direct_calls = 0
        self._llm_calls = 0
        self._cache_hits = 0
        self._successes = 0
        self._failures = 0
        
        # Token tracking
        self._tokens_used = 0
        self._tokens_saved = 0
        
        # Latency tracking
        self._latencies: deque[float] = deque(maxlen=1000)
    
    def record(
        self,
        endpoint: str,
        via: str,
        tokens: int,
        latency_ms: float,
        success: bool,
        cache_hit: bool = False,
        confidence: Optional[float] = None,
    ):
        """
        Record a telemetry event.
        
        Args:
            endpoint: Endpoint called
            via: How it was called ("direct" or "llm")
            tokens: Tokens used (0 for direct calls)
            latency_ms: Latency in milliseconds
            success: Whether call succeeded
            cache_hit: Whether result was from cache
            confidence: Routing confidence score
        """
        if not self.enabled:
            return
        
        # Create event
        event = TelemetryEvent(
            endpoint=endpoint,
            via=via,
            tokens=tokens,
            latency_ms=latency_ms,
            success=success,
            cache_hit=cache_hit,
            confidence=confidence,
        )
        
        # Store event
        self._events.append(event)
        
        # Update counters
        self._total_calls += 1
        
        if via == "direct":
            self._direct_calls += 1
            # Estimate tokens saved (average LLM call uses ~500 tokens)
            self._tokens_saved += 500
        else:
            self._llm_calls += 1
            self._tokens_used += tokens
        
        if cache_hit:
            self._cache_hits += 1
        
        if success:
            self._successes += 1
        else:
            self._failures += 1
        
        # Track latency
        self._latencies.append(latency_ms)
        
        # Check if we should export
        if time.time() - self._last_export > self.export_interval:
            self.export()
    
    def log_call(
        self,
        endpoint: str,
        via: str = "direct",
        tokens: int = 0,
        latency_ms: float = 0,
        ok: bool = True,
    ):
        """
        Convenience method to log an API call.
        
        Args:
            endpoint: Endpoint called
            via: How it was called
            tokens: Tokens used
            latency_ms: Latency in milliseconds
            ok: Whether call succeeded
        """
        self.record(
            endpoint=endpoint,
            via=via,
            tokens=tokens,
            latency_ms=latency_ms,
            success=ok,
            cache_hit=False,
        )
    
    def summary(self) -> TelemetrySummary:
        """
        Get telemetry summary.
        
        Returns:
            TelemetrySummary with statistics
        """
        # Calculate rates
        cache_hit_rate = (
            self._cache_hits / self._total_calls if self._total_calls > 0 else 0
        )
        short_circuit_rate = (
            self._direct_calls / self._total_calls if self._total_calls > 0 else 0
        )
        success_rate = (
            self._successes / self._total_calls if self._total_calls > 0 else 0
        )
        
        # Calculate latency percentiles
        if self._latencies:
            latencies = list(self._latencies)
            avg_latency = statistics.mean(latencies)
            p50_latency = statistics.median(latencies)
            p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else max(latencies)
        else:
            avg_latency = p50_latency = p95_latency = 0
        
        return TelemetrySummary(
            total_calls=self._total_calls,
            direct_calls=self._direct_calls,
            llm_calls=self._llm_calls,
            tokens_saved=self._tokens_saved,
            tokens_used=self._tokens_used,
            cache_hits=self._cache_hits,
            cache_hit_rate=cache_hit_rate,
            short_circuit_rate=short_circuit_rate,
            avg_latency_ms=avg_latency,
            p50_latency_ms=p50_latency,
            p95_latency_ms=p95_latency,
            success_rate=success_rate,
        )
    
    def get_events(
        self,
        since: Optional[datetime] = None,
        endpoint: Optional[str] = None,
        via: Optional[str] = None,
    ) -> List[TelemetryEvent]:
        """
        Get filtered telemetry events.
        
        Args:
            since: Only events after this time
            endpoint: Filter by endpoint
            via: Filter by call method
            
        Returns:
            List of matching events
        """
        events = list(self._events)
        
        if since:
            events = [e for e in events if e.timestamp >= since]
        
        if endpoint:
            events = [e for e in events if e.endpoint == endpoint]
        
        if via:
            events = [e for e in events if e.via == via]
        
        return events
    
    def endpoint_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get per-endpoint statistics.
        
        Returns:
            Dictionary of endpoint -> stats
        """
        endpoint_data = {}
        
        for event in self._events:
            if event.endpoint not in endpoint_data:
                endpoint_data[event.endpoint] = {
                    "calls": 0,
                    "direct": 0,
                    "llm": 0,
                    "successes": 0,
                    "failures": 0,
                    "cache_hits": 0,
                    "latencies": [],
                    "confidences": [],
                }
            
            data = endpoint_data[event.endpoint]
            data["calls"] += 1
            
            if event.via == "direct":
                data["direct"] += 1
            else:
                data["llm"] += 1
            
            if event.success:
                data["successes"] += 1
            else:
                data["failures"] += 1
            
            if event.cache_hit:
                data["cache_hits"] += 1
            
            data["latencies"].append(event.latency_ms)
            
            if event.confidence is not None:
                data["confidences"].append(event.confidence)
        
        # Calculate aggregates
        for endpoint, data in endpoint_data.items():
            if data["latencies"]:
                data["avg_latency"] = statistics.mean(data["latencies"])
                data["p95_latency"] = (
                    statistics.quantiles(data["latencies"], n=20)[18]
                    if len(data["latencies"]) > 20
                    else max(data["latencies"])
                )
            else:
                data["avg_latency"] = 0
                data["p95_latency"] = 0
            
            if data["confidences"]:
                data["avg_confidence"] = statistics.mean(data["confidences"])
            else:
                data["avg_confidence"] = 0
            
            data["success_rate"] = (
                data["successes"] / data["calls"] if data["calls"] > 0 else 0
            )
            data["cache_hit_rate"] = (
                data["cache_hits"] / data["calls"] if data["calls"] > 0 else 0
            )
            
            # Remove raw lists for cleaner output
            del data["latencies"]
            del data["confidences"]
        
        return endpoint_data
    
    def export(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        """
        Export telemetry data.
        
        Args:
            filepath: Optional file to write to
            
        Returns:
            Exported data dictionary
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "summary": self.summary().model_dump(),
            "endpoint_stats": self.endpoint_stats(),
            "recent_events": [
                e.model_dump() for e in list(self._events)[-100:]
            ],
        }
        
        if filepath:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)
        
        self._last_export = time.time()
        return data
    
    def reset(self):
        """Reset all telemetry data."""
        self._events.clear()
        self._latencies.clear()
        
        self._total_calls = 0
        self._direct_calls = 0
        self._llm_calls = 0
        self._cache_hits = 0
        self._successes = 0
        self._failures = 0
        self._tokens_used = 0
        self._tokens_saved = 0
        
        self._last_export = time.time()
    
    def print_summary(self):
        """Print a human-readable summary."""
        summary = self.summary()
        
        print("\n=== Socket Agent Client Telemetry ===")
        print(f"Total Calls: {summary.total_calls}")
        print(f"  Direct: {summary.direct_calls} ({summary.short_circuit_rate:.1%})")
        print(f"  LLM: {summary.llm_calls} ({1 - summary.short_circuit_rate:.1%})")
        print(f"\nTokens:")
        print(f"  Saved: {summary.tokens_saved:,}")
        print(f"  Used: {summary.tokens_used:,}")
        print(f"  Net Savings: {summary.tokens_saved - summary.tokens_used:,}")
        print(f"\nPerformance:")
        print(f"  Cache Hit Rate: {summary.cache_hit_rate:.1%}")
        print(f"  Success Rate: {summary.success_rate:.1%}")
        print(f"  Avg Latency: {summary.avg_latency_ms:.1f}ms")
        print(f"  P50 Latency: {summary.p50_latency_ms:.1f}ms")
        print(f"  P95 Latency: {summary.p95_latency_ms:.1f}ms")
        
        # Top endpoints
        endpoint_stats = self.endpoint_stats()
        if endpoint_stats:
            print(f"\nTop Endpoints:")
            sorted_endpoints = sorted(
                endpoint_stats.items(),
                key=lambda x: x[1]["calls"],
                reverse=True,
            )[:5]
            
            for endpoint, stats in sorted_endpoints:
                print(f"  {endpoint}: {stats['calls']} calls "
                      f"({stats['direct']}/{stats['llm']} direct/llm)")


def create_telemetry(**kwargs) -> Telemetry:
    """
    Create a telemetry instance.
    
    Args:
        **kwargs: Arguments for Telemetry constructor
        
    Returns:
        Telemetry instance
    """
    return Telemetry(**kwargs)
