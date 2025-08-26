"""Parameter extraction from natural language text."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class ParameterExtractor:
    """Extracts API parameters from natural language text."""
    
    def __init__(self):
        """Initialize parameter extractor."""
        # Common patterns for different data types
        self.patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "url": r'https?://[^\s]+',
            "phone": r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}',
            "date": r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
            "time": r'\b\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?\b',
            "number": r'\b\d+(?:\.\d+)?\b',
            "uuid": r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
            "ip": r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
        }
        
        # Compile patterns
        self.compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.patterns.items()
        }
    
    def extract(
        self,
        text: str,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract parameters from text.
        
        Args:
            text: Natural language text
            schema: Optional JSON schema for guidance
            
        Returns:
            Dictionary of extracted parameters
        """
        params = {}
        
        if schema:
            # Schema-guided extraction
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            
            for prop_name, prop_schema in properties.items():
                value = self.extract_single(text, prop_name, prop_schema)
                if value is not None:
                    params[prop_name] = value
                elif prop_name in required:
                    # Try harder for required fields
                    value = self._extract_required(text, prop_name, prop_schema)
                    if value is not None:
                        params[prop_name] = value
        else:
            # Heuristic extraction
            params = self._extract_heuristic(text)
        
        return params
    
    def extract_single(
        self,
        text: str,
        param_name: str,
        schema: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Extract a single parameter from text.
        
        Args:
            text: Input text
            param_name: Parameter name
            schema: Parameter schema
            
        Returns:
            Extracted value or None
        """
        param_type = schema.get("type", "string")
        
        # Try different extraction strategies
        strategies = [
            self._extract_by_name_mention,
            self._extract_by_type_pattern,
            self._extract_by_enum,
            self._extract_by_schema_pattern,
            self._extract_by_context,
        ]
        
        for strategy in strategies:
            value = strategy(text, param_name, schema)
            if value is not None:
                return self._convert_type(value, param_type)
        
        return None
    
    def _extract_by_name_mention(
        self,
        text: str,
        param_name: str,
        schema: Dict[str, Any]
    ) -> Optional[str]:
        """Extract by explicit parameter name mention."""
        # Patterns for explicit mentions
        patterns = [
            # "param_name: value" or "param_name = value"
            rf'{param_name}[\s:=]+["\']*([^"\',\n]+)',
            # "param_name is value"
            rf'{param_name}\s+is\s+["\']*([^"\',\n]+)',
            # "with param_name value"
            rf'with\s+{param_name}\s+["\']*([^"\',\n]+)',
            # "set param_name to value"
            rf'set\s+{param_name}\s+to\s+["\']*([^"\',\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_by_type_pattern(
        self,
        text: str,
        param_name: str,
        schema: Dict[str, Any]
    ) -> Optional[str]:
        """Extract by data type pattern."""
        param_type = schema.get("type", "string")
        format_hint = schema.get("format", "")
        
        # Map schema types/formats to pattern names
        type_pattern_map = {
            ("string", "email"): "email",
            ("string", "uri"): "url",
            ("string", "date"): "date",
            ("string", "date-time"): "date",
            ("string", "time"): "time",
            ("string", "uuid"): "uuid",
            ("string", "ipv4"): "ip",
            ("string", "phone"): "phone",
            ("integer", ""): "number",
            ("number", ""): "number",
        }
        
        pattern_name = type_pattern_map.get((param_type, format_hint))
        if pattern_name and pattern_name in self.compiled_patterns:
            pattern = self.compiled_patterns[pattern_name]
            matches = pattern.findall(text)
            if matches:
                # Return first match
                return matches[0] if isinstance(matches[0], str) else str(matches[0])
        
        return None
    
    def _extract_by_enum(
        self,
        text: str,
        param_name: str,
        schema: Dict[str, Any]
    ) -> Optional[Any]:
        """Extract enum values."""
        if "enum" not in schema:
            return None
        
        text_lower = text.lower()
        for enum_value in schema["enum"]:
            # Check exact match
            if str(enum_value).lower() in text_lower:
                return enum_value
            
            # Check partial match for longer enum values
            if len(str(enum_value)) > 3:
                if str(enum_value)[:3].lower() in text_lower:
                    return enum_value
        
        return None
    
    def _extract_by_schema_pattern(
        self,
        text: str,
        param_name: str,
        schema: Dict[str, Any]
    ) -> Optional[str]:
        """Extract using schema-defined pattern."""
        if "pattern" not in schema:
            return None
        
        try:
            pattern = re.compile(schema["pattern"], re.IGNORECASE)
            match = pattern.search(text)
            if match:
                return match.group(0)
        except re.error:
            pass
        
        return None
    
    def _extract_by_context(
        self,
        text: str,
        param_name: str,
        schema: Dict[str, Any]
    ) -> Optional[str]:
        """Extract based on contextual clues."""
        param_type = schema.get("type", "string")
        
        # Common parameter names and their extraction patterns
        context_patterns = {
            "username": [
                r'user(?:name)?\s+(?:is\s+)?([a-zA-Z0-9_]+)',
                r'(?:as|for)\s+([a-zA-Z0-9_]+)',
            ],
            "password": [
                r'password\s+(?:is\s+)?([^\s]+)',
                r'with\s+password\s+([^\s]+)',
            ],
            "name": [
                r'(?:called|named)\s+([a-zA-Z\s]+?)(?:\s|$)',
                r'name\s+(?:is\s+)?([a-zA-Z\s]+?)(?:\s|$)',
            ],
            "title": [
                r'(?:titled|called)\s+"([^"]+)"',
                r'title\s+(?:is\s+)?([^,\n]+)',
            ],
            "description": [
                r'description\s+(?:is\s+)?["\']([^"\']+)',
                r'described\s+as\s+["\']([^"\']+)',
            ],
            "id": [
                r'(?:id|ID)\s+(?:is\s+)?([a-zA-Z0-9-_]+)',
                r'#([a-zA-Z0-9-_]+)',
            ],
            "quantity": [
                r'(\d+)\s+(?:items?|pieces?|units?)',
                r'quantity\s+(?:of\s+)?(\d+)',
            ],
            "price": [
                r'\$([0-9]+(?:\.[0-9]{2})?)',
                r'([0-9]+(?:\.[0-9]{2})?)\s+(?:dollars?|USD)',
            ],
        }
        
        # Check if parameter name matches known patterns
        for known_param, patterns in context_patterns.items():
            if known_param in param_name.lower():
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
        
        # For string types, try to extract quoted values
        if param_type == "string":
            quotes = re.findall(r'["\'](.*?)["\']', text)
            if quotes:
                # Return the first quoted string
                return quotes[0]
        
        return None
    
    def _extract_required(
        self,
        text: str,
        param_name: str,
        schema: Dict[str, Any]
    ) -> Optional[Any]:
        """Try harder to extract required parameters."""
        param_type = schema.get("type", "string")
        
        # For required strings, be more aggressive
        if param_type == "string":
            # Look for any quoted string
            quotes = re.findall(r'["\'](.*?)["\']', text)
            if quotes:
                return quotes[0]
            
            # Look for value after common prepositions
            patterns = [
                rf'(?:for|with|of|about)\s+([a-zA-Z0-9_]+)',
                rf'([a-zA-Z0-9_]+)\s+(?:is|are|was|were)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1)
        
        elif param_type in ["integer", "number"]:
            # Extract any number
            numbers = re.findall(r'\b\d+(?:\.\d+)?\b', text)
            if numbers:
                return numbers[0]
        
        return None
    
    def _extract_heuristic(self, text: str) -> Dict[str, Any]:
        """Extract parameters without schema guidance."""
        params = {}
        
        # Extract common data types
        for data_type, pattern in self.compiled_patterns.items():
            matches = pattern.findall(text)
            if matches:
                # Store first match with descriptive key
                if data_type == "email":
                    params["email"] = matches[0]
                elif data_type == "url":
                    params["url"] = matches[0]
                elif data_type == "phone":
                    params["phone"] = matches[0]
                elif data_type == "date":
                    params["date"] = matches[0]
                elif data_type == "uuid":
                    params["id"] = matches[0]
        
        # Extract quoted strings
        quotes = re.findall(r'["\'](.*?)["\']', text)
        if quotes:
            # Guess parameter names based on content
            for i, quote in enumerate(quotes[:3]):  # Limit to first 3
                if "@" in quote:
                    params["email"] = quote
                elif len(quote) < 20:
                    params[f"value{i+1}"] = quote
                else:
                    params["text"] = quote
        
        # Extract numbers
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', text)
        if numbers:
            # Try to identify what the numbers represent
            for num in numbers[:2]:  # Limit to first 2
                num_float = float(num)
                if "quantity" not in params and num_float == int(num_float):
                    params["quantity"] = int(num_float)
                elif "amount" not in params:
                    params["amount"] = num_float
        
        return params
    
    def _convert_type(self, value: str, target_type: str) -> Any:
        """Convert extracted value to target type."""
        if target_type == "integer":
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        elif target_type == "number":
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        elif target_type == "boolean":
            return value.lower() in ["true", "yes", "1", "on", "enabled"]
        elif target_type == "array":
            # Try to split comma-separated values
            if "," in value:
                return [v.strip() for v in value.split(",")]
            return [value]
        else:
            # Default to string
            return str(value)


def extract_parameters(
    text: str,
    schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to extract parameters.
    
    Args:
        text: Input text
        schema: Optional JSON schema
        
    Returns:
        Extracted parameters
    """
    extractor = ParameterExtractor()
    return extractor.extract(text, schema)
