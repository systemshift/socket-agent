"""Main client for socket-agent APIs with smart routing."""

import time
from typing import Any, Callable, Dict, Optional, Union

from .cache import Cache
from .descriptor import DescriptorFetcher
from .exceptions import DiscoveryError, ExecutionError, RoutingError
from .executor import Executor
from .policy import Policy
from .router.model import ModelBooster
from .router.rules import RulesEngine
from .stubs import StubStore
from .telemetry import Telemetry
from .templates import Renderer
from .types import APIResult, DecisionType, Descriptor, RouteResult


class Client:
    """Smart client for socket-agent APIs with zero-token routing."""
    
    def __init__(
        self,
        service_url: str,
        *,
        tiny_model: Optional[str] = None,
        http_session: Optional[Any] = None,
        policy: Optional[Policy] = None,
        auth_token: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize client.
        
        Args:
            service_url: Base URL of the service
            tiny_model: Optional path to tiny model for routing
            http_session: Optional HTTP session
            policy: Policy configuration
            auth_token: Optional bearer token
            api_key: Optional API key
        """
        self.service_url = service_url
        self.auth_token = auth_token
        self.api_key = api_key
        
        # Initialize components
        self.policy = policy or Policy()
        self.descriptor: Optional[Descriptor] = None
        
        # Core components
        self.stubs = StubStore()
        self.router = RulesEngine(stub_store=self.stubs)  # Explicitly pass stub_store
        self.executor = Executor(http_session=http_session)
        self.renderer = Renderer()
        
        # Cache
        self.cache = Cache(
            max_size=1000,
            max_size_mb=self.policy.max_cache_size_mb,
            enable_semantic=self.policy.enable_semantic_cache,
            semantic_radius=self.policy.semantic_cache_radius,
        )
        
        # Telemetry
        self.telemetry = Telemetry(
            enabled=self.policy.telemetry_enabled,
            export_interval=self.policy.telemetry_export_interval,
        )
        
        # Optional model booster
        self.model_booster = ModelBooster(
            tiny_model or self.policy.tiny_model_path
        )
        
        # LLM fallback handler (to be set by user)
        self._llm_handler: Optional[Callable] = None
        
        # Track if started
        self._started = False
    
    def start(self):
        """Fetch descriptor and initialize components."""
        if self._started:
            return
        
        try:
            # Fetch descriptor
            fetcher = DescriptorFetcher()
            self.descriptor = fetcher.fetch(self.service_url)
            fetcher.close()
            
            # Compile stubs
            self.stubs.compile_from_descriptor(self.descriptor)
            
            # Load templates
            self.renderer.load_templates(self.descriptor)
            
            self._started = True
            
        except Exception as e:
            raise DiscoveryError(f"Failed to start client: {e}") from e
    
    def route(self, text: str) -> tuple[str, Dict[str, Any], float]:
        """
        Route natural language text to endpoint.
        
        Args:
            text: Natural language input
            
        Returns:
            Tuple of (endpoint, args, confidence)
        """
        if not self._started:
            self.start()
        
        # Use rules engine for routing
        route_result = self.router.route(text)
        
        # Optionally boost with model
        if self.model_booster.model:
            # Get all candidates for reranking
            candidates = []
            pattern_matches = self.router._match_by_pattern(text.lower())
            candidates.extend(pattern_matches)
            keyword_matches = self.router._match_by_keywords(text.lower())
            candidates.extend(keyword_matches)
            action_matches = self.router._match_by_action(text.lower())
            candidates.extend(action_matches)
            
            if candidates:
                route_result = self.model_booster.boost(
                    text, route_result, candidates
                )
        
        return route_result.endpoint, route_result.args, route_result.confidence
    
    def __call__(
        self,
        text_or_endpoint: str,
        **kwargs
    ) -> APIResult:
        """
        Main entry point for API calls.
        
        Can be called with:
        - Natural language text: client("create todo: buy milk")
        - Direct endpoint + args: client("create_todo", text="buy milk")
        
        Args:
            text_or_endpoint: Natural language or endpoint name
            **kwargs: Arguments for direct endpoint call
            
        Returns:
            APIResult with response data
        """
        if not self._started:
            self.start()
        
        start_time = time.time()
        
        # Determine if this is natural language or direct call
        if kwargs:
            # Direct endpoint call
            endpoint = text_or_endpoint
            args = kwargs
            confidence = 1.0
            via = "direct"
        else:
            # Natural language routing
            text = text_or_endpoint
            endpoint, args, confidence = self.route(text)
            
            # Check confidence threshold
            if self.policy.should_fallback(confidence):
                return self.call_via_llm(text)
            elif self.policy.should_confirm(confidence):
                # Could ask for confirmation here
                # For now, proceed
                pass
            
            via = "direct" if confidence >= self.policy.short_circuit_threshold else "llm"
        
        # Get stub
        stub = self.stubs.get(endpoint)
        if not stub:
            raise RoutingError(f"Unknown endpoint: {endpoint}")
        
        # Check cache
        cache_key = stub.cache_key(args)
        cached = self.cache.get(cache_key, semantic_key=text_or_endpoint if not kwargs else None)
        
        if cached is not None:
            # Cache hit
            duration_ms = (time.time() - start_time) * 1000
            
            # Record telemetry
            self.telemetry.record(
                endpoint=endpoint,
                via=via,
                tokens=0,
                latency_ms=duration_ms,
                success=True,
                cache_hit=True,
                confidence=confidence,
            )
            
            # Return cached result
            result = APIResult(
                success=True,
                status_code=200,
                result=cached,
                rendered_text=self.renderer.render(endpoint, cached),
                error=None,
                duration_ms=duration_ms,
                tokens_used=0,
                cache_hit=True,
            )
            return result
        
        # Execute API call
        result = self.executor.call(
            method=stub.method,
            url=stub.url,
            args=args,
            headers=stub.headers,
            auth_token=self.auth_token,
            api_key=self.api_key,
        )
        
        # Render response
        if result.success and result.result:
            result.rendered_text = self.renderer.render(endpoint, result.result)
        
        # Cache successful results
        if result.success and result.result:
            ttl = self.policy.ttl(stub)
            self.cache.set(
                cache_key,
                result.result,
                ttl=ttl,
                semantic_key=text_or_endpoint if not kwargs else None,
            )
        
        # Record telemetry
        self.telemetry.record(
            endpoint=endpoint,
            via=via,
            tokens=0,
            latency_ms=result.duration_ms,
            success=result.success,
            cache_hit=False,
            confidence=confidence,
        )
        
        return result
    
    def call_via_llm(self, text: str) -> APIResult:
        """
        Fallback to LLM for complex requests.
        
        Args:
            text: Natural language input
            
        Returns:
            APIResult from LLM execution
        """
        if not self._llm_handler:
            # No LLM handler configured
            return APIResult(
                success=False,
                status_code=0,
                result=None,
                rendered_text=None,
                error="No LLM handler configured for fallback",
                duration_ms=0,
                tokens_used=0,
                cache_hit=False,
            )
        
        start_time = time.time()
        
        try:
            # Call LLM handler
            result = self._llm_handler(text, self.descriptor)
            
            # Ensure it's an APIResult
            if not isinstance(result, APIResult):
                # Convert to APIResult
                result = APIResult(
                    success=True,
                    status_code=200,
                    result=result,
                    rendered_text=str(result),
                    error=None,
                    duration_ms=(time.time() - start_time) * 1000,
                    tokens_used=500,  # Estimate
                    cache_hit=False,
                )
            
            # Record telemetry
            self.telemetry.record(
                endpoint="llm_fallback",
                via="llm",
                tokens=result.tokens_used,
                latency_ms=result.duration_ms,
                success=result.success,
                cache_hit=False,
                confidence=0.0,
            )
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Record failure
            self.telemetry.record(
                endpoint="llm_fallback",
                via="llm",
                tokens=0,
                latency_ms=duration_ms,
                success=False,
                cache_hit=False,
                confidence=0.0,
            )
            
            return APIResult(
                success=False,
                status_code=0,
                result=None,
                rendered_text=None,
                error=f"LLM handler failed: {e}",
                duration_ms=duration_ms,
                tokens_used=0,
                cache_hit=False,
            )
    
    def set_llm_handler(self, handler: Callable[[str, Descriptor], Any]):
        """
        Set the LLM fallback handler.
        
        Args:
            handler: Function that takes (text, descriptor) and returns result
        """
        self._llm_handler = handler
    
    def has_stub(self, name: str) -> bool:
        """Check if a stub exists."""
        return name in self.stubs
    
    def learn_stub(self, name: str):
        """Learn patterns for a stub (placeholder for learning)."""
        # This would implement pattern learning from usage
        pass
    
    def export_stubs(self, filepath: str):
        """Export learned stubs to file."""
        import json
        
        stubs_data = {
            "service_url": self.service_url,
            "stubs": [
                stub.model_dump() for stub in self.stubs.list_all()
            ],
            "telemetry": self.telemetry.summary().model_dump(),
        }
        
        with open(filepath, 'w') as f:
            json.dump(stubs_data, f, indent=2, default=str)
    
    def close(self):
        """Clean up resources."""
        self.executor.close()
        self.cache.clear()
        if self.telemetry.enabled:
            self.telemetry.export()
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_client(
    service_url: str,
    preset: Optional[str] = None,
    **kwargs
) -> Client:
    """
    Create a client with optional preset.
    
    Args:
        service_url: Service URL
        preset: Policy preset name
        **kwargs: Additional client options
        
    Returns:
        Configured Client instance
    """
    from .policy import create_policy
    
    # Create policy
    policy_kwargs = {}
    client_kwargs = {}
    
    for key, value in kwargs.items():
        if key in [
            "short_circuit_threshold",
            "confirm_threshold",
            "cache_ttl_default",
            "enable_semantic_cache",
            "semantic_cache_radius",
            "max_cache_size_mb",
            "enable_learning",
            "telemetry_enabled",
            "telemetry_export_interval",
        ]:
            policy_kwargs[key] = value
        else:
            client_kwargs[key] = value
    
    policy = create_policy(preset, **policy_kwargs)
    
    return Client(service_url, policy=policy, **client_kwargs)
