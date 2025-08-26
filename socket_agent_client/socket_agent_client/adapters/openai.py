"""OpenAI function calling adapter for socket-agent client."""

from typing import Any, Dict, List, Optional

from ..client import Client


def create_openai_function(
    service_url: str,
    **client_kwargs
) -> Dict[str, Any]:
    """
    Create an OpenAI function definition from a socket-agent service.
    
    Args:
        service_url: URL of the socket-agent service
        **client_kwargs: Additional arguments for Client
        
    Returns:
        OpenAI function definition dictionary
    """
    # Initialize client to get descriptor
    client = Client(service_url, **client_kwargs)
    client.start()
    
    # Build function definition
    function_def = {
        "name": f"call_{client.descriptor.name.replace(' ', '_').lower()}",
        "description": f"{client.descriptor.description}. You can use natural language to describe what you want to do.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language description of the API call to make"
                }
            },
            "required": ["query"]
        }
    }
    
    return function_def


class OpenAIFunctionHandler:
    """
    Handler for OpenAI function calls with socket-agent.
    """
    
    def __init__(self, service_url: str, **kwargs):
        """
        Initialize OpenAI function handler.
        
        Args:
            service_url: Socket-agent service URL
            **kwargs: Client configuration
        """
        self.client = Client(service_url, **kwargs)
        self.client.start()
        self.function_name = f"call_{self.client.descriptor.name.replace(' ', '_').lower()}"
    
    def get_function_definition(self) -> Dict[str, Any]:
        """
        Get OpenAI function definition.
        
        Returns:
            Function definition dictionary
        """
        # Build detailed parameters from endpoints
        properties = {
            "query": {
                "type": "string",
                "description": "Natural language query"
            }
        }
        
        # Add endpoint-specific hints
        endpoint_descriptions = []
        for endpoint in self.client.descriptor.endpoints:
            endpoint_descriptions.append(
                f"- {endpoint.summary} (use phrases like: {self._get_example_phrases(endpoint)})"
            )
        
        description = f"{self.client.descriptor.description}\n\nAvailable operations:\n" + "\n".join(endpoint_descriptions)
        
        return {
            "name": self.function_name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": ["query"]
            }
        }
    
    def _get_example_phrases(self, endpoint) -> str:
        """Get example phrases for an endpoint."""
        method = endpoint.method.lower()
        resource = endpoint.path.strip("/").split("/")[0] if "/" in endpoint.path else endpoint.path.strip("/")
        
        if method == "post":
            return f"'create {resource}', 'add new {resource}'"
        elif method == "get":
            if "{" in endpoint.path:
                return f"'get {resource}', 'show {resource}'"
            else:
                return f"'list {resource}', 'show all {resource}'"
        elif method in ["put", "patch"]:
            return f"'update {resource}', 'edit {resource}'"
        elif method == "delete":
            return f"'delete {resource}', 'remove {resource}'"
        else:
            return endpoint.summary.lower()
    
    def handle_function_call(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an OpenAI function call.
        
        Args:
            arguments: Function arguments from OpenAI
            
        Returns:
            Function execution result
        """
        query = arguments.get("query", "")
        
        # Route and execute
        endpoint, args, confidence = self.client.route(query)
        
        # Execute based on confidence
        if confidence >= self.client.policy.short_circuit_threshold:
            result = self.client(endpoint, **args)
            
            return {
                "success": result.success,
                "result": result.result,
                "text": result.rendered_text or str(result.result),
                "metadata": {
                    "endpoint": endpoint,
                    "confidence": confidence,
                    "via": "direct",
                    "tokens_saved": 500,  # Estimate
                }
            }
        else:
            # Low confidence, might need LLM help
            result = self.client.call_via_llm(query)
            
            return {
                "success": result.success,
                "result": result.result,
                "text": result.rendered_text or str(result.result),
                "metadata": {
                    "endpoint": "unknown",
                    "confidence": confidence,
                    "via": "llm",
                    "tokens_used": result.tokens_used,
                }
            }
    
    def create_tool_choice(self) -> Dict[str, Any]:
        """
        Create tool_choice parameter for OpenAI.
        
        Returns:
            Tool choice dictionary
        """
        return {
            "type": "function",
            "function": {"name": self.function_name}
        }


def create_openai_tools(service_urls: List[str], **kwargs) -> List[Dict[str, Any]]:
    """
    Create multiple OpenAI function definitions from socket-agent services.
    
    Args:
        service_urls: List of socket-agent service URLs
        **kwargs: Client configuration
        
    Returns:
        List of OpenAI function definitions
    """
    tools = []
    
    for url in service_urls:
        try:
            function_def = create_openai_function(url, **kwargs)
            tools.append({"type": "function", "function": function_def})
        except Exception as e:
            print(f"Warning: Could not create function for {url}: {e}")
    
    return tools


class OpenAISocketAgentIntegration:
    """
    Full integration for using socket-agent with OpenAI.
    """
    
    def __init__(self):
        """Initialize integration."""
        self.handlers = {}
    
    def add_service(self, service_url: str, **kwargs) -> str:
        """
        Add a socket-agent service.
        
        Args:
            service_url: Service URL
            **kwargs: Client configuration
            
        Returns:
            Function name
        """
        handler = OpenAIFunctionHandler(service_url, **kwargs)
        function_name = handler.function_name
        self.handlers[function_name] = handler
        return function_name
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get all tool definitions for OpenAI.
        
        Returns:
            List of tool definitions
        """
        tools = []
        for handler in self.handlers.values():
            tools.append({
                "type": "function",
                "function": handler.get_function_definition()
            })
        return tools
    
    def handle_tool_call(self, tool_call) -> Dict[str, Any]:
        """
        Handle a tool call from OpenAI.
        
        Args:
            tool_call: Tool call object from OpenAI
            
        Returns:
            Tool execution result
        """
        function_name = tool_call.function.name
        
        if function_name not in self.handlers:
            return {
                "error": f"Unknown function: {function_name}"
            }
        
        import json
        arguments = json.loads(tool_call.function.arguments)
        
        handler = self.handlers[function_name]
        return handler.handle_function_call(arguments)
    
    def get_telemetry(self) -> Dict[str, Dict[str, Any]]:
        """
        Get telemetry for all services.
        
        Returns:
            Dictionary of service telemetry
        """
        telemetry = {}
        for name, handler in self.handlers.items():
            telemetry[name] = handler.client.telemetry.summary().model_dump()
        return telemetry
    
    def close(self):
        """Clean up all handlers."""
        for handler in self.handlers.values():
            handler.client.close()
        self.handlers.clear()
