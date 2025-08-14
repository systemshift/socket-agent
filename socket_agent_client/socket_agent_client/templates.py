"""Response template rendering for socket-agent client."""

import json
import re
from typing import Any, Dict, Optional

from .exceptions import TemplateError


class Renderer:
    """Renders API responses using templates."""
    
    def __init__(self):
        """Initialize renderer."""
        self.templates: Dict[str, str] = {}
        self._jmespath = None
        self._jinja2 = None
        
        # Try to import optional dependencies
        try:
            import jmespath
            self._jmespath = jmespath
        except ImportError:
            pass
        
        try:
            from jinja2 import Template, Environment, meta
            self._jinja2 = Template
            self._jinja_env = Environment()
        except ImportError:
            pass
    
    def load_templates(self, descriptor):
        """
        Load templates from descriptor.
        
        Args:
            descriptor: API descriptor with response_templates
        """
        if hasattr(descriptor, 'response_templates'):
            self.templates = dict(descriptor.response_templates)
    
    def render(
        self,
        endpoint: str,
        data: Any,
        template: Optional[str] = None,
    ) -> str:
        """
        Render response data using template.
        
        Args:
            endpoint: Endpoint name or path
            data: Response data to render
            template: Optional template override
            
        Returns:
            Rendered text string
        """
        # Get template
        if template is None:
            template = self.templates.get(endpoint)
        
        if not template:
            # No template, return JSON representation
            return self._default_render(data)
        
        try:
            # Detect template type and render
            if template.startswith("jmespath:"):
                return self._render_jmespath(template[9:], data)
            elif "{{" in template or "{%" in template:
                return self._render_jinja2(template, data)
            else:
                return self._render_simple(template, data)
        except Exception as e:
            raise TemplateError(f"Failed to render template: {e}") from e
    
    def _default_render(self, data: Any) -> str:
        """Default rendering for data without template."""
        if data is None:
            return "Success"
        
        if isinstance(data, dict):
            # Special handling for common patterns
            if "message" in data:
                return data["message"]
            elif "status" in data:
                return f"Status: {data['status']}"
            elif "id" in data and "name" in data:
                return f"{data['name']} (ID: {data['id']})"
            elif "id" in data:
                return f"Created with ID: {data['id']}"
            elif "success" in data:
                return "Success" if data["success"] else "Failed"
            elif "result" in data:
                return self._default_render(data["result"])
        
        elif isinstance(data, list):
            if not data:
                return "Empty list"
            elif len(data) == 1:
                return f"1 item: {self._default_render(data[0])}"
            else:
                return f"{len(data)} items"
        
        elif isinstance(data, (str, int, float, bool)):
            return str(data)
        
        # Fallback to JSON
        return json.dumps(data, indent=2, default=str)
    
    def _render_simple(self, template: str, data: Any) -> str:
        """
        Simple template rendering with {key} placeholders.
        
        Example: "User {username} created with ID {id}"
        """
        if not isinstance(data, dict):
            return template
        
        # Find all placeholders
        placeholders = re.findall(r'\{(\w+)\}', template)
        
        result = template
        for placeholder in placeholders:
            value = self._get_nested_value(data, placeholder)
            if value is not None:
                result = result.replace(f"{{{placeholder}}}", str(value))
        
        return result
    
    def _render_jinja2(self, template: str, data: Any) -> str:
        """
        Jinja2 template rendering.
        
        Example: "User {{ user.name }} ({{ user.email }})"
        """
        if not self._jinja2:
            # Fallback to simple rendering
            return self._render_simple(template, data)
        
        try:
            tmpl = self._jinja2(template)
            return tmpl.render(data if isinstance(data, dict) else {"data": data})
        except Exception as e:
            raise TemplateError(f"Jinja2 rendering failed: {e}") from e
    
    def _render_jmespath(self, expression: str, data: Any) -> str:
        """
        JMESPath expression rendering.
        
        Example: "jmespath:items[].{name: name, price: price}"
        """
        if not self._jmespath:
            raise TemplateError("JMESPath not available. Install 'jmespath' package.")
        
        try:
            result = self._jmespath.search(expression, data)
            if isinstance(result, (dict, list)):
                return json.dumps(result, indent=2, default=str)
            return str(result) if result is not None else ""
        except Exception as e:
            raise TemplateError(f"JMESPath evaluation failed: {e}") from e
    
    def _get_nested_value(self, data: dict, path: str) -> Any:
        """
        Get nested value from dictionary using dot notation.
        
        Example: "user.profile.name" -> data["user"]["profile"]["name"]
        """
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current
    
    def add_template(self, endpoint: str, template: str):
        """Add or update a template."""
        self.templates[endpoint] = template
    
    def remove_template(self, endpoint: str):
        """Remove a template."""
        self.templates.pop(endpoint, None)
    
    def clear_templates(self):
        """Clear all templates."""
        self.templates.clear()


class TemplateBuilder:
    """Helper to build templates from examples."""
    
    @staticmethod
    def from_example(response_data: dict, desired_output: str) -> str:
        """
        Generate a template from example data and desired output.
        
        Args:
            response_data: Example API response
            desired_output: Desired rendered output
            
        Returns:
            Template string
        """
        # Try to identify placeholders in desired output
        template = desired_output
        
        # Find potential values in response that appear in output
        for key, value in response_data.items():
            if isinstance(value, (str, int, float)) and str(value) in desired_output:
                # Replace value with placeholder
                template = template.replace(str(value), f"{{{key}}}")
        
        return template
    
    @staticmethod
    def suggest_template(endpoint: str, response_schema: dict) -> str:
        """
        Suggest a template based on endpoint and schema.
        
        Args:
            endpoint: Endpoint name/path
            response_schema: JSON Schema of response
            
        Returns:
            Suggested template string
        """
        # Extract key fields from schema
        if not response_schema or "properties" not in response_schema:
            return ""
        
        props = response_schema["properties"]
        
        # Common patterns
        if "id" in props and "name" in props:
            return "{name} (ID: {id})"
        elif "message" in props:
            return "{message}"
        elif "status" in props:
            return "Status: {status}"
        elif "success" in props:
            return "Operation {'successful' if success else 'failed'}"
        elif "items" in props and response_schema.get("type") == "object":
            return "Found {len(items)} items"
        
        # Build from available fields
        fields = []
        for key in ["title", "name", "label", "description", "value", "result"]:
            if key in props:
                fields.append(f"{{{key}}}")
        
        if fields:
            return " - ".join(fields)
        
        # Fallback
        return "Response received"


def create_renderer(descriptor=None) -> Renderer:
    """
    Create a renderer with templates from descriptor.
    
    Args:
        descriptor: Optional API descriptor
        
    Returns:
        Configured Renderer instance
    """
    renderer = Renderer()
    if descriptor:
        renderer.load_templates(descriptor)
    return renderer
