"""Descriptor fetching and validation for socket-agent APIs."""

import json
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from .exceptions import DiscoveryError
from .types import Descriptor


class DescriptorFetcher:
    """Fetches and validates socket-agent descriptors."""
    
    WELL_KNOWN_PATH = "/.well-known/socket-agent"
    MAX_SIZE_BYTES = 8 * 1024  # 8KB hard limit
    RECOMMENDED_SIZE_BYTES = 3 * 1024  # 3KB recommended
    
    def __init__(self, timeout: float = 30.0, verify_ssl: bool = True):
        """
        Initialize descriptor fetcher.
        
        Args:
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                verify=self.verify_ssl,
                follow_redirects=True,
                limits=httpx.Limits()
            )
        return self._client
    
    def fetch(self, service_url: str) -> Descriptor:
        """
        Fetch descriptor from service URL.
        
        Args:
            service_url: Base URL of the service
            
        Returns:
            Validated Descriptor object
            
        Raises:
            DiscoveryError: If fetching or validation fails
        """
        # Normalize URL
        service_url = self._normalize_url(service_url)
        
        # Build descriptor URL
        descriptor_url = urljoin(service_url, self.WELL_KNOWN_PATH)
        
        try:
            # Fetch descriptor
            response = self.client.get(
                descriptor_url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "socket-agent-client/1.0"
                }
            )
            response.raise_for_status()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise DiscoveryError(
                    f"No socket-agent descriptor found at {descriptor_url}. "
                    "Ensure the service implements socket-agent."
                ) from e
            raise DiscoveryError(
                f"HTTP {e.response.status_code} when fetching descriptor: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise DiscoveryError(f"Failed to fetch descriptor: {e}") from e
        
        # Check size
        content_length = len(response.content)
        if content_length > self.MAX_SIZE_BYTES:
            raise DiscoveryError(
                f"Descriptor size ({content_length / 1024:.2f}KB) exceeds "
                f"maximum allowed size ({self.MAX_SIZE_BYTES / 1024:.2f}KB)"
            )
        
        if content_length > self.RECOMMENDED_SIZE_BYTES:
            import warnings
            warnings.warn(
                f"Descriptor size ({content_length / 1024:.2f}KB) exceeds "
                f"recommended size ({self.RECOMMENDED_SIZE_BYTES / 1024:.2f}KB)",
                UserWarning
            )
        
        # Parse JSON
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise DiscoveryError(f"Invalid JSON in descriptor: {e}") from e
        
        # Ensure base_url is set
        if "base_url" not in data or not data["base_url"]:
            data["base_url"] = service_url
        
        # Validate and create descriptor
        try:
            descriptor = Descriptor(**data)
        except Exception as e:
            raise DiscoveryError(f"Invalid descriptor format: {e}") from e
        
        # Additional validation
        self._validate_descriptor(descriptor)
        
        return descriptor
    
    def _normalize_url(self, url: str) -> str:
        """Normalize service URL."""
        # Add scheme if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        # Parse and validate
        parsed = urlparse(url)
        if not parsed.netloc:
            raise DiscoveryError(f"Invalid service URL: {url}")
        
        # Remove trailing slash
        return url.rstrip("/")
    
    def _validate_descriptor(self, descriptor: Descriptor):
        """Perform additional validation on descriptor."""
        # Check required fields
        if not descriptor.name:
            raise DiscoveryError("Descriptor missing required field: name")
        
        if not descriptor.endpoints:
            raise DiscoveryError("Descriptor has no endpoints")
        
        # Validate endpoints
        for endpoint in descriptor.endpoints:
            if not endpoint.path:
                raise DiscoveryError(f"Endpoint missing path: {endpoint}")
            
            if endpoint.method not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                raise DiscoveryError(
                    f"Invalid HTTP method '{endpoint.method}' for {endpoint.path}"
                )
        
        # Check for duplicate endpoints
        endpoint_keys = [
            f"{ep.method}:{ep.path}" for ep in descriptor.endpoints
        ]
        if len(endpoint_keys) != len(set(endpoint_keys)):
            raise DiscoveryError("Descriptor contains duplicate endpoints")
        
        # Validate schemas if present
        for path, schema in descriptor.schemas.items():
            if not isinstance(schema, dict):
                raise DiscoveryError(f"Invalid schema for {path}: must be object")
            
            # Basic JSON Schema validation
            if "request" in schema:
                self._validate_json_schema(schema["request"], f"{path}.request")
            if "response" in schema:
                self._validate_json_schema(schema["response"], f"{path}.response")
    
    def _validate_json_schema(self, schema: dict, context: str):
        """Basic JSON Schema validation."""
        if not isinstance(schema, dict):
            raise DiscoveryError(f"Invalid schema at {context}: must be object")
        
        if "type" not in schema:
            # Type is technically optional but recommended
            import warnings
            warnings.warn(f"Schema at {context} missing 'type' field", UserWarning)
    
    def close(self):
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def fetch_descriptor(service_url: str, **kwargs) -> Descriptor:
    """
    Convenience function to fetch a descriptor.
    
    Args:
        service_url: Base URL of the service
        **kwargs: Additional arguments for DescriptorFetcher
        
    Returns:
        Descriptor object
    """
    with DescriptorFetcher(**kwargs) as fetcher:
        return fetcher.fetch(service_url)
