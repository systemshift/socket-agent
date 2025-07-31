"""Main client for interacting with socket-agent APIs."""

import time
from typing import Any, Dict, Optional, Union
import httpx
from .models import Descriptor, APICall, APIResult
from .discovery import DiscoveryClient


class SocketAgentClient:
    """Client for interacting with socket-agent APIs."""
    
    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        """
        Initialize the client.
        
        Args:
            base_url: Base URL of the API (can be set later with discover())
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/') if base_url else None
        self.timeout = timeout
        self.descriptor: Optional[Descriptor] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._discovery = DiscoveryClient(timeout=timeout)
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def discover(self, base_url: Optional[str] = None) -> Descriptor:
        """
        Discover the API by fetching its descriptor.
        
        Args:
            base_url: Base URL of the API (overrides constructor value)
            
        Returns:
            Descriptor object
        """
        if base_url:
            self.base_url = base_url.rstrip('/')
        
        if not self.base_url:
            raise ValueError("base_url must be provided either in constructor or discover()")
        
        self.descriptor = await self._discovery.discover(self.base_url)
        return self.descriptor
    
    async def call(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
    ) -> APIResult:
        """
        Make an API call.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/todo")
            params: Query parameters
            headers: Additional headers
            json: JSON body (for POST/PUT)
            data: Form data or raw body
            
        Returns:
            APIResult with status code and response data
        """
        if not self.base_url:
            raise ValueError("Must call discover() first or provide base_url")
        
        # Build full URL
        url = f"{self.base_url}{path}"
        
        # Record call for potential learning
        api_call = APICall(
            method=method,
            path=path,
            params=params,
            headers=headers,
            body=json or (data if isinstance(data, dict) else None)
        )
        
        # Make the request
        start_time = time.time()
        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                json=json,
                data=data,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Parse response
            try:
                body = response.json() if response.content else None
            except:
                body = {"raw": response.text} if response.text else None
            
            return APIResult(
                status_code=response.status_code,
                body=body,
                error=None if response.status_code < 400 else response.text,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return APIResult(
                status_code=0,
                body=None,
                error=str(e),
                duration_ms=duration_ms
            )
    
    def find_endpoint(self, method: str, path: str) -> Optional[Dict[str, Any]]:
        """
        Find endpoint info from descriptor.
        
        Args:
            method: HTTP method
            path: API path
            
        Returns:
            Endpoint info dict or None
        """
        if not self.descriptor:
            return None
        
        for endpoint in self.descriptor.endpoints:
            if endpoint.method == method and endpoint.path == path:
                # Get schema if available
                schema = self.descriptor.schema.get(path, {})
                return {
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "summary": endpoint.summary,
                    "request_schema": schema.get("request"),
                    "response_schema": schema.get("response"),
                }
        
        return None
    
    async def close(self):
        """Close HTTP clients."""
        if self._client:
            await self._client.aclose()
            self._client = None
        await self._discovery.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
