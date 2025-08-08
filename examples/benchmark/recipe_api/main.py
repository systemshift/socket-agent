"""Recipe Service API - Part of socket-agent benchmark suite."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from socket_agent import SocketAgentMiddleware, socket

# Create FastAPI app
app = FastAPI(title="Recipe Service API")

# In-memory recipe database
recipes_db = {
    "recipe-001": {
        "id": "recipe-001",
        "name": "Spaghetti Carbonara",
        "cuisine": "Italian",
        "servings": 4,
        "prep_time": 15,
        "cook_time": 20,
        "difficulty": "medium",
        "ingredients": [
            {"item": "Spaghetti Pasta", "amount": 1, "unit": "lb"},
            {"item": "Eggs", "amount": 4, "unit": "large"},
            {"item": "Parmesan Cheese", "amount": 1, "unit": "cup"},
            {"item": "Bacon", "amount": 8, "unit": "slices"}
        ],
        "instructions": [
            "Cook spaghetti according to package directions",
            "Cook bacon until crispy, chop into pieces",
            "Beat eggs with parmesan cheese",
            "Toss hot pasta with egg mixture and bacon"
        ],
        "nutrition": {
            "calories": 450,
            "protein": 20,
            "carbs": 45,
            "fat": 22
        }
    },
    "recipe-002": {
        "id": "recipe-002",
        "name": "Chicken Stir Fry",
        "cuisine": "Asian",
        "servings": 4,
        "prep_time": 20,
        "cook_time": 15,
        "difficulty": "easy",
        "ingredients": [
            {"item": "Chicken Breast", "amount": 1.5, "unit": "lb"},
            {"item": "Mixed Vegetables", "amount": 3, "unit": "cups"},
            {"item": "Soy Sauce", "amount": 3, "unit": "tbsp"},
            {"item": "Rice", "amount": 2, "unit": "cups"},
            {"item": "Garlic", "amount": 3, "unit": "cloves"}
        ],
        "instructions": [
            "Cook rice according to package directions",
            "Cut chicken into bite-sized pieces",
            "Heat oil in wok, cook chicken until done",
            "Add vegetables and garlic, stir fry for 5 minutes",
            "Add soy sauce, serve over rice"
        ],
        "nutrition": {
            "calories": 380,
            "protein": 35,
            "carbs": 40,
            "fat": 8
        }
    },
    "recipe-003": {
        "id": "recipe-003",
        "name": "Greek Salad",
        "cuisine": "Mediterranean",
        "servings": 6,
        "prep_time": 15,
        "cook_time": 0,
        "difficulty": "easy",
        "ingredients": [
            {"item": "Tomatoes", "amount": 4, "unit": "large"},
            {"item": "Cucumber", "amount": 1, "unit": "large"},
            {"item": "Red Onion", "amount": 0.5, "unit": "medium"},
            {"item": "Feta Cheese", "amount": 1, "unit": "cup"},
            {"item": "Olives", "amount": 0.5, "unit": "cup"},
            {"item": "Olive Oil", "amount": 3, "unit": "tbsp"}
        ],
        "instructions": [
            "Chop tomatoes, cucumber, and onion",
            "Combine vegetables in large bowl",
            "Add feta cheese and olives",
            "Drizzle with olive oil and toss"
        ],
        "nutrition": {
            "calories": 180,
            "protein": 8,
            "carbs": 12,
            "fat": 14
        }
    }
}

# User favorites storage
user_favorites: Dict[str, List[str]] = {}

# Models
class Ingredient(BaseModel):
    item: str
    amount: float
    unit: str

class NutritionInfo(BaseModel):
    calories: int
    protein: int
    carbs: int
    fat: int

class Recipe(BaseModel):
    id: str
    name: str
    cuisine: str
    servings: int
    prep_time: int
    cook_time: int
    difficulty: str
    ingredients: List[Ingredient]
    instructions: List[str]
    nutrition: NutritionInfo

class ShoppingList(BaseModel):
    recipe_ids: List[str]
    servings_multiplier: float
    ingredients: List[Dict]

# Routes
@app.get("/recipes", response_model=List[Recipe])
@socket.describe(
    "List all recipes",
    response_schema={
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "cuisine": {"type": "string"},
                "servings": {"type": "integer"},
                "prep_time": {"type": "integer"},
                "cook_time": {"type": "integer"},
                "difficulty": {"type": "string"}
            }
        }
    }
)
async def list_recipes(cuisine: Optional[str] = None, difficulty: Optional[str] = None):
    """List all recipes, optionally filtered by cuisine or difficulty."""
    recipes = list(recipes_db.values())
    
    if cuisine:
        recipes = [r for r in recipes if r["cuisine"].lower() == cuisine.lower()]
    
    if difficulty:
        recipes = [r for r in recipes if r["difficulty"] == difficulty]
    
    return recipes


@app.get("/recipes/search")
@socket.describe(
    "Search recipes by name or ingredient",
    response_schema={
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "cuisine": {"type": "string"},
                "servings": {"type": "integer"}
            }
        }
    }
)
async def search_recipes(q: str):
    """Search recipes by name or ingredient."""
    results = []
    query = q.lower()
    
    for recipe in recipes_db.values():
        # Search in recipe name
        if query in recipe["name"].lower():
            results.append(recipe)
            continue
        
        # Search in ingredients
        for ingredient in recipe["ingredients"]:
            if query in ingredient["item"].lower():
                results.append(recipe)
                break
    
    return results


@app.get("/recipes/{recipe_id}", response_model=Recipe)
@socket.describe(
    "Get detailed recipe information",
    response_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "cuisine": {"type": "string"},
            "servings": {"type": "integer"},
            "prep_time": {"type": "integer"},
            "cook_time": {"type": "integer"},
            "difficulty": {"type": "string"},
            "ingredients": {"type": "array"},
            "instructions": {"type": "array"},
            "nutrition": {"type": "object"}
        }
    }
)
async def get_recipe(recipe_id: str):
    """Get detailed information about a specific recipe."""
    if recipe_id not in recipes_db:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return Recipe(**recipes_db[recipe_id])


@app.post("/recipes/{recipe_id}/shopping-list")
@socket.describe(
    "Generate shopping list for a recipe",
    request_schema={
        "type": "object",
        "properties": {
            "servings": {"type": "integer"}
        }
    },
    response_schema={
        "type": "object",
        "properties": {
            "recipe_id": {"type": "string"},
            "recipe_name": {"type": "string"},
            "servings": {"type": "integer"},
            "ingredients": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "string"},
                        "amount": {"type": "number"},
                        "unit": {"type": "string"}
                    }
                }
            }
        }
    },
    examples=['curl -X POST /recipes/{recipe_id}/shopping-list -d \'{"servings":6}\'']
)
async def generate_shopping_list(recipe_id: str, request_body: Optional[Dict] = None):
    """Generate a shopping list for a recipe, optionally scaled for different servings."""
    if recipe_id not in recipes_db:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe = recipes_db[recipe_id]
    requested_servings = request_body.get("servings", recipe["servings"]) if request_body else recipe["servings"]
    multiplier = requested_servings / recipe["servings"]
    
    scaled_ingredients = []
    for ingredient in recipe["ingredients"]:
        scaled_ingredients.append({
            "item": ingredient["item"],
            "amount": ingredient["amount"] * multiplier,
            "unit": ingredient["unit"]
        })
    
    return {
        "recipe_id": recipe_id,
        "recipe_name": recipe["name"],
        "servings": requested_servings,
        "ingredients": scaled_ingredients
    }


@app.post("/shopping-list/multiple")
@socket.describe(
    "Generate combined shopping list for multiple recipes",
    request_schema={
        "type": "object",
        "properties": {
            "recipes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "recipe_id": {"type": "string"},
                        "servings": {"type": "integer"}
                    }
                }
            }
        },
        "required": ["recipes"]
    },
    response_schema={
        "type": "object",
        "properties": {
            "recipes": {"type": "array"},
            "combined_ingredients": {"type": "array"}
        }
    }
)
async def generate_combined_shopping_list(request: Dict):
    """Generate a combined shopping list for multiple recipes."""
    combined_ingredients = {}
    recipe_list = []
    
    for recipe_request in request["recipes"]:
        recipe_id = recipe_request["recipe_id"]
        if recipe_id not in recipes_db:
            continue
        
        recipe = recipes_db[recipe_id]
        requested_servings = recipe_request.get("servings", recipe["servings"])
        multiplier = requested_servings / recipe["servings"]
        
        recipe_list.append({
            "recipe_id": recipe_id,
            "recipe_name": recipe["name"],
            "servings": requested_servings
        })
        
        # Combine ingredients
        for ingredient in recipe["ingredients"]:
            key = f"{ingredient['item']}_{ingredient['unit']}"
            if key in combined_ingredients:
                combined_ingredients[key]["amount"] += ingredient["amount"] * multiplier
            else:
                combined_ingredients[key] = {
                    "item": ingredient["item"],
                    "amount": ingredient["amount"] * multiplier,
                    "unit": ingredient["unit"]
                }
    
    return {
        "recipes": recipe_list,
        "combined_ingredients": list(combined_ingredients.values())
    }


@app.post("/favorites/{user_id}/{recipe_id}")
@socket.describe(
    "Save a recipe to user's favorites",
    response_schema={
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "recipe_id": {"type": "string"},
            "saved": {"type": "boolean"}
        }
    }
)
async def save_favorite(user_id: str, recipe_id: str):
    """Save a recipe to user's favorites."""
    if recipe_id not in recipes_db:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    if user_id not in user_favorites:
        user_favorites[user_id] = []
    
    if recipe_id not in user_favorites[user_id]:
        user_favorites[user_id].append(recipe_id)
    
    return {"user_id": user_id, "recipe_id": recipe_id, "saved": True}


