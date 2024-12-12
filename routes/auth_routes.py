from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from backend_files.database import users
from backend_files.schemas import UserLogin, UserSignup
from bson import ObjectId


router = APIRouter()

@router.get("/profile/{user_id}")
async def get_profile(user_id: str):
    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user["_id"] = str(user["_id"])
        user.pop("password", None)  
        
        return user
        
    except Exception as e:
        print(f"Profile fetch error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/signout")
def signout():
    return {"status": "success"}

@router.post("/signin")
async def login(user_data: UserLogin):
    try:
        user = users.find_one({"username": user_data.username})
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if user_data.password != user["password"]:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user["_id"] = str(user["_id"])
        user.pop("password", None)  # Remove password from response
        
        return user
        
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/signup")
async def signup(user_data: UserSignup):
    try:
        if users.find_one({"username": user_data.username}):
            raise HTTPException(status_code=400, detail="Username already exists")
        
        default_goals = [
            {
                "id": "1",
                "name": "Retirement Fund",
                "current": 250000,
                "target": 500000,
                "percentage": 50,
                "category": "retirement",
                "targetDate": "2050-01-01"
            },
            {
                "id": "2",
                "name": "Emergency Fund",
                "current": 15000,
                "target": 20000,
                "percentage": 75,
                "category": "emergency",
                "targetDate": "2024-12-31"
            },
            {
                "id": "3",
                "name": "House Down Payment",
                "current": 40000,
                "target": 100000,
                "percentage": 40,
                "category": "housing",
                "targetDate": "2025-06-01"
            }
        ]
        
        user_doc = user_data.model_dump()
        user_doc["membership"] = "REGULAR"
        user_doc["cash"] = 25000.0
        user_doc["role"] = "USER"
        user_doc["portfolio"] = {}
        user_doc["watchlist"] = []
        user_doc["goals"] = default_goals
        
        result = users.insert_one(user_doc)
        
        new_user = users.find_one({"_id": result.inserted_id})
        new_user["_id"] = str(new_user["_id"])
        new_user.pop("password", None)
        
        return new_user
        
    except Exception as e:
        print(f"Signup error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/watchlist/{user_id}")
async def get_watchlist(user_id: str):
    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user.get("watchlist", [])
    except Exception as e:
        print(f"Watchlist fetch error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/watchlist/{user_id}")
async def add_to_watchlist(user_id: str, data: dict):
    try:
        symbol = data.get("symbol")
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol is required")
        
        result = users.update_one(
            {"_id": ObjectId(user_id)},
            {"$addToSet": {"watchlist": symbol}}  # addToSet prevents duplicates
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Failed to add to watchlist")
        
        # Return updated watchlist
        user = users.find_one({"_id": ObjectId(user_id)})
        return user.get("watchlist", [])
        
    except Exception as e:
        print(f"Add to watchlist error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/watchlist/{user_id}/{symbol}")
async def remove_from_watchlist(user_id: str, symbol: str):
    try:
        result = users.update_one(
            {"_id": ObjectId(user_id)},
            {"$pull": {"watchlist": symbol}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Failed to remove from watchlist")
        
        # Return updated watchlist
        user = users.find_one({"_id": ObjectId(user_id)})
        return user.get("watchlist", [])
        
    except Exception as e:
        print(f"Remove from watchlist error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/goals/{user_id}")
async def get_goals(user_id: str):
    try:
        print(f"Attempting to fetch goals for user_id: {user_id}")  # Debug log
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            print(f"User not found: {user_id}")  # Debug log
            raise HTTPException(status_code=404, detail="User not found")
        return {"goals": user.get("goals", [])}
    except Exception as e:
        print(f"Error fetching goals: {str(e)}")  # Debug log
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/goals/{user_id}")
async def update_goals(user_id: str, data: dict):
    try:
        print(f"Attempting to update goals for user_id: {user_id}")  # Debug log
        print(f"Update data: {data}")  # Debug log
        
        # Validate the goals data
        if not isinstance(data.get("goals"), list):
            raise HTTPException(status_code=400, detail="Invalid goals format")
            
        result = users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"goals": data.get("goals", [])}}
        )
        
        print(f"Update result: {result.modified_count}")  # Debug log
        
        if result.modified_count == 0:
            return {"message": "No changes needed"}
            
        return {"message": "Goals updated successfully"}
    except Exception as e:
        print(f"Error updating goals: {str(e)}")  # Debug log
        raise HTTPException(status_code=500, detail=str(e))
