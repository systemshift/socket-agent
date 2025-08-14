"""LangChain tool adapter for socket-agent client."""

from typing import Any, Dict, Optional, Type

from ..client import Client


def create_langchain_tool(
    service_url: str,
    **client_kwargs
) -> "BaseTool":
    """
    Create a LangChain tool from a socket-agent service.
    
    Args:
        service_url: URL of the socket-agent service
        **client_kwargs: Additional arguments for Client
        
    Returns:
        LangChain tool instance
    """
    try:
        from langchain.tools import BaseTool
        from pydantic import BaseModel, Field
    except ImportError:
        raise ImportError(
            "LangChain not installed. Install with: pip install langchain"
        )
    
    # Initialize client to get descriptor
    client = Client(service_url, **client_kwargs)
    client.start()
    
    # Create input schema
    class SocketAgentInput(BaseModel):
        query: str = Field(description="Natural language query for the API")
    
    # Create tool class
    class SocketAgentTool(BaseTool):
        name: str = f"socket_agent_{client.descriptor.name.replace(' ', '_').lower()}"
        description: str = f"{client.descriptor.description}. Use natural language to describe what you want to do."
        args_schema: Type[BaseModel] = SocketAgentInput
        client: Client = client
        
        def _run(self, query: str) -> str:
            """Execute the tool."""
            # Route and execute
            endpoint, args, confidence = self.client.route(query)
            
            # Execute based on confidence
            if confidence >= self.client.policy.short_circuit_threshold:
                result = self.client(endpoint, **args)
            else:
                result = self.client.call_via_llm(query)
            
            # Return rendered text or JSON
            if result.rendered_text:
                return result.rendered_text
            elif result.result:
                import json
                return json.dumps(result.result, indent=2, default=str)
            else:
                return f"Error: {result.error}" if result.error else "No result"
        
        async def _arun(self, query: str) -> str:
            """Async execution (not implemented, falls back to sync)."""
            return self._run(query)
    
    return SocketAgentTool()


class LangChainSocketAgentToolkit:
    """
    Toolkit for managing multiple socket-agent tools in LangChain.
    """
    
    def __init__(self):
        """Initialize toolkit."""
        self.tools = []
        self.clients = {}
    
    def add_service(self, service_url: str, **kwargs) -> "BaseTool":
        """
        Add a socket-agent service as a tool.
        
        Args:
            service_url: Service URL
            **kwargs: Client configuration
            
        Returns:
            LangChain tool
        """
        tool = create_langchain_tool(service_url, **kwargs)
        self.tools.append(tool)
        self.clients[tool.name] = tool.client
        return tool
    
    def get_tools(self) -> list:
        """
        Get all tools.
        
        Returns:
            List of LangChain tools
        """
        return self.tools
    
    def get_tool_names(self) -> list[str]:
        """
        Get tool names.
        
        Returns:
            List of tool names
        """
        return [tool.name for tool in self.tools]
    
    def get_telemetry(self) -> Dict[str, Any]:
        """
        Get telemetry for all services.
        
        Returns:
            Dictionary of service telemetry
        """
        telemetry = {}
        for name, client in self.clients.items():
            telemetry[name] = client.telemetry.summary().model_dump()
        return telemetry
    
    def close(self):
        """Clean up all clients."""
        for client in self.clients.values():
            client.close()
        self.tools.clear()
        self.clients.clear()


