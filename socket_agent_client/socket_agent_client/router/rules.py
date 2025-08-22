"""Rules-based routing engine for socket-agent client."""

import re
from typing import Any, Dict, List, Optional, Tuple

from ..exceptions import RoutingError
from ..stubs import StubStore
from ..types import DecisionType, RouteResult


class RulesEngine:
    """Heuristic-based routing engine."""
    
    def __init__(self, stub_store: Optional[StubStore] = None):
        """
        Initialize rules engine.
        
        Args:
            stub_store: Store of compiled stubs
        """
        self.stub_store = stub_store or StubStore()
        
        # Action verb mappings
        self.action_verbs = {
            "create": ["create", "add", "new", "make", "build", "generate", "insert", "post"],
            "read": ["get", "list", "show", "fetch", "retrieve", "find", "search", "view", "read"],
            "update": ["update", "edit", "modify", "change", "set", "patch", "alter"],
            "delete": ["delete", "remove", "destroy", "clear", "purge", "erase"],
        }
        
        # Compile action patterns
        self._action_patterns = {}
        for action, verbs in self.action_verbs.items():
            pattern = r'\b(' + '|'.join(verbs) + r')\b'
            self._action_patterns[action] = re.compile(pattern, re.IGNORECASE)
    
    def route(self, text: str) -> RouteResult:
        """
        Route natural language text to API endpoint.
        
        Args:
            text: Natural language input
            
        Returns:
            RouteResult with endpoint, args, and confidence
        """
        if not text:
            raise RoutingError("Empty input text")
        
        # Normalize text
        text_lower = text.lower().strip()
        
        # Try different matching strategies
        candidates = []
        
        # 1. Pattern matching
        pattern_matches = self._match_by_pattern(text_lower)
        candidates.extend(pattern_matches)
        
        # 2. Keyword matching
        keyword_matches = self._match_by_keywords(text_lower)
        candidates.extend(keyword_matches)
        
        # 3. Action + resource matching
        action_matches = self._match_by_action(text_lower)
        candidates.extend(action_matches)
        
        if not candidates:
            # No matches found
            return RouteResult(
                endpoint="unknown",
                method="",
                path="",
                args={},
                confidence=0.0,
                decision=DecisionType.FALLBACK,
                reasoning="No matching endpoints found",
            )
        
        # Sort by confidence and pick best
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_stub, confidence, reasoning = candidates[0]
        
        # Extract parameters
        args = self._extract_parameters(text, best_stub)
        
        # Determine decision type
        if confidence >= 0.88:
            decision = DecisionType.DIRECT
        elif confidence >= 0.70:
            decision = DecisionType.CONFIRM
        else:
            decision = DecisionType.FALLBACK
        
        return RouteResult(
            endpoint=best_stub.name,
            method=best_stub.method,
            path=best_stub.path,
            args=args,
            confidence=confidence,
            decision=decision,
            reasoning=reasoning,
        )
    
    def _match_by_pattern(self, text: str) -> List[Tuple[Any, float, str]]:
        """Match text against stub patterns."""
        matches = []
        
        for stub in self.stub_store.list_all():
            if not stub.patterns:
                continue
                
            for pattern_str in stub.patterns:
                try:
                    pattern = re.compile(pattern_str, re.IGNORECASE)
                    match = pattern.search(text)
                    if match:
                        # Calculate confidence based on match coverage
                        coverage = len(match.group(0)) / len(text)
                        confidence = min(0.95, 0.7 + coverage * 0.25)
                        reasoning = f"Pattern match: {pattern_str}"
                        matches.append((stub, confidence, reasoning))
                        break  # Only need one pattern match per stub
                except re.error:
                    continue
        
        return matches
    
    def _match_by_keywords(self, text: str) -> List[Tuple[Any, float, str]]:
        """Match text against stub keywords."""
        matches = []
        
        # Extract words from text (lowercase)
        text_words = set(re.findall(r'\w+', text.lower()))
        
        for stub in self.stub_store.list_all():
            if not stub.keywords:
                continue
            
            # Count matching keywords (case-insensitive)
            stub_keywords = set(k.lower() for k in stub.keywords)
            common_keywords = text_words & stub_keywords
            
            if common_keywords:
                # Calculate confidence based on keyword overlap
                overlap_ratio = len(common_keywords) / len(stub_keywords)
                importance_score = self._keyword_importance_score(common_keywords)
                confidence = min(0.90, overlap_ratio * 0.6 + importance_score * 0.4)
                
                reasoning = f"Keywords: {', '.join(common_keywords)}"
                matches.append((stub, confidence, reasoning))
        
        return matches
    
    def _match_by_action(self, text: str) -> List[Tuple[Any, float, str]]:
        """Match text by action verb and resource."""
        matches = []
        
        # Detect action
        detected_action = None
        for action, pattern in self._action_patterns.items():
            if pattern.search(text):
                detected_action = action
                break
        
        if not detected_action:
            return matches
        
        # Map action to HTTP method
        method_map = {
            "create": "POST",
            "read": "GET",
            "update": ["PUT", "PATCH"],
            "delete": "DELETE",
        }
        
        expected_methods = method_map.get(detected_action, [])
        if isinstance(expected_methods, str):
            expected_methods = [expected_methods]
        
        # Find stubs with matching method
        for stub in self.stub_store.list_all():
            if stub.method not in expected_methods:
                continue
            
            # Check if resource name appears in text (case-insensitive)
            resource = self._extract_resource_from_path(stub.path)
            if resource and resource.lower() in text.lower():
                confidence = 0.85
                reasoning = f"Action '{detected_action}' + resource '{resource}'"
                matches.append((stub, confidence, reasoning))
        
        return matches
    
    def _extract_resource_from_path(self, path: str) -> Optional[str]:
        """Extract resource name from API path."""
        # Remove leading slash and parameters
        clean_path = path.strip("/")
        clean_path = re.sub(r'\{[^}]+\}', '', clean_path)
        
        # Get first meaningful part
        parts = [p for p in clean_path.split("/") if p]
        if parts:
            resource = parts[0]
            # Singularize if needed
            if resource.endswith("s"):
                return resource[:-1]
            return resource
        
        return None
    
    def _keyword_importance_score(self, keywords: set) -> float:
        """Calculate importance score for keywords."""
        # Important keywords get higher scores
        important_words = {
            "create", "add", "new", "delete", "remove", "update",
            "edit", "get", "list", "fetch", "user", "account",
            "order", "product", "item", "cart", "payment",
        }
        
        important_count = len(keywords & important_words)
        if not keywords:
            return 0.0
        
        return min(1.0, important_count / len(keywords))
    
    def _extract_parameters(self, text: str, stub) -> Dict[str, Any]:
        """Extract parameters from text for the stub."""
        args = {}
        
        if not stub.input_schema:
            return args
        
        # Get schema properties
        properties = stub.input_schema.get("properties", {})
        required = stub.input_schema.get("required", [])
        
        for prop_name, prop_schema in properties.items():
            value = self._extract_single_parameter(text, prop_name, prop_schema)
            if value is not None:
                args[prop_name] = value
            elif prop_name in required:
                # Try to extract based on type
                if prop_schema.get("type") == "string":
                    # Extract quoted strings or specific patterns
                    value = self._extract_string_value(text, prop_name)
                    if value:
                        args[prop_name] = value
        
        return args
    
    def _extract_single_parameter(
        self,
        text: str,
        param_name: str,
        schema: Dict[str, Any]
    ) -> Optional[Any]:
        """Extract a single parameter from text."""
        param_type = schema.get("type", "string")
        
        # Look for explicit mentions (e.g., "name: alice", "id=123")
        patterns = [
            rf'{param_name}[:\s=]+["\']*([^"\',\s]+)',
            rf'{param_name}\s+is\s+["\']*([^"\',\s]+)',
            rf'with\s+{param_name}\s+["\']*([^"\',\s]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                return self._convert_value(value, param_type)
        
        # Check for enum values
        if "enum" in schema:
            for enum_value in schema["enum"]:
                if str(enum_value).lower() in text.lower():
                    return enum_value
        
        # Check for pattern-based extraction
        if "pattern" in schema:
            pattern = re.compile(schema["pattern"])
            match = pattern.search(text)
            if match:
                return self._convert_value(match.group(0), param_type)
        
        return None
    
    def _extract_string_value(self, text: str, param_name: str) -> Optional[str]:
        """Extract string value from text."""
        # Look for quoted strings
        quotes = re.findall(r'["\'](.*?)["\']', text)
        if quotes:
            # Use the first quoted string
            return quotes[0]
        
        # Look for value after certain keywords
        if param_name in ["name", "username", "title", "label"]:
            patterns = [
                r'(?:called|named|titled)\s+(\w+)',
                r'(?:new|create|add)\s+\w+\s+(\w+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1)
        
        return None
    
    def _convert_value(self, value: str, target_type: str) -> Any:
        """Convert string value to target type."""
        if target_type == "integer":
            try:
                return int(value)
            except ValueError:
                return None
        elif target_type == "number":
            try:
                return float(value)
            except ValueError:
                return None
        elif target_type == "boolean":
            return value.lower() in ["true", "yes", "1", "on"]
        else:
            return value
