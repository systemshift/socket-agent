# Socket Agent Client

A smart, zero-token client library for Socket Agent APIs that can short-circuit LLMs with learned stubs, offering massive token savings while maintaining flexibility.

## Features

### 🚀 Zero-Token Routing
- **Smart routing** that bypasses LLMs when confident
- **Natural language** API calls: `client("create user alice")`
- **Confidence-based decisions** with configurable thresholds
- **Pattern learning** from usage for continuous improvement

### 💾 Multi-Level Caching
- **Deterministic cache** for exact parameter matches
- **Semantic cache** (optional) for similar queries
- **Configurable TTLs** per endpoint
- **Automatic cache invalidation**

### 📊 Built-in Telemetry
- **Token savings tracking** - measure your ROI
- **Latency metrics** (p50, p95)
- **Hit rates** for cache and short-circuiting
- **Per-endpoint statistics**

### 🔌 Framework Adapters
- **MCP (Model Context Protocol)** integration
- **OpenAI function calling** support
- **LangChain tools** compatibility

### 🧠 Optional ML Enhancement
- Support for **tiny models** (ONNX, TFLite, PyTorch)
- **Confidence boosting** with neural reranking
- **Slot filling** with sequence models

## Installation

```bash
pip install socket-agent-client
```

For optional features:
```bash
# For semantic caching
pip install socket-agent-client[semantic]

# For ML model support
pip install socket-agent-client[ml]

# For all features
pip install socket-agent-client[all]
```

## Quick Start

### Basic Usage

```python
from socket_agent_client import Client

# Initialize client
client = Client("https://api.example.com")
client.start()

# Natural language API calls
result = client("create a new todo: buy milk")
print(result.rendered_text)  # Human-readable response

# Check confidence for a query
endpoint, args, confidence = client.route("list all users")
print(f"Confidence: {confidence:.2%}")

# Direct endpoint call when you know what you want
result = client("create_user", name="alice", email="alice@example.com")
```

### Policy Configuration

Control routing behavior with policies:

```python
from socket_agent_client import create_client

# Aggressive - maximize direct calls (fewer tokens)
client = create_client("https://api.example.com", preset="aggressive")

# Conservative - prioritize accuracy (more LLM calls)
client = create_client("https://api.example.com", preset="conservative")

# Custom policy
client = create_client(
    "https://api.example.com",
    short_circuit_threshold=0.90,  # 90% confidence for direct calls
    cache_ttl_default=300,          # 5 minute cache
    enable_semantic_cache=True,     # Enable similarity matching
)
```

### Telemetry & Metrics

Track your token savings and performance:

```python
# After some usage...
summary = client.telemetry.summary()

print(f"Token Savings: {summary.tokens_saved:,}")
print(f"Short-circuit rate: {summary.short_circuit_rate:.1%}")
print(f"Cache hit rate: {summary.cache_hit_rate:.1%}")
print(f"Avg latency: {summary.avg_latency_ms:.1f}ms")

# Export detailed telemetry
client.telemetry.export("telemetry.json")
```

### LLM Fallback

Handle complex queries that need LLM processing:

```python
def llm_handler(text, descriptor):
    # Your LLM logic here
    response = call_your_llm(text, context=descriptor)
    return response

client.set_llm_handler(llm_handler)

# Low confidence queries automatically fallback to LLM
result = client("do something complex and unusual")
```

## Framework Integration

### MCP (Model Context Protocol)

```python
from socket_agent_client.adapters import create_mcp_tool

tool = create_mcp_tool("https://api.example.com")

# Use in your MCP server
result = tool("create user alice", context={"auth": "token123"})
```

### OpenAI Function Calling

```python
from socket_agent_client.adapters import OpenAIFunctionHandler

handler = OpenAIFunctionHandler("https://api.example.com")

# Get function definition for OpenAI
function_def = handler.get_function_definition()

# Handle function calls
result = handler.handle_function_call({"query": "list all products"})
```

### LangChain

```python
from socket_agent_client.adapters import create_langchain_tool

tool = create_langchain_tool("https://api.example.com")

# Use in LangChain agents
result = tool.run("create a new order for customer 123")
```

## Advanced Features

### Tiny Model Integration

Boost routing confidence with a small ML model:

```python
client = Client(
    "https://api.example.com",
    tiny_model="models/intent_classifier.onnx"
)
```

### Batch Operations

```python
from socket_agent_client import BatchExecutor

batch = BatchExecutor(client.executor)
results = await batch.execute_batch([
    {"method": "POST", "path": "/users", "json": {"name": "alice"}},
    {"method": "GET", "path": "/users"},
    {"method": "DELETE", "path": "/users/123"},
])
```

### Custom Templates

Define how responses are rendered:

```python
client.renderer.add_template(
    "create_user",
    "New user {name} created with ID {id}"
)
```

## Architecture

```
User Input (NL text)
    ↓
Router (rules + optional model)
    ↓
Confidence Score
    ↓
┌─────────────────┐
│  High (≥88%)    │ → Direct API Call → Cache → Response
│  Medium (70-88%)│ → Confirmation → API Call → Response  
│  Low (<70%)     │ → LLM Fallback → Response
└─────────────────┘
```

## Performance

Based on real-world usage:

- **Token savings**: 70-90% reduction in LLM token usage
- **Latency**: 10-50ms for cached/direct calls vs 1-3s for LLM
- **Accuracy**: 95%+ routing accuracy with proper thresholds
- **Cache hit rate**: 40-60% with semantic caching enabled

## Configuration

### Environment Variables

```bash
SOCKET_AGENT_SHORT_CIRCUIT_THRESHOLD=0.88
SOCKET_AGENT_CACHE_TTL=300
SOCKET_AGENT_SEMANTIC_CACHE=true
SOCKET_AGENT_TELEMETRY=true
```

### Policy Presets

- **aggressive**: Maximize token savings (threshold: 0.75)
- **balanced**: Default balanced approach (threshold: 0.88)
- **conservative**: Prioritize accuracy (threshold: 0.95)
- **development**: Full telemetry and learning (threshold: 0.80)
- **production**: Optimized for production (threshold: 0.90)

## API Reference

### Client

```python
class Client:
    def __init__(service_url: str, **options)
    def start() -> None
    def route(text: str) -> Tuple[str, Dict, float]
    def __call__(text_or_endpoint: str, **kwargs) -> APIResult
    def set_llm_handler(handler: Callable) -> None
    def export_stubs(filepath: str) -> None
```

### Types

```python
@dataclass
class RouteResult:
    endpoint: str
    args: Dict[str, Any]
    confidence: float
    decision: DecisionType  # "direct", "confirm", or "fallback"

class APIResult:
    success: bool
    result: Any
    rendered_text: Optional[str]
    tokens_used: int
    cache_hit: bool
    duration_ms: float
```

## Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md).

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- [Socket Agent Server](https://github.com/systemshift/socket-agent)
- [Documentation](https://docs.socketagent.ai)
- [Examples](https://github.com/systemshift/socket-agent/tree/main/examples)
