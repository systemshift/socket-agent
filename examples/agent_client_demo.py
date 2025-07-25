#!/usr/bin/env python3
"""
Demo: LLM Agent interacting with a socket-agent API
This simulates how an LLM would discover and use an API.
"""

import json
import asyncio
from typing import Dict, Any
import httpx

class SocketAgentClient:
    """A simple client that discovers and interacts with socket-agent APIs."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.descriptor = None
        self.client = httpx.AsyncClient()
    
    async def discover(self) -> Dict[str, Any]:
        """Fetch the socket-agent descriptor."""
        response = await self.client.get(f"{self.base_url}/.well-known/socket-agent")
        response.raise_for_status()
        self.descriptor = response.json()
        return self.descriptor
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    def analyze_api(self) -> str:
        """Analyze the API and return a human-readable summary."""
        if not self.descriptor:
            return "No descriptor loaded. Call discover() first."
        
        summary = f"API: {self.descriptor['name']}\n"
        summary += f"Description: {self.descriptor['description']}\n\n"
        summary += "Available endpoints:\n"
        
        for endpoint in self.descriptor['endpoints']:
            summary += f"  {endpoint['method']} {endpoint['path']}: {endpoint['summary']}\n"
            
            # Add schema info if available
            if endpoint['path'] in self.descriptor.get('schema', {}):
                schema = self.descriptor['schema'][endpoint['path']]
                if 'request' in schema:
                    summary += f"    Request: {json.dumps(schema['request'], indent=6)}\n"
                if 'response' in schema:
                    summary += f"    Response: {json.dumps(schema['response'], indent=6)}\n"
        
        if self.descriptor.get('examples'):
            summary += "\nExamples:\n"
            for example in self.descriptor['examples']:
                summary += f"  {example}\n"
        
        return summary
    
    def generate_request_plan(self, user_intent: str) -> Dict[str, Any]:
        """
        Simulate an LLM analyzing user intent and generating an API call.
        In a real implementation, this would use an actual LLM.
        """
        intent_lower = user_intent.lower()
        
        # Simple intent matching (in reality, an LLM would do this)
        if "create" in intent_lower and "todo" in intent_lower:
            # Extract the todo text (simple regex in real LLM)
            import re
            match = re.search(r'"([^"]+)"', user_intent)
            todo_text = match.group(1) if match else "New todo"
            
            return {
                "method": "POST",
                "endpoint": "/todo",
                "body": {"text": todo_text},
                "explanation": f"Creating a new todo with text: '{todo_text}'"
            }
        
        elif "list" in intent_lower or "show" in intent_lower:
            return {
                "method": "GET",
                "endpoint": "/todos",
                "explanation": "Fetching all todos"
            }
        
        elif "complete" in intent_lower or "done" in intent_lower:
            # Extract ID if mentioned
            match = re.search(r'\b([a-f0-9-]{36})\b', user_intent)
            todo_id = match.group(1) if match else "example-id"
            
            return {
                "method": "PUT",
                "endpoint": f"/todo/{todo_id}/complete",
                "explanation": f"Marking todo {todo_id} as completed"
            }
        
        return {
            "error": "Could not understand the intent",
            "available_actions": [
                "Create a todo: 'create todo \"buy milk\"'",
                "List todos: 'show all todos'",
                "Complete a todo: 'mark todo {id} as done'"
            ]
        }
    
    async def execute_request(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the planned API request."""
        if "error" in plan:
            return plan
        
        url = f"{self.base_url}{plan['endpoint']}"
        
        if plan["method"] == "GET":
            response = await self.client.get(url)
        elif plan["method"] == "POST":
            response = await self.client.post(url, json=plan.get("body"))
        elif plan["method"] == "PUT":
            response = await self.client.put(url, json=plan.get("body"))
        elif plan["method"] == "DELETE":
            response = await self.client.delete(url)
        else:
            return {"error": f"Unsupported method: {plan['method']}"}
        
        return {
            "status": response.status_code,
            "data": response.json() if response.status_code < 400 else None,
            "error": response.text if response.status_code >= 400 else None
        }


async def demo_llm_interaction():
    """Demonstrate how an LLM agent would interact with the API."""
    print("=== Socket-Agent LLM Demo ===\n")
    
    # Initialize client
    client = SocketAgentClient("http://localhost:8000")
    
    try:
        # Step 1: Discover the API
        print("1. Discovering API...")
        descriptor = await client.discover()
        print(f"   Found: {descriptor['name']}")
        print(f"   Descriptor size: {len(json.dumps(descriptor))} bytes\n")
        
        # Step 2: Analyze what's available
        print("2. Analyzing API capabilities...")
        print(client.analyze_api())
        
        # Step 3: Simulate user requests
        print("\n3. Simulating user interactions...\n")
        
        # Test cases simulating what a user might ask an LLM
        test_intents = [
            'Create a todo "Buy groceries"',
            'Show me all todos',
            'Create another todo "Call dentist"',
            'List my todos'
        ]
        
        for intent in test_intents:
            print(f"User: {intent}")
            
            # LLM analyzes intent and generates plan
            plan = client.generate_request_plan(intent)
            print(f"Agent: {plan.get('explanation', 'Processing...')}")
            
            if "error" not in plan:
                # Execute the request
                result = await client.execute_request(plan)
                
                if result.get("status") < 400:
                    print(f"Result: Success! {json.dumps(result['data'], indent=2)}")
                else:
                    print(f"Result: Failed - {result.get('error')}")
            else:
                print(f"Result: {plan['error']}")
                print(f"Available actions: {plan['available_actions']}")
            
            print("-" * 50)
    
    finally:
        await client.close()


async def demo_token_comparison():
    """Compare token usage: discovery vs hardcoded."""
    print("\n=== Token Usage Comparison ===\n")
    
    # Simulate token counting (simplified)
    client = SocketAgentClient("http://localhost:8000")
    
    try:
        descriptor = await client.discover()
        
        # Discovery approach
        discovery_tokens = len(json.dumps(descriptor)) // 4  # Rough estimate
        print(f"Discovery approach:")
        print(f"  - Initial descriptor fetch: ~{discovery_tokens} tokens")
        print(f"  - Per request after that: ~50 tokens")
        print(f"  - Total for 10 requests: ~{discovery_tokens + 50*10} tokens")
        
        # Hardcoded approach (if we generated stubs)
        print(f"\nHardcoded stub approach:")
        print(f"  - No discovery needed: 0 tokens")
        print(f"  - Per request: ~30 tokens")
        print(f"  - Total for 10 requests: ~300 tokens")
        
        print(f"\nBreak-even point: ~{discovery_tokens // 20} requests")
        
    finally:
        await client.close()


if __name__ == "__main__":
    print("Make sure the Todo API is running on http://localhost:8000")
    print("Run with: cd examples/todo_fastapi && python main.py\n")
    
    # Run the demos
    asyncio.run(demo_llm_interaction())
    asyncio.run(demo_token_comparison())
