# socket-agent

Minimal API discovery for LLM agents. An alternative to complex API specifications that enables agents to understand and interact with your API through a simple, lightweight descriptor.

## Development

Dependencies for this repo are managed by [Determinate Nix](https://determinate.systems/).
To start working with them, install Determinate Nix and then run:

```sh
nix develop
```

Inside that environment, you should have python and (in the future) TypeScript and any other languages or dependencies required to work on socket-agent.

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

### Using the Client

Agents can discover and use your API with the client library:

```python
from socket_agent_client import SocketAgentClient

async with SocketAgentClient() as client:
    # Discover API
    await client.discover("http://localhost:8000")
    
    # Make calls
    result = await client.call("POST", "/todo", json={"text": "buy milk"})
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

- **[Multi-Service Benchmark](examples/benchmark)** - Complex real-world scenarios with grocery, recipe, and banking APIs demonstrating multi-service coordination

## Client Library

For agents and developers who want to interact with socket-agent APIs, we provide a client library:

```bash
pip install socket-agent-client
```

Features:
- Automatic API discovery
- Type-safe API calls  
- Pattern learning and stub generation for token optimization

See [socket-agent-client](socket-agent-client/) for more details.

## Architecture

socket-agent follows a clear separation of concerns:

- **Server (this package)**: Minimal, just serves descriptors
- **Client ([socket-agent-client](socket-agent-client/))**: Smart, handles discovery, learning, and optimization
- **Philosophy**: Servers stay dumb, clients do the work

## Project Structure

```
socket-agent/                 # Server library (this package)
├── socket_agent/            # Core server code
│   ├── decorators.py       # @socket.describe decorator
│   ├── middleware.py       # FastAPI middleware
│   └── schemas.py          # Descriptor format
├── examples/
│   └── benchmark/          # Multi-service demo
└── tests/

socket-agent-client/         # Client library (separate package)
├── socket_agent_client/    # Client code
│   ├── client.py          # API client
│   ├── discovery.py       # Descriptor fetching
│   └── learner.py         # Pattern learning
└── examples/
```

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
