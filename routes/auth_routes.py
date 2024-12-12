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
        
        user_doc = user_data.model_dump()
        user_doc["membership"] = "REGULAR"
        user_doc["cash"] = 25000.0
        user_doc["role"] = "USER"
        user_doc["portfolio"] = {}
        user_doc["watchlist"] = []
        
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
