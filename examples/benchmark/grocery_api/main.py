"""Grocery Store API - Part of socket-agent benchmark suite."""

from typing import Dict, List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from socket_agent import SocketAgentMiddleware, socket

# Create FastAPI app
app = FastAPI(title="Grocery Store API")

# In-memory data storage
products_db = {
    "milk-001": {
        "id": "milk-001",
        "name": "Whole Milk",
        "category": "dairy",
        "price": 3.99,
        "unit": "gallon",
        "stock": 50
    },
    "bread-001": {
        "id": "bread-001",
        "name": "Whole Wheat Bread",
        "category": "bakery",
        "price": 2.49,
        "unit": "loaf",
        "stock": 30
    },
    "eggs-001": {
        "id": "eggs-001",
        "name": "Large Eggs",
        "category": "dairy",
        "price": 4.99,
        "unit": "dozen",
        "stock": 100
    },
    "chicken-001": {
        "id": "chicken-001",
        "name": "Chicken Breast",
        "category": "meat",
        "price": 8.99,
        "unit": "lb",
        "stock": 25
    },
    "rice-001": {
        "id": "rice-001",
        "name": "Jasmine Rice",
        "category": "grains",
        "price": 12.99,
        "unit": "5lb bag",
        "stock": 40
    },
    "tomato-001": {
        "id": "tomato-001",
        "name": "Roma Tomatoes",
        "category": "produce",
        "price": 1.99,
        "unit": "lb",
        "stock": 60
    },
    "pasta-001": {
        "id": "pasta-001",
        "name": "Spaghetti",
        "category": "pasta",
        "price": 1.79,
        "unit": "box",
        "stock": 80
    },
    "cheese-001": {
        "id": "cheese-001",
        "name": "Cheddar Cheese",
        "category": "dairy",
        "price": 5.99,
        "unit": "lb",
        "stock": 35
    }
}

carts: Dict[str, Dict] = {}
orders: Dict[str, Dict] = {}

# Models
class Product(BaseModel):
    id: str
    name: str
    category: str
    price: float
    unit: str
    stock: int

class CartItem(BaseModel):
    product_id: str
    quantity: float

class Cart(BaseModel):
    id: str
    items: List[Dict]
    total: float

class Order(BaseModel):
    id: str
    cart_id: str
    items: List[Dict]
    total: float
    status: str
    created_at: str

# Routes
@app.get("/products", response_model=List[Product])
@socket.describe(
    "List all available products",
    response_schema={
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "category": {"type": "string"},
                "price": {"type": "number"},
                "unit": {"type": "string"},
                "stock": {"type": "integer"}
            }
        }
    }
)
async def list_products(category: Optional[str] = None):
    """List all products, optionally filtered by category."""
    products = list(products_db.values())
    if category:
        products = [p for p in products if p["category"] == category]
    return products


@app.get("/products/search")
@socket.describe(
    "Search products by name",
    response_schema={
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "category": {"type": "string"},
                "price": {"type": "number"},
                "unit": {"type": "string"},
                "stock": {"type": "integer"}
            }
        }
    }
)
async def search_products(q: str):
    """Search products by name (case-insensitive)."""
    results = []
    query = q.lower()
    for product in products_db.values():
        if query in product["name"].lower():
            results.append(product)
    return results


@app.get("/products/{product_id}", response_model=Product)
@socket.describe(
    "Get details of a specific product",
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "category": {"type": "string"},
            "price": {"type": "number"},
            "unit": {"type": "string"},
            "stock": {"type": "integer"}
        }
    }
)
async def get_product(product_id: str):
    """Get details of a specific product."""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(**products_db[product_id])


@app.post("/cart", response_model=Cart)
@socket.describe(
    "Create a new shopping cart",
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "items": {"type": "array"},
            "total": {"type": "number"}
        }
    }
)
async def create_cart():
    """Create a new shopping cart."""
    cart_id = str(uuid4())
    carts[cart_id] = {
        "id": cart_id,
        "items": [],
        "total": 0.0
    }
    return Cart(**carts[cart_id])


