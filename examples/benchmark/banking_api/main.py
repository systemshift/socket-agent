"""Banking API - Part of socket-agent benchmark suite."""

from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import uuid4
import httpx

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from socket_agent import SocketAgentMiddleware, socket

# Create FastAPI app
app = FastAPI(title="Banking API")

# In-memory account storage
accounts_db = {
    "user-001": {
        "id": "user-001",
        "name": "John Doe",
        "checking_balance": 2500.00,
        "savings_balance": 5000.00,
        "daily_spending_limit": 500.00,
        "spent_today": 0.00
    }
}

transactions_db: Dict[str, List[Dict]] = {
    "user-001": []
}

# Models
class Account(BaseModel):
    id: str
    name: str
    checking_balance: float
    savings_balance: float
    daily_spending_limit: float
    spent_today: float

class Transaction(BaseModel):
    id: str
    user_id: str
    type: str  # debit, credit, transfer
    amount: float
    description: str
    timestamp: str
    balance_after: float

class TransferRequest(BaseModel):
    from_account: str  # checking or savings
    to_account: str    # checking or savings
    amount: float

class PaymentRequest(BaseModel):
    order_id: str
    amount: float
    merchant: str

class SpendingLimitRequest(BaseModel):
    daily_limit: float

# Routes
@app.get("/accounts/{user_id}", response_model=Account)
@socket.describe(
    "Get account information including balances",
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "checking_balance": {"type": "number"},
            "savings_balance": {"type": "number"},
            "daily_spending_limit": {"type": "number"},
            "spent_today": {"type": "number"}
        }
    }
)
async def get_account(user_id: str):
    """Get account information for a user."""
    if user_id not in accounts_db:
        raise HTTPException(status_code=404, detail="Account not found")
    return Account(**accounts_db[user_id])


@app.get("/accounts/{user_id}/transactions", response_model=List[Transaction])
@socket.describe(
    "Get recent transactions",
    response_schema={
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "user_id": {"type": "string"},
                "type": {"type": "string"},
                "amount": {"type": "number"},
                "description": {"type": "string"},
                "timestamp": {"type": "string"},
                "balance_after": {"type": "number"}
            }
        }
    }
)
async def get_transactions(user_id: str, limit: int = 10):
    """Get recent transactions for an account."""
    if user_id not in accounts_db:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if user_id not in transactions_db:
        transactions_db[user_id] = []
    
    # Return most recent transactions
    return transactions_db[user_id][-limit:]


@app.post("/accounts/{user_id}/transfer")
@socket.describe(
    "Transfer money between checking and savings",
    request_schema={
        "type": "object",
        "properties": {
            "from_account": {"type": "string", "enum": ["checking", "savings"]},
            "to_account": {"type": "string", "enum": ["checking", "savings"]},
            "amount": {"type": "number"}
        },
        "required": ["from_account", "to_account", "amount"]
    },
    response_schema={
        "type": "object",
        "properties": {
            "transaction_id": {"type": "string"},
            "from_balance": {"type": "number"},
            "to_balance": {"type": "number"}
        }
    },
    examples=['curl -X POST /accounts/{user_id}/transfer -d \'{"from_account":"savings","to_account":"checking","amount":500}\'']
)
async def transfer_money(user_id: str, transfer: TransferRequest):
    """Transfer money between checking and savings accounts."""
    if user_id not in accounts_db:
        raise HTTPException(status_code=404, detail="Account not found")
    
    account = accounts_db[user_id]
    
    # Validate accounts
    if transfer.from_account == transfer.to_account:
        raise HTTPException(status_code=400, detail="Cannot transfer to same account")
    
    # Check balance
    from_balance_key = f"{transfer.from_account}_balance"
    to_balance_key = f"{transfer.to_account}_balance"
    
    if account[from_balance_key] < transfer.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    
    # Perform transfer
    account[from_balance_key] -= transfer.amount
    account[to_balance_key] += transfer.amount
    
    # Record transaction
    transaction_id = str(uuid4())
    transaction = {
        "id": transaction_id,
        "user_id": user_id,
        "type": "transfer",
        "amount": transfer.amount,
        "description": f"Transfer from {transfer.from_account} to {transfer.to_account}",
        "timestamp": datetime.now().isoformat(),
        "balance_after": account["checking_balance"]
    }
    
    if user_id not in transactions_db:
        transactions_db[user_id] = []
    transactions_db[user_id].append(transaction)
    
    return {
        "transaction_id": transaction_id,
        "from_balance": account[from_balance_key],
        "to_balance": account[to_balance_key]
    }


