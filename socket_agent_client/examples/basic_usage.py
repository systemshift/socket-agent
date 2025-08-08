#!/usr/bin/env python3
"""Basic usage example of socket_agent_client."""

import asyncio
from socket_agent_client import SocketAgentClient


async def main():
    """Demonstrate basic client usage."""
    
    # Create client
    async with SocketAgentClient() as client:
        # Discover API
        print("Discovering API...")
        descriptor = await client.discover("http://localhost:8001")
        
        print(f"Found: {descriptor.name}")
        print(f"Description: {descriptor.description}")
        print(f"Endpoints: {len(descriptor.endpoints)}")
        
        # List endpoints
        print("\nAvailable endpoints:")
        for endpoint in descriptor.endpoints:
            print(f"  {endpoint.method} {endpoint.path} - {endpoint.summary}")
        
        # Make some API calls
        print("\n--- Making API calls ---")
        
        # 1. List products
        print("\n1. Listing products:")
        result = await client.call("GET", "/products")
        if result.status_code == 200:
            products = result.body
            print(f"   Found {len(products)} products")
            for product in products[:3]:  # Show first 3
                print(f"   - {product['name']}: ${product['price']}")
        
        # 2. Create a cart
        print("\n2. Creating shopping cart:")
        result = await client.call("POST", "/cart")
        if result.status_code == 200:
            cart_id = result.body["id"]
            print(f"   Cart created: {cart_id}")
            
            # 3. Add item to cart
            print("\n3. Adding milk to cart:")
            result = await client.call(
                "POST",
                f"/cart/{cart_id}/items",
                json={"product_id": "milk-001", "quantity": 2}
            )
            if result.status_code == 200:
                print(f"   Total: ${result.body['total']}")
        
        # Show how to find endpoint info
        print("\n--- Endpoint Information ---")
        endpoint_info = client.find_endpoint("POST", "/cart/{cart_id}/items")
        if endpoint_info:
            print(f"Endpoint: {endpoint_info['summary']}")
            if endpoint_info.get('request_schema'):
                print(f"Request schema: {endpoint_info['request_schema']}")


if __name__ == "__main__":
    print("=== Socket-Agent Client Basic Usage ===")
    print("Make sure the Grocery API is running on http://localhost:8001")
    print()
    
    asyncio.run(main())
