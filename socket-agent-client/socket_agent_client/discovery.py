"""Discovery client for socket-agent APIs."""

import httpx
from typing import Optional
from .models import Descriptor


class DiscoveryClient:
    """Client for discovering socket-agent APIs."""
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def discover(self, base_url: str) -> Descriptor:
        """
        Discover a socket-agent API by fetching its descriptor.
        
        Args:
            base_url: Base URL of the API (e.g., "http://localhost:8000")
            
        Returns:
            Descriptor object containing API information
            
        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the descriptor is invalid
        """
        # Ensure base_url doesn't end with /
        base_url = base_url.rstrip('/')
        
        # Fetch descriptor
        response = await self.client.get(f"{base_url}/.well-known/socket-agent")
        response.raise_for_status()
        
        # Parse descriptor
        data = response.json()
        
        # Ensure base_url is set correctly
        if 'base_url' not in data or not data['base_url']:
            data['base_url'] = base_url
        
        return Descriptor(**data)
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
