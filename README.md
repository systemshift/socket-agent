# socket-agent

Minimal API discovery for LLM agents. An alternative to complex API specifications that enables agents to understand and interact with your API through a simple, lightweight descriptor.

## Quick Start (60 seconds)

### Installation

```bash
pip install socket-agent
```

### Basic Usage

```python
from fastapi import FastAPI
from pydantic import BaseModel
from socket_agent import socket, SocketAgentMiddleware

app = FastAPI()

class TodoCreate(BaseModel):
    text: str

@app.post("/todo")
@socket.describe(
    "Create a new todo item",
    request_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"]
    },
    response_schema={
        "type": "object", 
        "properties": {"id": {"type": "string"}}
    }
)
async def create_todo(todo: TodoCreate):
    return {"id": "123", "text": todo.text}

# Initialize socket-agent
SocketAgentMiddleware(
    app,
    name="Todo API",
    description="Simple todo management"
)
```

### Test the Descriptor

Run your app and fetch the descriptor:

```bash
curl http://localhost:8000/.well-known/socket-agent
```

## What is socket-agent?

socket-agent provides a lightweight alternative to OpenAPI/Swagger for exposing APIs to LLM agents. Instead of maintaining complex specifications, you:

1. Add simple decorators to your endpoints
2. socket-agent automatically generates a minimal descriptor
3. LLM agents fetch the descriptor once and understand your entire API

## Key Features

- **Minimal by Design**: Descriptors are typically under 3KB (hard limit: 8KB)
- **Zero Configuration**: Just add decorators and middleware
- **Agent-Optimized**: Designed specifically for LLM consumption
- **FastAPI Native**: Built for modern Python web APIs

## Descriptor Format

The descriptor served at `/.well-known/socket-agent` contains:

```json
{
  "name": "Your API",
  "description": "API description",
  "base_url": "https://api.example.com",
  "endpoints": [
    {
      "path": "/todo",
      "method": "POST",
      "summary": "Create todo"
    }
  ],
  "schema": {
    "/todo": {
      "request": { "type": "object", "properties": {...} },
      "response": { "type": "object", "properties": {...} }
    }
  },
  "auth": { "type": "none" },
  "examples": ["curl -X POST /todo -d '{\"text\":\"buy milk\"}'"]
}
```

## Philosophy

Modern APIs are over-structured. While humans need detailed documentation, LLM agents can understand APIs from minimal descriptions. socket-agent embraces this by providing just enough structure for agents to interact with your services effectively.

## Examples

See the [examples/todo_fastapi](examples/todo_fastapi) directory for a complete working example.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black socket_agent tests
isort socket_agent tests
```

## License

MIT
