"""MCP (Model Context Protocol) adapter for socket-agent client."""

from typing import Any, Dict, Optional

from ..client import Client


def create_mcp_tool(
    service_url: str,
    threshold: float = 0.88,
    **client_kwargs
) -> callable:
    """
    Create an MCP-compatible tool from a socket-agent service.
    
    Args:
        service_url: URL of the socket-agent service
        threshold: Confidence threshold for short-circuiting
        **client_kwargs: Additional arguments for Client
        
    Returns:
        MCP tool function
    """
    # Initialize client
    client = Client(service_url, **client_kwargs)
    client.start()
    
    def mcp_tool(query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        MCP tool implementation.
        
        Args:
            query: Natural language query
            context: Optional context dictionary
            
        Returns:
            Tool execution result
        """
        # Route the query
        endpoint, args, confidence = client.route(query)
        
        # Add context to args if provided
        if context:
            args.update(context)
        
        # Decide based on confidence
        if confidence >= threshold:
            # Direct call (short-circuit)
            result = client(endpoint, **args)
            
            return {
                "decision": "stub",
                "endpoint": endpoint,
                "args": args,
                "confidence": confidence,
                "result": result.result,
                "rendered_text": result.rendered_text,
                "tokens": 0,
                "cache_hit": result.cache_hit,
                "latency_ms": result.duration_ms,
            }
        else:
            # Fallback to LLM
            result = client.call_via_llm(query)
            
            return {
                "decision": "fallback",
                "endpoint": endpoint,
                "args": args,
                "confidence": confidence,
                "result": result.result,
                "rendered_text": result.rendered_text,
                "tokens": result.tokens_used,
                "cache_hit": False,
                "latency_ms": result.duration_ms,
            }
    
    # Add metadata for MCP
    mcp_tool.__name__ = f"socket_agent_{client.descriptor.name.replace(' ', '_').lower()}"
    mcp_tool.__doc__ = f"""
    {client.descriptor.description}
    
    Available endpoints:
    {chr(10).join(f"  - {ep.method} {ep.path}: {ep.summary}" for ep in client.descriptor.endpoints)}
    """
    
    # MCP metadata
    mcp_tool.mcp_metadata = {
        "name": mcp_tool.__name__,
        "description": client.descriptor.description,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query for the API"
                },
                "context": {
                    "type": "object",
                    "description": "Optional context parameters"
                }
            },
            "required": ["query"]
        }
    }
    
    return mcp_tool


class MCPToolWrapper:
    """
    Wrapper class for MCP tool with state management.
    """
    
    def __init__(self, service_url: str, **kwargs):
        """
        Initialize MCP tool wrapper.
        
        Args:
            service_url: Socket-agent service URL
            **kwargs: Client configuration
        """
        self.client = Client(service_url, **kwargs)
        self.client.start()
        
        # Track usage for learning
        self.usage_history = []
    
    def __call__(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Execute tool with query.
        
        Args:
            query: Natural language query
            **kwargs: Additional parameters
            
        Returns:
            Execution result
        """
        # Route and execute
        endpoint, args, confidence = self.client.route(query)
        
        # Merge kwargs into args
        args.update(kwargs)
        
        # Execute based on confidence
        if confidence >= self.client.policy.short_circuit_threshold:
            result = self.client(endpoint, **args)
            via = "direct"
        else:
            result = self.client.call_via_llm(query)
            via = "llm"
        
        # Track usage
        self.usage_history.append({
            "query": query,
            "endpoint": endpoint,
            "confidence": confidence,
            "via": via,
            "success": result.success,
        })
        
        return {
            "success": result.success,
            "data": result.result,
            "text": result.rendered_text,
            "metadata": {
                "endpoint": endpoint,
                "confidence": confidence,
                "via": via,
                "tokens": result.tokens_used,
                "cache_hit": result.cache_hit,
            }
        }
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry summary."""
        return self.client.telemetry.summary().model_dump()
    
    def export_learning(self, filepath: str):
        """Export learned patterns."""
        self.client.export_stubs(filepath)
    
    def close(self):
        """Clean up resources."""
        self.client.close()


def create_mcp_server_config(
    service_url: str,
    name: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create MCP server configuration for a socket-agent service.
    
    Args:
        service_url: Socket-agent service URL
        name: Optional server name
        **kwargs: Additional configuration
        
    Returns:
        MCP server configuration dictionary
    """
    # Fetch descriptor to get metadata
    from ..descriptor import fetch_descriptor
    descriptor = fetch_descriptor(service_url)
    
    return {
        "name": name or descriptor.name,
        "description": descriptor.description,
        "type": "socket-agent",
        "config": {
            "service_url": service_url,
            "endpoints": [
                {
                    "path": ep.path,
                    "method": ep.method,
                    "summary": ep.summary,
                }
                for ep in descriptor.endpoints
            ],
            **kwargs
        }
    }
