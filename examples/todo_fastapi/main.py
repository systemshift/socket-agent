"""Todo API example for socket-agent tests and docs."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI
from pydantic import BaseModel

from socket_agent import SocketAgentMiddleware, socket

app = FastAPI(title="Todo API")


class TodoCreate(BaseModel):
    text: str


@app.post("/todo")
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
        },
    },
    examples=['curl -X POST /todo -d \'{"text":"buy milk"}\''],
)
async def create_todo(todo: TodoCreate):
    return {"id": "1", "text": todo.text}


# Initialize socket-agent middleware
SocketAgentMiddleware(
    app,
    name="Todo API",
    description="Simple todo list management API",
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
