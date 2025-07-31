#!/usr/bin/env python3
"""
Socket-Agent Benchmark Suite
Tests complex multi-service scenarios to demonstrate agentic behavior.
"""

import asyncio
import json
import time
from typing import Dict, List, Any
import httpx
from datetime import datetime

# Service URLs
GROCERY_URL = "http://localhost:8001"
RECIPE_URL = "http://localhost:8002"
BANKING_URL = "http://localhost:8003"


class BenchmarkAgent:
    """A test agent that can interact with multiple services."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.descriptors = {}
        self.metrics = {
            "api_calls": 0,
            "tokens_used": 0,
            "errors": 0,
            "start_time": None,
            "scenarios": {}
        }
    
    async def discover_services(self):
        """Discover all three services via socket-agent."""
        services = [
            ("grocery", GROCERY_URL),
            ("recipe", RECIPE_URL),
            ("banking", BANKING_URL)
        ]
        
        for name, url in services:
            try:
                response = await self.client.get(f"{url}/.well-known/socket-agent")
                self.descriptors[name] = response.json()
                print(f"✓ Discovered {name} service: {self.descriptors[name]['name']}")
                # Simulate token usage for descriptor
                self.metrics["tokens_used"] += len(json.dumps(self.descriptors[name])) // 4
            except Exception as e:
                print(f"✗ Failed to discover {name} service: {e}")
                self.metrics["errors"] += 1
    
    async def api_call(self, service: str, method: str, path: str, **kwargs):
        """Make an API call and track metrics."""
        self.metrics["api_calls"] += 1
        
        # Simulate token usage for request
        self.metrics["tokens_used"] += 50
        
        url = {
            "grocery": GROCERY_URL,
            "recipe": RECIPE_URL,
            "banking": BANKING_URL
        }[service]
        
        try:
            if method == "GET":
                response = await self.client.get(f"{url}{path}", **kwargs)
            elif method == "POST":
                response = await self.client.post(f"{url}{path}", **kwargs)
            elif method == "PUT":
                response = await self.client.put(f"{url}{path}", **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.metrics["errors"] += 1
            print(f"  ✗ API call failed: {e}")
            raise
    
    async def scenario_dinner_party(self):
        """Scenario 1: Plan a dinner party for 6 people."""
        print("\n=== Scenario 1: Planning Dinner Party for 6 ===")
        scenario_start = time.time()
        
        try:
            # Step 1: Find a suitable recipe
            print("1. Searching for pasta recipes...")
            recipes = await self.api_call("recipe", "GET", "/recipes/search", params={"q": "pasta"})
            recipe = recipes[0]  # Pick Spaghetti Carbonara
            print(f"   Found: {recipe['name']}")
            
            # Step 2: Get shopping list for 6 people
            print("2. Generating shopping list for 6 people...")
            shopping_list = await self.api_call(
                "recipe", "POST", f"/recipes/{recipe['id']}/shopping-list",
                json={"servings": 6}
            )
            print(f"   Need to buy: {len(shopping_list['ingredients'])} items")
            
            # Step 3: Check budget
            print("3. Checking bank account...")
            account = await self.api_call("banking", "GET", "/accounts/user-001")
            print(f"   Available balance: ${account['checking_balance']:.2f}")
            
            # Step 4: Create grocery cart
            print("4. Creating shopping cart...")
            cart = await self.api_call("grocery", "POST", "/cart")
            cart_id = cart["id"]
            
            # Step 5: Add ingredients to cart
            print("5. Adding ingredients to cart...")
            total_cost = 0
            for ingredient in shopping_list['ingredients']:
                # Search for product
                products = await self.api_call(
                    "grocery", "GET", "/products/search",
                    params={"q": ingredient['item']}
                )
                
                if products:
                    product = products[0]
                    # Add to cart
                    cart = await self.api_call(
                        "grocery", "POST", f"/cart/{cart_id}/items",
                        json={
                            "product_id": product['id'],
                            "quantity": ingredient['amount']
                        }
                    )
                    total_cost = cart['total']
                    print(f"   Added {ingredient['item']}: ${product['price'] * ingredient['amount']:.2f}")
            
            print(f"   Total cart: ${total_cost:.2f}")
            
            # Step 6: Check if we can afford it
            budget_check = await self.api_call(
                "banking", "GET", f"/accounts/user-001/budget-check",
                params={"amount": total_cost}
            )
            
            if budget_check['within_balance'] and budget_check['within_daily_limit']:
                print("6. Budget check passed! Proceeding to checkout...")
                
                # Step 7: Checkout
                order = await self.api_call("grocery", "POST", f"/checkout/{cart_id}")
                print(f"   Order created: {order['id']}")
                
                # Step 8: Pay for order
                payment = await self.api_call(
                    "banking", "POST", "/payments/order",
                    json={
                        "order_id": order['id'],
                        "amount": order['total'],
                        "merchant": "Grocery Store"
                    }
                )
                print(f"   Payment successful! Remaining balance: ${payment['remaining_balance']:.2f}")
            else:
                print("6. Budget check failed! Cannot afford this meal.")
            
            self.metrics["scenarios"]["dinner_party"] = {
                "success": True,
                "duration": time.time() - scenario_start,
                "api_calls": self.metrics["api_calls"]
            }
            
        except Exception as e:
            print(f"Scenario failed: {e}")
            self.metrics["scenarios"]["dinner_party"] = {
                "success": False,
                "duration": time.time() - scenario_start,
                "error": str(e)
            }
    
    async def scenario_healthy_budget(self):
        """Scenario 2: Find healthy meals within budget."""
        print("\n=== Scenario 2: Healthy Eating on Budget ===")
        scenario_start = time.time()
        
        try:
            # Step 1: Check budget constraints
            print("1. Checking daily spending limit...")
            account = await self.api_call("banking", "GET", "/accounts/user-001")
            available = account['daily_spending_limit'] - account['spent_today']
            print(f"   Available to spend today: ${available:.2f}")
            
            # Step 2: Find healthy recipes
            print("2. Finding healthy recipes under 400 calories...")
            healthy_recipes = await self.api_call(
                "recipe", "GET", "/recipes/nutrition/healthy",
                params={"max_calories": 400}
            )
            print(f"   Found {len(healthy_recipes)} healthy options")
            
            # Step 3: Calculate costs for each recipe
            print("3. Calculating costs for healthy options...")
            affordable_meals = []
            
            for recipe in healthy_recipes[:2]:  # Check first 2
                # Get full recipe details
                full_recipe = await self.api_call("recipe", "GET", f"/recipes/{recipe['id']}")
                
                # Calculate ingredient costs
                total_cost = 0
                for ingredient in full_recipe['ingredients']:
                    products = await self.api_call(
                        "grocery", "GET", "/products/search",
                        params={"q": ingredient['item']}
                    )
                    if products:
                        total_cost += products[0]['price'] * ingredient['amount']
                
                print(f"   {recipe['name']}: ${total_cost:.2f} ({recipe['calories']} cal)")
                
                if total_cost <= available:
                    affordable_meals.append({
                        "recipe": recipe,
                        "cost": total_cost
                    })
            
            if affordable_meals:
                print(f"4. Found {len(affordable_meals)} affordable healthy meals!")
                # Save favorite
                best_meal = affordable_meals[0]
                await self.api_call(
                    "recipe", "POST", 
                    f"/favorites/user-001/{best_meal['recipe']['id']}"
                )
                print(f"   Saved {best_meal['recipe']['name']} to favorites")
            else:
                print("4. No meals fit within budget constraints")
            
            self.metrics["scenarios"]["healthy_budget"] = {
                "success": True,
                "duration": time.time() - scenario_start,
                "affordable_meals": len(affordable_meals)
            }
            
        except Exception as e:
            print(f"Scenario failed: {e}")
            self.metrics["scenarios"]["healthy_budget"] = {
                "success": False,
                "duration": time.time() - scenario_start,
                "error": str(e)
            }
    
    async def scenario_payday_shopping(self):
        """Scenario 3: Stock up pantry after getting paid."""
        print("\n=== Scenario 3: Payday Pantry Stocking ===")
        scenario_start = time.time()
        
        try:
            # Step 1: Simulate payday
            print("1. Depositing paycheck...")
            deposit = await self.api_call(
                "banking", "POST", "/accounts/user-001/deposit",
                json={"amount": 2000.00, "description": "Monthly salary"}
            )
            print(f"   New balance: ${deposit['new_balance']:.2f}")
            
            # Step 2: Get favorite recipes
            print("2. Getting favorite recipes...")
            favorites = await self.api_call("recipe", "GET", "/favorites/user-001")
            
            # Step 3: Generate combined shopping list
            print("3. Creating shopping list for multiple recipes...")
            recipe_requests = [
                {"recipe_id": "recipe-001", "servings": 8},  # Extra servings
                {"recipe_id": "recipe-002", "servings": 6}
            ]
            
            combined_list = await self.api_call(
                "recipe", "POST", "/shopping-list/multiple",
                json={"recipes": recipe_requests}
            )
            print(f"   Combined {len(combined_list['recipes'])} recipes")
            print(f"   Total ingredients: {len(combined_list['combined_ingredients'])}")
            
            # Step 4: Create cart and add pantry staples
            print("4. Shopping for pantry staples...")
            cart = await self.api_call("grocery", "POST", "/cart")
            cart_id = cart["id"]
            
            # Add staples
            staples = ["rice", "pasta", "milk", "eggs", "bread"]
            for item in staples:
                products = await self.api_call(
                    "grocery", "GET", "/products/search",
                    params={"q": item}
                )
                if products:
                    cart = await self.api_call(
                        "grocery", "POST", f"/cart/{cart_id}/items",
                        json={"product_id": products[0]['id'], "quantity": 2}
                    )
            
            print(f"   Cart total: ${cart['total']:.2f}")
            
            # Step 5: Checkout and pay
            print("5. Checking out...")
            order = await self.api_call("grocery", "POST", f"/checkout/{cart_id}")
            
            payment = await self.api_call(
                "banking", "POST", "/payments/order",
                json={
                    "order_id": order['id'],
                    "amount": order['total'],
                    "merchant": "Grocery Store"
                }
            )
            print(f"   Paid ${order['total']:.2f}")
            print(f"   Remaining balance: ${payment['remaining_balance']:.2f}")
            
            # Step 6: Update spending limit for the month
            print("6. Updating monthly budget...")
            await self.api_call(
                "banking", "PUT", "/accounts/user-001/spending-limit",
                json={"daily_limit": 100.00}  # Increase limit after payday
            )
            print("   Daily spending limit updated to $100")
            
            self.metrics["scenarios"]["payday_shopping"] = {
                "success": True,
                "duration": time.time() - scenario_start,
                "amount_spent": order['total']
            }
            
        except Exception as e:
            print(f"Scenario failed: {e}")
            self.metrics["scenarios"]["payday_shopping"] = {
                "success": False,
                "duration": time.time() - scenario_start,
                "error": str(e)
            }
    
    async def run_benchmark(self):
        """Run all benchmark scenarios."""
        print("=== Socket-Agent Multi-Service Benchmark ===")
        print(f"Started at: {datetime.now().isoformat()}")
        self.metrics["start_time"] = time.time()
        
        # Discover services
        await self.discover_services()
        
        # Run scenarios
        await self.scenario_dinner_party()
        await self.scenario_healthy_budget()
        await self.scenario_payday_shopping()
        
        # Print summary
        duration = time.time() - self.metrics["start_time"]
        print("\n=== Benchmark Summary ===")
        print(f"Total duration: {duration:.2f} seconds")
        print(f"API calls made: {self.metrics['api_calls']}")
        print(f"Tokens used (estimated): {self.metrics['tokens_used']}")
        print(f"Errors encountered: {self.metrics['errors']}")
        print(f"Token efficiency: {self.metrics['tokens_used'] / max(1, self.metrics['api_calls']):.1f} tokens/call")
        
        print("\nScenario Results:")
        for name, result in self.metrics["scenarios"].items():
            status = "✓" if result.get("success") else "✗"
            print(f"  {status} {name}: {result.get('duration', 0):.2f}s")
        
        await self.client.aclose()
        return self.metrics


async def main():
    """Run the benchmark suite."""
    agent = BenchmarkAgent()
    
    print("Make sure all three services are running:")
    print("  Terminal 1: cd examples/benchmark/grocery_api && python main.py")
    print("  Terminal 2: cd examples/benchmark/recipe_api && python main.py")
    print("  Terminal 3: cd examples/benchmark/banking_api && python main.py")
    print("\nPress Enter when ready...")
    input()
    
    try:
        metrics = await agent.run_benchmark()
        
        # Save metrics to file
        with open("benchmark_results.json", "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"\nResults saved to benchmark_results.json")
        
    except KeyboardInterrupt:
        print("\nBenchmark interrupted")
    except Exception as e:
        print(f"\nBenchmark failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
