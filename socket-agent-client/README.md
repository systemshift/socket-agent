# Socket-Agent Client

A Python client library for interacting with socket-agent APIs. This library provides tools for discovering APIs, making calls, and learning patterns to generate optimized stubs.

## Installation

```bash
pip install socket-agent-client
```

## Features

- **API Discovery**: Automatically fetch and parse socket-agent descriptors
- **Type-Safe Client**: Full type hints and Pydantic models
- **Pattern Learning**: Learn from API usage to generate optimized stubs
- **Async Support**: Built on httpx for modern async Python
- **Minimal Dependencies**: Built on httpx and pydantic

## Quick Start

### Basic Usage

```python
import asyncio
from socket_agent_client import SocketAgentClient

async def main():
    # Create client
    async with SocketAgentClient() as client:
        # Discover API
        descriptor = await client.discover("http://localhost:8000")
        print(f"Found: {descriptor.name}")
        
        # Make API calls
        result = await client.call("GET", "/todos")
        if result.status_code == 200:
            print(f"Todos: {result.body}")

asyncio.run(main())
```

### With Pattern Learning

```python
from socket_agent_client import SocketAgentClient, PatternLearner

# Create learner
learner = PatternLearner(min_observations=5)

# Learn from usage
async with SocketAgentClient() as client:
    await client.discover("http://localhost:8000")
    
    # Make calls and observe patterns
    for task in ["create todo buy milk", "add task call mom"]:
        result = await client.call("POST", "/todo", json={"text": task})
        learner.observe(task, api_call, result)
    
    # Generate optimized stub
    stub = learner.generate_stub("http://localhost:8000/.well-known/socket-agent")
    stub.save("todo_api.stub.json")
```

## Stub Generation

The pattern learner analyzes your API usage to create optimized stubs:

```json
{
  "version": "1.0",
  "source": "http://localhost:8000/.well-known/socket-agent",
  "learned_patterns": [
    {
      "intent_pattern": ".*(create|add|new).*todo.*",
      "api_pattern": {
        "method": "POST",
        "path": "/todo",
        "extract_params": {
          "text": "text after action words"
        }
      },
      "confidence": 0.95,
      "observations": 47
    }
  ]
}
```

## Benefits

1. **Token Savings**: Stubs are typically 70-90% smaller than full descriptors
2. **Faster Responses**: Skip discovery and pattern matching
3. **Privacy**: All learning happens client-side
4. **Shareable**: Export stubs for other agents to use

## API Reference

### SocketAgentClient

Main client for interacting with APIs:

- `discover(base_url)`: Fetch API descriptor
- `call(method, path, **kwargs)`: Make API calls
- `find_endpoint(method, path)`: Get endpoint info from descriptor

### PatternLearner

Learn patterns from API usage:

- `observe(intent, call, result)`: Record an interaction
- `analyze_patterns()`: Find patterns in observations
- `generate_stub(source_url)`: Create optimized stub

### Models

- `Descriptor`: Parsed API descriptor
- `APICall`: Record of an API call
- `APIResult`: Result of an API call
- `LearnedPattern`: Pattern discovered from usage
- `Stub`: Optimized representation of patterns

## Examples

See the `examples/` directory for complete examples:

- `basic_usage.py`: Simple API discovery and calls
- `with_learning.py`: Pattern learning and stub generation

## Philosophy

This client library embraces the socket-agent philosophy:

- **Server stays dumb**: All intelligence lives in the client
- **Learn by doing**: Patterns emerge from actual usage
- **Privacy first**: No tracking or analytics
- **Model agnostic**: Works with any LLM or agent framework

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black socket_agent_client
isort socket_agent_client
```

## License

MIT
