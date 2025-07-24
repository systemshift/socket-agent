# Todo API Example

This is a simple example demonstrating how to use socket-agent with FastAPI.

## Running the Example

1. Install dependencies:
```bash
pip install fastapi uvicorn socket-agent
```

2. Run the server:
```bash
python main.py
```

3. The API will be available at http://localhost:8000

## Testing the Socket-Agent Descriptor

Once the server is running, you can fetch the socket-agent descriptor:

```bash
curl http://localhost:8000/.well-known/socket-agent
```

This will return a JSON descriptor that LLM agents can use to understand and interact with the API.

## API Endpoints

- `POST /todo` - Create a new todo
- `GET /todo/{id}` - Get a specific todo
- `GET /todos` - List all todos
- `PUT /todo/{id}/complete` - Mark a todo as completed
- `DELETE /todo/{id}` - Delete a todo

## Example Usage

Create a todo:
```bash
curl -X POST http://localhost:8000/todo \
  -H "Content-Type: application/json" \
  -d '{"text": "Buy groceries"}'
```

List all todos:
```bash
curl http://localhost:8000/todos
