#!/usr/bin/env python3
"""
Real LLM Agent using socket-agent
This demonstrates how an actual LLM would discover and interact with APIs.
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional
import httpx

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()  # This loads .env file from current directory or parent directories
except ImportError:
    pass  # dotenv not installed, will use system environment variables only

# Optional: Use OpenAI for real LLM interaction
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("Note: Install openai package for real LLM interaction: pip install openai")


class LLMSocketAgent:
    """An LLM-powered agent that can discover and use socket-agent APIs."""
    
    def __init__(self, base_url: str, openai_api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.descriptor = None
        self.client = httpx.AsyncClient()
        
        if openai_api_key and HAS_OPENAI:
            self.openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
        else:
            self.openai_client = None
    
    async def discover(self) -> Dict[str, Any]:
        """Fetch and analyze the socket-agent descriptor."""
        response = await self.client.get(f"{self.base_url}/.well-known/socket-agent")
        response.raise_for_status()
        self.descriptor = response.json()
        return self.descriptor
    
    async def ask_llm(self, prompt: str) -> str:
        """Ask the LLM to analyze and respond."""
        if not self.openai_client:
            # Fallback to rule-based responses
            return self._mock_llm_response(prompt)
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an API agent. Analyze the user's request and generate appropriate API calls based on the provided API descriptor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1  # Low temperature for consistent API calls
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return self._mock_llm_response(prompt)
    
    def _mock_llm_response(self, prompt: str) -> str:
        """Simple mock responses when OpenAI is not available."""
        if "create" in prompt.lower() and "todo" in prompt.lower():
            return json.dumps({
                "action": "create_todo",
                "method": "POST",
                "endpoint": "/todo",
                "body": {"text": "New todo item"}
            })
        elif "list" in prompt.lower() or "show" in prompt.lower():
            return json.dumps({
                "action": "list_todos",
                "method": "GET",
                "endpoint": "/todos"
            })
        return json.dumps({"error": "Could not understand request"})
    
    async def process_user_request(self, user_request: str) -> Dict[str, Any]:
        """Process a natural language request using the LLM."""
        # Create a prompt with the API descriptor
        prompt = f"""
API Descriptor:
{json.dumps(self.descriptor, indent=2)}

User Request: "{user_request}"

Based on the API descriptor above, generate a JSON response with the appropriate API call.
The response should include:
- action: A brief description of what you're doing
- method: The HTTP method (GET, POST, PUT, DELETE)
- endpoint: The API endpoint path
- body: The request body (if needed)

Respond only with valid JSON.
"""
        
        # Get LLM response
        llm_response = await self.ask_llm(prompt)
        
        try:
            # Parse the LLM's JSON response
            return json.loads(llm_response)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            return {"error": "LLM response was not valid JSON", "raw": llm_response}
    
    async def execute_api_call(self, api_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the API call planned by the LLM."""
        if "error" in api_plan:
            return api_plan
        
        method = api_plan.get("method", "GET").upper()
        endpoint = api_plan.get("endpoint", "/")
        body = api_plan.get("body")
        
        # Handle both relative and absolute URLs
        if endpoint.startswith(('http://', 'https://')):
            # LLM returned full URL, use it as-is
            url = endpoint
        else:
            # LLM returned relative path, prepend base URL
            url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = await self.client.get(url)
            elif method == "POST":
                response = await self.client.post(url, json=body)
            elif method == "PUT":
                response = await self.client.put(url, json=body)
            elif method == "DELETE":
                response = await self.client.delete(url)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            return {
                "status": response.status_code,
                "data": response.json() if response.status_code < 400 else None,
                "error": response.text if response.status_code >= 400 else None
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def close(self):
        """Clean up resources."""
        await self.client.aclose()
        if self.openai_client:
            await self.openai_client.close()


async def interactive_demo():
    """Run an interactive demo where users can type commands."""
    print("=== Socket-Agent Interactive LLM Demo ===\n")
    
    # Get OpenAI API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key and HAS_OPENAI:
        print("Note: Set OPENAI_API_KEY environment variable for real LLM interaction")
        print("Using mock LLM responses instead.\n")
    
    agent = LLMSocketAgent("http://localhost:8000", api_key)
    
    try:
        # Discover the API
        print("Discovering API...")
        descriptor = await agent.discover()
        print(f"Found: {descriptor['name']} - {descriptor['description']}")
        print(f"Endpoints: {len(descriptor['endpoints'])} available\n")
        
        # Interactive loop
        print("You can now interact with the API using natural language.")
        print("Examples:")
        print('  - "Create a todo to buy milk"')
        print('  - "Show me all my todos"')
        print('  - "Mark the first todo as complete"')
        print("\nType 'quit' to exit.\n")
        
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            
            if not user_input:
                continue
            
            # Process the request
            print("Agent: Analyzing your request...")
            api_plan = await agent.process_user_request(user_input)
            
            if "error" in api_plan:
                print(f"Agent: Sorry, I couldn't understand that. {api_plan.get('error')}")
                continue
            
            print(f"Agent: {api_plan.get('action', 'Processing request...')}")
            print(f"       (Calling {api_plan.get('method')} {api_plan.get('endpoint')})")
            
            # Execute the API call
            result = await agent.execute_api_call(api_plan)
            
            if result.get("status", 500) < 400:
                print(f"Agent: Success! Here's the result:")
                print(json.dumps(result.get("data"), indent=2))
            else:
                print(f"Agent: The request failed: {result.get('error')}")
            
            print()  # Empty line for readability
    
    finally:
        await agent.close()


async def automated_test():
    """Run automated tests showing the LLM agent in action."""
    print("\n=== Automated Test Sequence ===\n")
    
    agent = LLMSocketAgent("http://localhost:8000")
    
    try:
        await agent.discover()
        
        # Test sequence
        test_requests = [
            "Create a todo item that says 'Buy groceries'",
            "Create another todo: 'Schedule dentist appointment'",
            "Show me all the todos",
            "I need to see my todo list"
        ]
        
        for request in test_requests:
            print(f"User: {request}")
            
            # Get LLM plan
            api_plan = await agent.process_user_request(request)
            print(f"LLM Plan: {json.dumps(api_plan, indent=2)}")
            
            # Execute
            if "error" not in api_plan:
                result = await agent.execute_api_call(api_plan)
                print(f"Result: {json.dumps(result, indent=2)}")
            
            print("-" * 60)
            await asyncio.sleep(1)  # Small delay for readability
    
    finally:
        await agent.close()


if __name__ == "__main__":
    print("Make sure the Todo API is running on http://localhost:8000")
    print("Run with: cd examples/todo_fastapi && python main.py\n")
    
    # Check if we should run interactive or automated mode
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        asyncio.run(automated_test())
    else:
        asyncio.run(interactive_demo())
