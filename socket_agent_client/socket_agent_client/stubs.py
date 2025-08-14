"""Stub compilation and management for socket-agent APIs."""

import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

from .exceptions import StubCompilationError
from .types import Descriptor, Stub


class StubCompiler:
    """Compiles stubs from descriptors."""
    
    # Common action keywords for different operations
    ACTION_KEYWORDS = {
        "create": ["create", "add", "new", "make", "build", "generate", "insert"],
        "read": ["get", "list", "show", "fetch", "retrieve", "find", "search", "view"],
        "update": ["update", "edit", "modify", "change", "set", "patch"],
        "delete": ["delete", "remove", "destroy", "clear", "purge"],
    }
    
    def compile(self, descriptor: Descriptor) -> List[Stub]:
        """
        Compile stubs from a descriptor.
        
        Args:
            descriptor: API descriptor
            
        Returns:
            List of compiled stubs
            
        Raises:
            StubCompilationError: If compilation fails
        """
        stubs = []
        
        for endpoint in descriptor.endpoints:
            try:
                stub = self._compile_endpoint(endpoint, descriptor)
                stubs.append(stub)
            except Exception as e:
                raise StubCompilationError(
                    f"Failed to compile stub for {endpoint.method} {endpoint.path}: {e}"
                ) from e
        
        return stubs
    
    def _compile_endpoint(self, endpoint, descriptor: Descriptor) -> Stub:
        """Compile a single endpoint into a stub."""
        # Generate stub name
        name = self._generate_stub_name(endpoint)
        
        # Build full URL
        url = urljoin(descriptor.base_url, endpoint.path)
        
        # Get schemas if available
        schema_key = endpoint.path
        schemas = descriptor.schemas.get(schema_key, {})
        input_schema = schemas.get("request")
        output_schema = schemas.get("response")
        
        # Extract keywords from summary and path
        keywords = self._extract_keywords(endpoint)
        
        # Generate patterns for matching
        patterns = self._generate_patterns(endpoint, keywords)
        
        # Get cache TTL hint
        cache_ttl = descriptor.cache_hints.get(endpoint.path)
        
        # Get response template
        response_template = descriptor.response_templates.get(endpoint.path)
        
        # Build headers (including auth if needed)
        headers = self._build_headers(descriptor.auth)
        
        return Stub(
            name=name,
            method=endpoint.method,
            url=url,
            path=endpoint.path,
            input_schema=input_schema,
            output_schema=output_schema,
            headers=headers,
            cache_ttl=cache_ttl,
            response_template=response_template,
            keywords=keywords,
            patterns=patterns,
            version=descriptor.specVersion,
        )
    
    def _generate_stub_name(self, endpoint) -> str:
        """Generate a unique name for the stub."""
        # Convert path to name (e.g., /users/{id} -> users_by_id)
        path = endpoint.path.strip("/")
        path = re.sub(r"\{(\w+)\}", r"by_\1", path)
        path = path.replace("/", "_")
        
        # Combine method and path
        method_prefix = endpoint.method.lower()
        if method_prefix == "get":
            method_prefix = "fetch" if "{" in endpoint.path else "list"
        
        return f"{method_prefix}_{path}" if path else method_prefix
    
    def _extract_keywords(self, endpoint) -> List[str]:
        """Extract keywords from endpoint for matching."""
        keywords = []
        
        # Extract from summary
        if endpoint.summary:
            words = re.findall(r"\w+", endpoint.summary.lower())
            keywords.extend(words)
        
        # Extract from path
        path_parts = endpoint.path.strip("/").split("/")
        for part in path_parts:
            if not part.startswith("{"):
                keywords.append(part.lower())
        
        # Add method-related keywords
        method = endpoint.method.lower()
        if method == "post":
            keywords.extend(["create", "add", "new"])
        elif method == "get":
            keywords.extend(["get", "fetch", "list", "show"])
        elif method == "put" or method == "patch":
            keywords.extend(["update", "edit", "modify"])
        elif method == "delete":
            keywords.extend(["delete", "remove", "destroy"])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen and len(kw) > 2:  # Skip very short words
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords
    
    def _generate_patterns(self, endpoint, keywords: List[str]) -> List[str]:
        """Generate regex patterns for matching this endpoint."""
        patterns = []
        
        # Pattern based on method and resource
        resource = self._extract_resource(endpoint.path)
        if resource:
            method = endpoint.method.lower()
            
            if method == "post":
                patterns.append(f"(create|add|new).*{resource}")
            elif method == "get":
                if "{" in endpoint.path:
                    patterns.append(f"(get|fetch|show).*{resource}.*\\b\\w+\\b")
                else:
                    patterns.append(f"(list|get|show).*{resource}")
            elif method in ["put", "patch"]:
                patterns.append(f"(update|edit|modify).*{resource}")
            elif method == "delete":
                patterns.append(f"(delete|remove).*{resource}")
        
        # Pattern from summary
        if endpoint.summary:
            summary_pattern = self._summary_to_pattern(endpoint.summary)
            if summary_pattern:
                patterns.append(summary_pattern)
        
        # Pattern from keywords
        if len(keywords) >= 2:
            # Create pattern from most important keywords
            important = keywords[:3]
            patterns.append(".*" + ".*".join(important) + ".*")
        
        return patterns
    
    def _extract_resource(self, path: str) -> Optional[str]:
        """Extract the main resource from a path."""
        # Remove leading slash and parameters
        clean_path = path.strip("/")
        clean_path = re.sub(r"\{[^}]+\}", "", clean_path)
        
        # Get the first meaningful part
        parts = [p for p in clean_path.split("/") if p]
        if parts:
            # Singularize if needed (simple heuristic)
            resource = parts[0]
            if resource.endswith("s"):
                return resource[:-1]
            return resource
        
        return None
    
    def _summary_to_pattern(self, summary: str) -> Optional[str]:
        """Convert summary to a regex pattern."""
        # Extract action words
        words = summary.lower().split()
        action_words = []
        resource_words = []
        
        for word in words:
            # Check if it's an action word
            for action_type, action_list in self.ACTION_KEYWORDS.items():
                if word in action_list:
                    action_words.append(f"({word}|{'|'.join(action_list[:3])})")
                    break
            else:
                # Might be a resource word
                if len(word) > 3 and word not in ["with", "from", "into", "that"]:
                    resource_words.append(word)
        
        if action_words and resource_words:
            return ".*" + ".*".join(action_words[:1] + resource_words[:1]) + ".*"
        
        return None
    
    def _build_headers(self, auth: Dict[str, Any]) -> Dict[str, str]:
        """Build headers including authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "socket-agent-client/1.0",
        }
        
        # Add auth headers if needed
        auth_type = auth.get("type", "none")
        
        if auth_type == "bearer":
            # Placeholder for bearer token
            headers["Authorization"] = "Bearer ${token}"
        elif auth_type == "api_key":
            key_header = auth.get("header", "X-API-Key")
            headers[key_header] = "${api_key}"
        elif auth_type == "basic":
            headers["Authorization"] = "Basic ${credentials}"
        
        return headers


class StubStore:
    """Manages compiled stubs."""
    
    def __init__(self):
        """Initialize stub store."""
        self._stubs: Dict[str, Stub] = {}
        self._by_endpoint: Dict[str, Stub] = {}
        self._keywords_index: Dict[str, Set[str]] = {}
        self._patterns: List[tuple[re.Pattern, str]] = []
    
    def add(self, stub: Stub):
        """Add a stub to the store."""
        # Store by name
        self._stubs[stub.name] = stub
        
        # Store by endpoint key
        endpoint_key = f"{stub.method}:{stub.path}"
        self._by_endpoint[endpoint_key] = stub
        
        # Index keywords
        for keyword in stub.keywords:
            if keyword not in self._keywords_index:
                self._keywords_index[keyword] = set()
            self._keywords_index[keyword].add(stub.name)
        
        # Compile patterns
        for pattern_str in stub.patterns:
            try:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                self._patterns.append((pattern, stub.name))
            except re.error:
                # Skip invalid patterns
                pass
    
    def compile_from_descriptor(self, descriptor: Descriptor):
        """Compile and store stubs from a descriptor."""
        compiler = StubCompiler()
        stubs = compiler.compile(descriptor)
        
        # Clear existing stubs
        self.clear()
        
        # Add new stubs
        for stub in stubs:
            self.add(stub)
    
    def get(self, name: str) -> Optional[Stub]:
        """Get stub by name."""
        return self._stubs.get(name)
    
    def get_by_endpoint(self, method: str, path: str) -> Optional[Stub]:
        """Get stub by endpoint."""
        endpoint_key = f"{method}:{path}"
        return self._by_endpoint.get(endpoint_key)
    
    def find_by_keywords(self, text: str) -> List[Stub]:
        """Find stubs matching keywords in text."""
        text_lower = text.lower()
        words = set(re.findall(r"\w+", text_lower))
        
        # Find stubs with matching keywords
        matching_stubs = set()
        for word in words:
            if word in self._keywords_index:
                for stub_name in self._keywords_index[word]:
                    matching_stubs.add(stub_name)
        
        # Return stubs sorted by number of matching keywords
        stubs = []
        for stub_name in matching_stubs:
            stub = self._stubs[stub_name]
            match_count = sum(1 for kw in stub.keywords if kw in words)
            stubs.append((match_count, stub))
        
        stubs.sort(key=lambda x: x[0], reverse=True)
        return [stub for _, stub in stubs]
    
    def find_by_pattern(self, text: str) -> List[Stub]:
        """Find stubs matching patterns."""
        matches = []
        
        for pattern, stub_name in self._patterns:
            match = pattern.search(text)
            if match:
                stub = self._stubs[stub_name]
                # Score based on match quality
                score = len(match.group(0)) / len(text)
                matches.append((score, stub))
        
        # Sort by score
        matches.sort(key=lambda x: x[0], reverse=True)
        return [stub for _, stub in matches]
    
    def list_all(self) -> List[Stub]:
        """List all stubs."""
        return list(self._stubs.values())
    
    def clear(self):
        """Clear all stubs."""
        self._stubs.clear()
        self._by_endpoint.clear()
        self._keywords_index.clear()
        self._patterns.clear()
    
    def __len__(self) -> int:
        """Get number of stubs."""
        return len(self._stubs)
    
    def __contains__(self, name: str) -> bool:
        """Check if stub exists."""
        return name in self._stubs
