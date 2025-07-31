#!/usr/bin/env python3
"""Example demonstrating pattern learning and stub generation."""

import asyncio
import json
from socket_agent_client import SocketAgentClient, PatternLearner, APICall


async def main():
    """Demonstrate learning from API usage."""
    
    # Create client and learner
    client = SocketAgentClient()
    learner = PatternLearner(min_observations=3, min_confidence=0.7)
    
    # Discover API
    print("Discovering Recipe API...")
    descriptor = await client.discover("http://localhost:8002")
    print(f"Found: {descriptor.name}")
    
    # Simulate various user intents
    test_intents = [
        # Search intents
        ("find pasta recipes", "GET", "/recipes/search", {"q": "pasta"}),
        ("search for pasta dishes", "GET", "/recipes/search", {"q": "pasta"}),
        ("look for spaghetti recipes", "GET", "/recipes/search", {"q": "spaghetti"}),
        ("find chicken recipes", "GET", "/recipes/search", {"q": "chicken"}),
        ("search for salad recipes", "GET", "/recipes/search", {"q": "salad"}),
        
        # Get recipe details
        ("show me recipe details for recipe-001", "GET", "/recipes/recipe-001", None),
        ("get information about recipe-001", "GET", "/recipes/recipe-001", None),
        ("tell me about recipe recipe-001", "GET", "/recipes/recipe-001", None),
        
        # Shopping list generation
        ("create shopping list for recipe-001", "POST", "/recipes/recipe-001/shopping-list", {"servings": 4}),
        ("generate ingredients list for recipe-001", "POST", "/recipes/recipe-001/shopping-list", {"servings": 4}),
        ("make shopping list for recipe-001 for 6 people", "POST", "/recipes/recipe-001/shopping-list", {"servings": 6}),
        
        # List all recipes
        ("show all recipes", "GET", "/recipes", None),
        ("list available recipes", "GET", "/recipes", None),
        ("what recipes do you have", "GET", "/recipes", None),
    ]
    
    print("\n--- Learning from API usage ---")
    
    # Execute intents and learn
    for intent, method, path, params in test_intents:
        print(f"\nIntent: '{intent}'")
        
        # Create APICall object for learning
        api_call = APICall(
            method=method,
            path=path,
            params=params if method == "GET" else None,
            body=params if method == "POST" else None
        )
        
        # Make the actual call
        if method == "GET":
            result = await client.call(method, path, params=params)
        else:
            result = await client.call(method, path, json=params)
        
        print(f"  → {method} {path} - Status: {result.status_code}")
        
        # Record for learning
        learner.observe(intent, api_call, result)
    
    # Generate stub
    print("\n--- Generating Stub ---")
    stub = learner.generate_stub(descriptor.base_url + "/.well-known/socket-agent")
    
    print(f"Total observations: {stub.metadata['total_calls']}")
    print(f"Unique intents: {stub.metadata['unique_intents']}")
    print(f"Endpoints used: {stub.metadata['endpoints_used']}")
    
    print("\nLearned patterns:")
    for pattern in stub.learned_patterns:
        print(f"\n- Intent pattern: {pattern.intent_pattern}")
        print(f"  API: {pattern.api_pattern['method']} {pattern.api_pattern['path']}")
        print(f"  Confidence: {pattern.confidence:.2%} ({pattern.observations} observations)")
        if pattern.api_pattern.get('extract_params'):
            print(f"  Parameters: {pattern.api_pattern['extract_params']}")
    
    # Save stub
    stub_file = "recipe_api.stub.json"
    stub.save(stub_file)
    print(f"\n✓ Stub saved to {stub_file}")
    
    # Show stub size comparison
    print("\n--- Size Comparison ---")
    descriptor_size = len(json.dumps(descriptor.model_dump()))
    stub_size = len(json.dumps(stub.model_dump()))
    print(f"Original descriptor: {descriptor_size} bytes")
    print(f"Generated stub: {stub_size} bytes")
    print(f"Size reduction: {(1 - stub_size/descriptor_size)*100:.1f}%")
    
    await client.close()


if __name__ == "__main__":
    print("=== Socket-Agent Client Learning Example ===")
    print("Make sure the Recipe API is running on http://localhost:8002")
    print()
    
    asyncio.run(main())