@app.get("/favorites/{user_id}")
@socket.describe(
    "Get user's favorite recipes",
    response_schema={
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "cuisine": {"type": "string"}
            }
        }
    }
)
async def get_favorites(user_id: str):
    """Get all favorite recipes for a user."""
    if user_id not in user_favorites:
        return []
    
    favorites = []
    for recipe_id in user_favorites[user_id]:
        if recipe_id in recipes_db:
            recipe = recipes_db[recipe_id]
            favorites.append({
                "id": recipe["id"],
                "name": recipe["name"],
                "cuisine": recipe["cuisine"]
            })
    
    return favorites


@app.get("/recipes/nutrition/healthy")
@socket.describe(
    "Find healthy recipes under calorie limit",
    response_schema={
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "calories": {"type": "integer"},
                "protein": {"type": "integer"}
            }
        }
    }
)
async def find_healthy_recipes(max_calories: int = 500):
    """Find recipes under a certain calorie limit."""
    healthy_recipes = []
    
    for recipe in recipes_db.values():
        if recipe["nutrition"]["calories"] <= max_calories:
            healthy_recipes.append({
                "id": recipe["id"],
                "name": recipe["name"],
                "calories": recipe["nutrition"]["calories"],
                "protein": recipe["nutrition"]["protein"]
            })
    
    return sorted(healthy_recipes, key=lambda x: x["calories"])


# Initialize socket-agent middleware
SocketAgentMiddleware(
    app,
    name="Recipe Service API",
    description="Recipe discovery, nutrition info, and shopping list generation",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
