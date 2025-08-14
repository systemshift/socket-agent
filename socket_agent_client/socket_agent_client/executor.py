"""HTTP execution layer for socket-agent client."""

import json
import time
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin

import httpx

from .exceptions import AuthenticationError, ExecutionError, RateLimitError
from .types import APIResult


class Executor:
    """Handles HTTP requests to API endpoints."""
    
    def __init__(
        self,
        http_session: Optional[httpx.Client] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize executor.
        
        Args:
            http_session: Optional HTTP client to use
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
        """
        self._session = http_session
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._owned_session = False
    
    @property
    def session(self) -> httpx.Client:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20,
                ),
            )
            self._owned_session = True
        return self._session
    
    def call(
        self,
        method: str,
        url: str,
        args: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth_token: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> APIResult:
        """
        Execute an API call.
        
        Args:
            method: HTTP method
            url: Full URL to call
            args: Arguments to send (as JSON body or query params)
            headers: Additional headers
            auth_token: Bearer token for authentication
            api_key: API key for authentication
            
        Returns:
            APIResult with response data
        """
        # Prepare headers
        final_headers = self._prepare_headers(headers, auth_token, api_key)
        
        # Prepare request parameters
        json_body = None
        params = None
        
        if args:
            if method in ["POST", "PUT", "PATCH"]:
                json_body = args
            else:
                params = args
        
        # Execute with retries
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self._execute_request(
                    method=method,
                    url=url,
                    headers=final_headers,
                    json=json_body,
                    params=params,
                )
                
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Parse response
                result = self._parse_response(response, duration_ms)
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", str(self.retry_delay))
                    raise RateLimitError(f"Rate limited. Retry after {retry_after} seconds")
                
                # Check for auth errors
                if response.status_code in [401, 403]:
                    raise AuthenticationError(f"Authentication failed: {response.status_code}")
                
                return result
                
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                
            except (RateLimitError, AuthenticationError):
                raise
                
            except Exception as e:
                last_error = e
                break
        
        # All retries failed
        duration_ms = (time.time() - start_time) * 1000
        error_msg = f"Failed after {self.max_retries} attempts: {last_error}"
        
        return APIResult(
            success=False,
            status_code=0,
            result=None,
            rendered_text=None,
            error=error_msg,
            duration_ms=duration_ms,
            tokens_used=0,
            cache_hit=False,
        )
    
    def _prepare_headers(
        self,
        headers: Optional[Dict[str, str]],
        auth_token: Optional[str],
        api_key: Optional[str],
    ) -> Dict[str, str]:
        """Prepare request headers."""
        final_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "socket-agent-client/1.0",
        }
        
        # Add custom headers
        if headers:
            for key, value in headers.items():
                # Replace placeholders
                if value == "${token}" and auth_token:
                    final_headers[key] = f"Bearer {auth_token}"
                elif value == "${api_key}" and api_key:
                    final_headers[key] = api_key
                elif value == "${credentials}":
                    # Basic auth would need username:password
                    pass
                elif not value.startswith("${"):
                    final_headers[key] = value
        
        # Add auth if not in custom headers
        if auth_token and "Authorization" not in final_headers:
            final_headers["Authorization"] = f"Bearer {auth_token}"
        
        if api_key and "X-API-Key" not in final_headers:
            final_headers["X-API-Key"] = api_key
        
        return final_headers
    
    def _execute_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Execute a single HTTP request."""
        return self.session.request(
            method=method,
            url=url,
            headers=headers,
            json=json,
            params=params,
        )
    
    def _parse_response(self, response: httpx.Response, duration_ms: float) -> APIResult:
        """Parse HTTP response into APIResult."""
        # Try to parse JSON
        try:
            if response.content:
                result = response.json()
            else:
                result = None
        except json.JSONDecodeError:
            # Return raw text if not JSON
            result = {"raw": response.text} if response.text else None
        
        # Determine success
        success = 200 <= response.status_code < 400
        
        # Build error message if failed
        error = None
        if not success:
            if isinstance(result, dict) and "error" in result:
                error = result["error"]
            elif isinstance(result, dict) and "message" in result:
                error = result["message"]
            else:
                error = f"HTTP {response.status_code}: {response.reason_phrase}"
        
        return APIResult(
            success=success,
            status_code=response.status_code,
            result=result,
            rendered_text=None,  # Will be filled by renderer
            error=error,
            duration_ms=duration_ms,
            tokens_used=0,
            cache_hit=False,
        )
    
    def close(self):
        """Close HTTP session if owned."""
        if self._owned_session and self._session:
            self._session.close()
            self._session = None
            self._owned_session = False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class BatchExecutor:
    """Execute multiple API calls in parallel."""
    
    def __init__(self, executor: Executor, max_concurrent: int = 5):
        """
        Initialize batch executor.
        
        Args:
            executor: Base executor to use
            max_concurrent: Maximum concurrent requests
        """
        self.executor = executor
        self.max_concurrent = max_concurrent
    
    async def execute_batch(
        self,
        requests: list[Dict[str, Any]]
    ) -> list[APIResult]:
        """
        Execute multiple requests in parallel.
        
        Args:
            requests: List of request dictionaries with method, url, args, etc.
            
        Returns:
            List of APIResults in the same order as requests
        """
        import asyncio
        
        # Create async client
        async with httpx.AsyncClient(
            timeout=self.executor.timeout,
            limits=httpx.Limits(max_connections=self.max_concurrent),
        ) as client:
            
            # Create tasks
            tasks = []
            for req in requests:
                task = self._execute_async(client, **req)
                tasks.append(task)
            
            # Execute in parallel with concurrency limit
            results = []
            for i in range(0, len(tasks), self.max_concurrent):
                batch = tasks[i:i + self.max_concurrent]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        # Convert exception to APIResult
                        results.append(APIResult(
                            success=False,
                            status_code=0,
                            result=None,
                            error=str(result),
                            duration_ms=0,
                            tokens_used=0,
                            cache_hit=False,
                        ))
                    else:
                        results.append(result)
            
            return results
    
    async def _execute_async(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        args: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> APIResult:
        """Execute a single async request."""
        start_time = time.time()
        
        # Prepare headers
        final_headers = self.executor._prepare_headers(
            headers,
            kwargs.get("auth_token"),
            kwargs.get("api_key"),
        )
        
        # Prepare body/params
        json_body = None
        params = None
        if args:
            if method in ["POST", "PUT", "PATCH"]:
                json_body = args
            else:
                params = args
        
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=final_headers,
                json=json_body,
                params=params,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            return self.executor._parse_response(response, duration_ms)
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return APIResult(
                success=False,
                status_code=0,
                result=None,
                error=str(e),
                duration_ms=duration_ms,
                tokens_used=0,
                cache_hit=False,
            )
