"""Test that the manifest follows the expected schema."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from socket_agent import SocketAgentMiddleware, socket


def test_descriptor_schema():
    """Test that the descriptor has all required fields."""
    app = FastAPI()

    @app.post("/test")
    @socket.describe(
        "Test endpoint",
        request_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        response_schema={"type": "object", "properties": {"id": {"type": "string"}}},
        examples=['curl -X POST /test -d \'{"name":"test"}\''],
    )
    async def test_endpoint():
        return {"id": "123"}

    # Add middleware
    SocketAgentMiddleware(
        app,
        name="Test API",
        description="Test API description",
    )

    client = TestClient(app)
    response = client.get("/.well-known/socket-agent")
    assert response.status_code == 200

    descriptor = response.json()

    # Check required fields
    assert "name" in descriptor
    assert descriptor["name"] == "Test API"

    assert "description" in descriptor
    assert descriptor["description"] == "Test API description"

    assert "base_url" in descriptor
    assert descriptor["base_url"].startswith("http")

    assert "endpoints" in descriptor
    assert isinstance(descriptor["endpoints"], list)
    assert len(descriptor["endpoints"]) > 0

    # Check endpoint structure
    endpoint = descriptor["endpoints"][0]
    assert "path" in endpoint
    assert "method" in endpoint
    assert "summary" in endpoint

    assert "schemas" in descriptor
    assert isinstance(descriptor["schemas"], dict)

    assert "auth" in descriptor
    assert descriptor["auth"]["type"] == "none"

    assert "examples" in descriptor
    assert isinstance(descriptor["examples"], list)

    assert "specVersion" in descriptor


def test_endpoint_info_structure():
    """Test that endpoint info has the correct structure."""
    app = FastAPI()

    @app.get("/users/{user_id}")
    @socket.describe("Get user by ID")
    async def get_user(user_id: str):
        return {"id": user_id}

    @app.post("/users")
    @socket.describe("Create a new user")
    async def create_user():
        return {"id": "new"}

    SocketAgentMiddleware(app, name="User API", description="User management")

    client = TestClient(app)
    response = client.get("/.well-known/socket-agent")
    descriptor = response.json()

    endpoints = descriptor["endpoints"]
    assert len(endpoints) == 2

    # Check GET endpoint
    get_endpoint = next(e for e in endpoints if e["method"] == "GET")
    assert get_endpoint["path"] == "/users/{user_id}"
    assert get_endpoint["summary"] == "Get user by ID"

    # Check POST endpoint
    post_endpoint = next(e for e in endpoints if e["method"] == "POST")
    assert post_endpoint["path"] == "/users"
    assert post_endpoint["summary"] == "Create a new user"


def test_schema_inclusion():
    """Test that schemas are properly included in the descriptor."""
    app = FastAPI()

    @app.post("/items")
    @socket.describe(
        "Create an item",
        request_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "price": {"type": "number"},
            },
            "required": ["name", "price"],
        },
        response_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "price": {"type": "number"},
            },
        },
    )
    async def create_item():
        return {"id": "123", "name": "Test", "price": 9.99}

    SocketAgentMiddleware(app, name="Item API", description="Item management")

    client = TestClient(app)
    response = client.get("/.well-known/socket-agent")
    descriptor = response.json()

    assert "/items" in descriptor["schemas"]
    assert "request" in descriptor["schemas"]["/items"]
    assert "response" in descriptor["schemas"]["/items"]

    request_schema = descriptor["schemas"]["/items"]["request"]
    assert request_schema["type"] == "object"
    assert "name" in request_schema["properties"]
    assert "price" in request_schema["properties"]
    assert request_schema["required"] == ["name", "price"]


def test_examples_collection():
    """Test that examples are collected from all endpoints."""
    app = FastAPI()

    @app.post("/a")
    @socket.describe("Endpoint A", examples=["curl -X POST /a"])
    async def endpoint_a():
        return {"ok": True}

    @app.post("/b")
    @socket.describe("Endpoint B", examples=["curl -X POST /b", "curl -X POST /b -d '{}'"])
    async def endpoint_b():
        return {"ok": True}

    SocketAgentMiddleware(app, name="Test", description="Test")

    client = TestClient(app)
    response = client.get("/.well-known/socket-agent")
    descriptor = response.json()

    assert len(descriptor["examples"]) == 3
    assert "curl -X POST /a" in descriptor["examples"]
    assert "curl -X POST /b" in descriptor["examples"]