def create_langchain_agent_executor(
    service_urls: list[str],
    llm: Optional[Any] = None,
    **kwargs
) -> Any:
    """
    Create a LangChain agent executor with socket-agent tools.
    
    Args:
        service_urls: List of socket-agent service URLs
        llm: LangChain LLM instance
        **kwargs: Additional configuration
        
    Returns:
        AgentExecutor instance
    """
    try:
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain.prompts import PromptTemplate
    except ImportError:
        raise ImportError(
            "LangChain not installed. Install with: pip install langchain"
        )
    
    if llm is None:
        raise ValueError("LLM instance required for agent executor")
    
    # Create toolkit
    toolkit = LangChainSocketAgentToolkit()
    
    # Add all services
    for url in service_urls:
        try:
            toolkit.add_service(url)
        except Exception as e:
            print(f"Warning: Could not add service {url}: {e}")
    
    tools = toolkit.get_tools()
    
    if not tools:
        raise ValueError("No tools could be created from the provided services")
    
    # Create prompt
    prompt = PromptTemplate.from_template(
        """You are an AI assistant with access to various APIs through socket-agent tools.
        
Available tools:
{tools}

Tool names: {tool_names}

Use the tools to help answer the user's question. You can use natural language to describe what you want to do with each tool.

Question: {input}
Thought: {agent_scratchpad}
"""
    )
    
    # Create agent
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
    )
    
    # Create executor
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=kwargs.get("verbose", True),
        max_iterations=kwargs.get("max_iterations", 5),
    )
    
    # Attach toolkit for cleanup
    executor.toolkit = toolkit
    
    return executor


class SocketAgentLangChainTool:
    """
    Advanced LangChain tool with caching and telemetry.
    """
    
    def __init__(self, service_url: str, **kwargs):
        """
        Initialize tool.
        
        Args:
            service_url: Socket-agent service URL
            **kwargs: Client configuration
        """
        try:
            from langchain.tools import BaseTool
            from langchain.callbacks.manager import CallbackManagerForToolRun
            from pydantic import BaseModel, Field
        except ImportError:
            raise ImportError(
                "LangChain not installed. Install with: pip install langchain"
            )
        
        self.client = Client(service_url, **kwargs)
        self.client.start()
        
        # Create the tool class
        class CustomTool(BaseTool):
            name: str = f"socket_agent_{self.client.descriptor.name.replace(' ', '_').lower()}"
            description: str = self._build_description()
            client: Client = self.client
            return_direct: bool = kwargs.get("return_direct", False)
            
            class InputSchema(BaseModel):
                query: str = Field(description="Natural language query")
                use_cache: bool = Field(default=True, description="Use cache if available")
            
            args_schema: Type[BaseModel] = InputSchema
            
            def _run(
                self,
                query: str,
                use_cache: bool = True,
                run_manager: Optional[CallbackManagerForToolRun] = None,
            ) -> str:
                """Execute the tool."""
                # Route the query
                endpoint, args, confidence = self.client.route(query)
                
                # Log to callback manager
                if run_manager:
                    run_manager.on_text(
                        f"Routing confidence: {confidence:.2f}\n",
                        verbose=True
                    )
                
                # Execute
                if confidence >= self.client.policy.short_circuit_threshold:
                    result = self.client(endpoint, **args)
                    via = "direct"
                else:
                    result = self.client.call_via_llm(query)
                    via = "llm"
                
                # Log telemetry
                if run_manager:
                    run_manager.on_text(
                        f"Execution via: {via}, Tokens: {result.tokens_used}\n",
                        verbose=True
                    )
                
                # Return result
                if result.rendered_text:
                    return result.rendered_text
                elif result.result:
                    import json
                    return json.dumps(result.result, indent=2, default=str)
                else:
                    return f"Error: {result.error}" if result.error else "No result"
            
            async def _arun(
                self,
                query: str,
                use_cache: bool = True,
                run_manager: Optional[Any] = None,
            ) -> str:
                """Async execution."""
                # For now, fall back to sync
                return self._run(query, use_cache, run_manager)
        
        self.tool = CustomTool()
    
    def _build_description(self) -> str:
        """Build detailed tool description."""
        desc = f"{self.client.descriptor.description}\n\nEndpoints:\n"
        
        for ep in self.client.descriptor.endpoints:
            desc += f"- {ep.summary}\n"
        
        desc += "\nUse natural language to describe what you want to do."
        return desc
    
    def get_tool(self) -> "BaseTool":
        """Get the LangChain tool."""
        return self.tool
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry summary."""
        return self.client.telemetry.summary().model_dump()
    
    def close(self):
        """Clean up resources."""
        self.client.close()
