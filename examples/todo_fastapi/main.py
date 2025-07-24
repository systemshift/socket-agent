"""Example Todo API using socket-agent."""

from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from socket_agent import SocketAgentMiddleware, socket

# Create FastAPI app
app = FastAPI(title="Todo API")

# In-memory storage
todos: Dict[str, Dict] = {}


# Models
class TodoCreate(BaseModel):
    text: str


class TodoResponse(BaseModel):
    id: str
    text: str
    completed: bool = False


# Routes
@app.post("/todo", response_model=TodoResponse)
@socket.describe(
    "Create a new todo item",
    request_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "text": {"type": "string"},
            "completed": {"type": "boolean"},
        },
    },
    examples=['curl -X POST /todo -d \'{"text":"buy milk"}\''],
)
async def create_todo(todo: TodoCreate):
    """Create a new todo item."""
    todo_id = str(uuid4())
    todo_data = {
        "id": todo_id,
        "text": todo.text,
        "completed": False,
    }
    todos[todo_id] = todo_data
    return TodoResponse(**todo_data)


@app.get("/todo/{todo_id}", response_model=TodoResponse)
@socket.describe(
    "Get a todo item by ID",
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "text": {"type": "string"},
            "completed": {"type": "boolean"},
        },
    },
)
async def get_todo(todo_id: str):
    """Get a todo item by ID."""
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    return TodoResponse(**todos[todo_id])


@app.get("/todos", response_model=List[TodoResponse])
@socket.describe(
    "List all todo items",
    response_schema={
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "text": {"type": "string"},
                "completed": {"type": "boolean"},
            },
        },
    },
)
async def list_todos():
    """List all todo items."""
    return [TodoResponse(**todo) for todo in todos.values()]


@app.put("/todo/{todo_id}/complete")
@socket.describe(
    "Mark a todo item as completed",
    response_schema={
        "type": "object",
        "properties": {"success": {"type": "boolean"}},
    },
)
async def complete_todo(todo_id: str):
    """Mark a todo item as completed."""
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    todos[todo_id]["completed"] = True
    return {"success": True}


@app.delete("/todo/{todo_id}")
@socket.describe(
    "Delete a todo item",
    response_schema={
        "type": "object",
        "properties": {"success": {"type": "boolean"}},
    },
)
async def delete_todo(todo_id: str):
    """Delete a todo item."""
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    del todos[todo_id]
    return {"success": True}


# Initialize socket-agent middleware
SocketAgentMiddleware(
    app,
    name="Todo API",
    description="Simple todo list management API",
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