@app.post("/cart/{cart_id}/items")
@socket.describe(
    "Add item to cart",
    request_schema={
        "type": "object",
        "properties": {
            "product_id": {"type": "string"},
            "quantity": {"type": "number"}
        },
        "required": ["product_id", "quantity"]
    },
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "items": {"type": "array"},
            "total": {"type": "number"}
        }
    },
    examples=['curl -X POST /cart/{cart_id}/items -d \'{"product_id":"milk-001","quantity":2}\'']
)
async def add_to_cart(cart_id: str, item: CartItem):
    """Add an item to the shopping cart."""
    if cart_id not in carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    if item.product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product = products_db[item.product_id]
    
    # Check stock
    if product["stock"] < item.quantity:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient stock. Only {product['stock']} available"
        )
    
    # Add to cart
    cart = carts[cart_id]
    cart_item = {
        "product_id": item.product_id,
        "product_name": product["name"],
        "quantity": item.quantity,
        "unit_price": product["price"],
        "subtotal": product["price"] * item.quantity
    }
    
    # Check if item already in cart
    for existing_item in cart["items"]:
        if existing_item["product_id"] == item.product_id:
            existing_item["quantity"] += item.quantity
            existing_item["subtotal"] = existing_item["unit_price"] * existing_item["quantity"]
            break
    else:
        cart["items"].append(cart_item)
    
    # Update total
    cart["total"] = sum(item["subtotal"] for item in cart["items"])
    
    return Cart(**cart)


@app.get("/cart/{cart_id}", response_model=Cart)
@socket.describe(
    "Get cart contents",
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "items": {"type": "array"},
            "total": {"type": "number"}
        }
    }
)
async def get_cart(cart_id: str):
    """Get the contents of a shopping cart."""
    if cart_id not in carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    return Cart(**carts[cart_id])


@app.post("/checkout/{cart_id}", response_model=Order)
@socket.describe(
    "Checkout and create order from cart",
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "cart_id": {"type": "string"},
            "items": {"type": "array"},
            "total": {"type": "number"},
            "status": {"type": "string"},
            "created_at": {"type": "string"}
        }
    }
)
async def checkout(cart_id: str):
    """Checkout and create an order from the cart."""
    if cart_id not in carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    cart = carts[cart_id]
    if not cart["items"]:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Create order
    order_id = str(uuid4())
    order = {
        "id": order_id,
        "cart_id": cart_id,
        "items": cart["items"].copy(),
        "total": cart["total"],
        "status": "pending_payment",
        "created_at": datetime.now().isoformat()
    }
    
    # Update stock
    for item in cart["items"]:
        product = products_db[item["product_id"]]
        product["stock"] -= item["quantity"]
    
    orders[order_id] = order
    
    # Clear cart
    cart["items"] = []
    cart["total"] = 0.0
    
    return Order(**order)


@app.get("/orders/{order_id}", response_model=Order)
@socket.describe(
    "Get order details",
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "cart_id": {"type": "string"},
            "items": {"type": "array"},
            "total": {"type": "number"},
            "status": {"type": "string"},
            "created_at": {"type": "string"}
        }
    }
)
async def get_order(order_id: str):
    """Get details of a specific order."""
    if order_id not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    return Order(**orders[order_id])


@app.put("/orders/{order_id}/status")
@socket.describe(
    "Update order status (used by banking API after payment)",
    request_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string"}
        },
        "required": ["status"]
    },
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "status": {"type": "string"}
        }
    }
)
async def update_order_status(order_id: str, status_update: Dict[str, str]):
    """Update the status of an order."""
    if order_id not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    
    orders[order_id]["status"] = status_update["status"]
    return {"id": order_id, "status": status_update["status"]}


# Initialize socket-agent middleware
SocketAgentMiddleware(
    app,
    name="Grocery Store API",
    description="Online grocery shopping with cart and checkout functionality",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
