#!/usr/bin/env python3
"""Quick test script to verify socket-agent functionality."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from socket_agent import socket, SocketAgentMiddleware

# Create a simple test app
app = FastAPI()

class ItemCreate(BaseModel):
    name: str
    price: float

@app.post("/items")
@socket.describe(
    "Create a new item",
    request_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "price": {"type": "number"}
        },
        "required": ["name", "price"]
    },
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "price": {"type": "number"}
        }
    },
    examples=['curl -X POST /items -d \'{"name":"Widget","price":9.99}\'']
)
async def create_item(item: ItemCreate):
    return {"id": "123", "name": item.name, "price": item.price}

@app.get("/items/{item_id}")
@socket.describe("Get item by ID")
async def get_item(item_id: str):
    return {"id": item_id, "name": "Widget", "price": 9.99}

# Initialize socket-agent
SocketAgentMiddleware(
    app,
    name="Test API",
    description="Simple test API for socket-agent"
)

# Test the descriptor endpoint
client = TestClient(app)

print("Testing socket-agent descriptor endpoint...")
response = client.get("/.well-known/socket-agent")

if response.status_code == 200:
    print("✓ Descriptor endpoint is working!")
    print("\nDescriptor content:")
    import json
    descriptor = response.json()
    print(json.dumps(descriptor, indent=2))
    
    # Calculate size
    size_kb = len(json.dumps(descriptor, separators=(',', ':')).encode('utf-8')) / 1024
    print(f"\nDescriptor size: {size_kb:.2f}KB")
else:
    print(f"✗ Failed to fetch descriptor: {response.status_code}")
    print(response.text)
