"""Test that the descriptor size stays within limits."""

import pytest
from fastapi import FastAPI

from socket_agent import SocketAgentMiddleware, socket
from socket_agent.spec_builder import build_descriptor


def test_minimal_descriptor_size():
    """Test that a minimal descriptor is under 3KB."""
    app = FastAPI()

    @app.post("/test")
    @socket.describe("Test endpoint")
    async def test_endpoint():
        return {"ok": True}

    descriptor = build_descriptor(
        app,
        name="Test API",
        description="Minimal test API",
        base_url="http://localhost",
    )

    size_kb = descriptor.size_kb()
    assert size_kb < 3, f"Minimal descriptor size {size_kb:.2f}KB exceeds 3KB"


def test_todo_example_size():
    """Test that the todo example descriptor is under 3KB."""
    # Import the todo app
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "todo_fastapi"))
    from main import app

    descriptor = build_descriptor(
        app,
        name="Todo API",
        description="Simple todo list management API",
        base_url="http://localhost:8000",
    )

    size_kb = descriptor.size_kb()
    assert size_kb < 3, f"Todo example descriptor size {size_kb:.2f}KB exceeds 3KB"
    print(f"Todo example descriptor size: {size_kb:.2f}KB")


def test_size_limit_enforcement():
    """Test that descriptors over 8KB raise an error."""
    app = FastAPI()

    # Create many endpoints with large schemas
    for i in range(50):

        @app.post(f"/endpoint{i}")
        @socket.describe(
            f"Endpoint {i} with a very long description that takes up space",
            request_schema={
                "type": "object",
                "properties": {
                    f"field{j}": {
                        "type": "string",
                        "description": f"This is field {j} with a long description",
                    }
                    for j in range(20)
                },
            },
        )
        async def endpoint():
            return {"ok": True}

    with pytest.raises(ValueError, match="exceeds 8KB limit"):
        build_descriptor(
            app,
            name="Large API",
            description="API with too many endpoints",
            base_url="http://localhost",
        )