@app.post("/payments/order")
@socket.describe(
    "Pay for a grocery order",
    request_schema={
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "amount": {"type": "number"},
            "merchant": {"type": "string"}
        },
        "required": ["order_id", "amount", "merchant"]
    },
    response_schema={
        "type": "object",
        "properties": {
            "payment_id": {"type": "string"},
            "order_id": {"type": "string"},
            "amount": {"type": "number"},
            "status": {"type": "string"},
            "remaining_balance": {"type": "number"}
        }
    },
    examples=['curl -X POST /payments/order -d \'{"order_id":"abc123","amount":45.99,"merchant":"Grocery Store"}\'']
)
async def pay_for_order(payment: PaymentRequest, user_id: str = "user-001"):
    """Process payment for an order."""
    if user_id not in accounts_db:
        raise HTTPException(status_code=404, detail="Account not found")
    
    account = accounts_db[user_id]
    
    # Check daily spending limit
    if account["spent_today"] + payment.amount > account["daily_spending_limit"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Payment exceeds daily spending limit. Remaining: ${account['daily_spending_limit'] - account['spent_today']:.2f}"
        )
    
    # Check balance
    if account["checking_balance"] < payment.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds in checking account")
    
    # Process payment
    account["checking_balance"] -= payment.amount
    account["spent_today"] += payment.amount
    
    # Record transaction
    payment_id = str(uuid4())
    transaction = {
        "id": payment_id,
        "user_id": user_id,
        "type": "debit",
        "amount": payment.amount,
        "description": f"Payment to {payment.merchant} - Order {payment.order_id}",
        "timestamp": datetime.now().isoformat(),
        "balance_after": account["checking_balance"]
    }
    
    if user_id not in transactions_db:
        transactions_db[user_id] = []
    transactions_db[user_id].append(transaction)
    
    # Update order status in grocery API (if available)
    try:
        async with httpx.AsyncClient() as client:
            await client.put(
                f"http://localhost:8001/orders/{payment.order_id}/status",
                json={"status": "paid"}
            )
    except:
        pass  # Grocery API might not be running
    
    return {
        "payment_id": payment_id,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "status": "completed",
        "remaining_balance": account["checking_balance"]
    }


@app.put("/accounts/{user_id}/spending-limit")
@socket.describe(
    "Set daily spending limit",
    request_schema={
        "type": "object",
        "properties": {
            "daily_limit": {"type": "number"}
        },
        "required": ["daily_limit"]
    },
    response_schema={
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "daily_limit": {"type": "number"},
            "updated": {"type": "boolean"}
        }
    }
)
async def set_spending_limit(user_id: str, limit: SpendingLimitRequest):
    """Set or update daily spending limit."""
    if user_id not in accounts_db:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if limit.daily_limit < 0:
        raise HTTPException(status_code=400, detail="Limit must be positive")
    
    accounts_db[user_id]["daily_spending_limit"] = limit.daily_limit
    
    return {
        "user_id": user_id,
        "daily_limit": limit.daily_limit,
        "updated": True
    }


@app.get("/accounts/{user_id}/budget-check")
@socket.describe(
    "Check if amount is within budget",
    response_schema={
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
            "within_daily_limit": {"type": "boolean"},
            "within_balance": {"type": "boolean"},
            "available_today": {"type": "number"},
            "checking_balance": {"type": "number"}
        }
    }
)
async def check_budget(user_id: str, amount: float):
    """Check if a specific amount is within budget constraints."""
    if user_id not in accounts_db:
        raise HTTPException(status_code=404, detail="Account not found")
    
    account = accounts_db[user_id]
    available_today = account["daily_spending_limit"] - account["spent_today"]
    
    return {
        "amount": amount,
        "within_daily_limit": amount <= available_today,
        "within_balance": amount <= account["checking_balance"],
        "available_today": available_today,
        "checking_balance": account["checking_balance"]
    }


@app.post("/accounts/{user_id}/deposit")
@socket.describe(
    "Deposit money (simulating paycheck)",
    request_schema={
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
            "description": {"type": "string"}
        },
        "required": ["amount"]
    },
    response_schema={
        "type": "object",
        "properties": {
            "transaction_id": {"type": "string"},
            "new_balance": {"type": "number"}
        }
    }
)
async def deposit_money(user_id: str, deposit: Dict[str, Any]):
    """Deposit money into checking account."""
    if user_id not in accounts_db:
        raise HTTPException(status_code=404, detail="Account not found")
    
    amount = deposit["amount"]
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Deposit amount must be positive")
    
    account = accounts_db[user_id]
    account["checking_balance"] += amount
    
    # Record transaction
    transaction_id = str(uuid4())
    transaction = {
        "id": transaction_id,
        "user_id": user_id,
        "type": "credit",
        "amount": amount,
        "description": deposit.get("description", "Deposit"),
        "timestamp": datetime.now().isoformat(),
        "balance_after": account["checking_balance"]
    }
    
    if user_id not in transactions_db:
        transactions_db[user_id] = []
    transactions_db[user_id].append(transaction)
    
    # Reset daily spending on new deposit (simulating new day)
    account["spent_today"] = 0.00
    
    return {
        "transaction_id": transaction_id,
        "new_balance": account["checking_balance"]
    }


# Initialize socket-agent middleware
SocketAgentMiddleware(
    app,
    name="Banking API",
    description="Banking services with account management, transfers, and payment processing",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
